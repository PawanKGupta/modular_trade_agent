"""Repository for PortfolioSnapshot management (Phase 0.3)"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import PortfolioSnapshot
from src.infrastructure.db.timezone_utils import ist_now

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class PortfolioSnapshotRepository:
    """Repository for managing portfolio snapshots"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, snapshot: PortfolioSnapshot) -> PortfolioSnapshot:
        """Create a new portfolio snapshot"""
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def get_by_date_range(
        self, user_id: int, start_date: date, end_date: date, snapshot_type: str = "eod"
    ) -> list[PortfolioSnapshot]:
        """Get snapshots for a date range"""
        stmt = (
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.user_id == user_id,
                PortfolioSnapshot.date >= start_date,
                PortfolioSnapshot.date <= end_date,
                PortfolioSnapshot.snapshot_type == snapshot_type,
            )
            .order_by(PortfolioSnapshot.date.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_latest(self, user_id: int, snapshot_type: str = "eod") -> PortfolioSnapshot | None:
        """Get the latest snapshot for a user"""
        stmt = (
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.user_id == user_id,
                PortfolioSnapshot.snapshot_type == snapshot_type,
            )
            .order_by(PortfolioSnapshot.date.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_date(
        self, user_id: int, snapshot_date: date, snapshot_type: str = "eod"
    ) -> PortfolioSnapshot | None:
        """Get snapshot for a specific date"""
        stmt = (
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.user_id == user_id,
                PortfolioSnapshot.date == snapshot_date,
                PortfolioSnapshot.snapshot_type == snapshot_type,
            )
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def upsert_daily(
        self,
        user_id: int,
        snapshot_date: date,
        snapshot_data: dict,
        snapshot_type: str = "eod",
    ) -> PortfolioSnapshot:
        """
        Upsert (insert or update) a daily snapshot.

        Args:
            user_id: User ID
            snapshot_date: Date for the snapshot
            snapshot_data: Dictionary with snapshot fields:
                - total_value, invested_value, available_cash
                - unrealized_pnl, realized_pnl
                - open_positions_count, closed_positions_count
                - total_return, daily_return
            snapshot_type: Type of snapshot ('eod' or 'intraday')

        Returns:
            Created or updated PortfolioSnapshot
        """
        # Check if snapshot already exists
        existing = self.get_by_date(user_id, snapshot_date, snapshot_type)

        if existing:
            # Update existing snapshot
            existing.total_value = snapshot_data.get("total_value", existing.total_value)
            existing.invested_value = snapshot_data.get("invested_value", existing.invested_value)
            existing.available_cash = snapshot_data.get("available_cash", existing.available_cash)
            existing.unrealized_pnl = snapshot_data.get("unrealized_pnl", existing.unrealized_pnl)
            existing.realized_pnl = snapshot_data.get("realized_pnl", existing.realized_pnl)
            existing.open_positions_count = snapshot_data.get(
                "open_positions_count", existing.open_positions_count
            )
            existing.closed_positions_count = snapshot_data.get(
                "closed_positions_count", existing.closed_positions_count
            )
            existing.total_return = snapshot_data.get("total_return", existing.total_return)
            existing.daily_return = snapshot_data.get("daily_return", existing.daily_return)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new snapshot
            snapshot = PortfolioSnapshot(
                user_id=user_id,
                date=snapshot_date,
                total_value=snapshot_data.get("total_value", 0.0),
                invested_value=snapshot_data.get("invested_value", 0.0),
                available_cash=snapshot_data.get("available_cash", 0.0),
                unrealized_pnl=snapshot_data.get("unrealized_pnl", 0.0),
                realized_pnl=snapshot_data.get("realized_pnl", 0.0),
                open_positions_count=snapshot_data.get("open_positions_count", 0),
                closed_positions_count=snapshot_data.get("closed_positions_count", 0),
                total_return=snapshot_data.get("total_return", 0.0),
                daily_return=snapshot_data.get("daily_return", 0.0),
                snapshot_type=snapshot_type,
                created_at=ist_now(),
            )
            return self.create(snapshot)

