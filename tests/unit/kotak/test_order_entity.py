import pytest
from datetime import datetime
from modules.kotak_neo_auto_trader.domain.entities.order import Order
from modules.kotak_neo_auto_trader.domain.value_objects.money import Money
from modules.kotak_neo_auto_trader.domain.value_objects.order_enums import (
    OrderType, TransactionType, OrderStatus, ProductType, OrderVariety, Exchange
)


def test_order_validation_and_lifecycle():
    # LIMIT requires price
    with pytest.raises(ValueError):
        Order(
            symbol='RELIANCE.NS', quantity=10, order_type=OrderType.LIMIT,
            transaction_type=TransactionType.BUY
        )

    order = Order(
        symbol='RELIANCE.NS', quantity=10, order_type=OrderType.MARKET,
        transaction_type=TransactionType.BUY, product_type=ProductType.CNC,
        variety=OrderVariety.REGULAR, exchange=Exchange.NSE
    )
    assert order.is_buy_order()
    assert order.is_market_order()
    assert order.is_active()

    # Place and execute
    order.place('OID123')
    assert order.status == OrderStatus.OPEN
    order.execute(Money.from_float(2500.0), 10)
    assert order.is_executed()
    assert order.status == OrderStatus.COMPLETE
    assert order.get_fill_percentage() == 100.0

    # Executed value
    assert order.calculate_executed_value().to_float() == 2500.0 * 10


def test_order_execute_validation():
    order = Order(
        symbol='TCS.NS', quantity=10, order_type=OrderType.MARKET,
        transaction_type=TransactionType.SELL
    )
    order.place('OID999')
    with pytest.raises(ValueError):
        order.execute(Money.from_float(100.0), 0)
    with pytest.raises(ValueError):
        order.execute(Money.from_float(100.0), 11)


def _buy_order(**kwargs) -> Order:
    defaults = {
        "symbol": "RELIANCE.NS",
        "quantity": 10,
        "order_type": OrderType.LIMIT,
        "transaction_type": TransactionType.BUY,
        "price": Money.from_float(2500.0),
        "validity": "DAY",
        "status": OrderStatus.OPEN,
    }
    defaults.update(kwargs)
    return Order(**defaults)


def test_is_pending_open_buy_for_premarket_adjustment_active_day_buy():
    assert _buy_order().is_pending_open_buy_for_premarket_adjustment() is True


def test_is_pending_open_buy_for_premarket_adjustment_rejects_ioc():
    assert _buy_order(validity="IOC").is_pending_open_buy_for_premarket_adjustment() is False


def test_is_pending_open_buy_for_premarket_adjustment_rejects_sell():
    assert (
        _buy_order(transaction_type=TransactionType.SELL, order_type=OrderType.MARKET, price=None)
        .is_pending_open_buy_for_premarket_adjustment()
        is False
    )


@pytest.mark.parametrize(
    "status",
    [OrderStatus.CANCELLED, OrderStatus.COMPLETE, OrderStatus.REJECTED],
)
def test_is_pending_open_buy_for_premarket_adjustment_rejects_inactive(status):
    assert _buy_order(status=status).is_pending_open_buy_for_premarket_adjustment() is False
