"""
Basic tests for paper trading system
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.domain import (
    Order, Money, OrderType, TransactionType, OrderStatus, ProductType, OrderVariety, Exchange
)


@pytest.fixture
def paper_config():
    """Create test configuration"""
    return PaperTradingConfig(
        initial_capital=100000.0,
        enable_slippage=False,  # Disable for predictable tests
        enable_fees=False,
        price_source="mock",
        storage_path="paper_trading/test",
        enforce_market_hours=False
    )


@pytest.fixture
def broker(paper_config):
    """Create paper trading broker"""
    broker = PaperTradingBrokerAdapter(paper_config)
    yield broker
    # Cleanup
    broker.reset()


class TestConnection:
    """Test connection management"""

    def test_connect(self, broker):
        """Test broker connection"""
        assert broker.connect() is True
        assert broker.is_connected() is True

    def test_disconnect(self, broker):
        """Test broker disconnection"""
        broker.connect()
        assert broker.disconnect() is True
        assert broker.is_connected() is False

    def test_reconnect(self, broker):
        """Test reconnection"""
        broker.connect()
        broker.disconnect()
        assert broker.connect() is True


class TestInitialization:
    """Test account initialization"""

    def test_initial_balance(self, broker):
        """Test initial balance"""
        broker.connect()
        balance = broker.get_available_balance()
        assert balance.amount == 100000.0

    def test_empty_holdings(self, broker):
        """Test initial holdings are empty"""
        broker.connect()
        holdings = broker.get_holdings()
        assert len(holdings) == 0


class TestMarketOrders:
    """Test market order execution"""

    def test_place_market_buy(self, broker):
        """Test placing market BUY order"""
        broker.connect()

        # Set mock price
        broker.price_provider.set_mock_price("INFY", 1450.00)

        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY
        )

        order_id = broker.place_order(order)
        assert order_id is not None
        assert order_id.startswith("PT")

    def test_market_buy_creates_holding(self, broker):
        """Test that market BUY creates holding"""
        broker.connect()
        broker.price_provider.set_mock_price("TCS", 3500.00)

        order = Order(
            symbol="TCS",
            quantity=5,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY
        )

        broker.place_order(order)

        holdings = broker.get_holdings()
        assert len(holdings) == 1
        assert holdings[0].symbol == "TCS"
        assert holdings[0].quantity == 5

    def test_market_buy_reduces_balance(self, broker):
        """Test that BUY order reduces balance"""
        broker.connect()
        initial_balance = broker.get_available_balance().amount

        broker.price_provider.set_mock_price("RELIANCE", 2500.00)

        order = Order(
            symbol="RELIANCE",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY
        )

        broker.place_order(order)

        final_balance = broker.get_available_balance().amount
        assert final_balance < initial_balance
        assert initial_balance - final_balance == 25000.0  # 10 * 2500


class TestSellOrders:
    """Test sell order execution"""

    def test_sell_without_holding_fails(self, broker):
        """Test selling without holding fails"""
        broker.connect()

        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.SELL
        )

        # Should place order but execution will fail
        order_id = broker.place_order(order)

        # Check order status
        order_obj = broker.get_order(order_id)
        assert order_obj.status == OrderStatus.REJECTED

    def test_sell_with_holding_succeeds(self, broker):
        """Test selling with holding succeeds"""
        broker.connect()
        broker.price_provider.set_mock_price("INFY", 1450.00)

        # First buy
        buy_order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY
        )
        broker.place_order(buy_order)

        # Then sell
        sell_order = Order(
            symbol="INFY",
            quantity=5,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.SELL
        )
        order_id = broker.place_order(sell_order)

        # Check holding reduced
        holding = broker.get_holding("INFY")
        assert holding.quantity == 5


class TestPortfolio:
    """Test portfolio management"""

    def test_averaging_down(self, broker):
        """Test averaging down functionality"""
        broker.connect()

        # First buy at 1500
        broker.price_provider.set_mock_price("INFY", 1500.00)
        order1 = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY
        )
        broker.place_order(order1)

        # Second buy at 1400 (averaged down)
        broker.price_provider.set_mock_price("INFY", 1400.00)
        order2 = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY
        )
        broker.place_order(order2)

        # Check average price
        holding = broker.get_holding("INFY")
        assert holding.quantity == 20
        assert holding.average_price.amount == 1450.00  # Average of 1500 and 1400


class TestOrderRetrieval:
    """Test order retrieval methods"""

    def test_get_all_orders(self, broker):
        """Test getting all orders"""
        broker.connect()
        broker.price_provider.set_mock_price("INFY", 1450.00)

        # Place multiple orders
        for i in range(3):
            order = Order(
                symbol="INFY",
                quantity=5,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.BUY
            )
            broker.place_order(order)

        orders = broker.get_all_orders()
        assert len(orders) == 3

    def test_search_orders_by_symbol(self, broker):
        """Test searching orders by symbol"""
        broker.connect()
        broker.price_provider.set_mock_price("INFY", 1450.00)
        broker.price_provider.set_mock_price("TCS", 3500.00)

        # Place orders for different symbols
        order1 = Order(symbol="INFY", quantity=10, order_type=OrderType.MARKET, transaction_type=TransactionType.BUY)
        order2 = Order(symbol="TCS", quantity=5, order_type=OrderType.MARKET, transaction_type=TransactionType.BUY)
        order3 = Order(symbol="INFY", quantity=5, order_type=OrderType.MARKET, transaction_type=TransactionType.BUY)

        broker.place_order(order1)
        broker.place_order(order2)
        broker.place_order(order3)

        infy_orders = broker.search_orders_by_symbol("INFY")
        assert len(infy_orders) == 2


class TestAccountLimits:
    """Test account limits and balance"""

    def test_get_account_limits(self, broker):
        """Test getting account limits"""
        broker.connect()
        limits = broker.get_account_limits()

        assert "available_cash" in limits
        assert "portfolio_value" in limits
        assert "total_value" in limits


class TestPersistence:
    """Test state persistence"""

    def test_state_persists_after_disconnect(self, paper_config):
        """Test state persists after disconnect and reconnect"""
        # Session 1
        broker1 = PaperTradingBrokerAdapter(paper_config)
        broker1.connect()
        broker1.price_provider.set_mock_price("INFY", 1450.00)

        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY
        )
        broker1.place_order(order)
        broker1.disconnect()

        # Session 2
        broker2 = PaperTradingBrokerAdapter(paper_config)
        broker2.connect()

        # Check holding persisted
        holdings = broker2.get_holdings()
        assert len(holdings) == 1
        assert holdings[0].symbol == "INFY"

        # Cleanup
        broker2.reset()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

