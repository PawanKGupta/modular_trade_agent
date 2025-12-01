"""Conflict Detection Service

Detects conflicts between unified service and individual service executions.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from src.infrastructure.db.timezone_utils import IST, ist_now
from src.infrastructure.persistence.individual_service_task_execution_repository import (
    IndividualServiceTaskExecutionRepository,
)
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository
from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository


class ConflictDetectionService:
    """Service for detecting execution conflicts"""

    def __init__(self, db: Session):
        self.db = db
        self._service_status_repo = ServiceStatusRepository(db)
        self._service_task_repo = ServiceTaskRepository(db)
        self._individual_task_repo = IndividualServiceTaskExecutionRepository(db)

    def is_unified_service_running(self, user_id: int) -> bool:
        """Check if unified service is running for a user"""
        status = self._service_status_repo.get(user_id)
        return status.service_running if status else False

    def check_conflict(
        self, user_id: int, task_name: str, check_recent_minutes: int = 2
    ) -> tuple[bool, str]:
        """
        Check if running the task would conflict with unified service.

        Args:
            user_id: User ID
            task_name: Task name to check
            check_recent_minutes: Minutes to look back for recent executions

        Returns:
            (has_conflict: bool, message: str)
        """
        # Check if unified service is running
        unified_running = self.is_unified_service_running(user_id)
        if not unified_running:
            return False, ""

        # Check if task started within last N minutes in unified service
        # This serves as a proxy for "running" since ServiceTaskExecution
        # doesn't track "running" status
        recent_tasks = self._service_task_repo.list(user_id=user_id, task_name=task_name, limit=10)
        if recent_tasks:
            cutoff_time = ist_now() - timedelta(minutes=check_recent_minutes)
            for task in recent_tasks:
                # Normalize executed_at to timezone-aware if it's naive
                executed_at = task.executed_at
                if executed_at.tzinfo is None:
                    executed_at = executed_at.replace(tzinfo=IST)
                if executed_at >= cutoff_time:
                    msg = (
                        f"Task '{task_name}' was started recently in unified service "
                        f"(within last {check_recent_minutes} minutes)"
                    )
                    return (True, msg)

        # Check if task is currently executing in individual service
        running_individual = self._individual_task_repo.get_running_tasks(
            user_id=user_id, task_name=task_name
        )
        if running_individual:
            return True, f"Task '{task_name}' is currently running as individual service"

        # Check if task started recently in individual service
        recent_individual = self._individual_task_repo.get_recent_tasks(
            user_id=user_id, task_name=task_name, minutes=check_recent_minutes
        )
        if recent_individual:
            msg = (
                f"Task '{task_name}' was started recently as individual service "
                f"(within last {check_recent_minutes} minutes)"
            )
            return (True, msg)

        return False, ""

    def is_task_running(self, user_id: int, task_name: str) -> bool:
        """Check if task is currently running (unified or individual)"""
        # Check unified service - look for very recent tasks (within last 30 seconds)
        recent_unified = self._service_task_repo.list(user_id=user_id, task_name=task_name, limit=1)
        if recent_unified:
            cutoff_time = ist_now() - timedelta(seconds=30)
            executed_at = recent_unified[0].executed_at
            # Normalize executed_at to timezone-aware if it's naive
            if executed_at.tzinfo is None:
                executed_at = executed_at.replace(tzinfo=IST)
            if executed_at >= cutoff_time:
                return True

        # Check individual service
        running_individual = self._individual_task_repo.get_running_tasks(
            user_id=user_id, task_name=task_name
        )
        return len(running_individual) > 0

    def can_start_individual_service(self, user_id: int) -> tuple[bool, str]:
        """
        Check if individual service can be started (unified service must not be running).

        Returns:
            (can_start: bool, message: str)
        """
        if self.is_unified_service_running(user_id):
            return False, "Cannot start individual service when unified service is running"
        return True, ""
