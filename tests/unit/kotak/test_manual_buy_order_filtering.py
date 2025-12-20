"""
Tests for manual buy order filtering in sell order placement.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest  # noqa: E402

from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor  # noqa: E402
from src.infrastructure.db.models import Orders  # noqa: E402
from src.infrastructure.db.timezone_utils import ist_now  # noqa: E402


class TestManualBuyOrderFiltering:
    """Test that manual buy orders are not tracked"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        return Mock()

    @pytest.fixture
    def mock_sell_manager(self):
        """Mock SellOrderManager."""
        manager = Mock()
        manager.get_existing_sell_orders = Mock(return_value={})
        manager.active_sell_orders = {}
        manager.has_completed_sell_order = Mock(return_value=None)
        manager.place_sell_order = Mock(return_value="ORDER123")
        return manager

    @pytest.fixture
    def mock_orders_repo(self):
        """Mock OrdersRepository."""
        repo = Mock()
        return repo

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository."""
        return Mock()

    @pytest.fixture
    def unified_monitor(
        self, mock_sell_manager, mock_db_session, mock_orders_repo, mock_positions_repo
    ):
        """Create UnifiedOrderMonitor instance."""
        with (
            patch("modules.kotak_neo_auto_trader.unified_order_monitor.DB_AVAILABLE", True),
            patch(
                "modules.kotak_neo_auto_trader.unified_order_monitor.OrdersRepository",
                return_value=mock_orders_repo,
            ),
            patch(
                "modules.kotak_neo_auto_trader.unified_order_monitor.PositionsRepository",
                return_value=mock_positions_repo,
            ),
        ):
            monitor = UnifiedOrderMonitor(
                sell_order_manager=mock_sell_manager,
                db_session=mock_db_session,
                user_id=1,
            )
            monitor.orders_repo = mock_orders_repo
            monitor.positions_repo = mock_positions_repo
            return monitor

    def _setup_sell_manager_mocks(self, mock_sell_manager):
        """Helper to setup sell manager mocks."""
        mock_sell_manager.get_existing_sell_orders.return_value = {}
        mock_sell_manager.active_sell_orders = {}
        mock_sell_manager.lowest_ema9 = {}  # Initialize as dict, not Mock
        mock_sell_manager.has_completed_sell_order.return_value = None
        mock_sell_manager._get_ema9_with_retry.return_value = 2500.0
        mock_sell_manager._register_order = Mock()  # Mock the register_order method

    def _setup_order_attributes(self, order, price=2500.0, qty=10.0):
        """Helper to setup order attributes for Mock objects."""
        order.execution_price = price
        order.execution_qty = qty
        order.quantity = qty
        order.avg_price = price
        order.price = price

    def test_check_and_place_sell_orders_skips_manual_buy_orders(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that manual buy orders are skipped in sell order placement."""

        execution_time = ist_now().replace(hour=10, minute=30)

        # Manual buy order (orig_source='manual')
        manual_buy_order = Mock(spec=Orders)
        manual_buy_order.side = "buy"
        manual_buy_order.orig_source = "manual"
        manual_buy_order.symbol = "RELIANCE-EQ"
        manual_buy_order.execution_time = execution_time
        manual_buy_order.filled_at = execution_time

        # System buy order (orig_source='signal')
        system_buy_order = Mock(spec=Orders)
        system_buy_order.side = "buy"
        system_buy_order.orig_source = "signal"
        system_buy_order.symbol = "TCS-EQ"
        system_buy_order.execution_time = execution_time
        system_buy_order.filled_at = execution_time
        system_buy_order.order_metadata = {"ticker": "TCS.NS"}
        self._setup_order_attributes(system_buy_order, price=3000.0, qty=10.0)

        mock_orders_repo.list.return_value = [manual_buy_order, system_buy_order]

        # Setup mocks for sell manager
        self._setup_sell_manager_mocks(mock_sell_manager)

        # Execute
        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        # Verify: Only system buy order processed (manual buy skipped)
        assert count == 1
        # Only TCS should have sell order placed
        assert mock_sell_manager.place_sell_order.call_count == 1

    def test_manual_buy_order_not_processed_for_sell_placement(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that manual buy orders are not processed."""

        execution_time = ist_now().replace(hour=10, minute=30)

        manual_buy_order = Mock(spec=Orders)
        manual_buy_order.side = "buy"
        manual_buy_order.orig_source = "manual"
        manual_buy_order.symbol = "RELIANCE-EQ"
        manual_buy_order.execution_time = execution_time
        manual_buy_order.filled_at = execution_time

        mock_orders_repo.list.return_value = [manual_buy_order]
        self._setup_sell_manager_mocks(mock_sell_manager)

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        # Verify: No sell orders placed (manual buy skipped)
        assert count == 0
        mock_sell_manager.place_sell_order.assert_not_called()

    def test_system_buy_order_processed_for_sell_placement(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that system buy orders are processed."""

        execution_time = ist_now().replace(hour=10, minute=30)

        system_buy_order = Mock(spec=Orders)
        system_buy_order.side = "buy"
        system_buy_order.orig_source = "signal"  # System order
        system_buy_order.symbol = "RELIANCE-EQ"
        system_buy_order.execution_time = execution_time
        system_buy_order.filled_at = execution_time
        system_buy_order.order_metadata = {"ticker": "RELIANCE.NS"}
        self._setup_order_attributes(system_buy_order)

        mock_orders_repo.list.return_value = [system_buy_order]
        self._setup_sell_manager_mocks(mock_sell_manager)

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        # Verify: Sell order placed for system buy
        assert count == 1
        mock_sell_manager.place_sell_order.assert_called_once()

    def test_orig_source_none_treated_as_system_order(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that orig_source=None is treated as system order."""

        execution_time = ist_now().replace(hour=10, minute=30)

        system_buy_order = Mock(spec=Orders)
        system_buy_order.side = "buy"
        system_buy_order.orig_source = None  # None = system order
        system_buy_order.symbol = "RELIANCE-EQ"
        system_buy_order.execution_time = execution_time
        system_buy_order.filled_at = execution_time
        system_buy_order.order_metadata = {"ticker": "RELIANCE.NS"}
        self._setup_order_attributes(system_buy_order)

        mock_orders_repo.list.return_value = [system_buy_order]
        self._setup_sell_manager_mocks(mock_sell_manager)

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        # Verify: Treated as system order (sell order placed)
        assert count == 1
        mock_sell_manager.place_sell_order.assert_called_once()

    def test_orig_source_case_insensitive(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that orig_source comparison is case insensitive."""

        execution_time = ist_now().replace(hour=10, minute=30)

        # Uppercase 'MANUAL'
        manual_buy_order = Mock(spec=Orders)
        manual_buy_order.side = "buy"
        manual_buy_order.orig_source = "MANUAL"  # Uppercase
        manual_buy_order.symbol = "RELIANCE-EQ"
        manual_buy_order.execution_time = execution_time
        manual_buy_order.filled_at = execution_time

        mock_orders_repo.list.return_value = [manual_buy_order]
        self._setup_sell_manager_mocks(mock_sell_manager)

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        # Verify: Skipped (case insensitive)
        assert count == 0
        mock_sell_manager.place_sell_order.assert_not_called()

    def test_orig_source_whitespace_handled(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that orig_source with whitespace is handled."""

        execution_time = ist_now().replace(hour=10, minute=30)

        # Whitespace in orig_source
        manual_buy_order = Mock(spec=Orders)
        manual_buy_order.side = "buy"
        manual_buy_order.orig_source = " manual "  # With whitespace
        manual_buy_order.symbol = "RELIANCE-EQ"
        manual_buy_order.execution_time = execution_time
        manual_buy_order.filled_at = execution_time

        mock_orders_repo.list.return_value = [manual_buy_order]
        self._setup_sell_manager_mocks(mock_sell_manager)

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        # Verify: Should be skipped (lower() handles whitespace)
        assert count == 0
        mock_sell_manager.place_sell_order.assert_not_called()

    def test_multiple_manual_buys_all_skipped(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that multiple manual buy orders are all skipped."""

        execution_time = ist_now().replace(hour=10, minute=30)

        manual_buy1 = Mock(spec=Orders)
        manual_buy1.side = "buy"
        manual_buy1.orig_source = "manual"
        manual_buy1.symbol = "RELIANCE-EQ"
        manual_buy1.execution_time = execution_time
        manual_buy1.filled_at = execution_time

        manual_buy2 = Mock(spec=Orders)
        manual_buy2.side = "buy"
        manual_buy2.orig_source = "manual"
        manual_buy2.symbol = "TCS-EQ"
        manual_buy2.execution_time = execution_time
        manual_buy2.filled_at = execution_time

        mock_orders_repo.list.return_value = [manual_buy1, manual_buy2]
        self._setup_sell_manager_mocks(mock_sell_manager)

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        # Verify: All skipped
        assert count == 0
        mock_sell_manager.place_sell_order.assert_not_called()

    def test_mixed_system_and_manual_buys_only_system_processed(
        self, unified_monitor, mock_orders_repo, mock_sell_manager
    ):
        """Test that only system buy orders are processed when mixed with manual."""

        execution_time = ist_now().replace(hour=10, minute=30)

        manual_buy = Mock(spec=Orders)
        manual_buy.side = "buy"
        manual_buy.orig_source = "manual"
        manual_buy.symbol = "RELIANCE-EQ"
        manual_buy.execution_time = execution_time
        manual_buy.filled_at = execution_time

        system_buy = Mock(spec=Orders)
        system_buy.side = "buy"
        system_buy.orig_source = "signal"
        system_buy.symbol = "TCS-EQ"
        system_buy.execution_time = execution_time
        system_buy.filled_at = execution_time
        system_buy.order_metadata = {"ticker": "TCS.NS"}
        self._setup_order_attributes(system_buy, price=3000.0, qty=10.0)

        mock_orders_repo.list.return_value = [manual_buy, system_buy]
        self._setup_sell_manager_mocks(mock_sell_manager)

        count = unified_monitor.check_and_place_sell_orders_for_new_holdings()

        # Verify: Only system buy processed
        assert count == 1
        assert mock_sell_manager.place_sell_order.call_count == 1
