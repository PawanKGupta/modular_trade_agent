"""
Unit tests for OrderSizingService configuration and truncation behavior
"""

import logging

from modules.kotak_neo_auto_trader.application.services.order_sizing import (
    OrderSizingService,
    TradingConfig,
)
from modules.kotak_neo_auto_trader.di_container import KotakNeoContainer
from modules.kotak_neo_auto_trader.domain.value_objects.money import Money


def test_order_sizing_config_loading(monkeypatch):
    """Verify OrderSizingService uses MAX_ORDER_VALUE from configurations"""
    from modules.kotak_neo_auto_trader.infrastructure import config

    monkeypatch.setattr(config, "MAX_ORDER_VALUE", 999999)

    container = KotakNeoContainer(use_mock=True)
    trading_config = container.get_trading_config()

    # Verify values are correctly mapped to TradingConfig in di_container
    assert trading_config.max_order_value == Money.from_int(999999)


def test_order_sizing_truncation_warning(caplog):
    """Verify order truncation and warning log when value exceeds cap"""
    config = TradingConfig(
        capital_per_trade=Money.from_int(600000),
        min_quantity=1,
        max_quantity=100000,
        max_order_value=Money.from_int(500000),
    )
    service = OrderSizingService(config=config)

    # Price = Rs 1,000. Capital = Rs 6,00,000. Normal qty = 600.
    # Capped at Rs 5,00,000 max order value -> qty = 500.
    symbol = "REBOUND"
    price = Money.from_int(1000)
    capital = Money.from_int(600000)

    with caplog.at_level(logging.WARNING):
        quantity = service.calculate_quantity(symbol, price, available_balance=capital)

    # Assert quantity is truncated to 500 (value = 500,000)
    assert quantity == 500

    # Assert warning log is captured
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"
    assert "exceeds max order value limit" in caplog.records[0].message
    assert "Capping and truncating order quantity from 600 to 500" in caplog.records[0].message


def test_order_sizing_no_truncation(caplog):
    """Verify no truncation or warning log when value is below cap"""
    config = TradingConfig(
        capital_per_trade=Money.from_int(400000),
        min_quantity=1,
        max_quantity=100000,
        max_order_value=Money.from_int(500000),
    )
    service = OrderSizingService(config=config)

    symbol = "REBOUND"
    price = Money.from_int(1000)
    capital = Money.from_int(400000)

    with caplog.at_level(logging.WARNING):
        quantity = service.calculate_quantity(symbol, price, available_balance=capital)

    # Assert quantity is 400 (value = 400,000)
    assert quantity == 400

    # Assert no warning log is captured
    assert len(caplog.records) == 0


def test_order_sizing_exactly_equal_cap(caplog):
    """Verify order value exactly equal to cap is not truncated (no warning)"""
    config = TradingConfig(
        capital_per_trade=Money.from_int(500000),
        min_quantity=1,
        max_quantity=100000,
        max_order_value=Money.from_int(500000),
    )
    service = OrderSizingService(config=config)

    symbol = "REBOUND"
    price = Money.from_int(1000)
    capital = Money.from_int(500000)

    with caplog.at_level(logging.WARNING):
        quantity = service.calculate_quantity(symbol, price, available_balance=capital)

    assert quantity == 500
    assert len(caplog.records) == 0


def test_order_sizing_price_exceeds_cap(caplog):
    """Verify price exceeding cap returns 0 quantity"""
    config = TradingConfig(
        capital_per_trade=Money.from_int(600000),
        min_quantity=1,
        max_quantity=100000,
        max_order_value=Money.from_int(500000),
    )
    service = OrderSizingService(config=config)

    symbol = "REBOUND"
    # Price is Rs 6,00,000 which exceeds max order value limit of Rs 5,00,000
    price = Money.from_int(600000)
    capital = Money.from_int(600000)

    with caplog.at_level(logging.WARNING):
        quantity = service.calculate_quantity(symbol, price, available_balance=capital)

    # Since price exceeds cap, affordable quantity at cap is 500,000 / 600,000 = 0
    assert quantity == 0


def test_order_sizing_capped_qty_below_min_qty(caplog):
    """Verify capped quantity falling below min_quantity returns 0"""
    config = TradingConfig(
        capital_per_trade=Money.from_int(600000),
        min_quantity=10,
        max_quantity=100000,
        max_order_value=Money.from_int(500000),
    )
    service = OrderSizingService(config=config)

    symbol = "REBOUND"
    # Price = Rs 60,000. Capital = Rs 6,00,000. Original qty = 10 (meets min_quantity=10).
    # Value = 10 * 60,000 = 600,000 (> 500,000 cap).
    # Capped qty = 500,000 / 60,000 = 8.
    # 8 < min_quantity=10, so it should return 0.
    price = Money.from_int(60000)
    capital = Money.from_int(600000)

    with caplog.at_level(logging.WARNING):
        quantity = service.calculate_quantity(symbol, price, available_balance=capital)

    assert quantity == 0


def test_order_sizing_service_uses_strategy_config():
    """Verify OrderSizingService loads max_order_value from strategy_config if provided"""
    from config.strategy_config import StrategyConfig

    strategy_config = StrategyConfig(max_order_value=750000.0)

    container = KotakNeoContainer(use_mock=True, strategy_config=strategy_config)
    trading_config = container.get_trading_config()

    assert trading_config.max_order_value == Money.from_int(750000)
