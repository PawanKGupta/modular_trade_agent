#!/usr/bin/env python3
"""Cross-check ``bulk_analysis_final_*.csv`` vs ``trade_agent`` recommendation gates.

Replays ``_passes_backtest_quality_filters`` and buy inclusion rules when
``enable_backtest_scoring=True`` and ``ml_enabled=False`` (default CLI).

Usage (repo root)::

    .venv\\Scripts\\python.exe tools/validate_bulk_analysis_final.py
    .venv\\Scripts\\python.exe tools/validate_bulk_analysis_final.py \\
        analysis_results/bulk_analysis_final_YYYYMMDD_HHMMSS.csv
"""

from __future__ import annotations

import argparse
import ast
import glob
import os
import re
import sys
from collections import Counter

import pandas as pd

# Mirror ``trade_agent._process_results`` defaults (backtest path, ml off).
_MIN_COMBINED_SCORE_BUY = 25
_MIN_BACKTEST_SCORE_QUALITY = 45.0
_MIN_WIN_RATE = 65.0
_MIN_AVG_PROFIT = 1.5


def _clean_numpy_repr(s: str) -> str:
    s = re.sub(r"np\.float64\(([^)]+)\)", r"\1", s)
    return s.replace("np.True_", "True").replace("np.False_", "False")


def parse_dict_cell(val) -> dict:
    """Parse a CSV cell that was written as a Python dict repr (with numpy scalars)."""
    if pd.isna(val):
        return {}
    raw = str(val).strip()
    if not raw:
        return {}
    try:
        return ast.literal_eval(_clean_numpy_repr(raw))
    except (SyntaxError, ValueError) as e:
        raise ValueError(f"Cannot parse dict cell: {e}") from e


def _normalize_total_trades(raw) -> int:
    if raw is None:
        return 0
    if isinstance(raw, str):
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 0
    if isinstance(raw, (int, float)):
        return int(raw)
    return 0


def passes_backtest_quality_filters(
    result: dict,
    *,
    min_win_rate: float = _MIN_WIN_RATE,
    min_avg_profit: float = _MIN_AVG_PROFIT,
    min_backtest_score: float = _MIN_BACKTEST_SCORE_QUALITY,
    require_positive_return: bool = True,
) -> bool:
    """Mirror ``trade_agent._process_results._passes_backtest_quality_filters``."""

    backtest = result.get("backtest") or {}
    if not backtest:
        return True

    total_trades = _normalize_total_trades(backtest.get("total_trades", 0))

    win_rate = float(backtest.get("win_rate") or 0)
    avg_return = float(backtest.get("avg_return") or 0)
    total_return = float(backtest.get("total_return_pct") or 0)
    backtest_score = float(backtest.get("score") or 0)

    if total_trades == 0:
        return bool(backtest_score >= min_backtest_score)

    trade_based_ok = (
        win_rate >= min_win_rate
        and avg_return >= min_avg_profit
        and (not require_positive_return or total_return > 0)
        and backtest_score >= min_backtest_score
    )
    return trade_based_ok


def would_recommend_buy(row: pd.Series, *, ml_enabled: bool = False) -> bool:
    """Buy list gate when backtest scoring on and ML paths ignored."""

    if row["status"] != "success":
        return False
    if ml_enabled:
        raise NotImplementedError("Use defaults only; ML branches not mirrored here.")
    backtest = parse_dict_cell(row["backtest"])
    wrapped = {"backtest": backtest}
    if not passes_backtest_quality_filters(wrapped):
        return False
    return (
        row["final_verdict"] in ("buy", "strong_buy")
        and float(row["combined_score"]) >= _MIN_COMBINED_SCORE_BUY
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=None,
        help="Path to bulk_analysis_final CSV (default: newest under analysis_results/)",
    )
    args = parser.parse_args()

    path = args.csv_path
    if path is None:
        finals = glob.glob(os.path.join("analysis_results", "bulk_analysis_final_*.csv"))
        if not finals:
            print("No analysis_results/bulk_analysis_final_*.csv found.", file=sys.stderr)
            return 1
        path = max(finals, key=os.path.getmtime)

    df = pd.read_csv(path)
    required = {"ticker", "status", "verdict", "final_verdict", "combined_score", "backtest"}
    missing = required - set(df.columns)
    if missing:
        print(f"CSV missing columns {missing}", file=sys.stderr)
        return 1

    buy_tickers = [row["ticker"] for _, row in df.iterrows() if would_recommend_buy(row)]

    print(f"File: {path}")
    print(f"Rows: {len(df)}")
    print(f"Recommended (buy list, ml_enabled=False): {buy_tickers or '(none)'}")

    if "backtest_mode" in df.columns:
        modes = Counter(str(v) for v in df["backtest_mode"].fillna(""))
        print(f"backtest_mode counts: {dict(modes)}")
        expect_integrated = os.getenv("BULK_EXPECT_INTEGRATED_BACKTEST", "").lower() in (
            "1",
            "true",
            "yes",
        )
        if expect_integrated and modes.get("simple_fallback", 0) > 0:
            print(
                "ERROR: BULK_EXPECT_INTEGRATED_BACKTEST set but CSV has simple_fallback rows.",
                file=sys.stderr,
            )
            return 1
    else:
        print("backtest_mode column: (missing — re-run trade_agent.py --backtest after Phase 0)")
    print()

    failed = False
    for _, row in df.iterrows():
        bt = parse_dict_cell(row["backtest"])
        pf = passes_backtest_quality_filters({"backtest": bt})
        rec = would_recommend_buy(row)
        print(
            f"{row['ticker']:<16} verdict={row['verdict']:<10} final={row['final_verdict']:<10} "
            f"comb={float(row['combined_score']):6.2f} bt_score={float(bt.get('score') or 0):6.2f} "
            f"trades={int(bt.get('total_trades') or 0):3d} quality_ok={pf!s:<5} recommend={rec!s}"
        )

        # Documented edge case: final_verdict can be buy while quality gate excludes alerting.
        low_bt = float(bt.get("score") or 0) < _MIN_BACKTEST_SCORE_QUALITY
        if row["final_verdict"] == "buy" and low_bt:
            if rec:
                msg = (
                    f"  ERROR: {row['ticker']} final=buy with bt_score "
                    f"<{_MIN_BACKTEST_SCORE_QUALITY} should not be recommended."
                )
                print(msg, file=sys.stderr)
                failed = True

    if failed:
        return 1
    print("\nOK: gates consistent with trade_agent.py (backtest on, ml off).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
