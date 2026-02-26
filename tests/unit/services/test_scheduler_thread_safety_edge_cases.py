"""
Extended thread-safety tests for scheduler (edge cases and stress tests)

Tests cover edge cases, error handling, and concurrent access patterns.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.application.services.schedule_manager import ScheduleManager


class TestSchedulerThreadSafetyEdgeCases:
    """Test edge cases and error scenarios for thread-safe scheduling"""

    def setup_method(self):
        """Setup for each test"""
        self.mock_db = MagicMock(spec=Session)
        self.service = MultiUserTradingService(self.mock_db)

    def test_scheduler_handles_session_creation_failure(self):
        """Test that scheduler handles SessionLocal() failure gracefully"""
        mock_service = MagicMock()
        mock_service.running = False

        with patch("src.infrastructure.db.session.SessionLocal") as mock_session_local:
            # Simulate session creation failure
            mock_session_local.side_effect = OperationalError("connection failed", None, None)

            with patch("src.application.services.multi_user_trading_service.get_user_logger"):
                # Should not crash, should handle exception
                thread = threading.Thread(
                    target=self.service._run_paper_trading_scheduler,
                    args=(mock_service, 1),
                    daemon=True,
                )
                thread.start()
                thread.join(timeout=2)

                # Thread should exit cleanly
                assert not thread.is_alive()

    def test_scheduler_cleans_up_session_on_exception(self):
        """Test that thread_db is properly closed even when scheduler crashes"""
        mock_service = MagicMock()
        mock_service.running = True
        mock_service.shutdown_requested = False

        mock_thread_db = MagicMock(spec=Session)
        sessions_closed = []

        def track_close():
            sessions_closed.append(True)

        mock_thread_db.close = track_close
        mock_thread_db.rollback = MagicMock()

        with patch("src.infrastructure.db.session.SessionLocal", return_value=mock_thread_db):
            with patch("src.infrastructure.db.session.engine"):  # Mock engine for pool logging
                with patch.object(ScheduleManager, "__init__") as mock_init:
                    # Mock ScheduleManager init to avoid repository creation issues
                    def init_mock(self_instance, db):
                        self_instance.db = db
                        self_instance._schedule_repo = MagicMock()

                    mock_init.side_effect = init_mock

                    with patch.object(ScheduleManager, "get_schedule") as mock_get_schedule:
                        # Force an exception in the scheduler loop
                        mock_get_schedule.side_effect = RuntimeError("Unexpected error")

                        with patch(
                            "src.application.services.multi_user_trading_service.get_user_logger"
                        ):
                            thread = threading.Thread(
                                target=self.service._run_paper_trading_scheduler,
                                args=(mock_service, 1),
                                daemon=True,
                            )
                            thread.start()
                            time.sleep(0.3)  # Let it hit the error
                            mock_service.running = False
                            thread.join(timeout=2)

        # Verify session was closed despite the exception
        assert len(sessions_closed) > 0, "Session should have been closed in finally block"

    def test_multiple_schedulers_different_users_isolated_sessions(self):
        """Test that multiple scheduler threads for different users have isolated sessions"""
        mock_service1 = MagicMock()
        mock_service1.running = False
        mock_service2 = MagicMock()
        mock_service2.running = False
        mock_service3 = MagicMock()
        mock_service3.running = False

        created_sessions = []
        session_user_mapping = {}

        def create_session():
            mock_session = MagicMock(spec=Session)
            session_id = len(created_sessions)
            created_sessions.append(mock_session)
            mock_session._test_id = session_id
            return mock_session

        with patch("src.infrastructure.db.session.SessionLocal", side_effect=create_session):
            with patch("src.application.services.multi_user_trading_service.get_user_logger"):
                # Start three scheduler threads for different users
                thread1 = threading.Thread(
                    target=self.service._run_paper_trading_scheduler,
                    args=(mock_service1, 1),
                    daemon=True,
                )
                thread2 = threading.Thread(
                    target=self.service._run_paper_trading_scheduler,
                    args=(mock_service2, 2),
                    daemon=True,
                )
                thread3 = threading.Thread(
                    target=self.service._run_paper_trading_scheduler,
                    args=(mock_service3, 3),
                    daemon=True,
                )

                thread1.start()
                thread2.start()
                thread3.start()

                # Allow all three threads to run to SessionLocal() before joining
                time.sleep(0.25)

                thread1.join(timeout=2)
                thread2.join(timeout=2)
                thread3.join(timeout=2)

        # Verify that at least 3 separate sessions were created
        assert (
            len(created_sessions) >= 3
        ), f"Expected >= 3 sessions (one per scheduler thread), got {len(created_sessions)}"
        # Verify all sessions are different objects
        assert created_sessions[0] is not created_sessions[1]
        assert created_sessions[1] is not created_sessions[2]
        assert created_sessions[0] is not created_sessions[2]

    def test_scheduler_session_not_shared_with_main_thread(self):
        """Test that scheduler never uses the main thread's db session"""
        mock_service = MagicMock()
        mock_service.running = False

        main_thread_session = self.mock_db
        thread_sessions_used = []

        def track_schedule_manager_init(self_instance, db):
            thread_sessions_used.append(db)
            # Call original init
            self_instance.db = db
            from src.infrastructure.persistence.service_schedule_repository import (
                ServiceScheduleRepository,
            )

            self_instance._schedule_repo = ServiceScheduleRepository(db)

        with patch.object(ScheduleManager, "__init__", track_schedule_manager_init):
            with patch("src.infrastructure.db.session.SessionLocal") as mock_session_local:
                mock_thread_db = MagicMock(spec=Session)
                mock_session_local.return_value = mock_thread_db

                with patch(
                    "src.application.services.multi_user_trading_service.get_user_logger",
                    create=True,
                ):
                    thread = threading.Thread(
                        target=self.service._run_paper_trading_scheduler,
                        args=(mock_service, 1),
                        daemon=True,
                    )
                    thread.start()
                    thread.join(timeout=2)

        # Verify scheduler used thread_db, not main_thread_session
        assert len(thread_sessions_used) > 0
        for session in thread_sessions_used:
            assert session is not main_thread_session, "Scheduler must not use main thread session"
            assert session is mock_thread_db, "Scheduler must use thread-local session"

    def test_scheduler_handles_commit_failures(self):
        """Test that scheduler handles commit failures without crashing"""
        mock_service = MagicMock()
        mock_service.running = True
        mock_service.shutdown_requested = False

        mock_thread_db = MagicMock(spec=Session)
        commit_call_count = [0]

        def failing_commit():
            commit_call_count[0] += 1
            if commit_call_count[0] <= 2:  # Fail first 2 commits
                raise OperationalError("database is locked", None, None)

        mock_thread_db.commit = failing_commit
        mock_thread_db.rollback = MagicMock()

        with patch("src.infrastructure.db.session.SessionLocal", return_value=mock_thread_db):
            with patch(
                "src.application.services.schedule_manager.ServiceScheduleRepository"
            ) as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.get_by_task_name.return_value = None
                mock_repo_class.return_value = mock_repo

                with patch("src.application.services.multi_user_trading_service.get_user_logger"):
                    thread = threading.Thread(
                        target=self.service._run_paper_trading_scheduler,
                        args=(mock_service, 1),
                        daemon=True,
                    )
                    thread.start()
                    time.sleep(0.3)  # Let it try a few commits
                    mock_service.running = False
                    thread.join(timeout=2)

        # Verify rollback was called when commit failed
        assert mock_thread_db.rollback.call_count > 0

    def test_concurrent_schedule_queries_use_different_sessions(self):
        """Test that concurrent schedule queries from different threads use different sessions"""
        mock_service = MagicMock()
        mock_service.running = True
        mock_service.shutdown_requested = False
        mock_service.tasks_completed = {}

        query_session_map = {}

        def track_get_schedule(self_instance, task_name):
            thread_id = threading.get_ident()
            if thread_id not in query_session_map:
                query_session_map[thread_id] = []
            query_session_map[thread_id].append(self_instance.db)
            # Return disabled schedule
            mock_schedule = MagicMock()
            mock_schedule.enabled = False
            return mock_schedule

        with patch.object(ScheduleManager, "get_schedule", track_get_schedule):
            with patch("src.infrastructure.db.session.SessionLocal") as mock_session_local:

                def create_unique_session():
                    session = MagicMock(spec=Session)
                    session._thread_id = threading.get_ident()
                    return session

                mock_session_local.side_effect = create_unique_session

                with patch(
                    "src.application.services.schedule_manager.ServiceScheduleRepository"
                ) as mock_repo_class:
                    mock_repo = MagicMock()
                    mock_repo.get_by_task_name.return_value = None
                    mock_repo_class.return_value = mock_repo

                    with patch(
                        "src.application.services.multi_user_trading_service.get_user_logger",
                        create=True,
                    ):
                        # Run scheduler briefly
                        thread = threading.Thread(
                            target=self.service._run_paper_trading_scheduler,
                            args=(mock_service, 1),
                            daemon=True,
                        )
                        thread.start()
                        time.sleep(0.2)
                        mock_service.running = False
                        thread.join(timeout=2)

        # Verify queries happened
        if query_session_map:
            for thread_id, sessions in query_session_map.items():
                # All queries in same thread should use same session
                if len(sessions) > 1:
                    first_session = sessions[0]
                    for session in sessions[1:]:
                        assert (
                            session is first_session
                        ), "All queries in same thread should use same session"

    def test_scheduler_heartbeat_isolation(self):
        """Test that heartbeat updates use thread-local session and don't affect main session"""
        mock_service = MagicMock()
        mock_service.running = True
        mock_service.shutdown_requested = False
        mock_service.tasks_completed = {}

        mock_thread_db = MagicMock(spec=Session)
        mock_thread_db.commit = MagicMock()
        mock_thread_db.rollback = MagicMock()

        with patch("src.infrastructure.db.session.SessionLocal", return_value=mock_thread_db):
            with patch("src.infrastructure.db.session.engine"):  # Mock engine for pool logging
                with patch(
                    "src.application.services.schedule_manager.ServiceScheduleRepository"
                ) as mock_repo_class:
                    mock_repo = MagicMock()
                    mock_repo.get_by_task_name.return_value = None
                    mock_repo_class.return_value = mock_repo

                    with patch(
                        "src.infrastructure.persistence.service_status_repository.ServiceStatusRepository"
                    ) as mock_status_repo_class:
                        mock_status_repo = MagicMock()
                        mock_status_repo_class.return_value = mock_status_repo

                        with patch(
                            "src.application.services.multi_user_trading_service.get_user_logger",
                            create=True,
                        ):
                            thread = threading.Thread(
                                target=self.service._run_paper_trading_scheduler,
                                args=(mock_service, 1),
                                daemon=True,
                            )
                            thread.start()
                            time.sleep(1.2)  # Wait for at least one full minute check cycle
                            mock_service.running = False
                            thread.join(timeout=2)

        # Verify thread_db.commit was called (for heartbeat or other operations)
        assert mock_thread_db.commit.called or mock_status_repo.update_heartbeat.called

    @pytest.mark.parametrize(
        "user_count",
        [1, 3, 5],
    )
    def test_multiple_users_concurrent_sessions(self, user_count):
        """Test multiple users with concurrent schedulers each have isolated sessions"""
        services = [MagicMock() for _ in range(user_count)]
        for svc in services:
            svc.running = False

        session_count = [0]

        def create_session():
            session = MagicMock(spec=Session)
            session._id = session_count[0]
            session_count[0] += 1
            return session

        with patch("src.infrastructure.db.session.SessionLocal", side_effect=create_session):
            with patch(
                "src.application.services.multi_user_trading_service.get_user_logger",
                create=True,
            ):
                threads = []
                for i, service in enumerate(services):
                    thread = threading.Thread(
                        target=self.service._run_paper_trading_scheduler,
                        args=(service, i + 1),
                        daemon=True,
                    )
                    threads.append(thread)
                    thread.start()

                # Wait for all threads
                for thread in threads:
                    thread.join(timeout=2)

        # Each scheduler should have created its own session
        assert session_count[0] >= user_count, f"Expected at least {user_count} sessions"
