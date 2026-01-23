"""
Unit tests for IndividualServiceManager - Timeout and Stale Execution Cleanup

Tests for:
- 2-minute timeout for all tasks (including analysis)
- Stale execution cleanup with correct timeout
- Age calculation accuracy with timezone-aware datetimes
- No false "failed" status due to timezone issues
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from src.application.services.individual_service_manager import (
    IndividualServiceManager,
)
from src.infrastructure.db.models import (
    IndividualServiceTaskExecution,
    Users,
)
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


class TestIndividualServiceManagerTimeout:
    """Test suite for timeout and stale execution cleanup"""

    def test_cleanup_stale_execution_uses_5_minute_timeout(self, db_session, sample_user):
        """Test that _cleanup_stale_execution uses 2-minute timeout for all tasks"""
        manager = IndividualServiceManager(db_session)

        # Create a stale execution (3 minutes old - should be cleaned up)
        stale_time = ist_now() - timedelta(minutes=3)
        stale_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=stale_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(stale_execution)
        db_session.commit()

        # Clean up stale executions
        cleaned = manager._cleanup_stale_execution(sample_user.id, "analysis", context="test")

        # Should have cleaned up the stale execution
        assert cleaned is True

        # Verify execution was marked as failed
        db_session.refresh(stale_execution)
        assert stale_execution.status == "failed"
        assert stale_execution.details is not None
        assert "stale_execution" in str(stale_execution.details)

    def test_cleanup_stale_execution_does_not_clean_recent_execution(self, db_session, sample_user):
        """Test that _cleanup_stale_execution does not clean recent executions (< 2 minutes)"""
        manager = IndividualServiceManager(db_session)

        # Create a recent execution (1 minute old - should NOT be cleaned up)
        recent_time = ist_now() - timedelta(minutes=1)
        recent_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=recent_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(recent_execution)
        db_session.commit()
        execution_id = recent_execution.id

        # Clean up stale executions
        cleaned = manager._cleanup_stale_execution(sample_user.id, "analysis", context="test")

        # Should NOT have cleaned up the recent execution
        assert cleaned is False

        # Verify execution is still running
        db_session.refresh(recent_execution)
        assert recent_execution.status == "running"
        assert recent_execution.id == execution_id

    def test_cleanup_stale_execution_5_minute_boundary(self, db_session, sample_user):
        """Test that _cleanup_stale_execution correctly handles 2-minute boundary"""
        manager = IndividualServiceManager(db_session)

        # Create execution just beyond 2-minute boundary (should be cleaned up)
        boundary_time = ist_now() - timedelta(minutes=2, seconds=1)
        boundary_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=boundary_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(boundary_execution)
        db_session.commit()

        # Clean up stale executions
        cleaned = manager._cleanup_stale_execution(sample_user.id, "analysis", context="test")

        # Should have cleaned up (2 minutes + 1 second > 2 minutes)
        assert cleaned is True
        db_session.refresh(boundary_execution)
        assert boundary_execution.status == "failed"

    def test_cleanup_stale_execution_handles_timezone_correctly(self, db_session, sample_user):
        """Test that stale execution cleanup handles timezone correctly (no false positives)"""
        manager = IndividualServiceManager(db_session)

        # Create a fresh execution (just now)
        fresh_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=ist_now(),
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(fresh_execution)
        db_session.commit()
        execution_id = fresh_execution.id

        # Clean up stale executions
        cleaned = manager._cleanup_stale_execution(sample_user.id, "analysis", context="test")

        # Should NOT have cleaned up (fresh execution)
        assert cleaned is False

        # Verify execution is still running
        db_session.refresh(fresh_execution)
        assert fresh_execution.status == "running"
        assert fresh_execution.id == execution_id

    def test_cleanup_stale_execution_works_for_all_task_types(self, db_session, sample_user):
        """Test that 2-minute timeout applies to all task types, not just analysis"""
        manager = IndividualServiceManager(db_session)

        # Test with different task types
        task_types = ["analysis", "buy_orders", "sell_monitor", "eod_cleanup", "premarket_retry"]

        for task_name in task_types:
            # Create stale execution (3 minutes old)
            stale_time = ist_now() - timedelta(minutes=3)
            stale_execution = IndividualServiceTaskExecution(
                user_id=sample_user.id,
                task_name=task_name,
                executed_at=stale_time,
                status="running",
                duration_seconds=0.0,
                execution_type="run_once",
            )
            db_session.add(stale_execution)
            db_session.commit()

            # Clean up stale executions
            cleaned = manager._cleanup_stale_execution(sample_user.id, task_name, context="test")

            # Should have cleaned up for all task types
            assert cleaned is True, f"Should clean up stale {task_name} execution"
            db_session.refresh(stale_execution)
            assert stale_execution.status == "failed", f"{task_name} should be marked as failed"

            # Clean up for next iteration
            db_session.delete(stale_execution)
            db_session.commit()

    def test_get_status_uses_5_minute_timeout(self, db_session, sample_user):
        """Test that get_status() uses 2-minute timeout when checking for stale executions"""
        manager = IndividualServiceManager(db_session)

        # Create a stale execution (3 minutes old)
        stale_time = ist_now() - timedelta(minutes=3)
        stale_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=stale_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(stale_execution)
        db_session.commit()

        # Get status (should trigger cleanup)
        status = manager.get_status(sample_user.id)

        # Verify stale execution was cleaned up
        assert "analysis" in status
        analysis_status = status["analysis"]
        # The status should reflect that the execution was marked as failed
        # (exact structure depends on implementation, but should not show as running)

        # Verify execution was marked as failed in database
        db_session.refresh(stale_execution)
        assert stale_execution.status == "failed"

    def test_run_once_cleans_stale_executions_before_checking(self, db_session, sample_user):
        """Test that run_once() cleans stale executions before checking if task is running"""
        manager = IndividualServiceManager(db_session)

        # Create a stale execution (3 minutes old)
        stale_time = ist_now() - timedelta(minutes=3)
        stale_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=stale_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(stale_execution)
        db_session.commit()

        # Mock the actual task execution to avoid running real analysis
        with patch.object(manager, "_execute_task_once", return_value=None):
            # Try to run once (should clean up stale execution first)
            success, message, details = manager.run_once(sample_user.id, "analysis")

            # Should succeed (stale execution was cleaned up)
            assert success is True

            # Verify stale execution was marked as failed
            db_session.refresh(stale_execution)
            assert stale_execution.status == "failed"

    def test_age_calculation_accuracy_with_timezone(self, db_session, sample_user):
        """Test that age calculations are accurate with timezone-aware datetimes"""
        manager = IndividualServiceManager(db_session)

        # Create execution 1 minute ago
        one_minute_ago = ist_now() - timedelta(minutes=1)
        execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=one_minute_ago,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(execution)
        db_session.commit()

        # Clean up stale executions (should NOT clean up 1-minute-old execution)
        cleaned = manager._cleanup_stale_execution(sample_user.id, "analysis", context="test")

        # Should NOT have cleaned up (1 minute < 2 minutes)
        assert cleaned is False

        # Verify execution is still running
        db_session.refresh(execution)
        assert execution.status == "running"

    @freeze_time("2025-12-18 10:00:00+05:30")
    def test_timezone_handling_prevents_false_stale_detection(self, db_session, sample_user):
        """Test that proper timezone handling prevents false stale detection"""
        manager = IndividualServiceManager(db_session)

        # Create execution at current time (frozen)
        execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=ist_now(),  # Will be 10:00 IST
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(execution)
        db_session.commit()

        # Move time forward by 1 minute
        with freeze_time("2025-12-18 10:01:00+05:30"):
            # Clean up stale executions
            cleaned = manager._cleanup_stale_execution(sample_user.id, "analysis", context="test")

            # Should NOT have cleaned up (only 1 minute old)
            assert cleaned is False

            # Verify execution is still running
            db_session.refresh(execution)
            assert execution.status == "running"

    def test_multiple_stale_executions_all_cleaned_up(self, db_session, sample_user):
        """Test that all stale executions are cleaned up, not just the latest"""
        manager = IndividualServiceManager(db_session)

        # Create multiple stale executions
        stale_times = [
            ist_now() - timedelta(minutes=10),  # 10 minutes old
            ist_now() - timedelta(minutes=7),  # 7 minutes old
            ist_now() - timedelta(minutes=6),  # 6 minutes old
        ]

        execution_ids = []
        for stale_time in stale_times:
            execution = IndividualServiceTaskExecution(
                user_id=sample_user.id,
                task_name="analysis",
                executed_at=stale_time,
                status="running",
                duration_seconds=0.0,
                execution_type="run_once",
            )
            db_session.add(execution)
        db_session.commit()
        # Get IDs after commit (SQLite assigns IDs on commit)
        for execution in (
            db_session.query(IndividualServiceTaskExecution)
            .filter(
                IndividualServiceTaskExecution.user_id == sample_user.id,
                IndividualServiceTaskExecution.task_name == "analysis",
                IndividualServiceTaskExecution.status == "running",
            )
            .all()
        ):
            execution_ids.append(execution.id)

        # Clean up stale executions
        cleaned = manager._cleanup_stale_execution(sample_user.id, "analysis", context="test")

        # Should have cleaned up all stale executions
        assert cleaned is True

        # Verify all executions were marked as failed
        # Refresh session to see updates from raw SQL
        db_session.expire_all()
        for exec_id in execution_ids:
            execution = db_session.get(IndividualServiceTaskExecution, exec_id)
            assert execution is not None, f"Execution {exec_id} should exist after cleanup"
            assert (
                execution.status == "failed"
            ), f"Execution {exec_id} should be marked as failed, got {execution.status}"

    def test_get_status_forces_failed_status_with_correct_age_calculation(
        self, db_session, sample_user
    ):
        """Test that get_status() correctly forces failed status with accurate age calculation"""
        manager = IndividualServiceManager(db_session)

        # Create a stale execution (6 minutes old)
        stale_time = ist_now() - timedelta(minutes=6)
        stale_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=stale_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(stale_execution)
        db_session.commit()

        # Get status - should detect stale execution and force failed status
        status = manager.get_status(sample_user.id)

        # Verify execution was marked as failed
        db_session.refresh(stale_execution)
        assert stale_execution.status == "failed"

    def test_get_status_does_not_force_failed_for_recent_execution(self, db_session, sample_user):
        """Test that get_status() does not force failed status for recent executions"""
        manager = IndividualServiceManager(db_session)

        # Create a recent execution (1 minute old)
        recent_time = ist_now() - timedelta(minutes=1)
        recent_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=recent_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(recent_execution)
        db_session.commit()

        # Get status - should NOT force failed status
        status = manager.get_status(sample_user.id)

        # Verify execution is still running
        db_session.refresh(recent_execution)
        assert recent_execution.status == "running"
