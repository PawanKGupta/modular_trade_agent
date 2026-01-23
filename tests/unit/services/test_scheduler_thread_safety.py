"""
Unit tests for scheduler thread-safety (Section 6)

Tests verify that the scheduler uses thread-local sessions correctly
to avoid InvalidRequestError when accessing ScheduleManager.
"""

import threading
import time
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.application.services.schedule_manager import ScheduleManager


class TestSchedulerThreadSafety:
    """Test thread-safety of scheduler session management"""

    def setup_method(self):
        """Setup for each test"""
        # Create a mock database session
        self.mock_db = MagicMock(spec=Session)
        self.service = MultiUserTradingService(self.mock_db)

    def test_scheduler_creates_thread_local_schedule_manager(self):
        """Test that scheduler creates a thread-local ScheduleManager with thread_db"""
        mock_service = MagicMock()
        mock_service.running = False  # Exit immediately
        mock_service.shutdown_requested = False

        # Track which session was used to create ScheduleManager
        schedule_manager_sessions = []

        original_init = ScheduleManager.__init__

        def track_init(self_instance, db):
            schedule_manager_sessions.append(db)
            return original_init(self_instance, db)

        with patch.object(ScheduleManager, "__init__", track_init):
            with patch("src.infrastructure.db.session.SessionLocal") as mock_session_local:
                # Create a mock thread-local session
                mock_thread_db = MagicMock(spec=Session)
                mock_session_local.return_value = mock_thread_db

                # Mock get_user_logger to avoid actual logger initialization
                with patch(
                    "src.application.services.multi_user_trading_service.get_user_logger",
                    create=True,
                ):
                    # Start scheduler in a thread
                    thread = threading.Thread(
                        target=self.service._run_paper_trading_scheduler,
                        args=(mock_service, 1),
                        daemon=True,
                    )
                    thread.start()
                    thread.join(timeout=2)

        # Verify that ScheduleManager was created with thread_db (not main db)
        assert len(schedule_manager_sessions) > 0
        # The thread-local ScheduleManager should use thread_db
        assert schedule_manager_sessions[-1] is mock_thread_db
        assert schedule_manager_sessions[-1] is not self.mock_db

    def test_scheduler_uses_thread_local_manager_for_all_schedule_queries(self):
        """Test that all schedule.get_schedule() calls use thread-local manager"""
        mock_service = MagicMock()
        mock_service.running = True
        mock_service.shutdown_requested = False
        mock_service.tasks_completed = {}

        # Track which session is used for schedule queries
        schedule_query_sessions = []

        def track_get_schedule(self_instance, task_name):
            # Record the session used by this ScheduleManager instance
            schedule_query_sessions.append(self_instance.db)
            # Return a disabled schedule to prevent execution
            mock_schedule = MagicMock()
            mock_schedule.enabled = False
            return mock_schedule

        with patch.object(ScheduleManager, "get_schedule", track_get_schedule):
            with patch("src.infrastructure.db.session.SessionLocal") as mock_session_local:
                mock_thread_db = MagicMock(spec=Session)
                mock_session_local.return_value = mock_thread_db

                # Mock ServiceScheduleRepository to avoid actual DB queries
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
                        # Run scheduler for a short time
                        thread = threading.Thread(
                            target=self.service._run_paper_trading_scheduler,
                            args=(mock_service, 1),
                            daemon=True,
                        )
                        thread.start()
                        time.sleep(0.2)  # Let it run briefly
                        mock_service.running = False  # Stop it
                        thread.join(timeout=2)

        # Verify that all schedule queries used thread_db, not main db
        if schedule_query_sessions:
            for session_used in schedule_query_sessions:
                assert session_used is mock_thread_db, "Schedule query used wrong session"
                assert session_used is not self.mock_db, "Schedule query used main thread session"

    def test_scheduler_no_session_conflict(self):
        """Test that scheduler does not cause session conflicts"""
        mock_service = MagicMock()
        mock_service.running = False  # Exit immediately

        mock_thread_db = MagicMock(spec=Session)
        mock_thread_db.execute = MagicMock()
        mock_thread_db.commit = MagicMock()
        mock_thread_db.rollback = MagicMock()
        mock_thread_db.close = MagicMock()

        with patch("src.infrastructure.db.session.SessionLocal", return_value=mock_thread_db):
            # Mock schedule repository
            with patch(
                "src.application.services.schedule_manager.ServiceScheduleRepository"
            ) as mock_repo_class:
                mock_repo = MagicMock()
                mock_schedule = MagicMock()
                mock_schedule.enabled = False
                mock_repo.get_by_task_name.return_value = mock_schedule
                mock_repo_class.return_value = mock_repo

                with patch(
                    "src.application.services.multi_user_trading_service.get_user_logger",
                    create=True,
                ):
                    # This should not raise InvalidRequestError or session conflicts
                    thread = threading.Thread(
                        target=self.service._run_paper_trading_scheduler,
                        args=(mock_service, 1),
                        daemon=True,
                    )
                    thread.start()
                    thread.join(timeout=2)

                    # Verify thread completed without errors
                    assert not thread.is_alive()

    def test_scheduler_separate_sessions_per_thread(self):
        """Test that each scheduler thread uses a separate session"""
        mock_service1 = MagicMock()
        mock_service1.running = False
        mock_service2 = MagicMock()
        mock_service2.running = False

        created_sessions = []

        def create_session():
            mock_session = MagicMock(spec=Session)
            created_sessions.append(mock_session)
            return mock_session

        with patch("src.infrastructure.db.session.SessionLocal", side_effect=create_session):
            with patch(
                "src.application.services.multi_user_trading_service.get_user_logger",
                create=True,
            ):
                # Start two scheduler threads
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

                thread1.start()
                thread2.start()
                thread1.join(timeout=2)
                thread2.join(timeout=2)

        # Verify that separate sessions were created
        assert len(created_sessions) >= 2
        assert created_sessions[0] is not created_sessions[1]
