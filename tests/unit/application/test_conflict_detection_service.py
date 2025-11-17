# ruff: noqa: PLC0415

"""
Unit tests for ConflictDetectionService

Tests for:
- Unified service running detection
- Conflict detection logic
- Task running detection
- Individual service start validation
"""

from datetime import timedelta

import pytest

from src.application.services.conflict_detection_service import ConflictDetectionService
from src.infrastructure.db.models import ServiceStatus, ServiceTaskExecution, Users
from src.infrastructure.db.timezone_utils import ist_now


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
def conflict_service(db_session):
    """Create ConflictDetectionService instance"""
    return ConflictDetectionService(db_session)


def test_is_unified_service_running_when_running(db_session, sample_user, conflict_service):
    """Test that unified service running status is detected correctly"""
    # Create service status with running = True
    status = ServiceStatus(
        user_id=sample_user.id,
        service_running=True,
        error_count=0,
    )
    db_session.add(status)
    db_session.commit()

    assert conflict_service.is_unified_service_running(sample_user.id) is True


def test_is_unified_service_running_when_stopped(db_session, sample_user, conflict_service):
    """Test that unified service stopped status is detected correctly"""
    # Create service status with running = False
    status = ServiceStatus(
        user_id=sample_user.id,
        service_running=False,
        error_count=0,
    )
    db_session.add(status)
    db_session.commit()

    assert conflict_service.is_unified_service_running(sample_user.id) is False


def test_is_unified_service_running_when_no_status(db_session, sample_user, conflict_service):
    """Test that unified service returns False when no status exists"""
    assert conflict_service.is_unified_service_running(sample_user.id) is False


def test_check_conflict_no_unified_service(db_session, sample_user, conflict_service):
    """Test that no conflict is detected when unified service is not running"""
    has_conflict, message = conflict_service.check_conflict(sample_user.id, "premarket_retry")
    assert has_conflict is False
    assert message == ""


def test_check_conflict_recent_task_execution(db_session, sample_user, conflict_service):
    """Test that conflict is detected when task was executed recently in unified service"""
    # Create service status with running = True
    status = ServiceStatus(
        user_id=sample_user.id,
        service_running=True,
        error_count=0,
    )
    db_session.add(status)

    # Create recent task execution (within last 2 minutes)
    recent_time = ist_now() - timedelta(minutes=1)
    task_execution = ServiceTaskExecution(
        user_id=sample_user.id,
        task_name="premarket_retry",
        executed_at=recent_time,
        status="success",
        duration_seconds=10.0,
    )
    db_session.add(task_execution)
    db_session.commit()

    has_conflict, message = conflict_service.check_conflict(
        sample_user.id, "premarket_retry", check_recent_minutes=2
    )
    assert has_conflict is True
    assert "recently" in message.lower()


def test_check_conflict_old_task_execution(db_session, sample_user, conflict_service):
    """Test that no conflict is detected when task execution is old"""
    # Create service status with running = True
    status = ServiceStatus(
        user_id=sample_user.id,
        service_running=True,
        error_count=0,
    )
    db_session.add(status)

    # Create old task execution (more than 2 minutes ago)
    old_time = ist_now() - timedelta(minutes=5)
    task_execution = ServiceTaskExecution(
        user_id=sample_user.id,
        task_name="premarket_retry",
        executed_at=old_time,
        status="success",
        duration_seconds=10.0,
    )
    db_session.add(task_execution)
    db_session.commit()

    has_conflict, message = conflict_service.check_conflict(
        sample_user.id, "premarket_retry", check_recent_minutes=2
    )
    assert has_conflict is False


def test_can_start_individual_service_when_unified_not_running(
    db_session, sample_user, conflict_service
):
    """Test that individual service can start when unified service is not running"""
    can_start, message = conflict_service.can_start_individual_service(sample_user.id)
    assert can_start is True
    assert message == ""


def test_can_start_individual_service_when_unified_running(
    db_session, sample_user, conflict_service
):
    """Test that individual service cannot start when unified service is running"""
    # Create service status with running = True
    status = ServiceStatus(
        user_id=sample_user.id,
        service_running=True,
        error_count=0,
    )
    db_session.add(status)
    db_session.commit()

    can_start, message = conflict_service.can_start_individual_service(sample_user.id)
    assert can_start is False
    assert "unified service" in message.lower()
