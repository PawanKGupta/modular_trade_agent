from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Signals


class SignalsRepository:
    def __init__(self, db: Session):
        self.db = db

    def recent(self, limit: int = 100) -> list[Signals]:
        stmt = select(Signals).order_by(Signals.ts.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def add_many(self, signals: list[Signals]) -> int:
        self.db.add_all(signals)
        self.db.commit()
        return len(signals)
