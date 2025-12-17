"""
Unit tests for IndividualServiceTaskExecutionRepository - Timezone Handling

Tests for:
- get_latest_status_raw() returns timezone-aware datetimes in IST
- Proper timezone conversion from UTC (database storage) to IST
- Age calculations are accurate with timezone-aware datetimes
"""

from datetime import datetime, timedelta

import pytest
from freezegun import freeze_time

from src.infrastructure.db.models import IndividualServiceTaskExecution, Users
from src.infrastructure.db.timezone_utils import IST, ist_now
from src.infrastructure.persistence.individual_service_task_execution_repository import (
    IndividualServiceTaskExecutionRepository,
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


@pytest.fixture
def repository(db_session):
    """Create repository instance"""
    return IndividualServiceTaskExecutionRepository(db_session)


class TestIndividualServiceTaskExecutionRepositoryTimezone:
    """Test suite for timezone handling in IndividualServiceTaskExecutionRepository"""

    def test_get_latest_status_raw_returns_timezone_aware_datetime(
        self, db_session, sample_user, repository
    ):
        """Test that get_latest_status_raw() returns timezone-aware datetime in IST"""
        # Create an execution record
        execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=ist_now(),
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(execution)
        db_session.commit()

        # Get latest status using raw SQL
        result = repository.get_latest_status_raw(sample_user.id, "analysis")

        assert result is not None
        assert "executed_at" in result
        executed_at = result["executed_at"]

        # Verify it's a datetime object
        assert isinstance(executed_at, datetime)

        # Verify it's timezone-aware
        assert executed_at.tzinfo is not None, "executed_at should be timezone-aware"

        # Verify it's in IST timezone
        assert executed_at.tzinfo == IST, f"executed_at should be in IST, got {executed_at.tzinfo}"

    def test_get_latest_status_raw_timezone_conversion_accuracy(
        self, db_session, sample_user, repository
    ):
        """Test that timezone conversion from UTC to IST is accurate"""
        # Create execution at a specific IST time
        # IST is UTC+5:30, so 10:00 IST = 04:30 UTC
        with freeze_time("2025-12-18 10:00:00+05:30"):
            execution = IndividualServiceTaskExecution(
                user_id=sample_user.id,
                task_name="analysis",
                executed_at=ist_now(),  # This will be 10:00 IST
                status="running",
                duration_seconds=0.0,
                execution_type="run_once",
            )
            db_session.add(execution)
            db_session.commit()

        # Get latest status using raw SQL
        result = repository.get_latest_status_raw(sample_user.id, "analysis")

        assert result is not None
        executed_at = result["executed_at"]

        # Verify the timezone-aware datetime represents the correct IST time
        assert executed_at.tzinfo == IST
        # The hour should be 10 (IST), not 4 (UTC)
        assert executed_at.hour == 10, f"Expected hour 10 (IST), got {executed_at.hour}"

    def test_get_latest_status_raw_age_calculation_accuracy(
        self, db_session, sample_user, repository
    ):
        """Test that age calculations using the returned datetime are accurate"""
        # Create execution 2 minutes ago
        two_minutes_ago = ist_now() - timedelta(minutes=2)

        execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=two_minutes_ago,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(execution)
        db_session.commit()

        # Get latest status using raw SQL
        result = repository.get_latest_status_raw(sample_user.id, "analysis")

        assert result is not None
        executed_at = result["executed_at"]

        # Calculate age using ist_now() (both should be in IST)
        current_time = ist_now()
        age = current_time - executed_at

        # Age should be approximately 2 minutes (allow small tolerance for test execution time)
        assert (
            timedelta(minutes=1, seconds=50) <= age <= timedelta(minutes=2, seconds=10)
        ), f"Expected age ~2 minutes, got {age.total_seconds()} seconds"

    def test_get_latest_status_raw_handles_naive_datetime_from_postgres(
        self, db_session, sample_user, repository
    ):
        """Test that naive datetime from PostgreSQL is converted to timezone-aware IST"""
        # Create execution
        execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=ist_now(),
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(execution)
        db_session.commit()

        # Get latest status using raw SQL
        result = repository.get_latest_status_raw(sample_user.id, "analysis")

        assert result is not None
        executed_at = result["executed_at"]

        # Even if PostgreSQL returns naive datetime, it should be converted to timezone-aware
        assert executed_at.tzinfo is not None
        assert executed_at.tzinfo == IST

    def test_get_latest_status_raw_returns_none_when_no_execution(
        self, db_session, sample_user, repository
    ):
        """Test that get_latest_status_raw() returns None when no execution exists"""
        result = repository.get_latest_status_raw(sample_user.id, "analysis")
        assert result is None

    def test_get_latest_status_raw_multiple_executions_returns_latest(
        self, db_session, sample_user, repository
    ):
        """Test that get_latest_status_raw() returns the most recent execution"""
        # Create older execution
        older_time = ist_now() - timedelta(hours=1)
        older_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=older_time,
            status="success",
            duration_seconds=100.0,
            execution_type="run_once",
        )
        db_session.add(older_execution)

        # Create newer execution
        newer_time = ist_now()
        newer_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=newer_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(newer_execution)
        db_session.commit()

        # Get latest status
        result = repository.get_latest_status_raw(sample_user.id, "analysis")

        assert result is not None
        assert result["status"] == "running"  # Should be the newer execution
        assert result["id"] == newer_execution.id
