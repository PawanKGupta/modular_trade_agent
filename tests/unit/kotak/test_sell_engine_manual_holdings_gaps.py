"""Gap tests for manual/system mixed holdings and reconciliation timing."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
from src.infrastructure.db.models import OrderStatus as DbOrderStatus, Positions, TradeMode


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
def sell_manager_with_repos():
    with patch(
        "modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio",
    ) as portfolio_cls:
        portfolio = Mock()
        portfolio.get_positions.return_value = {"data": []}
        portfolio_cls.return_value = portfolio

        positions_repo = Mock()
        orders_repo = Mock()

        manager = SellOrderManager(
            auth=Mock(),
            positions_repo=positions_repo,
            orders_repo=orders_repo,
            user_id=1,
        )
        manager.portfolio = portfolio
        manager.orders = Mock()
        manager.orders.get_orders.return_value = {"data": []}

        yield manager, positions_repo, orders_repo, portfolio


@pytest.fixture
def sell_manager_without_skip_mock(sell_manager_with_repos):
    """Sell manager using real reconciliation skip rules (for timing tests)."""
    manager, positions_repo, orders_repo, portfolio = sell_manager_with_repos
    return manager, positions_repo, orders_repo, portfolio


class TestMixedHoldingsReconcileGaps:
    """X3 / M4: manual shares mixed with system holdings."""

    def test_reconcile_only_manual_shares_remaining_misreduces_db(
        self, sell_manager_with_repos
    ):
        """
        X3 limitation: holdings reconcile cannot separate manual remainder from partial sell.

        User had 35 system shares and sold all 35 on broker; 10 manual shares remain.
        Broker total is 10, DB still 35 — reconcile treats this as a partial system sell
        and reduces DB to 10 (incorrect alignment to manual qty).
        """
        manager, positions_repo, orders_repo, portfolio = sell_manager_with_repos
        manager._should_skip_broker_holdings_reconciliation = Mock(return_value=False)

        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
        position.quantity = 35.0
        position.closed_at = None
        position.opened_at = datetime(2026, 6, 1, 9, 30, 0)
        positions_repo.list.return_value = [position]
        positions_repo.get_by_symbol.return_value = position
        orders_repo.list.return_value = ([], 0)

        portfolio.get_holdings.return_value = {
            "data": [{"tradingSymbol": "RELIANCE-EQ", "quantity": 10}]
        }

        stats = manager._reconcile_positions_with_broker_holdings()

        assert stats["updated"] == 1
        positions_repo.reduce_quantity.assert_called_once()
        assert positions_repo.reduce_quantity.call_args.kwargs["sold_quantity"] == 25.0
        positions_repo.mark_closed.assert_not_called()

    def test_detect_manual_sells_closes_position_on_untracked_full_system_sell(
        self, sell_manager_with_repos
    ):
        """
        X3 complement: order-book detection closes DB when user fully sells system qty on broker,
        even if manual shares remain in holdings (not represented in positions table).
        """
        manager, positions_repo, orders_repo, portfolio = sell_manager_with_repos
        manager._should_skip_broker_holdings_reconciliation = Mock(return_value=False)

        position = Mock(spec=Positions)
        position.symbol = "RELIANCE-EQ"
        position.quantity = 35.0
        position.closed_at = None
        position.opened_at = datetime(2026, 6, 1, 9, 30, 0)
        positions_repo.list.return_value = [position]
        positions_repo.get_by_symbol.return_value = position

        system_buy = _closed_buy(
            symbol="RELIANCE-EQ",
            qty=35.0,
            price=2500.0,
            execution_time=datetime(2026, 6, 1, 9, 31, 0),
        )
        orders_repo.list.return_value = ([system_buy], 1)

        broker_sell = {
            "trdSym": "RELIANCE-EQ",
            "transactionType": "S",
            "orderStatus": "complete",
            "fldQty": 35,
            "avgPrc": 2600.0,
            "nOrdNo": "MANUAL_SELL_001",
        }

        with patch.object(manager, "_normalize_order_strict") as mock_norm:
            mock_norm.return_value = {
                "status": "complete",
                "filled_qty": 35,
                "execution_price": 2600.0,
                "broker_order_id": "MANUAL_SELL_001",
                "symbol": "RELIANCE-EQ",
            }
            with patch.object(manager, "_register_order"):
                with patch.object(manager, "_resolve_close_reason_and_audit") as mock_resolve:
                    mock_resolve.return_value = ("MANUAL", None, "manual")
                    stats = manager._detect_manual_sells_from_orders({"data": [broker_sell]})

        assert stats["detected"] == 1
        assert stats["closed"] == 1
        positions_repo.mark_closed.assert_called_once()

    def test_reconcile_ignores_broker_excess_after_reentry_when_manual_shares_present(
        self, sell_manager_with_repos
    ):
        """
        M4 / X4: after re-entry, broker may exceed DB due to manual shares — do not sync/inflate DB.
        """
        manager, positions_repo, orders_repo, portfolio = sell_manager_with_repos
        manager._should_skip_broker_holdings_reconciliation = Mock(return_value=False)
        cycle_open = datetime(2026, 6, 10, 9, 30, 0)

        position = Mock(spec=Positions)
        position.symbol = "GALLANTT-EQ"
        position.quantity = 45.0
        position.closed_at = None
        position.opened_at = cycle_open
        positions_repo.list.return_value = [position]
        positions_repo.get_by_symbol.return_value = position

        initial = _closed_buy(
            symbol="GALLANTT-EQ",
            qty=35.0,
            price=640.0,
            execution_time=datetime(2026, 6, 10, 9, 31, 0),
        )
        reentry = _closed_buy(
            symbol="GALLANTT-EQ",
            qty=10.0,
            price=620.0,
            execution_time=datetime(2026, 6, 10, 10, 0, 0),
        )
        orders_repo.list.side_effect = lambda *args, **kwargs: (
            ([initial, reentry], 2)
            if kwargs.get("status") == DbOrderStatus.CLOSED
            else ([initial, reentry], 2)
        )

        portfolio.get_holdings.return_value = {
            "data": [{"tradingSymbol": "GALLANTT-EQ", "quantity": 55}]
        }
        portfolio.get_positions.return_value = {
            "data": [{"trdSym": "GALLANTT-EQ", "qty": "55"}]
        }

        stats = manager._reconcile_positions_with_broker_holdings()

        assert stats["ignored"] == 1
        assert stats["updated"] == 0
        positions_repo.upsert.assert_not_called()

        open_positions = manager.get_open_positions()
        assert len(open_positions) == 1
        assert open_positions[0]["qty"] == 45


class TestReconcileTimingGaps:
    """T3: skip reconciliation when broker holdings are unreliable."""

    def test_reconcile_skips_when_recent_executed_buy_within_120_minutes(
        self, sell_manager_without_skip_mock
    ):
        fixed_now = datetime(2026, 6, 10, 12, 0, 0)

        manager, positions_repo, orders_repo, portfolio = sell_manager_without_skip_mock

        position = Mock(spec=Positions)
        position.symbol = "PFC-EQ"
        position.quantity = 24.0
        position.closed_at = None
        position.opened_at = datetime(2026, 6, 1, 9, 30, 0)
        positions_repo.list.return_value = [position]
        positions_repo.get_by_symbol.return_value = position

        recent_buy = _closed_buy(
            symbol="PFC-EQ",
            qty=24.0,
            price=400.0,
            execution_time=fixed_now - timedelta(minutes=30),
        )
        orders_repo.list.return_value = ([recent_buy], 1)

        portfolio.get_holdings.return_value = {
            "data": [{"tradingSymbol": "PFC-EQ", "quantity": 0}]
        }

        from src.infrastructure.db.timezone_utils import IST

        fixed_now_aware = fixed_now.replace(tzinfo=IST)
        with (
            patch("modules.kotak_neo_auto_trader.sell_engine.ist_now", return_value=fixed_now_aware),
            patch("modules.kotak_neo_auto_trader.sell_engine.ist_now_naive", return_value=fixed_now),
        ):
            stats = manager._reconcile_positions_with_broker_holdings()

        assert stats["checked"] == 1
        assert stats["ignored"] == 1
        assert stats["closed"] == 0
        positions_repo.mark_closed.assert_not_called()
        positions_repo.reduce_quantity.assert_not_called()

    def test_has_recent_executed_buy_order_true_within_window(
        self, sell_manager_with_repos
    ):
        fixed_now = datetime(2026, 6, 10, 12, 0, 0)
        manager, positions_repo, orders_repo, _portfolio = sell_manager_with_repos

        position = Mock()
        position.opened_at = datetime(2026, 6, 1, 9, 30, 0)
        positions_repo.get_by_symbol.return_value = position

        recent_buy = _closed_buy(
            symbol="PFC-EQ",
            qty=10.0,
            price=400.0,
            execution_time=fixed_now - timedelta(minutes=45),
        )
        orders_repo.list.return_value = ([recent_buy], 1)

        with patch(
            "modules.kotak_neo_auto_trader.sell_engine.ist_now_naive",
            return_value=fixed_now,
        ):
            assert manager._has_recent_executed_buy_order("PFC-EQ", minutes=120) is True
