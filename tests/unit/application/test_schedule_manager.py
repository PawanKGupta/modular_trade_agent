# ruff: noqa: PLC0415

"""
Unit tests for ScheduleManager

Tests for:
- Schedule retrieval
- Next execution time calculation
- Schedule validation
- Trading day detection
"""

from datetime import datetime, time, timedelta

import pytest

from src.application.services.schedule_manager import ScheduleManager
from src.infrastructure.db.models import ServiceSchedule
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def schedule_manager(db_session):
    """Create ScheduleManager instance"""
    return ScheduleManager(db_session)


@pytest.fixture
def sample_schedules(db_session):
    """Create sample schedules for testing"""
    schedules = [
        ServiceSchedule(
            task_name="premarket_retry",
            schedule_time=time(9, 0),
            enabled=True,
            is_hourly=False,
            is_continuous=False,
            end_time=None,
            schedule_type="daily",
            description="Retries failed orders",
            created_at=ist_now(),
            updated_at=ist_now(),
        ),
        ServiceSchedule(
            task_name="position_monitor",
            schedule_time=time(9, 30),
            enabled=True,
            is_hourly=True,
            is_continuous=False,
            end_time=time(15, 30),
            schedule_type="daily",
            description="Hourly position monitoring",
            created_at=ist_now(),
            updated_at=ist_now(),
        ),
        ServiceSchedule(
            task_name="sell_monitor",
            schedule_time=time(9, 15),
            enabled=True,
            is_hourly=False,
            is_continuous=True,
            end_time=time(15, 30),
            schedule_type="daily",
            description="Continuous sell monitoring",
            created_at=ist_now(),
            updated_at=ist_now(),
        ),
    ]
    for schedule in schedules:
        db_session.add(schedule)
    db_session.commit()
    return schedules


def test_get_schedule_exists(db_session, schedule_manager, sample_schedules):
    """Test retrieving an existing schedule"""
    schedule = schedule_manager.get_schedule("premarket_retry")
    assert schedule is not None
    assert schedule.task_name == "premarket_retry"
    assert schedule.schedule_time == time(9, 0)


def test_get_schedule_not_exists(db_session, schedule_manager):
    """Test retrieving a non-existent schedule"""
    schedule = schedule_manager.get_schedule("nonexistent_task")
    assert schedule is None


def test_get_all_schedules(db_session, schedule_manager, sample_schedules):
    """Test retrieving all schedules"""
    schedules = schedule_manager.get_all_schedules()
    assert len(schedules) == 3
    task_names = {s.task_name for s in schedules}
    assert "premarket_retry" in task_names
    assert "position_monitor" in task_names
    assert "sell_monitor" in task_names


def test_get_enabled_schedules(db_session, schedule_manager, sample_schedules):
    """Test retrieving only enabled schedules"""
    # Disable one schedule
    sample_schedules[0].enabled = False
    db_session.commit()

    enabled = schedule_manager.get_enabled_schedules()
    assert len(enabled) == 2
    assert all(s.enabled for s in enabled)


def test_calculate_next_execution_one_time_task(db_session, schedule_manager, sample_schedules):
    """Test next execution calculation for one-time daily task"""
    # Set current time to before schedule time
    current_time = datetime.combine(ist_now().date(), time(8, 0))
    next_exec = schedule_manager.calculate_next_execution("premarket_retry", current_time)
    assert next_exec is not None
    assert next_exec.date() == current_time.date()
    assert next_exec.time() == time(9, 0)

    # Set current time to after schedule time
    current_time = datetime.combine(ist_now().date(), time(10, 0))
    next_exec = schedule_manager.calculate_next_execution("premarket_retry", current_time)
    assert next_exec is not None
    assert next_exec.date() == (current_time.date() + timedelta(days=1))
    assert next_exec.time() == time(9, 0)


def test_calculate_next_execution_hourly_task(db_session, schedule_manager, sample_schedules):
    """Test next execution calculation for hourly task"""
    # Set current time to before first execution
    current_time = datetime.combine(ist_now().date(), time(9, 0))
    next_exec = schedule_manager.calculate_next_execution("position_monitor", current_time)
    assert next_exec is not None
    assert next_exec.time() == time(9, 30)

    # Set current time to after :30 minutes
    current_time = datetime.combine(ist_now().date(), time(10, 45))
    next_exec = schedule_manager.calculate_next_execution("position_monitor", current_time)
    assert next_exec is not None
    assert next_exec.hour == 11
    assert next_exec.minute == 30


def test_calculate_next_execution_continuous_task(db_session, schedule_manager, sample_schedules):
    """Test next execution calculation for continuous task"""
    # Set current time to before start time
    current_time = datetime.combine(ist_now().date(), time(8, 0))
    next_exec = schedule_manager.calculate_next_execution("sell_monitor", current_time)
    assert next_exec is not None
    assert next_exec.time() == time(9, 15)

    # Set current time to within continuous window
    current_time = datetime.combine(ist_now().date(), time(10, 0))
    next_exec = schedule_manager.calculate_next_execution("sell_monitor", current_time)
    assert next_exec is not None
    # Should return current time (runs continuously)
    assert next_exec <= current_time + timedelta(seconds=1)


def test_calculate_next_execution_disabled_task(db_session, schedule_manager, sample_schedules):
    """Test that disabled tasks return None"""
    sample_schedules[0].enabled = False
    db_session.commit()

    next_exec = schedule_manager.calculate_next_execution("premarket_retry")
    assert next_exec is None


def test_validate_schedule_valid(db_session, schedule_manager):
    """Test validation of a valid schedule"""
    is_valid, message = schedule_manager.validate_schedule(
        task_name="premarket_retry",
        schedule_time=time(9, 0),
        is_hourly=False,
        is_continuous=False,
        end_time=None,
        schedule_type="daily",
    )
    assert is_valid is True
    assert message == ""


def test_validate_schedule_invalid_time(db_session, schedule_manager):
    """Test validation fails for time outside business hours"""
    # Test with time outside business hours (9:00 - 18:00) for non-continuous, non-hourly tasks
    is_valid, message = schedule_manager.validate_schedule(
        task_name="premarket_retry",
        schedule_time=time(8, 0),  # Before business hours
        is_hourly=False,
        is_continuous=False,
        end_time=None,
        schedule_type="daily",
    )
    assert not is_valid
    assert "business hours" in message.lower() or "9:00" in message or "18:00" in message


def test_validate_schedule_once_with_hourly_invalid(db_session, schedule_manager):
    """Test that schedule_type 'once' cannot be combined with hourly execution"""
    is_valid, message = schedule_manager.validate_schedule(
        task_name="analysis",
        schedule_time=time(16, 0),
        is_hourly=True,
        is_continuous=False,
        end_time=None,
        schedule_type="once",
    )
    assert not is_valid
    assert "cannot be combined with hourly" in message.lower()


def test_validate_schedule_once_with_continuous_invalid(db_session, schedule_manager):
    """Test that schedule_type 'once' cannot be combined with continuous execution"""
    is_valid, message = schedule_manager.validate_schedule(
        task_name="sell_monitor",
        schedule_time=time(9, 15),
        is_hourly=False,
        is_continuous=True,
        end_time=time(15, 30),
        schedule_type="once",
    )
    assert not is_valid
    assert "cannot be combined with continuous" in message.lower()


def test_validate_schedule_once_with_end_time_invalid(db_session, schedule_manager):
    """Test that schedule_type 'once' cannot have an end time"""
    is_valid, message = schedule_manager.validate_schedule(
        task_name="analysis",
        schedule_time=time(16, 0),
        is_hourly=False,
        is_continuous=False,
        end_time=time(17, 0),
        schedule_type="once",
    )
    assert not is_valid
    assert "cannot have an end time" in message.lower()


def test_validate_schedule_analysis_flexible_time(db_session, schedule_manager):
    """Test analysis service can be scheduled between 4PM-9AM"""
    # Test 2:40 AM - should be allowed
    is_valid, message = schedule_manager.validate_schedule(
        task_name="analysis",
        schedule_time=time(2, 40),
        is_hourly=False,
        is_continuous=False,
        end_time=None,
        schedule_type="daily",
    )
    assert is_valid, f"2:40 AM should be valid for analysis: {message}"

    # Test 4:00 PM - should be allowed
    is_valid, message = schedule_manager.validate_schedule(
        task_name="analysis",
        schedule_time=time(16, 0),
        is_hourly=False,
        is_continuous=False,
        end_time=None,
        schedule_type="daily",
    )
    assert is_valid, f"4:00 PM should be valid for analysis: {message}"

    # Test 9:00 AM - should be allowed (boundary)
    is_valid, message = schedule_manager.validate_schedule(
        task_name="analysis",
        schedule_time=time(9, 0),
        is_hourly=False,
        is_continuous=False,
        end_time=None,
        schedule_type="daily",
    )
    assert is_valid, f"9:00 AM should be valid for analysis: {message}"

    # Test 10:00 AM - should NOT be allowed (between 9AM and 4PM)
    is_valid, message = schedule_manager.validate_schedule(
        task_name="analysis",
        schedule_time=time(10, 0),
        is_hourly=False,
        is_continuous=False,
        end_time=None,
        schedule_type="daily",
    )
    assert not is_valid
    assert "off-trading hours" in message.lower() or "4:00 PM" in message


def test_validate_schedule_position_monitor_hourly(db_session, schedule_manager):
    """Test validation for position monitor hourly requirement"""
    is_valid, message = schedule_manager.validate_schedule(
        task_name="position_monitor",
        schedule_time=time(9, 15),  # Not :30 minutes
        is_hourly=True,
        is_continuous=False,
        end_time=None,
        schedule_type="daily",
    )
    assert is_valid is False
    assert ":30" in message or "30" in message


def test_validate_schedule_sell_monitor_continuous(db_session, schedule_manager):
    """Test validation for sell monitor continuous requirement"""
    is_valid, message = schedule_manager.validate_schedule(
        task_name="sell_monitor",
        schedule_time=time(15, 30),
        is_hourly=False,
        is_continuous=True,
        end_time=time(9, 15),  # End before start
        schedule_type="daily",
    )
    assert is_valid is False
    assert "before" in message.lower() or "start" in message.lower()


def test_validate_schedule_invalid_task_name(db_session, schedule_manager):
    """Test validation fails for invalid task name"""
    is_valid, message = schedule_manager.validate_schedule(
        task_name="invalid_task",
        schedule_time=time(9, 0),
        is_hourly=False,
        is_continuous=False,
        end_time=None,
        schedule_type="daily",
    )
    assert is_valid is False
    assert "invalid" in message.lower()


def test_is_trading_day_weekday(db_session, schedule_manager):
    """Test that weekdays are trading days"""
    # Get a weekday (Monday = 0, Friday = 4)
    today = ist_now().date()
    weekday = today.weekday()
    if weekday < 5:  # Monday-Friday
        assert schedule_manager.is_trading_day(today) is True


def test_is_trading_day_weekend(db_session, schedule_manager):
    """Test that weekends are not trading days"""
    # Get a Saturday (5) or Sunday (6)
    today = ist_now().date()
    weekday = today.weekday()
    if weekday >= 5:  # Saturday or Sunday
        assert schedule_manager.is_trading_day(today) is False
