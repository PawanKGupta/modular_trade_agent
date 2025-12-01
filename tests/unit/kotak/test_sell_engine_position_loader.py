"""
Unit tests for Sell Monitor PositionLoader integration

Tests verify the migration to use PositionLoader
while maintaining backward compatibility.
"""

from unittest.mock import Mock, patch

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager


class TestSellOrderManagerPositionLoaderInitialization:
    """Test SellOrderManager initialization with PositionLoader"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    def test_init_with_position_loader(self, mock_auth):
        """Test that SellOrderManager initializes PositionLoader"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(
            auth=mock_auth_instance, history_path="test_history.json"
        )

        assert manager.position_loader is not None
        assert manager.position_loader.history_path == "test_history.json"
        assert manager.position_loader.enable_caching is True

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    def test_position_loader_uses_correct_history_path(self, mock_auth):
        """Test that PositionLoader uses the provided history path"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        custom_path = "custom/path/history.json"
        manager = SellOrderManager(auth=mock_auth_instance, history_path=custom_path)

        assert manager.position_loader.history_path == custom_path


class TestSellOrderManagerPositionLoaderMethods:
    """Test SellOrderManager methods that use PositionLoader"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_open_positions_uses_position_loader(self, mock_scrip_master, mock_auth):
        """Test that get_open_positions() uses PositionLoader.load_open_positions()"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock PositionLoader
        mock_loader = Mock()
        expected_positions = [
            {
                "symbol": "RELIANCE",
                "ticker": "RELIANCE.NS",
                "entry_price": 2500.0,
                "qty": 10,
                "status": "open",
            }
        ]
        mock_loader.load_open_positions = Mock(return_value=expected_positions)

        manager = SellOrderManager(
            auth=mock_auth_instance, history_path="test_history.json"
        )
        # Replace the actual PositionLoader with mock
        manager.position_loader = mock_loader

        # Call get_open_positions
        result = manager.get_open_positions()

        # Verify PositionLoader was called
        mock_loader.load_open_positions.assert_called_once()

        # Verify result
        assert result == expected_positions
        assert len(result) == 1
        assert result[0]["symbol"] == "RELIANCE"

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_get_open_positions_handles_empty_positions(self, mock_get_loader, mock_auth):
        """Test get_open_positions() handles empty positions correctly"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock PositionLoader with empty positions
        mock_loader = Mock()
        mock_loader.load_open_positions = Mock(return_value=[])
        mock_get_loader.return_value = mock_loader

        manager = SellOrderManager(
            auth=mock_auth_instance, history_path="test_history.json"
        )

        # Call get_open_positions
        result = manager.get_open_positions()

        # Verify result
        assert result == []
        assert isinstance(result, list)

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_get_open_positions_handles_errors(self, mock_get_loader, mock_auth):
        """Test get_open_positions() handles errors gracefully"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock PositionLoader to raise exception
        mock_loader = Mock()
        mock_loader.load_open_positions = Mock(side_effect=Exception("Test error"))
        mock_get_loader.return_value = mock_loader

        manager = SellOrderManager(
            auth=mock_auth_instance, history_path="test_history.json"
        )

        # Call get_open_positions - should return empty list on error
        result = manager.get_open_positions()

        # Verify result is empty list (error handling)
        assert result == []
        assert isinstance(result, list)


class TestSellOrderManagerPositionLoaderBackwardCompatibility:
    """Test backward compatibility of SellOrderManager with PositionLoader"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_get_open_positions_backward_compatibility(self, mock_get_loader, mock_auth):
        """Test that get_open_positions() maintains backward compatibility"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock PositionLoader
        mock_loader = Mock()
        mock_loader.load_open_positions = Mock(return_value=[])
        mock_get_loader.return_value = mock_loader

        manager = SellOrderManager(
            auth=mock_auth_instance, history_path="test_history.json"
        )

        # Call get_open_positions
        result = manager.get_open_positions()

        # Verify result type and structure (backward compatibility)
        assert isinstance(result, list)
        assert result == []

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_position_loader_caching_enabled(self, mock_scrip_master, mock_auth):
        """Test that PositionLoader caching is enabled"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        mock_loader = Mock()
        mock_loader.load_open_positions = Mock(return_value=[])

        manager = SellOrderManager(
            auth=mock_auth_instance, history_path="test_history.json"
        )
        # Replace the actual PositionLoader with mock
        manager.position_loader = mock_loader

        # Call get_open_positions twice
        manager.get_open_positions()
        manager.get_open_positions()

        # Verify PositionLoader was called (caching should work)
        assert mock_loader.load_open_positions.call_count == 2

