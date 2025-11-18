"""Repository for IndividualServiceTaskExecution management"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from src.infrastructure.db.models import IndividualServiceTaskExecution
from src.infrastructure.db.timezone_utils import ist_now


class IndividualServiceTaskExecutionRepository:
    """Repository for managing individual service task execution history"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        task_name: str,
        status: Literal["success", "failed", "skipped", "running"],
        duration_seconds: float,
        details: dict | None = None,
        execution_type: Literal["scheduled", "run_once", "manual"] = "scheduled",
    ) -> IndividualServiceTaskExecution:
        """Create a new task execution record"""
        task = IndividualServiceTaskExecution(
            user_id=user_id,
            task_name=task_name,
            executed_at=ist_now(),
            status=status,
            duration_seconds=duration_seconds,
            details=details,
            execution_type=execution_type,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get(self, task_id: int) -> IndividualServiceTaskExecution | None:
        """Get task execution by ID"""
        return self.db.get(IndividualServiceTaskExecution, task_id)

    def list(
        self,
        user_id: int,
        task_name: str | None = None,
        status: str | None = None,
        execution_type: str | None = None,
        limit: int = 100,
    ) -> list[IndividualServiceTaskExecution]:
        """List task executions for a user"""
        stmt = select(IndividualServiceTaskExecution).where(
            IndividualServiceTaskExecution.user_id == user_id
        )

        if task_name:
            stmt = stmt.where(IndividualServiceTaskExecution.task_name == task_name)
        if status:
            stmt = stmt.where(IndividualServiceTaskExecution.status == status)
        if execution_type:
            stmt = stmt.where(IndividualServiceTaskExecution.execution_type == execution_type)

        stmt = stmt.order_by(desc(IndividualServiceTaskExecution.executed_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_latest(
        self, user_id: int, task_name: str | None = None
    ) -> IndividualServiceTaskExecution | None:
        """Get latest task execution for a user"""
        stmt = select(IndividualServiceTaskExecution).where(
            IndividualServiceTaskExecution.user_id == user_id
        )

        if task_name:
            stmt = stmt.where(IndividualServiceTaskExecution.task_name == task_name)

        stmt = stmt.order_by(desc(IndividualServiceTaskExecution.executed_at)).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_latest_status_raw(self, user_id: int, task_name: str) -> dict | None:
        """Get latest execution status using raw SQL to bypass session cache.

        Returns dict with: id, status, executed_at, duration_seconds, details
        """
        # Use raw SQL to bypass SQLAlchemy session cache
        # This ensures we see commits from other threads immediately
        sql = text(
            """
            SELECT id, status, executed_at, duration_seconds, details
            FROM individual_service_task_execution
            WHERE user_id = :user_id AND task_name = :task_name
            ORDER BY executed_at DESC
            LIMIT 1
        """
        )
        result = self.db.execute(sql, {"user_id": user_id, "task_name": task_name}).fetchone()
        if result:
            # Parse datetime field (SQLite may return datetime as string or object)
            executed_at = result[2]
            if isinstance(executed_at, str):
                try:
                    # Try parsing ISO format datetime string
                    if "Z" in executed_at:
                        executed_at = datetime.fromisoformat(executed_at.replace("Z", "+00:00"))
                    else:
                        executed_at = datetime.fromisoformat(executed_at)
                except (ValueError, AttributeError):
                    # Fallback: try parsing common SQLite datetime formats
                    try:
                        executed_at = datetime.strptime(executed_at, "%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        try:
                            executed_at = datetime.strptime(executed_at, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            # If all parsing fails, return as-is (will cause error but better than crashing)
                            executed_at = result[2]
            # If it's already a datetime object, use it as-is
            elif not isinstance(executed_at, datetime):
                executed_at = None

            # Parse JSON details field (SQLite returns JSON as string)
            details = result[4]
            if isinstance(details, str):
                try:
                    details = json.loads(details) if details else None
                except (json.JSONDecodeError, TypeError):
                    details = None
            elif details is None:
                details = None

            return {
                "id": result[0],
                "status": result[1],
                "executed_at": executed_at,
                "duration_seconds": result[3],
                "details": details,
            }
        return None

    def get_running_tasks(
        self, user_id: int, task_name: str | None = None
    ) -> list[IndividualServiceTaskExecution]:
        """Get currently running tasks (status='running')"""
        stmt = select(IndividualServiceTaskExecution).where(
            IndividualServiceTaskExecution.user_id == user_id,
            IndividualServiceTaskExecution.status == "running",
        )

        if task_name:
            stmt = stmt.where(IndividualServiceTaskExecution.task_name == task_name)

        return list(self.db.execute(stmt).scalars().all())

    def get_recent_tasks(
        self, user_id: int, task_name: str, minutes: int = 2
    ) -> list[IndividualServiceTaskExecution]:
        """Get tasks that started within the last N minutes"""
        from datetime import timedelta  # noqa: PLC0415

        cutoff_time = ist_now() - timedelta(minutes=minutes)
        stmt = (
            select(IndividualServiceTaskExecution)
            .where(
                IndividualServiceTaskExecution.user_id == user_id,
                IndividualServiceTaskExecution.task_name == task_name,
                IndividualServiceTaskExecution.executed_at >= cutoff_time,
            )
            .order_by(desc(IndividualServiceTaskExecution.executed_at))
        )

        return list(self.db.execute(stmt).scalars().all())

    def count_by_status(self, user_id: int, status: str) -> int:
        """Count tasks by status for a user"""
        stmt = select(IndividualServiceTaskExecution).where(
            IndividualServiceTaskExecution.user_id == user_id,
            IndividualServiceTaskExecution.status == status,
        )
        return len(list(self.db.execute(stmt).scalars().all()))
