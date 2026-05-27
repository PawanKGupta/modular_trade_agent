"""Portfolio account metrics use DB (not account.json)."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from server.app.routers import paper_trading as pt


def test_sum_paper_realized_pnl_filters_to_paper_only():
    opened = datetime(2025, 1, 1, 10, 0, 0)
    closed = datetime(2025, 2, 1, 10, 0, 0)
    paper_closed = SimpleNamespace(
        symbol="RELIANCE-EQ",
        opened_at=opened,
        closed_at=closed,
        realized_pnl=100.0,
    )
    broker_closed = SimpleNamespace(
        symbol="TCS-EQ",
        opened_at=opened,
        closed_at=closed,
        realized_pnl=999.0,
    )
    paper_buy = SimpleNamespace(
        symbol="RELIANCE-EQ",
        side="buy",
        placed_at=opened,
        trade_mode=pt.TradeMode.PAPER,
    )
    broker_buy = SimpleNamespace(
        symbol="TCS-EQ",
        side="buy",
        placed_at=opened,
        trade_mode=pt.TradeMode.BROKER,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [paper_closed, broker_closed]
    settings = SimpleNamespace(trade_mode=pt.TradeMode.PAPER)

    total = pt._sum_paper_realized_pnl(db, 1, [paper_buy, broker_buy], settings)
    assert total == pytest.approx(100.0)


def test_paper_orders_filters_by_trade_mode():
    paper = SimpleNamespace(trade_mode=pt.TradeMode.PAPER)
    broker = SimpleNamespace(trade_mode=pt.TradeMode.BROKER)
    assert pt._paper_orders([paper, broker]) == [paper]


def test_list_paper_closed_positions_excludes_broker_rows():
    opened = datetime(2025, 1, 1, 10, 0, 0)
    closed = datetime(2025, 2, 1, 10, 0, 0)
    paper_pos = SimpleNamespace(
        symbol="RELIANCE-EQ",
        opened_at=opened,
        closed_at=closed,
        realized_pnl=50.0,
    )
    broker_pos = SimpleNamespace(
        symbol="TCS-EQ",
        opened_at=opened,
        closed_at=closed,
        realized_pnl=500.0,
    )
    paper_buy = SimpleNamespace(
        symbol="RELIANCE-EQ",
        side="buy",
        placed_at=opened,
        trade_mode=pt.TradeMode.PAPER,
    )
    broker_buy = SimpleNamespace(
        symbol="TCS-EQ",
        side="buy",
        placed_at=opened,
        trade_mode=pt.TradeMode.BROKER,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [paper_pos, broker_pos]
    settings = SimpleNamespace(trade_mode=pt.TradeMode.PAPER)

    rows = pt._list_paper_closed_positions(db, 1, [paper_buy, broker_buy], settings)
    assert rows == [paper_pos]
    assert pt._sum_paper_realized_pnl(db, 1, [paper_buy, broker_buy], settings) == pytest.approx(
        50.0
    )


def test_history_net_pnl_matches_portfolio_realized_sum():
    """Closed-position DTO sum should match _sum_paper_realized_pnl for paper-only rows."""
    opened = datetime(2025, 1, 1, 10, 0, 0)
    closed = datetime(2025, 2, 1, 10, 0, 0)
    pos_a = SimpleNamespace(
        symbol="RELIANCE-EQ",
        opened_at=opened,
        closed_at=closed,
        realized_pnl=100.0,
        avg_price=100.0,
        exit_price=110.0,
        quantity=10,
        sell_order_id=None,
    )
    pos_b = SimpleNamespace(
        symbol="INFY-EQ",
        opened_at=opened,
        closed_at=closed,
        realized_pnl=-25.0,
        avg_price=200.0,
        exit_price=195.0,
        quantity=5,
        sell_order_id=None,
    )
    paper_buy_a = SimpleNamespace(
        symbol="RELIANCE-EQ",
        side="buy",
        placed_at=opened,
        trade_mode=pt.TradeMode.PAPER,
    )
    paper_buy_b = SimpleNamespace(
        symbol="INFY-EQ",
        side="buy",
        placed_at=opened,
        trade_mode=pt.TradeMode.PAPER,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [pos_a, pos_b]
    settings = SimpleNamespace(trade_mode=pt.TradeMode.PAPER)
    orders = [paper_buy_a, paper_buy_b]
    orders_repo = MagicMock()
    orders_repo.get.return_value = None
    fee_rate = 0.0

    closed_dtos = [
        row
        for p in pt._list_paper_closed_positions(db, 1, orders, settings)
        if (row := pt._build_closed_position_row(p, orders_repo, fee_rate)) is not None
    ]
    net_from_history = sum(p.realized_pnl for p in closed_dtos)
    assert net_from_history == pytest.approx(pt._sum_paper_realized_pnl(db, 1, orders, settings))


def test_derive_available_cash_matches_total_value_identity():
    initial = 1_000_000.0
    realized = 3_483.08
    unrealized = -475.20
    portfolio_value = 98_985.60
    cash = pt._derive_available_cash(initial, realized, unrealized, portfolio_value)
    assert cash + portfolio_value == pytest.approx(initial + realized + unrealized)
