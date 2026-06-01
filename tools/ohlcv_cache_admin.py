#!/usr/bin/env python3
"""
Admin CLI for Postgres/SQLite OHLCV cache operations.

Examples:
  .venv\\Scripts\\python.exe tools\\ohlcv_cache_admin.py health RELIANCE.NS
  .venv\\Scripts\\python.exe tools\\ohlcv_cache_admin.py gap-fill RELIANCE.NS --days 400
  .venv\\Scripts\\python.exe tools\\ohlcv_cache_admin.py invalidate RELIANCE.NS
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.application.services.ohlcv_cache_health import (  # noqa: E402
    assess_price_cache_health,
    sync_corporate_actions,
)
from src.application.services.ohlcv_cache_service import OhlcvCacheService  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402


def _date_range(days: int) -> tuple[date, date]:
    end_d = date.today()
    return end_d - timedelta(days=days), end_d


def cmd_health(symbol: str, days: int) -> int:
    start_d, end_d = _date_range(days)
    db = SessionLocal()
    try:
        sync_corporate_actions(symbol, db)
        report = assess_price_cache_health(symbol, start_d, end_d, db)
        print(json.dumps(report.__dict__, default=str, indent=2))
        return 0 if report.status == "ok" else 1
    finally:
        db.close()


def cmd_gap_fill(symbol: str, days: int, interval: str) -> int:
    start_d, end_d = _date_range(days)
    db = SessionLocal()
    try:
        svc = OhlcvCacheService(db)
        yf_end = end_d.isoformat()
        n = svc.gap_fill(
            symbol,
            start_d,
            end_d,
            interval=interval,
            days=days,
            yf_end_date=yf_end,
        )
        print(f"gap_fill upserted {n} rows for {symbol} [{interval}]")
        return 0
    finally:
        db.close()


def cmd_invalidate(symbol: str, interval: str | None) -> int:
    db = SessionLocal()
    try:
        svc = OhlcvCacheService(db)
        n = svc.invalidate_symbol(symbol, interval=interval)
        print(f"invalidated {n} rows for {symbol}")
        return 0
    finally:
        db.close()


def cmd_tail_refresh(symbol: str, interval: str) -> int:
    db = SessionLocal()
    try:
        svc = OhlcvCacheService(db)
        n = svc.refresh_tail(symbol, interval=interval)
        print(f"tail refresh upserted {n} rows for {symbol} [{interval}]")
        return 0
    finally:
        db.close()


def cmd_preload(symbols: list[str], days: int) -> int:
    start_d, end_d = _date_range(days)
    db = SessionLocal()
    try:
        svc = OhlcvCacheService(db)
        yf_end = end_d.isoformat()
        for sym in symbols:
            svc.gap_fill(sym, start_d, end_d, days=days, yf_end_date=yf_end)
            svc.gap_fill(sym, start_d, end_d, interval="1wk", days=days, yf_end_date=yf_end)
            print(f"preloaded {sym}")
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="OHLCV cache admin")
    sub = parser.add_subparsers(dest="command", required=True)

    p_health = sub.add_parser("health")
    p_health.add_argument("symbol")
    p_health.add_argument("--days", type=int, default=365 * 5)

    p_gap = sub.add_parser("gap-fill")
    p_gap.add_argument("symbol")
    p_gap.add_argument("--days", type=int, default=400)
    p_gap.add_argument("--interval", default="1d")

    p_inv = sub.add_parser("invalidate")
    p_inv.add_argument("symbol")
    p_inv.add_argument("--interval", default=None)

    p_tail = sub.add_parser("tail-refresh")
    p_tail.add_argument("symbol")
    p_tail.add_argument("--interval", default="1d")

    p_pre = sub.add_parser("preload-symbols")
    p_pre.add_argument("symbols", nargs="+")
    p_pre.add_argument("--days", type=int, default=400)

    args = parser.parse_args()
    if args.command == "health":
        return cmd_health(args.symbol, args.days)
    if args.command == "gap-fill":
        return cmd_gap_fill(args.symbol, args.days, args.interval)
    if args.command == "invalidate":
        return cmd_invalidate(args.symbol, args.interval)
    if args.command == "tail-refresh":
        return cmd_tail_refresh(args.symbol, args.interval)
    if args.command == "preload-symbols":
        return cmd_preload(args.symbols, args.days)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
