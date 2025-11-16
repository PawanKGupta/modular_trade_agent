"""Repository for Fills management"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Fills
from src.infrastructure.db.timezone_utils import ist_now


class FillsRepository:
    """Repository for managing order fills"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        order_id: int,
        qty: float,
        price: float,
        ts: datetime | None = None,
    ) -> Fills:
        """Create a new fill"""
        fill = Fills(
            order_id=order_id,
            qty=qty,
            price=price,
            ts=ts or ist_now(),
        )
        self.db.add(fill)
        self.db.commit()
        self.db.refresh(fill)
        return fill

    def get(self, fill_id: int) -> Fills | None:
        """Get fill by ID"""
        return self.db.get(Fills, fill_id)

    def list_by_order(self, order_id: int) -> list[Fills]:
        """List all fills for an order"""
        stmt = select(Fills).where(Fills.order_id == order_id).order_by(desc(Fills.ts))
        return list(self.db.execute(stmt).scalars().all())

    def bulk_create(self, fills: list[dict]) -> list[Fills]:
        """Bulk create fills (for migration)"""
        created_fills = []
        for fill_data in fills:
            fill = Fills(**fill_data)
            self.db.add(fill)
            created_fills.append(fill)
        self.db.commit()
        for fill in created_fills:
            self.db.refresh(fill)
        return created_fills
