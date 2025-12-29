"""
Unit tests for Sell Engine (Sell Monitor)

Tests verify the migration to PriceService and IndicatorService
while maintaining backward compatibility.
"""

from unittest.mock import Mock, patch

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
    def test_get_ema9_with_retry_succeeds_on_first_attempt(self, mock_scrip_master, mock_auth):
        """Test that _get_ema9_with_retry succeeds on first attempt"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock successful EMA9 calculation
        manager.get_current_ema9 = Mock(return_value=2500.0)

        result = manager._get_ema9_with_retry(
            "RELIANCE.NS", broker_symbol="RELIANCE-EQ", symbol="RELIANCE-EQ"
        )  # Full symbol after migration

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

        result = manager._get_ema9_with_retry(
            "RELIANCE.NS", broker_symbol="RELIANCE-EQ", symbol="RELIANCE-EQ"
        )  # Full symbol after migration

        assert result == 2500.0
        assert manager.get_current_ema9.call_count == 2

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_ema9_with_retry_falls_back_to_yesterday_ema9(self, mock_scrip_master, mock_auth):
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
        if (
            not hasattr(manager.indicator_service, "price_service")
            or manager.indicator_service.price_service is None
        ):
            manager.indicator_service.price_service = Mock()
        manager.indicator_service.price_service.get_price = Mock(return_value=mock_df)

        result = manager._get_ema9_with_retry(
            "RELIANCE.NS", broker_symbol="RELIANCE-EQ", symbol="RELIANCE-EQ"
        )  # Full symbol after migration

        # Should return yesterday's EMA9 (calculated from historical data)
        assert result is not None
        assert result > 0
        # Verify fallback was attempted
        manager.indicator_service.price_service.get_price.assert_called_once()

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_get_ema9_with_retry_returns_none_when_all_fail(self, mock_scrip_master, mock_auth):
        """Test that _get_ema9_with_retry returns None when all attempts and fallback fail"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Mock: All attempts fail
        manager.get_current_ema9 = Mock(return_value=None)

        # Mock: Fallback also fails (no price service or empty data)
        manager.indicator_service.price_service = None

        result = manager._get_ema9_with_retry(
            "RELIANCE.NS", broker_symbol="RELIANCE-EQ", symbol="RELIANCE-EQ"
        )  # Full symbol after migration

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

        result = manager._get_ema9_with_retry(
            "RELIANCE.NS", broker_symbol="RELIANCE-EQ", symbol="RELIANCE-EQ"
        )  # Full symbol after migration

        assert result == 2500.0
        assert manager.get_current_ema9.call_count == 2


class TestRemoveRejectedOrders:
    """Test _remove_rejected_orders handling of cancelled and rejected orders"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_cancelled_order_with_open_position_replaces_order(self, mock_scrip_master, mock_auth):
        """Test that cancelled order with open position triggers re-placement"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Setup cancelled order in active tracking
        manager.active_sell_orders["MIRZAINT"] = {
            "order_id": "CANCELLED123",
            "target_price": 37.44,
            "qty": 267,
            "ticker": "MIRZAINT.NS",
            "placed_symbol": "MIRZAINT-EQ",
        }

        # Mock positions repo - position exists and is open
        mock_position = Mock()
        mock_position.closed_at = None
        manager.positions_repo = Mock()
        manager.positions_repo.get_by_symbol.return_value = mock_position
        manager.user_id = 1

        # Mock broker orders - show order as cancelled
        cancelled_order = {
            "neoOrdNo": "CANCELLED123",
            "orderStatus": "cancelled",
            "transactionType": "SELL",
            "trdSym": "MIRZAINT-EQ",
        }

        manager.orders = Mock()
        manager.orders.get_orders.return_value = {"data": [cancelled_order]}

        # Mock _remove_from_tracking and place_sell_order
        manager._remove_from_tracking = Mock()
        manager.place_sell_order = Mock(return_value="NEW_ORDER456")
        manager._get_ema9_with_retry = Mock(return_value=37.50)

        # Call the method
        manager._remove_rejected_orders()

        # Verify order was removed from tracking first
        manager._remove_from_tracking.assert_called_once_with("MIRZAINT")

        # Verify new order was placed
        manager.place_sell_order.assert_called_once()
        call_args = manager.place_sell_order.call_args
        assert call_args[0][1] == 37.50  # new ema9

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_cancelled_order_with_closed_position_removes_from_tracking(
        self, mock_scrip_master, mock_auth
    ):
        """Test that cancelled order with closed position is removed"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Setup cancelled order
        manager.active_sell_orders["SALSTEEL"] = {
            "order_id": "CANCELLED789",
            "target_price": 40.72,
            "qty": 500,
        }

        # Mock positions repo - position is closed
        mock_position = Mock()
        mock_position.closed_at = "2025-12-29 14:30:00"
        manager.positions_repo = Mock()
        manager.positions_repo.get_by_symbol.return_value = mock_position
        manager.user_id = 1

        # Mock broker orders
        cancelled_order = {
            "neoOrdNo": "CANCELLED789",
            "orderStatus": "cancelled",
            "transactionType": "SELL",
        }

        manager.orders = Mock()
        manager.orders.get_orders.return_value = {"data": [cancelled_order]}

        # Mock _remove_from_tracking
        manager._remove_from_tracking = Mock()

        # Call the method
        manager._remove_rejected_orders()

        # Verify order was removed (not re-placed)
        manager._remove_from_tracking.assert_called_once_with("SALSTEEL")

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_rejected_order_is_removed_from_tracking(self, mock_scrip_master, mock_auth):
        """Test that rejected orders are removed without re-placement"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Setup rejected order
        manager.active_sell_orders["ORIENTCEM"] = {
            "order_id": "REJECTED111",
            "target_price": 169.70,
            "qty": 1096,
        }

        # Mock positions repo
        manager.positions_repo = Mock()
        manager.user_id = 1

        # Mock broker orders - show order as rejected
        rejected_order = {
            "neoOrdNo": "REJECTED111",
            "orderStatus": "rejected",
            "transactionType": "SELL",
            "rejectionReason": "RMS:Margin Exceeds",
        }

        manager.orders = Mock()
        manager.orders.get_orders.return_value = {"data": [rejected_order]}

        # Mock _remove_from_tracking and place_sell_order
        manager._remove_from_tracking = Mock()
        manager.place_sell_order = Mock()

        # Call the method
        manager._remove_rejected_orders()

        # Verify order was removed
        manager._remove_from_tracking.assert_called_once_with("ORIENTCEM")

        # Verify new order was NOT placed
        manager.place_sell_order.assert_not_called()

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_cancelled_order_without_ticker_logs_warning(self, mock_scrip_master, mock_auth):
        """Test that cancelled order without ticker logs warning"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Setup cancelled order without ticker
        manager.active_sell_orders["DREAMFOLKS"] = {
            "order_id": "CANCELLED555",
            "target_price": 108.25,
            "qty": 2129,
            "ticker": None,  # Missing ticker
        }

        # Mock positions repo - position exists
        mock_position = Mock()
        mock_position.closed_at = None
        manager.positions_repo = Mock()
        manager.positions_repo.get_by_symbol.return_value = mock_position
        manager.user_id = 1

        # Mock broker orders
        cancelled_order = {
            "neoOrdNo": "CANCELLED555",
            "orderStatus": "cancelled",
            "transactionType": "SELL",
        }

        manager.orders = Mock()
        manager.orders.get_orders.return_value = {"data": [cancelled_order]}

        # Mock _remove_from_tracking
        manager._remove_from_tracking = Mock()
        manager.place_sell_order = Mock()

        # Call the method
        manager._remove_rejected_orders()

        # Verify order was removed
        manager._remove_from_tracking.assert_called_once_with("DREAMFOLKS")

        # Verify new order was NOT placed (no ticker)
        manager.place_sell_order.assert_not_called()

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_cancelled_order_ema9_calculation_failure(self, mock_scrip_master, mock_auth):
        """Test handling when EMA9 calculation fails for cancelled order"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Setup cancelled order
        manager.active_sell_orders["TESTSTOCK"] = {
            "order_id": "CANCELLED999",
            "target_price": 100.00,
            "qty": 100,
            "ticker": "TESTSTOCK.NS",
        }

        # Mock positions repo - position exists
        mock_position = Mock()
        mock_position.closed_at = None
        manager.positions_repo = Mock()
        manager.positions_repo.get_by_symbol.return_value = mock_position
        manager.user_id = 1

        # Mock broker orders
        cancelled_order = {
            "neoOrdNo": "CANCELLED999",
            "orderStatus": "cancelled",
            "transactionType": "SELL",
        }

        manager.orders = Mock()
        manager.orders.get_orders.return_value = {"data": [cancelled_order]}

        # Mock _remove_from_tracking
        manager._remove_from_tracking = Mock()
        manager.place_sell_order = Mock()
        manager._get_ema9_with_retry = Mock(return_value=None)  # EMA9 calc fails

        # Call the method
        manager._remove_rejected_orders()

        # Verify order was removed
        manager._remove_from_tracking.assert_called_once_with("TESTSTOCK")

        # Verify new order was NOT placed (no EMA9)
        manager.place_sell_order.assert_not_called()

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    def test_multiple_cancelled_orders_mixed_positions(self, mock_scrip_master, mock_auth):
        """Test handling of multiple cancelled orders with mixed open/closed positions"""
        mock_auth_instance = Mock()
        mock_auth_instance.client = None
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(auth=mock_auth_instance, history_path="test_history.json")

        # Setup multiple cancelled orders
        manager.active_sell_orders["STOCK1"] = {
            "order_id": "CANCELLED001",
            "target_price": 100.00,
            "qty": 100,
            "ticker": "STOCK1.NS",
        }
        manager.active_sell_orders["STOCK2"] = {
            "order_id": "CANCELLED002",
            "target_price": 200.00,
            "qty": 50,
            "ticker": "STOCK2.NS",
        }

        # Mock positions repo - STOCK1 open, STOCK2 closed
        def get_position_side_effect(user_id, symbol):
            if symbol == "STOCK1":
                mock_pos = Mock()
                mock_pos.closed_at = None
                return mock_pos
            elif symbol == "STOCK2":
                mock_pos = Mock()
                mock_pos.closed_at = "2025-12-29 14:30:00"
                return mock_pos
            return None

        manager.positions_repo = Mock()
        manager.positions_repo.get_by_symbol.side_effect = get_position_side_effect
        manager.user_id = 1

        # Mock broker orders
        manager.orders = Mock()
        manager.orders.get_orders.return_value = {
            "data": [
                {"neoOrdNo": "CANCELLED001", "orderStatus": "cancelled", "transactionType": "SELL"},
                {"neoOrdNo": "CANCELLED002", "orderStatus": "cancelled", "transactionType": "SELL"},
            ]
        }

        # Mock methods
        manager._remove_from_tracking = Mock()
        manager.place_sell_order = Mock(return_value="NEW_ORDER")
        manager._get_ema9_with_retry = Mock(return_value=105.00)

        # Call the method
        manager._remove_rejected_orders()

        # Verify both orders were removed from tracking
        assert manager._remove_from_tracking.call_count == 2  # Both removed (STOCK1 and STOCK2)

        # Verify new order was placed only for STOCK1 (open position)
        manager.place_sell_order.assert_called_once()
