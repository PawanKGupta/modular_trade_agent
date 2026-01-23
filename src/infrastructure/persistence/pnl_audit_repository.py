"""Repository for PnlCalculationAudit management (Phase 0.5)"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import PnlCalculationAudit

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class PnlAuditRepository:
    """Repository for managing P&L calculation audit records"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, audit: PnlCalculationAudit) -> PnlCalculationAudit:
        """Create a new audit record"""
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(audit)
        return audit

    def get_by_user(self, user_id: int, limit: int = 100) -> list[PnlCalculationAudit]:
        """Get audit records for a user, ordered by most recent first"""
        stmt = (
            select(PnlCalculationAudit)
            .where(PnlCalculationAudit.user_id == user_id)
            .order_by(PnlCalculationAudit.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_latest(self, user_id: int) -> PnlCalculationAudit | None:
        """Get the most recent audit record for a user"""
        stmt = (
            select(PnlCalculationAudit)
            .where(PnlCalculationAudit.user_id == user_id)
            .order_by(PnlCalculationAudit.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_status(
        self, user_id: int, status: str, limit: int = 100
    ) -> list[PnlCalculationAudit]:
        """Get audit records filtered by status"""
        stmt = (
            select(PnlCalculationAudit)
            .where(
                PnlCalculationAudit.user_id == user_id,
                PnlCalculationAudit.status == status,
            )
            .order_by(PnlCalculationAudit.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

