"""
Unit tests for IndividualServiceManager - Default Schedules

Tests for:
- Auto-creation of default schedules when missing
- get_status returns services when schedules exist
"""

import pytest

from src.application.services.individual_service_manager import (
    IndividualServiceManager,
)
from src.infrastructure.db.models import Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.service_schedule_repository import (
    ServiceScheduleRepository,
)


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    user = Users(
        email="test@example.com",
        password_hash="hashed_password",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestIndividualServiceManagerSchedules:
    """Test suite for IndividualServiceManager default schedules"""

    def test_ensure_default_schedules_creates_when_missing(self, db_session, sample_user):
        """Test that default schedules are created when none exist"""
        manager = IndividualServiceManager(db_session)
        schedule_repo = ServiceScheduleRepository(db_session)

        # Verify no schedules exist initially
        schedules = schedule_repo.get_all()
        assert len(schedules) == 0

        # Call get_status which should trigger _ensure_default_schedules
        status = manager.get_status(sample_user.id)

        # Verify schedules were created
        schedules = schedule_repo.get_all()
        assert (
            len(schedules) == 6
        )  # premarket_retry, sell_monitor, position_monitor, analysis, buy_orders, eod_cleanup

        # Verify specific schedules exist
        task_names = {s.task_name for s in schedules}
        expected_tasks = {
            "premarket_retry",
            "sell_monitor",
            "position_monitor",
            "analysis",
            "buy_orders",
            "eod_cleanup",
        }
        assert task_names == expected_tasks

        # Verify schedule properties
        premarket = schedule_repo.get_by_task_name("premarket_retry")
        assert premarket is not None
        assert premarket.schedule_time.hour == 9
        assert premarket.schedule_time.minute == 0
        assert premarket.enabled is True
        assert premarket.schedule_type == "daily"

        sell_monitor = schedule_repo.get_by_task_name("sell_monitor")
        assert sell_monitor is not None
        assert sell_monitor.is_continuous is True
        assert sell_monitor.end_time is not None
        assert sell_monitor.end_time.hour == 15
        assert sell_monitor.end_time.minute == 30

        position_monitor = schedule_repo.get_by_task_name("position_monitor")
        assert position_monitor is not None
        assert position_monitor.is_hourly is True

    def test_ensure_default_schedules_does_not_duplicate(self, db_session, sample_user):
        """Test that default schedules are not duplicated if they already exist"""
        from datetime import time

        schedule_repo = ServiceScheduleRepository(db_session)

        # Create one schedule manually
        schedule_repo.create_or_update(
            task_name="premarket_retry",
            schedule_time=time(9, 0),
            enabled=True,
            is_hourly=False,
            is_continuous=False,
            schedule_type="daily",
            description="Existing schedule",
        )
        db_session.commit()

        # Create a new manager instance (to reset _schedules_checked flag)
        manager = IndividualServiceManager(db_session)

        # Call get_status which should trigger _ensure_default_schedules
        status = manager.get_status(sample_user.id)

        # Verify only one premarket_retry schedule exists
        premarket_schedules = [
            s for s in schedule_repo.get_all() if s.task_name == "premarket_retry"
        ]
        assert len(premarket_schedules) == 1

        # Verify other schedules were still created
        schedules = schedule_repo.get_all()
        assert len(schedules) == 6  # 1 existing + 5 new

    def test_get_status_returns_services_when_schedules_exist(self, db_session, sample_user):
        """Test that get_status returns service status for all scheduled tasks"""
        manager = IndividualServiceManager(db_session)

        # Call get_status which should create schedules and return status
        status = manager.get_status(sample_user.id)

        # Verify status contains all scheduled tasks
        assert isinstance(status, dict)
        assert len(status) == 6  # All 6 default schedules

        # Verify each task has required fields
        for task_name, info in status.items():
            assert "is_running" in info
            assert "schedule_enabled" in info
            assert "started_at" in info
            assert "last_execution_at" in info
            assert "next_execution_at" in info
            assert "process_id" in info

        # Verify initial state
        for task_name, info in status.items():
            assert info["is_running"] is False
            assert info["schedule_enabled"] is True
            assert info["process_id"] is None

    def test_get_status_handles_empty_database(self, db_session, sample_user):
        """Test that get_status works correctly with empty database"""
        manager = IndividualServiceManager(db_session)

        # Call get_status on empty database
        status = manager.get_status(sample_user.id)

        # Should still return status for all default schedules
        assert isinstance(status, dict)
        assert len(status) == 6

        # Verify schedules were created in database
        schedule_repo = ServiceScheduleRepository(db_session)
        schedules = schedule_repo.get_all()
        assert len(schedules) == 6
