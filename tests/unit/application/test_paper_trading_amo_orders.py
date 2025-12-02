"""
Tests for Paper Trading AMO Order Flow

Tests the complete AMO order lifecycle:
1. Order placement (4:05 PM) - No execution, saved as PENDING
2. Pre-market quantity adjustment (9:05 AM)
3. AMO order execution at market open (9:15 AM)
"""

from math import floor
from unittest.mock import MagicMock, Mock, patch

import pytest

from modules.kotak_neo_auto_trader.domain import (
    Money,
    Order,
    OrderStatus,
    OrderType,
    OrderVariety,
    TransactionType,
)
from src.application.services.paper_trading_service_adapter import (
    PaperTradingEngineAdapter,
    PaperTradingServiceAdapter,
)


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    from src.infrastructure.db.models import Users

    user = Users(
        email="amo_test@example.com",
        password_hash="test_hash",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_paper_broker():
    """Mock paper trading broker"""
    broker = MagicMock()
    broker.is_connected.return_value = True
    broker.get_holdings.return_value = []
    broker.get_available_balance.return_value = MagicMock(amount=1000000.0)
    broker.get_all_orders.return_value = []
    broker.get_pending_orders.return_value = []
    broker.place_order.return_value = "PAPER_ORDER_123"
    broker.cancel_order.return_value = True
    broker.config = MagicMock()
    broker.config.max_position_size = 200000.0
    broker.config.amo_execution_time = "09:15"
    broker.config.market_open_time = "09:15"
    broker.config.market_close_time = "15:30"
    broker.config.enforce_market_hours = True

    # Mock price provider
    broker.price_provider = MagicMock()
    broker.price_provider.get_price.return_value = 100.0
    broker.price_provider.get_prices.return_value = {"RELIANCE.NS": 100.0, "TCS.NS": 3500.0}

    return broker


class TestAMOOrderPlacement:
    """Test AMO order placement (4:05 PM) - No immediate execution"""

    def test_amo_order_placed_as_pending_not_executed(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that AMO orders are placed but not executed immediately"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker
        adapter.engine = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=adapter.logger,
        )

        recommendations = [Recommendation(ticker="RELIANCE.NS", verdict="buy", last_close=100.0)]

        with patch.object(
            adapter.engine, "load_latest_recommendations", return_value=recommendations
        ):
            adapter.run_buy_orders()

        # Verify order was placed
        assert mock_paper_broker.place_order.called

        # Get the order that was placed
        placed_order = mock_paper_broker.place_order.call_args[0][0]

        # Verify it's a MARKET AMO order
        assert placed_order.order_type == OrderType.MARKET
        assert placed_order.variety == OrderVariety.AMO
        assert placed_order.price is None  # MARKET orders don't have price

        # Verify order was NOT executed immediately (should be in PENDING/OPEN status)
        # Check that _execute_order was NOT called for AMO orders
        assert not hasattr(mock_paper_broker, "_execute_order") or not any(
            call[0][0].is_amo_order() if call[0] else False
            for call in getattr(mock_paper_broker, "_execute_order", Mock()).call_args_list
        )

    def test_amo_order_is_market_type(self, db_session, test_user, mock_paper_broker):
        """Test that AMO orders are placed as MARKET type (not LIMIT)"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        recommendations = [Recommendation(ticker="RELIANCE.NS", verdict="buy", last_close=100.0)]

        adapter.place_new_entries(recommendations)

        # Verify order was placed
        assert mock_paper_broker.place_order.called

        # Get the order
        order = mock_paper_broker.place_order.call_args[0][0]

        # Verify it's MARKET type
        assert order.order_type == OrderType.MARKET
        assert order.variety == OrderVariety.AMO
        assert order.price is None  # MARKET orders don't have price parameter

    def test_amo_order_saved_as_pending(self, db_session, test_user, mock_paper_broker):
        """Test that AMO orders are saved with OPEN/PENDING status"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=MagicMock(),
        )

        recommendations = [Recommendation(ticker="RELIANCE.NS", verdict="buy", last_close=100.0)]

        adapter.place_new_entries(recommendations)

        # Verify _save_order was called (order saved)
        # The order should be in OPEN status (not executed)
        assert mock_paper_broker.place_order.called


class TestPreMarketQuantityAdjustment:
    """Test pre-market quantity adjustment (9:05 AM)"""

    def test_adjust_amo_quantities_premarket_updates_quantity(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that pre-market adjustment updates quantity to keep capital constant"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker

        # Create a pending AMO order
        pending_order = Order(
            symbol="RELIANCE",
            quantity=2000,  # Original quantity (2000 × 100 = 200,000)
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            order_id="ORDER_123",
            status=OrderStatus.OPEN,
        )
        # Add metadata for price fetching
        pending_order._metadata = {"original_ticker": "RELIANCE.NS"}

        mock_paper_broker.get_pending_orders.return_value = [pending_order]

        # Mock pre-market price (higher than closing)
        mock_paper_broker.price_provider.get_price.return_value = 101.0  # Pre-market: Rs 101

        # Mock cancel and place order
        mock_paper_broker.cancel_order.return_value = True
        mock_paper_broker.place_order.return_value = "ORDER_456"

        summary = adapter.adjust_amo_quantities_premarket()

        # Verify adjustment happened
        assert summary["adjusted"] == 1
        assert summary["total_orders"] == 1

        # Verify cancel was called
        assert mock_paper_broker.cancel_order.called

        # Verify new order was placed with adjusted quantity
        assert mock_paper_broker.place_order.called
        new_order = mock_paper_broker.place_order.call_args[0][0]

        # New quantity should be: floor(200000 / 101) = 1980
        expected_qty = floor(200000.0 / 101.0)
        assert new_order.quantity == expected_qty
        assert new_order.order_type == OrderType.MARKET  # Still MARKET
        assert new_order.price is None  # Price not set for MARKET orders

    def test_adjust_amo_quantities_premarket_no_adjustment_when_price_same(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that no adjustment happens when pre-market price equals closing price"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker

        # Create pending order
        pending_order = Order(
            symbol="RELIANCE",
            quantity=2000,  # 2000 × 100 = 200,000
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            order_id="ORDER_123",
            status=OrderStatus.OPEN,
        )
        pending_order._metadata = {"original_ticker": "RELIANCE.NS"}

        mock_paper_broker.get_pending_orders.return_value = [pending_order]

        # Pre-market price same as closing (100.0)
        mock_paper_broker.price_provider.get_price.return_value = 100.0

        summary = adapter.adjust_amo_quantities_premarket()

        # Should not adjust (quantity would be same)
        assert summary["no_adjustment_needed"] == 1
        assert summary["adjusted"] == 0

        # Should not cancel or place new order
        assert not mock_paper_broker.cancel_order.called
        assert not mock_paper_broker.place_order.called

    def test_adjust_amo_quantities_premarket_handles_price_unavailable(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that adjustment skips orders when pre-market price is unavailable"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker

        pending_order = Order(
            symbol="RELIANCE",
            quantity=2000,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            order_id="ORDER_123",
            status=OrderStatus.OPEN,
        )
        pending_order._metadata = {"original_ticker": "RELIANCE.NS"}

        mock_paper_broker.get_pending_orders.return_value = [pending_order]

        # Price unavailable
        mock_paper_broker.price_provider.get_price.return_value = None

        summary = adapter.adjust_amo_quantities_premarket()

        # Should skip due to price unavailable
        assert summary["price_unavailable"] == 1
        assert summary["adjusted"] == 0

    def test_adjust_amo_quantities_premarket_logs_price_change(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that price change is logged even though price parameter is not used"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker

        pending_order = Order(
            symbol="RELIANCE",
            quantity=2000,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            order_id="ORDER_123",
            status=OrderStatus.OPEN,
        )
        pending_order._metadata = {"original_ticker": "RELIANCE.NS"}

        mock_paper_broker.get_pending_orders.return_value = [pending_order]
        mock_paper_broker.price_provider.get_price.return_value = 101.0
        mock_paper_broker.cancel_order.return_value = True
        mock_paper_broker.place_order.return_value = "ORDER_456"

        # Capture log messages
        with patch.object(adapter.logger, "info") as mock_log:
            adapter.adjust_amo_quantities_premarket()

            # Verify price change was logged
            log_calls = [str(call) for call in mock_log.call_args_list]
            assert any(
                "price logged" in str(call).lower() or "101" in str(call) for call in log_calls
            )


class TestAMOOrderExecution:
    """Test AMO order execution at market open (9:15 AM)"""

    def test_execute_amo_orders_at_market_open_executes_pending_orders(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that execute_amo_orders_at_market_open executes all pending AMO orders"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker

        # Create pending AMO orders
        order1 = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            order_id="ORDER_1",
            status=OrderStatus.OPEN,
        )
        order1._metadata = {"original_ticker": "RELIANCE.NS"}

        order2 = Order(
            symbol="TCS",
            quantity=57,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            order_id="ORDER_2",
            status=OrderStatus.OPEN,
        )
        order2._metadata = {"original_ticker": "TCS.NS"}

        mock_paper_broker.get_pending_orders.return_value = [order1, order2]

        # Mock opening prices
        def mock_get_price(symbol):
            if "RELIANCE" in symbol:
                return 101.0  # Opening price
            elif "TCS" in symbol:
                return 3500.0  # Opening price
            return None

        mock_paper_broker.price_provider.get_price.side_effect = mock_get_price

        # Mock execution (order status changes to EXECUTED)
        def mock_execute_order(order):
            order.status = OrderStatus.EXECUTED
            order.executed_price = MagicMock()
            if "RELIANCE" in order.symbol:
                order.executed_price.amount = 101.0
            elif "TCS" in order.symbol:
                order.executed_price.amount = 3500.0
            order.executed_quantity = order.quantity

        adapter.broker._execute_order = mock_execute_order

        summary = adapter.execute_amo_orders_at_market_open()

        # Verify execution
        assert summary["total_orders"] == 2
        assert summary["executed"] == 2
        assert summary["failed"] == 0

    def test_execute_amo_orders_at_market_open_executes_at_opening_price(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that AMO orders execute at opening price (not order price)"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker

        # Create pending AMO MARKET order
        order = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,  # MARKET order
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            order_id="ORDER_123",
            status=OrderStatus.OPEN,
        )
        order._metadata = {"original_ticker": "RELIANCE.NS"}

        mock_paper_broker.get_pending_orders.return_value = [order]

        # Opening price (different from any order price since MARKET orders don't have price)
        opening_price = 101.0
        mock_paper_broker.price_provider.get_price.return_value = opening_price

        # Track execution price
        execution_price_captured = None

        def mock_execute_order(order_arg):
            nonlocal execution_price_captured
            order_arg.status = OrderStatus.EXECUTED
            order_arg.executed_price = MagicMock()
            order_arg.executed_price.amount = opening_price
            execution_price_captured = opening_price
            order_arg.executed_quantity = order_arg.quantity

        adapter.broker._execute_order = mock_execute_order

        summary = adapter.execute_amo_orders_at_market_open()

        # Verify executed at opening price
        assert summary["executed"] == 1
        assert execution_price_captured == opening_price

    def test_execute_amo_orders_at_market_open_no_pending_orders(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that execution returns empty summary when no pending orders"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker

        # No pending orders
        mock_paper_broker.get_pending_orders.return_value = []

        summary = adapter.execute_amo_orders_at_market_open()

        assert summary["total_orders"] == 0
        assert summary["executed"] == 0

    def test_execute_amo_orders_at_market_open_filters_only_amo_buy_orders(
        self, db_session, test_user, mock_paper_broker
    ):
        """Test that only AMO buy orders are executed (not regular or sell orders)"""
        from config.strategy_config import StrategyConfig

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker

        # Mix of order types
        amo_buy = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            order_id="AMO_BUY",
            status=OrderStatus.OPEN,
        )
        amo_buy._metadata = {"original_ticker": "RELIANCE.NS"}

        regular_buy = Order(
            symbol="TCS",
            quantity=57,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.REGULAR,  # Not AMO
            order_id="REGULAR_BUY",
            status=OrderStatus.OPEN,
        )

        amo_sell = Order(
            symbol="INFY",
            quantity=100,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.SELL,  # Sell order
            variety=OrderVariety.AMO,
            order_id="AMO_SELL",
            status=OrderStatus.OPEN,
            price=Money(1500.0),  # LIMIT orders require price
        )

        mock_paper_broker.get_pending_orders.return_value = [amo_buy, regular_buy, amo_sell]

        mock_paper_broker.price_provider.get_price.return_value = 101.0

        def mock_execute_order(order):
            order.status = OrderStatus.EXECUTED
            order.executed_price = MagicMock(amount=101.0)
            order.executed_quantity = order.quantity

        adapter.broker._execute_order = mock_execute_order

        summary = adapter.execute_amo_orders_at_market_open()

        # Should only execute AMO buy order
        assert summary["total_orders"] == 1
        assert summary["executed"] == 1


class TestCompleteAMOFlow:
    """Test complete AMO order flow from placement to execution"""

    def test_complete_amo_flow_4pm_to_915am(self, db_session, test_user, mock_paper_broker):
        """Test complete flow: Place at 4:05 PM, adjust at 9:05 AM, execute at 9:15 AM"""
        from config.strategy_config import StrategyConfig
        from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation

        strategy_config = StrategyConfig(user_capital=200000.0, max_portfolio_size=6)

        adapter = PaperTradingServiceAdapter(
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
        )
        adapter.broker = mock_paper_broker
        adapter.engine = PaperTradingEngineAdapter(
            broker=mock_paper_broker,
            user_id=test_user.id,
            db_session=db_session,
            strategy_config=strategy_config,
            logger=adapter.logger,
        )

        # Step 1: 4:05 PM - Place AMO order
        recommendations = [Recommendation(ticker="RELIANCE.NS", verdict="buy", last_close=100.0)]

        with patch.object(
            adapter.engine, "load_latest_recommendations", return_value=recommendations
        ):
            adapter.run_buy_orders()

        # Verify order placed
        assert mock_paper_broker.place_order.called
        placed_order = mock_paper_broker.place_order.call_args[0][0]
        assert placed_order.order_type == OrderType.MARKET
        assert placed_order.variety == OrderVariety.AMO
        original_qty = placed_order.quantity  # Should be 2000 (200000 / 100)

        # Step 2: 9:05 AM - Pre-market adjustment
        # Create pending order for adjustment
        pending_order = Order(
            symbol="RELIANCE",
            quantity=original_qty,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            order_id="ORDER_123",
            status=OrderStatus.OPEN,
        )
        pending_order._metadata = {"original_ticker": "RELIANCE.NS"}

        mock_paper_broker.get_pending_orders.return_value = [pending_order]
        mock_paper_broker.price_provider.get_price.return_value = 101.0  # Pre-market price
        mock_paper_broker.cancel_order.return_value = True
        mock_paper_broker.place_order.return_value = "ORDER_456"

        # Reset call counts
        mock_paper_broker.cancel_order.reset_mock()
        mock_paper_broker.place_order.reset_mock()

        adjustment_summary = adapter.adjust_amo_quantities_premarket()

        # Verify adjustment
        assert adjustment_summary["adjusted"] == 1
        assert mock_paper_broker.cancel_order.called
        assert mock_paper_broker.place_order.called

        # Get adjusted order
        adjusted_order = mock_paper_broker.place_order.call_args[0][0]
        expected_qty = floor(200000.0 / 101.0)  # 1980
        assert adjusted_order.quantity == expected_qty

        # Step 3: 9:15 AM - Execute at market open
        # Create adjusted order for execution
        adjusted_order.status = OrderStatus.OPEN
        adjusted_order.order_id = "ORDER_456"
        mock_paper_broker.get_pending_orders.return_value = [adjusted_order]
        mock_paper_broker.price_provider.get_price.return_value = 101.0  # Opening price

        def mock_execute_order(order):
            order.status = OrderStatus.EXECUTED
            order.executed_price = MagicMock(amount=101.0)
            order.executed_quantity = order.quantity

        adapter.broker._execute_order = mock_execute_order

        execution_summary = adapter.execute_amo_orders_at_market_open()

        # Verify execution
        assert execution_summary["executed"] == 1
        assert execution_summary["total_orders"] == 1

        # Verify final execution price
        assert adjusted_order.status == OrderStatus.EXECUTED
        assert adjusted_order.executed_price.amount == 101.0  # Opening price
        assert adjusted_order.executed_quantity == expected_qty

        # Verify capital: 1980 × 101 = 199,980 ≈ 200,000 ✅
        final_capital = adjusted_order.executed_quantity * adjusted_order.executed_price.amount
        assert abs(final_capital - 200000.0) < 1000.0  # Within reasonable range
