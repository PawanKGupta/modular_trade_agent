"""
Comprehensive backward compatibility tests for all migrated services

Verifies that all services maintain 100% backward compatibility after migration
to PriceService and IndicatorService.
"""

import inspect
from unittest.mock import Mock, patch

import pandas as pd

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from modules.kotak_neo_auto_trader.position_monitor import PositionMonitor
from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager


class TestBackwardCompatibilityMethodSignatures:
    """Test that all method signatures remain unchanged"""

    def test_auto_trade_engine_get_daily_indicators_signature(self):
        """Test that AutoTradeEngine.get_daily_indicators() signature is unchanged"""
        # Static method signature should be: get_daily_indicators(ticker: str) -> dict | None
        sig = inspect.signature(AutoTradeEngine.get_daily_indicators)
        params = list(sig.parameters.keys())
        assert params == ["ticker"], f"Expected ['ticker'], got {params}"
        # Check return type (can be dict[str, Any] | None or dict[str, typing.Any] | None)
        return_annotation_str = str(sig.return_annotation)
        assert (
            "dict" in return_annotation_str and "None" in return_annotation_str
        ), f"Return type should be dict | None, got {sig.return_annotation}"

    def test_auto_trade_engine_market_was_open_today_signature(self):
        """Test that AutoTradeEngine.market_was_open_today() signature is unchanged"""
        import inspect

        sig = inspect.signature(AutoTradeEngine.market_was_open_today)
        params = list(sig.parameters.keys())
        assert params == [], f"Expected [], got {params}"
        assert sig.return_annotation in (
            bool,
            "bool",
        ), f"Return type should be bool, got {sig.return_annotation}"

    def test_auto_trade_engine_retry_pending_orders_signature(self):
        """Test that retry_pending_orders_from_db() signature is unchanged"""
        sig = inspect.signature(AutoTradeEngine.retry_pending_orders_from_db)
        params = list(sig.parameters.keys())
        assert params == ["self"], f"Expected ['self'], got {params}"
        assert sig.return_annotation in (
            dict[str, int],
            "dict[str, int]",
        ), f"Return type should be dict[str, int], got {sig.return_annotation}"

    def test_position_monitor_monitor_all_positions_signature(self):
        """Test that PositionMonitor.monitor_all_positions() signature is unchanged"""
        sig = inspect.signature(PositionMonitor.monitor_all_positions)
        params = list(sig.parameters.keys())
        assert params == ["self"], f"Expected ['self'], got {params}"
        # Return type should be dict[str, Any]
        assert "dict" in str(sig.return_annotation).lower()

    def test_sell_engine_get_current_ltp_signature(self):
        """Test that SellOrderManager.get_current_ltp() signature is unchanged"""
        sig = inspect.signature(SellOrderManager.get_current_ltp)
        params = list(sig.parameters.keys())
        assert "ticker" in params, f"Expected 'ticker' in params, got {params}"
        assert sig.return_annotation in (
            float | None,
            "float | None",
        ), f"Return type should be float | None, got {sig.return_annotation}"

    def test_sell_engine_get_current_ema9_signature(self):
        """Test that SellOrderManager.get_current_ema9() signature is unchanged"""
        sig = inspect.signature(SellOrderManager.get_current_ema9)
        params = list(sig.parameters.keys())
        assert "ticker" in params, f"Expected 'ticker' in params, got {params}"
        assert sig.return_annotation in (
            float | None,
            "float | None",
        ), f"Return type should be float | None, got {sig.return_annotation}"

    def test_sell_engine_monitor_and_update_signature(self):
        """Test that SellOrderManager.monitor_and_update() signature is unchanged"""
        sig = inspect.signature(SellOrderManager.monitor_and_update)
        params = list(sig.parameters.keys())
        assert params == ["self"], f"Expected ['self'], got {params}"
        assert sig.return_annotation in (
            dict[str, int],
            "dict[str, int]",
        ), f"Return type should be dict[str, int], got {sig.return_annotation}"


class TestBackwardCompatibilityReturnTypes:
    """Test that all return types remain unchanged"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.get_indicator_service")
    def test_get_daily_indicators_return_type(self, mock_get_indicator):
        """Test that get_daily_indicators() returns dict | None"""
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
        mock_get_indicator.return_value = mock_indicator_service

        result = AutoTradeEngine.get_daily_indicators("RELIANCE.NS")
        assert isinstance(result, (dict, type(None))), f"Expected dict | None, got {type(result)}"
        if result:
            assert "close" in result
            assert "rsi10" in result
            assert "ema9" in result
            assert "ema200" in result

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.get_price_service")
    def test_market_was_open_today_return_type(self, mock_get_price):
        """Test that market_was_open_today() returns bool"""
        mock_price_service = Mock()
        mock_df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=5),
                "close": [20000, 20100, 20200, 20300, 20400],
            }
        )
        mock_price_service.get_price = Mock(return_value=mock_df)
        mock_get_price.return_value = mock_price_service

        result = AutoTradeEngine.market_was_open_today()
        assert isinstance(result, bool), f"Expected bool, got {type(result)}"

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_pending_orders_return_type(self, mock_auth):
        """Test that retry_pending_orders_from_db() returns dict[str, int]"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        engine = AutoTradeEngine(env_file="test.env")
        engine.orders_repo = Mock()
        engine.orders_repo.get_retriable_failed_orders = Mock(return_value=[])
        engine.user_id = 1

        result = engine.retry_pending_orders_from_db()
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "retried" in result
        assert "placed" in result
        assert "failed" in result
        assert "skipped" in result
        assert all(isinstance(v, int) for v in result.values())

    @patch("modules.kotak_neo_auto_trader.services.position_loader.get_position_loader")
    def test_position_monitor_return_type(self, mock_get_position_loader):
        """Test that monitor_all_positions() returns correct structure"""
        # Mock PositionLoader
        mock_position_loader = Mock()
        mock_position_loader.load_open_positions.return_value = []
        mock_position_loader.get_positions_by_symbol.return_value = {}
        mock_get_position_loader.return_value = mock_position_loader

        monitor = PositionMonitor(
            history_path="test_history.json",
            enable_alerts=False,
            enable_realtime_prices=False,
        )
        monitor.position_loader = mock_position_loader

        # Mock services
        monitor.price_service.get_price = Mock(return_value=pd.DataFrame())
        monitor.indicator_service.calculate_all_indicators = Mock(return_value=pd.DataFrame())
        monitor.price_service.get_realtime_price = Mock(return_value=None)

        result = monitor.monitor_all_positions()
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "monitored" in result
        assert "alerts_sent" in result
        assert "exit_imminent" in result
        assert "averaging_opportunities" in result
        # "positions" key is only present when there are positions to monitor
        # When no positions, it returns the basic structure without "positions"

    @patch("modules.kotak_neo_auto_trader.sell_engine.load_history")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    def test_sell_engine_get_current_ltp_return_type(self, mock_auth, mock_load_history):
        """Test that get_current_ltp() returns float | None"""
        mock_load_history.return_value = {"trades": []}
        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(
            auth=mock_auth_instance,
            history_path="test_history.json",
        )

        # Mock PriceService
        manager.price_service.get_realtime_price = Mock(return_value=2500.0)

        result = manager.get_current_ltp("RELIANCE.NS")
        assert isinstance(result, (float, type(None))), f"Expected float | None, got {type(result)}"

    @patch("modules.kotak_neo_auto_trader.sell_engine.load_history")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    def test_sell_engine_get_current_ema9_return_type(self, mock_auth, mock_load_history):
        """Test that get_current_ema9() returns float | None"""
        mock_load_history.return_value = {"trades": []}
        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(
            auth=mock_auth_instance,
            history_path="test_history.json",
        )

        # Mock IndicatorService
        manager.indicator_service.calculate_ema9_realtime = Mock(return_value=2480.0)

        result = manager.get_current_ema9("RELIANCE.NS")
        assert isinstance(result, (float, type(None))), f"Expected float | None, got {type(result)}"

    @patch("modules.kotak_neo_auto_trader.sell_engine.load_history")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    def test_sell_engine_monitor_and_update_return_type(self, mock_auth, mock_load_history):
        """Test that monitor_and_update() returns dict[str, int]"""
        mock_load_history.return_value = {"trades": []}
        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance

        manager = SellOrderManager(
            auth=mock_auth_instance,
            history_path="test_history.json",
        )

        # Mock services
        manager.price_service.get_realtime_price = Mock(return_value=None)
        manager.indicator_service.calculate_ema9_realtime = Mock(return_value=None)

        result = manager.monitor_and_update()
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert all(isinstance(v, int) for v in result.values())


class TestBackwardCompatibilityStaticMethods:
    """Test that static methods still work for backward compatibility"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.get_indicator_service")
    def test_static_get_daily_indicators_works(self, mock_get_indicator):
        """Test that static get_daily_indicators() method still works"""
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
        mock_get_indicator.return_value = mock_indicator_service

        # Call static method (no instance needed)
        result = AutoTradeEngine.get_daily_indicators("RELIANCE.NS")
        assert result is not None
        assert result["close"] == 2500.0

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.get_price_service")
    def test_static_market_was_open_today_works(self, mock_get_price):
        """Test that static market_was_open_today() method still works"""
        mock_price_service = Mock()
        mock_df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=5),
                "close": [20000, 20100, 20200, 20300, 20400],
            }
        )
        mock_price_service.get_price = Mock(return_value=mock_df)
        mock_get_price.return_value = mock_price_service

        # Call static method (no instance needed)
        result = AutoTradeEngine.market_was_open_today()
        assert isinstance(result, bool)


class TestBackwardCompatibilityDataStructures:
    """Test that data structures in return values remain unchanged"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.get_indicator_service")
    def test_get_daily_indicators_keys_unchanged(self, mock_get_indicator):
        """Test that get_daily_indicators() returns same keys as before"""
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
        mock_get_indicator.return_value = mock_indicator_service

        result = AutoTradeEngine.get_daily_indicators("RELIANCE.NS")
        assert result is not None

        # Verify all expected keys are present
        expected_keys = {"close", "rsi10", "ema9", "ema200", "avg_volume"}
        assert (
            set(result.keys()) == expected_keys
        ), f"Expected {expected_keys}, got {set(result.keys())}"

        # Verify value types
        assert isinstance(result["close"], float)
        assert isinstance(result["rsi10"], float)
        assert isinstance(result["ema9"], float)
        assert isinstance(result["ema200"], float)
        assert isinstance(result["avg_volume"], float)

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_summary_keys_unchanged(self, mock_auth):
        """Test that retry_pending_orders_from_db() returns same keys as before"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        engine = AutoTradeEngine(env_file="test.env")
        engine.orders_repo = Mock()
        engine.orders_repo.get_retriable_failed_orders = Mock(return_value=[])
        engine.user_id = 1

        result = engine.retry_pending_orders_from_db()

        # Verify all expected keys are present
        expected_keys = {"retried", "placed", "failed", "skipped"}
        assert (
            set(result.keys()) == expected_keys
        ), f"Expected {expected_keys}, got {set(result.keys())}"

        # Verify all values are integers
        assert all(isinstance(v, int) for v in result.values())


class TestBackwardCompatibilityErrorHandling:
    """Test that error handling behavior remains unchanged"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.get_indicator_service")
    def test_get_daily_indicators_handles_none(self, mock_get_indicator):
        """Test that get_daily_indicators() handles None gracefully"""
        mock_indicator_service = Mock()
        mock_indicator_service.get_daily_indicators_dict = Mock(return_value=None)
        mock_get_indicator.return_value = mock_indicator_service

        result = AutoTradeEngine.get_daily_indicators("INVALID.NS")
        assert result is None, "Should return None when indicators unavailable"

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.get_price_service")
    def test_market_was_open_today_handles_none(self, mock_get_price):
        """Test that market_was_open_today() handles None gracefully"""
        mock_price_service = Mock()
        mock_price_service.get_price = Mock(return_value=None)
        mock_get_price.return_value = mock_price_service

        result = AutoTradeEngine.market_was_open_today()
        assert isinstance(result, bool), "Should return bool even when data unavailable"
        assert result is False, "Should return False when data unavailable"

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    def test_retry_handles_exceptions(self, mock_auth):
        """Test that retry_pending_orders_from_db() handles exceptions gracefully"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = False
        mock_auth_instance.login.return_value = True
        mock_auth.return_value = mock_auth_instance

        engine = AutoTradeEngine(env_file="test.env")
        engine.orders_repo = Mock()
        engine.orders_repo.get_retriable_failed_orders = Mock(side_effect=Exception("DB Error"))
        engine.user_id = 1

        # Should not raise, should return summary with zeros
        result = engine.retry_pending_orders_from_db()
        assert isinstance(result, dict)
        assert result["retried"] == 0
        assert result["placed"] == 0
        assert result["failed"] == 0
        assert result["skipped"] == 0
