"""Repository for ServiceTaskExecution management"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import ServiceTaskExecution
from src.infrastructure.db.timezone_utils import ist_now


class ServiceTaskRepository:
    """Repository for managing task execution history"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        task_name: str,
        status: Literal["success", "failed", "skipped"],
        duration_seconds: float,
        details: dict | None = None,
    ) -> ServiceTaskExecution:
        """Create a new task execution record"""
        task = ServiceTaskExecution(
            user_id=user_id,
            task_name=task_name,
            executed_at=ist_now(),
            status=status,
            duration_seconds=duration_seconds,
            details=details,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get(self, task_id: int) -> ServiceTaskExecution | None:
        """Get task execution by ID"""
        return self.db.get(ServiceTaskExecution, task_id)

    def list(
        self,
        user_id: int,
        task_name: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ServiceTaskExecution]:
        """List task executions for a user"""
        stmt = select(ServiceTaskExecution).where(ServiceTaskExecution.user_id == user_id)

        if task_name:
            stmt = stmt.where(ServiceTaskExecution.task_name == task_name)
        if status:
            stmt = stmt.where(ServiceTaskExecution.status == status)

        stmt = stmt.order_by(desc(ServiceTaskExecution.executed_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_latest(self, user_id: int, task_name: str | None = None) -> ServiceTaskExecution | None:
        """Get latest task execution for a user"""
        stmt = select(ServiceTaskExecution).where(ServiceTaskExecution.user_id == user_id)

        if task_name:
            stmt = stmt.where(ServiceTaskExecution.task_name == task_name)

        stmt = stmt.order_by(desc(ServiceTaskExecution.executed_at)).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()

    def count_by_status(self, user_id: int, status: str) -> int:
        """Count tasks by status for a user"""
        stmt = select(ServiceTaskExecution).where(
            ServiceTaskExecution.user_id == user_id,
            ServiceTaskExecution.status == status,
        )
        return len(list(self.db.execute(stmt).scalars().all()))
