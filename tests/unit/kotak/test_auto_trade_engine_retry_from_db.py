#!/usr/bin/env python3
"""
Tests for AutoTradeEngine retry_pending_orders_from_db method

Tests that orders with FAILED status are retried from database
at scheduled time (8:00 AM) instead of during buy order placement.
Note: RETRY_PENDING merged into FAILED - all FAILED orders are retriable until expiry.
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
        engine.orders = MagicMock()
        engine.orders_repo = MagicMock()
        engine.telegram_notifier = MagicMock()
        engine.telegram_notifier.enabled = True

        # Mock portfolio_service and order_validation_service
        engine.portfolio_service.check_portfolio_capacity = Mock(return_value=(True, 2, 6))
        engine.portfolio_service.has_position = Mock(return_value=False)
        engine.portfolio_service.get_current_positions = Mock(return_value=[])
        engine.portfolio_service.get_portfolio_count = Mock(return_value=2)

        engine.order_validation_service.check_portfolio_capacity = Mock(
            side_effect=lambda include_pending=True: engine.portfolio_service.check_portfolio_capacity(
                include_pending=include_pending
            )
        )
        engine.order_validation_service.check_duplicate_order = Mock(
            side_effect=lambda symbol, **kwargs: (
                engine.portfolio_service.has_position(symbol),
                (
                    "Already in holdings: " + symbol
                    if engine.portfolio_service.has_position(symbol)
                    else None
                ),
            )
        )
        engine.order_validation_service.check_balance = Mock(return_value=(True, 200000.0, 100))
        engine.order_validation_service.check_volume_ratio = Mock(return_value=(True, 0.01, None))
        engine.order_validation_service.portfolio_service = engine.portfolio_service

        # Mock indicator_service
        engine.indicator_service.get_daily_indicators_dict = Mock(
            return_value={
                "close": 2450.0,
                "rsi10": 25.0,
                "ema9": 2400.0,
                "ema200": 2300.0,
                "avg_volume": 1000000,
            }
        )

        return engine


class TestRetryPendingOrdersFromDB:
    """Test retry_pending_orders_from_db method"""

    def test_retry_pending_orders_success(self, auto_trade_engine):
        """Test successful retry of pending orders from DB"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED order (retriable)
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.status = DbOrderStatus.FAILED
        mock_order.retry_count = 1
        mock_order.price = 2450.0
        mock_order.quantity = 10

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_order]

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

        # Mock position volume ratio check
        auto_trade_engine.check_position_volume_ratio = Mock(return_value=True)

        # Mock order placement
        auto_trade_engine._attempt_place_order = Mock(return_value=(True, "ORDER123"))

        # Mock execution capital calculation
        auto_trade_engine._calculate_execution_capital = Mock(return_value=30000.0)

        summary = auto_trade_engine.retry_pending_orders_from_db()

        assert summary["retried"] == 1
        assert summary["placed"] == 1
        assert summary["failed"] == 0
        assert summary["skipped"] == 0

        # Verify order was updated
        auto_trade_engine.orders_repo.update.assert_called_once()
        update_call = auto_trade_engine.orders_repo.update.call_args
        assert update_call[0][0] == mock_order  # First positional arg is the order
        assert update_call[1]["broker_order_id"] == "ORDER123"
        assert update_call[1]["status"] == DbOrderStatus.PENDING

        # Verify notification was sent
        auto_trade_engine.telegram_notifier.notify_retry_queue_updated.assert_called_once()

    def test_retry_pending_orders_insufficient_balance(self, auto_trade_engine):
        """Test retry fails due to insufficient balance"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED order (retriable)
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.status = DbOrderStatus.FAILED
        mock_order.retry_count = 0
        mock_order.price = 2450.0
        mock_order.quantity = 10

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_order]

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

        # Mock insufficient balance
        auto_trade_engine.get_affordable_qty = Mock(return_value=5)  # Less than required
        auto_trade_engine.get_available_cash = Mock(return_value=10000.0)
        auto_trade_engine.check_position_volume_ratio = Mock(return_value=True)
        auto_trade_engine._calculate_execution_capital = Mock(return_value=30000.0)

        summary = auto_trade_engine.retry_pending_orders_from_db()

        assert summary["retried"] == 1
        assert summary["placed"] == 0
        assert summary["failed"] == 1
        assert summary["skipped"] == 0

        # Verify retry count was incremented
        assert mock_order.retry_count == 1
        auto_trade_engine.orders_repo.update.assert_called_once()

    def test_retry_pending_orders_already_in_holdings(self, auto_trade_engine):
        """Test retry skipped when already in holdings"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED order (retriable)
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.status = DbOrderStatus.FAILED

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_order]

        # Mock already in holdings - update portfolio_service mock
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
        auto_trade_engine.portfolio_size = Mock(return_value=2)
        auto_trade_engine.has_holding = Mock(return_value=True)  # Already in holdings
        auto_trade_engine.portfolio_service.has_position = Mock(
            return_value=True
        )  # Already in holdings
        auto_trade_engine.portfolio_service.get_portfolio_count = Mock(return_value=2)

        # Update order_validation_service mock to reflect holdings status
        auto_trade_engine.order_validation_service.check_duplicate_order = Mock(
            return_value=(True, "Already in holdings: RELIANCE")
        )
        auto_trade_engine.order_validation_service.check_portfolio_capacity = Mock(
            return_value=(True, 2, 6)
        )

        # Mock mark_cancelled
        auto_trade_engine.orders_repo.mark_cancelled = Mock()

        summary = auto_trade_engine.retry_pending_orders_from_db()

        assert summary["retried"] == 1
        assert summary["placed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 1

        # Verify order was marked as cancelled
        auto_trade_engine.orders_repo.mark_cancelled.assert_called_once()

    def test_retry_pending_orders_portfolio_limit(self, auto_trade_engine):
        """Test retry skipped when portfolio limit reached"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED orders (retriable)
        mock_order1 = Mock()
        mock_order1.symbol = "RELIANCE"
        mock_order1.status = DbOrderStatus.FAILED

        mock_order2 = Mock()
        mock_order2.symbol = "TCS"
        mock_order2.status = DbOrderStatus.FAILED

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [
            mock_order1,
            mock_order2,
        ]

        # Mock portfolio at limit - update portfolio_service mock
        auto_trade_engine.current_symbols_in_portfolio = Mock(
            return_value=["A", "B", "C", "D", "E", "F"]
        )
        auto_trade_engine.portfolio_size = Mock(return_value=6)  # At max_portfolio_size
        auto_trade_engine.portfolio_service.get_portfolio_count = Mock(return_value=6)
        auto_trade_engine.portfolio_service.check_portfolio_capacity = Mock(
            return_value=(False, 6, 6)
        )  # No capacity

        # Update order_validation_service mock to reflect capacity limit
        auto_trade_engine.order_validation_service.check_portfolio_capacity = Mock(
            return_value=(False, 6, 6)  # No capacity
        )
        auto_trade_engine.order_validation_service.check_duplicate_order = Mock(
            return_value=(False, None)
        )

        summary = auto_trade_engine.retry_pending_orders_from_db()

        # First order increments retried before checking limit, then breaks
        # Skipped calculation: len(orders) - retried + 1 = 2 - 1 + 1 = 2
        # So retried will be 1, and skipped will be 2 (both orders skipped)
        assert summary["retried"] == 1  # First order retried before limit check
        assert summary["skipped"] == 2  # Both orders skipped due to limit

    def test_retry_pending_orders_broker_api_error(self, auto_trade_engine):
        """Test retry fails due to broker API error"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED order (retriable)
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.status = DbOrderStatus.FAILED
        mock_order.retry_count = 0

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_order]

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

        # Mock order placement failure
        auto_trade_engine._attempt_place_order = Mock(return_value=(False, None))

        summary = auto_trade_engine.retry_pending_orders_from_db()

        assert summary["retried"] == 1
        assert summary["placed"] == 0
        assert summary["failed"] == 1
        assert summary["skipped"] == 0

        # Verify order was marked as FAILED (not retryable)
        auto_trade_engine.orders_repo.mark_failed.assert_called_once()
        call_args = auto_trade_engine.orders_repo.mark_failed.call_args
        assert call_args.kwargs["retry_pending"] is False

    def test_retry_pending_orders_no_orders(self, auto_trade_engine):
        """Test retry when no pending orders exist"""
        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = []

        summary = auto_trade_engine.retry_pending_orders_from_db()

        assert summary["retried"] == 0
        assert summary["placed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 0

    def test_retry_pending_orders_no_db(self, auto_trade_engine):
        """Test retry when DB not available"""
        auto_trade_engine.orders_repo = None

        summary = auto_trade_engine.retry_pending_orders_from_db()

        assert summary["retried"] == 0
        assert summary["placed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 0

    def test_retry_pending_orders_missing_indicators(self, auto_trade_engine):
        """Test retry skipped when indicators missing"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED order (retriable)
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.status = DbOrderStatus.FAILED

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_order]

        # Mock portfolio checks
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
        auto_trade_engine.portfolio_size = Mock(return_value=2)
        auto_trade_engine.has_holding = Mock(return_value=False)
        auto_trade_engine.has_active_buy_order = Mock(return_value=False)

        # Mock missing indicators - use indicator_service
        auto_trade_engine.indicator_service.get_daily_indicators_dict = Mock(return_value=None)

        summary = auto_trade_engine.retry_pending_orders_from_db()

        assert summary["retried"] == 1
        assert summary["placed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 1

    def test_retry_pending_orders_invalid_price(self, auto_trade_engine):
        """Test retry skipped when price is invalid"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED order (retriable)
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.status = DbOrderStatus.FAILED

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_order]

        # Mock portfolio checks
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
        auto_trade_engine.portfolio_size = Mock(return_value=2)
        auto_trade_engine.has_holding = Mock(return_value=False)
        auto_trade_engine.has_active_buy_order = Mock(return_value=False)

        # Mock invalid price - use indicator_service
        auto_trade_engine.indicator_service.get_daily_indicators_dict = Mock(
            return_value={
                "close": 0.0,  # Invalid price
                "rsi10": 25.0,
                "ema9": 2400.0,
                "ema200": 2300.0,
                "avg_volume": 1000000,
            }
        )

        summary = auto_trade_engine.retry_pending_orders_from_db()

        assert summary["retried"] == 1
        assert summary["placed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 1

    def test_retry_pending_orders_position_too_large(self, auto_trade_engine):
        """Test retry skipped when position too large for volume"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED order (retriable)
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.status = DbOrderStatus.FAILED

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_order]

        # Mock portfolio checks
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
        auto_trade_engine.portfolio_size = Mock(return_value=2)
        auto_trade_engine.has_holding = Mock(return_value=False)
        auto_trade_engine.has_active_buy_order = Mock(return_value=False)

        # Mock indicators - use indicator_service
        auto_trade_engine.indicator_service.get_daily_indicators_dict = Mock(
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
        auto_trade_engine._calculate_execution_capital = Mock(return_value=30000.0)

        # Mock position too large for volume - use order_validation_service
        auto_trade_engine.order_validation_service.check_volume_ratio = Mock(
            return_value=(False, 0.15, "Position too large")  # Invalid volume ratio
        )

        summary = auto_trade_engine.retry_pending_orders_from_db()

        assert summary["retried"] == 1
        assert summary["placed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 1

        # Verify order was marked as FAILED (position too large)
        auto_trade_engine.orders_repo.mark_failed.assert_called_once()
        call_args = auto_trade_engine.orders_repo.mark_failed.call_args
        assert "not retryable" in call_args.kwargs["failure_reason"]

    def test_retry_pending_orders_holdings_api_fallback_to_db(self, auto_trade_engine):
        """Test retry uses database fallback when holdings API fails"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED order (retriable)
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.status = DbOrderStatus.FAILED

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_order]

        # Mock portfolio checks
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
        auto_trade_engine.portfolio_size = Mock(return_value=2)

        # Mock holdings API failure, but database has ongoing order
        # Update order_validation_service to detect duplicate via database
        auto_trade_engine.portfolio_service.has_position = Mock(side_effect=Exception("API error"))
        auto_trade_engine.order_validation_service.check_duplicate_order = Mock(
            return_value=(True, "Active buy order exists for RELIANCE (database: ONGOING)")
        )

        # Mock database has ongoing order for this symbol
        mock_existing_order = Mock()
        mock_existing_order.symbol = "RELIANCE"
        mock_existing_order.status = DbOrderStatus.ONGOING
        auto_trade_engine.orders_repo.list.return_value = [mock_existing_order]
        auto_trade_engine.orders_repo.mark_cancelled = Mock()

        summary = auto_trade_engine.retry_pending_orders_from_db()

        assert summary["retried"] == 1
        assert summary["placed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 1

        # Verify order was marked as cancelled (database fallback detected duplicate)
        auto_trade_engine.orders_repo.mark_cancelled.assert_called_once()

    def test_retry_pending_orders_cancels_active_buy_order(self, auto_trade_engine):
        """Test retry cancels and replaces active buy order (consistent with place_new_entries)"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED order (retriable)
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.status = DbOrderStatus.FAILED
        mock_order.retry_count = 0

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_order]

        # Mock portfolio checks
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
        auto_trade_engine.portfolio_size = Mock(return_value=2)
        auto_trade_engine.has_holding = Mock(return_value=False)

        # Mock active buy order exists
        auto_trade_engine.has_active_buy_order = Mock(return_value=True)
        auto_trade_engine.orders = MagicMock()
        auto_trade_engine.orders.cancel_pending_buys_for_symbol = Mock(return_value=1)
        auto_trade_engine._symbol_variants = Mock(return_value=["RELIANCE", "RELIANCE-EQ"])

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

        summary = auto_trade_engine.retry_pending_orders_from_db()

        # Verify cancel was called
        auto_trade_engine.orders.cancel_pending_buys_for_symbol.assert_called_once()

        # Verify order was placed after cancel
        assert summary["retried"] == 1
        assert summary["placed"] == 1
        assert summary["failed"] == 0
        assert summary["skipped"] == 0

    def test_retry_pending_orders_active_order_db_fallback(self, auto_trade_engine):
        """Test retry uses database fallback when active order API check fails"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED order (retriable)
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.status = DbOrderStatus.FAILED
        mock_order.retry_count = 0

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_order]

        # Mock portfolio checks
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
        auto_trade_engine.portfolio_size = Mock(return_value=2)
        auto_trade_engine.has_holding = Mock(return_value=False)

        # Mock active order API check fails
        auto_trade_engine.has_active_buy_order = Mock(side_effect=Exception("API error"))

        # Mock database has pending buy order for this symbol
        mock_existing_order = Mock()
        mock_existing_order.id = 2  # Different ID
        mock_existing_order.symbol = "RELIANCE"
        mock_existing_order.side = "buy"
        mock_existing_order.status = DbOrderStatus.PENDING
        auto_trade_engine.orders_repo.list.return_value = [mock_existing_order]

        # Mock cancel
        auto_trade_engine.orders = MagicMock()
        auto_trade_engine.orders.cancel_pending_buys_for_symbol = Mock(return_value=1)
        auto_trade_engine._symbol_variants = Mock(return_value=["RELIANCE", "RELIANCE-EQ"])

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

        summary = auto_trade_engine.retry_pending_orders_from_db()

        # Verify cancel was called (database fallback detected active order)
        auto_trade_engine.orders.cancel_pending_buys_for_symbol.assert_called_once()

        # Verify order was placed after cancel
        assert summary["retried"] == 1
        assert summary["placed"] == 1
        assert summary["failed"] == 0
        assert summary["skipped"] == 0

    def test_retry_pending_orders_active_order_cancel_fails(self, auto_trade_engine):
        """Test retry skips if cancel fails (to prevent duplicates)"""
        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

        # Mock FAILED order (retriable)
        mock_order = Mock()
        mock_order.id = 1
        mock_order.symbol = "RELIANCE"
        mock_order.ticker = "RELIANCE.NS"
        mock_order.status = DbOrderStatus.FAILED
        mock_order.retry_count = 0
        mock_order.price = 2450.0
        mock_order.quantity = 10

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_order]

        # Mock portfolio checks
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])
        auto_trade_engine.portfolio_size = Mock(return_value=2)
        auto_trade_engine.has_holding = Mock(return_value=False)

        # Mock active buy order exists
        auto_trade_engine.has_active_buy_order = Mock(return_value=True)
        auto_trade_engine.orders = MagicMock()
        auto_trade_engine.orders.cancel_pending_buys_for_symbol = Mock(
            side_effect=Exception("Cancel failed")
        )
        auto_trade_engine._symbol_variants = Mock(return_value=["RELIANCE", "RELIANCE-EQ"])

        # Mock indicators (needed before cancel logic)
        auto_trade_engine.get_daily_indicators = Mock(
            return_value={
                "close": 2450.0,
                "rsi10": 25.0,
                "ema9": 2400.0,
                "ema200": 2300.0,
                "avg_volume": 1000000,
            }
        )

        # Mock execution capital calculation
        auto_trade_engine._calculate_execution_capital = Mock(return_value=30000.0)

        # Mock manual order check
        auto_trade_engine._check_for_manual_orders = Mock(return_value={"has_manual_order": False})

        summary = auto_trade_engine.retry_pending_orders_from_db()

        # Verify cancel was attempted
        auto_trade_engine.orders.cancel_pending_buys_for_symbol.assert_called_once()

        # Verify order was skipped (not placed) to prevent duplicates
        assert summary["retried"] == 1
        assert summary["placed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 1
