from modules.kotak_neo_auto_trader.domain.value_objects.order_enums import (
    OrderType, TransactionType, OrderStatus, ProductType, OrderVariety, Exchange
)


def test_enum_from_string_and_helpers():
    assert OrderType.from_string('MKT') == OrderType.MARKET
    assert OrderType.from_string('L') == OrderType.LIMIT

    assert TransactionType.from_string('B') == TransactionType.BUY
    assert TransactionType.from_string('S') == TransactionType.SELL

    assert OrderStatus.from_string('FILLED') == OrderStatus.COMPLETE
    assert OrderStatus.COMPLETE.is_terminal()
    assert OrderStatus.OPEN.is_active()

    assert ProductType.from_string('INTRADAY') == ProductType.MIS
    assert OrderVariety.from_string('AMO') == OrderVariety.AMO
    assert Exchange.from_string('NSE') == Exchange.NSE
