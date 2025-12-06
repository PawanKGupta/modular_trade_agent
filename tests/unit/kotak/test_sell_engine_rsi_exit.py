"""
Unit tests for RSI Exit functionality in SellOrderManager

Tests verify RSI exit condition checking and limit-to-market order conversion.
"""

from unittest.mock import Mock, patch

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager


class TestRSI10CacheInitialization:
    """Test RSI10 cache initialization at market open"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_rsi10_cache_initialized_empty(self, mock_scrip_master, mock_auth):
        """Test that RSI10 cache is initialized as empty dict"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        assert isinstance(manager.rsi10_cache, dict)
        assert len(manager.rsi10_cache) == 0
        assert isinstance(manager.converted_to_market, set)
        assert len(manager.converted_to_market) == 0

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.SellOrderManager._get_previous_day_rsi10")
    def test_initialize_rsi10_cache_with_positions(
        self, mock_get_previous_rsi, mock_scrip_master, mock_auth
    ):
        """Test that RSI10 cache is initialized with previous day's RSI10 for positions"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock previous day RSI10
        mock_get_previous_rsi.return_value = 35.5

        # Create mock positions
        open_positions = [
            {"symbol": "RELIANCE", "ticker": "RELIANCE.NS"},
            {"symbol": "TCS", "ticker": "TCS.NS"},
        ]

        # Call cache initialization
        manager._initialize_rsi10_cache(open_positions)

        # Verify cache was populated
        assert len(manager.rsi10_cache) == 2
        assert manager.rsi10_cache["RELIANCE"] == 35.5
        assert manager.rsi10_cache["TCS"] == 35.5
        assert mock_get_previous_rsi.call_count == 2

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.SellOrderManager._get_previous_day_rsi10")
    def test_initialize_rsi10_cache_handles_missing_ticker(
        self, mock_get_previous_rsi, mock_scrip_master, mock_auth
    ):
        """Test that cache initialization handles positions without ticker"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Create positions with missing ticker
        open_positions = [
            {"symbol": "RELIANCE", "ticker": "RELIANCE.NS"},
            {"symbol": "TCS"},  # Missing ticker
        ]

        # Call cache initialization
        manager._initialize_rsi10_cache(open_positions)

        # Verify only position with ticker was cached
        assert len(manager.rsi10_cache) == 1
        assert "RELIANCE" in manager.rsi10_cache
        assert "TCS" not in manager.rsi10_cache
        assert mock_get_previous_rsi.call_count == 1

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.SellOrderManager._get_previous_day_rsi10")
    def test_initialize_rsi10_cache_handles_none_rsi(
        self, mock_get_previous_rsi, mock_scrip_master, mock_auth
    ):
        """Test that cache initialization handles None RSI values"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock None RSI
        mock_get_previous_rsi.return_value = None

        open_positions = [{"symbol": "RELIANCE", "ticker": "RELIANCE.NS"}]

        # Call cache initialization
        manager._initialize_rsi10_cache(open_positions)

        # Verify cache was not populated
        assert len(manager.rsi10_cache) == 0


class TestGetCurrentRSI10:
    """Test real-time RSI10 calculation with fallback"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_current_rsi10_uses_real_time_first(self, mock_scrip_master, mock_auth):
        """Test that real-time RSI10 is used when available"""
        import pandas as pd

        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock price_service and indicator_service
        mock_df = pd.DataFrame(
            {
                "close": [100, 101, 102],
                "rsi10": [None, None, 45.0],  # Latest row has RSI10
            }
        )
        manager.price_service.get_price = Mock(return_value=mock_df)
        manager.indicator_service.calculate_all_indicators = Mock(return_value=mock_df)

        # No cached value
        manager.rsi10_cache = {}

        rsi10 = manager._get_current_rsi10("RELIANCE", "RELIANCE.NS")

        # Verify real-time RSI was used
        assert rsi10 == 45.0
        assert manager.rsi10_cache["RELIANCE"] == 45.0

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_current_rsi10_updates_cache_with_real_time(self, mock_scrip_master, mock_auth):
        """Test that cache is updated when real-time RSI10 is available"""
        import pandas as pd

        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock price_service and indicator_service
        mock_df = pd.DataFrame(
            {
                "close": [100, 101, 102],
                "rsi10": [None, None, 45.0],  # Latest row has RSI10
            }
        )
        manager.price_service.get_price = Mock(return_value=mock_df)
        manager.indicator_service.calculate_all_indicators = Mock(return_value=mock_df)

        # Set cached value (previous day)
        manager.rsi10_cache = {"RELIANCE": 35.0}

        rsi10 = manager._get_current_rsi10("RELIANCE", "RELIANCE.NS")

        # Verify real-time RSI was used and cache updated
        assert rsi10 == 45.0
        assert manager.rsi10_cache["RELIANCE"] == 45.0

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_current_rsi10_fallback_to_cache(self, mock_scrip_master, mock_auth):
        """Test that cached value is used when real-time RSI10 is unavailable"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock real-time RSI10 unavailable (price_service returns None or empty)
        manager.price_service.get_price = Mock(return_value=None)

        # Set cached value (previous day)
        manager.rsi10_cache = {"RELIANCE": 35.0}

        rsi10 = manager._get_current_rsi10("RELIANCE", "RELIANCE.NS")

        # Verify cached value was used
        assert rsi10 == 35.0

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_current_rsi10_returns_none_if_no_data(self, mock_scrip_master, mock_auth):
        """Test that None is returned when neither real-time nor cached RSI10 is available"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock real-time RSI10 unavailable (price_service returns None)
        manager.price_service.get_price = Mock(return_value=None)

        # No cached value
        manager.rsi10_cache = {}

        rsi10 = manager._get_current_rsi10("RELIANCE", "RELIANCE.NS")

        # Verify None was returned
        assert rsi10 is None


class TestRSIExitConditionCheck:
    """Test RSI exit condition checking"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.SellOrderManager._get_current_rsi10")
    @patch("modules.kotak_neo_auto_trader.sell_engine.SellOrderManager._convert_to_market_sell")
    def test_check_rsi_exit_condition_triggers_when_rsi_above_50(
        self, mock_convert, mock_get_rsi, mock_scrip_master, mock_auth
    ):
        """Test that RSI exit is triggered when RSI10 > 50"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock RSI10 > 50
        mock_get_rsi.return_value = 55.0
        mock_convert.return_value = True

        order_info = {"order_id": "ORDER123", "ticker": "RELIANCE.NS", "qty": 10}

        result = manager._check_rsi_exit_condition("RELIANCE", order_info)

        # Verify conversion was attempted
        assert result is True
        mock_get_rsi.assert_called_once_with("RELIANCE", "RELIANCE.NS")
        mock_convert.assert_called_once_with("RELIANCE", order_info, 55.0)

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.SellOrderManager._get_current_rsi10")
    def test_check_rsi_exit_condition_no_trigger_when_rsi_below_50(
        self, mock_get_rsi, mock_scrip_master, mock_auth
    ):
        """Test that RSI exit is not triggered when RSI10 <= 50"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock RSI10 <= 50
        mock_get_rsi.return_value = 45.0

        order_info = {"order_id": "ORDER123", "ticker": "RELIANCE.NS", "qty": 10}

        result = manager._check_rsi_exit_condition("RELIANCE", order_info)

        # Verify no conversion
        assert result is False

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_check_rsi_exit_condition_skips_already_converted(self, mock_scrip_master, mock_auth):
        """Test that already converted orders are skipped"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mark as already converted
        manager.converted_to_market.add("RELIANCE")

        order_info = {"order_id": "ORDER123", "ticker": "RELIANCE.NS", "qty": 10}

        result = manager._check_rsi_exit_condition("RELIANCE", order_info)

        # Verify skipped
        assert result is False

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.SellOrderManager._get_current_rsi10")
    def test_check_rsi_exit_condition_handles_missing_ticker(
        self, mock_get_rsi, mock_scrip_master, mock_auth
    ):
        """Test that missing ticker is handled gracefully"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        order_info = {"order_id": "ORDER123", "qty": 10}  # Missing ticker

        result = manager._check_rsi_exit_condition("RELIANCE", order_info)

        # Verify skipped
        assert result is False
        mock_get_rsi.assert_not_called()

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.SellOrderManager._get_current_rsi10")
    def test_check_rsi_exit_condition_handles_none_rsi(
        self, mock_get_rsi, mock_scrip_master, mock_auth
    ):
        """Test that None RSI is handled gracefully"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock None RSI
        mock_get_rsi.return_value = None

        order_info = {"order_id": "ORDER123", "ticker": "RELIANCE.NS", "qty": 10}

        result = manager._check_rsi_exit_condition("RELIANCE", order_info)

        # Verify skipped
        assert result is False


class TestConvertToMarketSell:
    """Test limit-to-market order conversion"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_convert_to_market_sell_modify_success(self, mock_scrip_master, mock_auth):
        """Test successful order modification (primary path)"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock successful modify
        manager.orders.modify_order = Mock(return_value={"stat": "Ok", "orderId": "ORDER123"})

        order_info = {
            "order_id": "ORDER123",
            "qty": 10,
            "placed_symbol": "RELIANCE-EQ",
        }

        result = manager._convert_to_market_sell("RELIANCE", order_info, 55.0)

        # Verify modification was attempted
        assert result is True
        manager.orders.modify_order.assert_called_once()
        call_args = manager.orders.modify_order.call_args
        assert call_args[1]["order_id"] == "ORDER123"
        assert call_args[1]["order_type"] == "MKT"
        assert "RELIANCE" in manager.converted_to_market

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_convert_to_market_sell_modify_failure_fallback(self, mock_scrip_master, mock_auth):
        """Test fallback to cancel+place when modify fails"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock modify failure
        manager.orders.modify_order = Mock(return_value={"stat": "Not_Ok", "emsg": "Error"})

        # Mock successful cancel and place
        manager.orders.cancel_order = Mock(return_value=True)
        manager.orders.place_market_sell = Mock(return_value={"stat": "Ok", "orderId": "MARKET123"})
        manager._is_valid_order_response = Mock(return_value=True)
        manager._extract_order_id = Mock(return_value="MARKET123")
        manager._remove_order = Mock()

        order_info = {
            "order_id": "ORDER123",
            "qty": 10,
            "placed_symbol": "RELIANCE-EQ",
        }

        result = manager._convert_to_market_sell("RELIANCE", order_info, 55.0)

        # Verify fallback was used
        assert result is True
        manager.orders.cancel_order.assert_called_once_with("ORDER123")
        manager.orders.place_market_sell.assert_called_once()
        assert "RELIANCE" in manager.converted_to_market

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_convert_to_market_sell_cancel_failure(self, mock_scrip_master, mock_auth):
        """Test error handling when cancel fails"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock modify failure
        manager.orders.modify_order = Mock(return_value={"stat": "Not_Ok"})

        # Mock cancel failure
        manager.orders.cancel_order = Mock(return_value=False)
        manager._send_rsi_exit_error_notification = Mock()

        order_info = {
            "order_id": "ORDER123",
            "qty": 10,
            "placed_symbol": "RELIANCE-EQ",
        }

        result = manager._convert_to_market_sell("RELIANCE", order_info, 55.0)

        # Verify error handling
        assert result is False
        manager._send_rsi_exit_error_notification.assert_called_once_with(
            "RELIANCE", "cancel_failed", 55.0
        )
        assert "RELIANCE" not in manager.converted_to_market

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_convert_to_market_sell_place_failure(self, mock_scrip_master, mock_auth):
        """Test error handling when place fails"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock modify failure
        manager.orders.modify_order = Mock(return_value={"stat": "Not_Ok"})

        # Mock cancel success, place failure
        manager.orders.cancel_order = Mock(return_value=True)
        manager.orders.place_market_sell = Mock(return_value={"stat": "Not_Ok"})
        manager._is_valid_order_response = Mock(return_value=False)
        manager._send_rsi_exit_error_notification = Mock()

        order_info = {
            "order_id": "ORDER123",
            "qty": 10,
            "placed_symbol": "RELIANCE-EQ",
        }

        result = manager._convert_to_market_sell("RELIANCE", order_info, 55.0)

        # Verify error handling
        assert result is False
        manager._send_rsi_exit_error_notification.assert_called_once_with(
            "RELIANCE", "place_failed", 55.0
        )
        assert "RELIANCE" not in manager.converted_to_market

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_convert_to_market_sell_handles_missing_order_id(self, mock_scrip_master, mock_auth):
        """Test error handling when order_id is missing"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        order_info = {
            "qty": 10,
            "placed_symbol": "RELIANCE-EQ",
        }  # Missing order_id

        result = manager._convert_to_market_sell("RELIANCE", order_info, 55.0)

        # Verify error handling
        assert result is False
        assert "RELIANCE" not in manager.converted_to_market
