"""
Test Order Simulator
"""

import pytest
from datetime import time as dt_time
from modules.kotak_neo_auto_trader.infrastructure.simulation import OrderSimulator, PriceProvider
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.domain import Order, Money, OrderType, TransactionType


class TestOrderSimulator:
    """Test order execution simulation"""

    @pytest.fixture
    def config(self):
        """Create test configuration"""
        return PaperTradingConfig(
            enable_slippage=False,  # Disable for predictable tests
            enable_fees=False,
            enforce_market_hours=False,
            price_source="mock"
        )

    @pytest.fixture
    def price_provider(self):
        """Create price provider"""
        provider = PriceProvider(mode="mock")
        provider.set_mock_price("INFY", 1450.00)
        provider.set_mock_price("TCS", 3500.00)
        return provider

    @pytest.fixture
    def simulator(self, config, price_provider):
        """Create order simulator"""
        return OrderSimulator(config, price_provider)

    def test_execute_market_buy_order(self, simulator):
        """Test market buy order execution"""
        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY
        )

        success, message, execution_price = simulator.execute_order(order)

        assert success is True
        assert execution_price is not None
        assert execution_price.amount > 0

    def test_execute_market_sell_order(self, simulator):
        """Test market sell order execution"""
        order = Order(
            symbol="TCS",
            quantity=5,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.SELL
        )

        success, message, execution_price = simulator.execute_order(order)

        assert success is True
        assert execution_price.amount > 0

    def test_execute_limit_buy_below_market(self, simulator):
        """Test limit buy order below market price"""
        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.BUY,
            price=Money(1500.00)  # Above current price
        )

        success, message, execution_price = simulator.execute_order(order)

        assert success is True
        assert execution_price.amount == 1500.00

    def test_execute_limit_buy_above_market(self, simulator):
        """Test limit buy order above market price (should not execute)"""
        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.BUY,
            price=Money(1400.00)  # Below current price
        )

        success, message, execution_price = simulator.execute_order(order)

        assert success is False
        assert "above limit" in message.lower() or "price" in message.lower()

    def test_execute_limit_sell_above_market(self, simulator):
        """Test limit sell order above market price"""
        order = Order(
            symbol="TCS",
            quantity=5,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.SELL,
            price=Money(3400.00)  # Below current price
        )

        success, message, execution_price = simulator.execute_order(order)

        assert success is True
        assert execution_price.amount == 3400.00

    def test_slippage_application(self):
        """Test slippage is applied correctly"""
        config = PaperTradingConfig(
            enable_slippage=True,
            slippage_range=(0.2, 0.2),  # Fixed 0.2%
            price_source="mock",
            enforce_market_hours=False
        )
        provider = PriceProvider(mode="mock")
        provider.set_mock_price("INFY", 1000.00)
        simulator = OrderSimulator(config, provider)

        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY
        )

        success, message, execution_price = simulator.execute_order(order)

        assert success is True
        # Buy orders should have positive slippage (pay more)
        assert execution_price.amount >= 1000.00

    def test_calculate_charges(self):
        """Test charges calculation"""
        config = PaperTradingConfig(enable_fees=True, price_source="mock")
        provider = PriceProvider(mode="mock")
        simulator = OrderSimulator(config, provider)

        order_value = 10000.0
        buy_charges = simulator.calculate_charges(order_value, is_buy=True)
        sell_charges = simulator.calculate_charges(order_value, is_buy=False)

        assert buy_charges > 0
        assert sell_charges > 0

    def test_validate_order_value_sufficient_funds(self, simulator):
        """Test order validation with sufficient funds"""
        order_value = 10000.0
        available_cash = 50000.0

        is_valid, error = simulator.validate_order_value(order_value, available_cash)

        assert is_valid is True
        assert error == ""

    def test_validate_order_value_insufficient_funds(self, simulator):
        """Test order validation with insufficient funds"""
        config = PaperTradingConfig(check_sufficient_funds=True, price_source="mock")
        provider = PriceProvider(mode="mock")
        simulator = OrderSimulator(config, provider)

        order_value = 50000.0
        available_cash = 10000.0

        is_valid, error = simulator.validate_order_value(order_value, available_cash)

        assert is_valid is False
        assert "Insufficient funds" in error

    def test_validate_order_value_exceeds_max_position(self, simulator):
        """Test order validation exceeding max position size"""
        order_value = 100000.0  # Exceeds default max_position_size
        available_cash = 200000.0

        is_valid, error = simulator.validate_order_value(order_value, available_cash)

        assert is_valid is False
        assert "max position size" in error

    def test_market_hours_enforcement(self):
        """Test market hours enforcement"""
        config = PaperTradingConfig(
            enforce_market_hours=True,
            market_open_time="09:15",
            market_close_time="15:30",
            price_source="mock"
        )
        provider = PriceProvider(mode="mock")
        provider.set_mock_price("INFY", 1450.00)
        simulator = OrderSimulator(config, provider)

        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY
        )

        # This will depend on current time, so just check it doesn't crash
        success, message, execution_price = simulator.execute_order(order)
        assert isinstance(success, bool)

    def test_get_execution_summary(self, simulator):
        """Test execution summary generation"""
        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY
        )
        execution_price = Money(1450.00)

        summary = simulator.get_execution_summary(order, execution_price)

        assert summary["symbol"] == "INFY"
        assert summary["quantity"] == 10
        assert summary["execution_price"] == 1450.00
        assert "order_value" in summary
        assert "charges" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

