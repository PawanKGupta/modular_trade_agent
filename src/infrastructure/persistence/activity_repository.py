from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Activity


class ActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    def recent(self, user_id: int | None, limit: int = 200) -> list[Activity]:
        stmt = select(Activity).order_by(Activity.ts.desc()).limit(limit)
        if user_id is not None:
            stmt = stmt.where(Activity.user_id == user_id)
        return list(self.db.execute(stmt).scalars().all())

    def append(
        self, *, user_id: int | None, type: str, ref_id: str | None, details: dict[str, Any] | None
    ) -> Activity:
        rec = Activity(user_id=user_id, type=type, ref_id=ref_id, details_json=details)
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec
