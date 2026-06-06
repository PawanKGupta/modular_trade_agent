"""
Unit tests for IndividualServiceManager - Timeout and Stale Execution Cleanup

Tests for:
- Orphan running rows (dead thread) cleaned after 2 minutes
- Active run-once thread never marked failed while still alive (incl. long analysis)
- get_status surfaces running while thread is alive
"""

from datetime import timedelta
from threading import Event, Thread
from unittest.mock import patch

import pytest

from src.application.services.individual_service_manager import (
    IndividualServiceManager,
    _RUN_ONCE_THREADS,
)
from src.infrastructure.db.models import (
    IndividualServiceTaskExecution,
    ServiceTaskExecution,
    UserRole,
    Users,
)
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    user = Users(
        email="test@example.com",
        password_hash="hashed_password",
        role=UserRole.ADMIN,
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestIndividualServiceManagerTimeout:
    """Test suite for timeout and stale execution cleanup"""

    def test_cleanup_stale_execution_orphan_after_2_minutes(self, db_session, sample_user):
        """Dead-thread 'running' rows are cleaned after the 2-minute orphan window."""
        manager = IndividualServiceManager(db_session)

        stale_time = ist_now() - timedelta(minutes=3)
        stale_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="buy_orders",
            executed_at=stale_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(stale_execution)
        db_session.commit()

        cleaned = manager._cleanup_stale_execution(sample_user.id, "buy_orders", context="test")

        assert cleaned is True
        db_session.refresh(stale_execution)
        assert stale_execution.status == "failed"
        assert stale_execution.details is not None
        assert "stale_execution" in str(stale_execution.details)

    def test_cleanup_stale_execution_skips_while_thread_alive(self, db_session, sample_user):
        """Long-running analysis is not failed while the run-once thread is still alive."""
        manager = IndividualServiceManager(db_session)

        stale_time = ist_now() - timedelta(minutes=10)
        running_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=stale_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(running_execution)
        db_session.commit()

        hold = Event()

        def _block_until_released() -> None:
            hold.wait(timeout=30)

        alive_thread = Thread(target=_block_until_released, daemon=True)
        alive_thread.start()
        _RUN_ONCE_THREADS[(sample_user.id, "analysis")] = alive_thread

        try:
            assert alive_thread.is_alive()
            cleaned = manager._cleanup_stale_execution(
                sample_user.id, "analysis", context="test"
            )
            assert cleaned is False
            db_session.refresh(running_execution)
            assert running_execution.status == "running"
        finally:
            hold.set()
            alive_thread.join(timeout=5)
            _RUN_ONCE_THREADS.pop((sample_user.id, "analysis"), None)

    def test_cleanup_stale_execution_does_not_clean_recent_execution(self, db_session, sample_user):
        """Recent running rows are not cleaned."""
        manager = IndividualServiceManager(db_session)

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

        cleaned = manager._cleanup_stale_execution(sample_user.id, "analysis", context="test")

        assert cleaned is False
        db_session.refresh(recent_execution)
        assert recent_execution.status == "running"
        assert recent_execution.id == execution_id

    def test_cleanup_stale_execution_2_minute_boundary(self, db_session, sample_user):
        """Orphan boundary: just over 2 minutes without a live thread is cleaned."""
        manager = IndividualServiceManager(db_session)

        boundary_time = ist_now() - timedelta(minutes=2, seconds=1)
        boundary_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="buy_orders",
            executed_at=boundary_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(boundary_execution)
        db_session.commit()

        cleaned = manager._cleanup_stale_execution(sample_user.id, "buy_orders", context="test")

        assert cleaned is True
        db_session.refresh(boundary_execution)
        assert boundary_execution.status == "failed"

    def test_cleanup_stale_execution_handles_timezone_correctly(self, db_session, sample_user):
        """Fresh executions are not marked stale."""
        manager = IndividualServiceManager(db_session)

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

        cleaned = manager._cleanup_stale_execution(sample_user.id, "analysis", context="test")

        assert cleaned is False
        db_session.refresh(fresh_execution)
        assert fresh_execution.status == "running"
        assert fresh_execution.id == execution_id

    def test_cleanup_stale_execution_works_for_all_task_types(self, db_session, sample_user):
        """Orphan cleanup applies to all task types when the thread is not alive."""
        manager = IndividualServiceManager(db_session)
        task_types = ["analysis", "buy_orders", "sell_monitor", "eod_cleanup", "premarket_retry"]

        for task_name in task_types:
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

            cleaned = manager._cleanup_stale_execution(sample_user.id, task_name, context="test")

            assert cleaned is True, f"Should clean up stale {task_name} execution"
            db_session.refresh(stale_execution)
            assert stale_execution.status == "failed", f"{task_name} should be marked as failed"

            db_session.delete(stale_execution)
            db_session.commit()

    def test_get_status_cleans_orphan_running_execution(self, db_session, sample_user):
        """get_status() cleans orphan running rows when the thread is not alive."""
        manager = IndividualServiceManager(db_session)

        stale_time = ist_now() - timedelta(minutes=3)
        stale_execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="buy_orders",
            executed_at=stale_time,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(stale_execution)
        db_session.commit()

        manager.get_status(sample_user.id)

        db_session.refresh(stale_execution)
        assert stale_execution.status == "failed"

    def test_get_status_shows_running_while_thread_alive(self, db_session, sample_user):
        """API reports running while the run-once worker thread is still alive."""
        manager = IndividualServiceManager(db_session)

        started = ist_now() - timedelta(minutes=6)
        execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=started,
            status="failed",
            duration_seconds=0.0,
            execution_type="run_once",
            details={"error": "stale_execution", "stale_execution": 1},
        )
        db_session.add(execution)
        db_session.commit()

        hold = Event()

        def _block_until_released() -> None:
            hold.wait(timeout=30)

        alive_thread = Thread(target=_block_until_released, daemon=True)
        alive_thread.start()
        _RUN_ONCE_THREADS[(sample_user.id, "analysis")] = alive_thread

        try:
            assert alive_thread.is_alive()
            status = manager.get_status(sample_user.id)
            assert status["analysis"]["last_execution_status"] == "running"
        finally:
            hold.set()
            alive_thread.join(timeout=5)
            _RUN_ONCE_THREADS.pop((sample_user.id, "analysis"), None)

    def test_get_status_current_run_started_at_uses_in_flight_execution(
        self, db_session, sample_user
    ):
        """current_run_started_at reflects the active run, not service.last_execution_at."""
        from src.infrastructure.persistence.individual_service_status_repository import (  # noqa: PLC0415
            IndividualServiceStatusRepository,
        )

        manager = IndividualServiceManager(db_session)
        status_repo = IndividualServiceStatusRepository(db_session)

        previous_run = ist_now() - timedelta(minutes=4)
        status_repo.update_last_execution(sample_user.id, "analysis", previous_run)

        current_run_start = ist_now() - timedelta(seconds=30)
        execution = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=current_run_start,
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(execution)
        db_session.commit()

        hold = Event()

        def _block() -> None:
            hold.wait(timeout=30)

        alive_thread = Thread(target=_block, daemon=True)
        alive_thread.start()
        _RUN_ONCE_THREADS[(sample_user.id, "analysis")] = alive_thread

        try:
            status = manager.get_status(sample_user.id)["analysis"]
            assert status["last_execution_status"] == "running"
            assert status["current_run_started_at"] is not None
            assert status["last_execution_at"] is not None
            current_started = status["current_run_started_at"].replace("Z", "+00:00")
            last_completed = status["last_execution_at"].replace("Z", "+00:00")
            from datetime import datetime  # noqa: PLC0415

            assert datetime.fromisoformat(current_started) > datetime.fromisoformat(
                last_completed
            )
        finally:
            hold.set()
            alive_thread.join(timeout=5)
            _RUN_ONCE_THREADS.pop((sample_user.id, "analysis"), None)

    def test_run_once_cleans_stale_executions_before_checking(self, db_session, sample_user):
        """run_once() cleans orphan running rows before starting a new execution."""
        manager = IndividualServiceManager(db_session)

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

        with patch.object(manager, "_execute_task_once", return_value=None):
            success, message, details = manager.run_once(sample_user.id, "analysis")

            assert success is True
            db_session.refresh(stale_execution)
            assert stale_execution.status == "failed"

    def test_age_calculation_accuracy_with_timezone(self, db_session, sample_user):
        """Age calculations are accurate with timezone-aware datetimes."""
        manager = IndividualServiceManager(db_session)

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

        cleaned = manager._cleanup_stale_execution(sample_user.id, "analysis", context="test")

        assert cleaned is False
        db_session.refresh(execution)
        assert execution.status == "running"

    def test_multiple_stale_executions_all_cleaned_up(self, db_session, sample_user):
        """All orphan running rows are cleaned up, not just the latest."""
        manager = IndividualServiceManager(db_session)

        stale_times = [
            ist_now() - timedelta(minutes=10),
            ist_now() - timedelta(minutes=7),
            ist_now() - timedelta(minutes=6),
        ]

        execution_ids = []
        for stale_time in stale_times:
            execution = IndividualServiceTaskExecution(
                user_id=sample_user.id,
                task_name="buy_orders",
                executed_at=stale_time,
                status="running",
                duration_seconds=0.0,
                execution_type="run_once",
            )
            db_session.add(execution)
        db_session.commit()

        for execution in (
            db_session.query(IndividualServiceTaskExecution)
            .filter(
                IndividualServiceTaskExecution.user_id == sample_user.id,
                IndividualServiceTaskExecution.task_name == "buy_orders",
                IndividualServiceTaskExecution.status == "running",
            )
            .all()
        ):
            execution_ids.append(execution.id)

        cleaned = manager._cleanup_stale_execution(sample_user.id, "buy_orders", context="test")

        assert cleaned is True
        db_session.expire_all()
        for exec_id in execution_ids:
            execution = db_session.get(IndividualServiceTaskExecution, exec_id)
            assert execution is not None
            assert execution.status == "failed"

    def test_get_status_orphan_running_marked_failed(self, db_session, sample_user):
        """get_status() marks orphan running rows failed when the thread is dead."""
        manager = IndividualServiceManager(db_session)

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

        manager.get_status(sample_user.id)

        db_session.refresh(stale_execution)
        assert stale_execution.status == "failed"

    def test_get_status_does_not_force_failed_for_recent_execution(self, db_session, sample_user):
        """get_status() keeps recent running rows as running."""
        manager = IndividualServiceManager(db_session)

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

        manager.get_status(sample_user.id)

        db_session.refresh(recent_execution)
        assert recent_execution.status == "running"
        assert manager.get_status(sample_user.id)["analysis"]["last_execution_status"] == "running"

    def test_run_once_thread_visible_across_manager_instances(self, db_session, sample_user):
        """Status polls use a new manager per request; thread registry must be process-wide."""
        manager_a = IndividualServiceManager(db_session)
        manager_b = IndividualServiceManager(db_session)
        hold = Event()

        def _block() -> None:
            hold.wait(timeout=30)

        alive_thread = Thread(target=_block, daemon=True)
        alive_thread.start()
        _RUN_ONCE_THREADS[(sample_user.id, "buy_orders")] = alive_thread

        try:
            assert manager_a._run_once_thread_is_alive(sample_user.id, "buy_orders")
            assert manager_b._run_once_thread_is_alive(sample_user.id, "buy_orders")
        finally:
            hold.set()
            alive_thread.join(timeout=5)
            _RUN_ONCE_THREADS.pop((sample_user.id, "buy_orders"), None)


class TestIndividualServiceCrossTaskIsolation:
    """Stale/run-once fixes must not bleed across task types or unified service display."""

    def test_analysis_thread_alive_does_not_block_buy_orders_orphan_cleanup(
        self, db_session, sample_user
    ):
        """Per-task thread map: long analysis must not protect other tasks' orphan rows."""
        manager = IndividualServiceManager(db_session)
        hold = Event()

        def _block() -> None:
            hold.wait(timeout=30)

        alive_thread = Thread(target=_block, daemon=True)
        alive_thread.start()
        _RUN_ONCE_THREADS[(sample_user.id, "analysis")] = alive_thread

        old_analysis = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=ist_now() - timedelta(minutes=15),
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        orphan_buy = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="buy_orders",
            executed_at=ist_now() - timedelta(minutes=4),
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add_all([old_analysis, orphan_buy])
        db_session.commit()

        try:
            assert manager._cleanup_stale_execution(sample_user.id, "analysis", "test") is False
            assert manager._cleanup_stale_execution(sample_user.id, "buy_orders", "test") is True
            db_session.refresh(old_analysis)
            db_session.refresh(orphan_buy)
            assert old_analysis.status == "running"
            assert orphan_buy.status == "failed"
        finally:
            hold.set()
            alive_thread.join(timeout=5)
            _RUN_ONCE_THREADS.pop((sample_user.id, "analysis"), None)

    def test_get_status_unified_buy_orders_unchanged_while_analysis_run_once_active(
        self, db_session, sample_user
    ):
        """Unified last result for other tasks stays visible during analysis run-once."""
        manager = IndividualServiceManager(db_session)
        hold = Event()

        def _block() -> None:
            hold.wait(timeout=30)

        alive_thread = Thread(target=_block, daemon=True)
        alive_thread.start()
        _RUN_ONCE_THREADS[(sample_user.id, "analysis")] = alive_thread

        unified_buy = ServiceTaskExecution(
            user_id=sample_user.id,
            task_name="buy_orders",
            executed_at=ist_now(),
            status="success",
            duration_seconds=12.5,
            details={"task": "buy_orders"},
        )
        analysis_run = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="analysis",
            executed_at=ist_now() - timedelta(minutes=5),
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add_all([unified_buy, analysis_run])
        db_session.commit()

        try:
            status = manager.get_status(sample_user.id)
            assert status["analysis"]["last_execution_status"] == "running"
            assert status["buy_orders"]["last_execution_status"] == "success"
            assert status["buy_orders"]["last_execution_duration"] == 12.5
            assert status["sell_monitor"]["is_running"] is False
        finally:
            hold.set()
            alive_thread.join(timeout=5)
            _RUN_ONCE_THREADS.pop((sample_user.id, "analysis"), None)

    def test_sell_monitor_run_once_thread_alive_not_marked_stale(self, db_session, sample_user):
        """Continuous-style tasks using run-once get the same alive-thread protection."""
        manager = IndividualServiceManager(db_session)
        hold = Event()

        def _block() -> None:
            hold.wait(timeout=30)

        alive_thread = Thread(target=_block, daemon=True)
        alive_thread.start()
        _RUN_ONCE_THREADS[(sample_user.id, "sell_monitor")] = alive_thread

        running = IndividualServiceTaskExecution(
            user_id=sample_user.id,
            task_name="sell_monitor",
            executed_at=ist_now() - timedelta(minutes=8),
            status="running",
            duration_seconds=0.0,
            execution_type="run_once",
        )
        db_session.add(running)
        db_session.commit()

        try:
            assert (
                manager._cleanup_stale_execution(sample_user.id, "sell_monitor", "test") is False
            )
            db_session.refresh(running)
            assert running.status == "running"
        finally:
            hold.set()
            alive_thread.join(timeout=5)
            _RUN_ONCE_THREADS.pop((sample_user.id, "sell_monitor"), None)
