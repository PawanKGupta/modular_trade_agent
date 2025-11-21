from __future__ import annotations

import builtins
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Positions
from src.infrastructure.db.timezone_utils import ist_now


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

    def upsert(
        self,
        *,
        user_id: int,
        symbol: str,
        quantity: float,
        avg_price: float,
        opened_at: datetime | None = None,
        reentry_count: int | None = None,
        reentries: dict | None = None,
        initial_entry_price: float | None = None,
        last_reentry_price: float | None = None,
    ) -> Positions:
        pos = self.get_by_symbol(user_id, symbol)
        if pos:
            pos.quantity = quantity
            pos.avg_price = avg_price
            if reentry_count is not None:
                pos.reentry_count = reentry_count
            if reentries is not None:
                pos.reentries = reentries
            if last_reentry_price is not None:
                pos.last_reentry_price = last_reentry_price
        else:
            # New position - set initial_entry_price if provided, otherwise use avg_price
            initial_price = initial_entry_price if initial_entry_price is not None else avg_price
            pos = Positions(
                user_id=user_id,
                symbol=symbol,
                quantity=quantity,
                avg_price=avg_price,
                unrealized_pnl=0.0,
                opened_at=opened_at or ist_now(),
                reentry_count=reentry_count or 0,
                reentries=reentries,
                initial_entry_price=initial_price,
                last_reentry_price=last_reentry_price,
            )
            self.db.add(pos)
        self.db.commit()
        self.db.refresh(pos)
        return pos

    def count_open(self, user_id: int) -> int:
        """Count open positions for a user"""
        stmt = select(Positions).where(Positions.user_id == user_id, Positions.closed_at.is_(None))
        return len(list(self.db.execute(stmt).scalars().all()))

    def bulk_create(self, positions: list[dict]) -> list[Positions]:
        """Bulk create positions (for migration)"""
        created_positions = []
        for pos_data in positions:
            position = Positions(**pos_data)
            self.db.add(position)
            created_positions.append(position)
        self.db.commit()
        for position in created_positions:
            self.db.refresh(position)
        return created_positions
