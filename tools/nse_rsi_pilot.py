"""
Pilot: compare RSI(10) from NSE UDiFF bhavcopy vs Yahoo vs TradingView reference.

Usage (repo root):
    .venv/bin/python tools/nse_rsi_pilot.py
    .venv/bin/python tools/nse_rsi_pilot.py --symbols DMART LINDEINDIA AXISCADES --days 420
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pandas_ta as ta

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from config.settings import NSE_BHAVCOPY_CACHE_DIR  # noqa: E402
from core.data_fetcher import fetch_ohlcv_yf  # noqa: E402
from src.infrastructure.data_providers.nse_bhavcopy_fetcher import (  # noqa: E402
    NseBhavcopyFetcher,
    find_equity_bar,
)
from src.infrastructure.data_providers.nse_symbol import base_from_cache_ticker  # noqa: E402

TV_RSI_JUN2 = {
    "DMART": 27.44,
    "LINDEINDIA": 31.24,
    "AXISCADES": 24.44,
}

TV_CLOSE_JUN2 = {
    "DMART": 4057.0,
    "LINDEINDIA": 6940.0,
    "AXISCADES": 1682.2,
}

RSI_PERIOD = 10
LOOKBACK_CALENDAR_DAYS = 600


def fetch_nse_closes(
    symbols: list[str],
    end_date: date,
    *,
    calendar_lookback: int,
    fetcher: NseBhavcopyFetcher,
) -> pd.DataFrame:
    """Build date x symbol close matrix from NSE bhavcopy."""
    sym_set = {base_from_cache_ticker(s) for s in symbols}
    rows: list[dict] = []
    start = end_date - timedelta(days=calendar_lookback)
    d = end_date
    fetched = 0
    while d >= start:
        df = fetcher.download_bhavcopy(d)
        if df is not None:
            fetched += 1
            for sym in sym_set:
                bar = find_equity_bar(df, sym)
                if bar is not None:
                    rows.append(
                        {
                            "date": bar.trade_date,
                            "symbol": sym,
                            "close": bar.close,
                        }
                    )
        d -= timedelta(days=1)

    if not rows:
        raise RuntimeError("No NSE bhavcopy rows downloaded — check network / dates")

    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")
    print(f"NSE: downloaded {fetched} trading-day files, {len(frame)} symbol-bars")
    return frame


def fetch_yahoo_closes(symbols: list[str], days: int = 800) -> pd.DataFrame:
    rows: list[dict] = []
    for sym in symbols:
        base = base_from_cache_ticker(sym)
        ticker = f"{base}.NS"
        df = fetch_ohlcv_yf(ticker, days=days)
        if df is None or df.empty:
            print(f"Yahoo: no data for {ticker}")
            continue
        for _, row in df.iterrows():
            rows.append(
                {
                    "date": pd.to_datetime(row["date"]).normalize(),
                    "symbol": base,
                    "close": float(row["close"]),
                }
            )
    return pd.DataFrame(rows)


def rsi_on_date(close_series: pd.Series, on_date: date, period: int = RSI_PERIOD) -> float | None:
    s = close_series.dropna().sort_index()
    target = pd.Timestamp(on_date).normalize()
    s = s.loc[s.index <= target]
    if len(s) < period + 1:
        return None
    rsi = ta.rsi(s, length=period)
    if rsi is None or rsi.empty or pd.isna(rsi.iloc[-1]):
        return None
    return float(rsi.iloc[-1])


def close_on_date(close_series: pd.Series, on_date: date) -> float | None:
    s = close_series.dropna().sort_index()
    target = pd.Timestamp(on_date).normalize()
    hits = s.loc[s.index == target]
    if hits.empty:
        hits = s.loc[s.index <= target]
        if hits.empty:
            return None
        return float(hits.iloc[-1])
    return float(hits.iloc[-1])


def compare_close_diffs(
    nse: pd.DataFrame,
    yahoo: pd.DataFrame,
    symbols: list[str],
    *,
    last_n: int = 20,
) -> None:
    print("\n--- Recent close diffs (NSE - Yahoo), last bars ---")
    bases = [base_from_cache_ticker(s) for s in symbols]
    for sym in bases:
        n = nse[nse["symbol"] == sym].set_index("date")["close"].sort_index()
        y = yahoo[yahoo["symbol"] == sym].set_index("date")["close"].sort_index()
        common = n.index.intersection(y.index)
        if common.empty:
            print(f"  {sym}: no overlapping dates")
            continue
        common = common.sort_values()[-last_n:]
        diffs = []
        for dt in common:
            diff = float(n.loc[dt] - y.loc[dt])
            if abs(diff) > 1e-4:
                diffs.append((dt.date(), diff, float(n.loc[dt]), float(y.loc[dt])))
        if not diffs:
            print(f"  {sym}: last {len(common)} bars — all closes match Yahoo")
        else:
            print(f"  {sym}: {len(diffs)} mismatches in last {len(common)} common bars")
            for dt, diff, nc, yc in diffs[-5:]:
                print(f"    {dt}  NSE={nc:.2f}  Yahoo={yc:.2f}  diff={diff:+.4f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="NSE vs Yahoo RSI pilot")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["DMART", "LINDEINDIA", "AXISCADES"],
    )
    parser.add_argument("--end-date", default="2026-06-02", help="As-of date (YYYY-MM-DD)")
    parser.add_argument("--calendar-lookback", type=int, default=LOOKBACK_CALENDAR_DAYS)
    parser.add_argument("--cache-dir", default=NSE_BHAVCOPY_CACHE_DIR)
    args = parser.parse_args()

    end_date = date.fromisoformat(args.end_date)
    symbols = [base_from_cache_ticker(s) for s in args.symbols]
    fetcher = NseBhavcopyFetcher(cache_dir=args.cache_dir)

    print(f"Pilot as-of {end_date}  symbols={symbols}")
    print(f"Cache: {args.cache_dir}\n")

    nse = fetch_nse_closes(
        symbols,
        end_date,
        calendar_lookback=args.calendar_lookback,
        fetcher=fetcher,
    )
    yahoo = fetch_yahoo_closes(symbols, days=800)
    compare_close_diffs(nse, yahoo, symbols)

    print("\n--- RSI(10) comparison ---")
    print(f"{'Symbol':<12} {'Close':>8} {'NSE RSI':>9} {'Yahoo RSI':>10} {'TV RSI':>8} {'NSE-TV':>8} {'Yahoo-TV':>9}")
    print("-" * 78)

    verdict_rows = []
    for sym in symbols:
        n = nse[nse["symbol"] == sym].set_index("date")["close"].sort_index()
        y = yahoo[yahoo["symbol"] == sym].set_index("date")["close"].sort_index()

        nse_rsi = rsi_on_date(n, end_date)
        yahoo_rsi = rsi_on_date(y, end_date)
        nse_close = close_on_date(n, end_date)
        tv_rsi = TV_RSI_JUN2.get(sym)
        tv_close = TV_CLOSE_JUN2.get(sym)

        nse_delta = (nse_rsi - tv_rsi) if (nse_rsi is not None and tv_rsi is not None) else None
        yahoo_delta = (yahoo_rsi - tv_rsi) if (yahoo_rsi is not None and tv_rsi is not None) else None

        print(
            f"{sym:<12} "
            f"{nse_close or 0:8.2f} "
            f"{nse_rsi if nse_rsi is not None else float('nan'):9.2f} "
            f"{yahoo_rsi if yahoo_rsi is not None else float('nan'):10.2f} "
            f"{tv_rsi if tv_rsi is not None else float('nan'):8.2f} "
            f"{nse_delta if nse_delta is not None else float('nan'):+8.2f} "
            f"{yahoo_delta if yahoo_delta is not None else float('nan'):+9.2f}"
        )
        verdict_rows.append(
            {
                "abs_nse_tv": abs(nse_delta) if nse_delta is not None else None,
                "abs_yahoo_tv": abs(yahoo_delta) if yahoo_delta is not None else None,
            }
        )

    prev_dates = sorted(nse["date"].unique())
    prev_dates = [d for d in prev_dates if pd.Timestamp(d).date() < end_date]
    if prev_dates:
        prev_td = pd.Timestamp(prev_dates[-1]).date()
        print(f"\n--- Previous session ({prev_td}) — 9:01 morning equivalent ---")
        for sym in symbols:
            n = nse[nse["symbol"] == sym].set_index("date")["close"].sort_index()
            y = yahoo[yahoo["symbol"] == sym].set_index("date")["close"].sort_index()
            print(
                f"  {sym}: NSE RSI={rsi_on_date(n, prev_td):.2f}  "
                f"Yahoo RSI={rsi_on_date(y, prev_td):.2f}"
            )

    print("\n--- Verdict ---")
    nse_wins = sum(
        1
        for r in verdict_rows
        if r["abs_nse_tv"] is not None
        and r["abs_yahoo_tv"] is not None
        and r["abs_nse_tv"] < r["abs_yahoo_tv"]
    )
    nse_avg = [r["abs_nse_tv"] for r in verdict_rows if r["abs_nse_tv"] is not None]
    yahoo_avg = [r["abs_yahoo_tv"] for r in verdict_rows if r["abs_yahoo_tv"] is not None]
    if nse_avg and yahoo_avg:
        print(f"  Mean |RSI - TV|: NSE={sum(nse_avg)/len(nse_avg):.3f}  Yahoo={sum(yahoo_avg)/len(yahoo_avg):.3f}")
    print(f"  NSE closer to TV on {nse_wins}/{len(verdict_rows)} symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
