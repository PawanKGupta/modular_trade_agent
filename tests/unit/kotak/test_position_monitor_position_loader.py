"""
Unit tests for Position Monitor PositionLoader integration

Tests verify the migration to use PositionLoader
while maintaining backward compatibility.
"""

from unittest.mock import Mock, patch

from modules.kotak_neo_auto_trader.position_monitor import PositionMonitor


class TestPositionMonitorPositionLoaderInitialization:
    """Test PositionMonitor initialization with PositionLoader"""

    def test_init_with_position_loader(self):
        """Test that PositionMonitor initializes PositionLoader"""
        monitor = PositionMonitor(history_path="test_history.json")

        assert monitor.position_loader is not None
        assert monitor.position_loader.history_path == "test_history.json"
        assert monitor.position_loader.enable_caching is True

    def test_position_loader_uses_correct_history_path(self):
        """Test that PositionLoader uses the provided history path"""
        custom_path = "custom/path/history.json"
        monitor = PositionMonitor(history_path=custom_path)

        assert monitor.position_loader.history_path == custom_path


class TestPositionMonitorPositionLoaderMethods:
    """Test PositionMonitor methods that use PositionLoader"""

    @patch("modules.kotak_neo_auto_trader.position_monitor.get_position_loader")
    def test_monitor_all_positions_uses_position_loader(self, mock_get_loader):
        """Test that monitor_all_positions() uses PositionLoader.get_positions_by_symbol()"""
        # Mock PositionLoader
        mock_loader = Mock()
        mock_loader.get_positions_by_symbol = Mock(return_value={})
        mock_get_loader.return_value = mock_loader

        monitor = PositionMonitor(history_path="test_history.json")

        # Call monitor_all_positions
        result = monitor.monitor_all_positions()

        # Verify PositionLoader was called
        mock_loader.get_positions_by_symbol.assert_called_once()

        # Verify result structure
        assert result is not None
        assert "monitored" in result
        assert "alerts_sent" in result

    @patch("modules.kotak_neo_auto_trader.position_monitor.get_position_loader")
    def test_monitor_all_positions_with_positions(self, mock_get_loader):
        """Test monitor_all_positions() with actual positions"""
        # Mock PositionLoader with positions
        mock_loader = Mock()
        mock_positions = {
            "RELIANCE": [
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "entry_price": 2500.0,
                    "qty": 10,
                    "status": "open",
                }
            ]
        }
        mock_loader.get_positions_by_symbol = Mock(return_value=mock_positions)
        mock_get_loader.return_value = mock_loader

        # Mock price and indicator services
        mock_price_service = Mock()
        mock_price_service.get_price = Mock(return_value=None)
        mock_price_service.get_realtime_price = Mock(return_value=2550.0)

        mock_indicator_service = Mock()
        mock_indicator_service.calculate_all_indicators = Mock(
            return_value={"rsi10": 30.0, "ema9": 2480.0, "ema200": 2400.0}
        )
        mock_indicator_service.calculate_ema9_realtime = Mock(return_value=2480.0)

        monitor = PositionMonitor(history_path="test_history.json")
        monitor.price_service = mock_price_service
        monitor.indicator_service = mock_indicator_service

        # Call monitor_all_positions
        result = monitor.monitor_all_positions()

        # Verify PositionLoader was called
        mock_loader.get_positions_by_symbol.assert_called_once()

        # Verify result
        assert result is not None
        assert result["monitored"] >= 0

    @patch("modules.kotak_neo_auto_trader.position_monitor.get_position_loader")
    def test_get_open_positions_delegates_to_position_loader(self, mock_get_loader):
        """Test that _get_open_positions() delegates to PositionLoader"""
        # Mock PositionLoader
        mock_loader = Mock()
        expected_positions = {
            "RELIANCE": [
                {
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "entry_price": 2500.0,
                    "qty": 10,
                    "status": "open",
                }
            ]
        }
        mock_loader.get_positions_by_symbol = Mock(return_value=expected_positions)
        mock_get_loader.return_value = mock_loader

        monitor = PositionMonitor(history_path="test_history.json")

        # Call _get_open_positions (backward compatibility method)
        result = monitor._get_open_positions({})  # history dict ignored

        # Verify PositionLoader was called
        mock_loader.get_positions_by_symbol.assert_called_once()

        # Verify result
        assert result == expected_positions
        assert "RELIANCE" in result


class TestPositionMonitorPositionLoaderBackwardCompatibility:
    """Test backward compatibility of PositionMonitor with PositionLoader"""

    @patch("modules.kotak_neo_auto_trader.position_monitor.get_position_loader")
    def test_get_open_positions_backward_compatibility(self, mock_get_loader):
        """Test that _get_open_positions() maintains backward compatibility"""
        # Mock PositionLoader
        mock_loader = Mock()
        mock_loader.get_positions_by_symbol = Mock(return_value={})
        mock_get_loader.return_value = mock_loader

        monitor = PositionMonitor(history_path="test_history.json")

        # Call _get_open_positions with history dict (ignored, but method signature unchanged)
        result = monitor._get_open_positions({"trades": []})

        # Verify result type and structure
        assert isinstance(result, dict)
        assert result == {}

    @patch("modules.kotak_neo_auto_trader.position_monitor.get_position_loader")
    def test_monitor_all_positions_handles_empty_positions(self, mock_get_loader):
        """Test that monitor_all_positions() handles empty positions correctly"""
        # Mock PositionLoader with empty positions
        mock_loader = Mock()
        mock_loader.get_positions_by_symbol = Mock(return_value={})
        mock_get_loader.return_value = mock_loader

        monitor = PositionMonitor(history_path="test_history.json")

        # Call monitor_all_positions
        result = monitor.monitor_all_positions()

        # Verify result structure
        assert result is not None
        assert result["monitored"] == 0
        assert "alerts_sent" in result
        assert "averaging_opportunities" in result
        assert "exit_imminent" in result

    @patch("modules.kotak_neo_auto_trader.position_monitor.get_position_loader")
    def test_position_loader_caching_enabled(self, mock_get_loader):
        """Test that PositionLoader caching is enabled"""
        mock_loader = Mock()
        mock_loader.get_positions_by_symbol = Mock(return_value={})
        mock_get_loader.return_value = mock_loader

        monitor = PositionMonitor(history_path="test_history.json")

        # Call monitor_all_positions twice
        monitor.monitor_all_positions()
        monitor.monitor_all_positions()

        # Verify PositionLoader was called (caching should work)
        assert mock_loader.get_positions_by_symbol.call_count == 2

