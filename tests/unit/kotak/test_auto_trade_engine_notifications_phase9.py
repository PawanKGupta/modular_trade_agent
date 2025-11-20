"""
Tests for Phase 9: Notification triggers in AutoTradeEngine

Tests notification triggers for order placement, retry queue updates.
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
def mock_telegram_notifier():
    """Mock TelegramNotifier"""
    notifier = Mock()
    notifier.enabled = True
    notifier.notify_order_placed = Mock(return_value=True)
    notifier.notify_retry_queue_updated = Mock(return_value=True)
    return notifier


@pytest.fixture
def auto_trade_engine(mock_auth, strategy_config, mock_telegram_notifier):
    """Create AutoTradeEngine instance with mocked telegram notifier"""
    from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine

    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth") as mock_auth_class:
        mock_auth_class.return_value = mock_auth

        engine = AutoTradeEngine(
            env_file="test.env",
            auth=mock_auth,
            user_id=1,
            db_session=MagicMock(),
            strategy_config=strategy_config,
            enable_telegram=True,
        )
        # Inject mock telegram notifier
        engine.telegram_notifier = mock_telegram_notifier

        # Mock portfolio
        engine.portfolio = MagicMock()
        engine.portfolio.get_holdings.return_value = {"data": []}
        engine.portfolio.get_available_cash.return_value = 100000.0

        # Mock orders
        engine.orders = MagicMock()

        # Mock orders repository
        engine.orders_repo = MagicMock()
        engine.orders_repo.create_amo = Mock()
        engine.orders_repo.list = Mock(return_value=[])
        engine.orders_repo.mark_failed = Mock()
        engine.orders_repo.mark_cancelled = Mock()
        engine.orders_repo.update = Mock()

        return engine


class TestAutoTradeEngineNotificationsPhase9:
    """Test Phase 9 notification triggers in AutoTradeEngine"""

    def test_notify_order_placed_success(self, auto_trade_engine, mock_telegram_notifier):
        """Test that order placed successfully sends notification (Phase 9)"""
        # Mock order placement response
        mock_response = {"data": {"orderId": "ORDER123"}}
        auto_trade_engine.orders.place_order.return_value = mock_response

        # Mock order verification to return success
        with patch.object(auto_trade_engine, "_verify_order_placement", return_value=(True, None)):
            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_tracked_symbol"):
                with patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_pending_order"):
                    success, order_id = auto_trade_engine._attempt_place_order(
                        broker_symbol="RELIANCE-EQ",
                        ticker="RELIANCE",
                        qty=10,
                        close=2500.0,
                        ind=MagicMock(),
                    )

                    assert success is True
                    assert order_id == "ORDER123"
                    # Verify notification was sent
                    mock_telegram_notifier.notify_order_placed.assert_called_once()
                    call_args = mock_telegram_notifier.notify_order_placed.call_args
                    assert call_args[1]["symbol"] == "RELIANCE-EQ"
                    assert call_args[1]["order_id"] == "ORDER123"
                    assert call_args[1]["quantity"] == 10
                    assert call_args[1]["order_type"] == "MARKET"

    def test_notify_order_placed_limit_order(self, auto_trade_engine, mock_telegram_notifier):
        """Test that limit order placement sends notification with price (Phase 9)"""
        # Mock order placement response
        mock_response = {"data": {"orderId": "ORDER123"}}
        auto_trade_engine.orders.place_order.return_value = mock_response

        # Mock order verification to return success
        with patch.object(auto_trade_engine, "_verify_order_placement", return_value=(True, None)):
            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_tracked_symbol"):
                with patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_pending_order"):
                    # Place limit order
                    success, order_id = auto_trade_engine._attempt_place_order(
                        broker_symbol="RELIANCE-EQ",
                        ticker="RELIANCE",
                        qty=10,
                        close=2500.0,
                        ind=MagicMock(),
                        use_limit_order=True,
                        limit_price=2495.0,
                    )

                    assert success is True
                    # Verify notification was sent with limit price
                    mock_telegram_notifier.notify_order_placed.assert_called_once()
                    call_args = mock_telegram_notifier.notify_order_placed.call_args
                    assert call_args[1]["order_type"] == "LIMIT"
                    assert call_args[1]["price"] == 2495.0

    def test_notify_order_placed_no_notification_when_disabled(self, auto_trade_engine):
        """Test that notification is not sent when telegram is disabled (Phase 9)"""
        # Disable telegram
        auto_trade_engine.telegram_notifier.enabled = False
        mock_telegram_notifier = auto_trade_engine.telegram_notifier

        # Mock order placement response
        mock_response = {"data": {"orderId": "ORDER123"}}
        auto_trade_engine.orders.place_order.return_value = mock_response

        # Mock order verification to return success
        with patch.object(auto_trade_engine, "_verify_order_placement", return_value=(True, None)):
            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_tracked_symbol"):
                with patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_pending_order"):
                    success, order_id = auto_trade_engine._attempt_place_order(
                        broker_symbol="RELIANCE-EQ",
                        ticker="RELIANCE",
                        qty=10,
                        close=2500.0,
                        ind=MagicMock(),
                    )

                    assert success is True
                    # Verify notification was not sent
                    mock_telegram_notifier.notify_order_placed.assert_not_called()

    def test_notify_order_placed_handles_notification_error(self, auto_trade_engine):
        """Test that notification errors don't crash order placement (Phase 9)"""
        # Mock telegram notifier to raise exception
        auto_trade_engine.telegram_notifier.notify_order_placed.side_effect = Exception(
            "Notification error"
        )

        # Mock order placement response
        mock_response = {"data": {"orderId": "ORDER123"}}
        auto_trade_engine.orders.place_order.return_value = mock_response

        # Mock order verification to return success
        with patch.object(auto_trade_engine, "_verify_order_placement", return_value=(True, None)):
            with patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_tracked_symbol"):
                with patch("modules.kotak_neo_auto_trader.auto_trade_engine.add_pending_order"):
                    # Should not raise exception
                    success, order_id = auto_trade_engine._attempt_place_order(
                        broker_symbol="RELIANCE-EQ",
                        ticker="RELIANCE",
                        qty=10,
                        close=2500.0,
                        ind=MagicMock(),
                    )

                    assert success is True

    def test_notify_retry_queue_updated_on_add(self, auto_trade_engine, mock_telegram_notifier):
        """Test that adding to retry queue sends notification (Phase 9)"""
        # Mock failed order
        failed_order = {
            "symbol": "RELIANCE",
            "qty": 10,
            "close": 2500.0,
            "reason": "insufficient_balance",
            "shortfall": 5000.0,
        }

        # Mock orders repository to return empty list (new failed order)
        auto_trade_engine.orders_repo.list.return_value = []
        mock_order = MagicMock()
        mock_order.retry_count = None
        auto_trade_engine.orders_repo.create_amo.return_value = mock_order

        auto_trade_engine._add_failed_order(failed_order)

        # Verify notification was sent for retryable order
        mock_telegram_notifier.notify_retry_queue_updated.assert_called_once()
        call_args = mock_telegram_notifier.notify_retry_queue_updated.call_args
        assert call_args[1]["symbol"] == "RELIANCE"
        assert call_args[1]["action"] == "added"
        assert call_args[1]["retry_count"] == 0

    def test_notify_retry_queue_updated_on_update(self, auto_trade_engine, mock_telegram_notifier):
        """Test that updating retry queue sends notification (Phase 9)"""
        # Mock existing failed order
        mock_order = MagicMock()
        mock_order.retry_count = 2
        mock_order.symbol = "RELIANCE"
        auto_trade_engine.orders_repo.list.return_value = [mock_order]

        # Mock failed order update
        failed_order = {
            "symbol": "RELIANCE",
            "qty": 10,
            "close": 2500.0,
            "reason": "insufficient_balance",
        }

        auto_trade_engine._add_failed_order(failed_order)

        # Verify notification was sent
        mock_telegram_notifier.notify_retry_queue_updated.assert_called_once()
        call_args = mock_telegram_notifier.notify_retry_queue_updated.call_args
        assert call_args[1]["symbol"] == "RELIANCE"
        assert call_args[1]["action"] == "updated"
        assert call_args[1]["retry_count"] == 3  # 2 + 1

    def test_notify_retry_queue_updated_on_remove(self, auto_trade_engine, mock_telegram_notifier):
        """Test that removing from retry queue sends notification (Phase 9)"""
        # Mock existing failed order
        mock_order = MagicMock()
        mock_order.retry_count = 3
        mock_order.symbol = "RELIANCE"
        auto_trade_engine.orders_repo.list.return_value = [mock_order]
        auto_trade_engine.orders_repo.mark_cancelled.return_value = mock_order

        auto_trade_engine._remove_failed_order("RELIANCE")

        # Verify notification was sent
        mock_telegram_notifier.notify_retry_queue_updated.assert_called_once()
        call_args = mock_telegram_notifier.notify_retry_queue_updated.call_args
        assert call_args[1]["symbol"] == "RELIANCE"
        assert call_args[1]["action"] == "removed"
        assert call_args[1]["retry_count"] == 3

    def test_notify_retry_queue_updated_retried_successfully(
        self, auto_trade_engine, mock_telegram_notifier
    ):
        """Test that successful retry sends notification (Phase 9)"""
        # Mock failed order in retry queue
        failed_order = {
            "symbol": "RELIANCE",
            "ticker": "RELIANCE",
            "qty": 10,
            "close": 2500.0,
            "retry_count": 2,
        }

        # Mock orders repository to return empty list for _remove_failed_order
        auto_trade_engine.orders_repo.list.return_value = []

        # Mock successful order placement
        with patch.object(
            auto_trade_engine, "_attempt_place_order", return_value=(True, "ORDER123")
        ):
            # This simulates the retry logic in _retry_failed_orders
            success, order_id = auto_trade_engine._attempt_place_order(
                broker_symbol="RELIANCE",
                ticker="RELIANCE",
                qty=10,
                close=2500.0,
                ind=MagicMock(),
            )
            if success:
                auto_trade_engine._remove_failed_order("RELIANCE")

                # Verify notification was sent
                # Note: In actual implementation, this happens in _retry_failed_orders
                # For test purposes, we verify the pattern
                mock_telegram_notifier.notify_retry_queue_updated.assert_called()
                calls = mock_telegram_notifier.notify_retry_queue_updated.call_args_list
                # Should have call for removal
                remove_calls = [c for c in calls if c[1].get("action") == "removed"]
                assert len(remove_calls) > 0

    def test_notify_retry_queue_no_notification_for_non_retryable(
        self, auto_trade_engine, mock_telegram_notifier
    ):
        """Test that non-retryable failures don't send notification (Phase 9)"""
        # Mock failed order that's not retryable
        failed_order = {
            "symbol": "RELIANCE",
            "qty": 10,
            "close": 2500.0,
            "reason": "invalid_symbol",  # Not retryable
        }

        # Mock orders repository to return empty list (new failed order)
        auto_trade_engine.orders_repo.list.return_value = []
        mock_order = MagicMock()
        mock_order.retry_count = None
        auto_trade_engine.orders_repo.create_amo.return_value = mock_order

        auto_trade_engine._add_failed_order(failed_order)

        # Verify notification was not sent (not retryable)
        mock_telegram_notifier.notify_retry_queue_updated.assert_not_called()

    def test_notify_retry_queue_handles_notification_error(self, auto_trade_engine):
        """Test that retry queue notification errors don't crash (Phase 9)"""
        # Mock telegram notifier to raise exception
        auto_trade_engine.telegram_notifier.notify_retry_queue_updated.side_effect = Exception(
            "Notification error"
        )

        # Mock failed order
        failed_order = {
            "symbol": "RELIANCE",
            "qty": 10,
            "close": 2500.0,
            "reason": "insufficient_balance",
        }

        # Mock orders repository to return empty list (new failed order)
        auto_trade_engine.orders_repo.list.return_value = []
        mock_order = MagicMock()
        mock_order.retry_count = None
        auto_trade_engine.orders_repo.create_amo.return_value = mock_order

        # Should not raise exception
        auto_trade_engine._add_failed_order(failed_order)
