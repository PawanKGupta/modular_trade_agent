"""
Tests for TradingService thread-safety fix.

Tests that TradingService.run() creates its own thread-local database session
to avoid thread-safety issues when running in background threads.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from modules.kotak_neo_auto_trader.run_trading_service import TradingService


class TestTradingServiceThreadSafety:
    """Test thread-safety in TradingService.run()"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        session = Mock(spec=Session)
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.refresh = Mock()
        session.close = Mock()
        return session

    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing"""
        return 1

    @pytest.fixture
    def mock_strategy_config(self):
        """Mock strategy config"""
        config = MagicMock()
        return config

    def test_run_creates_thread_local_session(
        self, mock_db_session, sample_user_id, mock_strategy_config
    ):
        """Test that run() creates a new thread-local database session"""
        with patch("src.infrastructure.db.session.SessionLocal") as mock_session_local:
            with patch("src.infrastructure.logging.get_user_logger") as mock_get_logger:
                with patch.object(TradingService, "initialize") as mock_init:
                    with patch.object(TradingService, "run_scheduler") as mock_scheduler:
                        with patch.object(TradingService, "shutdown"):
                            # Setup mocks
                            mock_thread_db = Mock(spec=Session)
                            mock_thread_db.rollback = Mock()
                            mock_thread_db.close = Mock()
                            mock_session_local.return_value = mock_thread_db

                            mock_logger = MagicMock()
                            mock_get_logger.return_value = mock_logger

                            mock_init.return_value = True
                            mock_scheduler.side_effect = KeyboardInterrupt()  # Exit immediately

                            # Create service
                            service = TradingService(
                                user_id=sample_user_id,
                                db_session=mock_db_session,
                                broker_creds=None,  # Paper mode
                                strategy_config=mock_strategy_config,
                            )

                            # Run service (will exit immediately due to KeyboardInterrupt)
                            try:
                                service.run()
                            except KeyboardInterrupt:
                                pass

                            # Verify thread-local session was created
                            mock_session_local.assert_called_once()

                            # Verify logger was called twice:
                            # 1. In __init__ with original session
                            # 2. In run() with thread-local session
                            assert mock_get_logger.call_count == 2

                            # Verify the second call (in run()) uses thread-local session
                            second_call = mock_get_logger.call_args_list[1]
                            assert second_call.kwargs["user_id"] == sample_user_id
                            assert second_call.kwargs["db"] == mock_thread_db
                            assert second_call.kwargs["module"] == "TradingService"

                            # Verify self.db was updated to thread-local session
                            assert service.db == mock_thread_db

                            # Verify schedule manager was recreated with thread-local session
                            from src.application.services.schedule_manager import ScheduleManager

                            assert isinstance(service._schedule_manager, ScheduleManager)
                            # Note: Can't verify schedule manager's db without accessing private attributes

                            # Verify cleanup was called
                            mock_thread_db.rollback.assert_called_once()
                            mock_thread_db.close.assert_called_once()

    def test_run_updates_logger_with_thread_local_session(
        self, mock_db_session, sample_user_id, mock_strategy_config
    ):
        """Test that run() updates logger to use thread-local session"""
        with patch("src.infrastructure.db.session.SessionLocal") as mock_session_local:
            with patch("src.infrastructure.logging.get_user_logger") as mock_get_logger:
                with patch.object(TradingService, "initialize") as mock_init:
                    with patch.object(TradingService, "run_scheduler") as mock_scheduler:
                        with patch.object(TradingService, "shutdown"):
                            # Setup mocks
                            mock_thread_db = Mock(spec=Session)
                            mock_thread_db.rollback = Mock()
                            mock_thread_db.close = Mock()
                            mock_session_local.return_value = mock_thread_db

                            # Create different logger instances for each call
                            original_logger = MagicMock()
                            new_logger = MagicMock()
                            mock_get_logger.side_effect = [original_logger, new_logger]

                            mock_init.return_value = True
                            mock_scheduler.side_effect = KeyboardInterrupt()

                            # Create service (logger is created in __init__ with original session)
                            service = TradingService(
                                user_id=sample_user_id,
                                db_session=mock_db_session,
                                broker_creds=None,
                                strategy_config=mock_strategy_config,
                            )

                            # Verify original logger was set
                            assert service.logger == original_logger

                            # Run service
                            try:
                                service.run()
                            except KeyboardInterrupt:
                                pass

                            # Verify logger was recreated (different instance)
                            assert service.logger != original_logger
                            assert service.logger == new_logger

                            # Verify logger was called twice:
                            # 1. In __init__ with original session
                            # 2. In run() with thread-local session
                            assert mock_get_logger.call_count == 2

                            # Verify the second call (in run()) uses thread-local session
                            second_call = mock_get_logger.call_args_list[1]
                            assert second_call.kwargs["user_id"] == sample_user_id
                            assert second_call.kwargs["db"] == mock_thread_db
                            assert second_call.kwargs["module"] == "TradingService"

    def test_run_handles_session_cleanup_exceptions(
        self, mock_db_session, sample_user_id, mock_strategy_config
    ):
        """Test that run() handles session cleanup exceptions gracefully"""
        with patch("src.infrastructure.db.session.SessionLocal") as mock_session_local:
            with patch("src.infrastructure.logging.get_user_logger") as mock_get_logger:
                with patch.object(TradingService, "initialize") as mock_init:
                    with patch.object(TradingService, "run_scheduler") as mock_scheduler:
                        with patch.object(TradingService, "shutdown"):
                            # Setup mocks with exceptions
                            mock_thread_db = Mock(spec=Session)
                            mock_thread_db.rollback = Mock(side_effect=Exception("Rollback failed"))
                            mock_thread_db.close = Mock(side_effect=Exception("Close failed"))
                            mock_session_local.return_value = mock_thread_db

                            mock_logger = MagicMock()
                            mock_get_logger.return_value = mock_logger

                            mock_init.return_value = True
                            mock_scheduler.side_effect = KeyboardInterrupt()

                            # Create service
                            service = TradingService(
                                user_id=sample_user_id,
                                db_session=mock_db_session,
                                broker_creds=None,
                                strategy_config=mock_strategy_config,
                            )

                            # Run service - should not raise exception even if cleanup fails
                            try:
                                service.run()
                            except KeyboardInterrupt:
                                pass
                            except Exception as e:
                                pytest.fail(
                                    f"run() should handle cleanup exceptions gracefully, "
                                    f"but raised: {e}"
                                )

                            # Verify cleanup was attempted
                            mock_thread_db.rollback.assert_called_once()
                            mock_thread_db.close.assert_called_once()

    def test_run_initializes_with_thread_local_session(
        self, mock_db_session, sample_user_id, mock_strategy_config
    ):
        """Test that initialize() is called with thread-local session"""
        with patch("src.infrastructure.db.session.SessionLocal") as mock_session_local:
            with patch("src.infrastructure.logging.get_user_logger") as mock_get_logger:
                with patch.object(TradingService, "initialize") as mock_init:
                    with patch.object(TradingService, "run_scheduler") as mock_scheduler:
                        with patch.object(TradingService, "shutdown"):
                            # Setup mocks
                            mock_thread_db = Mock(spec=Session)
                            mock_thread_db.rollback = Mock()
                            mock_thread_db.close = Mock()
                            mock_session_local.return_value = mock_thread_db

                            mock_logger = MagicMock()
                            mock_get_logger.return_value = mock_logger

                            mock_init.return_value = True
                            mock_scheduler.side_effect = KeyboardInterrupt()

                            # Create service
                            service = TradingService(
                                user_id=sample_user_id,
                                db_session=mock_db_session,
                                broker_creds=None,
                                strategy_config=mock_strategy_config,
                            )

                            # Run service
                            try:
                                service.run()
                            except KeyboardInterrupt:
                                pass

                            # Verify initialize was called
                            mock_init.assert_called_once()

                            # Verify that at the time initialize() was called, self.db was thread-local
                            # (We can't directly verify this, but verify self.db was updated)
                            assert service.db == mock_thread_db

    def test_run_creates_schedule_manager_with_thread_local_session(
        self, mock_db_session, sample_user_id, mock_strategy_config
    ):
        """Test that schedule manager is recreated with thread-local session"""
        with patch("src.infrastructure.db.session.SessionLocal") as mock_session_local:
            with patch("src.infrastructure.logging.get_user_logger") as mock_get_logger:
                with patch(
                    "src.application.services.schedule_manager.ScheduleManager"
                ) as mock_schedule_manager:
                    with patch.object(TradingService, "initialize") as mock_init:
                        with patch.object(TradingService, "run_scheduler") as mock_scheduler:
                            with patch.object(TradingService, "shutdown"):
                                # Setup mocks
                                mock_thread_db = Mock(spec=Session)
                                mock_thread_db.rollback = Mock()
                                mock_thread_db.close = Mock()
                                mock_session_local.return_value = mock_thread_db

                                mock_logger = MagicMock()
                                mock_get_logger.return_value = mock_logger

                                # Create different schedule manager instances for each call
                                original_schedule_instance = MagicMock()
                                new_schedule_instance = MagicMock()
                                mock_schedule_manager.side_effect = [
                                    original_schedule_instance,
                                    new_schedule_instance,
                                ]

                                mock_init.return_value = True
                                mock_scheduler.side_effect = KeyboardInterrupt()

                                # Create service
                                service = TradingService(
                                    user_id=sample_user_id,
                                    db_session=mock_db_session,
                                    broker_creds=None,
                                    strategy_config=mock_strategy_config,
                                )

                                # Verify original schedule manager was set
                                assert service._schedule_manager == original_schedule_instance

                                # Run service
                                try:
                                    service.run()
                                except KeyboardInterrupt:
                                    pass

                                # Verify schedule manager was called twice:
                                # 1. In __init__ with original session
                                # 2. In run() with thread-local session
                                assert mock_schedule_manager.call_count == 2

                                # Verify the second call (in run()) uses thread-local session
                                second_call = mock_schedule_manager.call_args_list[1]
                                assert second_call.args[0] == mock_thread_db

                                # Verify schedule manager instance was updated
                                assert service._schedule_manager == new_schedule_instance
                                assert service._schedule_manager != original_schedule_instance
