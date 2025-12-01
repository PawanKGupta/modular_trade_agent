"""Repository for AuditLog management"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import AuditLog
from src.infrastructure.db.timezone_utils import ist_now


class AuditLogRepository:
    """Repository for managing audit trail"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        action: Literal["create", "update", "delete", "login", "logout", "config_change"],
        resource_type: str,
        resource_id: int | None = None,
        changes: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Create a new audit log entry"""
        audit = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=ist_now(),
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(audit)
        return audit

    def get(self, audit_id: int) -> AuditLog | None:
        """Get audit log by ID"""
        return self.db.get(AuditLog, audit_id)

    def list(
        self,
        user_id: int | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[AuditLog]:
        """List audit logs with filters"""
        stmt = select(AuditLog)

        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        if start_time:
            stmt = stmt.where(AuditLog.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(AuditLog.timestamp <= end_time)

        stmt = stmt.order_by(desc(AuditLog.timestamp)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_resource(
        self,
        resource_type: str,
        resource_id: int,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Get audit logs for a specific resource"""
        return self.list(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )

    def get_by_user(
        self,
        user_id: int,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[AuditLog]:
        """Get audit logs for a specific user"""
        return self.list(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
