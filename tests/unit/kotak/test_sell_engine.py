"""
Unit tests for Sell Engine (Sell Monitor)

Tests verify the migration to PriceService and IndicatorService
while maintaining backward compatibility.
"""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from modules.kotak_neo_auto_trader.services.price_service import PriceService


class TestSellEngineInitialization:
    """Test SellOrderManager initialization with services"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.get_price_service")
    def test_init_with_services(self, mock_get_price_service, mock_scrip_master, mock_auth):
        """Test that SellOrderManager initializes PriceService and IndicatorService"""

        # Create a fresh PriceService instance based on the parameters passed
        def create_price_service(live_price_manager=None, enable_caching=True, **kwargs):
            return PriceService(
                live_price_manager=live_price_manager, enable_caching=enable_caching, **kwargs
            )

        mock_get_price_service.side_effect = create_price_service

        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        assert manager.price_service is not None
        assert manager.indicator_service is not None
        assert manager.price_manager is None  # No price_manager passed
        assert manager.price_service.live_price_manager is None  # No price_manager passed

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_init_with_price_manager(self, mock_scrip_master, mock_auth):
        """Test that SellOrderManager passes price_manager to services"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        mock_price_manager = Mock()
        manager = SellOrderManager(
            auth=mock_auth_instance,
            history_path="test_history.json",
            price_manager=mock_price_manager,
        )

        assert manager.price_manager == mock_price_manager
        assert manager.price_service.live_price_manager == mock_price_manager
        assert manager.indicator_service.price_service == manager.price_service


class TestSellEnginePriceServiceIntegration:
    """Test that SellOrderManager uses PriceService correctly"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_current_ltp_uses_price_service(self, mock_scrip_master, mock_auth):
        """Test that get_current_ltp() uses PriceService.get_realtime_price()"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock PriceService
        manager.price_service.get_realtime_price = Mock(return_value=2500.0)

        # Call get_current_ltp
        ltp = manager.get_current_ltp("RELIANCE.NS", broker_symbol="RELIANCE-EQ")

        # Verify PriceService.get_realtime_price() was called
        manager.price_service.get_realtime_price.assert_called_once()
        call_args = manager.price_service.get_realtime_price.call_args
        assert call_args[1]["ticker"] == "RELIANCE.NS"
        assert call_args[1]["broker_symbol"] == "RELIANCE-EQ"

        # Verify result
        assert ltp == 2500.0

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_current_ltp_handles_none(self, mock_scrip_master, mock_auth):
        """Test that get_current_ltp() handles None from PriceService"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock PriceService to return None
        manager.price_service.get_realtime_price = Mock(return_value=None)

        # Call get_current_ltp
        ltp = manager.get_current_ltp("RELIANCE.NS")

        # Verify result is None
        assert ltp is None


class TestSellEngineIndicatorServiceIntegration:
    """Test that SellOrderManager uses IndicatorService correctly"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_current_ema9_uses_indicator_service(self, mock_scrip_master, mock_auth):
        """Test that get_current_ema9() uses IndicatorService.calculate_ema9_realtime()"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock IndicatorService
        manager.indicator_service.calculate_ema9_realtime = Mock(return_value=2480.0)

        # Call get_current_ema9
        ema9 = manager.get_current_ema9("RELIANCE.NS", broker_symbol="RELIANCE-EQ")

        # Verify IndicatorService.calculate_ema9_realtime() was called
        manager.indicator_service.calculate_ema9_realtime.assert_called_once()
        call_args = manager.indicator_service.calculate_ema9_realtime.call_args
        assert call_args[1]["ticker"] == "RELIANCE.NS"
        assert call_args[1]["broker_symbol"] == "RELIANCE-EQ"
        assert call_args[1]["current_ltp"] is None  # Not provided, will be fetched

        # Verify result
        assert ema9 == 2480.0

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_current_ema9_handles_none(self, mock_scrip_master, mock_auth):
        """Test that get_current_ema9() handles None from IndicatorService"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock IndicatorService to return None
        manager.indicator_service.calculate_ema9_realtime = Mock(return_value=None)

        # Call get_current_ema9
        ema9 = manager.get_current_ema9("RELIANCE.NS")

        # Verify result is None
        assert ema9 is None


class TestSellEngineBackwardCompatibility:
    """Test that SellOrderManager maintains backward compatibility"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_current_ltp_same_signature(self, mock_scrip_master, mock_auth):
        """Test that get_current_ltp() maintains same signature"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock PriceService
        manager.price_service.get_realtime_price = Mock(return_value=2500.0)

        # Test with both arguments (original signature)
        ltp1 = manager.get_current_ltp("RELIANCE.NS", broker_symbol="RELIANCE-EQ")
        assert ltp1 == 2500.0

        # Test with only ticker (original signature)
        ltp2 = manager.get_current_ltp("RELIANCE.NS")
        assert ltp2 == 2500.0

        # Verify both calls were made
        assert manager.price_service.get_realtime_price.call_count == 2

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_current_ema9_same_signature(self, mock_scrip_master, mock_auth):
        """Test that get_current_ema9() maintains same signature"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock IndicatorService
        manager.indicator_service.calculate_ema9_realtime = Mock(return_value=2480.0)

        # Test with both arguments (original signature)
        ema9_1 = manager.get_current_ema9("RELIANCE.NS", broker_symbol="RELIANCE-EQ")
        assert ema9_1 == 2480.0

        # Test with only ticker (original signature)
        ema9_2 = manager.get_current_ema9("RELIANCE.NS")
        assert ema9_2 == 2480.0

        # Verify both calls were made
        assert manager.indicator_service.calculate_ema9_realtime.call_count == 2

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_methods_return_same_types(self, mock_scrip_master, mock_auth):
        """Test that methods return same types as before"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock services
        manager.price_service.get_realtime_price = Mock(return_value=2500.0)
        manager.indicator_service.calculate_ema9_realtime = Mock(return_value=2480.0)

        # Test return types
        ltp = manager.get_current_ltp("RELIANCE.NS")
        assert isinstance(ltp, (float, type(None)))

        ema9 = manager.get_current_ema9("RELIANCE.NS")
        assert isinstance(ema9, (float, type(None)))


class TestSellEngineServiceIntegration:
    """Test integration between PriceService and IndicatorService in SellOrderManager"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_services_share_price_service(self, mock_scrip_master, mock_auth):
        """Test that IndicatorService uses the same PriceService instance"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Verify services are connected
        assert manager.indicator_service.price_service == manager.price_service

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_caching_enabled(self, mock_scrip_master, mock_auth):
        """Test that caching is enabled in services"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Verify caching is enabled
        assert manager.price_service.enable_caching is True
        assert manager.indicator_service.enable_caching is True


class TestEMA9RetryMechanismIssue3:
    """Test Issue #3: EMA9 Calculation Failure - Retry and Fallback"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_ema9_with_retry_succeeds_on_first_attempt(
        self, mock_scrip_master, mock_auth
    ):
        """Test that _get_ema9_with_retry succeeds on first attempt"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock successful EMA9 calculation
        manager.get_current_ema9 = Mock(return_value=2500.0)

        result = manager._get_ema9_with_retry("RELIANCE.NS", broker_symbol="RELIANCE-EQ", symbol="RELIANCE")

        assert result == 2500.0
        manager.get_current_ema9.assert_called_once()

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_ema9_with_retry_succeeds_on_retry(self, mock_scrip_master, mock_auth):
        """Test that _get_ema9_with_retry succeeds after retry"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock: First attempt fails, second succeeds
        manager.get_current_ema9 = Mock(side_effect=[None, 2500.0])

        result = manager._get_ema9_with_retry("RELIANCE.NS", broker_symbol="RELIANCE-EQ", symbol="RELIANCE")

        assert result == 2500.0
        assert manager.get_current_ema9.call_count == 2

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_ema9_with_retry_falls_back_to_yesterday_ema9(
        self, mock_scrip_master, mock_auth
    ):
        """Test that _get_ema9_with_retry falls back to yesterday's EMA9 when all retries fail"""
        import pandas as pd

        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock: All attempts fail
        manager.get_current_ema9 = Mock(return_value=None)

        # Mock indicator service and price service for fallback
        # Need at least 9 data points for EMA9 calculation
        mock_df = pd.DataFrame(
            {
                "close": [2400.0 + i * 10 for i in range(20)],  # 20 data points
                "date": pd.date_range("2024-01-01", periods=20),
            }
        )
        # Ensure price_service exists and has get_price method
        if not hasattr(manager.indicator_service, "price_service") or manager.indicator_service.price_service is None:
            manager.indicator_service.price_service = Mock()
        manager.indicator_service.price_service.get_price = Mock(return_value=mock_df)

        result = manager._get_ema9_with_retry("RELIANCE.NS", broker_symbol="RELIANCE-EQ", symbol="RELIANCE")

        # Should return yesterday's EMA9 (calculated from historical data)
        assert result is not None
        assert result > 0
        # Verify fallback was attempted
        manager.indicator_service.price_service.get_price.assert_called_once()

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_ema9_with_retry_returns_none_when_all_fail(
        self, mock_scrip_master, mock_auth
    ):
        """Test that _get_ema9_with_retry returns None when all attempts and fallback fail"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock: All attempts fail
        manager.get_current_ema9 = Mock(return_value=None)

        # Mock: Fallback also fails (no price service or empty data)
        manager.indicator_service.price_service = None

        result = manager._get_ema9_with_retry("RELIANCE.NS", broker_symbol="RELIANCE-EQ", symbol="RELIANCE")

        assert result is None
        # Should have tried max_retries + 1 times
        assert manager.get_current_ema9.call_count == 3  # max_retries=2, so 3 attempts total

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_ema9_with_retry_handles_exceptions(self, mock_scrip_master, mock_auth):
        """Test that _get_ema9_with_retry handles exceptions during calculation"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock: First attempt raises exception, second succeeds
        manager.get_current_ema9 = Mock(side_effect=[Exception("Network error"), 2500.0])

        result = manager._get_ema9_with_retry("RELIANCE.NS", broker_symbol="RELIANCE-EQ", symbol="RELIANCE")

        assert result == 2500.0
        assert manager.get_current_ema9.call_count == 2
