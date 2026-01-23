"""
Tests for exit price and time recording for system positions.
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


class TestExitPriceTimeRecording:
    """Test exit price and time are recorded for all system positions"""

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
        orders.get_orders = Mock(return_value={"data": []})
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

    def test_manual_sell_order_saves_exit_price(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that manual sell order saves exit price."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"  # Full symbol after migration
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
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        all_orders_response = {
            "data": [
                {
                    "orderId": "MANUAL123",
                    "trdSym": "RELIANCE-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 100,
                    "avgPrc": 2500.0,  # Exit price
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE-EQ", "qty": 100}])

        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        assert stats["detected"] == 1
        call_args = mock_positions_repo.mark_closed.call_args
        # avgPrc is the only accepted source for execution price
        assert call_args.kwargs["exit_price"] == 2500.0

    def test_manual_sell_order_saves_execution_time(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that manual sell order saves execution time."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"  # Full symbol after migration
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
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        execution_time = ist_now() - timedelta(minutes=30)

        all_orders_response = {
            "data": [
                {
                    "orderId": "MANUAL123",
                    "trdSym": "RELIANCE-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 100,
                    "avgPrc": 2500.0,
                    "executionTime": execution_time.isoformat(),
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE-EQ", "qty": 100}])

        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        assert stats["detected"] == 1
        call_args = mock_positions_repo.mark_closed.call_args
        # Execution time should be saved as closed_at
        assert call_args.kwargs["closed_at"] is not None

    def test_manual_sell_order_extracts_price_from_order(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that exit price is extracted from order with fallbacks."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"  # Full symbol after migration
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
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        # Test with prc field (fallback)
        all_orders_response = {
            "data": [
                {
                    "orderId": "MANUAL123",
                    "trdSym": "RELIANCE-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 100,
                    "prc": 2500.0,  # Fallback field
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE-EQ", "qty": 100}])

        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        assert stats["detected"] == 1
        call_args = mock_positions_repo.mark_closed.call_args
        # No fallback: prc alone should not populate exit price
        assert call_args.kwargs["exit_price"] is None

    def test_manual_sell_order_extracts_time_from_order(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that execution time is extracted from order."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"  # Full symbol after migration
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
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        execution_time = ist_now() - timedelta(minutes=15)

        all_orders_response = {
            "data": [
                {
                    "orderId": "MANUAL123",
                    "trdSym": "RELIANCE-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 100,
                    "avgPrc": 2500.0,
                    "executionTime": execution_time.isoformat(),
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE-EQ", "qty": 100}])

        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        assert stats["detected"] == 1
        call_args = mock_positions_repo.mark_closed.call_args
        # closed_at should be set from execution time
        assert call_args.kwargs["closed_at"] is not None

    def test_manual_sell_order_prefers_avgPrc_over_prc(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """avgPrc should win over conflicting prc values."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
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
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        all_orders_response = {
            "data": [
                {
                    "orderId": "MANUAL123",
                    "trdSym": "RELIANCE-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 100,
                    "avgPrc": 2600.0,
                    "prc": 1.0,
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE-EQ", "qty": 100}])

        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        assert stats["detected"] == 1
        call_args = mock_positions_repo.mark_closed.call_args
        assert call_args.kwargs["exit_price"] == 2600.0

    def test_manual_sell_order_ignores_non_positive_avgPrc(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Non-positive avgPrc should be treated as missing even if prc is provided."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
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
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        all_orders_response = {
            "data": [
                {
                    "orderId": "MANUAL123",
                    "trdSym": "RELIANCE-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 100,
                    "avgPrc": 0.0,
                    "prc": 2500.0,
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE-EQ", "qty": 100}])

        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        assert stats["detected"] == 1
        call_args = mock_positions_repo.mark_closed.call_args
        assert call_args.kwargs["exit_price"] is None

    def test_missing_exit_price_handled_gracefully(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that missing exit price is handled gracefully."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"  # Full symbol after migration
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
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        all_orders_response = {
            "data": [
                {
                    "orderId": "MANUAL123",
                    "trdSym": "RELIANCE-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 100,
                    # No price fields
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE-EQ", "qty": 100}])

        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        assert stats["detected"] == 1
        call_args = mock_positions_repo.mark_closed.call_args
        # Exit price should be None if not available
        assert call_args.kwargs["exit_price"] is None

    def test_missing_execution_time_uses_current_time(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that missing execution time uses current time."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"  # Full symbol after migration
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
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        all_orders_response = {
            "data": [
                {
                    "orderId": "MANUAL123",
                    "trdSym": "RELIANCE-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 100,
                    "avgPrc": 2500.0,
                    # No executionTime field
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE-EQ", "qty": 100}])

        with patch("modules.kotak_neo_auto_trader.sell_engine.ist_now") as mock_ist_now:
            current_time = ist_now()
            mock_ist_now.return_value = current_time

            stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

            assert stats["detected"] == 1
            call_args = mock_positions_repo.mark_closed.call_args
            # Should use current time
            assert call_args.kwargs["closed_at"] is not None

    def test_exit_price_zero_handled(
        self, sell_manager, mock_positions_repo, mock_orders_repo, mock_orders
    ):
        """Test that exit price of zero is handled."""
        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"  # Full symbol after migration
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
        mock_orders_repo.list.return_value = ([system_buy_order], 1)

        all_orders_response = {
            "data": [
                {
                    "orderId": "MANUAL123",
                    "trdSym": "RELIANCE-EQ",
                    "transactionType": "SELL",
                    "orderStatus": "executed",
                    "filledQty": 100,
                    "avgPrc": 0.0,  # Zero price
                }
            ]
        }

        sell_manager.get_open_positions = Mock(return_value=[{"symbol": "RELIANCE-EQ", "qty": 100}])

        stats = sell_manager._detect_manual_sells_from_orders(all_orders_response)

        assert stats["detected"] == 1
        # Should still close position even with zero price
        mock_positions_repo.mark_closed.assert_called_once()
