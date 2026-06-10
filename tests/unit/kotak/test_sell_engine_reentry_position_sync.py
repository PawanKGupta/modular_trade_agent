"""Tests for cycle-scoped closed-buy position sync and sell modify price resolution."""

from datetime import datetime
from unittest.mock import Mock, patch

from src.infrastructure.db.models import OrderStatus, TradeMode
from src.infrastructure.db.timezone_utils import ist_now_naive

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


def _closed_buy(
    *,
    symbol: str,
    qty: float,
    price: float,
    execution_time: datetime,
    trade_mode=TradeMode.BROKER,
    orig_source: str = "signal",
):
    order = Mock()
    order.side = "buy"
    order.symbol = symbol
    order.execution_qty = qty
    order.execution_price = price
    order.quantity = qty
    order.orig_source = orig_source
    order.trade_mode = trade_mode
    order.execution_time = execution_time
    order.filled_at = None
    order.closed_at = None
    order.placed_at = execution_time
    return order


def test_sync_position_qty_from_closed_buys_updates_lagged_row_same_cycle():
    """Re-entry lag: both closed buys belong to the current open position cycle."""
    manager = _build_manager()
    cycle_open = datetime(2026, 6, 10, 9, 30, 0)

    buy_initial = _closed_buy(
        symbol="GALLANTT-EQ",
        qty=15.0,
        price=642.15,
        execution_time=datetime(2026, 6, 10, 9, 31, 0),
    )
    buy_reentry = _closed_buy(
        symbol="GALLANTT-EQ",
        qty=16.0,
        price=626.45,
        execution_time=datetime(2026, 6, 10, 10, 5, 0),
    )

    manager.orders_repo.list.return_value = ([buy_initial, buy_reentry], 2)

    existing = Mock()
    existing.opened_at = cycle_open
    existing.closed_at = None
    existing.entry_rsi = 29.0
    manager.positions_repo.get_by_symbol.return_value = existing
    manager.positions_repo.upsert = Mock()

    assert (
        manager._sync_position_qty_from_closed_buys(
            "GALLANTT-EQ", 15.0, broker_qty=31.0
        )
        is True
    )

    upsert_kwargs = manager.positions_repo.upsert.call_args.kwargs
    assert upsert_kwargs["quantity"] == 31.0
    expected_avg = (15.0 * 642.15 + 16.0 * 626.45) / 31.0
    assert abs(upsert_kwargs["avg_price"] - expected_avg) < 0.01


def test_closed_system_buy_totals_excludes_prior_trade_cycle():
    """Closed buys from a prior cycle must not inflate the current position total."""
    manager = _build_manager()
    cycle_open = datetime(2026, 6, 20, 9, 30, 0)

    prior_cycle_buy = _closed_buy(
        symbol="SALSTEEL-EQ",
        qty=10.0,
        price=100.0,
        execution_time=datetime(2026, 6, 1, 9, 31, 0),
    )
    current_cycle_buy = _closed_buy(
        symbol="SALSTEEL-EQ",
        qty=10.0,
        price=110.0,
        execution_time=datetime(2026, 6, 20, 9, 35, 0),
    )
    manager.orders_repo.list.return_value = ([prior_cycle_buy, current_cycle_buy], 2)

    totals = manager._closed_system_buy_totals(
        "SALSTEEL-EQ", opened_at=cycle_open, require_broker_trade_mode=True
    )

    assert totals is not None
    qty, avg = totals
    assert qty == 10.0
    assert abs(avg - 110.0) < 0.01


def test_multi_cycle_manual_buy_does_not_sync_from_historical_buys():
    """QA case: prior cycle buys + manual broker buy must not inflate DB or sell qty."""
    manager = _build_manager()
    cycle_open = datetime(2026, 6, 20, 9, 30, 0)

    prior_cycle_buy = _closed_buy(
        symbol="SALSTEEL-EQ",
        qty=10.0,
        price=100.0,
        execution_time=datetime(2026, 6, 1, 9, 31, 0),
    )
    current_cycle_buy = _closed_buy(
        symbol="SALSTEEL-EQ",
        qty=10.0,
        price=110.0,
        execution_time=datetime(2026, 6, 20, 9, 35, 0),
    )
    manager.orders_repo.list.return_value = ([prior_cycle_buy, current_cycle_buy], 2)

    position = Mock()
    position.symbol = "SALSTEEL-EQ"
    position.quantity = 10.0
    position.closed_at = None
    position.opened_at = cycle_open
    manager.positions_repo.list.return_value = [position]
    manager.positions_repo.get_by_symbol.return_value = position
    manager.positions_repo.upsert = Mock()

    manager.portfolio = Mock()
    manager.portfolio.get_holdings.return_value = {
        "data": [{"tradingSymbol": "SALSTEEL-EQ", "quantity": 15}]
    }
    manager.portfolio.get_positions.return_value = {
        "data": [{"trdSym": "SALSTEEL-EQ", "qty": "15"}]
    }
    manager.orders.get_orders.return_value = {"data": []}
    manager._should_skip_broker_holdings_reconciliation = Mock(return_value=False)

    stats = manager._reconcile_positions_with_broker_holdings()

    assert stats["checked"] == 1
    assert stats["updated"] == 0
    assert stats["ignored"] == 1
    manager.positions_repo.upsert.assert_not_called()


def test_closed_system_buy_totals_excludes_null_trade_mode_on_live_path():
    """Legacy NULL trade_mode rows must not count toward live broker totals."""
    manager = _build_manager()
    cycle_open = datetime(2026, 6, 20, 9, 30, 0)

    legacy_buy = _closed_buy(
        symbol="SALSTEEL-EQ",
        qty=10.0,
        price=100.0,
        execution_time=datetime(2026, 6, 20, 9, 31, 0),
        trade_mode=None,
    )
    broker_buy = _closed_buy(
        symbol="SALSTEEL-EQ",
        qty=10.0,
        price=110.0,
        execution_time=datetime(2026, 6, 20, 9, 35, 0),
        trade_mode=TradeMode.BROKER,
    )
    manager.orders_repo.list.return_value = ([legacy_buy, broker_buy], 2)

    totals = manager._closed_system_buy_totals(
        "SALSTEEL-EQ", opened_at=cycle_open, require_broker_trade_mode=True
    )

    assert totals is not None
    qty, avg = totals
    assert qty == 10.0
    assert abs(avg - 110.0) < 0.01


def test_sync_rejects_when_expected_exceeds_broker_qty():
    """Do not sync above broker holdings (manual buy excess on top of system qty)."""
    manager = _build_manager()
    cycle_open = datetime(2026, 6, 20, 9, 30, 0)

    current_cycle_buy = _closed_buy(
        symbol="SALSTEEL-EQ",
        qty=10.0,
        price=110.0,
        execution_time=datetime(2026, 6, 20, 9, 35, 0),
    )
    manager.orders_repo.list.return_value = ([current_cycle_buy], 1)

    existing = Mock()
    existing.opened_at = cycle_open
    existing.closed_at = None
    manager.positions_repo.get_by_symbol.return_value = existing
    manager.positions_repo.upsert = Mock()

    assert (
        manager._sync_position_qty_from_closed_buys(
            "SALSTEEL-EQ", 10.0, broker_qty=15.0
        )
        is False
    )
    manager.positions_repo.upsert.assert_not_called()


def test_get_open_positions_sells_system_qty_only_when_manual_buy_on_broker():
    """Sell placement must not include manual shares after reconciliation."""
    manager = _build_manager()
    cycle_open = datetime(2026, 6, 20, 9, 30, 0)

    prior_cycle_buy = _closed_buy(
        symbol="SALSTEEL-EQ",
        qty=10.0,
        price=100.0,
        execution_time=datetime(2026, 6, 1, 9, 31, 0),
    )
    current_cycle_buy = _closed_buy(
        symbol="SALSTEEL-EQ",
        qty=10.0,
        price=110.0,
        execution_time=datetime(2026, 6, 20, 9, 35, 0),
    )
    manager.orders_repo.list.return_value = ([prior_cycle_buy, current_cycle_buy], 2)

    position = Mock()
    position.symbol = "SALSTEEL-EQ"
    position.quantity = 10.0
    position.closed_at = None
    position.opened_at = cycle_open
    position.avg_price = 110.0
    manager.positions_repo.list.return_value = [position]

    manager.portfolio = Mock()
    manager.portfolio.get_holdings.return_value = {
        "data": [{"tradingSymbol": "SALSTEEL-EQ", "quantity": 15}]
    }
    manager.portfolio.get_positions.return_value = {
        "data": [{"trdSym": "SALSTEEL-EQ", "qty": "15"}]
    }

    open_positions = manager.get_open_positions()

    assert len(open_positions) == 1
    assert open_positions[0]["qty"] == 10


def test_reconcile_syncs_position_when_broker_exceeds_db_from_system_buys():
    manager = _build_manager()
    cycle_open = datetime(2026, 6, 10, 9, 30, 0)
    manager.portfolio = Mock()
    manager.portfolio.get_holdings.return_value = {
        "data": [{"tradingSymbol": "GALLANTT-EQ", "quantity": 31}]
    }
    manager.portfolio.get_positions.return_value = {
        "data": [{"trdSym": "GALLANTT-EQ", "qty": "31"}]
    }
    manager.orders.get_orders.return_value = {"data": []}

    position = Mock()
    position.symbol = "GALLANTT-EQ"
    position.quantity = 15.0
    position.closed_at = None
    position.opened_at = cycle_open
    manager.positions_repo.list.return_value = [position]
    manager._should_skip_broker_holdings_reconciliation = Mock(return_value=False)

    buy_initial = _closed_buy(
        symbol="GALLANTT-EQ",
        qty=15.0,
        price=642.15,
        execution_time=datetime(2026, 6, 10, 9, 31, 0),
    )
    buy_reentry = _closed_buy(
        symbol="GALLANTT-EQ",
        qty=16.0,
        price=626.45,
        execution_time=datetime(2026, 6, 10, 10, 5, 0),
    )
    manager.orders_repo.list.return_value = ([buy_initial, buy_reentry], 2)
    manager.positions_repo.get_by_symbol.return_value = position
    manager.positions_repo.upsert = Mock()

    stats = manager._reconcile_positions_with_broker_holdings()

    assert stats["updated"] == 1
    manager.positions_repo.upsert.assert_called_once()
    assert manager.positions_repo.upsert.call_args.kwargs["quantity"] == 31.0


def test_reconcile_manual_buy_ignored_with_prior_cycle_closed_buys():
    """Manual buy must stay ignored even when historical closed buys exist."""
    manager = _build_manager()
    cycle_open = ist_now_naive().replace(hour=9, minute=30, second=0, microsecond=0)

    prior_cycle_buy = _closed_buy(
        symbol="RELIANCE-EQ",
        qty=35.0,
        price=2500.0,
        execution_time=datetime(2026, 5, 1, 9, 31, 0),
    )
    current_cycle_buy = _closed_buy(
        symbol="RELIANCE-EQ",
        qty=35.0,
        price=2550.0,
        execution_time=cycle_open.replace(minute=35),
    )
    manager.orders_repo.list.return_value = ([prior_cycle_buy, current_cycle_buy], 2)

    position = Mock()
    position.symbol = "RELIANCE-EQ"
    position.quantity = 35.0
    position.closed_at = None
    position.opened_at = cycle_open
    manager.positions_repo.list.return_value = [position]
    manager.positions_repo.get_by_symbol.return_value = position

    manager.portfolio = Mock()
    manager.portfolio.get_holdings.return_value = {
        "data": [{"tradingSymbol": "RELIANCE-EQ", "quantity": 45}]
    }
    manager.portfolio.get_positions.return_value = {
        "data": [{"trdSym": "RELIANCE-EQ", "qty": "45"}]
    }
    manager.orders.get_orders.return_value = {"data": []}
    manager._should_skip_broker_holdings_reconciliation = Mock(return_value=False)

    stats = manager._reconcile_positions_with_broker_holdings()

    assert stats["checked"] == 1
    assert stats["ignored"] == 1
    assert stats["updated"] == 0
    manager.positions_repo.upsert.assert_not_called()
