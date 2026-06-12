"""NSE bhavcopy publish-window helpers (ingest gate + indicator same-day close policy)."""

from __future__ import annotations

import time
from datetime import date, time as dt_time

from config.settings import (
    NSE_BHAVCOPY_EARLIEST_IST,
    NSE_BHAVCOPY_PUBLISH_PROBE_TTL_S,
    daily_ohlcv_uses_nse,
)
from src.infrastructure.db.timezone_utils import ist_now
from utils.logger import logger

# Process-local probe cache: {iso_date: (published: bool, monotonic_ts)}
_publish_probe_cache: dict[str, tuple[bool, float]] = {}

NSE_SESSION_CLOSE = dt_time(15, 30)


def _parse_earliest_ist_time() -> dt_time:
    """Parse ``NSE_BHAVCOPY_EARLIEST_IST`` (``HH:MM``) for earliest same-day ingest attempt."""
    raw = (NSE_BHAVCOPY_EARLIEST_IST or "17:30").strip()
    parts = raw.split(":")
    if len(parts) != 2:
        logger.warning("Invalid NSE_BHAVCOPY_EARLIEST_IST=%r; using 17:30", raw)
        return dt_time(17, 30)
    try:
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("out of range")
        return dt_time(hour, minute)
    except ValueError:
        logger.warning("Invalid NSE_BHAVCOPY_EARLIEST_IST=%r; using 17:30", raw)
        return dt_time(17, 30)


def reset_nse_bhavcopy_publish_probe_cache() -> None:
    """Clear cached publish probe results (tests)."""
    _publish_probe_cache.clear()


def nse_bhavcopy_ingest_allowed_for_date(trade_date: date) -> bool:
    """
  Whether NSE gap-fill / ingest may attempt ``trade_date``.

  Historical dates are always allowed. Calendar today is gated by session,
  trading-day calendar, and ``NSE_BHAVCOPY_EARLIEST_IST``.
  """
    today_ist = ist_now().date()
    if trade_date != today_ist:
        return True
    return nse_bhavcopy_ingest_allowed_for_today()


def nse_bhavcopy_ingest_allowed_for_today() -> bool:
    """
    Whether HTTP ingest for **calendar today** is allowed now.

    False during the cash session, on non-trading days, and before the configured
    earliest IST time (default 17:30). Does not guarantee the zip exists yet.
    """
    from core.volume_analysis import is_market_hours  # noqa: PLC0415
    from src.infrastructure.utils.holiday_calendar import is_trading_day  # noqa: PLC0415

    today_ist = ist_now().date()
    if not is_trading_day(today_ist):
        return False
    if is_market_hours():
        return False
    if ist_now().time() < _parse_earliest_ist_time():
        return False
    return True


def nse_bhavcopy_eod_available() -> bool:
    """Backward-compatible alias: same as ``nse_bhavcopy_ingest_allowed_for_today()``."""
    return nse_bhavcopy_ingest_allowed_for_today()


def nse_today_bhavcopy_published(*, force_probe: bool = False) -> bool:
    """
    True when today's UDiFF final bhavcopy is known to exist (disk cache or HTTP probe).

    Probes are skipped before ``nse_bhavcopy_ingest_allowed_for_today()`` to avoid
    pointless 404s when operators run evening tasks early via the schedule UI.
    """
    if not daily_ohlcv_uses_nse():
        return False

    today_ist = ist_now().date()
    cache_key = today_ist.isoformat()
    if not force_probe and cache_key in _publish_probe_cache:
        published, cached_at = _publish_probe_cache[cache_key]
        if time.monotonic() - cached_at < NSE_BHAVCOPY_PUBLISH_PROBE_TTL_S:
            return published

    from src.infrastructure.data_providers.nse_bhavcopy_fetcher import (  # noqa: PLC0415
        NseBhavcopyFetcher,
    )

    fetcher = NseBhavcopyFetcher()
    if fetcher.has_cached_bhavcopy(today_ist):
        _publish_probe_cache[cache_key] = (True, time.monotonic())
        return True

    if not nse_bhavcopy_ingest_allowed_for_today():
        _publish_probe_cache[cache_key] = (False, time.monotonic())
        return False

    published = fetcher.is_bhavcopy_available_on_nse(today_ist)
    _publish_probe_cache[cache_key] = (published, time.monotonic())
    if published:
        logger.debug("NSE bhavcopy publish probe: today's file is available (%s)", today_ist)
    return published


def should_use_same_day_close_for_indicators() -> bool:
    """
    Whether post-close indicator paths should pass ``add_current_day=True``.

    For NSE daily source: only after session close **and** today's bhavcopy is
    confirmed (cache or probe). If an operator schedules analysis/re-entry early,
    this returns ``False`` and callers fall back to the prior session — no failure.

    For non-NSE daily sources: after 15:30 on a trading day (legacy clock gate).
    """
    from core.volume_analysis import is_market_hours  # noqa: PLC0415
    from src.infrastructure.utils.holiday_calendar import is_trading_day  # noqa: PLC0415

    today_ist = ist_now().date()
    if not is_trading_day(today_ist):
        return False
    if is_market_hours():
        return False
    if ist_now().time() < NSE_SESSION_CLOSE:
        return False

    if daily_ohlcv_uses_nse():
        return nse_today_bhavcopy_published()

    return True


def filter_nse_intraday_gap_dates(trade_days: list[date]) -> list[date]:
    """
    Drop dates that must not trigger NSE gap-fill right now (usually calendar today).

    Historical missing days are always kept.
    """
    if not trade_days:
        return trade_days

    filtered = [d for d in trade_days if nse_bhavcopy_ingest_allowed_for_date(d)]
    if len(filtered) < len(trade_days):
        today_ist = ist_now().date()
        skipped = [d for d in trade_days if d not in filtered]
        if today_ist in skipped:
            logger.debug(
                "NSE gap-fill: skipping calendar today %s (ingest not allowed yet; "
                "earliest=%s IST)",
                today_ist,
                NSE_BHAVCOPY_EARLIEST_IST,
            )
    return filtered
