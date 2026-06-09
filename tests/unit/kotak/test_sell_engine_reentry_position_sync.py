"""Tests for closed-buy position sync and sell modify price resolution."""

from unittest.mock import Mock, patch

from src.infrastructure.db.models import OrderStatus, TradeMode

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager


def _build_manager():
    with (
        patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio"),
        patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"),
    ):
        manager = SellOrderManager(
            auth=Mock(), positions_repo=Mock(), orders_repo=Mock(), user_id=2
        )
    manager.orders = Mock()
    return manager


def test_sync_position_qty_from_closed_buys_updates_lagged_row():
    manager = _build_manager()

    buy_initial = Mock()
    buy_initial.side = "buy"
    buy_initial.symbol = "GALLANTT-EQ"
    buy_initial.execution_qty = 15.0
    buy_initial.execution_price = 642.15
    buy_initial.quantity = 15.0
    buy_initial.orig_source = "signal"
    buy_initial.trade_mode = TradeMode.BROKER

    buy_reentry = Mock()
    buy_reentry.side = "buy"
    buy_reentry.symbol = "GALLANTT-EQ"
    buy_reentry.execution_qty = 16.0
    buy_reentry.execution_price = 626.45
    buy_reentry.quantity = 16.0
    buy_reentry.orig_source = "signal"
    buy_reentry.trade_mode = TradeMode.BROKER

    manager.orders_repo.list.return_value = ([buy_initial, buy_reentry], 2)

    existing = Mock()
    existing.opened_at = None
    existing.entry_rsi = 29.0
    manager.positions_repo.get_by_symbol.return_value = existing
    manager.positions_repo.upsert = Mock()

    assert manager._sync_position_qty_from_closed_buys("GALLANTT-EQ", 15.0) is True

    upsert_kwargs = manager.positions_repo.upsert.call_args.kwargs
    assert upsert_kwargs["quantity"] == 31.0
    expected_avg = (15.0 * 642.15 + 16.0 * 626.45) / 31.0
    assert abs(upsert_kwargs["avg_price"] - expected_avg) < 0.01


def test_reconcile_syncs_position_when_broker_exceeds_db_from_system_buys():
    manager = _build_manager()
    manager.portfolio = Mock()
    manager.portfolio.get_holdings.return_value = {
        "data": [{"tradingSymbol": "GALLANTT-EQ", "quantity": 16}]
    }
    manager.portfolio.get_positions.return_value = {
        "data": [{"trdSym": "GALLANTT-EQ", "qty": "16"}]
    }
    manager.orders.get_orders.return_value = {"data": []}

    position = Mock()
    position.symbol = "GALLANTT-EQ"
    position.quantity = 15.0
    position.closed_at = None
    manager.positions_repo.list.return_value = [position]
    manager._should_skip_broker_holdings_reconciliation = Mock(return_value=False)

    buy_initial = Mock(
        side="buy",
        symbol="GALLANTT-EQ",
        execution_qty=15.0,
        execution_price=642.15,
        quantity=15.0,
        orig_source="signal",
        trade_mode=TradeMode.BROKER,
    )
    buy_reentry = Mock(
        side="buy",
        symbol="GALLANTT-EQ",
        execution_qty=16.0,
        execution_price=626.45,
        quantity=16.0,
        orig_source="signal",
        trade_mode=TradeMode.BROKER,
    )
    manager.orders_repo.list.return_value = ([buy_initial, buy_reentry], 2)
    manager.positions_repo.get_by_symbol.return_value = position
    manager.positions_repo.upsert = Mock()

    stats = manager._reconcile_positions_with_broker_holdings()

    assert stats["updated"] == 1
    manager.positions_repo.upsert.assert_called_once()
