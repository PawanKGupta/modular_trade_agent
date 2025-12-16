"""
Unit tests for Issue #5: Positions Without Sell Orders

Tests verify:
1. get_positions_without_sell_orders() - database-only and broker API modes
2. _get_positions_without_sell_orders_db_only() - database-only implementation
3. _place_sell_orders_for_missing_positions() - returns tuple with failed positions
4. Enhanced Telegram alerts with symbol details
5. Edge cases: no positions, all have orders, EMA9 failures, zero quantity, etc.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest  # noqa: E402

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager  # noqa: E402
from src.infrastructure.db.models import Orders, Positions  # noqa: E402
from src.infrastructure.db.models import OrderStatus as DbOrderStatus  # noqa: E402


class TestGetPositionsWithoutSellOrdersDatabaseOnly:
    """Test get_positions_without_sell_orders() in database-only mode (default)"""

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
    def sell_manager(self, mock_auth, mock_positions_repo, mock_orders_repo):
        """Create SellOrderManager instance with mocks."""
        with (
            patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio"),
            patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"),
        ):
            manager = SellOrderManager(
                auth=mock_auth,
                positions_repo=mock_positions_repo,
                orders_repo=mock_orders_repo,
                user_id=1,
            )
            manager.indicator_service = Mock()
            manager.indicator_service.calculate_ema9_realtime = Mock(return_value=2500.0)
            manager.indicator_service.price_service = Mock()
            manager.indicator_service.price_service.get_price = Mock(return_value=None)
            return manager

    def test_no_open_positions(self, sell_manager, mock_positions_repo):
        """Test when there are no open positions."""
        mock_positions_repo.list.return_value = []

        result = sell_manager.get_positions_without_sell_orders()

        assert result == []
        mock_positions_repo.list.assert_called_once_with(1)

    def test_all_positions_have_sell_orders(
        self, sell_manager, mock_positions_repo, mock_orders_repo
    ):
        """Test when all positions have sell orders in database."""
        # Setup: 2 open positions
        pos1 = Mock(spec=Positions)
        pos1.symbol = "RELIANCE-EQ"  # Full symbol after migration
        pos1.quantity = 10.0
        pos1.avg_price = 2500.0
        pos1.closed_at = None

        pos2 = Mock(spec=Positions)
        pos2.symbol = "TCS-EQ"  # Full symbol after migration
        pos2.quantity = 5.0
        pos2.avg_price = 3500.0
        pos2.closed_at = None

        mock_positions_repo.list.return_value = [pos1, pos2]

        # Setup: Both have sell orders in database
        sell_order1 = Mock(spec=Orders)
        sell_order1.side = "sell"
        sell_order1.symbol = "RELIANCE-EQ"
        sell_order1.status = DbOrderStatus.PENDING

        sell_order2 = Mock(spec=Orders)
        sell_order2.side = "sell"
        sell_order2.symbol = "TCS-EQ"
        sell_order2.status = DbOrderStatus.ONGOING

        mock_orders_repo.list.return_value = [sell_order1, sell_order2]

        result = sell_manager.get_positions_without_sell_orders()

        assert result == []
        mock_positions_repo.list.assert_called_once_with(1)
        mock_orders_repo.list.assert_called_once_with(1)

    def test_some_positions_missing_sell_orders(
        self, sell_manager, mock_positions_repo, mock_orders_repo
    ):
        """Test when some positions have sell orders, some don't."""
        # Setup: 3 open positions
        pos1 = Mock(spec=Positions)
        pos1.symbol = "RELIANCE-EQ"  # Full symbol after migration
        pos1.quantity = 10.0
        pos1.avg_price = 2500.0
        pos1.closed_at = None

        pos2 = Mock(spec=Positions)
        pos2.symbol = "TCS-EQ"  # Full symbol after migration
        pos2.quantity = 5.0
        pos2.avg_price = 3500.0
        pos2.closed_at = None

        pos3 = Mock(spec=Positions)
        pos3.symbol = "INFY-EQ"  # Full symbol after migration
        pos3.quantity = 8.0
        pos3.avg_price = 1500.0
        pos3.closed_at = None

        mock_positions_repo.list.return_value = [pos1, pos2, pos3]

        # Setup: Only RELIANCE has sell order
        sell_order = Mock(spec=Orders)
        sell_order.side = "sell"
        sell_order.symbol = "RELIANCE-EQ"
        sell_order.status = DbOrderStatus.PENDING

        mock_orders_repo.list.return_value = [sell_order]

        # Mock EMA9 calculation
        sell_manager._get_ema9_with_retry = Mock(side_effect=lambda *args, **kwargs: 2500.0)

        result = sell_manager.get_positions_without_sell_orders()

        assert len(result) == 2  # TCS and INFY
        symbols = [r["symbol"] for r in result]
        assert "TCS-EQ" in symbols  # Full symbol after migration
        assert "INFY-EQ" in symbols  # Full symbol after migration
        assert "RELIANCE-EQ" not in symbols

        # Verify all have valid structure
        for r in result:
            assert "symbol" in r
            assert "entry_price" in r
            assert "quantity" in r
            assert "reason" in r
            assert "ticker" in r
            assert "broker_symbol" in r

    def test_ema9_calculation_failure(self, sell_manager, mock_positions_repo, mock_orders_repo):
        """Test when EMA9 calculation fails."""
        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE-EQ"  # Full symbol after migration
        pos.quantity = 10.0
        pos.avg_price = 2500.0
        pos.closed_at = None

        mock_positions_repo.list.return_value = [pos]
        mock_orders_repo.list.return_value = []  # No sell orders

        # Mock EMA9 calculation failure
        sell_manager._get_ema9_with_retry = Mock(return_value=None)

        # Pass skip_ema9_check=False to get detailed analysis
        result = sell_manager.get_positions_without_sell_orders(skip_ema9_check=False)

        assert len(result) == 1
        assert result[0]["symbol"] == "RELIANCE-EQ"  # Full symbol after migration
        assert result[0]["reason"] == "EMA9 calculation failed (Issue #3)"

    def test_zero_quantity_position(self, sell_manager, mock_positions_repo, mock_orders_repo):
        """Test when position has zero quantity."""
        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE-EQ"  # Full symbol after migration
        pos.quantity = 0.0
        pos.avg_price = 2500.0
        pos.closed_at = None

        mock_positions_repo.list.return_value = [pos]
        mock_orders_repo.list.return_value = []

        # Mock EMA9 calculation success
        sell_manager._get_ema9_with_retry = Mock(return_value=2500.0)

        result = sell_manager.get_positions_without_sell_orders()

        assert len(result) == 1
        assert result[0]["symbol"] == "RELIANCE-EQ"  # Full symbol after migration
        assert result[0]["reason"] == "Zero or invalid quantity (Issue #2)"

    def test_closed_positions_excluded(self, sell_manager, mock_positions_repo, mock_orders_repo):
        """Test that closed positions are excluded."""
        from datetime import datetime

        open_pos = Mock(spec=Positions)
        open_pos.symbol = "RELIANCE-EQ"  # Full symbol after migration
        open_pos.quantity = 10.0
        open_pos.avg_price = 2500.0
        open_pos.closed_at = None

        closed_pos = Mock(spec=Positions)
        closed_pos.symbol = "TCS-EQ"  # Full symbol after migration
        closed_pos.quantity = 5.0
        closed_pos.avg_price = 3500.0
        closed_pos.closed_at = datetime.now()

        mock_positions_repo.list.return_value = [open_pos, closed_pos]
        mock_orders_repo.list.return_value = []

        sell_manager._get_ema9_with_retry = Mock(return_value=2500.0)

        result = sell_manager.get_positions_without_sell_orders()

        assert len(result) == 1
        assert result[0]["symbol"] == "RELIANCE-EQ"  # Full symbol after migration
        assert "TCS-EQ" not in [r["symbol"] for r in result]  # Full symbol after migration

    def test_orders_repo_not_available(self, sell_manager, mock_positions_repo):
        """Test when orders_repo is not available."""
        sell_manager.orders_repo = None

        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE-EQ"  # Full symbol after migration
        pos.quantity = 10.0
        pos.avg_price = 2500.0
        pos.closed_at = None

        mock_positions_repo.list.return_value = [pos]

        sell_manager._get_ema9_with_retry = Mock(return_value=2500.0)

        result = sell_manager.get_positions_without_sell_orders()

        # Should still work, just won't check for existing sell orders
        assert len(result) == 1
        assert result[0]["symbol"] == "RELIANCE-EQ"  # Full symbol after migration

    def test_enriches_metadata_from_orders(
        self, sell_manager, mock_positions_repo, mock_orders_repo
    ):
        """Test that ticker and broker_symbol are enriched from buy orders."""
        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE-EQ"  # Full symbol after migration
        pos.quantity = 10.0
        pos.avg_price = 2500.0
        pos.closed_at = None

        mock_positions_repo.list.return_value = [pos]
        mock_orders_repo.list.return_value = []  # No sell orders

        # Mock buy order with metadata
        buy_order = Mock(spec=Orders)
        buy_order.side = "buy"
        buy_order.symbol = "RELIANCE-EQ"
        buy_order.status = DbOrderStatus.ONGOING
        buy_order.order_metadata = {"ticker": "RELIANCE.NS"}

        # Mock list to return buy order when checking for metadata
        def list_side_effect(user_id, status=None):
            if status == DbOrderStatus.ONGOING:
                return [buy_order]
            return []

        mock_orders_repo.list.side_effect = list_side_effect

        sell_manager._get_ema9_with_retry = Mock(return_value=2500.0)

        result = sell_manager.get_positions_without_sell_orders()

        assert len(result) == 1
        # Ticker should use base symbol (RELIANCE.NS), not full symbol (RELIANCE-EQ.NS)
        assert result[0]["ticker"] == "RELIANCE.NS"
        assert result[0]["broker_symbol"] == "RELIANCE-EQ"
        assert result[0]["symbol"] == "RELIANCE-EQ"  # Full symbol after migration

    def test_exception_during_analysis(self, sell_manager, mock_positions_repo, mock_orders_repo):
        """Test when exception occurs during analysis."""
        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE-EQ"  # Full symbol after migration
        pos.quantity = 10.0
        pos.avg_price = 2500.0
        pos.closed_at = None

        mock_positions_repo.list.return_value = [pos]
        mock_orders_repo.list.return_value = []

        # Mock EMA9 calculation to raise exception
        sell_manager._get_ema9_with_retry = Mock(side_effect=Exception("Network error"))

        # Pass skip_ema9_check=False to get detailed analysis
        result = sell_manager.get_positions_without_sell_orders(skip_ema9_check=False)

        assert len(result) == 1
        assert result[0]["symbol"] == "RELIANCE-EQ"  # Full symbol after migration
        assert "Error during analysis" in result[0]["reason"]

    def test_missing_positions_repo(self, sell_manager):
        """Test when positions_repo is not available."""
        sell_manager.positions_repo = None

        # Implementation gracefully returns empty list when repos are missing
        result = sell_manager.get_positions_without_sell_orders()
        assert result == []

    def test_missing_user_id(self, sell_manager):
        """Test when user_id is not available."""
        sell_manager.user_id = None

        result = sell_manager.get_positions_without_sell_orders()

        assert result == []


class TestGetPositionsWithoutSellOrdersBrokerAPIMode:
    """Test get_positions_without_sell_orders() in broker API mode"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        return Mock()

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository."""
        return Mock()

    @pytest.fixture
    def mock_orders_repo(self):
        """Mock OrdersRepository."""
        return Mock()

    @pytest.fixture
    def mock_portfolio(self):
        """Mock KotakNeoPortfolio."""
        return Mock()

    @pytest.fixture
    def mock_broker_orders(self):
        """Mock broker orders API."""
        return Mock()

    @pytest.fixture
    def sell_manager(
        self, mock_auth, mock_positions_repo, mock_orders_repo, mock_portfolio, mock_broker_orders
    ):
        """Create SellOrderManager instance with mocks."""
        with (
            patch(
                "modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio",
                return_value=mock_portfolio,
            ),
            patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"),
        ):
            manager = SellOrderManager(
                auth=mock_auth,
                positions_repo=mock_positions_repo,
                orders_repo=mock_orders_repo,
                user_id=1,
            )
            manager.portfolio = mock_portfolio
            manager.orders = mock_broker_orders
            manager.indicator_service = Mock()
            manager.indicator_service.calculate_ema9_realtime = Mock(return_value=2500.0)
            manager.indicator_service.price_service = Mock()
            manager.indicator_service.price_service.get_price = Mock(return_value=None)
            return manager

    def test_uses_broker_api_when_requested(
        self, sell_manager, mock_positions_repo, mock_portfolio, mock_broker_orders
    ):
        """Test that broker API mode calls get_open_positions() and get_existing_sell_orders()."""
        # Mock get_open_positions to return positions
        sell_manager.get_open_positions = Mock(
            return_value=[
                {
                    "symbol": "RELIANCE-EQ",  # Full symbol after migration
                    "qty": 10,
                    "entry_price": 2500.0,
                    "ticker": "RELIANCE.NS",
                    "placed_symbol": "RELIANCE-EQ",
                }
            ]
        )

        # Mock get_existing_sell_orders to return empty (no existing orders)
        sell_manager.get_existing_sell_orders = Mock(return_value={})

        # Mock EMA9 calculation
        sell_manager._get_ema9_with_retry = Mock(return_value=2500.0)

        result = sell_manager.get_positions_without_sell_orders(use_broker_api=True)

        # Verify broker API methods were called
        sell_manager.get_open_positions.assert_called_once()
        sell_manager.get_existing_sell_orders.assert_called_once()

        assert len(result) == 1
        assert result[0]["symbol"] == "RELIANCE-EQ"  # Full symbol after migration

    def test_broker_api_validates_holdings(
        self, sell_manager, mock_positions_repo, mock_portfolio, mock_broker_orders
    ):
        """Test that broker API mode validates against broker holdings."""
        # Mock get_open_positions (which calls portfolio.get_holdings())
        sell_manager.get_open_positions = Mock(return_value=[])

        result = sell_manager.get_positions_without_sell_orders(use_broker_api=True)

        sell_manager.get_open_positions.assert_called_once()
        assert result == []


class TestPlaceSellOrdersForMissingPositions:
    """Test _place_sell_orders_for_missing_positions() returns tuple with failed positions"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        return Mock()

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository."""
        return Mock()

    @pytest.fixture
    def mock_orders_repo(self):
        """Mock OrdersRepository."""
        return Mock()

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_positions_repo, mock_orders_repo):
        """Create SellOrderManager instance with mocks."""
        with (
            patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio"),
            patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"),
        ):
            manager = SellOrderManager(
                auth=mock_auth,
                positions_repo=mock_positions_repo,
                orders_repo=mock_orders_repo,
                user_id=1,
            )
            manager.orders = Mock()
            manager.indicator_service = Mock()
            manager.indicator_service.calculate_ema9_realtime = Mock(return_value=2500.0)
            manager.indicator_service.price_service = Mock()
            manager.indicator_service.price_service.get_price = Mock(return_value=None)
            manager._register_order = Mock()
            manager.lowest_ema9 = {}
            return manager

    def test_returns_tuple_with_orders_placed_and_failed(self, sell_manager, mock_positions_repo):
        """Test that method returns tuple (orders_placed, failed_positions)."""
        # Mock get_open_positions
        sell_manager.get_open_positions = Mock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "ticker": "RELIANCE.NS",
                    "placed_symbol": "RELIANCE-EQ",
                }
            ]
        )

        # Mock get_existing_sell_orders (no existing orders)
        sell_manager.get_existing_sell_orders = Mock(return_value={})

        # Mock EMA9 calculation
        sell_manager._get_ema9_with_retry = Mock(return_value=2500.0)

        # Mock place_sell_order to succeed
        sell_manager.place_sell_order = Mock(return_value="ORDER123")

        orders_placed, failed_positions = sell_manager._place_sell_orders_for_missing_positions()

        assert isinstance(orders_placed, int)
        assert isinstance(failed_positions, list)
        assert orders_placed == 1
        assert len(failed_positions) == 0

    def test_tracks_failed_positions_ema9_failure(self, sell_manager, mock_positions_repo):
        """Test that failed positions are tracked when EMA9 calculation fails."""
        sell_manager.get_open_positions = Mock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "ticker": "RELIANCE.NS",
                    "placed_symbol": "RELIANCE-EQ",
                }
            ]
        )
        sell_manager.get_existing_sell_orders = Mock(return_value={})

        # Mock EMA9 calculation failure
        sell_manager._get_ema9_with_retry = Mock(return_value=None)

        orders_placed, failed_positions = sell_manager._place_sell_orders_for_missing_positions()

        assert orders_placed == 0
        assert len(failed_positions) == 1
        assert failed_positions[0]["symbol"] == "RELIANCE"
        assert failed_positions[0]["reason"] == "EMA9 calculation failed (Issue #3)"
        assert failed_positions[0]["entry_price"] == 2500.0
        assert failed_positions[0]["quantity"] == 10

    def test_tracks_failed_positions_order_placement_failure(
        self, sell_manager, mock_positions_repo
    ):
        """Test that failed positions are tracked when order placement fails."""
        sell_manager.get_open_positions = Mock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "ticker": "RELIANCE.NS",
                    "placed_symbol": "RELIANCE-EQ",
                }
            ]
        )
        sell_manager.get_existing_sell_orders = Mock(return_value={})

        # Mock EMA9 calculation success
        sell_manager._get_ema9_with_retry = Mock(return_value=2500.0)

        # Mock place_sell_order to fail (returns None)
        sell_manager.place_sell_order = Mock(return_value=None)

        orders_placed, failed_positions = sell_manager._place_sell_orders_for_missing_positions()

        assert orders_placed == 0
        assert len(failed_positions) == 1
        assert failed_positions[0]["symbol"] == "RELIANCE"
        assert "Order placement failed" in failed_positions[0]["reason"]

    def test_tracks_failed_positions_exception(self, sell_manager, mock_positions_repo):
        """Test that failed positions are tracked when exception occurs."""
        sell_manager.get_open_positions = Mock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "ticker": "RELIANCE.NS",
                    "placed_symbol": "RELIANCE-EQ",
                }
            ]
        )
        sell_manager.get_existing_sell_orders = Mock(return_value={})

        # Mock EMA9 calculation to raise exception
        sell_manager._get_ema9_with_retry = Mock(side_effect=Exception("Network error"))

        orders_placed, failed_positions = sell_manager._place_sell_orders_for_missing_positions()

        assert orders_placed == 0
        assert len(failed_positions) == 1
        assert failed_positions[0]["symbol"] == "RELIANCE"
        assert "Exception" in failed_positions[0]["reason"]

    def test_skips_positions_with_existing_orders(self, sell_manager, mock_positions_repo):
        """Test that positions with existing sell orders are skipped."""
        sell_manager.get_open_positions = Mock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "ticker": "RELIANCE.NS",
                    "placed_symbol": "RELIANCE-EQ",
                },
                {
                    "symbol": "TCS",
                    "qty": 5,
                    "entry_price": 3500.0,
                    "ticker": "TCS.NS",
                    "placed_symbol": "TCS-EQ",
                },
            ]
        )

        # Mock existing sell order for RELIANCE
        sell_manager.get_existing_sell_orders = Mock(
            return_value={"RELIANCE": {"order_id": "EXISTING123", "qty": 10, "price": 2500.0}}
        )

        sell_manager._get_ema9_with_retry = Mock(return_value=2500.0)
        sell_manager.place_sell_order = Mock(return_value="ORDER123")

        orders_placed, failed_positions = sell_manager._place_sell_orders_for_missing_positions()

        # Only TCS should have order placed (RELIANCE skipped)
        assert orders_placed == 1
        assert len(failed_positions) == 0
        # Verify place_sell_order was called only once (for TCS)
        assert sell_manager.place_sell_order.call_count == 1

    def test_handles_missing_positions_repo(self, sell_manager):
        """Test when positions_repo is not available."""
        sell_manager.positions_repo = None

        orders_placed, failed_positions = sell_manager._place_sell_orders_for_missing_positions()

        assert orders_placed == 0
        assert failed_positions == []

    def test_handles_missing_user_id(self, sell_manager):
        """Test when user_id is not available."""
        sell_manager.user_id = None

        orders_placed, failed_positions = sell_manager._place_sell_orders_for_missing_positions()

        assert orders_placed == 0
        assert failed_positions == []

    def test_handles_empty_open_positions(self, sell_manager, mock_positions_repo):
        """Test when there are no open positions."""
        sell_manager.get_open_positions = Mock(return_value=[])
        sell_manager.get_existing_sell_orders = Mock(return_value={})

        orders_placed, failed_positions = sell_manager._place_sell_orders_for_missing_positions()

        assert orders_placed == 0
        assert failed_positions == []

    def test_partial_success_tracks_both(self, sell_manager, mock_positions_repo):
        """Test when some orders succeed and some fail."""
        sell_manager.get_open_positions = Mock(
            return_value=[
                {
                    "symbol": "RELIANCE",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "ticker": "RELIANCE.NS",
                    "placed_symbol": "RELIANCE-EQ",
                },
                {
                    "symbol": "TCS",
                    "qty": 5,
                    "entry_price": 3500.0,
                    "ticker": "TCS.NS",
                    "placed_symbol": "TCS-EQ",
                },
            ]
        )
        sell_manager.get_existing_sell_orders = Mock(return_value={})

        # Mock EMA9 calculation success for both
        sell_manager._get_ema9_with_retry = Mock(return_value=2500.0)

        # Mock place_sell_order: succeed for RELIANCE, fail for TCS
        def place_order_side_effect(position, ema9):
            if position["symbol"] == "RELIANCE":
                return "ORDER123"
            return None

        sell_manager.place_sell_order = Mock(side_effect=place_order_side_effect)

        orders_placed, failed_positions = sell_manager._place_sell_orders_for_missing_positions()

        assert orders_placed == 1  # RELIANCE succeeded
        assert len(failed_positions) == 1  # TCS failed
        assert failed_positions[0]["symbol"] == "TCS"


class TestCheckPositionsWithoutSellOrders:
    """Test _check_positions_without_sell_orders() method"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        return Mock()

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository."""
        return Mock()

    @pytest.fixture
    def mock_orders_repo(self):
        """Mock OrdersRepository."""
        return Mock()

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_positions_repo, mock_orders_repo):
        """Create SellOrderManager instance with mocks."""
        with (
            patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio"),
            patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"),
        ):
            manager = SellOrderManager(
                auth=mock_auth,
                positions_repo=mock_positions_repo,
                orders_repo=mock_orders_repo,
                user_id=1,
            )
            manager.active_sell_orders = {}
            return manager

    def test_counts_positions_without_orders(self, sell_manager, mock_positions_repo):
        """Test that method correctly counts positions without sell orders."""
        from datetime import datetime

        # Setup: 3 open positions with required fields
        pos1 = Mock(spec=Positions)
        pos1.symbol = "RELIANCE-EQ"  # Full symbol after migration
        pos1.quantity = 10.0
        pos1.avg_price = 2500.0
        pos1.opened_at = datetime.now()
        pos1.closed_at = None

        pos2 = Mock(spec=Positions)
        pos2.symbol = "TCS-EQ"  # Full symbol after migration
        pos2.quantity = 5.0
        pos2.avg_price = 3500.0
        pos2.opened_at = datetime.now()
        pos2.closed_at = None

        pos3 = Mock(spec=Positions)
        pos3.symbol = "INFY-EQ"  # Full symbol after migration
        pos3.quantity = 8.0
        pos3.avg_price = 1500.0
        pos3.opened_at = datetime.now()
        pos3.closed_at = None

        mock_positions_repo.list.return_value = [pos1, pos2, pos3]

        # Mock portfolio to avoid broker API calls
        sell_manager.portfolio = Mock()
        sell_manager.portfolio.get_holdings = Mock(return_value={"data": []})

        # Mock get_existing_sell_orders to return only RELIANCE
        sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE-EQ": {"order_id": "ORDER123", "qty": 10, "price": 2500.0}
            }  # Full symbol after migration
        )

        count = sell_manager._check_positions_without_sell_orders()

        assert count == 2  # TCS and INFY

    def test_returns_zero_when_all_have_orders(self, sell_manager, mock_positions_repo):
        """Test that method returns 0 when all positions have sell orders."""
        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE"
        pos.closed_at = None

        mock_positions_repo.list.return_value = [pos]
        sell_manager.active_sell_orders = {"RELIANCE": {"order_id": "ORDER123"}}

        count = sell_manager._check_positions_without_sell_orders()

        assert count == 0

    def test_excludes_closed_positions(self, sell_manager, mock_positions_repo):
        """Test that closed positions are excluded from count."""
        from datetime import datetime

        open_pos = Mock(spec=Positions)
        open_pos.symbol = "RELIANCE-EQ"  # Full symbol after migration
        open_pos.quantity = 10.0
        open_pos.avg_price = 2500.0
        open_pos.opened_at = datetime.now()
        open_pos.closed_at = None

        closed_pos = Mock(spec=Positions)
        closed_pos.symbol = "TCS-EQ"  # Full symbol after migration
        closed_pos.quantity = 5.0
        closed_pos.avg_price = 3500.0
        closed_pos.opened_at = datetime.now()
        closed_pos.closed_at = datetime.now()

        mock_positions_repo.list.return_value = [open_pos, closed_pos]

        # Mock portfolio to avoid broker API calls
        sell_manager.portfolio = Mock()
        sell_manager.portfolio.get_holdings = Mock(return_value={"data": []})

        # Mock get_existing_sell_orders to return empty (no orders)
        sell_manager.get_existing_sell_orders = Mock(return_value={})

        count = sell_manager._check_positions_without_sell_orders()

        assert count == 1  # Only open position counted

    def test_handles_missing_repos(self, sell_manager):
        """Test when repositories are not available."""
        sell_manager.positions_repo = None

        count = sell_manager._check_positions_without_sell_orders()

        assert count == 0

    def test_handles_exception(self, sell_manager, mock_positions_repo):
        """Test that exceptions are handled gracefully."""
        mock_positions_repo.list.side_effect = Exception("Database error")

        count = sell_manager._check_positions_without_sell_orders()

        assert count == 0


class TestMonitorAndUpdateIntegration:
    """Test integration of Issue #5 fixes with monitor_and_update()"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        return Mock()

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository."""
        return Mock()

    @pytest.fixture
    def mock_orders_repo(self):
        """Mock OrdersRepository."""
        return Mock()

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_positions_repo, mock_orders_repo):
        """Create SellOrderManager instance with mocks."""
        with (
            patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio"),
            patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"),
        ):
            manager = SellOrderManager(
                auth=mock_auth,
                positions_repo=mock_positions_repo,
                orders_repo=mock_orders_repo,
                user_id=1,
            )
            manager.active_sell_orders = {}
            manager.orders = Mock()
            manager.indicator_service = Mock()
            manager.indicator_service.calculate_ema9_realtime = Mock(return_value=2500.0)
            manager.indicator_service.price_service = Mock()
            manager.indicator_service.price_service.get_price = Mock(return_value=None)
            manager._register_order = Mock()
            manager.lowest_ema9 = {}
            manager._cleanup_rejected_orders = Mock()
            manager._check_and_retry_circuit_expansion = Mock(return_value=0)
            return manager

    def test_monitor_and_update_checks_missing_orders_when_empty(
        self, sell_manager, mock_positions_repo
    ):
        """Test that monitor_and_update() checks for missing orders when active_sell_orders is empty."""
        sell_manager.active_sell_orders = {}

        # Mock positions without orders
        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE"
        pos.closed_at = None
        mock_positions_repo.list.return_value = [pos]

        # Mock check and place methods
        sell_manager._check_positions_without_sell_orders = Mock(return_value=1)
        sell_manager._place_sell_orders_for_missing_positions = Mock(return_value=(0, []))

        # Mock other required methods
        sell_manager.orders.get_orders = Mock(return_value={"data": []})

        stats = sell_manager.monitor_and_update()

        # Verify missing orders were checked
        sell_manager._check_positions_without_sell_orders.assert_called_once()
        sell_manager._place_sell_orders_for_missing_positions.assert_called_once()
        assert "missing_orders_placed" in stats

    def test_monitor_and_update_places_missing_orders(self, sell_manager, mock_positions_repo):
        """Test that monitor_and_update() places orders for missing positions."""
        sell_manager.active_sell_orders = {}

        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE"
        pos.closed_at = None
        mock_positions_repo.list.return_value = [pos]

        sell_manager._check_positions_without_sell_orders = Mock(return_value=1)
        sell_manager._place_sell_orders_for_missing_positions = Mock(return_value=(1, []))

        sell_manager.orders.get_orders = Mock(return_value={"data": []})

        stats = sell_manager.monitor_and_update()

        assert stats["missing_orders_placed"] == 1

    def test_monitor_and_update_tracks_failed_positions(self, sell_manager, mock_positions_repo):
        """Test that monitor_and_update() tracks failed positions."""
        sell_manager.active_sell_orders = {}

        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE"
        pos.closed_at = None
        mock_positions_repo.list.return_value = [pos]

        failed_positions = [
            {
                "symbol": "RELIANCE",
                "reason": "EMA9 calculation failed",
                "entry_price": 2500.0,
                "quantity": 10,
            }
        ]

        sell_manager._check_positions_without_sell_orders = Mock(return_value=1)
        sell_manager._place_sell_orders_for_missing_positions = Mock(
            return_value=(0, failed_positions)
        )

        sell_manager.orders.get_orders = Mock(return_value={"data": []})

        stats = sell_manager.monitor_and_update()

        assert stats["missing_orders_placed"] == 0
        # Failed positions are tracked internally but not in stats
        sell_manager._place_sell_orders_for_missing_positions.assert_called_once()


class TestTelegramAlertEnhancements:
    """Test enhanced Telegram alerts with symbol details"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        return Mock()

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository."""
        return Mock()

    @pytest.fixture
    def mock_orders_repo(self):
        """Mock OrdersRepository."""
        return Mock()

    @pytest.fixture
    def mock_telegram_notifier(self):
        """Mock TelegramNotifier."""
        notifier = Mock()
        notifier.enabled = True
        return notifier

    @pytest.fixture
    def sell_manager(
        self, mock_auth, mock_positions_repo, mock_orders_repo, mock_telegram_notifier
    ):
        """Create SellOrderManager instance with mocks."""
        with (
            patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio"),
            patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"),
        ):
            manager = SellOrderManager(
                auth=mock_auth,
                positions_repo=mock_positions_repo,
                orders_repo=mock_orders_repo,
                user_id=1,
            )
            manager.telegram_notifier = mock_telegram_notifier
            manager.active_sell_orders = {}
            manager.orders = Mock()
            manager.indicator_service = Mock()
            manager.indicator_service.calculate_ema9_realtime = Mock(return_value=2500.0)
            manager.indicator_service.price_service = Mock()
            manager.indicator_service.price_service.get_price = Mock(return_value=None)
            manager._register_order = Mock()
            manager.lowest_ema9 = {}
            manager._cleanup_rejected_orders = Mock()
            manager._check_and_retry_circuit_expansion = Mock(return_value=0)
            return manager

    def test_sends_alert_when_no_orders_placed(
        self, sell_manager, mock_positions_repo, mock_telegram_notifier
    ):
        """Test that alert is sent when no orders could be placed."""
        sell_manager.active_sell_orders = {}

        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE"
        pos.closed_at = None
        mock_positions_repo.list.return_value = [pos]

        failed_positions = [
            {
                "symbol": "RELIANCE",
                "reason": "EMA9 calculation failed (Issue #3)",
                "entry_price": 2500.0,
                "quantity": 10,
            }
        ]

        sell_manager._check_positions_without_sell_orders = Mock(return_value=1)
        sell_manager._place_sell_orders_for_missing_positions = Mock(
            return_value=(0, failed_positions)
        )

        sell_manager.orders.get_orders = Mock(return_value={"data": []})

        sell_manager.monitor_and_update()

        # Verify alert was sent
        mock_telegram_notifier.notify_system_alert.assert_called()
        call_args = mock_telegram_notifier.notify_system_alert.call_args

        assert call_args.kwargs["alert_type"] == "SELL_ORDERS_MISSING"
        assert call_args.kwargs["severity"] == "WARNING"
        assert "RELIANCE" in call_args.kwargs["message_text"]
        assert "EMA9 calculation failed" in call_args.kwargs["message_text"]

    def test_sends_alert_when_partial_orders_placed(
        self, sell_manager, mock_positions_repo, mock_telegram_notifier
    ):
        """Test that alert is sent when some orders were placed but not all."""
        sell_manager.active_sell_orders = {}

        pos1 = Mock(spec=Positions)
        pos1.symbol = "RELIANCE-EQ"  # Full symbol after migration
        pos1.closed_at = None

        pos2 = Mock(spec=Positions)
        pos2.symbol = "TCS-EQ"  # Full symbol after migration
        pos2.closed_at = None

        mock_positions_repo.list.return_value = [pos1, pos2]

        failed_positions = [
            {
                "symbol": "TCS",
                "reason": "EMA9 calculation failed (Issue #3)",
                "entry_price": 3500.0,
                "quantity": 5,
            }
        ]

        sell_manager._check_positions_without_sell_orders = Mock(return_value=2)
        sell_manager._place_sell_orders_for_missing_positions = Mock(
            return_value=(1, failed_positions)
        )

        sell_manager.orders.get_orders = Mock(return_value={"data": []})

        sell_manager.monitor_and_update()

        # Verify partial success alert was sent
        mock_telegram_notifier.notify_system_alert.assert_called()
        call_args = mock_telegram_notifier.notify_system_alert.call_args

        assert call_args.kwargs["alert_type"] == "SELL_ORDERS_PARTIALLY_PLACED"
        assert "1/2" in call_args.kwargs["message_text"]  # 1 out of 2 successful
        assert "TCS" in call_args.kwargs["message_text"]

    def test_alert_includes_reason_summary(
        self, sell_manager, mock_positions_repo, mock_telegram_notifier
    ):
        """Test that alert includes summary of failure reasons."""
        sell_manager.active_sell_orders = {}

        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE"
        pos.closed_at = None
        mock_positions_repo.list.return_value = [pos]

        failed_positions = [
            {
                "symbol": "RELIANCE",
                "reason": "EMA9 calculation failed (Issue #3)",
                "entry_price": 2500.0,
                "quantity": 10,
            }
        ]

        sell_manager._check_positions_without_sell_orders = Mock(return_value=1)
        sell_manager._place_sell_orders_for_missing_positions = Mock(
            return_value=(0, failed_positions)
        )

        sell_manager.orders.get_orders = Mock(return_value={"data": []})

        sell_manager.monitor_and_update()

        call_args = mock_telegram_notifier.notify_system_alert.call_args
        message = call_args.kwargs["message_text"]

        # Verify message includes reason summary
        assert "Reasons:" in message
        assert "EMA9 calculation failed" in message

    def test_alert_limits_symbol_list(
        self, sell_manager, mock_positions_repo, mock_telegram_notifier
    ):
        """Test that alert limits symbol list to 10 and shows '+X more'."""
        sell_manager.active_sell_orders = {}

        # Create 15 positions
        positions = []
        for i in range(15):
            pos = Mock(spec=Positions)
            pos.symbol = f"STOCK{i}"
            pos.closed_at = None
            positions.append(pos)

        mock_positions_repo.list.return_value = positions

        # Create 15 failed positions
        failed_positions = [
            {
                "symbol": f"STOCK{i}",
                "reason": "EMA9 calculation failed",
                "entry_price": 1000.0,
                "quantity": 10,
            }
            for i in range(15)
        ]

        sell_manager._check_positions_without_sell_orders = Mock(return_value=15)
        sell_manager._place_sell_orders_for_missing_positions = Mock(
            return_value=(0, failed_positions)
        )

        sell_manager.orders.get_orders = Mock(return_value={"data": []})

        sell_manager.monitor_and_update()

        call_args = mock_telegram_notifier.notify_system_alert.call_args
        message = call_args.kwargs["message_text"]

        # Verify message shows first 10 and "+5 more"
        assert "+5 more" in message
        # Verify first 10 symbols are shown
        for i in range(10):
            assert f"STOCK{i}" in message

    def test_no_alert_when_telegram_notifier_disabled(
        self, sell_manager, mock_positions_repo, mock_telegram_notifier
    ):
        """Test that no alert is sent when Telegram notifier is disabled."""
        sell_manager.telegram_notifier.enabled = False
        sell_manager.active_sell_orders = {}

        pos = Mock(spec=Positions)
        pos.symbol = "RELIANCE"
        pos.closed_at = None
        mock_positions_repo.list.return_value = [pos]

        failed_positions = [
            {
                "symbol": "RELIANCE",
                "reason": "EMA9 calculation failed",
                "entry_price": 2500.0,
                "quantity": 10,
            }
        ]

        sell_manager._check_positions_without_sell_orders = Mock(return_value=1)
        sell_manager._place_sell_orders_for_missing_positions = Mock(
            return_value=(0, failed_positions)
        )

        sell_manager.orders.get_orders = Mock(return_value={"data": []})

        # Should not raise error even if notifier is disabled
        stats = sell_manager.monitor_and_update()

        assert stats["missing_orders_placed"] == 0
