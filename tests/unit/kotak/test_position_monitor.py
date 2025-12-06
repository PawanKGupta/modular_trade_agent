"""
Unit tests for Position Monitor

Tests verify the migration to PriceService and IndicatorService
while maintaining backward compatibility.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pandas as pd

from modules.kotak_neo_auto_trader.position_monitor import (
    PositionMonitor,
    PositionStatus,
    get_position_monitor,
)


class TestPositionMonitorInitialization:
    """Test PositionMonitor initialization with services"""

    def test_init_with_services(self):
        """Test that PositionMonitor initializes PriceService and IndicatorService"""
        monitor = PositionMonitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=False,
        )

        assert monitor.price_service is not None
        assert monitor.indicator_service is not None
        assert monitor.price_service.live_price_manager is None  # No real-time prices

    def test_init_with_live_price_manager(self):
        """Test that PositionMonitor passes live_price_manager to services"""
        mock_price_manager = Mock()
        monitor = PositionMonitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=True,
            live_price_manager=mock_price_manager,
        )

        assert monitor.price_manager == mock_price_manager
        assert monitor.price_service.live_price_manager == mock_price_manager
        assert monitor.indicator_service.price_service == monitor.price_service

    def test_get_position_monitor_factory(self):
        """Test factory function creates monitor correctly"""
        monitor = get_position_monitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=False,
        )

        assert isinstance(monitor, PositionMonitor)
        assert monitor.price_service is not None
        assert monitor.indicator_service is not None


class TestPositionMonitorPriceServiceIntegration:
    """Test that PositionMonitor uses PriceService correctly"""

    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_monitor_uses_price_service_for_historical_data(self, mock_get_position_loader):
        """Test that monitor uses PriceService.get_price() for historical data"""
        # Mock PositionLoader
        mock_position_loader = Mock()
        mock_position_loader.load_open_positions.return_value = [
            {
                "status": "open",
                "symbol": "RELIANCE",
                "ticker": "RELIANCE.NS",
                "qty": 10,
                "entry_price": 2500.0,
                "entry_time": "2024-01-01T10:00:00",
            }
        ]
        mock_position_loader.get_positions_by_symbol.return_value = {
            "RELIANCE": [
                {
                    "status": "open",
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "entry_time": "2024-01-01T10:00:00",
                }
            ]
        }
        mock_get_position_loader.return_value = mock_position_loader

        # Mock PositionLoader
        mock_position_loader = Mock()
        mock_position_loader.load_open_positions.return_value = [
            {
                "status": "open",
                "symbol": "RELIANCE",
                "ticker": "RELIANCE.NS",
                "qty": 10,
                "entry_price": 2500.0,
                "entry_time": "2024-01-01T10:00:00",
            }
        ]
        mock_position_loader.get_positions_by_symbol.return_value = {
            "RELIANCE": [
                {
                    "status": "open",
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "entry_time": "2024-01-01T10:00:00",
                }
            ]
        }
        mock_get_position_loader.return_value = mock_position_loader

        # Create monitor with mocked services
        monitor = PositionMonitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=False,
        )

        # Mock PriceService
        mock_df = pd.DataFrame(
            {
                "close": [2500, 2510, 2520],
                "open": [2490, 2500, 2510],
                "high": [2510, 2520, 2530],
                "low": [2480, 2490, 2500],
                "volume": [1000, 1100, 1200],
                "date": pd.date_range("2024-01-01", periods=3),
            }
        )
        monitor.price_service.get_price = Mock(return_value=mock_df)
        monitor.position_loader = mock_position_loader

        # Mock IndicatorService
        mock_df_with_indicators = mock_df.copy()
        mock_df_with_indicators["rsi10"] = [25.0, 30.0, 35.0]
        mock_df_with_indicators["ema9"] = [2480.0, 2490.0, 2500.0]
        mock_df_with_indicators["ema200"] = [2400.0, 2410.0, 2420.0]
        monitor.indicator_service.calculate_all_indicators = Mock(
            return_value=mock_df_with_indicators
        )
        monitor.price_service.get_realtime_price = Mock(return_value=None)

        # Run monitoring
        results = monitor.monitor_all_positions()

        # Verify PriceService.get_price() was called
        monitor.price_service.get_price.assert_called_once()
        call_args = monitor.price_service.get_price.call_args
        assert call_args[0][0] == "RELIANCE.NS"  # ticker
        assert call_args[1]["days"] == 200
        assert call_args[1]["interval"] == "1d"
        assert call_args[1]["add_current_day"] is True

        # Verify IndicatorService was called
        monitor.indicator_service.calculate_all_indicators.assert_called_once()

        # Verify results
        assert results["monitored"] == 1

    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_monitor_uses_price_service_for_realtime_price(self, mock_get_position_loader):
        """Test that monitor uses PriceService.get_realtime_price()"""
        # Mock PositionLoader
        mock_position_loader = Mock()
        mock_position_loader.load_open_positions.return_value = [
            {
                "status": "open",
                "symbol": "RELIANCE",
                "ticker": "RELIANCE.NS",
                "qty": 10,
                "entry_price": 2500.0,
                "entry_time": "2024-01-01T10:00:00",
            }
        ]
        mock_position_loader.get_positions_by_symbol.return_value = {
            "RELIANCE": [
                {
                    "status": "open",
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "entry_time": "2024-01-01T10:00:00",
                }
            ]
        }
        mock_get_position_loader.return_value = mock_position_loader

        monitor = PositionMonitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=True,
        )
        monitor.position_loader = mock_position_loader

        # Mock services
        mock_df = pd.DataFrame(
            {
                "close": [2500, 2510, 2520],
                "date": pd.date_range("2024-01-01", periods=3),
            }
        )
        monitor.price_service.get_price = Mock(return_value=mock_df)

        mock_df_with_indicators = mock_df.copy()
        mock_df_with_indicators["rsi10"] = [25.0, 30.0, 35.0]  # Match DataFrame length
        mock_df_with_indicators["ema9"] = [2480.0, 2490.0, 2500.0]
        mock_df_with_indicators["ema200"] = [2400.0, 2410.0, 2420.0]
        monitor.indicator_service.calculate_all_indicators = Mock(
            return_value=mock_df_with_indicators
        )

        # Mock real-time price
        monitor.price_service.get_realtime_price = Mock(return_value=2550.0)

        # Run monitoring
        results = monitor.monitor_all_positions()

        # Verify get_realtime_price was called
        monitor.price_service.get_realtime_price.assert_called_once()
        call_args = monitor.price_service.get_realtime_price.call_args
        assert call_args[1]["symbol"] == "RELIANCE"
        assert call_args[1]["ticker"] == "RELIANCE.NS"

        assert results["monitored"] == 1


class TestPositionMonitorIndicatorServiceIntegration:
    """Test that PositionMonitor uses IndicatorService correctly"""

    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_monitor_uses_indicator_service_for_calculations(self, mock_get_position_loader):
        """Test that monitor uses IndicatorService.calculate_all_indicators()"""
        # Mock PositionLoader
        mock_position_loader = Mock()
        mock_position_loader.load_open_positions.return_value = [
            {
                "status": "open",
                "symbol": "RELIANCE",
                "ticker": "RELIANCE.NS",
                "qty": 10,
                "entry_price": 2500.0,
                "entry_time": "2024-01-01T10:00:00",
            }
        ]
        mock_position_loader.get_positions_by_symbol.return_value = {
            "RELIANCE": [
                {
                    "status": "open",
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "entry_time": "2024-01-01T10:00:00",
                }
            ]
        }
        mock_get_position_loader.return_value = mock_position_loader

        monitor = PositionMonitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=False,
        )
        monitor.position_loader = mock_position_loader

        # Mock PriceService
        mock_df = pd.DataFrame(
            {
                "close": [2500, 2510, 2520],
                "date": pd.date_range("2024-01-01", periods=3),
            }
        )
        monitor.price_service.get_price = Mock(return_value=mock_df)
        monitor.price_service.get_realtime_price = Mock(return_value=None)

        # Mock IndicatorService
        mock_df_with_indicators = mock_df.copy()
        mock_df_with_indicators["rsi10"] = [25.0, 30.0, 35.0]
        mock_df_with_indicators["ema9"] = [2480.0, 2490.0, 2500.0]
        mock_df_with_indicators["ema200"] = [2400.0, 2410.0, 2420.0]
        monitor.indicator_service.calculate_all_indicators = Mock(
            return_value=mock_df_with_indicators
        )

        # Run monitoring
        results = monitor.monitor_all_positions()

        # Verify IndicatorService.calculate_all_indicators() was called
        monitor.indicator_service.calculate_all_indicators.assert_called_once()

        # Verify results contain correct indicator values
        assert results["monitored"] == 1
        position = results["positions"][0]
        assert position.rsi10 == 35.0  # Latest RSI value
        assert position.ema9 == 2500.0  # Latest EMA9 value
        assert position.ema200 == 2420.0  # Latest EMA200 value

    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_monitor_uses_indicator_service_for_realtime_ema9(self, mock_get_position_loader):
        """Test that monitor uses IndicatorService.calculate_ema9_realtime() when needed"""
        # Mock PositionLoader
        mock_position_loader = Mock()
        mock_position_loader.load_open_positions.return_value = [
            {
                "status": "open",
                "symbol": "RELIANCE",
                "ticker": "RELIANCE.NS",
                "qty": 10,
                "entry_price": 2500.0,
                "entry_time": "2024-01-01T10:00:00",
            }
        ]
        mock_position_loader.get_positions_by_symbol.return_value = {
            "RELIANCE": [
                {
                    "status": "open",
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "entry_time": "2024-01-01T10:00:00",
                }
            ]
        }
        mock_get_position_loader.return_value = mock_position_loader

        monitor = PositionMonitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=True,  # Enable real-time prices
        )
        monitor.position_loader = mock_position_loader

        # Mock PriceService
        mock_df = pd.DataFrame(
            {
                "close": [2500, 2510, 2520],
                "date": pd.date_range("2024-01-01", periods=3),
            }
        )
        monitor.price_service.get_price = Mock(return_value=mock_df)
        monitor.price_service.get_realtime_price = Mock(return_value=2550.0)  # Different from close

        # Mock IndicatorService
        mock_df_with_indicators = mock_df.copy()
        mock_df_with_indicators["rsi10"] = [25.0, 30.0, 35.0]  # Match DataFrame length
        mock_df_with_indicators["ema9"] = [2480.0, 2490.0, 2500.0]  # Historical EMA9
        mock_df_with_indicators["ema200"] = [2400.0, 2410.0, 2420.0]
        monitor.indicator_service.calculate_all_indicators = Mock(
            return_value=mock_df_with_indicators
        )
        monitor.indicator_service.calculate_ema9_realtime = Mock(return_value=2520.0)

        # Run monitoring
        results = monitor.monitor_all_positions()

        # Verify calculate_ema9_realtime was called (because real-time price differs from close)
        monitor.indicator_service.calculate_ema9_realtime.assert_called_once()
        call_args = monitor.indicator_service.calculate_ema9_realtime.call_args
        assert call_args[1]["ticker"] == "RELIANCE.NS"
        assert call_args[1]["current_ltp"] == 2550.0

        # Verify results use real-time EMA9
        assert results["monitored"] == 1
        position = results["positions"][0]
        assert position.ema9 == 2520.0  # Real-time EMA9, not historical


class TestPositionMonitorBackwardCompatibility:
    """Test that PositionMonitor maintains backward compatibility"""

    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_monitor_returns_same_structure(self, mock_get_position_loader):
        """Test that monitor returns same structure as before migration"""
        # Mock PositionLoader
        mock_position_loader = Mock()
        mock_position_loader.load_open_positions.return_value = [
            {
                "status": "open",
                "symbol": "RELIANCE",
                "ticker": "RELIANCE.NS",
                "qty": 10,
                "entry_price": 2500.0,
                "entry_time": "2024-01-01T10:00:00",
            }
        ]
        mock_position_loader.get_positions_by_symbol.return_value = {
            "RELIANCE": [
                {
                    "status": "open",
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "entry_time": "2024-01-01T10:00:00",
                }
            ]
        }
        mock_get_position_loader.return_value = mock_position_loader

        monitor = PositionMonitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=False,
        )
        monitor.position_loader = mock_position_loader

        # Mock services
        mock_df = pd.DataFrame(
            {
                "close": [2500, 2510, 2520],
                "date": pd.date_range("2024-01-01", periods=3),
            }
        )
        monitor.price_service.get_price = Mock(return_value=mock_df)

        mock_df_with_indicators = mock_df.copy()
        mock_df_with_indicators["rsi10"] = [25.0, 30.0, 35.0]
        mock_df_with_indicators["ema9"] = [2480.0, 2490.0, 2500.0]
        mock_df_with_indicators["ema200"] = [2400.0, 2410.0, 2420.0]
        monitor.indicator_service.calculate_all_indicators = Mock(
            return_value=mock_df_with_indicators
        )
        monitor.price_service.get_realtime_price = Mock(return_value=None)

        # Run monitoring
        results = monitor.monitor_all_positions()

        # Verify return structure matches original
        assert "monitored" in results
        assert "alerts_sent" in results
        assert "exit_imminent" in results
        assert "averaging_opportunities" in results
        assert "positions" in results

        # Verify PositionStatus structure
        if results["positions"]:
            position = results["positions"][0]
            assert isinstance(position, PositionStatus)
            assert hasattr(position, "symbol")
            assert hasattr(position, "current_price")
            assert hasattr(position, "rsi10")
            assert hasattr(position, "ema9")
            assert hasattr(position, "ema200")
            assert hasattr(position, "unrealized_pnl")
            assert hasattr(position, "alerts")

    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_monitor_handles_no_positions(self, mock_get_position_loader):
        """Test that monitor handles no open positions correctly"""
        mock_position_loader = Mock()
        mock_position_loader.load_open_positions.return_value = []
        mock_position_loader.get_positions_by_symbol.return_value = {}
        mock_get_position_loader.return_value = mock_position_loader

        monitor = PositionMonitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=False,
        )
        # Set the mocked position_loader (required for the mock to work)
        monitor.position_loader = mock_position_loader

        results = monitor.monitor_all_positions()

        assert results["monitored"] == 0
        assert results["alerts_sent"] == 0
        assert results["exit_imminent"] == 0
        assert results["averaging_opportunities"] == 0

    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_monitor_handles_missing_data_gracefully(self, mock_get_position_loader):
        """Test that monitor handles missing price data gracefully"""
        # Mock PositionLoader
        mock_position_loader = Mock()
        mock_position_loader.load_open_positions.return_value = [
            {
                "status": "open",
                "symbol": "INVALID",
                "ticker": "INVALID.NS",
                "qty": 10,
                "entry_price": 100.0,
                "entry_time": "2024-01-01T10:00:00",
            }
        ]
        mock_position_loader.get_positions_by_symbol.return_value = {
            "INVALID": [
                {
                    "status": "open",
                    "symbol": "INVALID",
                    "ticker": "INVALID.NS",
                    "qty": 10,
                    "entry_price": 100.0,
                    "entry_time": "2024-01-01T10:00:00",
                }
            ]
        }
        mock_get_position_loader.return_value = mock_position_loader

        monitor = PositionMonitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=False,
        )
        monitor.position_loader = mock_position_loader

        # Mock PriceService to return None (no data)
        monitor.price_service.get_price = Mock(return_value=None)

        # Run monitoring - should handle gracefully
        results = monitor.monitor_all_positions()

        # Should not crash, but return 0 monitored
        assert results["monitored"] == 0


class TestPositionMonitorSubscription:
    """Test that PositionMonitor uses PriceService for subscription"""

    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_monitor_subscribes_via_price_service(self, mock_get_position_loader):
        """Test that monitor subscribes to symbols via PriceService"""
        # Mock PositionLoader
        mock_position_loader = Mock()
        mock_position_loader.load_open_positions.return_value = [
            {
                "status": "open",
                "symbol": "RELIANCE",
                "ticker": "RELIANCE.NS",
                "qty": 10,
                "entry_price": 2500.0,
                "entry_time": "2024-01-01T10:00:00",
            }
        ]
        mock_position_loader.get_positions_by_symbol.return_value = {
            "RELIANCE": [
                {
                    "status": "open",
                    "symbol": "RELIANCE",
                    "ticker": "RELIANCE.NS",
                    "qty": 10,
                    "entry_price": 2500.0,
                    "entry_time": "2024-01-01T10:00:00",
                }
            ]
        }
        mock_get_position_loader.return_value = mock_position_loader

        monitor = PositionMonitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=True,
        )
        monitor.position_loader = mock_position_loader

        # Mock services
        mock_df = pd.DataFrame({"close": [2500], "date": [datetime.now()]})
        monitor.price_service.get_price = Mock(return_value=mock_df)
        monitor.price_service.get_realtime_price = Mock(return_value=2500.0)
        monitor.price_service.subscribe_to_symbols = Mock(return_value=True)

        mock_df_with_indicators = mock_df.copy()
        mock_df_with_indicators["rsi10"] = [25.0]
        mock_df_with_indicators["ema9"] = [2480.0]
        mock_df_with_indicators["ema200"] = [2400.0]
        monitor.indicator_service.calculate_all_indicators = Mock(
            return_value=mock_df_with_indicators
        )

        # Run monitoring
        monitor.monitor_all_positions()

        # Verify subscription was called
        monitor.price_service.subscribe_to_symbols.assert_called_once()
        call_args = monitor.price_service.subscribe_to_symbols.call_args
        assert "RELIANCE" in call_args[0][0]  # Symbol in subscription list
