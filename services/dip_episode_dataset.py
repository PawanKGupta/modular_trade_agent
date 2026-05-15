"""
Generate dip-buy training rows from historical daily candles.

This module converts the rule-based dip averaging strategy into supervised-learning
examples. Each example represents one "episode":

- Entry when RSI10 drops below 30.
- Adds when RSI10 <= 20, RSI10 <= 10, and on "re-activation" (RSI crosses above 30
  and later crosses back below 30).
- Exit at the first EMA9 touch (close >= ema9) OR RSI10 >= 50, *after the last add*.

Sizing assumption: equal capital per add. PnL% is computed accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from core.backtest_scoring import calculate_wilder_rsi
from utils.logger import logger


@dataclass(frozen=True)
class DipEpisodeParams:
    """Parameters governing episode generation."""

    rsi_entry: float = 30.0
    rsi_add_20: float = 20.0
    rsi_add_10: float = 10.0
    rsi_exit: float = 50.0
    ema_length: int = 9
    rsi_period: int = 10
    min_history_days: int = 260  # ensure rolling features are meaningful
    label_net_win_threshold_pct: float = 1.0
    label_strong_win_threshold_pct: float = 3.0


def _ensure_indicators(df: pd.DataFrame, *, params: DipEpisodeParams) -> pd.DataFrame:
    """
    Ensure required indicator columns exist: rsi_10 and ema9.

    Expects OHLCV columns at minimum: close, and optionally open/high/low/volume.
    """
    if df.empty:
        raise ValueError("Input dataframe is empty")
    required = {"close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    out = df.copy()

    if "rsi_10" not in out.columns:
        out["rsi_10"] = calculate_wilder_rsi(out["close"], period=params.rsi_period)
    if "ema9" not in out.columns:
        try:
            import pandas_ta as ta  # noqa: PLC0415 - optional dependency

            out["ema9"] = ta.ema(out["close"], length=params.ema_length)
        except Exception:
            out["ema9"] = out["close"].ewm(span=params.ema_length, adjust=False).mean()

    return out


def _basic_features(frame: pd.DataFrame, idx: int) -> dict[str, Any]:
    """
    Compute features at the entry index using only data up to idx (inclusive).
    """
    s = frame.iloc[: idx + 1]
    row = frame.iloc[idx]
    close = float(row["close"])
    rsi_10 = float(row["rsi_10"]) if not pd.isna(row["rsi_10"]) else 50.0
    ema9 = float(row["ema9"]) if not pd.isna(row["ema9"]) else close

    # Rolling helpers guarded by available length.
    def _rolling_max(col: str, n: int) -> float:
        tail = s[col].tail(n) if col in s.columns else pd.Series(dtype=float)
        return float(tail.max()) if len(tail) else close

    def _rolling_min(col: str, n: int) -> float:
        tail = s[col].tail(n) if col in s.columns else pd.Series(dtype=float)
        return float(tail.min()) if len(tail) else close

    high20 = _rolling_max("high" if "high" in s.columns else "close", 20)
    low20 = _rolling_min("low" if "low" in s.columns else "close", 20)

    dip_depth_from_20d_high_pct = ((high20 - close) / high20) * 100 if high20 > 0 else 0.0
    support_distance_pct = ((close - low20) / close) * 100 if close > 0 else 0.0
    ema9_distance_pct = ((ema9 - close) / close) * 100 if close > 0 else 0.0

    # Simple volatility proxy using close returns
    if len(s) >= 21:
        ret = s["close"].pct_change().tail(20)
        vol_20d = float(ret.std(ddof=0) * 100) if ret.notna().any() else 0.0
    else:
        vol_20d = 0.0

    # Consecutive red days ending at idx
    if len(s) >= 2:
        diffs = s["close"].diff()
        red = diffs < 0
        consec = 0
        for v in reversed(red.tolist()):
            if v:
                consec += 1
            else:
                break
    else:
        consec = 0

    # Volume ratio vs 20d avg if present.
    volume_ratio = 1.0
    if "volume" in s.columns:
        cur_v = float(row["volume"]) if not pd.isna(row["volume"]) else 0.0
        avg_v = float(s["volume"].tail(20).mean()) if len(s) >= 20 else cur_v
        if avg_v and avg_v > 0:
            volume_ratio = cur_v / avg_v

    return {
        "rsi_10": rsi_10,
        "ema9_distance_pct": ema9_distance_pct,
        "dip_depth_from_20d_high_pct": dip_depth_from_20d_high_pct,
        "support_distance_pct": support_distance_pct,
        "consecutive_red_days": float(consec),
        "volume_ratio": float(volume_ratio),
        "volatility_20d_pct": vol_20d,
    }


def generate_dip_episode_rows(
    df: pd.DataFrame,
    *,
    ticker: str,
    params: DipEpisodeParams | None = None,
) -> pd.DataFrame:
    """
    Generate one training row per dip "episode".

    Args:
        df: Daily candle frame sorted by date ascending. Columns: date (optional index),
            open/high/low/close/volume. If index is not datetime-like, the caller should
            supply a `date` column.
        ticker: Ticker symbol for metadata.
        params: Episode/label parameters.

    Returns:
        DataFrame with one row per episode containing features at entry and outcome labels.
    """
    p = params or DipEpisodeParams()
    frame = _ensure_indicators(df, params=p)
    frame = frame.copy()

    if "date" in frame.columns:
        dates = pd.to_datetime(frame["date"])
    else:
        dates = pd.to_datetime(frame.index)
    frame["__date"] = dates
    frame = frame.sort_values("__date").reset_index(drop=True)

    if len(frame) < p.min_history_days:
        logger.info("Dip dataset: %s skipped (only %s rows)", ticker, len(frame))
        return pd.DataFrame()

    episodes: list[dict[str, Any]] = []

    in_episode = False
    entry_idx = -1
    entry_features: dict[str, Any] | None = None
    entry_prices: list[float] = []
    last_add_idx = -1
    last_seen_rsi_above_30 = False
    add_flags = {"rsi20": False, "rsi10": False}

    for i, row in frame.iterrows():
        rsi = row["rsi_10"]
        if pd.isna(rsi):
            continue
        rsi_f = float(rsi)

        # Track reset: RSI > 30.
        if rsi_f > p.rsi_entry:
            last_seen_rsi_above_30 = True
            add_flags["rsi20"] = False
            add_flags["rsi10"] = False

        # Start a new episode on the first RSI<30.
        if not in_episode and rsi_f < p.rsi_entry:
            in_episode = True
            entry_idx = i
            entry_features = _basic_features(frame, i)
            entry_prices = [float(row["close"])]
            last_add_idx = i
            last_seen_rsi_above_30 = False
            add_flags = {"rsi20": False, "rsi10": False}
            continue

        if not in_episode:
            continue

        # Add logic: first time RSI hits <=20/<=10 OR after reset (RSI>30 then <30).
        did_add = False
        if rsi_f <= p.rsi_add_10:
            if not add_flags["rsi10"] or last_seen_rsi_above_30:
                entry_prices.append(float(row["close"]))
                last_add_idx = i
                add_flags["rsi10"] = True
                last_seen_rsi_above_30 = False
                did_add = True
        elif rsi_f <= p.rsi_add_20:
            if not add_flags["rsi20"] or last_seen_rsi_above_30:
                entry_prices.append(float(row["close"]))
                last_add_idx = i
                add_flags["rsi20"] = True
                last_seen_rsi_above_30 = False
                did_add = True
        elif rsi_f < p.rsi_entry:
            # Re-activation add: only after RSI > 30 was seen (reset), then RSI drops <30 again.
            if last_seen_rsi_above_30:
                entry_prices.append(float(row["close"]))
                last_add_idx = i
                last_seen_rsi_above_30 = False
                did_add = True

        # Exit only after the last add: first EMA9 touch OR RSI>=50.
        if i > last_add_idx:
            close = float(row["close"])
            ema9 = float(row["ema9"]) if not pd.isna(row["ema9"]) else close
            ema_touch = close >= ema9
            rsi_exit = rsi_f >= p.rsi_exit
            if ema_touch or rsi_exit:
                assert entry_features is not None
                exit_price = close
                # Equal capital per add => PnL% = (exit * avg(1/p_i)) - 1
                inv_prices = [1.0 / px for px in entry_prices if px > 0]
                if not inv_prices:
                    break
                pnl_pct = (exit_price * (sum(inv_prices) / len(inv_prices)) - 1.0) * 100.0
                net_win = 1 if pnl_pct >= p.label_net_win_threshold_pct else 0
                strong_win = 1 if pnl_pct >= p.label_strong_win_threshold_pct else 0

                episodes.append(
                    {
                        "ticker": ticker,
                        "entry_date": frame.loc[entry_idx, "__date"].date().isoformat(),
                        "exit_date": frame.loc[i, "__date"].date().isoformat(),
                        "n_adds": len(entry_prices),
                        "pnl_pct": float(round(pnl_pct, 4)),
                        "net_win": net_win,
                        "strong_win": strong_win,
                        **entry_features,
                    }
                )

                # Reset episode state.
                in_episode = False
                entry_idx = -1
                entry_features = None
                entry_prices = []
                last_add_idx = -1
                last_seen_rsi_above_30 = False
                add_flags = {"rsi20": False, "rsi10": False}
                continue

        # If we added today, we must wait for a later day to exit.
        if did_add:
            continue

    if not episodes:
        return pd.DataFrame()

    out = pd.DataFrame(episodes)
    # Stable column order: metadata, labels, then features.
    meta = ["ticker", "entry_date", "exit_date", "n_adds"]
    labels = ["pnl_pct", "net_win", "strong_win"]
    feat_cols = [c for c in out.columns if c not in meta + labels]
    return out[meta + labels + sorted(feat_cols)]
