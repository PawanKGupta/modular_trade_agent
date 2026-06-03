"""Tests for rehydrating active_sell_orders from broker during sell monitor."""

from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager


@pytest.fixture
def sell_manager():
    auth = Mock(spec=KotakNeoAuth)
    with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
        manager = SellOrderManager(auth=auth, history_path="test_history.json")
    manager.positions_repo = Mock()
    manager.user_id = 1
    manager.orders = Mock()
    manager.active_sell_orders = {}
    manager.lowest_ema9 = {}
    manager.state_manager = None
    return manager


def test_sync_active_sell_orders_from_broker_registers_pending_sell(sell_manager):
    sell_manager.get_open_positions = Mock(
        return_value=[
            {
                "symbol": "RELIANCE-EQ",
                "placed_symbol": "RELIANCE-EQ",
                "ticker": "RELIANCE.NS",
                "qty": 10,
            }
        ]
    )
    sell_manager.get_existing_sell_orders = Mock(
        return_value={
            "RELIANCE-EQ": {"order_id": "BR123", "qty": 10, "price": 2500.0},
        }
    )
    sell_manager._persist_existing_broker_sell_order = Mock()
    sell_manager._get_ema9_with_retry = Mock()

    synced = sell_manager._sync_active_sell_orders_from_broker_for_monitoring()

    assert synced == 1
    assert "RELIANCE-EQ" in sell_manager.active_sell_orders
    assert sell_manager.active_sell_orders["RELIANCE-EQ"]["order_id"] == "BR123"


def test_monitor_and_update_always_calls_rehydrate_sync(sell_manager):
    sell_manager.active_sell_orders = {"TCS-EQ": {"order_id": "X1", "target_price": 4000.0}}
    sell_manager._cleanup_rejected_orders = Mock()
    sell_manager._reconcile_stale_pending_sell_orders = Mock(return_value={})
    sell_manager._check_and_retry_circuit_expansion = Mock(return_value=0)
    sell_manager.check_order_execution = Mock(return_value=[])
    sell_manager.has_completed_sell_order = Mock(return_value=None)
    sell_manager.orders.get_orders = Mock(return_value={"data": []})

    with (
        patch.object(
            sell_manager, "_sync_active_sell_orders_from_broker_for_monitoring", return_value=0
        ) as mock_sync,
        patch.object(sell_manager, "_detect_and_track_pending_manual_sell_orders", return_value={}),
        patch.object(sell_manager, "_check_and_update_single_stock", return_value={"action": "checked"}),
    ):
        sell_manager.monitor_and_update()

    mock_sync.assert_called_once()


def test_sync_skips_symbols_already_tracked(sell_manager):
    sell_manager.active_sell_orders = {
        "RELIANCE-EQ": {"order_id": "BR999", "target_price": 2500.0, "qty": 10},
    }
    sell_manager.get_open_positions = Mock(
        return_value=[
            {"symbol": "RELIANCE-EQ", "qty": 10, "ticker": "RELIANCE.NS"},
            {"symbol": "TCS-EQ", "qty": 5, "ticker": "TCS.NS", "placed_symbol": "TCS-EQ"},
        ]
    )
    sell_manager.get_existing_sell_orders = Mock(
        return_value={
            "RELIANCE-EQ": {"order_id": "BR999", "qty": 10, "price": 2500.0},
            "TCS-EQ": {"order_id": "BR456", "qty": 5, "price": 4000.0},
        }
    )
    sell_manager._persist_existing_broker_sell_order = Mock()
    sell_manager._register_order = Mock(side_effect=lambda **kw: sell_manager.active_sell_orders.__setitem__(
        kw["symbol"],
        {"order_id": kw["order_id"], "target_price": kw["target_price"], "qty": kw["qty"]},
    ))

    synced = sell_manager._sync_active_sell_orders_from_broker_for_monitoring()

    assert synced == 1
    assert "TCS-EQ" in sell_manager.active_sell_orders
    assert sell_manager.active_sell_orders["RELIANCE-EQ"]["order_id"] == "BR999"
