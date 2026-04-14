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
