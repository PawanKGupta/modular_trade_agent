from __future__ import annotations

import builtins
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Orders, OrderStatus


class OrdersRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, order_id: int) -> Orders | None:
        return self.db.get(Orders, order_id)

    def list(self, user_id: int, status: OrderStatus | None = None) -> builtins.list[Orders]:
        stmt = select(Orders).where(Orders.user_id == user_id)
        if status:
            stmt = stmt.where(Orders.status == status)
        stmt = stmt.order_by(Orders.placed_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def create_amo(
        self,
        *,
        user_id: int,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None,
    ) -> Orders:
        order = Orders(
            user_id=user_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.AMO,
            placed_at=datetime.utcnow(),
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def update(self, order: Orders, **fields) -> Orders:
        for k, v in fields.items():
            if hasattr(order, k) and v is not None:
                setattr(order, k, v)
        self.db.commit()
        self.db.refresh(order)
        return order

    def cancel(self, order: Orders) -> None:
        # For AMO orders, cancel means remove or mark closed without fills
        order.status = OrderStatus.CLOSED
        order.closed_at = datetime.utcnow()
        self.db.commit()
