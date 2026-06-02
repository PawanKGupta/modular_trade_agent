#!/usr/bin/env python3
"""
Backfill NSE UDiFF bhavcopy into Postgres/SQLite ``price_cache``.

Examples:
    .venv/bin/python tools/nse_bhavcopy_backfill.py backfill-symbol DMART.NS --days 500
    .venv/bin/python tools/nse_bhavcopy_backfill.py backfill-cached --days 500
    .venv/bin/python tools/nse_bhavcopy_backfill.py backfill-dates --from 2024-07-08 --to 2026-06-02 --symbols DMART.NS,LINDEINDIA.NS
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.application.services.nse_bhavcopy_ingest_service import NseBhavcopyIngestService  # noqa: E402
from src.infrastructure.data_providers.nse_symbol import ensure_cache_ticker  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402
from src.infrastructure.persistence.price_cache_repository import (  # noqa: E402
    DEFAULT_INTERVAL,
    PriceCacheRepository,
)
from src.infrastructure.utils.holiday_calendar import iter_trading_days  # noqa: E402


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def cmd_backfill_symbol(symbol: str, days: int) -> int:
    end_d = date.today()
    start_d = end_d - timedelta(days=days + 30)
    db = SessionLocal()
    try:
        svc = NseBhavcopyIngestService(db)
        n = svc.fill_symbol_range(symbol, start_d, end_d)
        print(f"backfill-symbol {ensure_cache_ticker(symbol)}: upserted {n} rows ({start_d}..{end_d})")
        return 0
    finally:
        db.close()


def cmd_backfill_cached(days: int, *, limit: int | None = None) -> int:
    """
    Backfill every distinct daily symbol already present in ``price_cache``.

    Discovers tickers from existing cache rows, then ingests one bhavcopy zip per
    trading day (shared across all symbols — efficient for large universes).
    """
    from src.application.services.ohlcv_fetch_validation import validate_cached_symbol

    end_d = date.today()
    start_d = end_d - timedelta(days=days + 30)
    db = SessionLocal()
    try:
        repo = PriceCacheRepository(db)
        symbols = repo.list_cached_symbols(interval=DEFAULT_INTERVAL)
        if limit is not None:
            symbols = symbols[:limit]
        if not symbols:
            print("backfill-cached: no symbols in price_cache (interval=1d)")
            return 0

        tickers = [ensure_cache_ticker(s) for s in symbols]
        print(f"backfill-cached: {len(tickers)} symbol(s), range {start_d}..{end_d}")

        svc = NseBhavcopyIngestService(db)
        total = 0
        trading_days = list(iter_trading_days(start_d, end_d))
        for i, trade_day in enumerate(trading_days, start=1):
            n = svc.ingest_trading_day(trade_day, tickers)
            total += n
            if i % 20 == 0 or i == len(trading_days):
                print(f"  [{i}/{len(trading_days)}] {trade_day}: cumulative {total} rows")

        for ticker in tickers:
            repo.refresh_symbol_meta(ticker, interval=DEFAULT_INTERVAL)
            post = validate_cached_symbol(repo, ticker, start_d, end_d, interval=DEFAULT_INTERVAL)
            repo.record_fetch_validation(
                ticker,
                DEFAULT_INTERVAL,
                fetch_status=post.status,
                coverage_pct=post.coverage_pct,
                message=post.message,
            )

        print(f"backfill-cached done: {total} rows upserted for {len(tickers)} symbol(s)")
        return 0
    finally:
        db.close()


def cmd_backfill_dates(from_d: date, to_d: date, symbols: list[str] | None, all_equity: bool) -> int:
    db = SessionLocal()
    try:
        svc = NseBhavcopyIngestService(db)
        total = 0
        tickers = [ensure_cache_ticker(s) for s in symbols] if symbols else None
        for trade_day in iter_trading_days(from_d, to_d):
            if tickers:
                n = svc.ingest_trading_day(trade_day, tickers)
            else:
                n = svc.ingest_trading_day(trade_day, None, all_equity=all_equity)
            total += n
            print(f"  {trade_day}: {n} rows")
        print(f"backfill-dates total rows upserted: {total}")
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="NSE bhavcopy -> price_cache backfill")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sym = sub.add_parser("backfill-symbol", help="Backfill one symbol over --days calendar lookback")
    p_sym.add_argument("symbol", help="Ticker e.g. DMART.NS")
    p_sym.add_argument("--days", type=int, default=500)

    p_cached = sub.add_parser(
        "backfill-cached",
        help="Backfill all symbols already in price_cache (daily 1d)",
    )
    p_cached.add_argument("--days", type=int, default=500)
    p_cached.add_argument("--limit", type=int, default=None, help="Max symbols (testing)")

    p_dates = sub.add_parser("backfill-dates", help="Backfill one bhavcopy file per trading day")
    p_dates.add_argument("--from", dest="from_date", required=True, help="YYYY-MM-DD")
    p_dates.add_argument("--to", dest="to_date", required=True, help="YYYY-MM-DD")
    p_dates.add_argument(
        "--symbols",
        help="Comma-separated tickers (e.g. DMART.NS,LINDEINDIA.NS). Omit with --all-equity.",
    )
    p_dates.add_argument(
        "--all-equity",
        action="store_true",
        help="Ingest all EQ symbols per day (large; use deliberately)",
    )

    args = parser.parse_args()
    if args.command == "backfill-symbol":
        return cmd_backfill_symbol(args.symbol, args.days)
    if args.command == "backfill-cached":
        return cmd_backfill_cached(args.days, limit=args.limit)
    if args.command == "backfill-dates":
        symbols = None
        if args.symbols:
            symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        if not symbols and not args.all_equity:
            print("Provide --symbols or --all-equity", file=sys.stderr)
            return 2
        return cmd_backfill_dates(
            _parse_date(args.from_date),
            _parse_date(args.to_date),
            symbols,
            args.all_equity,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
