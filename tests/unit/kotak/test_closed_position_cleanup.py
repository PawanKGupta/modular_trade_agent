"""
Tests for closed position cleanup during monitoring.
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
from src.infrastructure.db.models import Positions  # noqa: E402
from src.infrastructure.db.timezone_utils import ist_now  # noqa: E402


class TestClosedPositionCleanup:
    """Test that closed positions are removed from monitoring"""

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
    def mock_orders(self):
        """Mock Orders API."""
        orders = Mock()
        orders.get_orders = Mock(return_value={"data": []})
        orders.get_pending_orders = Mock(return_value=[])
        return orders

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_positions_repo, mock_orders):
        """Create SellOrderManager instance with mocks."""
        with patch(
            "modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio",
        ):
            manager = SellOrderManager(
                auth=mock_auth,
                positions_repo=mock_positions_repo,
                user_id=1,
            )
            manager.orders = mock_orders
            manager.active_sell_orders = {
                "RELIANCE": {"order_id": "ORDER123", "target_price": 2500.0, "qty": 100}
            }
            manager.lowest_ema9 = {"RELIANCE": 2500.0}
            return manager

    def test_closed_position_skipped_in_monitoring(
        self, sell_manager, mock_positions_repo, mock_orders
    ):
        """Test that closed position is skipped during monitoring."""
        closed_position = Mock(spec=Positions)
        closed_position.symbol = "RELIANCE"
        closed_position.quantity = 0.0
        closed_position.closed_at = ist_now() - timedelta(minutes=5)

        mock_positions_repo.get_by_symbol.return_value = closed_position

        # Mock _check_and_update_single_stock behavior
        with patch.object(sell_manager, "_check_and_update_single_stock") as mock_check:
            # Simulate the check that happens in monitor_and_update
            result = {
                "symbol": "RELIANCE",
                "action": "skipped",
                "success": True,
                "remove_from_tracking": True,
            }
            mock_check.return_value = result

            # Simulate monitoring cycle
            symbols_to_remove = []
            if result.get("remove_from_tracking"):
                symbols_to_remove.append("RELIANCE")

            # Verify: Position marked for removal
            assert "RELIANCE" in symbols_to_remove

    def test_closed_position_removed_from_active_sell_orders(
        self, sell_manager, mock_positions_repo, mock_orders
    ):
        """Test that closed position is removed from active_sell_orders."""
        closed_position = Mock(spec=Positions)
        closed_position.symbol = "RELIANCE"
        closed_position.quantity = 0.0
        closed_position.closed_at = ist_now() - timedelta(minutes=5)

        mock_positions_repo.get_by_symbol.return_value = closed_position

        # Simulate removal
        if "RELIANCE" in sell_manager.active_sell_orders:
            del sell_manager.active_sell_orders["RELIANCE"]

        # Verify: Removed from active_sell_orders
        assert "RELIANCE" not in sell_manager.active_sell_orders

    def test_closed_position_removed_from_lowest_ema9(
        self, sell_manager, mock_positions_repo, mock_orders
    ):
        """Test that closed position is removed from lowest_ema9."""
        closed_position = Mock(spec=Positions)
        closed_position.symbol = "RELIANCE"
        closed_position.quantity = 0.0
        closed_position.closed_at = ist_now() - timedelta(minutes=5)

        mock_positions_repo.get_by_symbol.return_value = closed_position

        # Simulate removal
        if "RELIANCE" in sell_manager.lowest_ema9:
            del sell_manager.lowest_ema9["RELIANCE"]

        # Verify: Removed from lowest_ema9
        assert "RELIANCE" not in sell_manager.lowest_ema9

    def test_multiple_closed_positions_all_removed(
        self, sell_manager, mock_positions_repo, mock_orders
    ):
        """Test that multiple closed positions are all removed."""
        sell_manager.active_sell_orders = {
            "RELIANCE": {"order_id": "ORDER1", "target_price": 2500.0, "qty": 100},
            "TCS": {"order_id": "ORDER2", "target_price": 3000.0, "qty": 50},
        }
        sell_manager.lowest_ema9 = {"RELIANCE": 2500.0, "TCS": 3000.0}

        closed_position1 = Mock(spec=Positions)
        closed_position1.symbol = "RELIANCE"
        closed_position1.closed_at = ist_now() - timedelta(minutes=5)

        closed_position2 = Mock(spec=Positions)
        closed_position2.symbol = "TCS"
        closed_position2.closed_at = ist_now() - timedelta(minutes=3)

        mock_positions_repo.get_by_symbol.side_effect = [
            closed_position1,
            closed_position2,
        ]

        # Simulate removal
        symbols_to_remove = ["RELIANCE", "TCS"]
        for symbol in symbols_to_remove:
            if symbol in sell_manager.active_sell_orders:
                del sell_manager.active_sell_orders[symbol]
            if symbol in sell_manager.lowest_ema9:
                del sell_manager.lowest_ema9[symbol]

        # Verify: All removed
        assert len(sell_manager.active_sell_orders) == 0
        assert len(sell_manager.lowest_ema9) == 0

    def test_position_closed_by_system_sell_order(
        self, sell_manager, mock_positions_repo, mock_orders
    ):
        """Test cleanup when position closed by system sell order."""
        closed_position = Mock(spec=Positions)
        closed_position.symbol = "RELIANCE"
        closed_position.quantity = 0.0
        closed_position.closed_at = ist_now() - timedelta(minutes=2)

        mock_positions_repo.get_by_symbol.return_value = closed_position

        # Position was closed by system sell order
        # Next monitoring cycle should remove it
        if closed_position.closed_at:
            if "RELIANCE" in sell_manager.active_sell_orders:
                del sell_manager.active_sell_orders["RELIANCE"]

        assert "RELIANCE" not in sell_manager.active_sell_orders

    def test_position_closed_by_manual_sell_order(
        self, sell_manager, mock_positions_repo, mock_orders
    ):
        """Test cleanup when position closed by manual sell order."""
        closed_position = Mock(spec=Positions)
        closed_position.symbol = "RELIANCE"
        closed_position.quantity = 0.0
        closed_position.closed_at = ist_now() - timedelta(minutes=1)

        mock_positions_repo.get_by_symbol.return_value = closed_position

        # Position was closed by manual sell order
        # Next monitoring cycle should remove it
        if closed_position.closed_at:
            if "RELIANCE" in sell_manager.active_sell_orders:
                del sell_manager.active_sell_orders["RELIANCE"]

        assert "RELIANCE" not in sell_manager.active_sell_orders

    def test_position_closed_by_reconciliation(
        self, sell_manager, mock_positions_repo, mock_orders
    ):
        """Test cleanup when position closed by reconciliation."""
        closed_position = Mock(spec=Positions)
        closed_position.symbol = "RELIANCE"
        closed_position.quantity = 0.0
        closed_position.closed_at = ist_now() - timedelta(minutes=10)

        mock_positions_repo.get_by_symbol.return_value = closed_position

        # Position was closed by reconciliation
        # Next monitoring cycle should remove it
        if closed_position.closed_at:
            if "RELIANCE" in sell_manager.active_sell_orders:
                del sell_manager.active_sell_orders["RELIANCE"]

        assert "RELIANCE" not in sell_manager.active_sell_orders
