"""Repository for IndividualServiceStatus management"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import IndividualServiceStatus
from src.infrastructure.db.timezone_utils import ist_now


class IndividualServiceStatusRepository:
    """Repository for managing individual service status per user"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_user_and_task(self, user_id: int, task_name: str) -> IndividualServiceStatus | None:
        """Get service status for a specific user and task"""
        stmt = select(IndividualServiceStatus).where(
            IndividualServiceStatus.user_id == user_id,
            IndividualServiceStatus.task_name == task_name,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_user(self, user_id: int) -> list[IndividualServiceStatus]:
        """List all service statuses for a user"""
        stmt = (
            select(IndividualServiceStatus)
            .where(IndividualServiceStatus.user_id == user_id)
            .order_by(IndividualServiceStatus.task_name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_running_services(self, user_id: int) -> list[IndividualServiceStatus]:
        """Get all running individual services for a user"""
        stmt = select(IndividualServiceStatus).where(
            IndividualServiceStatus.user_id == user_id,
            IndividualServiceStatus.is_running.is_(True),
        )
        return list(self.db.execute(stmt).scalars().all())

    def create_or_update(
        self,
        *,
        user_id: int,
        task_name: str,
        is_running: bool = False,
        started_at: datetime | None = None,
        last_execution_at: datetime | None = None,
        next_execution_at: datetime | None = None,
        process_id: int | None = None,
    ) -> IndividualServiceStatus:
        """Create or update service status"""
        status = self.get_by_user_and_task(user_id, task_name)
        if status:
            # Update existing
            status.is_running = is_running
            if started_at is not None:
                status.started_at = started_at
            if last_execution_at is not None:
                status.last_execution_at = last_execution_at
            if next_execution_at is not None:
                status.next_execution_at = next_execution_at
            if process_id is not None:
                status.process_id = process_id
            status.updated_at = ist_now()
        else:
            # Create new
            status = IndividualServiceStatus(
                user_id=user_id,
                task_name=task_name,
                is_running=is_running,
                started_at=started_at,
                last_execution_at=last_execution_at,
                next_execution_at=next_execution_at,
                process_id=process_id,
            )
            self.db.add(status)

        self.db.commit()
        self.db.refresh(status)
        return status

    def mark_running(
        self,
        user_id: int,
        task_name: str,
        process_id: int | None = None,
    ) -> IndividualServiceStatus:
        """Mark service as running"""
        return self.create_or_update(
            user_id=user_id,
            task_name=task_name,
            is_running=True,
            started_at=ist_now(),
            process_id=process_id,
        )

    def mark_stopped(self, user_id: int, task_name: str) -> IndividualServiceStatus:
        """Mark service as stopped"""
        status = self.get_by_user_and_task(user_id, task_name)
        if not status:
            # Create if doesn't exist
            return self.create_or_update(
                user_id=user_id,
                task_name=task_name,
                is_running=False,
            )

        status.is_running = False
        status.process_id = None
        status.updated_at = ist_now()
        self.db.commit()
        self.db.refresh(status)
        return status

    def update_last_execution(
        self, user_id: int, task_name: str, execution_time: datetime | None = None
    ) -> IndividualServiceStatus:
        """Update last execution time"""
        if execution_time is None:
            execution_time = ist_now()
        return self.create_or_update(
            user_id=user_id,
            task_name=task_name,
            last_execution_at=execution_time,
        )

    def update_next_execution(
        self, user_id: int, task_name: str, next_execution: datetime | None
    ) -> IndividualServiceStatus:
        """Update next execution time"""
        return self.create_or_update(
            user_id=user_id,
            task_name=task_name,
            next_execution_at=next_execution,
        )

    def mark_all_stopped(self, user_id: int) -> int:
        """Mark all individual services as stopped for a user (e.g., on server restart)"""
        services = self.list_by_user(user_id)
        count = 0
        for service in services:
            if service.is_running:
                service.is_running = False
                service.process_id = None
                service.updated_at = ist_now()
                count += 1
        if count > 0:
            self.db.commit()
        return count
