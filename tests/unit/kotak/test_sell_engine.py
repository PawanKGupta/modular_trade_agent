"""
Unit tests for Sell Engine (Sell Monitor)

Tests verify the migration to PriceService and IndicatorService
while maintaining backward compatibility.
"""

from unittest.mock import Mock, patch

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager


class TestSellEngineInitialization:
    """Test SellOrderManager initialization with services"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_init_with_services(self, mock_scrip_master, mock_auth):
        """Test that SellOrderManager initializes PriceService and IndicatorService"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        assert manager.price_service is not None
        assert manager.indicator_service is not None
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
