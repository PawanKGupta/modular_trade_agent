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


def test_derive_available_cash_matches_total_value_identity():
    initial = 1_000_000.0
    realized = 3_483.08
    unrealized = -475.20
    portfolio_value = 98_985.60
    cash = pt._derive_available_cash(initial, realized, unrealized, portfolio_value)
    assert cash + portfolio_value == pytest.approx(initial + realized + unrealized)
