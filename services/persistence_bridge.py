from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.infrastructure.db.session import SessionLocal
from src.infrastructure.persistence.csv_repository import CSVRepository  # legacy optional
from src.infrastructure.persistence.dual_write import (
    DualActivityWriter,
    DualOrdersWriter,
    DualSignalsWriter,
)
from src.infrastructure.persistence.trade_history_repository import (
    TradeHistoryRepository,  # legacy optional
)


def persist_signals(rows: list[dict[str, Any]], *, db: Session | None = None) -> int:
    owned = False
    if db is None:
        db = SessionLocal()
        owned = True
    try:
        writer = DualSignalsWriter(db, csv_repo=CSVRepository())
        return writer.add_many(rows)
    finally:
        if owned:
            db.close()


def create_amo_order(
    *,
    user_id: int,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None,
    db: Session | None = None,
) -> int:
    owned = False
    if db is None:
        db = SessionLocal()
        owned = True
    try:
        orders_writer = DualOrdersWriter(db, csv_repo=CSVRepository())
        activity_writer = DualActivityWriter(
            db, trade_history_repo=TradeHistoryRepository("trade_history.csv")
        )
        order = orders_writer.create_amo(
            user_id=user_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )
        activity_writer.append(
            user_id=user_id, type="order_created", ref_id=str(order.id), details={"symbol": symbol}
        )
        return order.id
    finally:
        if owned:
            db.close()
