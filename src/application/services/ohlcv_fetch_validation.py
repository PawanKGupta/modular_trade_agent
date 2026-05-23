"""
Validate Yahoo OHLCV frames at ingest time (before writing to price_cache).

Used to detect API failures, corrupt rows, and insufficient history so EMA/RSI
are not computed on bad data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd

from config.settings import OHLCV_CACHE_MIN_COVERAGE_PCT
from src.infrastructure.persistence.price_cache_repository import (
    DEFAULT_INTERVAL,
    WEEKLY_INTERVAL,
    PriceCacheRepository,
    week_has_cached_bar,
)
from src.infrastructure.utils.holiday_calendar import (
    iter_expected_weekly_bar_dates,
    iter_trading_days,
)

FetchStatus = Literal["ok", "partial", "failed"]

OHLCV_FIELDS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class FetchValidationResult:
    """Outcome of validating a Yahoo OHLCV DataFrame for cache ingest."""

    status: FetchStatus
    message: str
    coverage_pct: float = 0.0
    row_count: int = 0
    invalid_ohlc_rows: int = 0
    duplicate_dates: int = 0


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "date" not in out.columns:
        raise ValueError("DataFrame missing date column")
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    for col in OHLCV_FIELDS:
        if col not in out.columns:
            raise ValueError(f"DataFrame missing {col}")
    return out.sort_values("date").reset_index(drop=True)


def _is_missing_price(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and (math.isnan(value) or pd.isna(value)):
        return True
    return False


def validate_yahoo_ohlcv_frame(
    df: pd.DataFrame | None,
    *,
    symbol: str,
    interval: str,
    start_date: date,
    end_date: date,
    min_coverage_pct: float | None = None,
) -> FetchValidationResult:
    """
    Structural + coverage validation for a Yahoo OHLCV fetch.

    Args:
        df: Raw Yahoo frame (lowercase OHLCV + date).
        symbol: Ticker (logging context).
        interval: ``1d`` or ``1wk``.
        start_date: Intended cache window start.
        end_date: Intended cache window end.
        min_coverage_pct: Minimum coverage to mark ``ok`` (else ``partial``).

    Returns:
        FetchValidationResult with status ok | partial | failed.
    """
    min_cov = min_coverage_pct if min_coverage_pct is not None else OHLCV_CACHE_MIN_COVERAGE_PCT

    if df is None or df.empty:
        return FetchValidationResult(
            status="failed",
            message=f"{symbol} [{interval}]: empty Yahoo response",
        )

    try:
        frame = _normalize_frame(df)
    except ValueError as exc:
        return FetchValidationResult(status="failed", message=str(exc))

    dupes = int(frame["date"].duplicated().sum())
    if dupes:
        return FetchValidationResult(
            status="failed",
            message=f"{symbol} [{interval}]: {dupes} duplicate dates in Yahoo data",
            duplicate_dates=dupes,
            row_count=len(frame),
        )

    in_window = frame[(frame["date"].dt.date >= start_date) & (frame["date"].dt.date <= end_date)]
    if in_window.empty:
        return FetchValidationResult(
            status="failed",
            message=f"{symbol} [{interval}]: no bars in window {start_date}..{end_date}",
            row_count=len(frame),
        )

    invalid = 0
    rows = list(in_window.iterrows())
    for i, (_, row) in enumerate(rows):
        is_last = i == len(rows) - 1
        for fld in ("open", "high", "low", "close"):
            val = row[fld]
            if _is_missing_price(val):
                if is_last and interval == DEFAULT_INTERVAL:
                    continue
                invalid += 1
                break
            if float(val) <= 0:
                invalid += 1
                break
        if invalid:
            break
        if float(row["high"]) < float(row["low"]):
            invalid += 1
            break
        vol = row["volume"]
        if _is_missing_price(vol) or int(vol) < 0:
            invalid += 1
            break

    if invalid:
        return FetchValidationResult(
            status="failed",
            message=f"{symbol} [{interval}]: {invalid} bars with invalid OHLCV",
            row_count=len(in_window),
            invalid_ohlc_rows=invalid,
        )

    repo_stub_coverage = _coverage_for_frame(in_window, start_date, end_date, interval)
    status: FetchStatus = "ok" if repo_stub_coverage >= min_cov else "partial"
    msg = f"{symbol} [{interval}]: {len(in_window)} bars, coverage={repo_stub_coverage:.1f}%"
    if status == "partial":
        msg += f" (below {min_cov}% — short history or listing; use with care for long EMA)"

    return FetchValidationResult(
        status=status,
        message=msg,
        coverage_pct=repo_stub_coverage,
        row_count=len(in_window),
    )


def _coverage_for_frame(
    frame: pd.DataFrame,
    start_date: date,
    end_date: date,
    interval: str,
) -> float:
    """Approximate coverage for the fetched frame (matches cache repo logic)."""
    cached_dates = {d.date() for d in frame["date"]}
    if interval == WEEKLY_INTERVAL:
        expected = list(iter_expected_weekly_bar_dates(start_date, end_date))
        if not expected:
            return 100.0
        hits = sum(1 for d in expected if week_has_cached_bar(cached_dates, d))
        return 100.0 * hits / len(expected)

    expected = list(iter_trading_days(start_date, end_date))
    if not expected:
        return 100.0
    hits = sum(1 for d in expected if d in cached_dates)
    return 100.0 * hits / len(expected)


def validate_cached_symbol(
    repo: PriceCacheRepository,
    symbol: str,
    start_date: date,
    end_date: date,
    interval: str = DEFAULT_INTERVAL,
    *,
    min_coverage_pct: float | None = None,
) -> FetchValidationResult:
    """
    Validate rows already in price_cache for a symbol/window (post-upsert check).
    """
    min_cov = min_coverage_pct if min_coverage_pct is not None else OHLCV_CACHE_MIN_COVERAGE_PCT
    bars = repo.get_range(symbol, start_date, end_date, interval=interval)
    if not bars:
        return FetchValidationResult(
            status="failed",
            message=f"{symbol} [{interval}]: no rows in cache for window",
        )

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
    return validate_yahoo_ohlcv_frame(
        pd.DataFrame(rows),
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        min_coverage_pct=min_cov,
    )
