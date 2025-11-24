#!/usr/bin/env python3
"""
Tests to verify that place_new_entries no longer processes retry queue

This test ensures that the retry queue processing has been removed from
buy order placement and retries only happen at scheduled time.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from config.strategy_config import StrategyConfig


@pytest.fixture
def mock_auth():
    """Mock KotakNeoAuth"""
    auth = MagicMock()
    auth.is_authenticated.return_value = True
    auth.login.return_value = True
    return auth


@pytest.fixture
def strategy_config():
    """Default strategy config"""
    return StrategyConfig(
        rsi_period=14,
        rsi_oversold=25.0,
        user_capital=300000.0,
        max_portfolio_size=6,
    )


@pytest.fixture
def auto_trade_engine(mock_auth, strategy_config):
    """Create AutoTradeEngine instance"""
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth") as mock_auth_class:
        mock_auth_class.return_value = mock_auth

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,
            user_id=1,
            db_session=MagicMock(),
            strategy_config=strategy_config,
        )

        # Mock portfolio and orders
        engine.portfolio = MagicMock()
        engine.portfolio.get_holdings.return_value = {"data": []}  # Valid holdings response
        engine.orders = MagicMock()
        engine.orders_repo = MagicMock()
        engine.telegram_notifier = MagicMock()
        engine.telegram_notifier.enabled = True

        return engine


class TestNoRetryDuringPlacement:
    """Test that place_new_entries does not process retry queue"""

    def test_place_new_entries_does_not_call_get_failed_orders(self, auto_trade_engine):
        """Test that place_new_entries does not call _get_failed_orders"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        # Mock recommendation
        rec = Recommendation(
            ticker="RELIANCE.NS",
            verdict="buy",
            last_close=2450.0,
            execution_capital=30000.0,
        )

        # Mock portfolio checks
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
        auto_trade_engine.portfolio_size = Mock(return_value=2)
        auto_trade_engine.has_holding = Mock(return_value=False)
        auto_trade_engine.has_active_buy_order = Mock(return_value=False)

        # Mock indicators
        auto_trade_engine.get_daily_indicators = Mock(
            return_value={
                "close": 2450.0,
                "rsi10": 25.0,
                "ema9": 2400.0,
                "ema200": 2300.0,
                "avg_volume": 1000000,
            }
        )

        # Mock balance check - use order_validation_service
        auto_trade_engine.get_affordable_qty = Mock(return_value=20)
        auto_trade_engine.get_available_cash = Mock(return_value=50000.0)
        auto_trade_engine.check_position_volume_ratio = Mock(return_value=True)
        auto_trade_engine._calculate_execution_capital = Mock(return_value=30000.0)

        # Mock portfolio_service and order_validation_service
        auto_trade_engine.portfolio_service.get_current_positions = Mock(return_value=[])
        auto_trade_engine.portfolio_service.get_portfolio_count = Mock(return_value=2)
        auto_trade_engine.portfolio_service.check_portfolio_capacity = Mock(
            return_value=(True, 2, 6)
        )
        auto_trade_engine.portfolio_service.has_position = Mock(return_value=False)

        auto_trade_engine.order_validation_service.check_balance = Mock(
            return_value=(True, 50000.0, 20)
        )
        auto_trade_engine.order_validation_service.check_portfolio_capacity = Mock(
            return_value=(True, 2, 6)
        )
        auto_trade_engine.order_validation_service.check_duplicate_order = Mock(
            return_value=(False, None)
        )
        auto_trade_engine.order_validation_service.check_volume_ratio = Mock(
            return_value=(True, 0.01, None)
        )
        auto_trade_engine.order_validation_service.get_available_cash = Mock(return_value=50000.0)
        auto_trade_engine.order_validation_service.orders = auto_trade_engine.orders
        auto_trade_engine.order_validation_service.orders_repo = auto_trade_engine.orders_repo

        # Mock order placement
        auto_trade_engine._attempt_place_order = Mock(return_value=(True, "ORDER123"))

        # Mock _get_failed_orders to track if it's called
        auto_trade_engine._get_failed_orders = Mock()

        # Call place_new_entries
        summary = auto_trade_engine.place_new_entries([rec])

        # Verify _get_failed_orders was NOT called (retry queue processing removed)
        auto_trade_engine._get_failed_orders.assert_not_called()

        # Verify order was placed
        assert summary["placed"] == 1
        assert "retried" not in summary  # retried field removed from summary

    def test_place_new_entries_creates_retry_pending_on_insufficient_balance(
        self, auto_trade_engine
    ):
        """Test that insufficient balance creates RETRY_PENDING order in DB"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        # Mock recommendation
        rec = Recommendation(
            ticker="RELIANCE.NS",
            verdict="buy",
            last_close=2450.0,
            execution_capital=30000.0,
        )

        # Mock portfolio checks
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
        auto_trade_engine.portfolio_size = Mock(return_value=2)
        auto_trade_engine.has_holding = Mock(return_value=False)
        auto_trade_engine.has_active_buy_order = Mock(return_value=False)

        # Mock indicators
        auto_trade_engine.get_daily_indicators = Mock(
            return_value={
                "close": 2450.0,
                "rsi10": 25.0,
                "ema9": 2400.0,
                "ema200": 2300.0,
                "avg_volume": 1000000,
            }
        )

        # Mock insufficient balance - use order_validation_service
        auto_trade_engine.get_affordable_qty = Mock(return_value=5)  # Less than required
        auto_trade_engine.get_available_cash = Mock(return_value=10000.0)
        auto_trade_engine.check_position_volume_ratio = Mock(return_value=True)
        auto_trade_engine._calculate_execution_capital = Mock(return_value=30000.0)

        # Mock portfolio_service and order_validation_service
        auto_trade_engine.portfolio_service.get_current_positions = Mock(return_value=[])
        auto_trade_engine.portfolio_service.get_portfolio_count = Mock(return_value=2)
        auto_trade_engine.portfolio_service.check_portfolio_capacity = Mock(
            return_value=(True, 2, 6)
        )
        auto_trade_engine.portfolio_service.has_position = Mock(return_value=False)

        # Mock order_validation_service to return insufficient balance
        auto_trade_engine.order_validation_service.check_balance = Mock(
            return_value=(False, 10000.0, 5)  # Insufficient balance
        )
        auto_trade_engine.order_validation_service.check_portfolio_capacity = Mock(
            return_value=(True, 2, 6)
        )
        auto_trade_engine.order_validation_service.check_duplicate_order = Mock(
            return_value=(False, None)
        )
        auto_trade_engine.order_validation_service.check_volume_ratio = Mock(
            return_value=(True, 0.01, None)
        )
        auto_trade_engine.order_validation_service.get_available_cash = Mock(return_value=10000.0)
        auto_trade_engine.order_validation_service.orders = auto_trade_engine.orders
        auto_trade_engine.order_validation_service.orders_repo = auto_trade_engine.orders_repo

        # Mock _add_failed_order
        auto_trade_engine._add_failed_order = Mock()

        # Call place_new_entries
        summary = auto_trade_engine.place_new_entries([rec])

        # Verify order was NOT placed
        assert summary["placed"] == 0
        assert summary["failed_balance"] == 1

        # Verify _add_failed_order was called to create RETRY_PENDING order
        auto_trade_engine._add_failed_order.assert_called_once()
        call_args = auto_trade_engine._add_failed_order.call_args[0][0]
        assert call_args["symbol"] == "RELIANCE"
        assert call_args["reason"] == "insufficient_balance"

    def test_place_new_entries_summary_no_retried_field(self, auto_trade_engine):
        """Test that summary no longer includes 'retried' field"""
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        # Mock recommendation
        rec = Recommendation(
            ticker="RELIANCE.NS",
            verdict="buy",
            last_close=2450.0,
            execution_capital=30000.0,
        )

        # Mock portfolio checks
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
        auto_trade_engine.portfolio_size = Mock(return_value=2)
        auto_trade_engine.has_holding = Mock(return_value=False)
        auto_trade_engine.has_active_buy_order = Mock(return_value=False)

        # Mock indicators
        auto_trade_engine.get_daily_indicators = Mock(
            return_value={
                "close": 2450.0,
                "rsi10": 25.0,
                "ema9": 2400.0,
                "ema200": 2300.0,
                "avg_volume": 1000000,
            }
        )

        # Mock balance check
        auto_trade_engine.get_affordable_qty = Mock(return_value=20)
        auto_trade_engine.get_available_cash = Mock(return_value=50000.0)
        auto_trade_engine.check_position_volume_ratio = Mock(return_value=True)
        auto_trade_engine._calculate_execution_capital = Mock(return_value=30000.0)

        # Mock order placement
        auto_trade_engine._attempt_place_order = Mock(return_value=(True, "ORDER123"))

        # Call place_new_entries
        summary = auto_trade_engine.place_new_entries([rec])

        # Verify 'retried' field is not in summary
        assert "retried" not in summary

        # Verify expected fields are present
        assert "attempted" in summary
        assert "placed" in summary
        assert "failed_balance" in summary
