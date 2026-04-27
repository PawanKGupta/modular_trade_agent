from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import PnlDaily


class PnlRepository:
    def __init__(self, db: Session):
        self.db = db

    def range(self, user_id: int, start: date, end: date) -> list[PnlDaily]:
        stmt = (
            select(PnlDaily)
            .where(PnlDaily.user_id == user_id)
            .where(PnlDaily.date >= start)
            .where(PnlDaily.date <= end)
            .order_by(PnlDaily.date.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def sum_realized_pnl_calendar_month(self, user_id: int, year: int, month: int) -> float:
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        total = self.db.execute(
            select(func.coalesce(func.sum(PnlDaily.realized_pnl), 0.0)).where(
                PnlDaily.user_id == user_id,
                PnlDaily.date >= start,
                PnlDaily.date <= end,
            )
        ).scalar_one()
        return float(total or 0.0)

    def upsert(self, rec: PnlDaily) -> PnlDaily:
        # Query for existing record
        existing = self.db.execute(
            select(PnlDaily).where(PnlDaily.user_id == rec.user_id, PnlDaily.date == rec.date)
        ).scalar_one_or_none()

        if existing:
            # Update existing record
            existing.realized_pnl = rec.realized_pnl
            existing.unrealized_pnl = rec.unrealized_pnl
            existing.fees = rec.fees
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new record
            self.db.add(rec)
            self.db.commit()
            self.db.refresh(rec)
            return rec
