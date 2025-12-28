"""
Integration tests for thread-safe scheduler with real database operations

Tests actual database interactions across threads to ensure isolation and correctness.
"""

import threading
import time
from datetime import datetime, time as dt_time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from uuid import uuid4

from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.application.services.schedule_manager import ScheduleManager
from src.infrastructure.db.models import (
    ServiceSchedule,
    ServiceStatus,
    UserSettings,
    TradeMode,
    Users,
)
from src.infrastructure.persistence.service_schedule_repository import (
    ServiceScheduleRepository,
)
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository

# Skip these integration tests when using in-memory SQLite with StaticPool,
# as SQLite+StaticPool shares a single connection across threads and does not
# provide reliable transaction isolation or cross-thread behavior for these cases.
from src.infrastructure.db.session import engine as _engine  # noqa: E402

pytestmark = pytest.mark.skipif(
    _engine.dialect.name == "sqlite" and isinstance(_engine.pool, StaticPool),
    reason="Integration concurrency tests require a non-StaticPool database",
)


@pytest.mark.integration
class TestSchedulerThreadSafetyIntegration:
    """Integration tests for thread-safe scheduler with real database"""

    @pytest.fixture
    def test_user(self, db_session: Session):
        """Create a test user"""
        from src.infrastructure.db.session import SessionLocal

        project_db = SessionLocal()
        try:
            user = Users(
                email=f"test_scheduler_{uuid4().hex}@example.com",
                name="Test User",
                password_hash="dummy_hash",
            )
            project_db.add(user)
            project_db.commit()
            project_db.refresh(user)
            user_id = user.id

            # Create settings
            settings = UserSettings(
                user_id=user_id,
                trade_mode=TradeMode.PAPER,
            )
            project_db.add(settings)
            project_db.commit()
        finally:
            project_db.close()

        yield user_id

        # Cleanup
        from src.infrastructure.db.session import SessionLocal

        project_db = SessionLocal()
        try:
            project_db.query(ServiceStatus).filter(ServiceStatus.user_id == user_id).delete()
            project_db.query(UserSettings).filter(UserSettings.user_id == user_id).delete()
            project_db.query(Users).filter(Users.id == user_id).delete()
            project_db.commit()
        finally:
            project_db.close()

    @pytest.fixture
    def test_schedules(self, db_session: Session, test_user: int):
        """Create test schedules"""
        from src.infrastructure.db.session import SessionLocal
        project_db = SessionLocal()
        schedules = [
            ServiceSchedule(
                task_name="test_task_1",
                schedule_time=dt_time(9, 15),
                enabled=True,
                is_continuous=False,
                is_hourly=False,
            ),
            ServiceSchedule(
                task_name="test_task_2",
                schedule_time=dt_time(14, 30),
                enabled=True,
                is_continuous=False,
                is_hourly=False,
            ),
        ]
        try:
            for schedule in schedules:
                project_db.add(schedule)
            project_db.commit()
        finally:
            project_db.close()

        yield schedules

        # Cleanup
        from src.infrastructure.db.session import SessionLocal
        project_db = SessionLocal()
        try:
            for schedule in schedules:
                project_db.delete(schedule)
            project_db.commit()
        finally:
            project_db.close()

    def test_concurrent_schedule_queries_real_db(self, db_session: Session, test_user: int, test_schedules):
        """Test that concurrent schedule queries from multiple threads work correctly"""
        results = {"thread1": [], "thread2": [], "thread3": []}
        errors = []

        def query_schedules(thread_name: str):
            """Query schedules from a thread-local session"""
            try:
                from src.infrastructure.db.session import SessionLocal

                thread_db = SessionLocal()
                try:
                    repo = ServiceScheduleRepository(thread_db)
                    schedule = repo.get_by_task_name("test_task_1")
                    results[thread_name].append(schedule)

                    # Query again to test session reuse
                    schedule2 = repo.get_by_task_name("test_task_2")
                    results[thread_name].append(schedule2)
                finally:
                    thread_db.close()
            except Exception as e:
                errors.append((thread_name, str(e)))

        # Start multiple threads
        threads = []
        for i in range(3):
            thread_name = f"thread{i + 1}"
            thread = threading.Thread(target=query_schedules, args=(thread_name,), daemon=True)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5)

        # Verify no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Verify all threads got results
        for thread_name, thread_results in results.items():
            assert len(thread_results) == 2, f"{thread_name} should have 2 results"
            assert thread_results[0] is not None, f"{thread_name} should find test_task_1"
            assert thread_results[1] is not None, f"{thread_name} should find test_task_2"
            assert thread_results[0].task_name == "test_task_1"
            assert thread_results[1].task_name == "test_task_2"

    def test_concurrent_heartbeat_updates_real_db(self, db_session: Session, test_user: int):
        """Test that concurrent heartbeat updates from multiple threads work correctly"""
        errors = []
        update_counts = {"thread1": 0, "thread2": 0, "thread3": 0}

        # Create initial service status
        from src.infrastructure.db.session import SessionLocal
        project_db = SessionLocal()
        try:
            status = ServiceStatus(user_id=test_user, service_running=True)
            project_db.add(status)
            project_db.commit()
        finally:
            project_db.close()

        def update_heartbeat(thread_name: str, updates: int = 3):
            """Update heartbeat from a thread-local session"""
            try:
                from src.infrastructure.db.session import SessionLocal

                thread_db = SessionLocal()
                try:
                    repo = ServiceStatusRepository(thread_db)
                    for _ in range(updates):
                        repo.update_heartbeat(test_user)
                        thread_db.commit()
                        update_counts[thread_name] += 1
                        time.sleep(0.01)  # Small delay between updates
                finally:
                    thread_db.close()
            except Exception as e:
                errors.append((thread_name, str(e)))

        # Start multiple threads updating heartbeat
        threads = []
        for i in range(3):
            thread_name = f"thread{i + 1}"
            thread = threading.Thread(target=update_heartbeat, args=(thread_name, 5), daemon=True)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=10)

        # Verify no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Verify all threads completed their updates
        for thread_name, count in update_counts.items():
            assert count == 5, f"{thread_name} should have completed 5 updates, got {count}"

        # Verify final heartbeat was updated
        from src.infrastructure.db.session import SessionLocal
        with SessionLocal() as project_db:
            project_db.expire_all()
            final_status = project_db.query(ServiceStatus).filter_by(user_id=test_user).first()
        assert final_status is not None
        assert final_status.last_heartbeat is not None

        # Cleanup
        from src.infrastructure.db.session import SessionLocal
        with SessionLocal() as project_db:
            status_row = project_db.query(ServiceStatus).filter_by(user_id=test_user).first()
            if status_row:
                project_db.delete(status_row)
                project_db.commit()

    def test_transaction_isolation_between_threads(self, db_session: Session, test_user: int):
        """Test that uncommitted changes in one thread don't affect another thread"""
        from src.infrastructure.db.session import SessionLocal

        # Thread 1: Create but don't commit
        thread1_schedule = None
        thread1_committed = False

        def thread1_create_uncommitted():
            nonlocal thread1_schedule, thread1_committed
            thread_db = SessionLocal()
            try:
                schedule = ServiceSchedule(
                    task_name="uncommitted_task",
                    schedule_time=dt_time(10, 0),
                    enabled=True,
                )
                thread_db.add(schedule)
                thread_db.flush()  # Flush but don't commit
                thread1_schedule = schedule
                time.sleep(0.2)  # Hold transaction open
                thread_db.rollback()  # Rollback instead of commit
                thread1_committed = False
            finally:
                thread_db.close()

        # Thread 2: Try to read the uncommitted data
        thread2_result = None

        def thread2_query():
            nonlocal thread2_result
            time.sleep(0.1)  # Let thread1 flush first
            thread_db = SessionLocal()
            try:
                repo = ServiceScheduleRepository(thread_db)
                result = repo.get_by_task_name("uncommitted_task")
                thread2_result = result
            finally:
                thread_db.close()

        # Run threads
        t1 = threading.Thread(target=thread1_create_uncommitted, daemon=True)
        t2 = threading.Thread(target=thread2_query, daemon=True)

        t1.start()
        t2.start()

        t1.join(timeout=5)
        t2.join(timeout=5)

        # Thread 2 should NOT see uncommitted data from thread 1
        assert thread2_result is None, "Thread 2 should not see uncommitted data from thread 1"

    def test_schedule_manager_thread_local_with_real_db(
        self, db_session: Session, test_user: int, test_schedules
    ):
        """Test ScheduleManager uses thread-local sessions correctly with real database"""
        manager_sessions = []
        errors = []

        def use_schedule_manager(thread_id: int):
            """Use ScheduleManager from a thread"""
            try:
                from src.infrastructure.db.session import SessionLocal

                thread_db = SessionLocal()
                try:
                    manager = ScheduleManager(thread_db)
                    manager_sessions.append((thread_id, manager.db))

                    # Perform actual operations
                    schedule = manager.get_schedule("test_task_1")
                    assert schedule is not None

                    all_schedules = manager.get_all_schedules()
                    assert len(all_schedules) > 0
                finally:
                    thread_db.close()
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=use_schedule_manager, args=(i,), daemon=True)
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=5)

        # Verify no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Verify each thread used its own session
        assert len(manager_sessions) == 3
        session_ids = [id(session) for _, session in manager_sessions]
        # All sessions should be different objects
        assert len(set(session_ids)) == 3, "Each thread should use a different session"

    def test_concurrent_writes_to_different_records(self, db_session: Session, test_user: int):
        """Test that concurrent writes to different records work correctly"""
        errors = []
        created_schedules = []

        def create_schedule(task_name: str):
            """Create a schedule from a thread-local session"""
            try:
                from src.infrastructure.db.session import SessionLocal

                thread_db = SessionLocal()
                try:
                    schedule = ServiceSchedule(
                        task_name=task_name,
                        schedule_time=dt_time(12, 0),
                        enabled=True,
                    )
                    thread_db.add(schedule)
                    thread_db.commit()
                    thread_db.refresh(schedule)
                    created_schedules.append(schedule.id)
                finally:
                    thread_db.close()
            except Exception as e:
                errors.append((task_name, str(e)))

        # Create schedules from multiple threads
        threads = []
        task_names = [f"concurrent_task_{i}" for i in range(5)]
        for task_name in task_names:
            thread = threading.Thread(target=create_schedule, args=(task_name,), daemon=True)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5)

        # Verify no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Verify all schedules were created
        assert len(created_schedules) == 5

        # Cleanup
        from src.infrastructure.db.session import SessionLocal
        with SessionLocal() as project_db:
            project_db.query(ServiceSchedule).filter(
                ServiceSchedule.task_name.in_(task_names)
            ).delete(synchronize_session=False)
            project_db.commit()

    def test_session_cleanup_on_thread_exit(self, db_session: Session, test_user: int):
        """Test that sessions are properly cleaned up when threads exit"""
        from src.infrastructure.db.session import engine
        from src.infrastructure.db.connection_monitor import get_active_connections_count

        initial_connections = get_active_connections_count(engine)

        def use_session_and_exit():
            """Create session, use it, and exit"""
            from src.infrastructure.db.session import SessionLocal

            thread_db = SessionLocal()
            try:
                # Do some work
                from src.infrastructure.persistence.service_schedule_repository import (
                    ServiceScheduleRepository,
                )

                repo = ServiceScheduleRepository(thread_db)
                repo.get_all()
            finally:
                thread_db.close()

        # Start and complete threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=use_session_and_exit, daemon=True)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)

        # Give connections time to be returned to pool
        time.sleep(0.5)

        # Connection count should return to initial or close to it
        final_connections = get_active_connections_count(engine)
        # Allow some variance but connections shouldn't leak
        assert (
            final_connections <= initial_connections + 2
        ), f"Connections may have leaked: initial={initial_connections}, final={final_connections}"
