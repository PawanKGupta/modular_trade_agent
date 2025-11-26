from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Signals, SignalStatus
from src.infrastructure.db.timezone_utils import ist_now


class SignalsRepository:
    def __init__(self, db: Session):
        self.db = db

    def recent(self, limit: int = 100, active_only: bool = False) -> list[Signals]:
        """Get recent signals, optionally filtered by status"""
        stmt = select(Signals).order_by(Signals.ts.desc())
        if active_only:
            stmt = stmt.where(Signals.status == SignalStatus.ACTIVE)
        stmt = stmt.limit(limit)
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

    def mark_old_signals_as_expired(self, before_timestamp: datetime | None = None) -> int:
        """
        Mark old signals as EXPIRED.

        By default, marks all ACTIVE signals from previous analysis runs as EXPIRED.
        This is called before each analysis run to expire stale signals.

        Args:
            before_timestamp: Mark signals before this time as expired (defaults to current time)

        Returns:
            Number of signals marked as expired
        """
        if before_timestamp is None:
            before_timestamp = ist_now()

        # Mark all ACTIVE signals before the timestamp as EXPIRED
        result = self.db.execute(
            update(Signals)
            .where(Signals.status == SignalStatus.ACTIVE, Signals.ts < before_timestamp)
            .values(status=SignalStatus.EXPIRED)
        )
        self.db.commit()
        return result.rowcount

    def mark_as_traded(self, symbol: str) -> bool:
        """
        Mark a signal as TRADED when an order is placed.

        Args:
            symbol: Stock symbol

        Returns:
            True if signal was found and marked, False otherwise
        """
        result = self.db.execute(
            update(Signals)
            .where(Signals.symbol == symbol, Signals.status == SignalStatus.ACTIVE)
            .values(status=SignalStatus.TRADED)
        )
        self.db.commit()
        return result.rowcount > 0

    def mark_as_rejected(self, symbol: str) -> bool:
        """
        Mark a signal as REJECTED when user manually rejects it.

        Args:
            symbol: Stock symbol

        Returns:
            True if signal was found and marked, False otherwise
        """
        result = self.db.execute(
            update(Signals)
            .where(Signals.symbol == symbol, Signals.status == SignalStatus.ACTIVE)
            .values(status=SignalStatus.REJECTED)
        )
        self.db.commit()
        return result.rowcount > 0

    def get_active_signals(self, limit: int = 100) -> list[Signals]:
        """Get only ACTIVE signals"""
        stmt = (
            select(Signals)
            .where(Signals.status == SignalStatus.ACTIVE)
            .order_by(Signals.ts.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
