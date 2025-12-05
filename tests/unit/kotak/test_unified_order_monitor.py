#!/usr/bin/env python3
"""
Tests for UnifiedOrderMonitor
Tests buy and sell order monitoring functionality.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


class TestUnifiedOrderMonitor:
    """Test UnifiedOrderMonitor unified order monitoring"""

    @pytest.fixture
    def mock_sell_manager(self):
        """Create mock SellOrderManager"""
        sell_manager = Mock()
        sell_manager.orders = Mock()
        sell_manager.monitor_and_update = Mock(
            return_value={"checked": 5, "updated": 2, "executed": 1}
        )
        return sell_manager

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session"""
        return Mock()

    @pytest.fixture
    def mock_orders_repo(self):
        """Create mock OrdersRepository"""
        repo = Mock()
        repo.get_pending_amo_orders = Mock(return_value=[])
        repo.get = Mock()
        repo.update_status_check = Mock()
        repo.mark_executed = Mock()
        repo.mark_rejected = Mock()
        repo.mark_cancelled = Mock()
        return repo

    @pytest.fixture
    def unified_monitor(self, mock_sell_manager, mock_db_session, mock_orders_repo):
        """Create UnifiedOrderMonitor instance with mocks"""
        with (
            patch("modules.kotak_neo_auto_trader.unified_order_monitor.DB_AVAILABLE", True),
            patch(
                "modules.kotak_neo_auto_trader.unified_order_monitor.OrdersRepository",
                return_value=mock_orders_repo,
            ),
        ):
            from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor

            monitor = UnifiedOrderMonitor(
                sell_order_manager=mock_sell_manager,
                db_session=mock_db_session,
                user_id=1,
            )
            monitor.orders_repo = mock_orders_repo
            return monitor

    def test_initialization(self, mock_sell_manager, mock_db_session):
        """Test UnifiedOrderMonitor initialization"""
        from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor

        monitor = UnifiedOrderMonitor(
            sell_order_manager=mock_sell_manager,
            db_session=mock_db_session,
            user_id=1,
        )

        assert monitor.sell_manager == mock_sell_manager
        assert monitor.orders == mock_sell_manager.orders
        assert monitor.db_session == mock_db_session
        assert monitor.user_id == 1
        assert monitor.active_buy_orders == {}

    def test_initialization_without_db(self, mock_sell_manager):
        """Test initialization when DB is not available"""
        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.DB_AVAILABLE", False):
            from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor

            monitor = UnifiedOrderMonitor(
                sell_order_manager=mock_sell_manager,
                db_session=None,
                user_id=None,
            )

            assert monitor.orders_repo is None

    def test_load_pending_buy_orders_empty(self, unified_monitor, mock_orders_repo):
        """Test loading pending buy orders when none exist"""
        mock_orders_repo.get_pending_amo_orders.return_value = []

        count = unified_monitor.load_pending_buy_orders()

        assert count == 0
        assert len(unified_monitor.active_buy_orders) == 0
        mock_orders_repo.get_pending_amo_orders.assert_called_once_with(1)

    def test_load_pending_buy_orders_with_orders(self, unified_monitor, mock_orders_repo):
        """Test loading pending buy orders"""
        # Create mock order objects
        mock_order1 = Mock()
        mock_order1.id = 1
        mock_order1.broker_order_id = "BROKER123"
        mock_order1.order_id = "ORDER123"
        mock_order1.symbol = "RELIANCE"
        mock_order1.quantity = 10.0
        mock_order1.status = Mock(value="amo")
        mock_order1.placed_at = datetime.now()

        mock_order2 = Mock()
        mock_order2.id = 2
        mock_order2.broker_order_id = "BROKER456"
        mock_order2.order_id = "ORDER456"
        mock_order2.symbol = "TCS"
        mock_order2.quantity = 5.0
        mock_order2.status = Mock(value="amo")
        mock_order2.placed_at = datetime.now()

        mock_orders_repo.get_pending_amo_orders.return_value = [mock_order1, mock_order2]

        count = unified_monitor.load_pending_buy_orders()

        assert count == 2
        assert len(unified_monitor.active_buy_orders) == 2
        assert "BROKER123" in unified_monitor.active_buy_orders
        assert "BROKER456" in unified_monitor.active_buy_orders
        assert unified_monitor.active_buy_orders["BROKER123"]["symbol"] == "RELIANCE"
        assert unified_monitor.active_buy_orders["BROKER456"]["symbol"] == "TCS"

    def test_load_pending_buy_orders_no_broker_order_id(self, unified_monitor, mock_orders_repo):
        """Test loading orders without broker_order_id uses order_id"""
        mock_order = Mock()
        mock_order.id = 1
        mock_order.broker_order_id = None
        mock_order.order_id = "ORDER123"
        mock_order.symbol = "RELIANCE"
        mock_order.quantity = 10.0
        mock_order.status = Mock(value="amo")
        mock_order.placed_at = datetime.now()

        mock_orders_repo.get_pending_amo_orders.return_value = [mock_order]

        count = unified_monitor.load_pending_buy_orders()

        assert count == 1
        assert "ORDER123" in unified_monitor.active_buy_orders

    def test_load_pending_buy_orders_no_db(self, mock_sell_manager):
        """Test loading when DB is not available"""
        with patch("modules.kotak_neo_auto_trader.unified_order_monitor.DB_AVAILABLE", False):
            from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor

            monitor = UnifiedOrderMonitor(
                sell_order_manager=mock_sell_manager,
                db_session=None,
                user_id=None,
            )

            count = monitor.load_pending_buy_orders()
            assert count == 0

    def test_check_buy_order_status_no_orders(self, unified_monitor):
        """Test checking status when no active buy orders"""
        stats = unified_monitor.check_buy_order_status()

        assert stats["checked"] == 0
        assert stats["executed"] == 0
        assert stats["rejected"] == 0
        assert stats["cancelled"] == 0

    def test_check_buy_order_status_executed(self, unified_monitor, mock_orders_repo):
        """Test checking status for executed order"""
        # Setup active buy order
        unified_monitor.active_buy_orders["ORDER123"] = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
            "order_id": "ORDER123",
            "db_order_id": 1,
            "status": "amo",
            "placed_at": datetime.now(),
        }

        # Mock broker order response
        broker_order = {
            "neoOrdNo": "ORDER123",
            "orderStatus": "EXECUTED",
            "avgPrc": 2450.50,
            "qty": 10,
        }

        # Mock database order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_orders_repo.get.return_value = mock_db_order

        stats = unified_monitor.check_buy_order_status(broker_orders=[broker_order])

        assert stats["checked"] == 1
        assert stats["executed"] == 1
        assert stats["rejected"] == 0
        assert stats["cancelled"] == 0
        assert "ORDER123" not in unified_monitor.active_buy_orders
        mock_orders_repo.mark_executed.assert_called_once()

    def test_check_buy_order_status_rejected(self, unified_monitor, mock_orders_repo):
        """Test checking status for rejected order"""
        unified_monitor.active_buy_orders["ORDER123"] = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
            "order_id": "ORDER123",
            "db_order_id": 1,
            "status": "amo",
            "placed_at": datetime.now(),
        }

        broker_order = {
            "neoOrdNo": "ORDER123",
            "orderStatus": "REJECTED",
            "rejRsn": "Insufficient funds",
        }

        mock_db_order = Mock()
        mock_orders_repo.get.return_value = mock_db_order

        stats = unified_monitor.check_buy_order_status(broker_orders=[broker_order])

        assert stats["checked"] == 1
        assert stats["executed"] == 0
        assert stats["rejected"] == 1
        assert stats["cancelled"] == 0
        assert "ORDER123" not in unified_monitor.active_buy_orders
        mock_orders_repo.mark_rejected.assert_called_once()

    def test_check_buy_order_status_cancelled(self, unified_monitor, mock_orders_repo):
        """Test checking status for cancelled order"""
        unified_monitor.active_buy_orders["ORDER123"] = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
            "order_id": "ORDER123",
            "db_order_id": 1,
            "status": "amo",
            "placed_at": datetime.now(),
        }

        broker_order = {
            "neoOrdNo": "ORDER123",
            "orderStatus": "CANCELLED",
        }

        mock_db_order = Mock()
        mock_orders_repo.get.return_value = mock_db_order

        stats = unified_monitor.check_buy_order_status(broker_orders=[broker_order])

        assert stats["checked"] == 1
        assert stats["executed"] == 0
        assert stats["rejected"] == 0
        assert stats["cancelled"] == 1
        assert "ORDER123" not in unified_monitor.active_buy_orders
        mock_orders_repo.mark_cancelled.assert_called_once()

    def test_check_buy_order_status_fetch_from_broker(self, unified_monitor, mock_sell_manager):
        """Test fetching orders from broker when not provided"""
        unified_monitor.active_buy_orders["ORDER123"] = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
            "order_id": "ORDER123",
            "db_order_id": 1,
            "status": "amo",
            "placed_at": datetime.now(),
        }

        # Mock broker API response
        mock_orders_api = Mock()
        mock_orders_api.get_orders.return_value = {"data": []}
        unified_monitor.orders = mock_orders_api

        stats = unified_monitor.check_buy_order_status()

        assert stats["checked"] == 1
        mock_orders_api.get_orders.assert_called_once()

    def test_check_buy_order_status_order_not_found(self, unified_monitor):
        """Test when order is not found in broker orders"""
        unified_monitor.active_buy_orders["ORDER123"] = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
            "order_id": "ORDER123",
            "db_order_id": 1,
            "status": "amo",
            "placed_at": datetime.now(),
        }

        stats = unified_monitor.check_buy_order_status(broker_orders=[])

        assert stats["checked"] == 1
        assert stats["executed"] == 0
        # Order should remain in tracking if not found
        assert "ORDER123" in unified_monitor.active_buy_orders

    def test_update_buy_order_status_executed(self, unified_monitor, mock_orders_repo):
        """Test updating buy order status for executed order"""
        mock_db_order = Mock()
        broker_order = {
            "orderStatus": "EXECUTED",
            "avgPrc": 2450.50,
            "qty": 10,
        }

        unified_monitor._update_buy_order_status(mock_db_order, broker_order, "executed")

        mock_orders_repo.update_status_check.assert_called_once_with(mock_db_order)
        mock_orders_repo.mark_executed.assert_called_once()

    def test_update_buy_order_status_rejected(self, unified_monitor, mock_orders_repo):
        """Test updating buy order status for rejected order"""
        mock_db_order = Mock()
        broker_order = {
            "orderStatus": "REJECTED",
            "rejRsn": "Insufficient funds",
        }

        unified_monitor._update_buy_order_status(mock_db_order, broker_order, "rejected")

        mock_orders_repo.update_status_check.assert_called_once_with(mock_db_order)
        mock_orders_repo.mark_rejected.assert_called_once()

    def test_update_buy_order_status_cancelled(self, unified_monitor, mock_orders_repo):
        """Test updating buy order status for cancelled order"""
        mock_db_order = Mock()
        broker_order = {
            "orderStatus": "CANCELLED",
        }

        unified_monitor._update_buy_order_status(mock_db_order, broker_order, "cancelled")

        mock_orders_repo.update_status_check.assert_called_once_with(mock_db_order)
        mock_orders_repo.mark_cancelled.assert_called_once()

    def test_handle_buy_order_execution(self, unified_monitor):
        """Test handling executed buy order"""
        order_id = "ORDER123"
        order_info = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
        }
        broker_order = {
            "avgPrc": 2450.50,
            "qty": 10,
        }

        # Should not raise exception
        unified_monitor._handle_buy_order_execution(order_id, order_info, broker_order)

    def test_handle_buy_order_rejection(self, unified_monitor):
        """Test handling rejected buy order"""
        order_id = "ORDER123"
        order_info = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
        }
        broker_order = {
            "rejRsn": "Insufficient funds",
        }

        # Should not raise exception
        unified_monitor._handle_buy_order_rejection(order_id, order_info, broker_order)

    def test_handle_buy_order_cancellation(self, unified_monitor):
        """Test handling cancelled buy order"""
        order_id = "ORDER123"
        order_info = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
        }
        broker_order = {
            "rejRsn": "User cancelled",
        }

        # Should not raise exception
        unified_monitor._handle_buy_order_cancellation(order_id, order_info, broker_order)

    def test_monitor_all_orders_no_buy_orders(self, unified_monitor, mock_sell_manager):
        """Test monitoring when no buy orders exist"""
        mock_sell_manager.monitor_and_update.return_value = {
            "checked": 5,
            "updated": 2,
            "executed": 1,
        }

        stats = unified_monitor.monitor_all_orders()

        assert stats["checked"] == 5
        assert stats["updated"] == 2
        assert stats["executed"] == 1
        mock_sell_manager.monitor_and_update.assert_called_once()

    def test_monitor_all_orders_with_buy_orders(
        self, unified_monitor, mock_sell_manager, mock_orders_repo
    ):
        """Test monitoring with both buy and sell orders"""
        # Setup buy orders
        unified_monitor.active_buy_orders["ORDER123"] = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
            "order_id": "ORDER123",
            "db_order_id": 1,
            "status": "amo",
            "placed_at": datetime.now(),
        }

        mock_sell_manager.monitor_and_update.return_value = {
            "checked": 5,
            "updated": 2,
            "executed": 1,
        }

        # Mock broker orders
        mock_orders_api = Mock()
        mock_orders_api.get_orders.return_value = {"data": []}
        unified_monitor.orders = mock_orders_api

        stats = unified_monitor.monitor_all_orders()

        assert stats["checked"] >= 5  # Sell orders + buy orders
        assert stats["updated"] == 2
        assert stats["executed"] >= 1

    def test_monitor_all_orders_loads_pending_orders(self, unified_monitor, mock_orders_repo):
        """Test that monitor_all_orders loads pending orders if not already loaded"""
        # Create mock order
        mock_order = Mock()
        mock_order.id = 1
        mock_order.broker_order_id = "BROKER123"
        mock_order.order_id = "ORDER123"
        mock_order.symbol = "RELIANCE"
        mock_order.quantity = 10.0
        mock_order.status = Mock(value="amo")
        mock_order.placed_at = datetime.now()

        mock_orders_repo.get_pending_amo_orders.return_value = [mock_order]

        # Mock sell manager
        unified_monitor.sell_manager.monitor_and_update.return_value = {
            "checked": 0,
            "updated": 0,
            "executed": 0,
        }

        # Mock broker orders
        mock_orders_api = Mock()
        mock_orders_api.get_orders.return_value = {"data": []}
        unified_monitor.orders = mock_orders_api

        unified_monitor.monitor_all_orders()

        # Should have loaded the pending order
        assert len(unified_monitor.active_buy_orders) == 1
        mock_orders_repo.get_pending_amo_orders.assert_called_once()

    def test_monitor_all_orders_checks_new_holdings(
        self, unified_monitor, mock_sell_manager, mock_orders_repo
    ):
        """Test that monitor_all_orders calls check_and_place_sell_orders_for_new_holdings"""
        # Mock sell manager
        mock_sell_manager.monitor_and_update.return_value = {
            "checked": 5,
            "updated": 2,
            "executed": 1,
        }

        # Mock check_buy_order_status
        unified_monitor.check_buy_order_status = Mock(
            return_value={
                "checked": 0,
                "executed": 0,
                "rejected": 0,
                "cancelled": 0,
            }
        )

        # Mock check_and_place_sell_orders_for_new_holdings
        unified_monitor.check_and_place_sell_orders_for_new_holdings = Mock(return_value=2)

        # Mock broker orders
        mock_orders_api = Mock()
        mock_orders_api.get_orders.return_value = {"data": []}
        unified_monitor.orders = mock_orders_api

        stats = unified_monitor.monitor_all_orders()

        # Verify new holdings check was called
        unified_monitor.check_and_place_sell_orders_for_new_holdings.assert_called_once()
        # Verify stats include new_holdings_tracked
        assert "new_holdings_tracked" in stats
        assert stats["new_holdings_tracked"] == 2

    def test_check_buy_order_status_error_handling(self, unified_monitor):
        """Test error handling in check_buy_order_status"""
        unified_monitor.active_buy_orders["ORDER123"] = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
            "order_id": "ORDER123",
            "db_order_id": 1,
            "status": "amo",
            "placed_at": datetime.now(),
        }

        # Mock orders API to raise exception
        unified_monitor.orders = Mock()
        unified_monitor.orders.get_orders.side_effect = Exception("API Error")

        # Should handle error gracefully
        stats = unified_monitor.check_buy_order_status()
        assert stats["checked"] == 0  # Should return empty stats on error

    def test_update_buy_order_status_error_handling(self, unified_monitor, mock_orders_repo):
        """Test error handling in _update_buy_order_status"""
        mock_db_order = Mock()
        broker_order = {"orderStatus": "EXECUTED"}

        # Make mark_executed raise exception
        mock_orders_repo.mark_executed.side_effect = Exception("DB Error")

        # Should handle error gracefully
        unified_monitor._update_buy_order_status(mock_db_order, broker_order, "executed")
        # Should not raise exception

    def test_load_pending_buy_orders_error_handling(self, unified_monitor, mock_orders_repo):
        """Test error handling in load_pending_buy_orders"""
        mock_orders_repo.get_pending_amo_orders.side_effect = Exception("DB Error")

        # Should handle error gracefully
        count = unified_monitor.load_pending_buy_orders()
        assert count == 0

    def test_check_buy_order_status_multiple_statuses(self, unified_monitor, mock_orders_repo):
        """Test checking multiple orders with different statuses"""
        # Setup multiple orders
        unified_monitor.active_buy_orders["ORDER1"] = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
            "order_id": "ORDER1",
            "db_order_id": 1,
            "status": "amo",
            "placed_at": datetime.now(),
        }
        unified_monitor.active_buy_orders["ORDER2"] = {
            "symbol": "TCS",
            "quantity": 5.0,
            "order_id": "ORDER2",
            "db_order_id": 2,
            "status": "amo",
            "placed_at": datetime.now(),
        }
        unified_monitor.active_buy_orders["ORDER3"] = {
            "symbol": "INFY",
            "quantity": 3.0,
            "order_id": "ORDER3",
            "db_order_id": 3,
            "status": "amo",
            "placed_at": datetime.now(),
        }

        broker_orders = [
            {"neoOrdNo": "ORDER1", "orderStatus": "EXECUTED", "avgPrc": 2450.50, "qty": 10},
            {"neoOrdNo": "ORDER2", "orderStatus": "REJECTED", "rejRsn": "Insufficient funds"},
            {"neoOrdNo": "ORDER3", "orderStatus": "OPEN"},  # Still open
        ]

        mock_db_orders = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_orders_repo.get.side_effect = mock_db_orders

        stats = unified_monitor.check_buy_order_status(broker_orders=broker_orders)

        assert stats["checked"] == 3
        assert stats["executed"] == 1
        assert stats["rejected"] == 1
        assert stats["cancelled"] == 0
        # ORDER3 should still be in tracking (status is OPEN)
        assert "ORDER3" in unified_monitor.active_buy_orders
        # ORDER1 and ORDER2 should be removed
        assert "ORDER1" not in unified_monitor.active_buy_orders
        assert "ORDER2" not in unified_monitor.active_buy_orders

    # Phase 4: OrderStateManager integration tests
    def test_register_buy_orders_with_state_manager(self, unified_monitor):
        """Test registering buy orders with OrderStateManager"""
        # Setup mock state manager
        mock_state_manager = Mock()
        mock_state_manager.register_buy_order = Mock(return_value=True)
        unified_monitor.sell_manager.state_manager = mock_state_manager

        # Add some buy orders
        unified_monitor.active_buy_orders["ORDER1"] = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
            "order_id": "ORDER1",
            "price": 2450.0,
            "ticker": "RELIANCE.NS",
        }
        unified_monitor.active_buy_orders["ORDER2"] = {
            "symbol": "TCS",
            "quantity": 5.0,
            "order_id": "ORDER2",
            "price": None,  # Market order
            "ticker": "TCS.NS",
        }

        count = unified_monitor.register_buy_orders_with_state_manager()

        assert count == 2
        assert mock_state_manager.register_buy_order.call_count == 2
        mock_state_manager.register_buy_order.assert_any_call(
            symbol="RELIANCE",
            order_id="ORDER1",
            quantity=10.0,
            price=2450.0,
            ticker="RELIANCE.NS",
        )
        mock_state_manager.register_buy_order.assert_any_call(
            symbol="TCS",
            order_id="ORDER2",
            quantity=5.0,
            price=None,
            ticker="TCS.NS",
        )

    def test_register_buy_orders_without_state_manager(self, unified_monitor):
        """Test registering when OrderStateManager is not available"""
        unified_monitor.sell_manager.state_manager = None

        unified_monitor.active_buy_orders["ORDER1"] = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
            "order_id": "ORDER1",
        }

        count = unified_monitor.register_buy_orders_with_state_manager()

        assert count == 0

    def test_register_buy_orders_partial_failure(self, unified_monitor):
        """Test registering when some orders fail"""
        mock_state_manager = Mock()
        mock_state_manager.register_buy_order = Mock(side_effect=[True, False, True])
        unified_monitor.sell_manager.state_manager = mock_state_manager

        unified_monitor.active_buy_orders["ORDER1"] = {
            "symbol": "RELIANCE",
            "quantity": 10.0,
            "order_id": "ORDER1",
        }
        unified_monitor.active_buy_orders["ORDER2"] = {
            "symbol": "TCS",
            "quantity": 5.0,
            "order_id": "ORDER2",
        }
        unified_monitor.active_buy_orders["ORDER3"] = {
            "symbol": "INFY",
            "quantity": 3.0,
            "order_id": "ORDER3",
        }

        count = unified_monitor.register_buy_orders_with_state_manager()

        assert count == 2  # 2 successful, 1 failed
        assert mock_state_manager.register_buy_order.call_count == 3

    def test_handle_buy_order_execution_with_state_manager(self, unified_monitor):
        """Test buy order execution handler with OrderStateManager"""
        mock_state_manager = Mock()
        mock_state_manager.mark_buy_order_executed = Mock(return_value=True)
        unified_monitor.sell_manager.state_manager = mock_state_manager

        order_info = {"symbol": "RELIANCE", "quantity": 10.0}
        broker_order = {"neoOrdNo": "ORDER1", "avgPrc": 2455.50, "qty": 10}

        unified_monitor._handle_buy_order_execution("ORDER1", order_info, broker_order)

        mock_state_manager.mark_buy_order_executed.assert_called_once_with(
            symbol="RELIANCE",
            order_id="ORDER1",
            execution_price=2455.50,
            execution_qty=10,
        )

    def test_handle_buy_order_rejection_with_state_manager(self, unified_monitor):
        """Test buy order rejection handler with OrderStateManager"""
        mock_state_manager = Mock()
        mock_state_manager.remove_buy_order_from_tracking = Mock(return_value=True)
        unified_monitor.sell_manager.state_manager = mock_state_manager

        order_info = {"symbol": "RELIANCE", "quantity": 10.0}
        broker_order = {"neoOrdNo": "ORDER1", "rejRsn": "Insufficient balance"}

        unified_monitor._handle_buy_order_rejection("ORDER1", order_info, broker_order)

        mock_state_manager.remove_buy_order_from_tracking.assert_called_once_with(
            order_id="ORDER1",
            reason="Rejected: Insufficient balance",
        )

    def test_handle_buy_order_cancellation_with_state_manager(self, unified_monitor):
        """Test buy order cancellation handler with OrderStateManager"""
        mock_state_manager = Mock()
        mock_state_manager.remove_buy_order_from_tracking = Mock(return_value=True)
        unified_monitor.sell_manager.state_manager = mock_state_manager

        order_info = {"symbol": "RELIANCE", "quantity": 10.0}
        # Note: OrderFieldExtractor.get_rejection_reason() is used for cancellation
        # and may return None/Unknown if cancellation reason is not in expected format
        broker_order = {"neoOrdNo": "ORDER1", "rejRsn": "User cancelled"}

        unified_monitor._handle_buy_order_cancellation("ORDER1", order_info, broker_order)

        # The reason will be "Cancelled: User cancelled" if extracted, or "Cancelled: Unknown" if not
        mock_state_manager.remove_buy_order_from_tracking.assert_called_once()
        call_args = mock_state_manager.remove_buy_order_from_tracking.call_args
        assert call_args[1]["order_id"] == "ORDER1"
        assert call_args[1]["reason"].startswith("Cancelled:")

    def test_handle_buy_order_execution_without_state_manager(self, unified_monitor):
        """Test buy order execution handler when OrderStateManager is not available"""
        unified_monitor.sell_manager.state_manager = None

        order_info = {"symbol": "RELIANCE", "quantity": 10.0}
        broker_order = {"neoOrdNo": "ORDER1", "avgPrc": 2455.50, "qty": 10}

        # Should not raise exception
        unified_monitor._handle_buy_order_execution("ORDER1", order_info, broker_order)

    # Phase 9: Notification trigger tests
    def test_handle_buy_order_execution_sends_notification(self, unified_monitor):
        """Test that execution handler sends notification (Phase 9)"""
        mock_telegram = Mock()
        mock_telegram.enabled = True
        mock_telegram.notify_order_execution = Mock(return_value=True)
        # Mock preference service to allow notifications
        mock_telegram.preference_service = None  # No preference service = legacy behavior
        mock_telegram._should_send_notification = Mock(return_value=True)  # Always allow
        unified_monitor.telegram_notifier = mock_telegram

        order_info = {"symbol": "RELIANCE", "quantity": 10.0}
        broker_order = {"neoOrdNo": "ORDER1", "avgPrc": 2455.50, "qty": 10}

        unified_monitor._handle_buy_order_execution("ORDER1", order_info, broker_order)

        mock_telegram.notify_order_execution.assert_called_once_with(
            symbol="RELIANCE",
            order_id="ORDER1",
            quantity=10,
            executed_price=2455.50,
            user_id=unified_monitor.user_id,
        )

    def test_handle_buy_order_execution_no_notification_when_disabled(self, unified_monitor):
        """Test that execution handler doesn't send notification when disabled (Phase 9)"""
        mock_telegram = Mock()
        mock_telegram.enabled = False
        mock_telegram.notify_order_execution = Mock()
        unified_monitor.telegram_notifier = mock_telegram

        order_info = {"symbol": "RELIANCE", "quantity": 10.0}
        broker_order = {"neoOrdNo": "ORDER1", "avgPrc": 2455.50, "qty": 10}

        unified_monitor._handle_buy_order_execution("ORDER1", order_info, broker_order)

        mock_telegram.notify_order_execution.assert_not_called()

    def test_handle_buy_order_rejection_sends_notification(self, unified_monitor):
        """Test that rejection handler sends notification with broker reason (Phase 9)"""
        mock_telegram = Mock()
        mock_telegram.enabled = True
        mock_telegram.notify_order_rejection = Mock(return_value=True)
        # Mock preference service to allow notifications
        mock_telegram.preference_service = None  # No preference service = legacy behavior
        mock_telegram._should_send_notification = Mock(return_value=True)  # Always allow
        unified_monitor.telegram_notifier = mock_telegram

        order_info = {"symbol": "RELIANCE", "quantity": 10.0}
        broker_order = {"neoOrdNo": "ORDER1", "rejRsn": "Insufficient balance"}

        unified_monitor._handle_buy_order_rejection("ORDER1", order_info, broker_order)

        mock_telegram.notify_order_rejection.assert_called_once_with(
            symbol="RELIANCE",
            order_id="ORDER1",
            quantity=10,
            rejection_reason="Insufficient balance",
            user_id=unified_monitor.user_id,
        )

    def test_handle_buy_order_rejection_sends_notification_unknown_reason(self, unified_monitor):
        """Test that rejection handler sends notification with Unknown when reason not available (Phase 9)"""
        mock_telegram = Mock()
        mock_telegram.enabled = True
        mock_telegram.notify_order_rejection = Mock(return_value=True)
        # Mock preference service to allow notifications
        mock_telegram.preference_service = None  # No preference service = legacy behavior
        mock_telegram._should_send_notification = Mock(return_value=True)  # Always allow
        unified_monitor.telegram_notifier = mock_telegram

        order_info = {"symbol": "RELIANCE", "quantity": 10.0}
        broker_order = {"neoOrdNo": "ORDER1"}  # No rejection reason

        unified_monitor._handle_buy_order_rejection("ORDER1", order_info, broker_order)

        mock_telegram.notify_order_rejection.assert_called_once_with(
            symbol="RELIANCE",
            order_id="ORDER1",
            quantity=10,
            rejection_reason="Unknown",
            user_id=unified_monitor.user_id,
        )

    def test_handle_buy_order_cancellation_sends_notification(self, unified_monitor):
        """Test that cancellation handler sends notification (Phase 9)"""
        mock_telegram = Mock()
        mock_telegram.enabled = True
        mock_telegram.notify_order_cancelled = Mock(return_value=True)
        # Mock preference service to allow notifications
        mock_telegram.preference_service = None  # No preference service = legacy behavior
        mock_telegram._should_send_notification = Mock(return_value=True)  # Always allow
        unified_monitor.telegram_notifier = mock_telegram

        order_info = {"symbol": "RELIANCE", "quantity": 10.0}
        broker_order = {"neoOrdNo": "ORDER1", "rejRsn": "User cancelled"}

        unified_monitor._handle_buy_order_cancellation("ORDER1", order_info, broker_order)

        mock_telegram.notify_order_cancelled.assert_called_once_with(
            symbol="RELIANCE",
            order_id="ORDER1",
            cancellation_reason="User cancelled",
            user_id=unified_monitor.user_id,
        )

    def test_handle_buy_order_cancellation_no_notification_when_disabled(self, unified_monitor):
        """Test that cancellation handler doesn't send notification when disabled (Phase 9)"""
        mock_telegram = Mock()
        mock_telegram.enabled = False
        mock_telegram.notify_order_cancelled = Mock()
        unified_monitor.telegram_notifier = mock_telegram

        order_info = {"symbol": "RELIANCE", "quantity": 10.0}
        broker_order = {"neoOrdNo": "ORDER1", "rejRsn": "User cancelled"}

        unified_monitor._handle_buy_order_cancellation("ORDER1", order_info, broker_order)

        mock_telegram.notify_order_cancelled.assert_not_called()

    def test_handle_buy_order_execution_handles_notification_error(self, unified_monitor):
        """Test that execution handler handles notification errors gracefully (Phase 9)"""
        mock_telegram = Mock()
        mock_telegram.enabled = True
        mock_telegram.notify_order_execution = Mock(side_effect=Exception("Notification error"))
        unified_monitor.telegram_notifier = mock_telegram

        order_info = {"symbol": "RELIANCE", "quantity": 10.0}
        broker_order = {"neoOrdNo": "ORDER1", "avgPrc": 2455.50, "qty": 10}

        # Should not raise exception
        unified_monitor._handle_buy_order_execution("ORDER1", order_info, broker_order)

    def test_check_and_place_sell_orders_for_new_holdings_no_orders(
        self, unified_monitor, mock_orders_repo
    ):
        """Test checking for new holdings when no orders exist"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        mock_orders_repo.list.return_value = []

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0
        # Verify list was called with correct parameters
        mock_orders_repo.list.assert_called_once()
        call_args = mock_orders_repo.list.call_args
        # Check user_id (can be positional or keyword)
        if call_args.args:
            assert call_args.args[0] == 1  # user_id as positional
        else:
            assert call_args.kwargs.get("user_id") == 1  # user_id as keyword

        # Check status parameter (can be positional or keyword)
        status_arg = None
        if len(call_args.args) > 1:
            status_arg = call_args.args[1]
        elif "status" in call_args.kwargs:
            status_arg = call_args.kwargs["status"]

        # Verify status is ONGOING (may be passed as enum or value)
        if status_arg:
            assert status_arg == DbOrderStatus.ONGOING or (
                hasattr(status_arg, "value") and status_arg.value == "ongoing"
            )

    def test_check_and_place_sell_orders_for_new_holdings_no_db(self, unified_monitor):
        """Test checking for new holdings when DB is not available"""
        unified_monitor.orders_repo = None

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0

    def test_check_and_place_sell_orders_for_new_holdings_no_sell_manager(self, unified_monitor):
        """Test checking for new holdings when sell_manager is not available"""
        unified_monitor.sell_manager = None

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0

    def test_check_and_place_sell_orders_for_new_holdings_executed_today(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test placing sell orders for newly executed buy orders"""
        from src.infrastructure.db.timezone_utils import ist_now

        # Create mock order executed today
        execution_time = ist_now().replace(hour=10, minute=30)  # 10:30 AM today

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.execution_price = 2450.50
        mock_order.execution_qty = 10.0
        mock_order.quantity = 10.0
        mock_order.avg_price = 2450.50
        mock_order.price = 2450.50
        mock_order.execution_time = execution_time
        mock_order.filled_at = execution_time
        mock_order.order_metadata = {"ticker": "RELIANCE.NS"}

        # Mock orders_repo.list to return the order
        mock_orders_repo.list.return_value = [mock_order]

        # Mock sell_manager methods
        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.has_completed_sell_order.return_value = None
        mock_sell_manager.get_current_ema9.return_value = 2500.0  # EMA9 above entry
        mock_sell_manager.place_sell_order.return_value = "SELL123"
        mock_sell_manager._register_order = Mock()
        mock_sell_manager.lowest_ema9 = {}

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 1
        mock_sell_manager.place_sell_order.assert_called_once()
        mock_sell_manager._register_order.assert_called_once()
        assert "RELIANCE" in mock_sell_manager.lowest_ema9

    def test_check_and_place_sell_orders_for_new_holdings_already_has_sell_order(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test skipping holdings that already have sell orders"""
        from src.infrastructure.db.timezone_utils import ist_now

        execution_time = ist_now().replace(hour=10, minute=30)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.execution_price = 2450.50
        mock_order.execution_qty = 10.0
        mock_order.quantity = 10.0
        mock_order.execution_time = execution_time
        mock_order.order_metadata = {"ticker": "RELIANCE.NS"}

        mock_orders_repo.list.return_value = [mock_order]

        # Mock that symbol already has sell order
        mock_sell_manager.get_existing_sell_orders.return_value = {
            "RELIANCE": {"order_id": "EXISTING"}
        }
        mock_sell_manager.active_sell_orders = {}

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0
        mock_sell_manager.place_sell_order.assert_not_called()

    def test_check_and_place_sell_orders_for_new_holdings_ema9_too_low(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test skipping holdings when EMA9 is too low (more than 5% below entry)"""
        from src.infrastructure.db.timezone_utils import ist_now

        execution_time = ist_now().replace(hour=10, minute=30)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.execution_price = 2450.50
        mock_order.execution_qty = 10.0
        mock_order.quantity = 10.0
        mock_order.execution_time = execution_time
        mock_order.order_metadata = {"ticker": "RELIANCE.NS"}

        mock_orders_repo.list.return_value = [mock_order]

        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.has_completed_sell_order.return_value = None
        # EMA9 is 6% below entry (too low)
        mock_sell_manager.get_current_ema9.return_value = 2300.0

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0
        mock_sell_manager.place_sell_order.assert_not_called()

    def test_check_and_place_sell_orders_for_new_holdings_skips_sell_orders(
        self, unified_monitor, mock_orders_repo
    ):
        """Test that sell orders are skipped (only buy orders are processed)"""
        from src.infrastructure.db.timezone_utils import ist_now

        execution_time = ist_now().replace(hour=10, minute=30)

        mock_sell_order = Mock()
        mock_sell_order.side = "sell"
        mock_sell_order.execution_time = execution_time

        mock_orders_repo.list.return_value = [mock_sell_order]

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0

    def test_check_and_place_sell_orders_for_new_holdings_skips_old_orders(
        self, unified_monitor, mock_orders_repo
    ):
        """Test that orders executed before today are skipped"""
        from datetime import timedelta

        from src.infrastructure.db.timezone_utils import ist_now

        # Order executed yesterday
        yesterday = ist_now() - timedelta(days=1)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.execution_time = yesterday
        mock_order.filled_at = yesterday

        mock_orders_repo.list.return_value = [mock_order]

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0

    def test_check_and_place_sell_orders_for_new_holdings_error_handling(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test error handling when placing sell order fails"""
        from src.infrastructure.db.timezone_utils import ist_now

        execution_time = ist_now().replace(hour=10, minute=30)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.execution_price = 2450.50
        mock_order.execution_qty = 10.0
        mock_order.quantity = 10.0
        mock_order.execution_time = execution_time
        mock_order.order_metadata = {"ticker": "RELIANCE.NS"}

        mock_orders_repo.list.return_value = [mock_order]

        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.has_completed_sell_order.return_value = None
        mock_sell_manager.get_current_ema9.return_value = 2500.0
        # Place sell order fails
        mock_sell_manager.place_sell_order.side_effect = Exception("Place order failed")

        # Should handle error gracefully
        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0

    def test_check_and_place_sell_orders_for_new_holdings_no_execution_time_uses_filled_at(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that orders without execution_time use filled_at"""
        from src.infrastructure.db.timezone_utils import ist_now

        filled_at = ist_now().replace(hour=10, minute=30)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.execution_price = 2450.50
        mock_order.execution_qty = 10.0
        mock_order.quantity = 10.0
        mock_order.execution_time = None  # No execution_time
        mock_order.filled_at = filled_at  # Use filled_at instead
        mock_order.order_metadata = {"ticker": "RELIANCE.NS"}

        mock_orders_repo.list.return_value = [mock_order]

        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.has_completed_sell_order.return_value = None
        mock_sell_manager.get_current_ema9.return_value = 2500.0
        mock_sell_manager.place_sell_order.return_value = "SELL123"
        mock_sell_manager._register_order = Mock()
        mock_sell_manager.lowest_ema9 = {}

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 1
        mock_sell_manager.place_sell_order.assert_called_once()

    def test_check_and_place_sell_orders_for_new_holdings_no_ticker_constructs_from_symbol(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that ticker is constructed from symbol if not in metadata"""
        from src.infrastructure.db.timezone_utils import ist_now

        execution_time = ist_now().replace(hour=10, minute=30)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.execution_price = 2450.50
        mock_order.execution_qty = 10.0
        mock_order.quantity = 10.0
        mock_order.execution_time = execution_time
        mock_order.order_metadata = {}  # No ticker in metadata

        mock_orders_repo.list.return_value = [mock_order]

        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.has_completed_sell_order.return_value = None
        mock_sell_manager.get_current_ema9.return_value = 2500.0
        mock_sell_manager.place_sell_order.return_value = "SELL123"
        mock_sell_manager._register_order = Mock()
        mock_sell_manager.lowest_ema9 = {}

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 1
        # Verify ticker was constructed (get_current_ema9 should be called with RELIANCE.NS)
        mock_sell_manager.get_current_ema9.assert_called_once()
        call_args = mock_sell_manager.get_current_ema9.call_args
        assert call_args[0][0] == "RELIANCE.NS"  # Ticker constructed from symbol

    def test_check_and_place_sell_orders_for_new_holdings_invalid_price(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test skipping orders with invalid execution price"""
        from src.infrastructure.db.timezone_utils import ist_now

        execution_time = ist_now().replace(hour=10, minute=30)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.execution_price = None  # Invalid price
        mock_order.execution_qty = 10.0
        mock_order.quantity = 10.0
        mock_order.avg_price = None
        mock_order.price = None
        mock_order.execution_time = execution_time
        mock_order.order_metadata = {"ticker": "RELIANCE.NS"}

        mock_orders_repo.list.return_value = [mock_order]

        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0
        mock_sell_manager.place_sell_order.assert_not_called()

    def test_check_and_place_sell_orders_for_new_holdings_invalid_qty(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test skipping orders with invalid execution quantity"""
        from src.infrastructure.db.timezone_utils import ist_now

        execution_time = ist_now().replace(hour=10, minute=30)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.execution_price = 2450.50
        mock_order.execution_qty = 0  # Invalid qty
        mock_order.quantity = 0
        mock_order.execution_time = execution_time
        mock_order.order_metadata = {"ticker": "RELIANCE.NS"}

        mock_orders_repo.list.return_value = [mock_order]

        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0
        mock_sell_manager.place_sell_order.assert_not_called()

    def test_check_and_place_sell_orders_for_new_holdings_ema9_none(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test skipping orders when EMA9 calculation fails"""
        from src.infrastructure.db.timezone_utils import ist_now

        execution_time = ist_now().replace(hour=10, minute=30)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.execution_price = 2450.50
        mock_order.execution_qty = 10.0
        mock_order.quantity = 10.0
        mock_order.execution_time = execution_time
        mock_order.order_metadata = {"ticker": "RELIANCE.NS"}

        mock_orders_repo.list.return_value = [mock_order]

        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.has_completed_sell_order.return_value = None
        mock_sell_manager.get_current_ema9.return_value = None  # EMA9 calculation fails

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0
        mock_sell_manager.place_sell_order.assert_not_called()

    def test_check_and_place_sell_orders_for_new_holdings_place_order_returns_none(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test handling when place_sell_order returns None"""
        from src.infrastructure.db.timezone_utils import ist_now

        execution_time = ist_now().replace(hour=10, minute=30)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.execution_price = 2450.50
        mock_order.execution_qty = 10.0
        mock_order.quantity = 10.0
        mock_order.execution_time = execution_time
        mock_order.order_metadata = {"ticker": "RELIANCE.NS"}

        mock_orders_repo.list.return_value = [mock_order]

        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.has_completed_sell_order.return_value = None
        mock_sell_manager.get_current_ema9.return_value = 2500.0
        mock_sell_manager.place_sell_order.return_value = None  # Order placement fails
        mock_sell_manager._register_order = Mock()
        mock_sell_manager.lowest_ema9 = {}

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 0
        mock_sell_manager.place_sell_order.assert_called_once()
        mock_sell_manager._register_order.assert_not_called()  # Should not register if order placement fails

    def test_check_and_place_sell_orders_for_new_holdings_multiple_orders_one_fails(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that processing continues when one order fails"""
        from src.infrastructure.db.timezone_utils import ist_now

        execution_time = ist_now().replace(hour=10, minute=30)

        # First order fails
        mock_order1 = Mock()
        mock_order1.side = "buy"
        mock_order1.symbol = "RELIANCE-EQ"
        mock_order1.execution_price = 2450.50
        mock_order1.execution_qty = 10.0
        mock_order1.quantity = 10.0
        mock_order1.execution_time = execution_time
        mock_order1.order_metadata = {"ticker": "RELIANCE.NS"}

        # Second order succeeds
        mock_order2 = Mock()
        mock_order2.side = "buy"
        mock_order2.symbol = "TCS-EQ"
        mock_order2.execution_price = 3200.0
        mock_order2.execution_qty = 5.0
        mock_order2.quantity = 5.0
        mock_order2.execution_time = execution_time
        mock_order2.order_metadata = {"ticker": "TCS.NS"}

        mock_orders_repo.list.return_value = [mock_order1, mock_order2]

        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.has_completed_sell_order.return_value = None
        mock_sell_manager.get_current_ema9.side_effect = [
            None,
            3300.0,
        ]  # First fails, second succeeds
        mock_sell_manager.place_sell_order.return_value = "SELL456"
        mock_sell_manager._register_order = Mock()
        mock_sell_manager.lowest_ema9 = {}

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        # Should have processed both orders, but only placed one
        assert count == 1
        assert mock_sell_manager.get_current_ema9.call_count == 2
        assert mock_sell_manager.place_sell_order.call_count == 1
        assert "TCS" in mock_sell_manager.lowest_ema9

    def test_check_and_place_sell_orders_for_new_holdings_timezone_naive_datetime(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that timezone-naive datetimes are handled correctly without comparison errors"""
        from datetime import datetime

        # Create a timezone-naive datetime (simulating database storage without timezone)
        # This is the scenario that was causing the error
        naive_execution_time = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "RELIANCE-EQ"
        mock_order.execution_price = 2450.50
        mock_order.execution_qty = 10.0
        mock_order.quantity = 10.0
        mock_order.avg_price = 2450.50
        mock_order.price = 2450.50
        # Set timezone-naive datetime (this was causing the error)
        mock_order.execution_time = naive_execution_time
        mock_order.filled_at = None
        mock_order.order_metadata = {"ticker": "RELIANCE.NS"}

        mock_orders_repo.list.return_value = [mock_order]

        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.has_completed_sell_order.return_value = None
        mock_sell_manager.get_current_ema9.return_value = 2500.0
        mock_sell_manager.place_sell_order.return_value = "SELL123"
        mock_sell_manager._register_order = Mock()
        mock_sell_manager.lowest_ema9 = {}

        # Should not raise "can't compare offset-naive and offset-aware datetimes" error
        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        # Should successfully process the order
        assert count == 1
        mock_sell_manager.place_sell_order.assert_called_once()
        mock_sell_manager._register_order.assert_called_once()
        assert "RELIANCE" in mock_sell_manager.lowest_ema9

    def test_check_and_place_sell_orders_for_new_holdings_timezone_naive_filled_at(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that timezone-naive filled_at is handled correctly"""
        from datetime import datetime

        # Create a timezone-naive datetime for filled_at
        naive_filled_at = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)

        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "TCS-EQ"
        mock_order.execution_price = 3200.0
        mock_order.execution_qty = 5.0
        mock_order.quantity = 5.0
        mock_order.avg_price = 3200.0
        mock_order.price = 3200.0
        # No execution_time, but filled_at is timezone-naive
        mock_order.execution_time = None
        mock_order.filled_at = naive_filled_at
        mock_order.order_metadata = {"ticker": "TCS.NS"}

        mock_orders_repo.list.return_value = [mock_order]

        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.has_completed_sell_order.return_value = None
        mock_sell_manager.get_current_ema9.return_value = 3300.0
        mock_sell_manager.place_sell_order.return_value = "SELL456"
        mock_sell_manager._register_order = Mock()
        mock_sell_manager.lowest_ema9 = {}

        # Should not raise datetime comparison error
        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        assert count == 1
        mock_sell_manager.place_sell_order.assert_called_once()
        assert "TCS" in mock_sell_manager.lowest_ema9
