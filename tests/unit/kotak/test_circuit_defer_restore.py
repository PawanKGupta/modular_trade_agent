"""Restore circuit defer queue from DB after restart."""

from unittest.mock import MagicMock, patch

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager


def test_restore_circuit_defer_queue_loads_from_orders_repo():
    auth = MagicMock()
    with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
        mgr = SellOrderManager(auth=auth, orders_repo=MagicMock(), user_id=2)

    defer_order = MagicMock()
    defer_order.symbol = "AXISCADES-EQ"
    defer_order.price = 1860.4
    defer_order.quantity = 5
    defer_order.reason = "deferred"
    defer_order.order_metadata = {
        "upper_circuit": 1859.2,
        "lower_circuit": 1682.2,
        "ema9_target": 1860.4,
        "ticker": "AXISCADES.NS",
        "trade": {
            "symbol": "AXISCADES-EQ",
            "placed_symbol": "AXISCADES-EQ",
            "ticker": "AXISCADES.NS",
            "qty": 5,
        },
    }
    mgr.orders_repo.list_circuit_deferred_sells.return_value = [defer_order]

    restored = mgr._restore_circuit_defer_queue()

    assert restored == 1
    assert "AXISCADES-EQ" in mgr.waiting_for_circuit_expansion
    assert mgr.waiting_for_circuit_expansion["AXISCADES-EQ"]["upper_circuit"] == 1859.2
