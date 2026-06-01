"""
OHLCV operator fields for bulk analysis CSV exports (``trade_agent --backtest``, jobs).

Populates ``cache_health_status`` and per-symbol ``yahoo_calls`` on each result row.
"""

from __future__ import annotations

from datetime import date, timedelta

from config.settings import OHLCV_CACHE_ENABLED
from src.application.services.ohlcv_cache_service import (
    get_ohlcv_cache_stats,
    reset_ohlcv_cache_stats,
)
from src.infrastructure.persistence.price_cache_repository import DEFAULT_INTERVAL

_ANALYSIS_YAHOO_KEY = "_yahoo_calls_analysis"


def reset_symbol_yahoo_counter() -> None:
    """Reset process-local Yahoo fetch counter before analysis or backtest for one symbol."""
    reset_ohlcv_cache_stats()


def record_analysis_yahoo_calls(result: dict) -> None:
    """Store Yahoo calls used during ``analyze_ticker`` (before backtest scoring)."""
    if not isinstance(result, dict):
        return
    result[_ANALYSIS_YAHOO_KEY] = get_ohlcv_cache_stats().get("yahoo_calls", 0)


def apply_ohlcv_ops_fields(
    result: dict,
    symbol: str,
    *,
    cache_health_override: str | None = None,
) -> None:
    """
    Set ``cache_health_status`` and ``yahoo_calls`` on a bulk analysis result dict.

    ``yahoo_calls`` sums analysis-phase calls (if recorded) plus backtest-phase calls
    since the last ``reset_symbol_yahoo_counter()`` before backtest.
    """
    if not isinstance(result, dict):
        return

    ticker = symbol or result.get("ticker") or ""
    if cache_health_override is not None:
        result["cache_health_status"] = cache_health_override
    else:
        result["cache_health_status"] = _read_cache_health_status(ticker)

    analysis_calls = int(result.pop(_ANALYSIS_YAHOO_KEY, 0) or 0)
    backtest_calls = get_ohlcv_cache_stats().get("yahoo_calls", 0)
    result["yahoo_calls"] = analysis_calls + backtest_calls


def _read_cache_health_status(symbol: str) -> str:
    if not OHLCV_CACHE_ENABLED or not symbol:
        return "disabled"
    try:
        from src.application.services.ohlcv_cache_health import (  # noqa: PLC0415
            assess_price_cache_health,
        )
        from src.infrastructure.db.session import SessionLocal  # noqa: PLC0415
        from src.infrastructure.persistence.price_cache_repository import (  # noqa: PLC0415
            PriceCacheRepository,
        )

        end_d = date.today()
        start_d = end_d - timedelta(days=365 * 5)
        db = SessionLocal()
        try:
            meta = PriceCacheRepository(db).get_symbol_meta(symbol, interval=DEFAULT_INTERVAL)
            if meta is None or not (meta.row_count or 0):
                return "empty"
            report = assess_price_cache_health(symbol, start_d, end_d, db)
            return report.status
        finally:
            db.close()
    except Exception:
        return "unknown"
