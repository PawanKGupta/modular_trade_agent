"""Repository for ServiceLog management"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import ServiceLog
from src.infrastructure.db.timezone_utils import ist_now


class ServiceLogRepository:
    """Repository for managing structured service logs"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        module: str,
        message: str,
        context: dict | None = None,
    ) -> ServiceLog:
        """Create a new log entry"""
        log = ServiceLog(
            user_id=user_id,
            level=level,
            module=module,
            message=message[:1024],  # Truncate to max length
            context=context,
            timestamp=ist_now(),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get(self, log_id: int) -> ServiceLog | None:
        """Get log entry by ID"""
        return self.db.get(ServiceLog, log_id)

    def list(
        self,
        user_id: int,
        level: str | None = None,
        module: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[ServiceLog]:
        """List log entries for a user with filters"""
        stmt = select(ServiceLog).where(ServiceLog.user_id == user_id)

        if level:
            stmt = stmt.where(ServiceLog.level == level)
        if module:
            stmt = stmt.where(ServiceLog.module == module)
        if start_time:
            stmt = stmt.where(ServiceLog.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(ServiceLog.timestamp <= end_time)

        stmt = stmt.order_by(desc(ServiceLog.timestamp)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_errors(
        self,
        user_id: int,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[ServiceLog]:
        """Get error-level logs for a user"""
        return self.list(
            user_id=user_id,
            level="ERROR",
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def get_critical(
        self,
        user_id: int,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[ServiceLog]:
        """Get critical-level logs for a user"""
        return self.list(
            user_id=user_id,
            level="CRITICAL",
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def count_by_level(self, user_id: int, level: str) -> int:
        """Count logs by level for a user"""
        stmt = select(ServiceLog).where(
            ServiceLog.user_id == user_id,
            ServiceLog.level == level,
        )
        return len(list(self.db.execute(stmt).scalars().all()))

    def delete_old_logs(self, user_id: int, before_date: datetime) -> int:
        """Delete logs older than specified date (for retention)"""
        stmt = select(ServiceLog).where(
            and_(
                ServiceLog.user_id == user_id,
                ServiceLog.timestamp < before_date,
            )
        )
        logs_to_delete = list(self.db.execute(stmt).scalars().all())
        count = len(logs_to_delete)
        for log in logs_to_delete:
            self.db.delete(log)
        self.db.commit()
        return count
