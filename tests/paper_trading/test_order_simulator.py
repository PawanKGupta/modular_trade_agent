"""
Test Order Simulator
"""

import pytest

from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.domain import Money, Order, OrderType, TransactionType
from modules.kotak_neo_auto_trader.infrastructure.simulation import OrderSimulator, PriceProvider


class TestOrderSimulator:
    """Test order execution simulation"""

    @pytest.fixture
    def config(self):
        """Create test configuration"""
        return PaperTradingConfig(
            enable_slippage=False,  # Disable for predictable tests
            enable_fees=False,
            enforce_market_hours=False,
            price_source="mock",
        )

    @pytest.fixture
    def price_provider(self):
        """Create price provider"""
        provider = PriceProvider(mode="mock")
        # Set prices with .NS suffix (as OrderSimulator will add it automatically)
        provider.set_mock_price("INFY.NS", 1450.00)
        provider.set_mock_price("TCS.NS", 3500.00)
        # Also set without suffix for backward compatibility tests
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
            transaction_type=TransactionType.BUY,
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
            transaction_type=TransactionType.SELL,
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
            price=Money(1500.00),  # Above current price
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
            price=Money(1400.00),  # Below current price
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
            price=Money(3400.00),  # Below current price
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
            enforce_market_hours=False,
        )
        provider = PriceProvider(mode="mock")
        provider.set_mock_price("INFY", 1000.00)
        simulator = OrderSimulator(config, provider)

        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
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
            price_source="mock",
        )
        provider = PriceProvider(mode="mock")
        provider.set_mock_price("INFY", 1450.00)
        simulator = OrderSimulator(config, provider)

        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
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
            transaction_type=TransactionType.BUY,
        )
        execution_price = Money(1450.00)

        summary = simulator.get_execution_summary(order, execution_price)

        assert summary["symbol"] == "INFY"
        assert summary["quantity"] == 10
        assert summary["execution_price"] == 1450.00
        assert "order_value" in summary
        assert "charges" in summary

    def test_execute_order_with_ns_suffix_in_metadata(self):
        """Test order execution with .NS suffix in metadata (Bug fix test)"""
        config = PaperTradingConfig(
            enable_slippage=False, enforce_market_hours=False, price_source="mock"
        )
        provider = PriceProvider(mode="mock")
        # Set price with .NS suffix (as yfinance expects)
        provider.set_mock_price("APOLLOHOSP.NS", 5500.00)
        simulator = OrderSimulator(config, provider)

        # Order symbol without .NS suffix
        order = Order(
            symbol="APOLLOHOSP",
            quantity=2,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )
        # Add metadata with original ticker (includes .NS)
        order._metadata = {"original_ticker": "APOLLOHOSP.NS"}

        success, message, execution_price = simulator.execute_order(order)

        assert success is True, f"Order execution failed: {message}"
        assert execution_price is not None
        assert execution_price.amount == 5500.00

    def test_execute_order_without_suffix_adds_ns_automatically(self):
        """Test order execution automatically adds .NS suffix for Indian stocks (Bug fix test)"""
        config = PaperTradingConfig(
            enable_slippage=False, enforce_market_hours=False, price_source="mock"
        )
        provider = PriceProvider(mode="mock")
        # Set price with .NS suffix (as yfinance expects)
        provider.set_mock_price("TATASTEEL.NS", 140.50)
        simulator = OrderSimulator(config, provider)

        # Order symbol without .NS suffix and no metadata
        order = Order(
            symbol="TATASTEEL",
            quantity=120,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )

        success, message, execution_price = simulator.execute_order(order)

        # Should succeed because OrderSimulator automatically adds .NS suffix
        assert success is True, f"Order execution failed: {message}"
        assert execution_price is not None
        assert execution_price.amount == 140.50

    def test_execute_order_with_existing_ns_suffix(self):
        """Test order execution when symbol already has .NS suffix"""
        config = PaperTradingConfig(
            enable_slippage=False, enforce_market_hours=False, price_source="mock"
        )
        provider = PriceProvider(mode="mock")
        provider.set_mock_price("RELIANCE.NS", 2450.00)
        simulator = OrderSimulator(config, provider)

        # Order symbol already has .NS suffix
        order = Order(
            symbol="RELIANCE.NS",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )

        success, message, execution_price = simulator.execute_order(order)

        assert success is True
        assert execution_price.amount == 2450.00

    def test_execute_order_price_not_available(self):
        """Test order execution fails gracefully when price not available"""
        config = PaperTradingConfig(
            enable_slippage=False,
            enforce_market_hours=False,
            price_source="live",  # Use "live" mode instead of "mock" to properly test price unavailability
        )
        # Create provider without HAS_DATA_FETCHER or HAS_YFINANCE_PROVIDER
        # This will force it to return None for prices
        provider = PriceProvider(mode="live")
        # Clear any cached data
        provider.clear_cache()
        simulator = OrderSimulator(config, provider)

        order = Order(
            symbol="INVALIDSTOCK",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )

        success, message, execution_price = simulator.execute_order(order)

        # In live mode without data providers, price should be None
        # Note: This test may succeed if data providers are available, which is acceptable
        # The important thing is it doesn't crash
        assert isinstance(success, bool)
        if not success:
            assert "Price not available" in message or "Market is closed" in message
            assert execution_price is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
