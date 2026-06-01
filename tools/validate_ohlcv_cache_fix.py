"""
Validate OHLCV cache warm-path: second fetch should not call Yahoo.

Usage (repo root, Postgres DB_URL set):
    .venv\\Scripts\\python.exe tools\\validate_ohlcv_cache_fix.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.application.services.ohlcv_cache_service import (  # noqa: E402
    OhlcvCacheService,
    get_ohlcv_cache_stats,
    reset_ohlcv_cache_stats,
)
from src.infrastructure.db.models import PriceCache  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402
from src.infrastructure.persistence.price_cache_repository import (  # noqa: E402
    PriceCacheRepository,
)


def _counting_fetch(real_fetch, counter: list[int]):
    def _wrap(*args, **kwargs):
        counter.append(1)
        return real_fetch(*args, **kwargs)

    return _wrap


def main() -> int:
    from core.data_fetcher import fetch_ohlcv_yf_raw  # noqa: PLC0415

    db = SessionLocal()
    repo = PriceCacheRepository(db)
    symbols = sorted(db.execute(select(PriceCache.symbol).distinct()).scalars().all())[:12]
    if not symbols:
        print("No symbols in price_cache; run trade_agent --backtest first.")
        return 1

    end_d = date.today()
    end = end_d.isoformat()
    windows = [
        ("analysis_1d", 420, "1d"),
        ("analysis_1wk", 420, "1wk"),
        ("backtest_1d", 1900, "1d"),
        ("backtest_1wk", 1900, "1wk"),
    ]

    print(f"Symbols ({len(symbols)}): {', '.join(symbols)}")
    reset_ohlcv_cache_stats()
    direct_calls: list[int] = []
    svc = OhlcvCacheService(db, fetch_func=_counting_fetch(fetch_ohlcv_yf_raw, direct_calls))

    for label, days, interval in windows:
        reset_ohlcv_cache_stats()
        direct_calls.clear()
        for sym in symbols:
            svc.get_ohlcv(sym, days=days, interval=interval, end_date=end, add_current_day=False)
            svc.get_ohlcv(sym, days=days, interval=interval, end_date=end, add_current_day=False)
        stats = get_ohlcv_cache_stats()
        start_d = end_d - timedelta(days=days + 5)
        gaps = sum(
            len(repo.get_dates_needing_gap_fill(sym, start_d, end_d, interval=interval))
            for sym in symbols
        )
        print(
            f"  {label}: yahoo_calls={stats['yahoo_calls']} "
            f"direct_fetch={len(direct_calls)} symbols={len(symbols)} pre_check_gaps={gaps}"
        )
        if stats["yahoo_calls"] > len(symbols) * 2:
            print("    WARN: high Yahoo usage on second pass — cache may not be warm")
        elif stats["yahoo_calls"] == 0:
            print("    OK: cache_hit path (no Yahoo on repeat fetch)")

    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
