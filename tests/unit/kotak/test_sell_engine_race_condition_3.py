"""
Tests for Race Condition #3: Reentry During Sell Order Update

Tests verify that:
1. run_at_market_open() re-reads position quantity before updating sell order
2. Sell order is updated with latest quantity even if reentry executes during processing
3. Locked read prevents stale quantity updates
"""

from unittest.mock import MagicMock

import pytest

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from src.infrastructure.db.models import Positions
from src.infrastructure.db.timezone_utils import ist_now


class TestReentryDuringSellOrderUpdate:
    """Test race condition fix for reentry during sell order update"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth"""
        auth = MagicMock()
        return auth

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository"""
        repo = MagicMock()
        return repo

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_positions_repo):
        """Create SellOrderManager with mocked dependencies"""
        manager = SellOrderManager(
            auth=mock_auth,
            positions_repo=mock_positions_repo,
            user_id=1,
        )
        manager.get_existing_sell_orders = MagicMock(return_value={})
        manager.get_current_ema9 = MagicMock(return_value=100.0)
        manager.orders = MagicMock()
        manager.orders.place_order = MagicMock(return_value={"order_id": "TEST123"})
        manager.orders.get_orders = MagicMock(
            return_value={"data": []}
        )  # Mock for run_at_market_open optimization
        manager._register_order = MagicMock()
        return manager

    def test_re_reads_position_before_updating_sell_order(self, sell_manager, mock_positions_repo):
        """Test that position is re-read with lock before updating sell order"""
        # Initial position read (stale quantity)
        initial_position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=100.0,
            avg_price=100.0,
            opened_at=ist_now(),
        )

        # Updated position (after reentry executed)
        updated_position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=110.0,  # Reentry added 10 shares
            avg_price=105.0,
            opened_at=ist_now(),
        )

        # Mock get_open_positions to return initial quantity
        sell_manager.get_open_positions = MagicMock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 100.0,  # Stale quantity
                    "entry_price": 100.0,
                }
            ]
        )

        # Mock existing sell order with LOWER quantity (triggers update path)
        sell_manager.get_existing_sell_orders = MagicMock(
            return_value={
                "RELIANCE": {
                    "order_id": "SELL123",
                    "qty": 90,  # Existing order has LESS quantity (triggers qty > existing_qty)
                    "price": 100.0,
                }
            }
        )

        # Mock re-read with updated quantity (simulating reentry executed)
        mock_positions_repo.get_by_symbol_for_update = MagicMock(return_value=updated_position)
        sell_manager.update_sell_order = MagicMock(return_value=True)

        # Run at market open
        orders_placed = sell_manager.run_at_market_open()

        # Verify position was re-read with lock
        mock_positions_repo.get_by_symbol_for_update.assert_called_once_with(1, "RELIANCE")

        # Verify sell order was updated with latest quantity (110, not 100)
        sell_manager.update_sell_order.assert_called_once()
        call_args = sell_manager.update_sell_order.call_args
        assert call_args[1]["qty"] == 110, "Should use latest quantity from re-read"

    def test_uses_initial_quantity_if_re_read_fails(self, sell_manager, mock_positions_repo):
        """Test that initial quantity is used if re-read fails"""
        # Initial position read
        sell_manager.get_open_positions = MagicMock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 100.0,
                    "entry_price": 100.0,
                }
            ]
        )

        # Mock existing sell order with LOWER quantity (triggers update path)
        sell_manager.get_existing_sell_orders = MagicMock(
            return_value={
                "RELIANCE": {
                    "order_id": "SELL123",
                    "qty": 90,  # Existing order has LESS quantity (triggers qty > existing_qty)
                    "price": 100.0,
                }
            }
        )

        # Mock re-read to fail
        mock_positions_repo.get_by_symbol_for_update = MagicMock(
            side_effect=Exception("Database error")
        )
        sell_manager.update_sell_order = MagicMock(return_value=True)

        # Run at market open
        orders_placed = sell_manager.run_at_market_open()

        # Verify re-read was attempted
        mock_positions_repo.get_by_symbol_for_update.assert_called_once()

        # Verify sell order was updated with initial quantity (fallback)
        sell_manager.update_sell_order.assert_called_once()
        call_args = sell_manager.update_sell_order.call_args
        assert call_args[1]["qty"] == 100, "Should use initial quantity as fallback"

    def test_no_re_read_if_quantity_not_increased(self, sell_manager, mock_positions_repo):
        """Test that re-read is not performed if quantity hasn't increased"""
        # Initial position read
        sell_manager.get_open_positions = MagicMock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 100.0,
                    "entry_price": 100.0,
                }
            ]
        )

        # Mock existing sell order with same quantity
        sell_manager.get_existing_sell_orders = MagicMock(
            return_value={
                "RELIANCE": {
                    "order_id": "SELL123",
                    "qty": 100,  # Same quantity
                    "price": 100.0,
                }
            }
        )

        # Run at market open
        orders_placed = sell_manager.run_at_market_open()

        # Verify re-read was NOT called (quantity didn't increase)
        mock_positions_repo.get_by_symbol_for_update.assert_not_called()

    def test_re_read_uses_locked_read(self, sell_manager, mock_positions_repo):
        """Test that re-read uses get_by_symbol_for_update (locked read)"""
        # Setup
        updated_position = Positions(
            user_id=1,
            symbol="RELIANCE",
            quantity=110.0,
            avg_price=105.0,
            opened_at=ist_now(),
        )

        sell_manager.get_open_positions = MagicMock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 100.0,
                    "entry_price": 100.0,
                }
            ]
        )

        sell_manager.get_existing_sell_orders = MagicMock(
            return_value={
                "RELIANCE": {
                    "order_id": "SELL123",
                    "qty": 90,  # Existing order has LESS quantity (triggers qty > existing_qty)
                    "price": 100.0,
                }
            }
        )

        mock_positions_repo.get_by_symbol_for_update = MagicMock(return_value=updated_position)
        sell_manager.update_sell_order = MagicMock(return_value=True)

        # Run at market open
        sell_manager.run_at_market_open()

        # Verify locked read was used (not regular get_by_symbol)
        # Expected 2 calls: one for re-read before update, one for _reconcile_single_symbol()
        assert mock_positions_repo.get_by_symbol_for_update.call_count == 2
        # Verify regular get_by_symbol was NOT called
        if hasattr(mock_positions_repo, "get_by_symbol"):
            mock_positions_repo.get_by_symbol.assert_not_called()
