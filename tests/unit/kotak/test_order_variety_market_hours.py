"""
Tests for order variety selection based on market hours
"""

import types
from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine


class TestOrderVarietyMarketHours:
    """Test that orders use REGULAR variety during market hours and AMO when closed"""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock AutoTradeEngine instance"""
        engine = Mock(spec=AutoTradeEngine)
        engine.strategy_config = Mock()
        engine.strategy_config.default_variety = "AMO"
        engine.strategy_config.default_exchange = "NSE"
        engine.strategy_config.default_product = "CNC"
        return engine

    def test_get_order_variety_for_market_hours_during_market(self, mock_engine):
        """Test that REGULAR is returned during market hours (9:00 AM - 3:30 PM)"""

        # Create a real instance by patching __init__ to skip initialization
        def init_none(self):
            pass

        with patch.object(AutoTradeEngine, "__init__", init_none):
            engine = AutoTradeEngine()
            engine.strategy_config = Mock()
            engine.strategy_config.default_variety = "AMO"
            # Manually bind the method to the instance
            engine._get_order_variety_for_market_hours = types.MethodType(
                AutoTradeEngine._get_order_variety_for_market_hours, engine
            )

            # Test during pre-market (9:00 AM)
            with patch("core.volume_analysis.is_market_hours", return_value=True):
                variety = engine._get_order_variety_for_market_hours()
                assert variety == "REGULAR"

            # Test during regular market (12:00 PM)
            with patch("core.volume_analysis.is_market_hours", return_value=True):
                variety = engine._get_order_variety_for_market_hours()
                assert variety == "REGULAR"

            # Test at market close (3:30 PM)
            with patch("core.volume_analysis.is_market_hours", return_value=True):
                variety = engine._get_order_variety_for_market_hours()
                assert variety == "REGULAR"

    def test_get_order_variety_for_market_hours_after_market(self, mock_engine):
        """Test that AMO is returned when market is closed"""

        # Create a real instance by patching __init__ to skip initialization
        def init_none(self):
            pass

        with patch.object(AutoTradeEngine, "__init__", init_none):
            engine = AutoTradeEngine()
            engine.strategy_config = Mock()
            engine.strategy_config.default_variety = "AMO"
            # Manually bind the method to the instance
            engine._get_order_variety_for_market_hours = types.MethodType(
                AutoTradeEngine._get_order_variety_for_market_hours, engine
            )

            # Test before market open (8:00 AM)
            with patch("core.volume_analysis.is_market_hours", return_value=False):
                variety = engine._get_order_variety_for_market_hours()
                assert variety == "AMO"

            # Test after market close (4:00 PM)
            with patch("core.volume_analysis.is_market_hours", return_value=False):
                variety = engine._get_order_variety_for_market_hours()
                assert variety == "AMO"

    @patch("core.volume_analysis.is_market_hours")
    def test_attempt_place_order_uses_regular_during_market(self, mock_is_market_hours):
        """Test that _attempt_place_order uses REGULAR variety during market hours"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

        mock_is_market_hours.return_value = True

        with patch.object(AutoTradeEngine, "__init__", lambda self: None):
            engine = AutoTradeEngine()
            engine.orders = Mock()
            engine.orders.place_market_buy = Mock(return_value={"stat": "ok", "nOrdNo": "12345"})
            engine.orders.place_limit_buy = Mock(return_value={"stat": "ok", "nOrdNo": "12345"})
            engine.scrip_master = None
            engine.orders_repo = Mock()
            engine.telegram_notifier = None
            engine.db = None  # Add db attribute
            engine.user_id = 1  # Add user_id attribute
            engine.portfolio = Mock()  # Add portfolio attribute
            engine.strategy_config = Mock()
            engine.strategy_config.default_variety = "AMO"

            # Mock the order tracking functions
            with (
                patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_tracked_symbol"),
                patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_pending_order"),
                patch(
                    "modules.kotak_neo_auto_trader.auto_trade_engine.extract_order_id",
                    return_value="12345",
                ),
            ):
                # Call _attempt_place_order
                success, order_id = engine._attempt_place_order(
                    broker_symbol="RELIANCE-EQ", ticker="RELIANCE.NS", qty=10, close=2500.0, ind={}
                )

                # Verify that place_market_buy was called with REGULAR variety
                if engine.orders.place_market_buy.called:
                    call_args = engine.orders.place_market_buy.call_args
                    assert call_args[1]["variety"] == "REGULAR"

    @patch("core.volume_analysis.is_market_hours")
    def test_attempt_place_order_uses_amo_after_market(self, mock_is_market_hours):
        """Test that _attempt_place_order uses AMO variety when market is closed"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

        mock_is_market_hours.return_value = False

        with patch.object(AutoTradeEngine, "__init__", lambda self: None):
            engine = AutoTradeEngine()
            engine.orders = Mock()
            engine.orders.place_market_buy = Mock(return_value={"stat": "ok", "nOrdNo": "12345"})
            engine.orders.place_limit_buy = Mock(return_value={"stat": "ok", "nOrdNo": "12345"})
            engine.scrip_master = None
            engine.orders_repo = Mock()
            engine.telegram_notifier = None
            engine.db = None  # Add db attribute
            engine.user_id = 1  # Add user_id attribute
            engine.portfolio = Mock()  # Add portfolio attribute
            engine.strategy_config = Mock()
            engine.strategy_config.default_variety = "AMO"

            # Mock config module
            import modules.kotak_neo_auto_trader.config as config_module

            config_module.DEFAULT_VARIETY = "AMO"

            # Mock the order tracking functions
            with (
                patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_tracked_symbol"),
                patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_pending_order"),
                patch(
                    "modules.kotak_neo_auto_trader.auto_trade_engine.extract_order_id",
                    return_value="12345",
                ),
            ):
                # Call _attempt_place_order
                success, order_id = engine._attempt_place_order(
                    broker_symbol="RELIANCE-EQ", ticker="RELIANCE.NS", qty=10, close=2500.0, ind={}
                )

                # Verify that place_market_buy was called with AMO variety
                if engine.orders.place_market_buy.called:
                    call_args = engine.orders.place_market_buy.call_args
                    assert call_args[1]["variety"] == "AMO"
