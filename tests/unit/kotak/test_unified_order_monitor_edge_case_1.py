"""
Tests for Edge Case #1: Sell Order Quantity Updated When Reentry Executes

Tests that unified_order_monitor updates sell orders immediately when reentry executes.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor


class TestUnifiedOrderMonitorSellOrderUpdateOnReentry:
    """Test that UnifiedOrderMonitor updates sell orders when reentry executes"""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock()
        auth.client = Mock()
        return auth

    @pytest.fixture
    def mock_sell_manager(self, mock_auth):
        """Create mock SellOrderManager"""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.orders = Mock()
            manager.update_sell_order = Mock(return_value=True)
            manager.get_existing_sell_orders = Mock(return_value={})
            manager.active_sell_orders = {}
            return manager

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session"""
        return Mock()

    @pytest.fixture
    def unified_monitor(self, mock_sell_manager, mock_db_session):
        """Create UnifiedOrderMonitor instance"""
        with (
            patch("modules.kotak_neo_auto_trader.unified_order_monitor.OrdersRepository"),
            patch("modules.kotak_neo_auto_trader.unified_order_monitor.PositionsRepository"),
        ):
            monitor = UnifiedOrderMonitor(
                sell_order_manager=mock_sell_manager,
                db_session=mock_db_session,
                user_id=1,
            )
            return monitor

    @pytest.fixture
    def mock_positions_repo(self, unified_monitor):
        """Mock positions repository"""
        positions_repo = Mock()
        unified_monitor.positions_repo = positions_repo
        return positions_repo

    @pytest.fixture
    def mock_orders_repo(self, unified_monitor):
        """Mock orders repository"""
        orders_repo = Mock()
        unified_monitor.orders_repo = orders_repo
        return orders_repo

    def test_create_position_updates_sell_order_when_reentry_executes(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """Test that _create_position_from_executed_order updates sell order when reentry executes"""
        # Setup: Existing position with 35 shares
        existing_position = Mock()
        existing_position.quantity = 35.0
        existing_position.avg_price = 9.00
        existing_position.opened_at = Mock()
        existing_position.entry_rsi = 25.0
        existing_position.closed_at = None  # Position is open
        existing_position.reentry_count = 0
        existing_position.reentries = []
        existing_position.last_reentry_price = None

        mock_positions_repo.get_by_symbol.return_value = existing_position

        # Mock order info
        order_info = {
            "symbol": "RELIANCE-EQ",
            "db_order_id": 1,
        }

        # Mock DB order with metadata
        db_order = Mock()
        db_order.order_metadata = {"entry_rsi": 18.0}  # Reentry at RSI 18
        db_order.filled_at = None
        db_order.execution_time = None
        mock_orders_repo.get.return_value = db_order

        # Mock existing sell order (35 shares)
        mock_sell_manager.get_existing_sell_orders.return_value = {
            "RELIANCE": {
                "order_id": "SELL123",
                "qty": 35,
                "price": 9.50,
            }
        }

        # Call _create_position_from_executed_order with reentry (10 shares)
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER456",
            order_info=order_info,
            execution_price=9.50,
            execution_qty=10.0,  # Reentry quantity
        )

        # Verify position was updated
        mock_positions_repo.upsert.assert_called_once()
        call_args = mock_positions_repo.upsert.call_args
        assert call_args[1]["quantity"] == 45.0  # 35 + 10

        # Verify sell order was updated
        mock_sell_manager.update_sell_order.assert_called_once_with(
            order_id="SELL123",
            symbol="RELIANCE",
            qty=45,  # Updated quantity
            new_price=9.50,  # Same price
        )

    def test_create_position_does_not_update_sell_order_when_new_position(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """Test that _create_position_from_executed_order does not update sell order for new positions"""
        # No existing position (new entry)
        mock_positions_repo.get_by_symbol.return_value = None

        order_info = {
            "symbol": "RELIANCE-EQ",
            "db_order_id": 1,
        }

        db_order = Mock()
        db_order.order_metadata = {"entry_rsi": 25.0}
        db_order.filled_at = None
        db_order.execution_time = None
        mock_orders_repo.get.return_value = db_order

        # Call _create_position_from_executed_order (new position)
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER456",
            order_info=order_info,
            execution_price=9.00,
            execution_qty=35.0,
        )

        # Verify position was created
        mock_positions_repo.upsert.assert_called_once()

        # Verify sell order was NOT updated (new position, no existing sell order)
        mock_sell_manager.update_sell_order.assert_not_called()

    def test_create_position_handles_update_failure_gracefully(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """Test that _create_position_from_executed_order handles sell order update failure gracefully"""
        existing_position = Mock()
        existing_position.quantity = 35.0
        existing_position.avg_price = 9.00
        existing_position.opened_at = Mock()
        existing_position.entry_rsi = 25.0
        existing_position.closed_at = None  # Position is open
        existing_position.reentry_count = 0
        existing_position.reentries = []
        existing_position.last_reentry_price = None

        mock_positions_repo.get_by_symbol.return_value = existing_position

        order_info = {
            "symbol": "RELIANCE-EQ",
            "db_order_id": 1,
        }

        db_order = Mock()
        db_order.order_metadata = {"entry_rsi": 18.0}
        db_order.filled_at = None
        db_order.execution_time = None
        mock_orders_repo.get.return_value = db_order

        mock_sell_manager.get_existing_sell_orders.return_value = {
            "RELIANCE": {
                "order_id": "SELL123",
                "qty": 35,
                "price": 9.50,
            }
        }

        # Mock update_sell_order to fail
        mock_sell_manager.update_sell_order.return_value = False

        # Call should not raise exception
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER456",
            order_info=order_info,
            execution_price=9.50,
            execution_qty=10.0,
        )

        # Verify position was still updated (even if sell order update failed)
        mock_positions_repo.upsert.assert_called_once()

        # Verify update_sell_order was called (but failed)
        mock_sell_manager.update_sell_order.assert_called_once()

    def test_create_position_handles_no_existing_sell_order(
        self, unified_monitor, mock_positions_repo, mock_orders_repo, mock_sell_manager
    ):
        """Test that _create_position_from_executed_order handles case when no existing sell order"""
        existing_position = Mock()
        existing_position.quantity = 35.0
        existing_position.avg_price = 9.00
        existing_position.opened_at = Mock()
        existing_position.entry_rsi = 25.0
        existing_position.closed_at = None  # Position is open
        existing_position.reentry_count = 0
        existing_position.reentries = []
        existing_position.last_reentry_price = None

        mock_positions_repo.get_by_symbol.return_value = existing_position

        order_info = {
            "symbol": "RELIANCE-EQ",
            "db_order_id": 1,
        }

        db_order = Mock()
        db_order.order_metadata = {"entry_rsi": 18.0}
        db_order.filled_at = None
        db_order.execution_time = None
        mock_orders_repo.get.return_value = db_order

        # No existing sell order
        mock_sell_manager.get_existing_sell_orders.return_value = {}

        # Call should not raise exception
        unified_monitor._create_position_from_executed_order(
            order_id="ORDER456",
            order_info=order_info,
            execution_price=9.50,
            execution_qty=10.0,
        )

        # Verify position was updated
        mock_positions_repo.upsert.assert_called_once()

        # Verify update_sell_order was NOT called (no existing order)
        mock_sell_manager.update_sell_order.assert_not_called()
