from __future__ import annotations

import builtins

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Positions


class PositionsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_symbol(self, user_id: int, symbol: str) -> Positions | None:
        return (
            self.db.query(Positions)
            .filter(Positions.user_id == user_id, Positions.symbol == symbol)
            .first()
        )

    def list(self, user_id: int) -> builtins.list[Positions]:
        stmt = (
            select(Positions)
            .where(Positions.user_id == user_id)
            .order_by(Positions.opened_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def upsert(self, *, user_id: int, symbol: str, quantity: float, avg_price: float) -> Positions:
        pos = self.get_by_symbol(user_id, symbol)
        if pos:
            pos.quantity = quantity
            pos.avg_price = avg_price
        else:
            pos = Positions(
                user_id=user_id,
                symbol=symbol,
                quantity=quantity,
                avg_price=avg_price,
                unrealized_pnl=0.0,
            )
            self.db.add(pos)
        self.db.commit()
        self.db.refresh(pos)
        return pos
