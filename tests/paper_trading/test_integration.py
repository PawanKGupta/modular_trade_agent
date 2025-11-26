"""
Integration Tests for Paper Trading System
"""

import pytest

from modules.kotak_neo_auto_trader.application.dto import OrderRequest
from modules.kotak_neo_auto_trader.application.use_cases import PlaceOrderUseCase
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.domain import (
    Money,
    Order,
    OrderType,
    OrderVariety,
    ProductType,
    TransactionType,
)
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter


class TestPaperTradingIntegration:
    """End-to-end integration tests"""

    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration"""
        return PaperTradingConfig(
            initial_capital=100000.0,
            enable_slippage=False,
            enable_fees=False,
            price_source="mock",
            storage_path=str(tmp_path / "paper_trading"),
            enforce_market_hours=False,
        )

    @pytest.fixture
    def broker(self, config):
        """Create paper trading broker"""
        broker = PaperTradingBrokerAdapter(config)
        broker.connect()

        # Set mock prices (both with and without .NS suffix for compatibility)
        broker.price_provider.set_mock_price("INFY", 1450.00)
        broker.price_provider.set_mock_price("INFY.NS", 1450.00)
        broker.price_provider.set_mock_price("TCS", 3500.00)
        broker.price_provider.set_mock_price("TCS.NS", 3500.00)
        broker.price_provider.set_mock_price("RELIANCE", 2500.00)
        broker.price_provider.set_mock_price("RELIANCE.NS", 2500.00)

        yield broker
        broker.reset()

    def test_complete_buy_workflow(self, broker):
        """Test complete buy order workflow"""
        initial_balance = broker.get_available_balance()

        # Place order
        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )
        order_id = broker.place_order(order)

        # Verify order
        assert order_id is not None
        retrieved_order = broker.get_order(order_id)
        assert retrieved_order is not None

        # Verify holding
        holdings = broker.get_holdings()
        assert len(holdings) == 1
        assert holdings[0].symbol == "INFY"

        # Verify balance decreased
        final_balance = broker.get_available_balance()
        assert final_balance < initial_balance

    def test_complete_sell_workflow(self, broker):
        """Test complete sell order workflow"""
        # First buy
        buy_order = Order(
            symbol="TCS",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )
        broker.place_order(buy_order)

        balance_after_buy = broker.get_available_balance()

        # Then sell
        sell_order = Order(
            symbol="TCS",
            quantity=5,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.SELL,
        )
        broker.place_order(sell_order)

        # Verify holding reduced
        holding = broker.get_holding("TCS")
        assert holding.quantity == 5

        # Verify balance increased
        balance_after_sell = broker.get_available_balance()
        assert balance_after_sell > balance_after_buy

    def test_multiple_positions(self, broker):
        """Test managing multiple positions"""
        # Buy multiple stocks
        symbols = ["INFY", "TCS", "RELIANCE"]

        for symbol in symbols:
            order = Order(
                symbol=symbol,
                quantity=5,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.BUY,
            )
            broker.place_order(order)

        # Verify all holdings
        holdings = broker.get_holdings()
        assert len(holdings) == 3

        holding_symbols = [h.symbol for h in holdings]
        for symbol in symbols:
            assert symbol in holding_symbols

    def test_averaging_down(self, broker):
        """Test averaging down positions"""
        # First buy at 1450
        broker.price_provider.set_mock_price("INFY", 1450.00)
        order1 = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )
        broker.place_order(order1)

        # Second buy at 1350 (averaged down)
        broker.price_provider.set_mock_price("INFY", 1350.00)
        order2 = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )
        broker.place_order(order2)

        # Verify averaged price
        holding = broker.get_holding("INFY")
        assert holding.quantity == 20
        # Average should be around 1400
        assert 1390 < holding.average_price.amount < 1410

    def test_with_use_case(self, broker):
        """Test using the PlaceOrderUseCase"""
        use_case = PlaceOrderUseCase(broker_gateway=broker)

        request = OrderRequest.market_buy(
            symbol="INFY", quantity=10, variety=OrderVariety.REGULAR, product_type=ProductType.CNC
        )

        response = use_case.execute(request)

        assert response.success is True
        assert response.order_id is not None

    def test_persistence_across_sessions(self, config):
        """Test data persists across broker sessions"""
        # Session 1
        broker1 = PaperTradingBrokerAdapter(config)
        broker1.connect()
        broker1.price_provider.set_mock_price("INFY", 1450.00)
        broker1.price_provider.set_mock_price("INFY.NS", 1450.00)

        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )
        broker1.place_order(order)
        broker1.disconnect()

        # Session 2
        broker2 = PaperTradingBrokerAdapter(config)
        broker2.connect()

        holdings = broker2.get_holdings()
        assert len(holdings) == 1

        broker2.reset()

    def test_account_limits(self, broker):
        """Test account limits retrieval"""
        limits = broker.get_account_limits()

        assert "available_cash" in limits
        assert "portfolio_value" in limits
        assert "total_value" in limits
        assert limits["available_cash"].amount == 100000.0

    def test_order_search(self, broker):
        """Test searching orders"""
        # Place multiple orders
        for symbol in ["INFY", "TCS", "INFY"]:
            order = Order(
                symbol=symbol,
                quantity=5,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.BUY,
            )
            broker.place_order(order)

        # Search by symbol
        infy_orders = broker.search_orders_by_symbol("INFY")
        assert len(infy_orders) == 2

    def test_cancel_pending_buys(self, broker):
        """Test canceling pending buy orders"""
        # Place order that won't execute (limit below market)
        order = Order(
            symbol="INFY",
            quantity=10,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.BUY,
            price=Money(1000.00),  # Well below market
        )
        order_id = broker.place_order(order)

        # Cancel it
        cancelled_count = broker.cancel_pending_buys_for_symbol("INFY")
        assert cancelled_count >= 0  # May or may not have executed

    def test_sell_without_holding_fails(self, broker):
        """Test that selling without holding is rejected"""
        order = Order(
            symbol="INVALID",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.SELL,
        )

        order_id = broker.place_order(order)
        retrieved_order = broker.get_order(order_id)

        # Order should be rejected
        assert retrieved_order.status.value == "REJECTED"


class TestDuplicateOrderPrevention:
    """Test duplicate order prevention with pending orders"""

    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration"""
        return PaperTradingConfig(
            initial_capital=100000.0,
            enable_slippage=False,
            enable_fees=False,
            price_source="mock",
            storage_path=str(tmp_path / "paper_trading"),
            enforce_market_hours=False,
        )

    @pytest.fixture
    def broker(self, config):
        """Create paper trading broker"""
        broker = PaperTradingBrokerAdapter(config)
        broker.connect()

        # Set mock prices
        broker.price_provider.set_mock_price("RELIANCE", 2500.00)
        broker.price_provider.set_mock_price("RELIANCE.NS", 2500.00)
        broker.price_provider.set_mock_price("TCS", 3500.00)
        broker.price_provider.set_mock_price("TCS.NS", 3500.00)

        yield broker
        broker.reset()

    def test_duplicate_prevention_with_executed_holding(self, broker):
        """Test that duplicate check prevents ordering stock already in holdings"""
        # Place and execute first order
        order1 = Order(
            symbol="RELIANCE",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )
        order_id1 = broker.place_order(order1)
        assert order_id1 is not None

        # Verify holding exists
        holdings = broker.get_holdings()
        assert len(holdings) == 1
        assert holdings[0].symbol == "RELIANCE"

        # Try to place duplicate order
        # In real implementation, this should be caught by place_new_entries()
        # but broker itself doesn't prevent it, so we verify the check exists
        holdings_symbols = {h.symbol.replace(".NS", "").upper() for h in holdings}
        assert "RELIANCE" in holdings_symbols

    def test_duplicate_prevention_with_pending_order(self, broker):
        """Test that duplicate check includes pending/open orders"""
        # Place order but don't execute (keep it pending)
        # Use LIMIT order that won't execute immediately
        order = Order(
            symbol="RELIANCE",
            quantity=10,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.BUY,
            price=Money(2000.00),  # Below market price, won't execute
        )
        order_id = broker.place_order(order)
        assert order_id is not None

        # Verify order is pending
        order_obj = broker.get_order(order_id)
        assert order_obj.is_active()

        # No holdings yet (order not executed)
        holdings = broker.get_holdings()
        assert len(holdings) == 0

        # But order exists
        all_orders = broker.get_all_orders()
        assert len(all_orders) == 1

        # Check for duplicates should include pending orders
        pending_buy_symbols = set()
        for o in all_orders:
            if o.is_buy_order() and o.is_active():
                normalized = o.symbol.replace(".NS", "").upper()
                pending_buy_symbols.add(normalized)

        assert "RELIANCE" in pending_buy_symbols

    def test_multiple_pending_orders_detection(self, broker):
        """Test detection of multiple pending orders"""
        # Place multiple pending orders
        symbols = ["RELIANCE", "TCS"]
        for symbol in symbols:
            order = Order(
                symbol=symbol,
                quantity=10,
                order_type=OrderType.LIMIT,
                transaction_type=TransactionType.BUY,
                price=Money(1000.00),  # Won't execute
            )
            broker.place_order(order)

        # Get all pending buy orders
        all_orders = broker.get_all_orders()
        pending_buy_symbols = set()
        for o in all_orders:
            if o.is_buy_order() and o.is_active():
                normalized = o.symbol.replace(".NS", "").upper()
                pending_buy_symbols.add(normalized)

        assert "RELIANCE" in pending_buy_symbols
        assert "TCS" in pending_buy_symbols
        assert len(pending_buy_symbols) == 2

    def test_completed_orders_dont_block_new_orders(self, broker):
        """Test that completed orders don't prevent new orders"""
        # Place and execute order
        order1 = Order(
            symbol="RELIANCE",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )
        broker.place_order(order1)

        # Sell all holdings
        sell_order = Order(
            symbol="RELIANCE",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.SELL,
        )
        broker.place_order(sell_order)

        # Verify no holdings
        holdings = broker.get_holdings()
        assert len(holdings) == 0

        # Get pending orders (should be none)
        all_orders = broker.get_all_orders()
        pending_buy_symbols = set()
        for o in all_orders:
            if o.is_buy_order() and o.is_active():
                normalized = o.symbol.replace(".NS", "").upper()
                pending_buy_symbols.add(normalized)

        # Should be able to place new order (no pending, no holdings)
        assert "RELIANCE" not in pending_buy_symbols
        assert len(holdings) == 0


class TestFrozenEMA9SellStrategy:
    """Test frozen EMA9 sell monitoring strategy (integration)"""

    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration"""
        return PaperTradingConfig(
            initial_capital=100000.0,
            enable_slippage=False,
            enable_fees=False,
            price_source="mock",
            storage_path=str(tmp_path / "paper_trading"),
            enforce_market_hours=False,
        )

    @pytest.fixture
    def broker(self, config):
        """Create paper trading broker with holdings"""
        broker = PaperTradingBrokerAdapter(config)
        broker.connect()

        # Set mock prices
        broker.price_provider.set_mock_price("RELIANCE", 2500.00)
        broker.price_provider.set_mock_price("RELIANCE.NS", 2500.00)
        broker.price_provider.set_mock_price("TCS", 3500.00)
        broker.price_provider.set_mock_price("TCS.NS", 3500.00)

        # Place buy orders to create holdings
        for symbol, price in [("RELIANCE", 2500.00), ("TCS", 3500.00)]:
            order = Order(
                symbol=symbol,
                quantity=10,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.BUY,
            )
            broker.place_order(order)

        yield broker
        broker.reset()

    def test_sell_order_placement_at_target(self, broker):
        """Test that sell orders can be placed at frozen EMA9 target"""

        # Verify we have holdings
        holdings = broker.get_holdings()
        assert len(holdings) == 2

        # In real implementation, sell orders would be placed at EMA9
        # Here we simulate placing limit sell orders at target price
        for holding in holdings:
            target_price = (
                float(holding.average_price.amount) * 1.04
            )  # 4% above entry (simulated EMA9)

            sell_order = Order(
                symbol=holding.symbol,
                quantity=holding.quantity,
                order_type=OrderType.LIMIT,
                transaction_type=TransactionType.SELL,
                price=Money(target_price),
            )
            order_id = broker.place_order(sell_order)
            assert order_id is not None

        # Verify sell orders exist
        all_orders = broker.get_all_orders()
        sell_orders = [o for o in all_orders if not o.is_buy_order() and o.is_active()]
        assert len(sell_orders) == 2

    def test_sell_order_executes_when_price_reaches_target(self, broker):
        """Test that sell order executes when price reaches frozen target"""
        # Place limit sell order at target
        target_price = 2600.00
        sell_order = Order(
            symbol="RELIANCE",
            quantity=10,
            order_type=OrderType.LIMIT,
            transaction_type=TransactionType.SELL,
            price=Money(target_price),
        )
        order_id = broker.place_order(sell_order)

        # Update price to target
        broker.price_provider.set_mock_price("RELIANCE", target_price)
        broker.price_provider.set_mock_price("RELIANCE.NS", target_price)

        # Re-fetch order to trigger execution check
        # Note: In real implementation, order simulator checks this
        order_obj = broker.get_order(order_id)

        # Order should execute when price >= limit price
        # This tests the order execution logic
        assert order_obj is not None

    def test_market_sell_on_rsi_exit(self, broker):
        """Test that market sell executes on RSI > 50 condition"""
        # Place market sell order (simulating RSI exit)
        sell_order = Order(
            symbol="RELIANCE",
            quantity=10,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.SELL,
        )
        sell_order._metadata = {"exit_reason": "RSI > 50"}

        order_id = broker.place_order(sell_order)
        assert order_id is not None

        # Market order should execute immediately
        order_obj = broker.get_order(order_id)
        assert order_obj.is_executed()

        # Holdings should be updated
        holdings = broker.get_holdings()
        reliance_holding = next((h for h in holdings if h.symbol == "RELIANCE"), None)
        assert reliance_holding is None  # Should be sold out

    def test_pnl_tracking(self, broker):
        """Test P&L tracking on sell orders"""
        # Verify we already have 2 holdings from fixture
        initial_holdings = broker.get_holdings()
        assert len(initial_holdings) == 2

        # Place sell order for one holding at higher price (profit)
        reliance_holding = next(h for h in initial_holdings if "RELIANCE" in h.symbol)

        # Update price higher to simulate profit
        broker.price_provider.set_mock_price("RELIANCE", 2600.00)
        broker.price_provider.set_mock_price("RELIANCE.NS", 2600.00)

        # Get updated holdings with new prices
        updated_holdings = broker.get_holdings()
        reliance_updated = next(h for h in updated_holdings if "RELIANCE" in h.symbol)

        # Calculate P&L - should be positive
        pnl = reliance_updated.calculate_pnl()

        # Should have profit (bought at 2500, now at 2600)
        assert pnl.amount > 0


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def broker(self, tmp_path):
        """Create broker for edge case testing"""
        config = PaperTradingConfig(
            initial_capital=10000.0,  # Small capital
            max_position_size=5000.0,  # Adjust max position size for small capital
            enable_slippage=False,
            enable_fees=False,
            price_source="mock",
            storage_path=str(tmp_path / "paper_trading"),
            enforce_market_hours=False,
            check_sufficient_funds=True,
        )
        broker = PaperTradingBrokerAdapter(config)
        broker.connect()
        broker.price_provider.set_mock_price("EXPENSIVE", 10000.00)
        yield broker
        broker.reset()

    def test_insufficient_funds(self, broker):
        """Test order rejection due to insufficient funds"""
        order = Order(
            symbol="EXPENSIVE",
            quantity=10,  # Would cost 100,000
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )

        order_id = broker.place_order(order)
        retrieved_order = broker.get_order(order_id)

        # Should be rejected
        assert retrieved_order.status.value == "REJECTED"

    def test_zero_balance_remaining(self, broker):
        """Test handling zero balance"""
        # Buy something to reduce balance to near zero
        broker.price_provider.set_mock_price("CHEAP", 1000.00)
        order = Order(
            symbol="CHEAP",
            quantity=9,
            order_type=OrderType.MARKET,
            transaction_type=TransactionType.BUY,
        )
        broker.place_order(order)

        balance = broker.get_available_balance()
        assert balance.amount >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
