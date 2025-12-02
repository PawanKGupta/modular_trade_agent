"""
Tests for Order Simulator AMO Order Execution

Tests that AMO orders execute correctly at market open with opening price.
"""

from datetime import time as dt_time
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
from modules.kotak_neo_auto_trader.infrastructure.simulation.order_simulator import OrderSimulator
from modules.kotak_neo_auto_trader.infrastructure.simulation.price_provider import PriceProvider


@pytest.fixture
def order_simulator():
    """Create order simulator with test config"""
    config = PaperTradingConfig(
        enforce_market_hours=True,
        market_open_time="09:15",
        market_close_time="15:30",
        amo_execution_time="09:15",
    )
    price_provider = Mock(spec=PriceProvider)
    return OrderSimulator(config, price_provider)


class TestAMOMarketOrderExecution:
    """Test AMO MARKET order execution at market open"""

    def test_amo_market_order_executes_at_opening_price(self, order_simulator):
        """Test that AMO MARKET orders execute at opening price"""
        # Create AMO MARKET order
        order = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            status=OrderStatus.OPEN,
        )
        order._metadata = {"original_ticker": "RELIANCE.NS"}

        # Mock opening price
        opening_price = 101.0
        order_simulator.price_provider.get_price.return_value = opening_price

        # Mock current time as 9:15 AM (market open)
        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.simulation.order_simulator.datetime"
        ) as mock_datetime:
            mock_now = Mock()
            mock_now.time.return_value = dt_time(9, 15)
            mock_datetime.now.return_value = mock_now

            success, message, execution_price = order_simulator.execute_order(order)

            # Verify execution
            assert success is True
            assert execution_price is not None
            assert execution_price.amount == opening_price
            assert "opening price" in message.lower()

    def test_amo_market_order_waits_until_market_open(self, order_simulator):
        """Test that AMO orders don't execute before market open time"""
        order = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            status=OrderStatus.OPEN,
        )

        # Mock time as 9:14 AM (before market open)
        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.simulation.order_simulator.datetime"
        ) as mock_datetime:
            mock_now = Mock()
            mock_now.time.return_value = dt_time(9, 14)
            mock_datetime.now.return_value = mock_now

            success, message, execution_price = order_simulator.execute_order(order)

            # Should not execute yet
            assert success is False
            assert "execution time not reached" in message.lower()
            assert execution_price is None

    def test_amo_market_order_executes_at_opening_price_regardless_of_order_price(
        self, order_simulator
    ):
        """Test that MARKET orders execute at opening price (order price is None)"""
        order = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,  # MARKET order has no price
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            status=OrderStatus.OPEN,
        )
        order._metadata = {"original_ticker": "RELIANCE.NS"}

        opening_price = 101.0
        order_simulator.price_provider.get_price.return_value = opening_price

        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.simulation.order_simulator.datetime"
        ) as mock_datetime:
            mock_now = Mock()
            mock_now.time.return_value = dt_time(9, 15)
            mock_datetime.now.return_value = mock_now

            success, message, execution_price = order_simulator.execute_order(order)

            # Should execute at opening price
            assert success is True
            assert execution_price.amount == opening_price

    def test_amo_order_execution_uses_original_ticker_for_price(self, order_simulator):
        """Test that AMO order execution uses original ticker from metadata for price fetching"""
        order = Order(
            symbol="RELIANCE",  # Base symbol
            quantity=1980,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
            status=OrderStatus.OPEN,
        )
        order._metadata = {"original_ticker": "RELIANCE.NS"}  # Full ticker with .NS

        opening_price = 101.0
        order_simulator.price_provider.get_price.return_value = opening_price

        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.simulation.order_simulator.datetime"
        ) as mock_datetime:
            mock_now = Mock()
            mock_now.time.return_value = dt_time(9, 15)
            mock_datetime.now.return_value = mock_now

            order_simulator.execute_order(order)

            # Verify price was fetched using original ticker
            order_simulator.price_provider.get_price.assert_called_with("RELIANCE.NS")


class TestAMOExecutionTimeCheck:
    """Test should_execute_amo() method"""

    def test_should_execute_amo_returns_true_at_market_open(self, order_simulator):
        """Test that should_execute_amo returns True at 9:15 AM"""
        order = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
        )

        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.simulation.order_simulator.datetime"
        ) as mock_datetime:
            mock_now = Mock()
            mock_now.time.return_value = dt_time(9, 15)  # Market open
            mock_datetime.now.return_value = mock_now

            result = order_simulator.should_execute_amo(order)

            assert result is True

    def test_should_execute_amo_returns_false_before_market_open(self, order_simulator):
        """Test that should_execute_amo returns False before 9:15 AM"""
        order = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.AMO,
        )

        with patch(
            "modules.kotak_neo_auto_trader.infrastructure.simulation.order_simulator.datetime"
        ) as mock_datetime:
            mock_now = Mock()
            mock_now.time.return_value = dt_time(9, 14)  # Before market open
            mock_datetime.now.return_value = mock_now

            result = order_simulator.should_execute_amo(order)

            assert result is False

    def test_should_execute_amo_returns_false_for_non_amo_orders(self, order_simulator):
        """Test that should_execute_amo returns False for non-AMO orders"""
        order = Order(
            symbol="RELIANCE",
            quantity=1980,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
            variety=OrderVariety.REGULAR,  # Not AMO
        )

        result = order_simulator.should_execute_amo(order)

        assert result is False
