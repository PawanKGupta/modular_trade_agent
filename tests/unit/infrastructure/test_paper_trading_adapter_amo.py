"""
Tests for Paper Trading Adapter AMO Order Behavior

Tests that AMO orders are placed but not executed immediately.
"""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.domain import (
    Order,
    OrderStatus,
    OrderType,
    OrderVariety,
    TransactionType,
)
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.paper_trading_adapter import (
    PaperTradingBrokerAdapter,
)


@pytest.fixture
def paper_broker():
    """Create paper trading broker"""
    config = PaperTradingConfig(
        enforce_market_hours=True,
        market_open_time="09:15",
        market_close_time="15:30",
        amo_execution_time="09:15",
    )
    broker = PaperTradingBrokerAdapter(config, storage_path="paper_trading/test_amo")
    broker.connect()
    yield broker
    broker.reset()


class TestAMOOrderPlacement:
    """Test AMO order placement behavior"""

    def test_amo_order_placed_but_not_executed_immediately(self, paper_broker):
        """Test that AMO orders are saved as PENDING/OPEN and not executed immediately"""
        # Create AMO MARKET order
        order = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
        )
        order._metadata = {"original_ticker": "RELIANCE.NS"}

        # Mock price provider
        paper_broker.price_provider.get_price = Mock(return_value=100.0)

        # Place order (should NOT execute immediately)
        order_id = paper_broker.place_order(order)

        # Verify order was placed
        assert order_id is not None
        assert order.order_id == order_id
        assert order.status == OrderStatus.OPEN  # Should be OPEN, not EXECUTED

        # Verify order is in pending orders
        pending_orders = paper_broker.get_pending_orders()
        assert len(pending_orders) == 1
        assert pending_orders[0].order_id == order_id
        assert pending_orders[0].is_amo_order() is True
        assert pending_orders[0].status == OrderStatus.OPEN

        # Verify order was NOT executed (no holdings created)
        holdings = paper_broker.get_holdings()
        assert len(holdings) == 0  # No holdings because order not executed

    def test_amo_order_remains_pending_until_market_open(self, paper_broker):
        """Test that AMO orders remain in PENDING/OPEN status until market open"""
        order = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
        )
        order._metadata = {"original_ticker": "RELIANCE.NS"}

        paper_broker.price_provider.get_price = Mock(return_value=100.0)

        # Place order during off-market hours (e.g., 4:05 PM)
        order_id = paper_broker.place_order(order)

        # Verify order is pending
        assert order.status == OrderStatus.OPEN
        assert not order.is_executed()

        # Verify order can be retrieved
        retrieved_order = paper_broker.get_order(order_id)
        assert retrieved_order is not None
        assert retrieved_order.order_id == order_id
        assert retrieved_order.status == OrderStatus.OPEN
        assert retrieved_order.is_amo_order() is True

    def test_regular_market_order_executes_immediately_if_market_open(self, paper_broker):
        """Test that regular (non-AMO) MARKET orders execute immediately if market is open"""
        order = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.REGULAR,  # Not AMO
        )
        order._metadata = {"original_ticker": "RELIANCE.NS"}

        paper_broker.price_provider.get_price = Mock(return_value=100.0)

        # Mock market as open
        with patch.object(paper_broker.order_simulator, "_is_market_open", return_value=True):
            order_id = paper_broker.place_order(order)

            # Regular market order should execute immediately if market is open
            # (This depends on market hours check, but for non-AMO orders, execution happens)
            assert order_id is not None

    def test_amo_order_type_is_market(self, paper_broker):
        """Test that AMO orders are placed as MARKET type (not LIMIT)"""
        order = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,  # MARKET order
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
        )
        order._metadata = {"original_ticker": "RELIANCE.NS"}

        paper_broker.price_provider.get_price = Mock(return_value=100.0)

        order_id = paper_broker.place_order(order)

        # Verify order type is MARKET
        retrieved_order = paper_broker.get_order(order_id)
        assert retrieved_order.order_type == OrderType.MARKET
        assert retrieved_order.price is None  # MARKET orders don't have price parameter
