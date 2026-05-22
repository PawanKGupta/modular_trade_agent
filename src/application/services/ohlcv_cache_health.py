"""OHLCV cache health assessment and corporate-action sync."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd
from sqlalchemy.orm import Session

from config.settings import OHLCV_CACHE_MIN_COVERAGE_PCT, OHLCV_CACHE_TAIL_OVERLAP_TRADING_DAYS
from src.application.services.ohlcv_cache_service import OhlcvCacheService, _bars_to_dataframe
from src.infrastructure.persistence.price_cache_repository import (
    DEFAULT_INTERVAL,
    PriceCacheRepository,
)
from src.infrastructure.utils.holiday_calendar import get_previous_trading_day, iter_trading_days

logger = logging.getLogger(__name__)

HealthStatus = Literal["ok", "stale", "incomplete", "corrupt"]
RecommendedAction = Literal[
    "none", "gap_fill", "tail_refresh", "segment_refetch", "invalidate_symbol"
]


@dataclass
class PriceCacheHealthReport:
    """Result of assess_price_cache_health."""

    symbol: str
    start_date: date
    end_date: date
    interval: str
    status: HealthStatus
    recommended_action: RecommendedAction
    coverage_pct: float
    message: str
    tail_overlap_skipped: bool = False


def sync_corporate_actions(symbol: str, db: Session) -> int:
    """
    Pull split history from yfinance into corporate_actions table.

    Args:
        symbol: Stock ticker.
        db: Database session.

    Returns:
        Number of split rows upserted.
    """
    import yfinance as yf  # noqa: PLC0415

    repo = PriceCacheRepository(db)
    ticker = yf.Ticker(symbol)
    splits = ticker.splits
    if splits is None or splits.empty:
        return 0

    count = 0
    for ts, ratio in splits.items():
        ex = ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()
        if ratio and float(ratio) != 1.0:
            repo.upsert_corporate_action(symbol, ex, float(ratio), action_type="split")
            count += 1
    return count


def _overlap_crosses_split(
    symbol: str, overlap_start: date, overlap_end: date, repo: PriceCacheRepository
) -> bool:
    actions = repo.list_corporate_actions(symbol, start_date=overlap_start, end_date=overlap_end)
    return any(a.action_type == "split" for a in actions)


def assess_price_cache_health(
    symbol: str,
    start_date: date,
    end_date: date,
    db: Session,
    *,
    interval: str = DEFAULT_INTERVAL,
    min_coverage_pct: float | None = None,
    tail_overlap_days: int | None = None,
    cache_service: OhlcvCacheService | None = None,
) -> PriceCacheHealthReport:
    """
    Assess structural integrity, coverage, and optional tail drift for cached OHLCV.

    Tail Yahoo comparison is skipped when overlap window crosses a recorded split ex_date
    (unadjusted step-down is expected).
    """
    repo = PriceCacheRepository(db)
    min_cov = min_coverage_pct if min_coverage_pct is not None else OHLCV_CACHE_MIN_COVERAGE_PCT
    tail_n = (
        tail_overlap_days
        if tail_overlap_days is not None
        else OHLCV_CACHE_TAIL_OVERLAP_TRADING_DAYS
    )

    expected_days = list(iter_trading_days(start_date, end_date))
    if not expected_days:
        return PriceCacheHealthReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            status="ok",
            recommended_action="none",
            coverage_pct=100.0,
            message="Empty trading-day window",
        )

    bars = repo.get_range(symbol, start_date, end_date, interval=interval)
    cached_dates = {b.date for b in bars}
    coverage_pct = 100.0 * len(cached_dates & set(expected_days)) / len(expected_days)

    if not bars:
        return PriceCacheHealthReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            status="incomplete",
            recommended_action="gap_fill",
            coverage_pct=0.0,
            message="No cached bars in range",
        )

    df = _bars_to_dataframe(bars)
    if df["close"].isna().any() or (df["close"] <= 0).any():
        return PriceCacheHealthReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            status="corrupt",
            recommended_action="invalidate_symbol",
            coverage_pct=coverage_pct,
            message="Invalid close prices in cache",
        )

    if df["date"].duplicated().any():
        return PriceCacheHealthReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            status="corrupt",
            recommended_action="segment_refetch",
            coverage_pct=coverage_pct,
            message="Duplicate dates in cache",
        )

    if coverage_pct < min_cov:
        return PriceCacheHealthReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            status="incomplete",
            recommended_action="gap_fill",
            coverage_pct=coverage_pct,
            message=f"Coverage {coverage_pct:.1f}% below {min_cov}%",
        )

    # Tail overlap check
    overlap_end = end_date
    overlap_start = overlap_end
    for _ in range(tail_n):
        overlap_start = get_previous_trading_day(overlap_start)

    tail_skipped = _overlap_crosses_split(symbol, overlap_start, overlap_end, repo)
    if tail_skipped:
        return PriceCacheHealthReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            status="ok",
            recommended_action="none",
            coverage_pct=coverage_pct,
            message="Tail overlap skipped (split in window)",
            tail_overlap_skipped=True,
        )

    if cache_service is None:
        cache_service = OhlcvCacheService(db)

    try:
        yahoo_tail = cache_service._yahoo_fetch(  # noqa: SLF001
            symbol,
            days=(overlap_end - overlap_start).days + 30,
            interval=interval,
            end_date=overlap_end.isoformat(),
            add_current_day=False,
        )
    except Exception as exc:
        logger.warning("Tail fetch failed for %s: %s", symbol, exc)
        return PriceCacheHealthReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            status="stale",
            recommended_action="tail_refresh",
            coverage_pct=coverage_pct,
            message=f"Tail validation fetch failed: {exc}",
        )

    if yahoo_tail is None or yahoo_tail.empty:
        return PriceCacheHealthReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            status="ok",
            recommended_action="none",
            coverage_pct=coverage_pct,
            message="Tail fetch empty; assuming ok",
        )

    cached_tail = df[(df["date"].dt.date >= overlap_start) & (df["date"].dt.date <= overlap_end)]
    yahoo_tail = yahoo_tail.copy()
    yahoo_tail["date"] = pd.to_datetime(yahoo_tail["date"])
    merged = cached_tail.set_index("date")["close"].to_frame("cached")
    yahoo_close = yahoo_tail.set_index("date")["close"].to_frame("yahoo")
    both = merged.join(yahoo_close, how="inner")
    if both.empty:
        return PriceCacheHealthReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            status="ok",
            recommended_action="none",
            coverage_pct=coverage_pct,
            message="No overlapping tail dates to compare",
        )

    rel_diff = (both["cached"] - both["yahoo"]).abs() / both["yahoo"].replace(0, pd.NA)
    if (rel_diff > 0.02).any():
        return PriceCacheHealthReport(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            status="stale",
            recommended_action="tail_refresh",
            coverage_pct=coverage_pct,
            message="Tail close drift >2% vs Yahoo",
        )

    return PriceCacheHealthReport(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        status="ok",
        recommended_action="none",
        coverage_pct=coverage_pct,
        message="Cache healthy",
    )


def repair_from_health_report(report: PriceCacheHealthReport, db: Session) -> None:
    """Apply recommended_action from a health report."""
    svc = OhlcvCacheService(db)
    if report.recommended_action == "gap_fill":
        svc.gap_fill(
            report.symbol,
            report.start_date,
            report.end_date,
            interval=report.interval,
            yf_end_date=report.end_date.isoformat(),
            add_current_day=False,
        )
    elif report.recommended_action == "tail_refresh":
        svc.refresh_tail(
            report.symbol,
            interval=report.interval,
            yf_end_date=report.end_date.isoformat(),
            add_current_day=False,
        )
    elif report.recommended_action == "invalidate_symbol":
        svc.invalidate_symbol(report.symbol, interval=report.interval)
