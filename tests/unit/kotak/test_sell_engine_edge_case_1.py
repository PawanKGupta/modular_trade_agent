"""
Tests for Edge Case #1: Sell Order Quantity Not Updated After Reentry

Tests that sell orders are updated when:
1. Reentry executes during market hours (immediate update)
2. run_at_market_open() runs next day and finds quantity mismatch (next-day update)
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager


class TestSellOrderUpdateAfterReentry:
    """Test Edge Case #1: Sell order quantity updated after reentry"""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock()
        auth.client = Mock()
        return auth

    @pytest.fixture
    def sell_manager(self, mock_auth):
        """Create SellOrderManager instance"""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.orders = Mock()
            manager.orders.modify_order = Mock(return_value={"stat": "Ok"})
            manager.orders.cancel_order = Mock(return_value={"stat": "Ok"})
            manager.orders.place_limit_sell = Mock(return_value={"nOrdNo": "NEW123"})
            manager.active_sell_orders = {}
            manager.lowest_ema9 = {}
            return manager

    def test_run_at_market_open_updates_existing_order_when_quantity_increases(self, sell_manager):
        """Test that run_at_market_open() updates existing sell order when quantity increases"""
        # Setup: Existing sell order with 35 shares
        existing_order_id = "SELL123"
        existing_qty = 35
        existing_price = 9.50

        # Mock get_existing_sell_orders to return existing order
        sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE": {
                    "order_id": existing_order_id,
                    "qty": existing_qty,
                    "price": existing_price,
                }
            }
        )

        # Mock get_open_positions to return position with increased quantity (45 shares - reentry happened)
        sell_manager.get_open_positions = Mock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 45,  # Increased from 35 (reentry)
                    "entry_price": 9.00,
                    "placed_symbol": "RELIANCE-EQ",
                }
            ]
        )

        # Mock has_completed_sell_order to return None (no completed orders)
        sell_manager.has_completed_sell_order = Mock(return_value=None)

        # Mock get_current_ema9
        sell_manager.get_current_ema9 = Mock(return_value=9.50)

        # Mock _register_order
        sell_manager._register_order = Mock()

        # Call run_at_market_open()
        orders_placed = sell_manager.run_at_market_open()

        # Verify update_sell_order was called with new quantity
        sell_manager.orders.modify_order.assert_called_once_with(
            order_id=existing_order_id,
            quantity=45,  # Updated quantity
            price=existing_price,  # Same price
            order_type="L",
        )

        # Verify order was tracked with new quantity
        sell_manager._register_order.assert_called_once()
        call_args = sell_manager._register_order.call_args
        assert call_args[1]["qty"] == 45
        assert call_args[1]["order_id"] == existing_order_id

        # Verify orders_placed count
        assert orders_placed == 1

    def test_run_at_market_open_skips_when_quantity_same(self, sell_manager):
        """Test that run_at_market_open() skips when quantity is same"""
        existing_order_id = "SELL123"
        existing_qty = 35
        existing_price = 9.50

        sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE": {
                    "order_id": existing_order_id,
                    "qty": existing_qty,
                    "price": existing_price,
                }
            }
        )

        sell_manager.get_open_positions = Mock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 35,  # Same quantity
                    "entry_price": 9.00,
                    "placed_symbol": "RELIANCE-EQ",
                }
            ]
        )

        sell_manager.has_completed_sell_order = Mock(return_value=None)
        sell_manager._register_order = Mock()

        orders_placed = sell_manager.run_at_market_open()

        # Verify modify_order was NOT called (quantity same)
        sell_manager.orders.modify_order.assert_not_called()

        # Verify order was tracked (but not updated)
        sell_manager._register_order.assert_called_once()
        call_args = sell_manager._register_order.call_args
        assert call_args[1]["qty"] == 35  # Same quantity

        assert orders_placed == 1

    def test_run_at_market_open_handles_quantity_decrease(self, sell_manager):
        """Test that run_at_market_open() handles quantity decrease gracefully"""
        existing_order_id = "SELL123"
        existing_qty = 45
        existing_price = 9.50

        sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE": {
                    "order_id": existing_order_id,
                    "qty": existing_qty,
                    "price": existing_price,
                }
            }
        )

        sell_manager.get_open_positions = Mock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 35,  # Decreased (partial sell?)
                    "entry_price": 9.00,
                    "placed_symbol": "RELIANCE-EQ",
                }
            ]
        )

        sell_manager.has_completed_sell_order = Mock(return_value=None)
        sell_manager._register_order = Mock()

        orders_placed = sell_manager.run_at_market_open()

        # Verify modify_order was NOT called (quantity decreased - might be partial sell)
        sell_manager.orders.modify_order.assert_not_called()

        # Verify order was tracked with existing quantity (not decreased)
        sell_manager._register_order.assert_called_once()
        call_args = sell_manager._register_order.call_args
        assert call_args[1]["qty"] == 45  # Keep existing quantity

        assert orders_placed == 1

    def test_run_at_market_open_handles_update_failure(self, sell_manager):
        """Test that run_at_market_open() handles update failure gracefully"""
        existing_order_id = "SELL123"
        existing_qty = 35
        existing_price = 9.50

        sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE": {
                    "order_id": existing_order_id,
                    "qty": existing_qty,
                    "price": existing_price,
                }
            }
        )

        sell_manager.get_open_positions = Mock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 45,  # Increased
                    "entry_price": 9.00,
                    "placed_symbol": "RELIANCE-EQ",
                }
            ]
        )

        sell_manager.has_completed_sell_order = Mock(return_value=None)
        sell_manager.update_sell_order = Mock(return_value=False)  # Update fails
        sell_manager._register_order = Mock()

        orders_placed = sell_manager.run_at_market_open()

        # Verify update_sell_order was called
        sell_manager.update_sell_order.assert_called_once()

        # When update fails, orders_placed is 0 (not counted as placed/updated)
        # The order will be updated next day by run_at_market_open()
        assert orders_placed == 0
