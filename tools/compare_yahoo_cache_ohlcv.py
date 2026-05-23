"""
Compare OHLCV **values** (open, high, low, close, volume) between Yahoo and cache.

Alignment is by identical bar ``date`` only. For each common date we compare five
scalar values — not merely that a row exists on both sides.

Also compares Yahoo vs ``fetch_ohlcv_yf()`` (what backtest/analysis actually reads).

Usage (repo root, DB_URL set):
    .venv\\Scripts\\python.exe tools\\compare_yahoo_cache_ohlcv.py PFOCUS.NS --days 400
    .venv\\Scripts\\python.exe tools\\compare_yahoo_cache_ohlcv.py PFOCUS.NS --verbose 5
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.data_fetcher import fetch_ohlcv_yf, fetch_ohlcv_yf_raw  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402
from src.infrastructure.persistence.price_cache_repository import (  # noqa: E402
    DEFAULT_INTERVAL,
    WEEKLY_INTERVAL,
    PriceCacheRepository,
)

OHLCV_FIELDS = ("open", "high", "low", "close", "volume")
PRICE_TOLERANCE = 1e-4


@dataclass
class ValueMismatch:
    """Single scalar OHLCV value that differs between two sources."""

    bar_date: date
    field: str
    left_label: str
    left_value: float | int
    right_label: str
    right_value: float | int
    abs_diff: float


@dataclass
class ValueCompareReport:
    """Result of comparing OHLCV scalars on matching bar dates."""

    left_label: str
    right_label: str
    left_bars: int
    right_bars: int
    common_dates: int
    only_left_dates: list[date] = field(default_factory=list)
    only_right_dates: list[date] = field(default_factory=list)
    value_checks: int = 0
    mismatches: list[ValueMismatch] = field(default_factory=list)
    skipped_incomplete_yahoo: list[date] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.value_checks > 0
            and not self.mismatches
            and self.common_dates == self.left_bars == self.right_bars
            and not self.only_left_dates
            and not self.only_right_dates
        )


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Canonical OHLCV frame: normalized date + five numeric columns."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", *OHLCV_FIELDS])

    out = df.copy()
    if "date" not in out.columns:
        raise ValueError("DataFrame missing date column")

    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    for col in OHLCV_FIELDS:
        if col not in out.columns:
            raise ValueError(f"DataFrame missing {col}")
        if col == "volume":
            out[col] = out[col].fillna(0).astype("int64")
        else:
            out[col] = out[col].astype("float64")

    out = out[["date", *OHLCV_FIELDS]].sort_values("date").reset_index(drop=True)
    if out["date"].duplicated().any():
        dupes = out.loc[out["date"].duplicated(), "date"].dt.date.tolist()
        raise ValueError(f"Duplicate bar dates in source: {dupes[:5]}")
    return out


def _is_missing_scalar(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and (math.isnan(value) or pd.isna(value)):
        return True
    return False


def _scalar_equal(field: str, left, right) -> bool:
    if _is_missing_scalar(left) and _is_missing_scalar(right):
        return True
    if _is_missing_scalar(left) or _is_missing_scalar(right):
        return False
    if field == "volume":
        return int(left) == int(right)
    return abs(float(left) - float(right)) <= PRICE_TOLERANCE


def _yahoo_incomplete_bar(row: pd.Series, suffix: str) -> bool:
    """True when Yahoo returned NaN/missing for any OHLC price on this bar."""
    for fld in ("open", "high", "low", "close"):
        col = f"{fld}{suffix}"
        if col not in row.index:
            return False
        if _is_missing_scalar(row[col]):
            return True
    return False


def compare_ohlcv_values(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    left_label: str,
    right_label: str,
) -> ValueCompareReport:
    """
    Compare each OHLCV scalar on bars that share the exact same ``date``.

    Performs ``len(common_dates) × 5`` value comparisons (not bar-count only).
    """
    left_n = _normalize_ohlcv(left)
    right_n = _normalize_ohlcv(right)

    left_dates = {d.date() for d in left_n["date"]}
    right_dates = {d.date() for d in right_n["date"]}
    common = sorted(left_dates & right_dates)
    only_left = sorted(left_dates - right_dates)
    only_right = sorted(right_dates - left_dates)

    report = ValueCompareReport(
        left_label=left_label,
        right_label=right_label,
        left_bars=len(left_n),
        right_bars=len(right_n),
        common_dates=len(common),
        only_left_dates=only_left,
        only_right_dates=only_right,
    )

    if not common:
        return report

    merged = left_n.merge(
        right_n,
        on="date",
        suffixes=("_left", "_right"),
        how="inner",
    )
    report.value_checks = len(merged) * len(OHLCV_FIELDS)

    left_is_yahoo = left_label.lower().startswith("yahoo")

    for _, row in merged.iterrows():
        bar_date = row["date"].date()
        if left_is_yahoo and _yahoo_incomplete_bar(row, "_left"):
            report.skipped_incomplete_yahoo.append(bar_date)
            report.value_checks -= len(OHLCV_FIELDS)
            continue

        for fld in OHLCV_FIELDS:
            lv = row[f"{fld}_left"]
            rv = row[f"{fld}_right"]
            if _scalar_equal(fld, lv, rv):
                continue
            abs_diff = (
                abs(int(lv) - int(rv))
                if fld == "volume" and not _is_missing_scalar(lv) and not _is_missing_scalar(rv)
                else (
                    float("nan")
                    if _is_missing_scalar(lv) or _is_missing_scalar(rv)
                    else abs(float(lv) - float(rv))
                )
            )
            lv_out = int(lv) if fld == "volume" and not _is_missing_scalar(lv) else lv
            rv_out = int(rv) if fld == "volume" and not _is_missing_scalar(rv) else rv
            report.mismatches.append(
                ValueMismatch(
                    bar_date=bar_date,
                    field=fld,
                    left_label=left_label,
                    left_value=lv_out,
                    right_label=right_label,
                    right_value=rv_out,
                    abs_diff=float(abs_diff) if not math.isnan(abs_diff) else float("nan"),
                )
            )

    return report


def _bars_to_df(bars) -> pd.DataFrame:
    rows = [
        {
            "date": b.date,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ]
    return pd.DataFrame(rows)


def _print_report(report: ValueCompareReport, *, verbose: int = 0) -> None:
    print(f"\n--- {report.left_label}  vs  {report.right_label} ---")
    print(
        f"  Bars: {report.left_label}={report.left_bars} "
        f"{report.right_label}={report.right_bars} "
        f"common_dates={report.common_dates}"
    )
    if report.only_left_dates:
        print(
            f"  Dates only in {report.left_label}: {len(report.only_left_dates)} "
            f"sample={report.only_left_dates[:5]}"
        )
    if report.only_right_dates:
        print(
            f"  Dates only in {report.right_label}: {len(report.only_right_dates)} "
            f"sample={report.only_right_dates[:5]}"
        )

    print(
        f"  Value checks: {report.value_checks} "
        f"({report.common_dates} dates × {len(OHLCV_FIELDS)} fields)"
    )
    print(f"  Value mismatches: {len(report.mismatches)}")
    if report.skipped_incomplete_yahoo:
        print(
            f"  Skipped incomplete Yahoo bars (NaN OHLC, not counted): "
            f"{report.skipped_incomplete_yahoo}"
        )

    if report.ok:
        print("  RESULT: PASS — every open/high/low/close/volume scalar matches")
    else:
        print("  RESULT: FAIL — at least one OHLCV scalar differs")

    if verbose > 0 and report.common_dates > 0 and not report.mismatches:
        print(f"  Sample matching bars (first {verbose}, all five fields):")
        # Re-build sample from labels - caller prints via helper
        return

    for mm in report.mismatches[: verbose if verbose > 0 else 10]:
        print(
            f"    {mm.bar_date} {mm.field}: "
            f"{mm.left_label}={mm.left_value} {mm.right_label}={mm.right_value} "
            f"diff={mm.abs_diff}"
        )


def _print_matching_bars_sample(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    left_label: str,
    right_label: str,
    n: int,
) -> None:
    left_n = _normalize_ohlcv(left)
    right_n = _normalize_ohlcv(right)
    merged = left_n.merge(right_n, on="date", suffixes=("_L", "_R")).head(n)
    print(f"  Sample ({n} bars) — full OHLCV values:")
    for _, row in merged.iterrows():
        d = row["date"].date()
        print(f"    {d}  [{left_label}]")
        print(
            f"      O={row['open_L']:.4f} H={row['high_L']:.4f} "
            f"L={row['low_L']:.4f} C={row['close_L']:.4f} V={int(row['volume_L'])}"
        )
        print(f"    {d}  [{right_label}]")
        print(
            f"      O={row['open_R']:.4f} H={row['high_R']:.4f} "
            f"L={row['low_R']:.4f} C={row['close_R']:.4f} V={int(row['volume_R'])}"
        )
        same = all(_scalar_equal(f, row[f"{f}_L"], row[f"{f}_R"]) for f in OHLCV_FIELDS)
        print(f"      all five fields equal: {'yes' if same else 'NO'}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scalar OHLCV value comparison (not bar-count only)",
    )
    parser.add_argument("symbol", nargs="?", default="PFOCUS.NS")
    parser.add_argument("--days", type=int, default=400)
    parser.add_argument(
        "--verbose",
        type=int,
        default=0,
        metavar="N",
        help="Print N sample bars with all OHLCV values, or N mismatches if any",
    )
    args = parser.parse_args()

    end_d = date.today()
    start_d = end_d - timedelta(days=args.days + 5)
    symbol = args.symbol
    end_s = end_d.isoformat()

    print(f"Symbol: {symbol}  range: {start_d} .. {end_d}  lookback_days={args.days}")
    print("Comparison uses identical bar dates; each date compares 5 scalar values.")

    all_ok = True

    for interval in (DEFAULT_INTERVAL, WEEKLY_INTERVAL):
        print(f"\n========== interval={interval} ==========")

        yahoo = fetch_ohlcv_yf_raw(
            symbol,
            days=args.days,
            interval=interval,
            end_date=end_s,
            add_current_day=False,
        )
        via_cache = fetch_ohlcv_yf(
            symbol,
            days=args.days,
            interval=interval,
            end_date=end_s,
            add_current_day=False,
        )

        db = SessionLocal()
        try:
            repo = PriceCacheRepository(db)
            bars = repo.get_range(symbol, start_d, end_d, interval=interval)
            postgres = _bars_to_df(bars)
        finally:
            db.close()

        if yahoo is None or yahoo.empty:
            print("  FAIL: Yahoo returned no data")
            all_ok = False
            continue

        r_yahoo_pg = compare_ohlcv_values(
            yahoo, postgres, left_label="Yahoo", right_label="Postgres"
        )
        _print_report(r_yahoo_pg, verbose=args.verbose)
        all_ok = all_ok and r_yahoo_pg.ok

        if via_cache is None or via_cache.empty:
            print("  FAIL: fetch_ohlcv_yf returned no data")
            all_ok = False
        else:
            r_yahoo_fetch = compare_ohlcv_values(
                yahoo, via_cache, left_label="Yahoo", right_label="fetch_ohlcv_yf"
            )
            _print_report(r_yahoo_fetch, verbose=args.verbose)
            all_ok = all_ok and r_yahoo_fetch.ok

            r_fetch_pg = compare_ohlcv_values(
                via_cache,
                postgres,
                left_label="fetch_ohlcv_yf",
                right_label="Postgres",
            )
            _print_report(r_fetch_pg, verbose=args.verbose)
            all_ok = all_ok and r_fetch_pg.ok

        if args.verbose > 0 and yahoo is not None and via_cache is not None:
            _print_matching_bars_sample(
                yahoo,
                via_cache,
                left_label="Yahoo",
                right_label="fetch_ohlcv_yf",
                n=args.verbose,
            )

    print("\n" + ("OVERALL: PASS" if all_ok else "OVERALL: FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
