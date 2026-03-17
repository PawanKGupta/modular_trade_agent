"""
Cleanup helpers for simulated Kotak integration tests.

Can be used:
1) Programmatically from tests (preferred)
2) As a script against a target DB_URL for manual cleanup
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from src.infrastructure.db.models import Fills, Orders, Positions, Users


def cleanup_simulated_test_data(
    db: Session,
    *,
    emails: Sequence[str] | None = None,
    symbols: Sequence[str] | None = None,
    broker_order_ids: Sequence[str] | None = None,
) -> dict[str, int]:
    """
    Delete test data scoped to specific users/symbols/order IDs.

    Returns row counts for observability in tests/logs.
    """
    emails = [e.strip().lower() for e in (emails or []) if e and e.strip()]
    symbols = [s.strip().upper() for s in (symbols or []) if s and s.strip()]
    broker_order_ids = [str(x).strip() for x in (broker_order_ids or []) if str(x).strip()]

    user_ids: list[int] = []
    if emails:
        stmt_users = select(Users.id).where(Users.email.in_(emails))
        user_ids = [int(x) for x in db.execute(stmt_users).scalars().all()]

    stats = {"fills": 0, "positions": 0, "orders": 0, "users": 0}

    if user_ids:
        stats["fills"] += db.execute(delete(Fills).where(Fills.user_id.in_(user_ids))).rowcount or 0
        stats["positions"] += db.execute(
            delete(Positions).where(Positions.user_id.in_(user_ids))
        ).rowcount or 0
        stats["orders"] += db.execute(delete(Orders).where(Orders.user_id.in_(user_ids))).rowcount or 0
        stats["users"] += db.execute(delete(Users).where(Users.id.in_(user_ids))).rowcount or 0

    if symbols:
        order_ids_for_symbols = list(
            db.execute(select(Orders.id).where(Orders.symbol.in_(symbols))).scalars().all()
        )
        if order_ids_for_symbols:
            stats["fills"] += db.execute(
                delete(Fills).where(Fills.order_id.in_(order_ids_for_symbols))
            ).rowcount or 0
        stats["positions"] += db.execute(
            delete(Positions).where(Positions.symbol.in_(symbols))
        ).rowcount or 0
        stats["orders"] += db.execute(
            delete(Orders).where(Orders.symbol.in_(symbols))
        ).rowcount or 0

    if broker_order_ids:
        stats["orders"] += db.execute(
            delete(Orders).where(Orders.broker_order_id.in_(broker_order_ids))
        ).rowcount or 0

    db.commit()
    return stats


def _run_cli() -> None:
    parser = argparse.ArgumentParser(description="Cleanup simulated Kotak test data from DB.")
    parser.add_argument("--email", action="append", default=[], help="User email to cleanup (repeatable)")
    parser.add_argument("--symbol", action="append", default=[], help="Order/position symbol to cleanup")
    parser.add_argument(
        "--broker-order-id",
        action="append",
        default=[],
        help="Broker order id to cleanup",
    )
    args = parser.parse_args()

    # Safety: script is intended for explicit test cleanups only.
    db_url = os.environ.get("DB_URL", "")
    if not db_url:
        raise SystemExit("DB_URL is not set.")

    script_engine = create_engine(db_url, future=True)
    SessionLocal = sessionmaker(bind=script_engine, autoflush=False, autocommit=False, future=True)
    db = SessionLocal()
    try:
        stats = cleanup_simulated_test_data(
            db,
            emails=args.email,
            symbols=args.symbol,
            broker_order_ids=args.broker_order_id,
        )
        print(f"Cleanup completed: {stats}")
    finally:
        db.close()
        script_engine.dispose()


if __name__ == "__main__":
    _run_cli()
