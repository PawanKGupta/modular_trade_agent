# ruff: noqa: E501
"""HTTP-layer and small-helper branches for `pnl` router not covered elsewhere."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from server.app.routers import pnl as pnl_router
from tests.unit.server.routers.test_pnl_router import _FakePagedDb


def test_pnl_summary_invalid_trade_mode_raises():
    with pytest.raises(HTTPException) as ei:
        pnl_router.pnl_summary(
            start=None,
            end=None,
            trade_mode="not-paper-or-broker",
            include_unrealized=False,
            db=MagicMock(),
            current=SimpleNamespace(id=1),
        )
    assert ei.value.status_code == 400


def test_audit_history_wraps_repository_errors(monkeypatch):
    class _Bad:
        def get_by_user(self, *_a, **_k):
            raise RuntimeError("db down")

    monkeypatch.setattr(pnl_router, "PnlAuditRepository", lambda db: _Bad())
    with pytest.raises(HTTPException) as ei:
        pnl_router.audit_history(
            limit=5, status=None, db=MagicMock(), current=SimpleNamespace(id=2)
        )
    assert ei.value.status_code == 500
    assert "db down" in str(ei.value.detail)


def test_calculate_pnl_wraps_unexpected_service_errors(monkeypatch):
    class _Svc:
        def calculate_daily_pnl(self, *_a, **_k):
            raise RuntimeError("calc exploded")

    monkeypatch.setattr(pnl_router, "PnlCalculationService", lambda db: _Svc())
    with pytest.raises(HTTPException) as ei:
        pnl_router.calculate_pnl(
            target_date=None,
            trade_mode=None,
            db=MagicMock(),
            current=SimpleNamespace(id=3),
        )
    assert ei.value.status_code == 500


def test_backfill_pnl_wraps_unexpected_service_errors(monkeypatch):
    class _Svc:
        def calculate_date_range(self, *_a, **_k):
            raise RuntimeError("backfill exploded")

    monkeypatch.setattr(pnl_router, "PnlCalculationService", lambda db: _Svc())
    with pytest.raises(HTTPException) as ei:
        pnl_router.backfill_pnl(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
            trade_mode=None,
            db=MagicMock(),
            current=SimpleNamespace(id=4),
        )
    assert ei.value.status_code == 500


def test_get_stock_name_returns_none_on_yfinance_error(monkeypatch):
    class _BadYf:
        def Ticker(self, *_a, **_k):
            raise ConnectionError("offline")

    monkeypatch.setitem(__import__("sys").modules, "yfinance", _BadYf())
    assert pnl_router._get_stock_name("RELIANCE-EQ") is None


def test_get_closed_positions_filters_by_trade_mode_and_asc_sort(monkeypatch):
    current = SimpleNamespace(id=501)
    pos = SimpleNamespace(
        id=1,
        symbol="AAA",
        quantity=1,
        avg_price=10.0,
        exit_price=11.0,
        opened_at=datetime(2024, 1, 1, 10, 0, 0),
        closed_at=datetime(2024, 1, 5, 10, 0, 0),
        realized_pnl=1.0,
        realized_pnl_pct=10.0,
        exit_reason="tp",
    )
    fake_db = _FakePagedDb([pos])
    buy = SimpleNamespace(
        symbol="AAA",
        side="buy",
        trade_mode=pnl_router.TradeMode.PAPER,
        placed_at=datetime(2024, 1, 1, 10, 30, 0),
    )
    monkeypatch.setattr(
        pnl_router,
        "OrdersRepository",
        lambda db: SimpleNamespace(list=lambda uid: ([buy], 1)),
    )
    monkeypatch.setattr(pnl_router, "_get_stock_name", lambda symbol: None)
    out = pnl_router.get_closed_positions(
        page=1,
        page_size=10,
        trade_mode="paper",
        sort_by="symbol",
        sort_order="asc",
        db=fake_db,
        current=current,
    )
    assert out.total == 1
    assert out.items[0].symbol == "AAA"
