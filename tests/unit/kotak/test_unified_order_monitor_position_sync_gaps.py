"""Gap tests for UnifiedOrderMonitor position sync reflection checks."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from modules.kotak_neo_auto_trader.unified_order_monitor import UnifiedOrderMonitor
from src.infrastructure.db.models import OrderStatus as DbOrderStatus, TradeMode


def _closed_buy(*, symbol, qty, price, execution_time, trade_mode=TradeMode.BROKER):
    order = Mock()
    order.side = "buy"
    order.symbol = symbol
    order.execution_qty = qty
    order.execution_price = price
    order.quantity = qty
    order.orig_source = "signal"
    order.trade_mode = trade_mode
    order.execution_time = execution_time
    order.filled_at = execution_time
    order.placed_at = execution_time
    order.status = DbOrderStatus.CLOSED
    return order


@pytest.fixture
def unified_monitor_with_sell_manager():
    with (
        patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio"),
        patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"),
        patch("modules.kotak_neo_auto_trader.unified_order_monitor.OrdersRepository"),
        patch("modules.kotak_neo_auto_trader.unified_order_monitor.PositionsRepository"),
    ):
        orders_repo = Mock()
        positions_repo = Mock()
        sell_manager = SellOrderManager(
            auth=Mock(),
            positions_repo=positions_repo,
            orders_repo=orders_repo,
            user_id=2,
        )
        sell_manager.orders = Mock()

        monitor = UnifiedOrderMonitor(
            sell_order_manager=sell_manager,
            db_session=Mock(),
            user_id=2,
        )
        monitor.orders_repo = orders_repo
        monitor.positions_repo = positions_repo

        yield monitor, sell_manager, positions_repo, orders_repo


class TestExecutionReflectedInOpenPositionGaps:
    """U3: cycle-scoped closed buys in monitor position reflection."""

    def test_execution_reflected_ignores_prior_cycle_closed_buys(
        self, unified_monitor_with_sell_manager
    ):
        """
        U3: prior-cycle closed buys must not make an in-sync position look lagging.
        """
        monitor, sell_manager, positions_repo, orders_repo = unified_monitor_with_sell_manager
        cycle_open = datetime(2026, 6, 20, 9, 30, 0)

        position = Mock()
        position.symbol = "SALSTEEL-EQ"
        position.quantity = 10.0
        position.closed_at = None
        position.opened_at = cycle_open
        positions_repo.get_by_symbol.return_value = position

        prior_cycle = _closed_buy(
            symbol="SALSTEEL-EQ",
            qty=10.0,
            price=100.0,
            execution_time=datetime(2026, 6, 1, 9, 31, 0),
        )
        current_cycle = _closed_buy(
            symbol="SALSTEEL-EQ",
            qty=10.0,
            price=110.0,
            execution_time=datetime(2026, 6, 20, 9, 35, 0),
        )
        orders_repo.list.return_value = ([prior_cycle, current_cycle], 2)

        order_obj = Mock()
        order_obj.symbol = "SALSTEEL-EQ"

        assert monitor._execution_reflected_in_open_position(order_obj) is True

    def test_execution_reflected_false_when_current_cycle_qty_lags(
        self, unified_monitor_with_sell_manager
    ):
        """In-cycle lag still reports not reflected when DB qty is below scoped closed buys."""
        monitor, sell_manager, positions_repo, orders_repo = unified_monitor_with_sell_manager
        cycle_open = datetime(2026, 6, 20, 9, 30, 0)

        position = Mock()
        position.symbol = "SALSTEEL-EQ"
        position.quantity = 10.0
        position.closed_at = None
        position.opened_at = cycle_open
        positions_repo.get_by_symbol.return_value = position

        initial = _closed_buy(
            symbol="SALSTEEL-EQ",
            qty=10.0,
            price=110.0,
            execution_time=datetime(2026, 6, 20, 9, 35, 0),
        )
        reentry = _closed_buy(
            symbol="SALSTEEL-EQ",
            qty=6.0,
            price=105.0,
            execution_time=datetime(2026, 6, 20, 10, 5, 0),
        )
        orders_repo.list.return_value = ([initial, reentry], 2)

        order_obj = Mock()
        order_obj.symbol = "SALSTEEL-EQ"

        assert monitor._execution_reflected_in_open_position(order_obj) is False
