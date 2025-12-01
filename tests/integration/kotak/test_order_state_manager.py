#!/usr/bin/env python3
"""
Tests for OrderStateManager unified state management
"""

import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.order_state_manager import OrderStateManager  # noqa: E402


class TestOrderStateManager:
    """Test OrderStateManager unified state management"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def history_path(self, temp_dir):
        """Create temporary history file"""
        path = os.path.join(temp_dir, "trades_history.json")
        with open(path, "w") as f:
            json.dump({"trades": [], "failed_orders": []}, f)
        return path

    @pytest.fixture
    def state_manager(self, history_path, temp_dir):
        """Create OrderStateManager instance"""
        return OrderStateManager(history_path=history_path, data_dir=temp_dir)

    def test_register_sell_order(self, state_manager):
        """Test registering a sell order"""
        result = state_manager.register_sell_order(
            symbol="RELIANCE-EQ",
            order_id="12345",
            target_price=2500.0,
            qty=10,
            ticker="RELIANCE.NS",
        )

        assert result is True
        assert "RELIANCE" in state_manager.active_sell_orders
        assert state_manager.active_sell_orders["RELIANCE"]["order_id"] == "12345"
        assert state_manager.active_sell_orders["RELIANCE"]["target_price"] == 2500.0
        assert state_manager.active_sell_orders["RELIANCE"]["qty"] == 10

    def test_update_sell_order_price(self, state_manager):
        """Test updating sell order price"""
        state_manager.register_sell_order(
            symbol="RELIANCE", order_id="12345", target_price=2500.0, qty=10
        )

        result = state_manager.update_sell_order_price("RELIANCE", 2550.0)

        assert result is True
        assert state_manager.active_sell_orders["RELIANCE"]["target_price"] == 2550.0

    def test_get_active_sell_orders(self, state_manager):
        """Test getting all active sell orders"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)
        state_manager.register_sell_order("DALBHARAT", "67890", 2100.0, 5)

        orders = state_manager.get_active_sell_orders()

        assert len(orders) == 2
        assert "RELIANCE" in orders
        assert "DALBHARAT" in orders

    def test_get_active_order(self, state_manager):
        """Test getting a specific active order"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)

        order = state_manager.get_active_order("RELIANCE")

        assert order is not None
        assert order["order_id"] == "12345"

        # Test with non-existent symbol
        order = state_manager.get_active_order("NONEXISTENT")
        assert order is None

    def test_mark_order_executed(self, state_manager):
        """Test marking order as executed"""
        state_manager.register_sell_order(
            symbol="RELIANCE", order_id="12345", target_price=2500.0, qty=10, ticker="RELIANCE.NS"
        )

        result = state_manager.mark_order_executed(
            symbol="RELIANCE", order_id="12345", execution_price=2505.0, execution_qty=10
        )

        assert result is True
        assert "RELIANCE" not in state_manager.active_sell_orders

    def test_remove_from_tracking(self, state_manager):
        """Test removing order from tracking"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)

        result = state_manager.remove_from_tracking("RELIANCE", reason="Rejected")

        assert result is True
        assert "RELIANCE" not in state_manager.active_sell_orders

    def test_remove_from_tracking_not_found(self, state_manager):
        """Test removing non-existent order"""
        result = state_manager.remove_from_tracking("NONEXISTENT")
        assert result is False

    def test_sync_with_broker_executed(self, state_manager):
        """Test syncing with broker when order is executed"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)

        broker_orders = [
            {
                "neoOrdNo": "12345",
                "trdSym": "RELIANCE-EQ",
                "orderStatus": "complete",
                "transactionType": "SELL",
                "avgPrc": 2505.0,
                "qty": 10,
            }
        ]

        mock_orders_api = Mock()
        stats = state_manager.sync_with_broker(mock_orders_api, broker_orders=broker_orders)

        assert stats["checked"] == 1
        assert stats["executed"] == 1
        assert "RELIANCE" not in state_manager.active_sell_orders

    def test_sync_with_broker_rejected(self, state_manager):
        """Test syncing with broker when order is rejected"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)

        broker_orders = [
            {
                "neoOrdNo": "12345",
                "trdSym": "RELIANCE-EQ",
                "orderStatus": "rejected",
                "transactionType": "SELL",
                "rejectionReason": "Insufficient balance",
            }
        ]

        mock_orders_api = Mock()
        stats = state_manager.sync_with_broker(mock_orders_api, broker_orders=broker_orders)

        assert stats["checked"] == 1
        assert stats["rejected"] == 1
        assert "RELIANCE" not in state_manager.active_sell_orders

    def test_sync_with_broker_cancelled(self, state_manager):
        """Test syncing with broker when order is cancelled"""
        state_manager.register_sell_order("RELIANCE", "12345", 2500.0, 10)

        broker_orders = [
            {
                "neoOrdNo": "12345",
                "trdSym": "RELIANCE-EQ",
                "orderStatus": "cancelled",
                "transactionType": "SELL",
            }
        ]

        mock_orders_api = Mock()
        stats = state_manager.sync_with_broker(mock_orders_api, broker_orders=broker_orders)

        assert stats["checked"] == 1
        assert stats["cancelled"] == 1
        assert "RELIANCE" not in state_manager.active_sell_orders

    def test_get_pending_orders(self, state_manager):
        """Test getting pending orders"""
        state_manager.register_sell_order(
            symbol="RELIANCE", order_id="12345", target_price=2500.0, qty=10, ticker="RELIANCE.NS"
        )

        pending = state_manager.get_pending_orders()

        assert len(pending) >= 1
        assert any(o["order_id"] == "12345" for o in pending)

    def test_thread_safety(self, state_manager):
        """Test thread safety of operations"""
        results = []

        def register_order(symbol, order_id):
            result = state_manager.register_sell_order(symbol, order_id, 2500.0, 10)
            results.append(result)

        threads = []
        for i in range(10):
            thread = threading.Thread(target=register_order, args=(f"SYMBOL{i}", f"ORDER{i}"))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All operations should succeed
        assert all(results)
        assert len(state_manager.active_sell_orders) == 10

    def test_get_trade_history(self, state_manager, history_path):
        """Test getting trade history"""
        history = state_manager.get_trade_history()

        assert isinstance(history, dict)
        assert "trades" in history
        assert "failed_orders" in history

    def test_register_sell_order_duplicate_prevention(self, state_manager):
        """Test that duplicate registration is prevented"""
        # Register order first time
        result1 = state_manager.register_sell_order(
            symbol="DALBHARAT-EQ",
            order_id="251106000008974",
            target_price=2095.53,
            qty=233,
            ticker="DALBHARAT.NS",
        )

        assert result1 is True
        assert "DALBHARAT" in state_manager.active_sell_orders
        assert state_manager.active_sell_orders["DALBHARAT"]["order_id"] == "251106000008974"
        assert state_manager.active_sell_orders["DALBHARAT"]["target_price"] == 2095.53

        # Get initial pending orders count
        initial_pending = state_manager.get_pending_orders()
        initial_count = len([o for o in initial_pending if o["order_id"] == "251106000008974"])

        # Try to register same order again with same price
        result2 = state_manager.register_sell_order(
            symbol="DALBHARAT-EQ",
            order_id="251106000008974",
            target_price=2095.53,
            qty=233,
            ticker="DALBHARAT.NS",
        )

        # Should return True (order already tracked) but not create duplicate
        assert result2 is True

        # Verify no duplicate in active orders
        assert len(state_manager.active_sell_orders) == 1
        assert state_manager.active_sell_orders["DALBHARAT"]["order_id"] == "251106000008974"

        # Verify no duplicate in pending orders
        final_pending = state_manager.get_pending_orders()
        final_count = len([o for o in final_pending if o["order_id"] == "251106000008974"])
        assert final_count == initial_count, "Duplicate order should not be added to pending orders"

    def test_register_sell_order_duplicate_with_zero_price(self, state_manager):
        """Test that duplicate with zero price doesn't overwrite correct price"""
        # Register order with correct price
        result1 = state_manager.register_sell_order(
            symbol="DALBHARAT-EQ",
            order_id="251106000008974",
            target_price=2095.53,
            qty=233,
            ticker="DALBHARAT.NS",
        )

        assert result1 is True
        assert state_manager.active_sell_orders["DALBHARAT"]["target_price"] == 2095.53

        # Try to register same order with zero price (simulating the bug scenario)
        result2 = state_manager.register_sell_order(
            symbol="DALBHARAT-EQ",
            order_id="251106000008974",
            target_price=0.0,
            qty=233,
            ticker="DALBHARAT.NS",
        )

        # Should return True but NOT update price to 0.0
        assert result2 is True
        # Price should remain unchanged (0.0 is not > 0, so update condition fails)
        assert state_manager.active_sell_orders["DALBHARAT"]["target_price"] == 2095.53

    def test_register_sell_order_price_update(self, state_manager):
        """Test that price update works when order already exists"""
        # Register order with initial price
        state_manager.register_sell_order(
            symbol="RELIANCE-EQ",
            order_id="12345",
            target_price=2500.0,
            qty=10,
            ticker="RELIANCE.NS",
        )

        assert state_manager.active_sell_orders["RELIANCE"]["target_price"] == 2500.0

        # Register same order with updated price
        result = state_manager.register_sell_order(
            symbol="RELIANCE-EQ",
            order_id="12345",
            target_price=2550.0,
            qty=10,
            ticker="RELIANCE.NS",
        )

        # Should update price
        assert result is True
        assert state_manager.active_sell_orders["RELIANCE"]["target_price"] == 2550.0
        assert "last_updated" in state_manager.active_sell_orders["RELIANCE"]

    # Phase 3: Buy order tests
    def test_register_buy_order(self, state_manager):
        """Test registering a buy order"""
        result = state_manager.register_buy_order(
            symbol="RELIANCE-EQ",
            order_id="BUY12345",
            quantity=10.0,
            price=2450.0,
            ticker="RELIANCE.NS",
        )

        assert result is True
        assert "BUY12345" in state_manager.active_buy_orders
        assert state_manager.active_buy_orders["BUY12345"]["symbol"] == "RELIANCE"
        assert state_manager.active_buy_orders["BUY12345"]["quantity"] == 10.0
        assert state_manager.active_buy_orders["BUY12345"]["price"] == 2450.0

    def test_register_buy_order_market(self, state_manager):
        """Test registering a market buy order (no price)"""
        result = state_manager.register_buy_order(
            symbol="TCS", order_id="BUY67890", quantity=5.0, ticker="TCS.NS"
        )

        assert result is True
        assert "BUY67890" in state_manager.active_buy_orders
        assert state_manager.active_buy_orders["BUY67890"]["price"] is None

    def test_register_buy_order_duplicate(self, state_manager):
        """Test that duplicate buy order registration is prevented"""
        result1 = state_manager.register_buy_order(
            symbol="RELIANCE", order_id="BUY12345", quantity=10.0, price=2450.0
        )

        assert result1 is True

        # Try to register same order again
        result2 = state_manager.register_buy_order(
            symbol="RELIANCE", order_id="BUY12345", quantity=10.0, price=2450.0
        )

        assert result2 is True
        assert len(state_manager.active_buy_orders) == 1

    def test_get_active_buy_orders(self, state_manager):
        """Test getting all active buy orders"""
        state_manager.register_buy_order("RELIANCE", "BUY1", 10.0, 2450.0)
        state_manager.register_buy_order("TCS", "BUY2", 5.0, 3200.0)

        orders = state_manager.get_active_buy_orders()

        assert len(orders) == 2
        assert "BUY1" in orders
        assert "BUY2" in orders

    def test_get_active_buy_order(self, state_manager):
        """Test getting a specific active buy order"""
        state_manager.register_buy_order("RELIANCE", "BUY12345", 10.0, 2450.0)

        order = state_manager.get_active_buy_order("BUY12345")

        assert order is not None
        assert order["symbol"] == "RELIANCE"
        assert order["quantity"] == 10.0

        # Test with non-existent order_id
        order = state_manager.get_active_buy_order("NONEXISTENT")
        assert order is None

    def test_mark_buy_order_executed(self, state_manager, history_path):
        """Test marking buy order as executed and adding to trade history"""
        state_manager.register_buy_order(
            symbol="RELIANCE",
            order_id="BUY12345",
            quantity=10.0,
            price=2450.0,
            ticker="RELIANCE.NS",
        )

        result = state_manager.mark_buy_order_executed(
            symbol="RELIANCE", order_id="BUY12345", execution_price=2455.50, execution_qty=10.0
        )

        assert result is True
        assert "BUY12345" not in state_manager.active_buy_orders

        # Check that trade was added to history
        history = state_manager.get_trade_history()
        trades = history.get("trades", [])
        assert len(trades) == 1
        assert trades[0]["symbol"] == "RELIANCE"
        assert trades[0]["entry_price"] == 2455.50
        assert trades[0]["qty"] == 10.0
        assert trades[0]["status"] == "open"
        assert trades[0]["buy_order_id"] == "BUY12345"

    def test_mark_buy_order_executed_defaults_qty(self, state_manager, history_path):
        """Test that execution qty defaults to order quantity"""
        state_manager.register_buy_order(
            symbol="TCS", order_id="BUY67890", quantity=5.0, price=3200.0
        )

        result = state_manager.mark_buy_order_executed(
            symbol="TCS",
            order_id="BUY67890",
            execution_price=3205.0,
            # execution_qty not provided
        )

        assert result is True
        history = state_manager.get_trade_history()
        trades = history.get("trades", [])
        assert trades[0]["qty"] == 5.0

    def test_remove_buy_order_from_tracking(self, state_manager):
        """Test removing buy order from tracking"""
        state_manager.register_buy_order("RELIANCE", "BUY12345", 10.0, 2450.0)

        result = state_manager.remove_buy_order_from_tracking("BUY12345", reason="Rejected")

        assert result is True
        assert "BUY12345" not in state_manager.active_buy_orders

    def test_remove_buy_order_from_tracking_not_found(self, state_manager):
        """Test removing non-existent buy order"""
        result = state_manager.remove_buy_order_from_tracking("NONEXISTENT")
        assert result is False

    def test_sync_with_broker_buy_order_executed(self, state_manager, history_path):
        """Test syncing with broker when buy order is executed"""
        state_manager.register_buy_order("RELIANCE", "BUY12345", 10.0, 2450.0)

        broker_orders = [
            {
                "neoOrdNo": "BUY12345",
                "trdSym": "RELIANCE-EQ",
                "orderStatus": "complete",
                "transactionType": "BUY",
                "avgPrc": 2455.50,
                "qty": 10,
            }
        ]

        mock_orders_api = Mock()
        stats = state_manager.sync_with_broker(mock_orders_api, broker_orders=broker_orders)

        assert stats["buy_checked"] == 1
        assert stats["buy_executed"] == 1
        assert "BUY12345" not in state_manager.active_buy_orders

        # Check trade history
        history = state_manager.get_trade_history()
        trades = history.get("trades", [])
        assert len(trades) == 1

    def test_sync_with_broker_buy_order_rejected(self, state_manager):
        """Test syncing with broker when buy order is rejected"""
        state_manager.register_buy_order("RELIANCE", "BUY12345", 10.0, 2450.0)

        broker_orders = [
            {
                "neoOrdNo": "BUY12345",
                "trdSym": "RELIANCE-EQ",
                "orderStatus": "rejected",
                "transactionType": "BUY",
                "rejRsn": "Insufficient balance",
            }
        ]

        mock_orders_api = Mock()
        stats = state_manager.sync_with_broker(mock_orders_api, broker_orders=broker_orders)

        assert stats["buy_checked"] == 1
        assert stats["buy_rejected"] == 1
        assert "BUY12345" not in state_manager.active_buy_orders

    def test_sync_with_broker_buy_order_cancelled(self, state_manager):
        """Test syncing with broker when buy order is cancelled"""
        state_manager.register_buy_order("RELIANCE", "BUY12345", 10.0, 2450.0)

        broker_orders = [
            {
                "neoOrdNo": "BUY12345",
                "trdSym": "RELIANCE-EQ",
                "orderStatus": "cancelled",
                "transactionType": "BUY",
            }
        ]

        mock_orders_api = Mock()
        stats = state_manager.sync_with_broker(mock_orders_api, broker_orders=broker_orders)

        assert stats["buy_checked"] == 1
        assert stats["buy_cancelled"] == 1
        assert "BUY12345" not in state_manager.active_buy_orders

    def test_sync_with_broker_both_buy_and_sell(self, state_manager, history_path):
        """Test syncing both buy and sell orders"""
        # Register both types
        state_manager.register_sell_order("RELIANCE", "SELL123", 2500.0, 10)
        state_manager.register_buy_order("TCS", "BUY456", 5.0, 3200.0)

        broker_orders = [
            {
                "neoOrdNo": "SELL123",
                "trdSym": "RELIANCE-EQ",
                "orderStatus": "complete",
                "transactionType": "SELL",
                "avgPrc": 2505.0,
                "qty": 10,
            },
            {
                "neoOrdNo": "BUY456",
                "trdSym": "TCS-EQ",
                "orderStatus": "complete",
                "transactionType": "BUY",
                "avgPrc": 3205.0,
                "qty": 5,
            },
        ]

        mock_orders_api = Mock()
        stats = state_manager.sync_with_broker(mock_orders_api, broker_orders=broker_orders)

        assert stats["checked"] == 1
        assert stats["executed"] == 1
        assert stats["buy_checked"] == 1
        assert stats["buy_executed"] == 1
        assert "RELIANCE" not in state_manager.active_sell_orders
        assert "BUY456" not in state_manager.active_buy_orders

    def test_sync_with_broker_buy_order_not_found(self, state_manager):
        """Test when buy order is not found in broker orders"""
        state_manager.register_buy_order("RELIANCE", "BUY12345", 10.0, 2450.0)

        mock_orders_api = Mock()
        stats = state_manager.sync_with_broker(mock_orders_api, broker_orders=[])

        assert stats["buy_checked"] == 1
        assert stats["buy_executed"] == 0
        # Order should remain in tracking if not found
        assert "BUY12345" in state_manager.active_buy_orders
