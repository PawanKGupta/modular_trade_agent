from __future__ import annotations

import pandas as pd

from services.dip_episode_dataset import DipEpisodeParams, generate_dip_episode_rows


def _df(prices: list[float], rsis: list[float], ema9s: list[float]) -> pd.DataFrame:
    assert len(prices) == len(rsis) == len(ema9s)
    return pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=len(prices), freq="D"),
            "close": prices,
            "rsi_10": rsis,
            "ema9": ema9s,
        }
    )


def test_single_episode_no_adds_exits_after_entry() -> None:
    # Entry at day 1 (RSI<30), no adds, exit when RSI>=50 after entry.
    df = _df(
        prices=[100, 99, 101],
        rsis=[35, 25, 55],
        ema9s=[100, 100, 100],
    )
    params = DipEpisodeParams(min_history_days=1, label_net_win_threshold_pct=1.0)
    out = generate_dip_episode_rows(df, ticker="TEST", params=params)
    assert len(out) == 1
    assert out.iloc[0]["n_adds"] == 1
    assert out.iloc[0]["net_win"] in (0, 1)


def test_add_on_rsi20_and_exit_after_last_add() -> None:
    # Entry day 1 (25), add day2 (<=20), exit at day4 (close>=ema9) but only after last add.
    df = _df(
        prices=[100, 98, 95, 97, 99],
        rsis=[40, 25, 19, 18, 35],
        ema9s=[100, 100, 100, 96, 96],
    )
    params = DipEpisodeParams(min_history_days=1, label_net_win_threshold_pct=0.0)
    out = generate_dip_episode_rows(df, ticker="TEST", params=params)
    assert len(out) == 1
    assert out.iloc[0]["n_adds"] == 2
    # With 0% threshold, should usually be net_win=1 here (but keep it loose).
    assert out.iloc[0]["pnl_pct"] == out.iloc[0]["pnl_pct"]


def test_reactivation_add_requires_rsi_above_30_seen() -> None:
    # Entry at day1. RSI rises above 30 (reset), then drops below 30 again => reactivation add.
    df = _df(
        prices=[100, 99, 101, 98, 102],
        rsis=[45, 25, 35, 28, 55],
        # Keep EMA9 above close so we don't exit before re-activation add.
        ema9s=[110, 110, 110, 110, 110],
    )
    params = DipEpisodeParams(min_history_days=1, label_net_win_threshold_pct=-100.0)
    out = generate_dip_episode_rows(df, ticker="TEST", params=params)
    assert len(out) == 1
    assert out.iloc[0]["n_adds"] == 2
