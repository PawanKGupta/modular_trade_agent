from __future__ import annotations

from datetime import date

from sqlalchemy import select
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

    def upsert(self, rec: PnlDaily) -> PnlDaily:
        self.db.merge(rec)
        self.db.commit()
        return rec
