"""
Tests for exit_reason tracking in sell orders and position closure (Phase 0.2).

Tests verify that:
1. System sell orders store exit_reason in order_metadata as "TARGET_HIT"
2. Manual position closures retrieve exit_reason from sell order metadata
3. Exit reason defaults to "MANUAL" when sell order not found or has no metadata
4. Position closure correctly populates exit_reason field
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


class TestExitReasonInOrderMetadata:
    """Test that exit_reason is stored in order metadata when placing sell orders"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        auth = Mock()
        # Prevent downstream components from treating auth as "not authenticated"
        auth.client = Mock()
        return auth

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository."""
        return Mock()

    @pytest.fixture
    def mock_orders_repo(self):
        """Mock OrdersRepository."""
        return Mock()

    @pytest.fixture
    def mock_broker_orders(self):
        """Mock broker Orders API."""
        orders = Mock()
        orders.place_limit_sell = Mock(return_value={"nOrdNo": "12345"})
        return orders

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_positions_repo, mock_orders_repo, mock_broker_orders):
        """Create SellOrderManager with mocks."""
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
            manager.orders = mock_broker_orders
            manager.scrip_master = Mock()
            manager.scrip_master.symbol_map = {}
            # round_to_tick_size() may consult scrip master; default Mock breaks `<= 0` checks
            manager.scrip_master.get_tick_size = Mock(return_value=None)
            manager.strategy_config = Mock()
            manager.strategy_config.default_exchange = "NSE"
            # Not relevant to these tests; keep disabled to avoid side effects.
            manager.targets_repo = None
            return manager

    def test_place_sell_order_stores_target_hit_in_metadata(
        self, sell_manager, mock_orders_repo, mock_broker_orders
    ):
        """Test that place_sell_order() stores exit_reason='TARGET_HIT' in metadata."""
        # Setup: Trade entry
        trade = {
            "placed_symbol": "RELIANCE-EQ",
            "symbol": "RELIANCE-EQ",
            "ticker": "RELIANCE.NS",
            "qty": 100,
        }
        target_price = 2500.0

        # Execute
        order_id = sell_manager.place_sell_order(trade, target_price)

        # Verify: Order ID returned
        assert order_id == "12345"

        # Verify: orders_repo.create_amo() was called with exit_reason in metadata
        mock_orders_repo.create_amo.assert_called_once()
        call_kwargs = mock_orders_repo.create_amo.call_args.kwargs

        # Verify exit_reason in metadata
        assert "order_metadata" in call_kwargs
        metadata = call_kwargs["order_metadata"]
        assert metadata.get("exit_reason") == "TARGET_HIT"
        assert metadata.get("source") == "sell_engine_run_at_market_open"
        assert metadata.get("ticker") == "RELIANCE.NS"

    def test_place_sell_order_metadata_includes_all_fields(
        self, sell_manager, mock_orders_repo, mock_broker_orders
    ):
        """Test that order metadata has all expected fields."""
        trade = {
            "placed_symbol": "TCS-EQ",
            "symbol": "TCS-EQ",
            "ticker": "TCS.NS",
            "qty": 50,
        }
        target_price = 3500.0

        sell_manager.place_sell_order(trade, target_price)

        mock_orders_repo.create_amo.assert_called_once()
        metadata = mock_orders_repo.create_amo.call_args.kwargs["order_metadata"]

        # Verify all expected fields
        assert metadata["exit_reason"] == "TARGET_HIT"
        assert metadata["ticker"] == "TCS.NS"
        assert "exchange" in metadata
        assert metadata["base_symbol"] == "TCS"
        assert metadata["full_symbol"] == "TCS-EQ"
        assert metadata["source"] == "sell_engine_run_at_market_open"


class TestManualSellExitReasonRetrieval:
    """Test that exit_reason is correctly retrieved when position closes"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        auth = Mock()
        auth.client = Mock()
        return auth

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository."""
        return Mock()

    @pytest.fixture
    def mock_orders_repo(self):
        """Mock OrdersRepository."""
        return Mock()

    @pytest.fixture
    def mock_broker_orders(self):
        """Mock broker Orders API."""
        orders = Mock()
        orders.get_orders = Mock(return_value={"data": []})
        return orders

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_positions_repo, mock_orders_repo, mock_broker_orders):
        """Create SellOrderManager with mocks."""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio"):
            manager = SellOrderManager(
                auth=mock_auth,
                positions_repo=mock_positions_repo,
                orders_repo=mock_orders_repo,
                user_id=1,
            )
            manager.orders = mock_broker_orders
            manager.get_open_positions = Mock(return_value=[])
            return manager

    def test_manual_sell_retrieves_target_hit_from_order_metadata(
        self, sell_manager, mock_positions_repo, mock_orders_repo
    ):
        """Test that manual sell closure retrieves exit_reason='TARGET_HIT' from order metadata."""
        # Setup: System position
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
        position.quantity = 100.0
        position.closed_at = None
        position.opened_at = ist_now() - timedelta(hours=2)

        mock_positions_repo.list.return_value = [position]
        mock_positions_repo.get_by_symbol.return_value = position

        # Setup: System buy order
        system_buy_order = Mock(spec=Orders)
        system_buy_order.side = "buy"
        system_buy_order.symbol = "RELIANCE-EQ"
        system_buy_order.orig_source = "signal"
        system_buy_order.execution_time = position.opened_at
        # Sell engine expects OrdersRepository.list() to return (items, total_count)
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        # Setup: Sell order with TARGET_HIT in metadata
        sell_order = Mock(spec=Orders)
        sell_order.order_metadata = {"exit_reason": "TARGET_HIT"}
        mock_orders_repo.get_by_broker_order_id.return_value = sell_order

        # Setup: Manual sell in orders response
        all_orders_response = {
            "data": [
                {
                    "orderId": "BROKER_SELL_123",
                    "trdSym": "RELIANCE-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 100,
                    "avgPrc": 2500.0,
                    "executionTime": "2025-12-16T10:30:00+05:30",
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE-EQ", "qty": 100}])

        # Execute
        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        # Verify: Position marked as closed
        assert stats["closed"] == 1

        # Verify: mark_closed was called with exit_reason="TARGET_HIT"
        mock_positions_repo.mark_closed.assert_called_once()
        call_kwargs = mock_positions_repo.mark_closed.call_args.kwargs
        assert call_kwargs["exit_reason"] == "TARGET_HIT"
        assert call_kwargs["exit_price"] == 2500.0

    def test_manual_sell_defaults_to_manual_when_order_not_found(
        self, sell_manager, mock_positions_repo, mock_orders_repo
    ):
        """Test that exit_reason defaults to 'MANUAL' when sell order not found."""
        # Setup: System position
        position = Mock(spec=Positions)
        position.symbol = "TCS-EQ"
        position.quantity = 50.0
        position.closed_at = None
        position.opened_at = ist_now() - timedelta(hours=1)

        mock_positions_repo.list.return_value = [position]
        mock_positions_repo.get_by_symbol.return_value = position

        # Setup: System buy order
        system_buy_order = Mock(spec=Orders)
        system_buy_order.side = "buy"
        system_buy_order.symbol = "TCS-EQ"
        system_buy_order.orig_source = "signal"
        system_buy_order.execution_time = position.opened_at
        # Sell engine expects OrdersRepository.list() to return (items, total_count)
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        # Setup: Sell order NOT found in DB
        mock_orders_repo.get_by_broker_order_id.return_value = None

        # Setup: Manual sell in orders response
        all_orders_response = {
            "data": [
                {
                    "orderId": "UNKNOWN_SELL_456",
                    "trdSym": "TCS-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 50,
                    "avgPrc": 3500.0,
                    "executionTime": "2025-12-16T11:00:00+05:30",
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "TCS-EQ", "qty": 50}])

        # Execute
        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        # Verify: Position marked as closed with default exit_reason
        assert stats["closed"] == 1
        mock_positions_repo.mark_closed.assert_called_once()
        call_kwargs = mock_positions_repo.mark_closed.call_args.kwargs
        assert call_kwargs["exit_reason"] == "MANUAL"

    def test_manual_sell_defaults_to_manual_when_metadata_is_none(
        self, sell_manager, mock_positions_repo, mock_orders_repo
    ):
        """Test that exit_reason defaults to 'MANUAL' when order_metadata is None."""
        # Setup: System position
        position = Mock(spec=Positions)
        position.symbol = "INFY-EQ"
        position.quantity = 75.0
        position.closed_at = None
        position.opened_at = ist_now() - timedelta(hours=3)

        mock_positions_repo.list.return_value = [position]
        mock_positions_repo.get_by_symbol.return_value = position

        # Setup: System buy order
        system_buy_order = Mock(spec=Orders)
        system_buy_order.side = "buy"
        system_buy_order.symbol = "INFY-EQ"
        system_buy_order.orig_source = "signal"
        system_buy_order.execution_time = position.opened_at
        # Sell engine expects OrdersRepository.list() to return (items, total_count)
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        # Setup: Sell order found but with NO metadata
        sell_order = Mock(spec=Orders)
        sell_order.order_metadata = None  # No metadata
        mock_orders_repo.get_by_broker_order_id.return_value = sell_order

        # Setup: Manual sell in orders response
        all_orders_response = {
            "data": [
                {
                    "orderId": "NO_METADATA_789",
                    "trdSym": "INFY-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 75,
                    "avgPrc": 1800.0,
                    "executionTime": "2025-12-16T14:30:00+05:30",
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "INFY-EQ", "qty": 75}])

        # Execute
        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        # Verify: Position marked as closed with default exit_reason
        assert stats["closed"] == 1
        mock_positions_repo.mark_closed.assert_called_once()
        call_kwargs = mock_positions_repo.mark_closed.call_args.kwargs
        assert call_kwargs["exit_reason"] == "MANUAL"

    def test_manual_sell_handles_exception_gracefully(
        self, sell_manager, mock_positions_repo, mock_orders_repo
    ):
        """Test that exception in retrieving sell order is handled gracefully."""
        # Setup: System position
        position = Mock(spec=Positions)
        position.symbol = "WIPRO-EQ"
        position.quantity = 25.0
        position.closed_at = None
        position.opened_at = ist_now() - timedelta(hours=2)

        mock_positions_repo.list.return_value = [position]
        mock_positions_repo.get_by_symbol.return_value = position

        # Setup: System buy order
        system_buy_order = Mock(spec=Orders)
        system_buy_order.side = "buy"
        system_buy_order.symbol = "WIPRO-EQ"
        system_buy_order.orig_source = "signal"
        system_buy_order.execution_time = position.opened_at
        # Sell engine expects OrdersRepository.list() to return (items, total_count)
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        # Setup: get_by_broker_order_id raises exception
        mock_orders_repo.get_by_broker_order_id.side_effect = Exception("DB error")

        # Setup: Manual sell in orders response
        all_orders_response = {
            "data": [
                {
                    "orderId": "ERROR_ORDER_999",
                    "trdSym": "WIPRO-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 25,
                    "avgPrc": 400.0,
                    "executionTime": "2025-12-16T15:00:00+05:30",
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "WIPRO-EQ", "qty": 25}])

        # Execute - should not raise exception
        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        # Verify: Position still marked as closed with fallback exit_reason
        assert stats["closed"] == 1
        mock_positions_repo.mark_closed.assert_called_once()
        call_kwargs = mock_positions_repo.mark_closed.call_args.kwargs
        assert call_kwargs["exit_reason"] == "MANUAL"


class TestExitReasonIntegration:
    """Integration tests combining sell order placement and position closure"""

    @pytest.fixture
    def mock_auth(self):
        """Mock KotakNeoAuth."""
        auth = Mock()
        auth.client = Mock()
        return auth

    @pytest.fixture
    def mock_positions_repo(self):
        """Mock PositionsRepository."""
        return Mock()

    @pytest.fixture
    def mock_orders_repo(self):
        """Mock OrdersRepository."""
        return Mock()

    @pytest.fixture
    def mock_broker_orders(self):
        """Mock broker Orders API."""
        orders = Mock()
        orders.place_limit_sell = Mock(return_value={"nOrdNo": "PLACE_12345"})
        orders.get_orders = Mock(return_value={"data": []})
        return orders

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_positions_repo, mock_orders_repo, mock_broker_orders):
        """Create SellOrderManager with mocks."""
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
            manager.orders = mock_broker_orders
            manager.scrip_master = Mock()
            manager.scrip_master.symbol_map = {}
            manager.scrip_master.get_tick_size = Mock(return_value=None)
            manager.get_open_positions = Mock(return_value=[])
            manager.strategy_config = Mock()
            manager.strategy_config.default_exchange = "NSE"
            manager.targets_repo = None
            return manager

    def test_end_to_end_target_hit_exit_reason(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_broker_orders
    ):
        """Test complete flow: place sell order -> detect manual sell -> mark closed with TARGET_HIT."""
        # Step 1: Place sell order (system-initiated)
        trade = {
            "placed_symbol": "MARUTI-EQ",
            "symbol": "MARUTI-EQ",
            "ticker": "MARUTI.NS",
            "qty": 10,
        }
        order_id = sell_manager.place_sell_order(trade, 8500.0)

        # Verify: Order metadata includes exit_reason="TARGET_HIT"
        assert order_id == "PLACE_12345"
        mock_orders_repo.create_amo.assert_called()
        placed_metadata = mock_orders_repo.create_amo.call_args.kwargs["order_metadata"]
        assert placed_metadata["exit_reason"] == "TARGET_HIT"

        # Step 2: Setup position and detect manual sell
        position = Mock(spec=Positions)
        position.symbol = "MARUTI-EQ"
        position.quantity = 10.0
        position.closed_at = None
        position.opened_at = ist_now() - timedelta(hours=1)

        mock_positions_repo.list.return_value = [position]
        mock_positions_repo.get_by_symbol.return_value = position

        system_buy_order = Mock(spec=Orders)
        system_buy_order.side = "buy"
        system_buy_order.symbol = "MARUTI-EQ"
        system_buy_order.orig_source = "signal"
        system_buy_order.execution_time = position.opened_at
        # Sell engine expects OrdersRepository.list() to return (items, total_count)
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        # Step 3: Setup sell order with metadata
        sell_order = Mock(spec=Orders)
        sell_order.order_metadata = placed_metadata
        mock_orders_repo.get_by_broker_order_id.return_value = sell_order

        # Step 4: Detect manual sell (user executed the system order)
        all_orders_response = {
            "data": [
                {
                    "orderId": "PLACE_12345",
                    "trdSym": "MARUTI-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 10,
                    "avgPrc": 8500.0,
                    "executionTime": ist_now().isoformat(),
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "MARUTI-EQ", "qty": 10}])

        # Execute
        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        # Verify: Position closed with TARGET_HIT exit reason
        assert stats["closed"] == 1
        mock_positions_repo.mark_closed.assert_called_once()
        close_kwargs = mock_positions_repo.mark_closed.call_args.kwargs
        assert close_kwargs["exit_reason"] == "TARGET_HIT"
        assert close_kwargs["exit_price"] == 8500.0
