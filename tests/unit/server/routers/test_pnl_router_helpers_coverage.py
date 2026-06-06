# ruff: noqa: E501
"""Cover ``pnl`` router helpers: paper paths, backfill guard, closed-trade stats, logger reload."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from server.app.routers import pnl as pnl_router
from src.infrastructure.db.models import TradeMode


def test_get_paper_trading_account_data_reads_json(tmp_path, monkeypatch):
    uid = 4242
    base = tmp_path / "paper_trading" / f"user_{uid}"
    base.mkdir(parents=True)
    (base / "account.json").write_text(json.dumps({"available_cash": 1.0}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    data = pnl_router._get_paper_trading_account_data(uid)
    assert data is not None
    assert data["available_cash"] == 1.0


def test_get_paper_trading_account_data_swallows_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _bad_open(*_a, **_k):
        raise OSError("no access")

    monkeypatch.setattr("builtins.open", _bad_open)
    assert pnl_router._get_paper_trading_account_data(9999) is None


def test_calculate_portfolio_unrealized_pnl_branches(tmp_path, monkeypatch):
    uid = 7
    root = tmp_path / "paper_trading" / f"user_{uid}"
    root.mkdir(parents=True)
    holdings = {
        "RELIANCE.NS": {"quantity": 2, "average_price": 100.0, "current_price": 110.0},
        "TATA.NS": {"quantity": 1, "average_price": 50.0, "current_price": 55.0},
    }
    (root / "holdings.json").write_text(json.dumps(holdings), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    class _Ticker:
        def __init__(self, symbol: str):
            self.symbol = symbol
            if "RELIANCE" in symbol:
                self.info = {"currentPrice": 120.0}
            else:
                self.info = {}

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=_Ticker))

    total = pnl_router._calculate_portfolio_unrealized_pnl(uid)
    assert total > 0


def test_calculate_portfolio_unrealized_pnl_yfinance_inner_failure(tmp_path, monkeypatch):
    uid = 8
    root = tmp_path / "paper_trading" / f"user_{uid}"
    root.mkdir(parents=True)
    (root / "holdings.json").write_text(
        json.dumps({"X.NS": {"quantity": 1, "average_price": 10.0, "current_price": 12.0}}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    class _BadTicker:
        def __init__(self, *_a, **_k):
            raise RuntimeError("offline")

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=_BadTicker))
    assert pnl_router._calculate_portfolio_unrealized_pnl(uid) == pytest.approx(2.0)


def test_ensure_pnl_records_empty_orders(monkeypatch):
    class _Repo:
        def list(self, user_id):
            return []

    monkeypatch.setattr(pnl_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(pnl_router, "PnlRepository", lambda db: MagicMock())
    out = pnl_router._ensure_pnl_records(1, date(2024, 1, 1), date(2024, 1, 5), MagicMock())
    assert out == []


def test_ensure_pnl_records_runs_backfill(monkeypatch):
    d1 = date(2024, 2, 1)

    class _Ord:
        def __init__(self):
            self.placed_at = datetime(2024, 1, 15, 12, 0, 0)

    class _OrdersRepo:
        def list(self, user_id):
            return [_Ord()]

    class _PnlRepo:
        def range(self, user_id, start, end):
            return [{"date": start}]

    class _Svc:
        def __init__(self, db):
            self.called = False

        def calculate_date_range(self, user_id, start, end):
            self.called = True

    svc = _Svc(MagicMock())
    monkeypatch.setattr(pnl_router, "OrdersRepository", lambda db: _OrdersRepo())
    monkeypatch.setattr(pnl_router, "PnlRepository", lambda db: _PnlRepo())
    monkeypatch.setattr(pnl_router, "PnlCalculationService", lambda db: svc)

    db = MagicMock()
    out = pnl_router._ensure_pnl_records(3, d1, date(2024, 2, 10), db)
    assert svc.called
    assert out == [{"date": d1}]


def test_compute_closed_trade_stats_trade_mode_and_float_errors(monkeypatch):
    pos_ok = SimpleNamespace(
        id=1,
        user_id=1,
        symbol="AAA",
        closed_at=datetime(2024, 6, 1, 12, 0, 0),
        opened_at=datetime(2024, 6, 1, 10, 0, 0),
        realized_pnl="not-a-float",
        exit_price=11.0,
        avg_price=10.0,
        sell_order_id=99,
    )
    pos_skip_mode = SimpleNamespace(
        id=2,
        user_id=1,
        symbol="BBB",
        closed_at=datetime(2024, 6, 2, 12, 0, 0),
        opened_at=datetime(2024, 6, 2, 10, 0, 0),
        realized_pnl=5.0,
        exit_price=None,
        avg_price=None,
        sell_order_id=None,
    )

    class _Q:
        def filter(self, *a, **k):
            return self

        def all(self):
            return [pos_ok, pos_skip_mode]

    db = MagicMock()
    db.query = lambda model: _Q()

    buy = SimpleNamespace(
        symbol="AAA",
        side="buy",
        trade_mode=TradeMode.PAPER,
        placed_at=datetime(2024, 6, 1, 10, 15, 0),
    )

    class _OrdersRepo:
        def list(self, user_id):
            return [buy]

        def get(self, oid):
            if oid == 99:
                return SimpleNamespace(quantity=2.0, execution_qty=None)
            return None

    monkeypatch.setattr(pnl_router, "OrdersRepository", lambda session: _OrdersRepo())

    total, green, red, min_p, max_p, avg_p = pnl_router._compute_closed_trade_stats(
        1, db, TradeMode.PAPER
    )
    assert total == pytest.approx(2.0)
    assert green == 1
    assert red == 0
    assert min_p == pytest.approx(2.0)
    assert max_p == pytest.approx(2.0)
    assert avg_p == pytest.approx(2.0)
