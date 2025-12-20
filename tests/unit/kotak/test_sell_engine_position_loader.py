"""
Unit tests for Sell Monitor - Database-Only Position Tracking

Tests verify the migration from PositionLoader (file-based) to database-only tracking.
PositionLoader is no longer used - positions are loaded from database only.
"""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from src.infrastructure.db.timezone_utils import ist_now


class TestSellOrderManagerDatabaseOnlyInitialization:
    """Test SellOrderManager initialization - PositionLoader removed"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_init_without_position_loader(self, mock_scrip_master, mock_auth):
        """Test that SellOrderManager no longer initializes PositionLoader"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # PositionLoader should not exist (removed)
        assert not hasattr(manager, "position_loader")

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_init_with_database_repos(self, mock_scrip_master, mock_auth):
        """Test that SellOrderManager can be initialized with database repositories"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        mock_positions_repo = Mock()
        mock_orders_repo = Mock()

        manager = SellOrderManager(
            auth=mock_auth_instance,
            positions_repo=mock_positions_repo,
            user_id=2,
            orders_repo=mock_orders_repo,
        )

        assert manager.positions_repo == mock_positions_repo
        assert manager.orders_repo == mock_orders_repo
        assert manager.user_id == 2
        # PositionLoader should not exist
        assert not hasattr(manager, "position_loader")


class TestSellOrderManagerDatabaseOnlyMethods:
    """Test SellOrderManager methods with database-only implementation"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_uses_database_repos(self, mock_scrip_master, mock_auth):
        """Test that get_open_positions() uses PositionsRepository (database-only)"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Create mock position
        mock_position = Mock()
        mock_position.symbol = "RELIANCE"
        mock_position.quantity = 10.0
        mock_position.avg_price = 2500.0
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

        # Verify PositionsRepository was called (not PositionLoader)
        mock_positions_repo.list.assert_called_once_with(2)

        # Verify result
        assert len(result) == 1
        assert result[0]["symbol"] == "RELIANCE"
        assert result[0]["qty"] == 10.0
        assert result[0]["entry_price"] == 2500.0
        assert result[0]["status"] == "open"

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_handles_empty_positions(self, mock_scrip_master, mock_auth):
        """Test get_open_positions() handles empty positions correctly"""
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
    def test_get_open_positions_raises_error_without_repos(self, mock_scrip_master, mock_auth):
        """Test get_open_positions() raises ValueError without database repos"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Call get_open_positions - should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            manager.get_open_positions()

        assert "PositionsRepository and user_id are required" in str(exc_info.value)


class TestSellOrderManagerDatabaseOnlyBackwardCompatibility:
    """Test backward compatibility - old code can still instantiate but will fail
    when calling get_open_positions()"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_init_backward_compatibility(self, mock_scrip_master, mock_auth):
        """Test that old code can still instantiate SellOrderManager without database repos"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Old code can still instantiate (backward compatible)
        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Should not raise error during init
        assert manager.positions_repo is None
        assert manager.user_id is None

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_requires_database_repos(self, mock_scrip_master, mock_auth):
        """Test that get_open_positions() requires database repos (will fail for old code)"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        # Old code can instantiate
        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # But calling get_open_positions() will raise ValueError
        with pytest.raises(ValueError) as exc_info:
            manager.get_open_positions()

        assert "PositionsRepository and user_id are required" in str(exc_info.value)
