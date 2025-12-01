"""
Tests for Phase 10: Manual Activity Detection in OrderStateManager

Tests detection of manual cancellations and modifications for buy orders.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.order_state_manager import OrderStateManager


@pytest.fixture
def mock_telegram_notifier():
    """Mock TelegramNotifier"""
    notifier = Mock()
    notifier.enabled = True
    notifier.send_message = Mock(return_value=True)
    notifier.notify_order_cancelled = Mock(return_value=True)
    notifier.notify_order_modified = Mock(return_value=True)
    # Mock preference service to allow notifications
    notifier.preference_service = None  # No preference service = legacy behavior (always send)
    notifier._should_send_notification = Mock(return_value=True)  # Always allow notifications
    return notifier


@pytest.fixture
def mock_orders_repo():
    """Mock OrdersRepository"""
    repo = Mock()
    repo.list = Mock(return_value=[])
    repo.update = Mock()
    repo.mark_cancelled = Mock()
    return repo


@pytest.fixture
def order_state_manager(mock_telegram_notifier, mock_orders_repo):
    """Create OrderStateManager instance with mocks"""
    manager = OrderStateManager(
        history_path="test_history.json",
        data_dir="test_data",
        telegram_notifier=mock_telegram_notifier,
        orders_repo=mock_orders_repo,
        user_id=1,
    )
    return manager


class TestManualActivityDetectionPhase10:
    """Test Phase 10 manual activity detection"""

    def test_detect_manual_price_modification(
        self, order_state_manager, mock_telegram_notifier, mock_orders_repo
    ):
        """Test detection of manual price modification"""
        # Register buy order with original price
        order_id = "ORDER123"
        order_state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id=order_id,
            quantity=10,
            price=2500.0,
        )

        # Mock broker order with modified price
        broker_order = {
            "neoOrdNo": order_id,
            "ordSt": "OPEN",
            "prc": 2495.0,  # Modified price
            "qty": 10,
        }

        stats = {}
        order_info = order_state_manager.get_active_buy_order(order_id)

        # Detect modifications
        order_state_manager._detect_manual_modifications(order_id, order_info, broker_order, stats)

        # Verify modification was detected
        assert stats.get("buy_manual_modified", 0) == 1
        assert order_info["price"] == 2495.0  # Updated price

        # Verify notification was sent (now uses notify_order_modified)
        mock_telegram_notifier.notify_order_modified.assert_called_once()
        call_args = mock_telegram_notifier.notify_order_modified.call_args
        assert call_args[1]["symbol"] == "RELIANCE"
        assert call_args[1]["order_id"] == "ORDER123"
        assert "price" in call_args[1]["changes"]
        assert call_args[1]["changes"]["price"] == (2500.0, 2495.0)

    def test_detect_manual_quantity_modification(self, order_state_manager, mock_telegram_notifier):
        """Test detection of manual quantity modification"""
        # Register buy order with original quantity
        order_id = "ORDER123"
        order_state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id=order_id,
            quantity=10,
            price=2500.0,
        )

        # Mock broker order with modified quantity
        broker_order = {
            "neoOrdNo": order_id,
            "ordSt": "OPEN",
            "prc": 2500.0,
            "qty": 15,  # Modified quantity
        }

        stats = {}
        order_info = order_state_manager.get_active_buy_order(order_id)

        # Detect modifications
        order_state_manager._detect_manual_modifications(order_id, order_info, broker_order, stats)

        # Verify modification was detected
        assert stats.get("buy_manual_modified", 0) == 1
        assert order_info["quantity"] == 15  # Updated quantity

        # Verify notification was sent (now uses notify_order_modified)
        mock_telegram_notifier.notify_order_modified.assert_called_once()
        call_args = mock_telegram_notifier.notify_order_modified.call_args
        assert call_args[1]["symbol"] == "RELIANCE"
        assert call_args[1]["order_id"] == "ORDER123"
        assert "quantity" in call_args[1]["changes"]
        assert call_args[1]["changes"]["quantity"] == (10, 15)

    def test_detect_manual_price_and_quantity_modification(
        self, order_state_manager, mock_telegram_notifier
    ):
        """Test detection of both price and quantity modifications"""
        # Register buy order
        order_id = "ORDER123"
        order_state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id=order_id,
            quantity=10,
            price=2500.0,
        )

        # Mock broker order with both modified
        broker_order = {
            "neoOrdNo": order_id,
            "ordSt": "OPEN",
            "prc": 2495.0,  # Modified price
            "qty": 15,  # Modified quantity
        }

        stats = {}
        order_info = order_state_manager.get_active_buy_order(order_id)

        # Detect modifications
        order_state_manager._detect_manual_modifications(order_id, order_info, broker_order, stats)

        # Verify modification was detected
        assert stats.get("buy_manual_modified", 0) == 1
        assert order_info["price"] == 2495.0
        assert order_info["quantity"] == 15

        # Verify notification includes both changes (now uses notify_order_modified)
        mock_telegram_notifier.notify_order_modified.assert_called_once()
        call_args = mock_telegram_notifier.notify_order_modified.call_args
        assert "price" in call_args[1]["changes"]
        assert "quantity" in call_args[1]["changes"]
        assert call_args[1]["changes"]["price"] == (2500.0, 2495.0)
        assert call_args[1]["changes"]["quantity"] == (10, 15)

    def test_no_modification_detected_when_values_match(self, order_state_manager):
        """Test that no modification is detected when values match"""
        # Register buy order
        order_id = "ORDER123"
        order_state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id=order_id,
            quantity=10,
            price=2500.0,
        )

        # Mock broker order with same values
        broker_order = {
            "neoOrdNo": order_id,
            "ordSt": "OPEN",
            "prc": 2500.0,  # Same price
            "qty": 10,  # Same quantity
        }

        stats = {}
        order_info = order_state_manager.get_active_buy_order(order_id)

        # Detect modifications
        order_state_manager._detect_manual_modifications(order_id, order_info, broker_order, stats)

        # Verify no modification was detected
        assert stats.get("buy_manual_modified", 0) == 0

    def test_handle_manual_cancellation(
        self, order_state_manager, mock_telegram_notifier, mock_orders_repo
    ):
        """Test handling of manual cancellation"""
        # Register buy order
        order_id = "ORDER123"
        order_state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id=order_id,
            quantity=10,
            price=2500.0,
        )

        # Mock broker order with cancelled status
        broker_order = {
            "neoOrdNo": order_id,
            "ordSt": "CANCELLED",
            "rejRsn": "User cancelled",
        }

        order_info = order_state_manager.get_active_buy_order(order_id)

        # Handle manual cancellation
        order_state_manager._handle_manual_cancellation(order_id, order_info, broker_order)

        # Verify order was marked as manually cancelled
        assert order_info.get("is_manual_cancelled") is True

        # Verify notification was sent
        mock_telegram_notifier.notify_order_cancelled.assert_called_once()
        call_args = mock_telegram_notifier.notify_order_cancelled.call_args
        assert call_args[1]["symbol"] == "RELIANCE"
        assert call_args[1]["order_id"] == order_id
        assert "Manual" in call_args[1]["cancellation_reason"]

    def test_sync_with_broker_detects_manual_cancellation(
        self, order_state_manager, mock_telegram_notifier
    ):
        """Test that sync_with_broker detects manual cancellation"""
        # Register buy order
        order_id = "ORDER123"
        order_state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id=order_id,
            quantity=10,
            price=2500.0,
        )

        # Mock orders API
        mock_orders_api = Mock()
        broker_orders = [
            {
                "neoOrdNo": order_id,
                "ordSt": "CANCELLED",
                "rejRsn": "User cancelled",
            }
        ]

        # Sync with broker
        stats = order_state_manager.sync_with_broker(mock_orders_api, broker_orders)

        # Verify manual cancellation was detected
        assert stats.get("buy_manual_cancelled", 0) == 1

        # Verify notification was sent
        mock_telegram_notifier.notify_order_cancelled.assert_called_once()

    def test_sync_with_broker_detects_manual_modification(
        self, order_state_manager, mock_telegram_notifier
    ):
        """Test that sync_with_broker detects manual modification"""
        # Register buy order
        order_id = "ORDER123"
        order_state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id=order_id,
            quantity=10,
            price=2500.0,
        )

        # Mock orders API
        mock_orders_api = Mock()
        broker_orders = [
            {
                "neoOrdNo": order_id,
                "ordSt": "OPEN",
                "prc": 2495.0,  # Modified price
                "qty": 10,
            }
        ]

        # Sync with broker
        stats = order_state_manager.sync_with_broker(mock_orders_api, broker_orders)

        # Verify manual modification was detected
        assert stats.get("buy_manual_modified", 0) == 1

        # Verify notification was sent (now uses notify_order_modified)
        mock_telegram_notifier.notify_order_modified.assert_called_once()

    def test_update_db_for_manual_modification(self, order_state_manager, mock_orders_repo):
        """Test database update for manual modification"""
        # Mock database order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = "ORDER123"
        mock_db_order.symbol = "RELIANCE"
        mock_orders_repo.list.return_value = [mock_db_order]

        # Update DB for manual modification
        order_state_manager._update_db_for_manual_modification(
            order_id="ORDER123",
            symbol="RELIANCE",
            new_price=2495.0,
            new_quantity=15,
        )

        # Verify DB was updated
        mock_orders_repo.update.assert_called_once()
        call_args = mock_orders_repo.update.call_args
        assert call_args[0][0] == mock_db_order
        assert call_args[1]["price"] == 2495.0
        assert call_args[1]["quantity"] == 15
        assert call_args[1]["is_manual"] is True

    def test_update_db_for_manual_cancellation(self, order_state_manager, mock_orders_repo):
        """Test database update for manual cancellation"""
        # Mock database order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = "ORDER123"
        mock_db_order.symbol = "RELIANCE"
        mock_orders_repo.list.return_value = [mock_db_order]

        # Update DB for manual cancellation
        order_state_manager._update_db_for_manual_cancellation(
            order_id="ORDER123",
            symbol="RELIANCE",
            cancellation_reason="User cancelled",
        )

        # Verify DB was updated
        mock_orders_repo.mark_cancelled.assert_called_once()
        mock_orders_repo.update.assert_called_once()
        call_args = mock_orders_repo.update.call_args
        assert call_args[1]["is_manual"] is True

    def test_no_notification_when_telegram_disabled(self, order_state_manager):
        """Test that no notification is sent when telegram is disabled"""
        order_state_manager.telegram_notifier.enabled = False

        # Register buy order
        order_id = "ORDER123"
        order_state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id=order_id,
            quantity=10,
            price=2500.0,
        )

        # Mock broker order with modified price
        broker_order = {
            "neoOrdNo": order_id,
            "ordSt": "OPEN",
            "prc": 2495.0,
            "qty": 10,
        }

        stats = {}
        order_info = order_state_manager.get_active_buy_order(order_id)

        # Detect modifications
        order_state_manager._detect_manual_modifications(order_id, order_info, broker_order, stats)

        # Verify modification was detected but no notification sent
        assert stats.get("buy_manual_modified", 0) == 1
        order_state_manager.telegram_notifier.send_message.assert_not_called()

    def test_no_db_update_when_repo_not_available(self, order_state_manager):
        """Test that DB update is skipped when repo is not available"""
        order_state_manager.orders_repo = None

        # Register buy order
        order_id = "ORDER123"
        order_state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id=order_id,
            quantity=10,
            price=2500.0,
        )

        # Mock broker order with modified price
        broker_order = {
            "neoOrdNo": order_id,
            "ordSt": "OPEN",
            "prc": 2495.0,
            "qty": 10,
        }

        stats = {}
        order_info = order_state_manager.get_active_buy_order(order_id)

        # Should not raise exception
        order_state_manager._detect_manual_modifications(order_id, order_info, broker_order, stats)

        # Verify modification was still detected
        assert stats.get("buy_manual_modified", 0) == 1

    def test_manual_modification_handles_errors_gracefully(self, order_state_manager):
        """Test that errors in manual modification detection don't crash"""
        # Register buy order
        order_id = "ORDER123"
        order_state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id=order_id,
            quantity=10,
            price=2500.0,
        )

        # Mock broker order that will cause error
        broker_order = None  # Invalid broker order

        stats = {}
        order_info = order_state_manager.get_active_buy_order(order_id)

        # Should not raise exception
        order_state_manager._detect_manual_modifications(order_id, order_info, broker_order, stats)

    def test_manual_cancellation_handles_errors_gracefully(self, order_state_manager):
        """Test that errors in manual cancellation handling don't crash"""
        # Register buy order
        order_id = "ORDER123"
        order_state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id=order_id,
            quantity=10,
            price=2500.0,
        )

        # Mock broker order that will cause error
        broker_order = None  # Invalid broker order

        order_info = order_state_manager.get_active_buy_order(order_id)

        # Should not raise exception
        order_state_manager._handle_manual_cancellation(order_id, order_info, broker_order)
