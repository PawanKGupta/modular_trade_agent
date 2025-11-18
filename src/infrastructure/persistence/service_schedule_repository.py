"""Repository for ServiceSchedule management"""

from __future__ import annotations

from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import ServiceSchedule
from src.infrastructure.db.timezone_utils import ist_now


class ServiceScheduleRepository:
    """Repository for managing service schedules (admin-editable)"""

    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[ServiceSchedule]:
        """Get all service schedules"""
        stmt = select(ServiceSchedule).order_by(ServiceSchedule.task_name)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_task_name(self, task_name: str) -> ServiceSchedule | None:
        """Get schedule by task name"""
        stmt = select(ServiceSchedule).where(ServiceSchedule.task_name == task_name)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_enabled(self) -> list[ServiceSchedule]:
        """Get all enabled schedules"""
        stmt = (
            select(ServiceSchedule)
            .where(ServiceSchedule.enabled.is_(True))
            .order_by(ServiceSchedule.task_name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create_or_update(
        self,
        *,
        task_name: str,
        schedule_time: time,
        enabled: bool = True,
        is_hourly: bool = False,
        is_continuous: bool = False,
        end_time: time | None = None,
        schedule_type: str = "daily",
        description: str | None = None,
        updated_by: int | None = None,
    ) -> ServiceSchedule:
        """Create or update a service schedule"""
        schedule = self.get_by_task_name(task_name)
        if schedule:
            # Update existing
            schedule.schedule_time = schedule_time
            schedule.enabled = enabled
            schedule.is_hourly = is_hourly
            schedule.is_continuous = is_continuous
            schedule.end_time = end_time
            schedule.schedule_type = schedule_type
            if description is not None:
                schedule.description = description
            if updated_by is not None:
                schedule.updated_by = updated_by
            schedule.updated_at = ist_now()
        else:
            # Create new
            schedule = ServiceSchedule(
                task_name=task_name,
                schedule_time=schedule_time,
                enabled=enabled,
                is_hourly=is_hourly,
                is_continuous=is_continuous,
                end_time=end_time,
                schedule_type=schedule_type,
                description=description,
                updated_by=updated_by,
            )
            self.db.add(schedule)

        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def update_enabled(
        self, task_name: str, enabled: bool, updated_by: int | None = None
    ) -> ServiceSchedule | None:
        """Update enabled status for a schedule"""
        schedule = self.get_by_task_name(task_name)
        if not schedule:
            return None

        schedule.enabled = enabled
        if updated_by is not None:
            schedule.updated_by = updated_by
        schedule.updated_at = ist_now()
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def bulk_update_enabled(self, enabled: bool, updated_by: int | None = None) -> int:
        """Bulk update enabled status for all schedules"""
        schedules = self.get_all()
        count = 0
        for schedule in schedules:
            schedule.enabled = enabled
            if updated_by is not None:
                schedule.updated_by = updated_by
            schedule.updated_at = ist_now()
            count += 1
        self.db.commit()
        return count
