"""Schedule Manager Service

Manages service schedules and calculates next execution times.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.service_schedule_repository import (
    ServiceScheduleRepository,
)

# Constants
HOURS_PER_DAY = 24
MINUTES_PER_HOUR = 60
POSITION_MONITOR_MINUTE = 30
WEEKEND_START_WEEKDAY = 5  # Saturday


def _preserve_timezone(naive_dt: datetime, aware_dt: datetime) -> datetime:
    """Preserve timezone from aware datetime to naive datetime"""
    return naive_dt.replace(tzinfo=aware_dt.tzinfo) if aware_dt.tzinfo else naive_dt


class ScheduleManager:
    """Service for managing and calculating service schedules"""

    def __init__(self, db: Session):
        self.db = db
        self._schedule_repo = ServiceScheduleRepository(db)

    def get_schedule(self, task_name: str):
        """Get schedule for a task"""
        return self._schedule_repo.get_by_task_name(task_name)

    def get_all_schedules(self):
        """Get all schedules"""
        return self._schedule_repo.get_all()

    def get_enabled_schedules(self):
        """Get all enabled schedules"""
        return self._schedule_repo.get_enabled()

    def calculate_next_execution(
        self, task_name: str, current_time: datetime | None = None
    ) -> datetime | None:
        """
        Calculate next execution time for a task based on its schedule.

        Args:
            task_name: Task name
            current_time: Current time (defaults to IST now)

        Returns:
            Next execution datetime or None if disabled
        """
        if current_time is None:
            current_time = ist_now()

        schedule = self.get_schedule(task_name)
        if not schedule or not schedule.enabled:
            return None

        current_date = current_time.date()
        current_time_only = current_time.time()

        if schedule.is_continuous:
            # Continuous task (sell_monitor): runs from schedule_time to end_time
            if schedule.end_time:
                if current_time_only < schedule.schedule_time:
                    # Before start time, next execution is today at schedule_time
                    result = datetime.combine(current_date, schedule.schedule_time)
                    return _preserve_timezone(result, current_time)
                elif current_time_only < schedule.end_time:
                    # Within continuous window, next execution is now (runs continuously)
                    return current_time
                else:
                    # After end time, next execution is tomorrow at schedule_time
                    next_date = current_date + timedelta(days=1)
                    result = datetime.combine(next_date, schedule.schedule_time)
                    return _preserve_timezone(result, current_time)
            # No end time, runs continuously from schedule_time
            elif current_time_only < schedule.schedule_time:
                result = datetime.combine(current_date, schedule.schedule_time)
                return _preserve_timezone(result, current_time)
            else:
                return current_time

        elif schedule.is_hourly:
            # Hourly task (position_monitor): runs at :30 minutes every hour
            schedule_minute = schedule.schedule_time.minute

            # Calculate next execution
            if current_time.minute < schedule_minute:
                # Same hour, just update minute
                next_execution = current_time.replace(
                    minute=schedule_minute, second=0, microsecond=0
                )
            else:
                # Next hour
                next_hour = current_time.hour + 1
                if next_hour >= HOURS_PER_DAY:
                    # Day rollover
                    next_date = current_date + timedelta(days=1)
                    result = datetime.combine(next_date, time(0, schedule_minute))
                    next_execution = _preserve_timezone(result, current_time)
                else:
                    next_execution = current_time.replace(
                        hour=next_hour, minute=schedule_minute, second=0, microsecond=0
                    )

            # Check if within valid hours (9:30 - 15:30 for position_monitor)
            if schedule.end_time:
                end_hour = schedule.end_time.hour
                if next_execution.hour > end_hour:
                    # Past end time, next execution is tomorrow at schedule_time
                    next_date = current_date + timedelta(days=1)
                    result = datetime.combine(next_date, schedule.schedule_time)
                    next_execution = _preserve_timezone(result, current_time)

            return next_execution

        else:
            # One-time daily task
            result = datetime.combine(current_date, schedule.schedule_time)
            schedule_datetime = _preserve_timezone(result, current_time)

            if current_time < schedule_datetime:
                # Today's execution hasn't happened yet
                return schedule_datetime
            else:
                # Today's execution already passed, next is tomorrow
                next_date = current_date + timedelta(days=1)
                result = datetime.combine(next_date, schedule.schedule_time)
                return _preserve_timezone(result, current_time)

    def validate_schedule(
        self,
        task_name: str,
        schedule_time: time,
        is_hourly: bool = False,
        is_continuous: bool = False,
        end_time: time | None = None,
    ) -> tuple[bool, str]:
        """
        Validate schedule configuration.

        Returns:
            (is_valid: bool, error_message: str)
        """
        # Time format validation
        if not (
            0 <= schedule_time.hour < HOURS_PER_DAY and 0 <= schedule_time.minute < MINUTES_PER_HOUR
        ):
            return False, "Invalid time format"

        # Position monitor: must be at :30 minutes if hourly
        if task_name == "position_monitor" and is_hourly:
            if schedule_time.minute != POSITION_MONITOR_MINUTE:
                return False, "Position monitor must be scheduled at :30 minutes when hourly"

        # Sell monitor: start time must be before end time if continuous
        if task_name == "sell_monitor" and is_continuous:
            if end_time and schedule_time >= end_time:
                return False, "Start time must be before end time for continuous tasks"

        # Business hours validation (9:00 - 18:00) for non-continuous, non-hourly tasks
        if not is_continuous and not is_hourly:
            if schedule_time < time(9, 0) or schedule_time > time(18, 0):
                return False, "Schedule time must be between 9:00 AM and 6:00 PM"

        # Valid task names
        valid_tasks = [
            "premarket_retry",
            "sell_monitor",
            "position_monitor",
            "analysis",
            "buy_orders",
            "eod_cleanup",
        ]
        if task_name not in valid_tasks:
            return False, f"Invalid task name. Must be one of: {', '.join(valid_tasks)}"

        return True, ""

    def is_trading_day(self, check_date: date | None = None) -> bool:
        """
        Check if a date is a trading day (Mon-Fri, excluding holidays).

        Args:
            check_date: Date to check (defaults to today)

        Returns:
            True if trading day, False otherwise
        """
        if check_date is None:
            check_date = ist_now().date()

        # Check if weekday (Monday=0, Sunday=6)
        weekday = check_date.weekday()
        if weekday >= WEEKEND_START_WEEKDAY:  # Saturday or Sunday
            return False

        # TODO: Add holiday checking logic if needed
        # For now, just check weekday

        return True
