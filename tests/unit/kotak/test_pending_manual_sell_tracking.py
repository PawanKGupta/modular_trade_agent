"""
Tests for pending manual sell order detection and tracking.
"""

import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest  # noqa: E402

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager  # noqa: E402
from src.infrastructure.db.models import Orders, Positions  # noqa: E402
from src.infrastructure.db.timezone_utils import ist_now  # noqa: E402


class TestDetectPendingManualSellOrders:
    """Test _detect_and_track_pending_manual_sell_orders() method"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        return Mock()

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository."""
        repo = Mock()
        return repo

    @pytest.fixture
    def mock_orders_repo(self):
        """Mock OrdersRepository."""
        repo = Mock()
        return repo

    @pytest.fixture
    def mock_orders(self):
        """Mock Orders API."""
        orders = Mock()
        orders.get_pending_orders = Mock(return_value=[])
        return orders

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_positions_repo, mock_orders_repo, mock_orders):
        """Create SellOrderManager instance with mocks."""
        with patch(
            "modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio",
        ):
            manager = SellOrderManager(
                auth=mock_auth,
                positions_repo=mock_positions_repo,
                user_id=1,
                orders_repo=mock_orders_repo,
            )
            manager.orders = mock_orders
            manager.active_sell_orders = {}
            return manager

    def test_detects_pending_manual_sell_for_system_position(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that pending manual sell is detected and tracked for system position."""
        # Setup: System position
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 100.0
        position.closed_at = None
        position.opened_at = ist_now() - timedelta(hours=2)

        mock_positions_repo.list.return_value = [position]
        mock_positions_repo.get_by_symbol.return_value = position

        # Mock system buy order
        system_buy_order = Mock(spec=Orders)
        system_buy_order.side = "buy"
        system_buy_order.symbol = "RELIANCE-EQ"
        system_buy_order.orig_source = "signal"
        system_buy_order.execution_time = position.opened_at
        mock_orders_repo.list.return_value = [system_buy_order]

        # Mock get_open_positions
        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE", "qty": 100}])

        # Mock pending orders with manual sell
        mock_orders.get_pending_orders.return_value = [
            {
                "orderId": "PENDING123",
                "trdSym": "RELIANCE-EQ",
                "transactionType": "SELL",
                "orderStatus": "pending",
                "quantity": 100,
                "price": 2500.0,
            }
        ]

        # Execute
        stats = sell_manager._detect_and_track_pending_manual_sell_orders()

        # Verify: Pending manual sell tracked
        assert stats["checked"] == 1
        assert stats["tracked"] == 1

        # Verify: Tracked in active_sell_orders
        assert "RELIANCE" in sell_manager.active_sell_orders
        tracked_order = sell_manager.active_sell_orders["RELIANCE"]
        assert tracked_order["order_id"] == "PENDING123"
        assert tracked_order["target_price"] == 2500.0
        assert tracked_order["qty"] == 100
        assert tracked_order.get("is_manual") is True

    def test_tracks_pending_manual_sell_in_active_sell_orders(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that pending manual sell is tracked in active_sell_orders."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 100.0
        position.closed_at = None
        position.opened_at = ist_now() - timedelta(hours=2)

        mock_positions_repo.list.return_value = [position]
        mock_positions_repo.get_by_symbol.return_value = position

        system_buy_order = Mock(spec=Orders)
        system_buy_order.side = "buy"
        system_buy_order.symbol = "RELIANCE-EQ"
        system_buy_order.orig_source = "signal"
        system_buy_order.execution_time = position.opened_at
        mock_orders_repo.list.return_value = [system_buy_order]

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE", "qty": 100}])

        mock_orders.get_pending_orders.return_value = [
            {
                "orderId": "PENDING123",
                "trdSym": "RELIANCE-EQ",
                "transactionType": "SELL",
                "orderStatus": "pending",
                "quantity": 100,
                "price": 2500.0,
            }
        ]

        stats = sell_manager._detect_and_track_pending_manual_sell_orders()

        assert stats["tracked"] == 1
        assert "RELIANCE" in sell_manager.active_sell_orders

    def test_skips_tracked_pending_orders(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that already tracked pending orders are skipped."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 100.0
        position.closed_at = None
        position.opened_at = ist_now() - timedelta(hours=2)

        mock_positions_repo.list.return_value = [position]
        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE", "qty": 100}])

        # Order already tracked
        sell_manager.active_sell_orders = {
            "RELIANCE": {"order_id": "PENDING123", "target_price": 2500.0, "qty": 100}
        }

        mock_orders.get_pending_orders.return_value = [
            {
                "orderId": "PENDING123",  # Same order ID
                "trdSym": "RELIANCE-EQ",
                "transactionType": "SELL",
                "orderStatus": "pending",
                "quantity": 100,
                "price": 2500.0,
            }
        ]

        stats = sell_manager._detect_and_track_pending_manual_sell_orders()

        assert stats["tracked"] == 0
        # Should not add duplicate

    def test_skips_manual_buy_positions(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that pending manual sell for manual buy position is skipped."""
        # No positions (manual buy not tracked)
        mock_positions_repo.list.return_value = []
        sell_manager.get_open_positions = Mock(return_value=[])

        mock_orders.get_pending_orders.return_value = [
            {
                "orderId": "PENDING123",
                "trdSym": "RELIANCE-EQ",
                "transactionType": "SELL",
                "orderStatus": "pending",
                "quantity": 100,
                "price": 2500.0,
            }
        ]

        stats = sell_manager._detect_and_track_pending_manual_sell_orders()

        assert stats["tracked"] == 0
        assert "RELIANCE" not in sell_manager.active_sell_orders

    def test_skips_closed_positions(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that pending manual sell for closed position is skipped."""
        closed_position = Mock(spec=Positions)
        closed_position.symbol = "RELIANCE"
        closed_position.quantity = 0.0
        closed_position.closed_at = ist_now() - timedelta(minutes=5)

        mock_positions_repo.list.return_value = []
        mock_positions_repo.get_by_symbol.return_value = closed_position

        sell_manager.get_open_positions = Mock(return_value=[])

        mock_orders.get_pending_orders.return_value = [
            {
                "orderId": "PENDING123",
                "trdSym": "RELIANCE-EQ",
                "transactionType": "SELL",
                "orderStatus": "pending",
                "quantity": 100,
                "price": 2500.0,
            }
        ]

        stats = sell_manager._detect_and_track_pending_manual_sell_orders()

        assert stats["tracked"] == 0
        assert "RELIANCE" not in sell_manager.active_sell_orders

    def test_validates_system_position_before_tracking(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that only system positions are tracked."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 100.0
        position.closed_at = None
        position.opened_at = ist_now() - timedelta(hours=2)

        mock_positions_repo.list.return_value = [position]
        mock_positions_repo.get_by_symbol.return_value = position

        # No system buy order (manual buy position)
        mock_orders_repo.list.return_value = []

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE", "qty": 100}])

        mock_orders.get_pending_orders.return_value = [
            {
                "orderId": "PENDING123",
                "trdSym": "RELIANCE-EQ",
                "transactionType": "SELL",
                "orderStatus": "pending",
                "quantity": 100,
                "price": 2500.0,
            }
        ]

        stats = sell_manager._detect_and_track_pending_manual_sell_orders()

        # Should be skipped because position is not from system buy
        assert stats["tracked"] == 0
        assert "RELIANCE" not in sell_manager.active_sell_orders

    def test_handles_pending_orders_api_failure(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that pending orders API failure is handled gracefully."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 100.0
        position.closed_at = None

        mock_positions_repo.list.return_value = [position]
        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE", "qty": 100}])

        # API failure
        mock_orders.get_pending_orders.side_effect = Exception("API Error")

        stats = sell_manager._detect_and_track_pending_manual_sell_orders()

        # Should return empty stats without crashing
        assert stats["checked"] == 1
        assert stats["tracked"] == 0

    def test_handles_missing_orders_repo(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that missing orders_repo is handled."""
        sell_manager.orders_repo = None

        stats = sell_manager._detect_and_track_pending_manual_sell_orders()

        assert stats == {"checked": 0, "tracked": 0}

    def test_handles_missing_positions_repo(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that missing positions_repo is handled."""
        sell_manager.positions_repo = None

        stats = sell_manager._detect_and_track_pending_manual_sell_orders()

        assert stats == {"checked": 0, "tracked": 0}

    def test_tracking_prevents_system_from_placing_duplicate(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that tracking prevents system from placing duplicate sell order."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE"
        position.quantity = 100.0
        position.closed_at = None
        position.opened_at = ist_now() - timedelta(hours=2)

        mock_positions_repo.list.return_value = [position]
        mock_positions_repo.get_by_symbol.return_value = position

        system_buy_order = Mock(spec=Orders)
        system_buy_order.side = "buy"
        system_buy_order.symbol = "RELIANCE-EQ"
        system_buy_order.orig_source = "signal"
        system_buy_order.execution_time = position.opened_at
        mock_orders_repo.list.return_value = [system_buy_order]

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE", "qty": 100}])

        mock_orders.get_pending_orders.return_value = [
            {
                "orderId": "PENDING123",
                "trdSym": "RELIANCE-EQ",
                "transactionType": "SELL",
                "orderStatus": "pending",
                "quantity": 100,
                "price": 2500.0,
            }
        ]

        # Track pending manual sell
        stats = sell_manager._detect_and_track_pending_manual_sell_orders()
        assert stats["tracked"] == 1

        # Verify: System would skip placing sell order because it's in active_sell_orders
        assert "RELIANCE" in sell_manager.active_sell_orders
        # This prevents duplicate placement in check_and_place_sell_orders_for_new_holdings()
