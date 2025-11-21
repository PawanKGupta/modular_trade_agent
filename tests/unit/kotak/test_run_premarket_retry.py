#!/usr/bin/env python3
"""
Tests for run_premarket_retry method in TradingService

Tests that run_premarket_retry calls retry_pending_orders_from_db
instead of processing retry queue during buy order placement.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    return MagicMock()


@pytest.fixture
def mock_engine():
    """Mock AutoTradeEngine"""
    engine = MagicMock()
    engine.retry_pending_orders_from_db = Mock(
        return_value={
            "retried": 2,
            "placed": 1,
            "failed": 1,
            "skipped": 0,
        }
    )
    return engine


@pytest.fixture
def trading_service(mock_db_session, mock_engine):
    """Create TradingService instance"""
    from modules.kotak_neo_auto_trader.run_trading_service import TradingService

    with patch(
        "modules.kotak_neo_auto_trader.run_trading_service.AutoTradeEngine"
    ) as mock_engine_class:
        mock_engine_class.return_value = mock_engine

        service = TradingService(
            user_id=1,
            db_session=mock_db_session,
            skip_execution_tracking=False,
        )

        service.engine = mock_engine
        service.logger = MagicMock()
        service.tasks_completed = {"premarket_retry": False}

        return service


class TestRunPremarketRetry:
    """Test run_premarket_retry method"""

    def test_run_premarket_retry_calls_retry_pending_orders_from_db(
        self, trading_service, mock_engine
    ):
        """Test that run_premarket_retry calls retry_pending_orders_from_db"""

        # Mock execute_task context manager
        with patch(
            "src.application.services.task_execution_wrapper.execute_task"
        ) as mock_execute_task:
            mock_context = {}  # Use real dict instead of MagicMock
            mock_context_manager = MagicMock()
            mock_context_manager.__enter__ = Mock(return_value=mock_context)
            mock_context_manager.__exit__ = Mock(return_value=None)
            mock_execute_task.return_value = mock_context_manager

            # Call run_premarket_retry
            trading_service.run_premarket_retry()

            # Verify retry_pending_orders_from_db was called
            mock_engine.retry_pending_orders_from_db.assert_called_once()

            # Verify task context was updated
            assert mock_context["summary"]["retried"] == 2
            assert mock_context["summary"]["placed"] == 1
            assert mock_context["summary"]["failed"] == 1
            assert mock_context["summary"]["skipped"] == 0
            assert mock_context["retried"] == 2
            assert mock_context["placed"] == 1
            assert mock_context["failed"] == 1
            assert mock_context["skipped"] == 0

    def test_run_premarket_retry_no_orders(self, trading_service, mock_engine):
        """Test run_premarket_retry when no orders to retry"""

        # Mock empty summary
        mock_engine.retry_pending_orders_from_db.return_value = {
            "retried": 0,
            "placed": 0,
            "failed": 0,
            "skipped": 0,
        }

        # Mock execute_task context manager
        with patch(
            "src.application.services.task_execution_wrapper.execute_task"
        ) as mock_execute_task:
            mock_context = {}  # Use real dict instead of MagicMock
            mock_context_manager = MagicMock()
            mock_context_manager.__enter__ = Mock(return_value=mock_context)
            mock_context_manager.__exit__ = Mock(return_value=None)
            mock_execute_task.return_value = mock_context_manager

            # Call run_premarket_retry
            trading_service.run_premarket_retry()

            # Verify retry_pending_orders_from_db was called
            mock_engine.retry_pending_orders_from_db.assert_called_once()

            # Verify task context was updated
            assert mock_context["summary"]["retried"] == 0
            assert mock_context["retried"] == 0

    def test_run_premarket_retry_does_not_call_place_new_entries(
        self, trading_service, mock_engine
    ):
        """Test that run_premarket_retry does NOT call place_new_entries"""

        # Mock execute_task context manager
        with patch(
            "src.application.services.task_execution_wrapper.execute_task"
        ) as mock_execute_task:
            mock_context = {}  # Use real dict instead of MagicMock
            mock_context_manager = MagicMock()
            mock_context_manager.__enter__ = Mock(return_value=mock_context)
            mock_context_manager.__exit__ = Mock(return_value=None)
            mock_execute_task.return_value = mock_context_manager

            # Call run_premarket_retry
            trading_service.run_premarket_retry()

            # Verify place_new_entries was NOT called
            mock_engine.place_new_entries.assert_not_called()

            # Verify load_latest_recommendations was NOT called
            mock_engine.load_latest_recommendations.assert_not_called()

            # Verify retry_pending_orders_from_db WAS called
            mock_engine.retry_pending_orders_from_db.assert_called_once()

    def test_run_premarket_retry_marks_task_completed(self, trading_service, mock_engine):
        """Test that run_premarket_retry marks task as completed"""

        # Mock execute_task context manager
        with patch(
            "src.application.services.task_execution_wrapper.execute_task"
        ) as mock_execute_task:
            mock_context = {}  # Use real dict instead of MagicMock
            mock_context_manager = MagicMock()
            mock_context_manager.__enter__ = Mock(return_value=mock_context)
            mock_context_manager.__exit__ = Mock(return_value=None)
            mock_execute_task.return_value = mock_context_manager

            # Verify task not completed initially
            assert trading_service.tasks_completed["premarket_retry"] is False

            # Call run_premarket_retry
            trading_service.run_premarket_retry()

            # Verify task marked as completed
            assert trading_service.tasks_completed["premarket_retry"] is True
