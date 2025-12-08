"""
Unit tests for AutoTradeEngine pending orders cache optimization

Tests verify that get_pending_orders() is called only once per place_new_entries()
call, and the cached result is reused for all duplicate checks and manual order checks.

This optimization reduces API calls from 5-6 per "buy once" click to just 1.
"""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine, Recommendation


class TestPendingOrdersCacheOptimization:
    """Test that pending orders are cached and reused to avoid redundant API calls"""

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.AutoTradeEngine.get_daily_indicators")
    def test_place_new_entries_caches_pending_orders_single_call(
        self, mock_get_indicators, mock_auth
    ):
        """Test that get_pending_orders() is called only once for multiple recommendations"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock indicators
        mock_get_indicators.return_value = {
            "close": 100.0,
            "rsi10": 25.0,
            "ema9": 95.0,
            "ema200": 90.0,
            "avg_volume": 1000000,
        }

        # Create engine
        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.history_path = None  # Disable file-based storage
        engine.portfolio = Mock()
        engine.portfolio.get_holdings = Mock(return_value={"data": []})
        engine.portfolio.get_limits = Mock(
            return_value={"data": {"day": {"used": 0, "available": 100000}}}
        )
        engine.orders = Mock()
        
        # Mock get_pending_orders to track calls
        mock_pending_orders = [
            {"order_id": "ORD001", "symbol": "RELIANCE-EQ", "status": "PENDING"},
            {"order_id": "ORD002", "symbol": "TCS-EQ", "status": "PENDING"},
        ]
        engine.orders.get_pending_orders = Mock(return_value=mock_pending_orders)

        # Mock OrderValidationService
        engine.order_validation_service = Mock()
        engine.order_validation_service.check_portfolio_capacity = Mock(
            return_value=(True, 3, 10)  # has_capacity, current_count, max_size
        )
        engine.order_validation_service.check_duplicate_order = Mock(
            return_value=(False, None)  # is_duplicate, reason
        )
        engine.order_validation_service.check_volume_ratio = Mock(
            return_value=(True, 0.5, "Rs 500+ (10%)")  # is_valid, ratio, tier_info
        )
        engine.order_validation_service.check_balance = Mock(
            return_value=(True, 100000.0, 40)  # has_sufficient, available_cash, affordable_qty
        )

        # Mock PortfolioService
        engine.portfolio_service = Mock()
        engine.portfolio_service.get_portfolio_count = Mock(return_value=3)
        engine.portfolio_service.get_current_positions = Mock(return_value=[])

        # Mock other dependencies
        engine.orders_repo = Mock()
        engine.orders_repo.list = Mock(return_value=[])
        engine.positions_repo = Mock()
        engine.positions_repo.list = Mock(return_value=[])
        engine.orders.place_order = Mock(
            return_value={"order_id": "NEW_ORD001", "status": "PENDING"}
        )

        # Create multiple recommendations to test caching
        recommendations = [
            Recommendation(ticker="RELIANCE.NS", verdict="BUY", last_close=100.0, execution_capital=None),
            Recommendation(ticker="TCS.NS", verdict="STRONG_BUY", last_close=100.0, execution_capital=None),
        ]

        # Call place_new_entries
        result = engine.place_new_entries(recommendations)

        # CRITICAL: get_pending_orders() should be called ONLY ONCE
        # regardless of how many recommendations we process
        assert (
            engine.orders.get_pending_orders.call_count == 1
        ), (
            f"Expected get_pending_orders() to be called once, "
            f"but it was called {engine.orders.get_pending_orders.call_count} times. "
            f"This defeats the cache optimization."
        )

        # Verify the cached orders were passed to check_duplicate_order
        # It should be called multiple times (once per recommendation) but with cached orders
        assert (
            engine.order_validation_service.check_duplicate_order.call_count >= 1
        ), "check_duplicate_order should be called at least once"

        # Verify cached_pending_orders was passed to check_duplicate_order calls
        found_cached_orders = False
        for call in engine.order_validation_service.check_duplicate_order.call_args_list:
            call_kwargs = call.kwargs
            if "cached_pending_orders" in call_kwargs:
                assert (
                    call_kwargs["cached_pending_orders"] == mock_pending_orders
                ), "Cached orders should be passed to check_duplicate_order"
                found_cached_orders = True

        assert found_cached_orders, (
            "check_duplicate_order should be called with cached_pending_orders parameter"
        )

    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth")
    @patch("modules.kotak_neo_auto_trader.auto_trade_engine.AutoTradeEngine.get_daily_indicators")
    def test_place_new_entries_handles_get_pending_orders_failure_gracefully(
        self, mock_get_indicators, mock_auth
    ):
        """Test that if get_pending_orders() fails, place_new_entries() continues without cache"""
        mock_auth_instance = Mock()
        mock_auth_instance.is_authenticated.return_value = True
        mock_auth.return_value = mock_auth_instance

        # Mock indicators
        mock_get_indicators.return_value = {
            "close": 100.0,
            "rsi10": 25.0,
            "ema9": 95.0,
            "ema200": 90.0,
            "avg_volume": 1000000,
        }

        # Create engine
        engine = AutoTradeEngine(env_file="test.env", user_id=1)
        engine.history_path = None  # Disable file-based storage
        engine.portfolio = Mock()
        engine.portfolio.get_holdings = Mock(return_value={"data": []})
        engine.portfolio.get_limits = Mock(
            return_value={"data": {"day": {"used": 0, "available": 100000}}}
        )
        engine.orders = Mock()
        
        # Mock get_pending_orders to raise an exception
        engine.orders.get_pending_orders = Mock(side_effect=Exception("API Error"))

        # Mock OrderValidationService
        engine.order_validation_service = Mock()
        engine.order_validation_service.check_portfolio_capacity = Mock(
            return_value=(True, 3, 10)
        )
        engine.order_validation_service.check_duplicate_order = Mock(
            return_value=(False, None)
        )
        engine.order_validation_service.check_volume_ratio = Mock(
            return_value=(True, 0.5, "Rs 500+ (10%)")
        )
        engine.order_validation_service.check_balance = Mock(
            return_value=(True, 100000.0, 40)
        )

        # Mock PortfolioService
        engine.portfolio_service = Mock()
        engine.portfolio_service.get_portfolio_count = Mock(return_value=3)
        engine.portfolio_service.get_current_positions = Mock(return_value=[])

        # Mock other dependencies
        engine.orders_repo = Mock()
        engine.orders_repo.list = Mock(return_value=[])
        engine.positions_repo = Mock()
        engine.positions_repo.list = Mock(return_value=[])
        engine.orders.place_order = Mock(
            return_value={"order_id": "NEW_ORD001", "status": "PENDING"}
        )

        # Create recommendation
        recommendations = [Recommendation(ticker="RELIANCE.NS", verdict="BUY", last_close=100.0, execution_capital=None)]

        # Call place_new_entries - should not raise exception
        result = engine.place_new_entries(recommendations)

        # Verify get_pending_orders was called (attempted to cache)
        # When cache fails, it will be called multiple times as fallback (once for initial cache,
        # then again for _check_for_manual_orders and broker order check)
        assert (
            engine.orders.get_pending_orders.call_count >= 1
        ), "get_pending_orders should be called at least once (initial cache attempt)"

        # Verify place_new_entries completed successfully despite cache failure
        assert result is not None, "place_new_entries should return a result even if cache fails"
        
        # Verify that when cache fails, the system gracefully falls back to per-check fetching
        # This is expected behavior - cache failure should not break the flow
