"""
Unit tests for AutoTradeEngine service integration

Tests verify the migration to PriceService and IndicatorService
while maintaining backward compatibility.
"""

from unittest.mock import Mock, patch

import pandas as pd

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine


class TestAutoTradeEngineInitialization:
    """Test AutoTradeEngine initialization with services"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_init_with_services(self, mock_auth):
        """Test that AutoTradeEngine initializes PriceService and IndicatorService"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        engine = AutoTradeEngine(env_file="test.env")

        assert engine.price_service is not None
        assert engine.indicator_service is not None
        assert engine.price_service.live_price_manager is None  # No price_manager initially

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_services_share_price_service(self, mock_auth):
        """Test that IndicatorService uses the same PriceService instance"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        engine = AutoTradeEngine(env_file="test.env")

        # Verify services are connected
        assert engine.indicator_service.price_service == engine.price_service

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_caching_enabled(self, mock_auth):
        """Test that caching is enabled in services"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        engine = AutoTradeEngine(env_file="test.env")

        # Verify caching is enabled
        assert engine.price_service.enable_caching is True
        assert engine.indicator_service.enable_caching is True


class TestAutoTradeEngineIndicatorServiceIntegration:
    """Test that AutoTradeEngine uses IndicatorService correctly"""

    def test_get_daily_indicators_uses_indicator_service(self):
        """Test that get_daily_indicators() uses IndicatorService.get_daily_indicators_dict()"""
        # Mock IndicatorService
        mock_indicator_service = Mock()
        mock_indicator_service.get_daily_indicators_dict = Mock(
            return_value={
                "close": 2500.0,
                "rsi10": 25.0,
                "ema9": 2480.0,
                "ema200": 2400.0,
                "avg_volume": 1000000.0,
            }
        )

        # Create temporary engine instance for static method
        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.get_indicator_service"
        ) as mock_get_indicator:
            mock_get_indicator.return_value = mock_indicator_service

            # Call static method
            result = AutoTradeEngine.get_daily_indicators("RELIANCE.NS")

            # Verify IndicatorService.get_daily_indicators_dict() was called
            mock_indicator_service.get_daily_indicators_dict.assert_called_once()
            call_args = mock_indicator_service.get_daily_indicators_dict.call_args
            assert call_args[1]["ticker"] == "RELIANCE.NS"

            # Verify result structure matches original
            assert result is not None
            assert "close" in result
            assert "rsi10" in result
            assert "ema9" in result
            assert "ema200" in result
            assert "avg_volume" in result

    def test_get_daily_indicators_handles_none(self):
        """Test that get_daily_indicators() handles None from IndicatorService"""
        # Mock IndicatorService to return None
        mock_indicator_service = Mock()
        mock_indicator_service.get_daily_indicators_dict = Mock(return_value=None)

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.get_indicator_service"
        ) as mock_get_indicator:
            mock_get_indicator.return_value = mock_indicator_service

            # Call static method
            result = AutoTradeEngine.get_daily_indicators("RELIANCE.NS")

            # Verify result is None
            assert result is None

    def test_get_daily_indicators_return_structure(self):
        """Test that get_daily_indicators() returns same structure as before"""
        # Mock IndicatorService
        mock_indicator_service = Mock()
        mock_indicator_service.get_daily_indicators_dict = Mock(
            return_value={
                "close": 2500.0,
                "rsi10": 25.0,
                "ema9": 2480.0,
                "ema200": 2400.0,
                "avg_volume": 1000000.0,
            }
        )

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.get_indicator_service"
        ) as mock_get_indicator:
            mock_get_indicator.return_value = mock_indicator_service

            result = AutoTradeEngine.get_daily_indicators("RELIANCE.NS")

            # Verify return structure matches original
            assert isinstance(result, dict)
            assert result["close"] == 2500.0
            assert result["rsi10"] == 25.0
            assert result["ema9"] == 2480.0
            assert result["ema200"] == 2400.0
            assert result["avg_volume"] == 1000000.0


class TestAutoTradeEnginePriceServiceIntegration:
    """Test that AutoTradeEngine uses PriceService correctly"""

    def test_market_was_open_today_uses_price_service(self):
        """Test that market_was_open_today() uses PriceService.get_price()"""
        # Mock PriceService
        mock_price_service = Mock()
        mock_df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=5),
                "close": [20000, 20100, 20200, 20300, 20400],
            }
        )
        mock_price_service.get_price = Mock(return_value=mock_df)

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.get_price_service"
        ) as mock_get_price:
            mock_get_price.return_value = mock_price_service

            # Call static method
            result = AutoTradeEngine.market_was_open_today()

            # Verify PriceService.get_price() was called
            mock_price_service.get_price.assert_called_once()
            call_args = mock_price_service.get_price.call_args
            assert call_args[0][0] == "^NSEI"  # NIFTY ticker
            assert call_args[1]["days"] == 5
            assert call_args[1]["interval"] == "1d"
            assert call_args[1]["add_current_day"] is True

            # Verify result is boolean
            assert isinstance(result, bool)

    def test_market_was_open_today_handles_none(self):
        """Test that market_was_open_today() handles None from PriceService"""
        # Mock PriceService to return None
        mock_price_service = Mock()
        mock_price_service.get_price = Mock(return_value=None)

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.get_price_service"
        ) as mock_get_price:
            mock_get_price.return_value = mock_price_service

            # Call static method
            result = AutoTradeEngine.market_was_open_today()

            # Verify result is False when no data
            assert result is False

    def test_market_was_open_today_handles_empty_dataframe(self):
        """Test that market_was_open_today() handles empty DataFrame"""
        # Mock PriceService to return empty DataFrame
        mock_price_service = Mock()
        mock_price_service.get_price = Mock(return_value=pd.DataFrame())

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.get_price_service"
        ) as mock_get_price:
            mock_get_price.return_value = mock_price_service

            # Call static method
            result = AutoTradeEngine.market_was_open_today()

            # Verify result is False when empty
            assert result is False


class TestAutoTradeEngineBackwardCompatibility:
    """Test that AutoTradeEngine maintains backward compatibility"""

    def test_get_daily_indicators_same_signature(self):
        """Test that get_daily_indicators() maintains same signature"""
        # Mock IndicatorService
        mock_indicator_service = Mock()
        mock_indicator_service.get_daily_indicators_dict = Mock(
            return_value={
                "close": 2500.0,
                "rsi10": 25.0,
                "ema9": 2480.0,
                "ema200": 2400.0,
                "avg_volume": 1000000.0,
            }
        )

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.get_indicator_service"
        ) as mock_get_indicator:
            mock_get_indicator.return_value = mock_indicator_service

            # Test static call (original signature)
            result = AutoTradeEngine.get_daily_indicators("RELIANCE.NS")

            # Verify result structure
            assert result is not None
            assert isinstance(result, dict)
            assert "close" in result
            assert "rsi10" in result
            assert "ema9" in result
            assert "ema200" in result
            assert "avg_volume" in result

    def test_get_daily_indicators_return_types(self):
        """Test that get_daily_indicators() returns correct types"""
        # Mock IndicatorService
        mock_indicator_service = Mock()
        mock_indicator_service.get_daily_indicators_dict = Mock(
            return_value={
                "close": 2500.0,
                "rsi10": 25.0,
                "ema9": 2480.0,
                "ema200": 2400.0,
                "avg_volume": 1000000.0,
            }
        )

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.get_indicator_service"
        ) as mock_get_indicator:
            mock_get_indicator.return_value = mock_indicator_service

            result = AutoTradeEngine.get_daily_indicators("RELIANCE.NS")

            # Verify return types match original
            assert isinstance(result, (dict, type(None)))
            if result:
                assert isinstance(result["close"], float)
                assert isinstance(result["rsi10"], float)
                assert isinstance(result["ema9"], float)
                assert isinstance(result["ema200"], float)
                assert isinstance(result["avg_volume"], float)

    def test_market_was_open_today_same_signature(self):
        """Test that market_was_open_today() maintains same signature"""
        # Mock PriceService
        mock_price_service = Mock()
        mock_df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=5),
                "close": [20000, 20100, 20200, 20300, 20400],
            }
        )
        mock_price_service.get_price = Mock(return_value=mock_df)

        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.get_price_service"
        ) as mock_get_price:
            mock_get_price.return_value = mock_price_service

            # Test static call (original signature)
            result = AutoTradeEngine.market_was_open_today()

            # Verify result type
            assert isinstance(result, bool)


class TestAutoTradeEngineServiceIntegration:
    """Test integration between PriceService and IndicatorService"""

    def test_get_daily_indicators_uses_cached_price_service(self):
        """Test that IndicatorService uses PriceService for price fetching"""
        # Mock PriceService
        mock_price_service = Mock()
        mock_df = pd.DataFrame(
            {
                "close": range(2500, 3300),
                "open": range(2490, 3290),
                "high": range(2510, 3310),
                "low": range(2480, 3280),
                "volume": range(1000000, 1000800),
                "date": pd.date_range("2022-01-01", periods=800),
            }
        )
        mock_price_service.get_price = Mock(return_value=mock_df)

        # Mock IndicatorService
        mock_indicator_service = Mock()
        mock_indicator_service.get_daily_indicators_dict = Mock(
            return_value={
                "close": 2500.0,
                "rsi10": 25.0,
                "ema9": 2480.0,
                "ema200": 2400.0,
                "avg_volume": 1000000.0,
            }
        )
        mock_indicator_service.price_service = mock_price_service

        with (
            patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.get_price_service"
            ) as mock_get_price,
            patch(
                "modules.kotak_neo_auto_trader.auto_trade_engine.get_indicator_service"
            ) as mock_get_indicator,
        ):
            mock_get_price.return_value = mock_price_service
            mock_get_indicator.return_value = mock_indicator_service

            # Call get_daily_indicators
            result = AutoTradeEngine.get_daily_indicators("RELIANCE.NS")

            # Verify IndicatorService was called
            mock_indicator_service.get_daily_indicators_dict.assert_called_once()

            # Verify result
            assert result is not None
            assert "close" in result
