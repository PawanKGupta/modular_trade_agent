"""Repository for ErrorLog management"""

# ruff: noqa: PLR0913

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import ErrorLog
from src.infrastructure.db.timezone_utils import ist_now


class ErrorLogRepository:
    """Repository for managing error/exception logs"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        error_type: str,
        error_message: str,
        traceback: str | None = None,
        context: dict | None = None,
    ) -> ErrorLog:
        """Create a new error log entry"""
        error = ErrorLog(
            user_id=user_id,
            error_type=error_type[:128],  # Truncate to max length
            error_message=error_message[:1024],  # Truncate to max length
            traceback=traceback[:8192] if traceback else None,  # Truncate to max length
            context=context,
            occurred_at=ist_now(),
        )
        self.db.add(error)
        self.db.commit()
        self.db.refresh(error)
        return error

    def get(self, error_id: int) -> ErrorLog | None:
        """Get error log by ID"""
        return self.db.get(ErrorLog, error_id)

    def _apply_search(self, stmt, search: str | None):
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    ErrorLog.error_message.ilike(pattern),
                    ErrorLog.error_type.ilike(pattern),
                )
            )
        return stmt

    def list(
        self,
        user_id: int,
        resolved: bool | None = None,
        error_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> list[ErrorLog]:
        """List error logs for a user with filters"""
        stmt = select(ErrorLog).where(ErrorLog.user_id == user_id)

        if resolved is not None:
            stmt = stmt.where(ErrorLog.resolved == resolved)
        if error_type:
            stmt = stmt.where(ErrorLog.error_type == error_type)
        if start_time:
            stmt = stmt.where(ErrorLog.occurred_at >= start_time)
        if end_time:
            stmt = stmt.where(ErrorLog.occurred_at <= end_time)
        stmt = self._apply_search(stmt, search)

        stmt = stmt.order_by(desc(ErrorLog.occurred_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def list_all(
        self,
        user_id: int | None = None,
        resolved: bool | None = None,
        error_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> list[ErrorLog]:
        """Admin: list error logs across users."""
        stmt = select(ErrorLog)
        if user_id:
            stmt = stmt.where(ErrorLog.user_id == user_id)
        if resolved is not None:
            stmt = stmt.where(ErrorLog.resolved == resolved)
        if error_type:
            stmt = stmt.where(ErrorLog.error_type == error_type)
        if start_time:
            stmt = stmt.where(ErrorLog.occurred_at >= start_time)
        if end_time:
            stmt = stmt.where(ErrorLog.occurred_at <= end_time)
        stmt = self._apply_search(stmt, search)
        stmt = stmt.order_by(desc(ErrorLog.occurred_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_unresolved(self, user_id: int, limit: int = 100) -> list[ErrorLog]:
        """Get unresolved errors for a user"""
        return self.list(user_id=user_id, resolved=False, limit=limit)

    def resolve(
        self,
        error_id: int,
        resolved_by: int,
        resolution_notes: str | None = None,
    ) -> ErrorLog:
        """Mark an error as resolved"""
        error = self.get(error_id)
        if not error:
            raise ValueError(f"Error log {error_id} not found")

        error.resolved = True
        error.resolved_at = ist_now()
        error.resolved_by = resolved_by
        if resolution_notes:
            error.resolution_notes = resolution_notes[:512]  # Truncate to max length

        self.db.commit()
        self.db.refresh(error)
        return error

    def count_unresolved(self, user_id: int) -> int:
        """Count unresolved errors for a user"""
        stmt = select(ErrorLog).where(
            ErrorLog.user_id == user_id,
            ErrorLog.resolved.is_(False),
        )
        return len(list(self.db.execute(stmt).scalars().all()))

    def delete_old_errors(
        self, user_id: int, before_date: datetime, resolved_only: bool = True
    ) -> int:
        """Delete old error logs (for retention)"""
        stmt = select(ErrorLog).where(
            and_(
                ErrorLog.user_id == user_id,
                ErrorLog.occurred_at < before_date,
            )
        )
        if resolved_only:
            stmt = stmt.where(ErrorLog.resolved.is_(True))

        errors_to_delete = list(self.db.execute(stmt).scalars().all())
        count = len(errors_to_delete)
        for error in errors_to_delete:
            self.db.delete(error)
        self.db.commit()
        return count

    def delete_old_errors_for_all(self, before_date: datetime, resolved_only: bool = True) -> int:
        """Delete old error logs across all users."""
        stmt = select(ErrorLog).where(ErrorLog.occurred_at < before_date)
        if resolved_only:
            stmt = stmt.where(ErrorLog.resolved.is_(True))

        errors_to_delete = list(self.db.execute(stmt).scalars().all())
        count = len(errors_to_delete)
        for error in errors_to_delete:
            self.db.delete(error)
        self.db.commit()
        return count
