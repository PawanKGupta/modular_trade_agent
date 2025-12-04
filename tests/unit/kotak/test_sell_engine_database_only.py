"""
Unit tests for SellOrderManager database-only position tracking

Tests verify the migration from file-based to database-only position tracking.
"""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from src.infrastructure.db.models import OrderStatus as DbOrderStatus
from src.infrastructure.db.timezone_utils import ist_now


class TestSellOrderManagerDatabaseOnlyInitialization:
    """Test SellOrderManager initialization with database repositories"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_init_with_database_repos(self, mock_scrip_master, mock_auth):
        """Test that SellOrderManager can be initialized with database repositories"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        mock_positions_repo = Mock()
        mock_orders_repo = Mock()
        user_id = 2

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=user_id,
            orders_repo=mock_orders_repo,
        )

        assert manager.positions_repo == mock_positions_repo
        assert manager.orders_repo == mock_orders_repo
        assert manager.user_id == user_id
        # PositionLoader should not exist
        assert not hasattr(manager, "position_loader")

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_init_without_database_repos(self, mock_scrip_master, mock_auth):
        """Test that SellOrderManager can be initialized without database repos
        (backward compatibility)"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Should not raise error during init
        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        assert manager.positions_repo is None
        assert manager.user_id is None
        # PositionLoader should not exist
        assert not hasattr(manager, "position_loader")


class TestSellOrderManagerGetOpenPositionsDatabaseOnly:
    """Test get_open_positions() with database-only implementation"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_with_database_repos(self, mock_scrip_master, mock_auth):
        """Test that get_open_positions() uses PositionsRepository"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create mock position
        mock_position = Mock()
        mock_position.symbol = "IFBIND"
        mock_position.quantity = 10.0
        mock_position.avg_price = 1500.0
        mock_position.opened_at = ist_now()
        mock_position.closed_at = None  # Open position

        # Create mock positions repository
        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = [mock_position]

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
        )

        # Call get_open_positions
        result = manager.get_open_positions()

        # Verify PositionsRepository was called
        mock_positions_repo.list.assert_called_once_with(2)

        # Verify result
        assert len(result) == 1
        assert result[0]["symbol"] == "IFBIND"
        assert result[0]["qty"] == 10.0
        assert result[0]["entry_price"] == 1500.0
        assert result[0]["status"] == "open"
        assert result[0]["ticker"] == "IFBIND.NS"  # Default ticker
        assert result[0]["placed_symbol"] == "IFBIND-EQ"  # Default placed_symbol

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_filters_closed_positions(self, mock_scrip_master, mock_auth):
        """Test that get_open_positions() filters out closed positions"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create mock positions (one open, one closed)
        mock_open_position = Mock()
        mock_open_position.symbol = "RELIANCE"
        mock_open_position.quantity = 10.0
        mock_open_position.avg_price = 2500.0
        mock_open_position.opened_at = ist_now()
        mock_open_position.closed_at = None  # Open position

        mock_closed_position = Mock()
        mock_closed_position.symbol = "TCS"
        mock_closed_position.quantity = 5.0
        mock_closed_position.avg_price = 3500.0
        mock_closed_position.opened_at = ist_now()
        mock_closed_position.closed_at = ist_now()  # Closed position

        # Create mock positions repository
        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = [mock_open_position, mock_closed_position]

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
        )

        # Call get_open_positions
        result = manager.get_open_positions()

        # Verify only open position is returned
        assert len(result) == 1
        assert result[0]["symbol"] == "RELIANCE"
        # Note: closed_at is not included in returned dict - it's only used for filtering

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_with_orders_repo_metadata_enrichment(
        self, mock_scrip_master, mock_auth
    ):
        """Test that get_open_positions() enriches metadata from OrdersRepository"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create mock position
        mock_position = Mock()
        mock_position.symbol = "IFBIND"
        mock_position.quantity = 10.0
        mock_position.avg_price = 1500.0
        mock_position.opened_at = ist_now()
        mock_position.closed_at = None

        # Create mock ONGOING order with metadata
        mock_order = Mock()
        mock_order.side = "buy"
        mock_order.symbol = "IFBIND-EQ"
        mock_order.execution_qty = 10.0
        mock_order.execution_price = 1500.0
        mock_order.execution_time = ist_now()
        mock_order.filled_at = ist_now()
        mock_order.placed_at = ist_now()
        mock_order.order_metadata = {"ticker": "IFBIND.NS"}

        # Create mock repositories
        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = [mock_position]

        mock_orders_repo = Mock()
        mock_orders_repo.list.return_value = [mock_order]

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
            orders_repo=mock_orders_repo,
        )

        # Call get_open_positions
        result = manager.get_open_positions()

        # Verify OrdersRepository was called for metadata enrichment
        mock_orders_repo.list.assert_called_once()
        call_args = mock_orders_repo.list.call_args
        assert call_args[0][0] == 2  # user_id
        assert call_args[1]["status"] == DbOrderStatus.ONGOING

        # Verify metadata was enriched
        assert len(result) == 1
        assert result[0]["ticker"] == "IFBIND.NS"  # From order metadata
        assert result[0]["placed_symbol"] == "IFBIND-EQ"  # From order symbol

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_without_orders_repo(self, mock_scrip_master, mock_auth):
        """Test that get_open_positions() works without orders_repo (uses defaults)"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create mock position
        mock_position = Mock()
        mock_position.symbol = "RELIANCE"
        mock_position.quantity = 10.0
        mock_position.avg_price = 2500.0
        mock_position.opened_at = ist_now()
        mock_position.closed_at = None

        # Create mock positions repository
        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = [mock_position]

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
            orders_repo=None,  # No orders_repo
        )

        # Call get_open_positions
        result = manager.get_open_positions()

        # Verify result uses default values
        assert len(result) == 1
        assert result[0]["ticker"] == "RELIANCE.NS"  # Default ticker
        assert result[0]["placed_symbol"] == "RELIANCE-EQ"  # Default placed_symbol

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_empty_positions(self, mock_scrip_master, mock_auth):
        """Test that get_open_positions() returns empty list when no positions"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create mock positions repository with empty list
        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = []

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
        )

        # Call get_open_positions
        result = manager.get_open_positions()

        # Verify result
        assert result == []
        assert isinstance(result, list)

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_without_positions_repo_raises_error(
        self, mock_scrip_master, mock_auth
    ):
        """Test that get_open_positions() raises ValueError without positions_repo"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Call get_open_positions - should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            manager.get_open_positions()

        assert "PositionsRepository and user_id are required" in str(exc_info.value)

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_without_user_id_raises_error(self, mock_scrip_master, mock_auth):
        """Test that get_open_positions() raises ValueError without user_id"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        mock_positions_repo = Mock()

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=None,  # No user_id
        )

        # Call get_open_positions - should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            manager.get_open_positions()

        assert "PositionsRepository and user_id are required" in str(exc_info.value)

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_metadata_enrichment_handles_errors(
        self, mock_scrip_master, mock_auth
    ):
        """Test that metadata enrichment handles errors gracefully"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create mock position
        mock_position = Mock()
        mock_position.symbol = "RELIANCE"
        mock_position.quantity = 10.0
        mock_position.avg_price = 2500.0
        mock_position.opened_at = ist_now()
        mock_position.closed_at = None

        # Create mock repositories
        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = [mock_position]

        mock_orders_repo = Mock()
        mock_orders_repo.list.side_effect = Exception("Database error")

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
            orders_repo=mock_orders_repo,
        )

        # Call get_open_positions - should not raise, should use defaults
        result = manager.get_open_positions()

        # Verify result uses default values (error handled gracefully)
        assert len(result) == 1
        assert result[0]["ticker"] == "RELIANCE.NS"  # Default ticker
        assert result[0]["placed_symbol"] == "RELIANCE-EQ"  # Default placed_symbol

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_multiple_positions(self, mock_scrip_master, mock_auth):
        """Test that get_open_positions() handles multiple positions correctly"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create multiple mock positions
        positions = []
        for i, symbol in enumerate(["RELIANCE", "TCS", "INFY"]):
            mock_position = Mock()
            mock_position.symbol = symbol
            mock_position.quantity = 10.0 + i
            mock_position.avg_price = 2000.0 + (i * 500)
            mock_position.opened_at = ist_now()
            mock_position.closed_at = None
            positions.append(mock_position)

        # Create mock positions repository
        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = positions

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
        )

        # Call get_open_positions
        result = manager.get_open_positions()

        # Verify all positions are returned
        assert len(result) == 3
        assert result[0]["symbol"] == "RELIANCE"
        assert result[1]["symbol"] == "TCS"
        assert result[2]["symbol"] == "INFY"

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_metadata_enrichment_matching_symbol(
        self, mock_scrip_master, mock_auth
    ):
        """Test that metadata enrichment matches symbols correctly"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create mock position
        mock_position = Mock()
        mock_position.symbol = "IFBIND"
        mock_position.quantity = 10.0
        mock_position.avg_price = 1500.0
        mock_position.opened_at = ist_now()
        mock_position.closed_at = None

        # Create mock ONGOING orders (one matching, one not)
        mock_matching_order = Mock()
        mock_matching_order.side = "buy"
        mock_matching_order.symbol = "IFBIND-EQ"
        mock_matching_order.execution_qty = 10.0
        mock_matching_order.execution_price = 1500.0
        mock_matching_order.execution_time = ist_now()
        mock_matching_order.filled_at = ist_now()
        mock_matching_order.placed_at = ist_now()
        mock_matching_order.order_metadata = {"ticker": "IFBIND.NS"}

        mock_non_matching_order = Mock()
        mock_non_matching_order.side = "buy"
        mock_non_matching_order.symbol = "RELIANCE-EQ"  # Different symbol
        mock_non_matching_order.execution_qty = 5.0
        mock_non_matching_order.execution_price = 2500.0
        mock_non_matching_order.execution_time = ist_now()
        mock_non_matching_order.filled_at = ist_now()
        mock_non_matching_order.placed_at = ist_now()
        mock_non_matching_order.order_metadata = {"ticker": "RELIANCE.NS"}

        # Create mock repositories
        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = [mock_position]

        mock_orders_repo = Mock()
        mock_orders_repo.list.return_value = [mock_matching_order, mock_non_matching_order]

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
            orders_repo=mock_orders_repo,
        )

        # Call get_open_positions
        result = manager.get_open_positions()

        # Verify matching order's metadata was used
        assert len(result) == 1
        assert result[0]["symbol"] == "IFBIND"
        assert result[0]["ticker"] == "IFBIND.NS"  # From matching order
        assert result[0]["placed_symbol"] == "IFBIND-EQ"  # From matching order

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_metadata_enrichment_only_buy_orders(
        self, mock_scrip_master, mock_auth
    ):
        """Test that metadata enrichment only uses buy orders"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create mock position
        mock_position = Mock()
        mock_position.symbol = "RELIANCE"
        mock_position.quantity = 10.0
        mock_position.avg_price = 2500.0
        mock_position.opened_at = ist_now()
        mock_position.closed_at = None

        # Create mock ONGOING orders (one buy, one sell)
        mock_buy_order = Mock()
        mock_buy_order.side = "buy"
        mock_buy_order.symbol = "RELIANCE-EQ"
        mock_buy_order.execution_qty = 10.0
        mock_buy_order.execution_price = 2500.0
        mock_buy_order.execution_time = ist_now()
        mock_buy_order.filled_at = ist_now()
        mock_buy_order.placed_at = ist_now()
        mock_buy_order.order_metadata = {"ticker": "RELIANCE.NS"}

        mock_sell_order = Mock()
        mock_sell_order.side = "sell"  # Sell order should be ignored
        mock_sell_order.symbol = "RELIANCE-EQ"
        mock_sell_order.execution_qty = 10.0
        mock_sell_order.execution_price = 2600.0
        mock_sell_order.execution_time = ist_now()
        mock_sell_order.filled_at = ist_now()
        mock_sell_order.placed_at = ist_now()
        mock_sell_order.order_metadata = {"ticker": "RELIANCE.NS"}

        # Create mock repositories
        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = [mock_position]

        mock_orders_repo = Mock()
        mock_orders_repo.list.return_value = [mock_buy_order, mock_sell_order]

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
            orders_repo=mock_orders_repo,
        )

        # Call get_open_positions
        result = manager.get_open_positions()

        # Verify buy order's metadata was used (sell order ignored)
        assert len(result) == 1
        assert result[0]["symbol"] == "RELIANCE"
        assert result[0]["ticker"] == "RELIANCE.NS"  # From buy order
        assert result[0]["placed_symbol"] == "RELIANCE-EQ"  # From buy order


class TestSellOrderManagerRunAtMarketOpenDatabaseOnly:
    """Test run_at_market_open() with database-only implementation"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.SellOrderManager.get_existing_sell_orders")
    @patch("modules.kotak_neo_auto_trader.sell_engine.SellOrderManager.get_current_ema9")
    @patch("modules.kotak_neo_auto_trader.sell_engine.SellOrderManager.place_sell_order")
    def test_run_at_market_open_with_database_positions(
        self,
        mock_place_sell_order,
        mock_get_ema9,
        mock_get_existing_orders,
        mock_scrip_master,
        mock_auth,
    ):
        """Test that run_at_market_open() places orders for database positions"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create mock position
        mock_position = Mock()
        mock_position.symbol = "IFBIND"
        mock_position.quantity = 10.0
        mock_position.avg_price = 1500.0
        mock_position.opened_at = ist_now()
        mock_position.closed_at = None

        # Create mock repositories
        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = [mock_position]

        # Mock methods
        mock_get_existing_orders.return_value = {}  # No existing orders
        mock_get_ema9.return_value = 1600.0  # EMA9 above entry
        mock_place_sell_order.return_value = "SELL123"

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
        )

        # Call run_at_market_open
        orders_placed = manager.run_at_market_open()

        # Verify get_open_positions was called (via run_at_market_open)
        mock_positions_repo.list.assert_called_once_with(2)

        # Verify order was placed
        assert orders_placed == 1
        mock_place_sell_order.assert_called_once()

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_run_at_market_open_no_positions(self, mock_scrip_master, mock_auth):
        """Test that run_at_market_open() returns 0 when no positions"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create mock positions repository with empty list
        mock_positions_repo = Mock()
        mock_positions_repo.list.return_value = []

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
        )

        # Call run_at_market_open
        orders_placed = manager.run_at_market_open()

        # Verify no orders were placed
        assert orders_placed == 0
