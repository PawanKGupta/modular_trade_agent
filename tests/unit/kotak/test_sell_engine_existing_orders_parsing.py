from datetime import UTC, datetime
from unittest.mock import Mock, patch

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager


def _build_manager():
    with (
        patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio"),
        patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"),
    ):
        manager = SellOrderManager(auth=Mock(), positions_repo=Mock(), orders_repo=Mock(), user_id=1)
    manager.orders = Mock()
    return manager


def test_get_existing_sell_orders_exposes_full_and_base_keys():
    manager = _build_manager()
    manager.orders.get_pending_orders.return_value = [
        {
            "tradingSymbol": "SBIN-EQ",
            "trnsTp": "S",
            "qty": "9",
            "prc": "1099.95",
            "nOrdNo": "ORD-SBIN-1",
        }
    ]

    existing = manager.get_existing_sell_orders()

    assert "SBIN-EQ" in existing
    assert "SBIN" in existing
    assert existing["SBIN-EQ"]["order_id"] == "ORD-SBIN-1"
    assert existing["SBIN-EQ"]["qty"] == 9
    assert existing["SBIN-EQ"]["price"] == 1099.95


def test_get_existing_sell_orders_handles_string_db_price_fallback():
    manager = _build_manager()
    manager.orders.get_pending_orders.return_value = [
        {
            "tradingSymbol": "SBIN-EQ",
            "trnsTp": "S",
            "qty": "9",
            "prc": "0",
            "nOrdNo": "ORD-SBIN-2",
        }
    ]
    db_order = Mock()
    db_order.price = "1099.95"
    db_order.updated_at = datetime.now(UTC)
    manager.orders_repo.get_by_broker_order_id.return_value = db_order
    manager.orders_repo.update = Mock()

    existing = manager.get_existing_sell_orders()

    assert existing["SBIN-EQ"]["price"] == 1099.95
    assert existing["SBIN-EQ"]["qty"] == 9


def test_get_existing_sell_orders_db_price_fallback_with_naive_updated_at():
    """Naive IST updated_at must not break DB price fallback (regression for reentry modify)."""
    manager = _build_manager()
    manager.orders.get_pending_orders.return_value = [
        {
            "tradingSymbol": "GALLANTT-EQ",
            "trnsTp": "S",
            "qty": "15",
            "prc": "0",
            "nOrdNo": "260609000026807",
        }
    ]
    db_order = Mock()
    db_order.price = 651.35
    # Naive timestamp (orders.updated_at convention)
    db_order.updated_at = datetime(2026, 6, 9, 9, 17, 52)
    manager.orders_repo.get_by_broker_order_id.return_value = db_order
    manager.orders_repo.update = Mock()

    existing = manager.get_existing_sell_orders()

    assert existing["GALLANTT-EQ"]["price"] == 651.35


def test_resolve_sell_modify_price_falls_back_to_db_and_ema9():
    manager = _build_manager()
    db_order = Mock()
    db_order.price = 651.35
    manager.orders_repo.get_by_broker_order_id.return_value = db_order

    price = manager.resolve_sell_modify_price(
        symbol="GALLANTT-EQ",
        order_id="260609000026807",
        reported_price=0.0,
    )
    assert price == 651.35

    manager.orders_repo.get_by_broker_order_id.return_value = None
    manager.active_sell_orders = {
        "GALLANTT-EQ": {"target_price": 650.0, "ticker": "GALLANTT.NS", "placed_symbol": "GALLANTT-EQ"}
    }
    price = manager.resolve_sell_modify_price(
        symbol="GALLANTT-EQ",
        order_id="260609000026807",
        reported_price=0.0,
    )
    assert price == 650.0
