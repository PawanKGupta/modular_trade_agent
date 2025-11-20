#!/usr/bin/env python3
"""
Tests for AutoTradeEngine failure status promotion (Phase 6)

Tests that failed orders use first-class statuses (FAILED, RETRY_PENDING)
and store metadata in dedicated columns instead of JSON metadata.
"""

from datetime import datetime
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
        engine.orders = MagicMock()
        engine.orders_repo = MagicMock()

        return engine


class TestFailureStatusPromotion:
    """Test failure status promotion to first-class statuses"""

    def test_add_failed_order_retry_pending(self, auto_trade_engine):
        """Test adding failed order with retry_pending status (insufficient balance)"""
        failed_order = {
            "symbol": "RELIANCE",
            "ticker": "RELIANCE.NS",
            "close": 2450.0,
            "qty": 10,
            "reason": "insufficient_balance",
            "shortfall": 5000.0,
        }

        # Mock no existing failed orders
        auto_trade_engine.orders_repo.list.return_value = []
        mock_new_order = Mock()
        mock_new_order.id = 1
        auto_trade_engine.orders_repo.create_amo.return_value = mock_new_order
        auto_trade_engine.orders_repo.mark_failed = Mock(return_value=mock_new_order)

        auto_trade_engine._add_failed_order(failed_order)

        # Should create order and mark as RETRY_PENDING
        auto_trade_engine.orders_repo.create_amo.assert_called_once()
        auto_trade_engine.orders_repo.mark_failed.assert_called_once()
        call_args = auto_trade_engine.orders_repo.mark_failed.call_args
        assert call_args.kwargs["retry_pending"] is True
        assert "insufficient_balance" in call_args.kwargs["failure_reason"]
        assert "shortfall" in call_args.kwargs["failure_reason"]

    def test_add_failed_order_failed_status(self, auto_trade_engine):
        """Test adding failed order with failed status (non-retryable)"""
        failed_order = {
            "symbol": "TCS",
            "ticker": "TCS.NS",
            "close": 3200.0,
            "qty": 5,
            "reason": "broker_api_error",
            "non_retryable": True,
        }

        # Mock no existing failed orders
        auto_trade_engine.orders_repo.list.return_value = []
        mock_new_order = Mock()
        mock_new_order.id = 1
        auto_trade_engine.orders_repo.create_amo.return_value = mock_new_order
        auto_trade_engine.orders_repo.mark_failed = Mock(return_value=mock_new_order)

        auto_trade_engine._add_failed_order(failed_order)

        # Should create order and mark as FAILED (not retryable)
        auto_trade_engine.orders_repo.mark_failed.assert_called_once()
        call_args = auto_trade_engine.orders_repo.mark_failed.call_args
        assert call_args.kwargs["retry_pending"] is False
        assert "broker_api_error" in call_args.kwargs["failure_reason"]

    def test_add_failed_order_update_existing(self, auto_trade_engine):
        """Test updating existing failed order"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        failed_order = {
            "symbol": "RELIANCE",
            "ticker": "RELIANCE.NS",
            "close": 2450.0,
            "qty": 10,
            "reason": "insufficient_balance",
            "shortfall": 5000.0,
        }

        # Mock existing failed order
        mock_existing_order = Mock()
        mock_existing_order.id = 1
        mock_existing_order.symbol = "RELIANCE"
        mock_existing_order.status = DbOrderStatus.RETRY_PENDING
        auto_trade_engine.orders_repo.list.return_value = [mock_existing_order]
        auto_trade_engine.orders_repo.mark_failed = Mock(return_value=mock_existing_order)

        auto_trade_engine._add_failed_order(failed_order)

        # Should update existing order, not create new
        auto_trade_engine.orders_repo.create_amo.assert_not_called()
        auto_trade_engine.orders_repo.mark_failed.assert_called_once()
        call_args = auto_trade_engine.orders_repo.mark_failed.call_args
        # mark_failed is called with order as keyword argument
        assert call_args.kwargs["order"] == mock_existing_order
        assert call_args.kwargs["retry_pending"] is True

    def test_remove_failed_order(self, auto_trade_engine):
        """Test removing failed order using new status"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock existing failed order
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.status = DbOrderStatus.RETRY_PENDING
        auto_trade_engine.orders_repo.list.return_value = [mock_order]
        auto_trade_engine.orders_repo.mark_cancelled = Mock(return_value=mock_order)

        auto_trade_engine._remove_failed_order("RELIANCE")

        # Should mark as cancelled
        auto_trade_engine.orders_repo.mark_cancelled.assert_called_once()
        call_args = auto_trade_engine.orders_repo.mark_cancelled.call_args
        # mark_cancelled is called with order as keyword argument
        assert call_args.kwargs["order"] == mock_order
        assert "Removed from retry queue" in call_args.kwargs["cancelled_reason"]

    def test_get_failed_orders(self, auto_trade_engine):
        """Test getting failed orders using new status"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock failed orders
        mock_order1 = Mock()
        mock_order1.symbol = "RELIANCE"
        mock_order1.ticker = "RELIANCE.NS"
        mock_order1.price = 2450.0
        mock_order1.quantity = 10
        mock_order1.failure_reason = "insufficient_balance - shortfall: Rs 5,000"
        mock_order1.first_failed_at = datetime.now()
        mock_order1.retry_count = 2
        mock_order1.status = DbOrderStatus.RETRY_PENDING

        mock_order2 = Mock()
        mock_order2.symbol = "TCS"
        mock_order2.ticker = "TCS.NS"
        mock_order2.price = 3200.0
        mock_order2.quantity = 5
        mock_order2.failure_reason = "broker_api_error"
        mock_order2.first_failed_at = datetime.now()
        mock_order2.retry_count = 0
        mock_order2.status = DbOrderStatus.FAILED

        auto_trade_engine.orders_repo.get_failed_orders.return_value = [mock_order1, mock_order2]

        failed_orders = auto_trade_engine._get_failed_orders()

        assert len(failed_orders) == 2
        assert failed_orders[0]["symbol"] == "RELIANCE"
        assert failed_orders[0]["reason"] == "insufficient_balance - shortfall: Rs 5,000"
        assert failed_orders[0]["status"] == "retry_pending"
        assert failed_orders[0]["retry_count"] == 2
        assert failed_orders[1]["symbol"] == "TCS"
        assert failed_orders[1]["status"] == "failed"

    def test_get_failed_orders_fallback(self, auto_trade_engine):
        """Test get_failed_orders fallback when get_failed_orders() method fails"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock get_failed_orders to raise exception
        auto_trade_engine.orders_repo.get_failed_orders.side_effect = Exception("DB error")

        # Mock orders with failed status
        mock_order = Mock()
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.price = 2450.0
        mock_order.quantity = 10
        mock_order.failure_reason = "insufficient_balance"
        mock_order.first_failed_at = datetime.now()
        mock_order.retry_count = 1
        mock_order.status = DbOrderStatus.RETRY_PENDING

        auto_trade_engine.orders_repo.list.return_value = [mock_order]

        failed_orders = auto_trade_engine._get_failed_orders()

        assert len(failed_orders) == 1
        assert failed_orders[0]["symbol"] == "RELIANCE"
        assert failed_orders[0]["status"] == "retry_pending"

    def test_add_failed_order_symbol_normalization(self, auto_trade_engine):
        """Test that symbol normalization works for finding existing failed orders"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        failed_order = {
            "symbol": "RELIANCE-EQ",
            "ticker": "RELIANCE.NS",
            "close": 2450.0,
            "qty": 10,
            "reason": "insufficient_balance",
        }

        # Mock existing failed order with different suffix
        mock_existing_order = Mock()
        mock_existing_order.id = 1
        mock_existing_order.symbol = "RELIANCE-BE"  # Different suffix
        mock_existing_order.status = DbOrderStatus.RETRY_PENDING
        auto_trade_engine.orders_repo.list.return_value = [mock_existing_order]
        auto_trade_engine.orders_repo.mark_failed = Mock(return_value=mock_existing_order)

        auto_trade_engine._add_failed_order(failed_order)

        # Should find existing order despite different suffix
        auto_trade_engine.orders_repo.create_amo.assert_not_called()
        auto_trade_engine.orders_repo.mark_failed.assert_called_once()

    def test_add_failed_order_empty_symbol(self, auto_trade_engine):
        """Test that empty symbol is handled gracefully"""
        failed_order = {
            "symbol": "",
            "ticker": "RELIANCE.NS",
            "close": 2450.0,
            "qty": 10,
            "reason": "insufficient_balance",
        }

        auto_trade_engine._add_failed_order(failed_order)

        # Should not create order or raise exception
        auto_trade_engine.orders_repo.create_amo.assert_not_called()

    def test_add_failed_order_database_error(self, auto_trade_engine):
        """Test that database errors are handled gracefully"""
        failed_order = {
            "symbol": "RELIANCE",
            "ticker": "RELIANCE.NS",
            "close": 2450.0,
            "qty": 10,
            "reason": "insufficient_balance",
        }

        # Mock no existing orders
        auto_trade_engine.orders_repo.list.return_value = []
        mock_new_order = Mock()
        auto_trade_engine.orders_repo.create_amo.return_value = mock_new_order
        auto_trade_engine.orders_repo.mark_failed.side_effect = Exception("DB error")
        auto_trade_engine.orders_repo.db = MagicMock()

        # Should not raise exception
        auto_trade_engine._add_failed_order(failed_order)

        # Should attempt rollback
        auto_trade_engine.orders_repo.db.rollback.assert_called()

    def test_remove_failed_order_not_found(self, auto_trade_engine):
        """Test removing failed order when none exists"""
        # Mock no failed orders
        auto_trade_engine.orders_repo.list.return_value = []

        # Should not raise exception
        auto_trade_engine._remove_failed_order("RELIANCE")

        auto_trade_engine.orders_repo.mark_cancelled.assert_not_called()

