#!/usr/bin/env python3
"""
Tests for AutoTradeEngine immediate order verification (Phase 5)

Tests that orders are immediately verified after placement to detect
immediate rejections from the broker.
"""

import time
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


class TestImmediateOrderVerification:
    """Test immediate order verification after placement"""

    def test_verify_order_placement_pending(self, auto_trade_engine):
        """Test verification when order is pending (expected for AMO)"""
        # Mock broker orders response - order is pending
        broker_order = {
            "neoOrdNo": "ORDER123",
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "open",
            "transactionType": "BUY",
        }

        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        is_valid, reason = auto_trade_engine._verify_order_placement(
            order_id="ORDER123", symbol="RELIANCE", wait_seconds=0  # Skip wait for test
        )

        assert is_valid is True
        assert reason is None
        auto_trade_engine.orders.get_orders.assert_called_once()

    def test_verify_order_placement_rejected(self, auto_trade_engine):
        """Test verification when order is immediately rejected"""
        # Mock broker orders response - order is rejected
        broker_order = {
            "neoOrdNo": "ORDER123",
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "rejected",
            "transactionType": "BUY",
            "rejRsn": "Insufficient balance",
        }

        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock database order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = "ORDER123"
        auto_trade_engine.orders_repo.list.return_value = [mock_db_order]
        auto_trade_engine.orders_repo.mark_rejected = Mock()

        # Mock telegram
        with patch("modules.kotak_neo_auto_trader.auto_trade_engine.send_telegram") as mock_telegram:
            is_valid, reason = auto_trade_engine._verify_order_placement(
                order_id="ORDER123", symbol="RELIANCE", wait_seconds=0  # Skip wait for test
            )

            assert is_valid is False
            assert reason == "Insufficient balance"
            auto_trade_engine.orders_repo.mark_rejected.assert_called_once_with(
                order_id=1, rejection_reason="Insufficient balance"
            )
            mock_telegram.assert_called_once()
            assert "REJECTED" in mock_telegram.call_args[0][0].upper()

    def test_verify_order_placement_executed(self, auto_trade_engine):
        """Test verification when order is immediately executed (rare for AMO)"""
        # Mock broker orders response - order is executed
        broker_order = {
            "neoOrdNo": "ORDER123",
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "complete",
            "transactionType": "BUY",
            "avgPrc": 2450.50,
            "qty": 10,
        }

        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        is_valid, reason = auto_trade_engine._verify_order_placement(
            order_id="ORDER123", symbol="RELIANCE", wait_seconds=0  # Skip wait for test
        )

        assert is_valid is True
        assert reason is None

    def test_verify_order_placement_not_found(self, auto_trade_engine):
        """Test verification when order is not found in broker list (normal for AMO)"""
        # Mock broker orders response - order not found
        auto_trade_engine.orders.get_orders.return_value = {"data": []}

        is_valid, reason = auto_trade_engine._verify_order_placement(
            order_id="ORDER123", symbol="RELIANCE", wait_seconds=0  # Skip wait for test
        )

        # Should assume valid if not found (normal for AMO orders)
        assert is_valid is True
        assert reason is None

    def test_verify_order_placement_no_order_id(self, auto_trade_engine):
        """Test verification when order_id is None"""
        is_valid, reason = auto_trade_engine._verify_order_placement(
            order_id=None, symbol="RELIANCE", wait_seconds=0
        )

        assert is_valid is True  # Assume valid if no order_id
        assert reason is None
        # Should not call broker API
        auto_trade_engine.orders.get_orders.assert_not_called()

    def test_verify_order_placement_broker_api_error(self, auto_trade_engine):
        """Test verification when broker API fails"""
        auto_trade_engine.orders.get_orders.return_value = None

        is_valid, reason = auto_trade_engine._verify_order_placement(
            order_id="ORDER123", symbol="RELIANCE", wait_seconds=0  # Skip wait for test
        )

        # Should assume valid on API error (don't block on verification failures)
        assert is_valid is True
        assert reason is None

    def test_verify_order_placement_exception_handling(self, auto_trade_engine):
        """Test verification handles exceptions gracefully"""
        auto_trade_engine.orders.get_orders.side_effect = Exception("Broker API error")

        is_valid, reason = auto_trade_engine._verify_order_placement(
            order_id="ORDER123", symbol="RELIANCE", wait_seconds=0  # Skip wait for test
        )

        # Should assume valid on exception (don't block on verification failures)
        assert is_valid is True
        assert reason is None

    def test_verify_order_placement_wait_time_clamping(self, auto_trade_engine):
        """Test that wait time is clamped between 10-30 seconds"""
        auto_trade_engine.orders.get_orders.return_value = {"data": []}

        with patch("time.sleep") as mock_sleep:
            # Test minimum clamping (should be 10 seconds)
            auto_trade_engine._verify_order_placement(
                order_id="ORDER123", symbol="RELIANCE", wait_seconds=5
            )
            mock_sleep.assert_called_once_with(10)

            mock_sleep.reset_mock()

            # Test maximum clamping (should be 30 seconds)
            auto_trade_engine._verify_order_placement(
                order_id="ORDER123", symbol="RELIANCE", wait_seconds=60
            )
            mock_sleep.assert_called_once_with(30)

            mock_sleep.reset_mock()

            # Test normal value (should use as-is)
            auto_trade_engine._verify_order_placement(
                order_id="ORDER123", symbol="RELIANCE", wait_seconds=15
            )
            mock_sleep.assert_called_once_with(15)

    def test_verify_order_placement_database_update_failure(self, auto_trade_engine):
        """Test that database update failure doesn't break verification"""
        # Mock broker orders response - order is rejected
        broker_order = {
            "neoOrdNo": "ORDER123",
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "rejected",
            "transactionType": "BUY",
            "rejRsn": "Invalid symbol",
        }

        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock database order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = "ORDER123"
        auto_trade_engine.orders_repo.list.return_value = [mock_db_order]
        auto_trade_engine.orders_repo.mark_rejected.side_effect = Exception("DB error")

        # Mock telegram
        with patch("modules.kotak_neo_auto_trader.auto_trade_engine.send_telegram"):
            is_valid, reason = auto_trade_engine._verify_order_placement(
                order_id="ORDER123", symbol="RELIANCE", wait_seconds=0  # Skip wait for test
            )

            # Should still return rejection even if DB update fails
            assert is_valid is False
            assert reason == "Invalid symbol"

    def test_verify_order_placement_telegram_failure(self, auto_trade_engine):
        """Test that telegram notification failure doesn't break verification"""
        # Mock broker orders response - order is rejected
        broker_order = {
            "neoOrdNo": "ORDER123",
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "rejected",
            "transactionType": "BUY",
            "rejRsn": "Insufficient balance",
        }

        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock database order
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.broker_order_id = "ORDER123"
        auto_trade_engine.orders_repo.list.return_value = [mock_db_order]
        auto_trade_engine.orders_repo.mark_rejected = Mock()

        # Mock telegram to fail
        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.send_telegram",
            side_effect=Exception("Telegram error"),
        ):
            is_valid, reason = auto_trade_engine._verify_order_placement(
                order_id="ORDER123", symbol="RELIANCE", wait_seconds=0  # Skip wait for test
            )

            # Should still return rejection even if telegram fails
            assert is_valid is False
            assert reason == "Insufficient balance"
            auto_trade_engine.orders_repo.mark_rejected.assert_called_once()

    def test_verify_order_placement_order_not_in_database(self, auto_trade_engine):
        """Test verification when order is not found in database"""
        # Mock broker orders response - order is rejected
        broker_order = {
            "neoOrdNo": "ORDER123",
            "trdSym": "RELIANCE-EQ",
            "orderStatus": "rejected",
            "transactionType": "BUY",
            "rejRsn": "Insufficient balance",
        }

        auto_trade_engine.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock database - order not found
        auto_trade_engine.orders_repo.list.return_value = []
        auto_trade_engine.orders_repo.mark_rejected = Mock()

        # Mock telegram
        with patch("modules.kotak_neo_auto_trader.auto_trade_engine.send_telegram"):
            is_valid, reason = auto_trade_engine._verify_order_placement(
                order_id="ORDER123", symbol="RELIANCE", wait_seconds=0  # Skip wait for test
            )

            # Should still return rejection even if order not in DB
            assert is_valid is False
            assert reason == "Insufficient balance"
            # Should not try to update database (order not found)
            auto_trade_engine.orders_repo.mark_rejected.assert_not_called()

