"""
Tests for Issue #1 Fix: Position Creation Failure

Tests enhanced validation, error handling, metrics tracking, and alerting
in UnifiedOrderMonitor._create_position_from_executed_order()
"""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor


class TestPositionCreationIssue1Fix:
    """Test Issue #1 fixes: Enhanced validation, metrics, and alerting"""

    @pytest.fixture
    def unified_monitor(self):
        """Create UnifiedOrderMonitor instance"""
        # Create mock sell_order_manager
        mock_sell_manager = Mock()
        mock_sell_manager.orders = Mock()

        # Create monitor with required parameters
        monitor = UnifiedOrderMonitor(
            sell_order_manager=mock_sell_manager,
            db_session=Mock(),
            user_id=1,
            telegram_notifier=Mock(),
        )
        # Override repos (they're initialized in __init__ but we want to control them)
        monitor.positions_repo = Mock()
        monitor.orders_repo = Mock()
        monitor.telegram_notifier.enabled = True
        monitor._position_creation_metrics = {
            "success": 0,
            "failed_missing_repos": 0,
            "failed_missing_symbol": 0,
            "failed_exception": 0,
        }
        return monitor

    def test_missing_positions_repo_tracks_metrics_and_sends_alert(self, unified_monitor):
        """Test that missing positions_repo tracks metrics and sends alert"""
        # Store original repo to check it wasn't used
        original_repo = unified_monitor.positions_repo
        unified_monitor.positions_repo = None

        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}

        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info=order_info,
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Verify metrics tracked
        assert unified_monitor._position_creation_metrics["failed_missing_repos"] == 1

        # Verify alert sent
        unified_monitor.telegram_notifier.notify_system_alert.assert_called_once()
        call_args = unified_monitor.telegram_notifier.notify_system_alert.call_args
        assert call_args.kwargs["alert_type"] == "POSITION_CREATION_FAILED"
        assert "Missing positions_repo or user_id" in call_args.kwargs["message_text"]
        assert call_args.kwargs["severity"] == "ERROR"
        assert call_args.kwargs["user_id"] == 1

        # Verify position not created (original repo should not have been called)
        original_repo.upsert.assert_not_called()

    def test_missing_user_id_tracks_metrics_and_sends_alert(self, unified_monitor):
        """Test that missing user_id tracks metrics and sends alert"""
        unified_monitor.user_id = None

        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}

        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info=order_info,
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Verify metrics tracked
        assert unified_monitor._position_creation_metrics["failed_missing_repos"] == 1

        # Verify alert sent
        unified_monitor.telegram_notifier.notify_system_alert.assert_called_once()

        # Verify position not created
        unified_monitor.positions_repo.upsert.assert_not_called()

    def test_missing_orders_repo_tracks_metrics_and_sends_alert(self, unified_monitor):
        """Test that missing orders_repo tracks metrics and sends alert"""
        unified_monitor.orders_repo = None

        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}

        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info=order_info,
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Verify metrics tracked
        assert unified_monitor._position_creation_metrics["failed_missing_repos"] == 1

        # Verify alert sent
        unified_monitor.telegram_notifier.notify_system_alert.assert_called_once()
        call_args = unified_monitor.telegram_notifier.notify_system_alert.call_args
        assert "Missing orders_repo" in call_args.kwargs["message_text"]

        # Verify position not created
        unified_monitor.positions_repo.upsert.assert_not_called()

    def test_missing_symbol_tracks_metrics_and_sends_alert(self, unified_monitor):
        """Test that missing symbol tracks metrics and sends alert"""
        order_info = {}  # No symbol

        # Mock orders_repo to return None (no db_order for fallback)
        unified_monitor.orders_repo.get = Mock(return_value=None)
        unified_monitor.orders_repo.get_by_broker_order_id = Mock(return_value=None)

        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info=order_info,
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Verify metrics tracked
        assert unified_monitor._position_creation_metrics["failed_missing_symbol"] == 1

        # Verify alert sent
        unified_monitor.telegram_notifier.notify_system_alert.assert_called_once()
        call_args = unified_monitor.telegram_notifier.notify_system_alert.call_args
        assert "Symbol not found" in call_args.kwargs["message_text"]

        # Verify position not created
        unified_monitor.positions_repo.upsert.assert_not_called()

    def test_missing_symbol_fallback_from_db_order(self, unified_monitor):
        """Test that missing symbol uses fallback from db_order"""
        order_info = {"db_order_id": 1}  # No symbol in order_info

        # Mock db_order with symbol
        db_order = Mock()
        db_order.symbol = "RELIANCE-EQ"
        db_order.order_metadata = {}
        unified_monitor.orders_repo.get = Mock(return_value=db_order)

        # Mock existing position check
        unified_monitor.positions_repo.get_by_symbol_for_update = Mock(return_value=None)

        # Mock transaction
        with patch(
            "modules.kotak_neo_auto_trader.unified_order_monitor.transaction"
        ) as mock_transaction:
            mock_transaction.return_value.__enter__ = Mock(
                return_value=unified_monitor.positions_repo.db
            )
            mock_transaction.return_value.__exit__ = Mock(return_value=False)

            unified_monitor._create_position_from_executed_order(
                order_id="ORDER123",
                order_info=order_info,
                execution_price=100.0,
                execution_qty=10.0,
            )

        # Verify position created (success case)
        assert unified_monitor._position_creation_metrics["success"] == 1
        unified_monitor.positions_repo.upsert.assert_called_once()

    def test_value_error_tracks_metrics_and_sends_alert(self, unified_monitor):
        """Test that ValueError exceptions track metrics and send alert"""
        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}

        # Mock to raise ValueError
        unified_monitor.positions_repo.get_by_symbol_for_update = Mock(
            side_effect=ValueError("Invalid quantity")
        )

        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info=order_info,
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Verify metrics tracked
        assert unified_monitor._position_creation_metrics["failed_exception"] == 1

        # Verify alert sent
        unified_monitor.telegram_notifier.notify_system_alert.assert_called_once()
        call_args = unified_monitor.telegram_notifier.notify_system_alert.call_args
        assert "Invalid data" in call_args.kwargs["message_text"]

    def test_key_error_tracks_metrics_and_sends_alert(self, unified_monitor):
        """Test that KeyError exceptions track metrics and send alert"""
        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}

        # Mock to raise KeyError
        unified_monitor.positions_repo.get_by_symbol_for_update = Mock(
            side_effect=KeyError("missing_field")
        )

        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info=order_info,
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Verify metrics tracked
        assert unified_monitor._position_creation_metrics["failed_exception"] == 1

        # Verify alert sent
        unified_monitor.telegram_notifier.notify_system_alert.assert_called_once()
        call_args = unified_monitor.telegram_notifier.notify_system_alert.call_args
        assert "Missing field" in call_args.kwargs["message_text"]

    def test_general_exception_tracks_metrics_and_sends_alert(self, unified_monitor):
        """Test that general exceptions track metrics and send alert"""
        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}

        # Mock to raise general exception
        unified_monitor.positions_repo.get_by_symbol_for_update = Mock(
            side_effect=Exception("Unexpected error")
        )

        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info=order_info,
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Verify metrics tracked
        assert unified_monitor._position_creation_metrics["failed_exception"] == 1

        # Verify alert sent
        unified_monitor.telegram_notifier.notify_system_alert.assert_called_once()
        call_args = unified_monitor.telegram_notifier.notify_system_alert.call_args
        assert "Unexpected error" in call_args.kwargs["message_text"]

    def test_success_case_tracks_metrics(self, unified_monitor):
        """Test that successful position creation tracks metrics"""
        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}

        # Mock successful position creation
        unified_monitor.positions_repo.get_by_symbol_for_update = Mock(return_value=None)
        unified_monitor.orders_repo.get = Mock(return_value=None)

        # Mock transaction
        with patch(
            "modules.kotak_neo_auto_trader.unified_order_monitor.transaction"
        ) as mock_transaction:
            mock_transaction.return_value.__enter__ = Mock(
                return_value=unified_monitor.positions_repo.db
            )
            mock_transaction.return_value.__exit__ = Mock(return_value=False)

            unified_monitor._create_position_from_executed_order(
                order_id="ORDER123",
                order_info=order_info,
                execution_price=100.0,
                execution_qty=10.0,
            )

        # Verify metrics tracked
        assert unified_monitor._position_creation_metrics["success"] == 1

        # Verify no alert sent (success case)
        unified_monitor.telegram_notifier.notify_system_alert.assert_not_called()

        # Verify position created
        unified_monitor.positions_repo.upsert.assert_called_once()

    def test_telegram_notifier_disabled_no_alert(self, unified_monitor):
        """Test that alerts are not sent if telegram notifier is disabled"""
        unified_monitor.telegram_notifier.enabled = False
        unified_monitor.positions_repo = None

        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}

        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info=order_info,
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Verify metrics still tracked
        assert unified_monitor._position_creation_metrics["failed_missing_repos"] == 1

        # Verify alert NOT sent (notifier disabled)
        unified_monitor.telegram_notifier.notify_system_alert.assert_not_called()

    def test_telegram_notifier_none_no_alert(self, unified_monitor):
        """Test that alerts are not sent if telegram notifier is None"""
        unified_monitor.telegram_notifier = None
        unified_monitor.positions_repo = None

        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}

        # Should not raise exception
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info=order_info,
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Verify metrics still tracked
        assert unified_monitor._position_creation_metrics["failed_missing_repos"] == 1

    def test_alert_send_failure_handled_gracefully(self, unified_monitor):
        """Test that alert send failures are handled gracefully"""
        unified_monitor.positions_repo = None
        unified_monitor.telegram_notifier.notify_system_alert = Mock(
            side_effect=Exception("Telegram API error")
        )

        order_info = {"symbol": "RELIANCE-EQ", "db_order_id": 1}

        # Should not raise exception
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER123",
            order_info=order_info,
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Verify metrics still tracked
        assert unified_monitor._position_creation_metrics["failed_missing_repos"] == 1

    def test_get_position_creation_metrics(self, unified_monitor):
        """Test that get_position_creation_metrics returns correct metrics"""
        # Set some metrics
        unified_monitor._position_creation_metrics = {
            "success": 10,
            "failed_missing_repos": 2,
            "failed_missing_symbol": 1,
            "failed_exception": 3,
        }

        metrics = unified_monitor.get_position_creation_metrics()

        assert metrics["success"] == 10
        assert metrics["failed_missing_repos"] == 2
        assert metrics["failed_missing_symbol"] == 1
        assert metrics["failed_exception"] == 3

    def test_reset_position_creation_metrics(self, unified_monitor):
        """Test that reset_position_creation_metrics resets all metrics"""
        # Set some metrics
        unified_monitor._position_creation_metrics = {
            "success": 10,
            "failed_missing_repos": 2,
            "failed_missing_symbol": 1,
            "failed_exception": 3,
        }

        unified_monitor.reset_position_creation_metrics()

        metrics = unified_monitor.get_position_creation_metrics()
        assert metrics["success"] == 0
        assert metrics["failed_missing_repos"] == 0
        assert metrics["failed_missing_symbol"] == 0
        assert metrics["failed_exception"] == 0

    def test_multiple_failure_types_track_separately(self, unified_monitor):
        """Test that different failure types are tracked separately"""
        # Test missing repos
        unified_monitor.positions_repo = None
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER1",
            order_info={"symbol": "RELIANCE-EQ"},
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Test missing symbol
        unified_monitor.positions_repo = Mock()
        unified_monitor.orders_repo.get = Mock(return_value=None)
        unified_monitor.orders_repo.get_by_broker_order_id = Mock(return_value=None)
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER2",
            order_info={},  # No symbol
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Test exception
        unified_monitor.positions_repo.get_by_symbol_for_update = Mock(
            side_effect=ValueError("Test error")
        )
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER3",
            order_info={"symbol": "RELIANCE-EQ"},
            execution_price=100.0,
            execution_qty=10.0,
        )

        # Verify all tracked separately
        assert unified_monitor._position_creation_metrics["failed_missing_repos"] == 1
        assert unified_monitor._position_creation_metrics["failed_missing_symbol"] == 1
        assert unified_monitor._position_creation_metrics["failed_exception"] == 1
