"""
Tests for Edge Case #12: Cancel pending reentry orders when position closes.

Edge Case #12 fix: When a sell order executes and closes a position,
cancel any pending reentry orders to prevent position from being reopened.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest  # noqa: E402

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager  # noqa: E402
from src.infrastructure.db.models import OrderStatus  # noqa: E402


class TestCancelPendingReentryOrders:
    """Test _cancel_pending_reentry_orders method"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth"""
        return Mock()

    @pytest.fixture
    def sell_manager(self, mock_auth):
        """Create SellOrderManager with mocked dependencies"""
        manager = SellOrderManager(
            auth=mock_auth,
            positions_repo=Mock(),
            user_id=1,
            orders_repo=Mock(),
        )
        manager.orders = Mock()
        return manager

    def test_cancel_pending_reentry_orders_success(self, sell_manager):
        """Test successful cancellation of pending reentry orders"""
        # Setup: Create mock pending reentry orders
        reentry_order_1 = Mock()
        reentry_order_1.id = 1
        reentry_order_1.side = "buy"
        reentry_order_1.status = OrderStatus.PENDING
        reentry_order_1.entry_type = "reentry"
        reentry_order_1.symbol = "RELIANCE-EQ"
        reentry_order_1.broker_order_id = "BROKER_ORDER_123"

        reentry_order_2 = Mock()
        reentry_order_2.id = 2
        reentry_order_2.side = "buy"
        reentry_order_2.status = OrderStatus.PENDING
        reentry_order_2.entry_type = "reentry"
        reentry_order_2.symbol = "RELIANCE-EQ"
        reentry_order_2.broker_order_id = "BROKER_ORDER_456"

        # Mock orders_repo.list to return reentry orders
        sell_manager.orders_repo.list.return_value = [reentry_order_1, reentry_order_2]

        # Mock successful cancellation
        sell_manager.orders.cancel_order.return_value = True

        # Execute
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify
        assert cancelled_count == 2
        assert sell_manager.orders.cancel_order.call_count == 2
        assert sell_manager.orders.cancel_order.call_args_list[0][0][0] == "BROKER_ORDER_123"
        assert sell_manager.orders.cancel_order.call_args_list[1][0][0] == "BROKER_ORDER_456"
        assert sell_manager.orders_repo.update.call_count == 2

    def test_cancel_pending_reentry_orders_no_orders(self, sell_manager):
        """Test when no pending reentry orders exist"""
        # Setup: Mock orders_repo.list to return empty list
        sell_manager.orders_repo.list.return_value = []

        # Execute
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify
        assert cancelled_count == 0
        sell_manager.orders.cancel_order.assert_not_called()
        sell_manager.orders_repo.update.assert_not_called()

    def test_cancel_pending_reentry_orders_filters_by_symbol(self, sell_manager):
        """Test that only reentry orders for the specified symbol are cancelled"""
        # Setup: Create mock orders for different symbols
        reliance_order = Mock()
        reliance_order.id = 1
        reliance_order.side = "buy"
        reliance_order.status = OrderStatus.PENDING
        reliance_order.entry_type = "reentry"
        reliance_order.symbol = "RELIANCE-EQ"
        reliance_order.broker_order_id = "BROKER_ORDER_123"

        tcs_order = Mock()
        tcs_order.id = 2
        tcs_order.side = "buy"
        tcs_order.status = OrderStatus.PENDING
        tcs_order.entry_type = "reentry"
        tcs_order.symbol = "TCS-EQ"
        tcs_order.broker_order_id = "BROKER_ORDER_456"

        # Mock orders_repo.list to return both orders
        sell_manager.orders_repo.list.return_value = [reliance_order, tcs_order]

        # Mock successful cancellation
        sell_manager.orders.cancel_order.return_value = True

        # Execute: Cancel only for RELIANCE
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify: Only RELIANCE order should be cancelled
        assert cancelled_count == 1
        assert sell_manager.orders.cancel_order.call_count == 1
        assert sell_manager.orders.cancel_order.call_args[0][0] == "BROKER_ORDER_123"
        assert sell_manager.orders_repo.update.call_count == 1

    def test_cancel_pending_reentry_orders_filters_by_status(self, sell_manager):
        """Test that only PENDING orders are cancelled (not EXECUTED or CANCELLED)"""
        # Setup: Create mock orders with different statuses
        pending_order = Mock()
        pending_order.id = 1
        pending_order.side = "buy"
        pending_order.status = OrderStatus.PENDING
        pending_order.entry_type = "reentry"
        pending_order.symbol = "RELIANCE-EQ"
        pending_order.broker_order_id = "BROKER_ORDER_123"

        executed_order = Mock()
        executed_order.id = 2
        executed_order.side = "buy"
        executed_order.status = OrderStatus.CLOSED  # CLOSED is used for executed orders
        executed_order.entry_type = "reentry"
        executed_order.symbol = "RELIANCE-EQ"
        executed_order.broker_order_id = "BROKER_ORDER_456"

        cancelled_order = Mock()
        cancelled_order.id = 3
        cancelled_order.side = "buy"
        cancelled_order.status = OrderStatus.CANCELLED
        cancelled_order.entry_type = "reentry"
        cancelled_order.symbol = "RELIANCE-EQ"
        cancelled_order.broker_order_id = "BROKER_ORDER_789"

        # Mock orders_repo.list to return all orders
        sell_manager.orders_repo.list.return_value = [
            pending_order,
            executed_order,
            cancelled_order,
        ]

        # Mock successful cancellation
        sell_manager.orders.cancel_order.return_value = True

        # Execute
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify: Only PENDING order should be cancelled
        assert cancelled_count == 1
        assert sell_manager.orders.cancel_order.call_count == 1
        assert sell_manager.orders.cancel_order.call_args[0][0] == "BROKER_ORDER_123"
        assert sell_manager.orders_repo.update.call_count == 1

    def test_cancel_pending_reentry_orders_filters_by_entry_type(self, sell_manager):
        """Test that only reentry orders are cancelled (not initial entries)"""
        # Setup: Create mock orders with different entry types
        reentry_order = Mock()
        reentry_order.id = 1
        reentry_order.side = "buy"
        reentry_order.status = OrderStatus.PENDING
        reentry_order.entry_type = "reentry"
        reentry_order.symbol = "RELIANCE-EQ"
        reentry_order.broker_order_id = "BROKER_ORDER_123"

        initial_order = Mock()
        initial_order.id = 2
        initial_order.side = "buy"
        initial_order.status = OrderStatus.PENDING
        initial_order.entry_type = "initial"
        initial_order.symbol = "RELIANCE-EQ"
        initial_order.broker_order_id = "BROKER_ORDER_456"

        # Mock orders_repo.list to return both orders
        sell_manager.orders_repo.list.return_value = [reentry_order, initial_order]

        # Mock successful cancellation
        sell_manager.orders.cancel_order.return_value = True

        # Execute
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify: Only reentry order should be cancelled
        assert cancelled_count == 1
        assert sell_manager.orders.cancel_order.call_count == 1
        assert sell_manager.orders.cancel_order.call_args[0][0] == "BROKER_ORDER_123"
        assert sell_manager.orders_repo.update.call_count == 1

    def test_cancel_pending_reentry_orders_no_broker_order_id(self, sell_manager):
        """Test handling of orders without broker_order_id"""
        # Setup: Create mock order without broker_order_id
        reentry_order = Mock()
        reentry_order.id = 1
        reentry_order.side = "buy"
        reentry_order.status = OrderStatus.PENDING
        reentry_order.entry_type = "reentry"
        reentry_order.symbol = "RELIANCE-EQ"
        reentry_order.broker_order_id = None  # No broker_order_id

        # Mock orders_repo.list to return the order
        sell_manager.orders_repo.list.return_value = [reentry_order]

        # Execute
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify: DB status should be updated even without broker_order_id
        assert cancelled_count == 1
        sell_manager.orders.cancel_order.assert_not_called()  # Should not call broker API
        assert sell_manager.orders_repo.update.call_count == 1
        # Verify update was called with CANCELLED status
        update_call = sell_manager.orders_repo.update.call_args
        assert update_call[0][0] == reentry_order
        assert update_call[1]["status"] == OrderStatus.CANCELLED
        assert update_call[1]["reason"] == "Position closed"

    def test_cancel_pending_reentry_orders_broker_cancel_fails(self, sell_manager):
        """Test handling when broker cancellation fails"""
        # Setup: Create mock pending reentry order
        reentry_order = Mock()
        reentry_order.id = 1
        reentry_order.side = "buy"
        reentry_order.status = OrderStatus.PENDING
        reentry_order.entry_type = "reentry"
        reentry_order.symbol = "RELIANCE-EQ"
        reentry_order.broker_order_id = "BROKER_ORDER_123"

        # Mock orders_repo.list to return the order
        sell_manager.orders_repo.list.return_value = [reentry_order]

        # Mock failed cancellation
        sell_manager.orders.cancel_order.return_value = False

        # Execute
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify: DB status should still be updated even if broker cancellation fails
        assert cancelled_count == 1
        assert sell_manager.orders.cancel_order.call_count == 1
        assert sell_manager.orders_repo.update.call_count == 1
        # Verify update was called with CANCELLED status and appropriate reason
        update_call = sell_manager.orders_repo.update.call_args
        assert update_call[0][0] == reentry_order
        assert update_call[1]["status"] == OrderStatus.CANCELLED
        assert "cancellation attempted" in update_call[1]["reason"].lower()

    def test_cancel_pending_reentry_orders_broker_cancel_exception(self, sell_manager):
        """Test handling when broker cancellation raises exception"""
        # Setup: Create mock pending reentry order
        reentry_order = Mock()
        reentry_order.id = 1
        reentry_order.side = "buy"
        reentry_order.status = OrderStatus.PENDING
        reentry_order.entry_type = "reentry"
        reentry_order.symbol = "RELIANCE-EQ"
        reentry_order.broker_order_id = "BROKER_ORDER_123"

        # Mock orders_repo.list to return the order
        sell_manager.orders_repo.list.return_value = [reentry_order]

        # Mock exception during cancellation
        sell_manager.orders.cancel_order.side_effect = Exception("Broker API error")

        # Execute
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify: Should handle exception gracefully and continue
        assert cancelled_count == 0  # No orders successfully cancelled due to exception
        assert sell_manager.orders.cancel_order.call_count == 1
        # DB status should not be updated if exception occurs
        sell_manager.orders_repo.update.assert_not_called()

    def test_cancel_pending_reentry_orders_missing_dependencies(self, sell_manager):
        """Test handling when orders_repo or user_id is not available"""
        # Setup: Remove dependencies
        sell_manager.orders_repo = None
        sell_manager.user_id = None

        # Execute
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify: Should return 0 and not fail
        assert cancelled_count == 0
        sell_manager.orders.cancel_order.assert_not_called()

    def test_cancel_pending_reentry_orders_missing_orders_repo(self, sell_manager):
        """Test handling when only orders_repo is missing"""
        # Setup: Remove orders_repo
        sell_manager.orders_repo = None

        # Execute
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify: Should return 0 and not fail
        assert cancelled_count == 0
        sell_manager.orders.cancel_order.assert_not_called()

    def test_cancel_pending_reentry_orders_missing_user_id(self, sell_manager):
        """Test handling when only user_id is missing"""
        # Setup: Remove user_id
        sell_manager.user_id = None

        # Execute
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify: Should return 0 and not fail
        assert cancelled_count == 0
        sell_manager.orders.cancel_order.assert_not_called()

    def test_cancel_pending_reentry_orders_multiple_symbols(self, sell_manager):
        """Test that cancellation correctly filters by symbol when multiple symbols have reentry orders"""
        # Setup: Create mock orders for different symbols
        reliance_order_1 = Mock()
        reliance_order_1.id = 1
        reliance_order_1.side = "buy"
        reliance_order_1.status = OrderStatus.PENDING
        reliance_order_1.entry_type = "reentry"
        reliance_order_1.symbol = "RELIANCE-EQ"
        reliance_order_1.broker_order_id = "BROKER_ORDER_123"

        reliance_order_2 = Mock()
        reliance_order_2.id = 2
        reliance_order_2.side = "buy"
        reliance_order_2.status = OrderStatus.PENDING
        reliance_order_2.entry_type = "reentry"
        reliance_order_2.symbol = "RELIANCE-EQ"
        reliance_order_2.broker_order_id = "BROKER_ORDER_456"

        tcs_order = Mock()
        tcs_order.id = 3
        tcs_order.side = "buy"
        tcs_order.status = OrderStatus.PENDING
        tcs_order.entry_type = "reentry"
        tcs_order.symbol = "TCS-EQ"
        tcs_order.broker_order_id = "BROKER_ORDER_789"

        # Mock orders_repo.list to return all orders
        sell_manager.orders_repo.list.return_value = [
            reliance_order_1,
            reliance_order_2,
            tcs_order,
        ]

        # Mock successful cancellation
        sell_manager.orders.cancel_order.return_value = True

        # Execute: Cancel only for RELIANCE
        cancelled_count = sell_manager._cancel_pending_reentry_orders("RELIANCE")

        # Verify: Only RELIANCE orders should be cancelled
        assert cancelled_count == 2
        assert sell_manager.orders.cancel_order.call_count == 2
        cancelled_order_ids = [
            call[0][0] for call in sell_manager.orders.cancel_order.call_args_list
        ]
        assert "BROKER_ORDER_123" in cancelled_order_ids
        assert "BROKER_ORDER_456" in cancelled_order_ids
        assert "BROKER_ORDER_789" not in cancelled_order_ids
        assert sell_manager.orders_repo.update.call_count == 2

