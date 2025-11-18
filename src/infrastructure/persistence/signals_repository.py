from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Signals
from src.infrastructure.db.timezone_utils import ist_now


class SignalsRepository:
    def __init__(self, db: Session):
        self.db = db

    def recent(self, limit: int = 100) -> list[Signals]:
        stmt = select(Signals).order_by(Signals.ts.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def by_date(self, target_date: date, limit: int = 100) -> list[Signals]:
        """Get signals for a specific date (IST timezone)"""
        # Use SQLite's date() function to extract date from ts column
        # Format: 'YYYY-MM-DD'
        target_date_str = target_date.isoformat()

        # Query: filter by date part of ts using SQLite date() function
        stmt = (
            select(Signals)
            .where(func.date(Signals.ts) == target_date_str)
            .order_by(Signals.ts.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def by_date_range(self, start_date: date, end_date: date, limit: int = 100) -> list[Signals]:
        """Get signals within a date range (IST timezone)"""
        # Use SQLite's date() function to extract date from ts column
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()

        # Query: filter by date range using SQLite date() function
        stmt = (
            select(Signals)
            .where(func.date(Signals.ts) >= start_date_str, func.date(Signals.ts) <= end_date_str)
            .order_by(Signals.ts.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def last_n_dates(self, n: int, limit: int = 100) -> list[Signals]:
        """Get signals from the last N unique dates"""
        # Get distinct dates from the last N days
        now = ist_now()
        end_date = now.date()
        start_date = end_date - timedelta(days=n - 1)

        return self.by_date_range(start_date, end_date, limit=limit)

    def add_many(self, signals: list[Signals]) -> int:
        self.db.add_all(signals)
        self.db.commit()
        return len(signals)
