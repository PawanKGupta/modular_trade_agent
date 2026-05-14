# ruff: noqa: E501, PLC0415
"""Additional metrics router coverage (trade_mode filter, errors, pool failure)."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server.app.routers import metrics as metrics_router


class FakeResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class FakeDBWithOrders:
    def __init__(self, positions, orders_by_id: dict):
        self._positions = positions
        self._orders = orders_by_id

    def execute(self, stmt):
        return FakeResult(self._positions)

    def query(self, model):
        return _OrderQuery(self._orders)


class _OrderQuery:
    def __init__(self, orders_by_id):
        self._orders = orders_by_id

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return None


def test_get_dashboard_metrics_invalid_trade_mode(monkeypatch):
    monkeypatch.setattr(
        metrics_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(ensure_default=lambda uid: SimpleNamespace()),
    )
    with pytest.raises(HTTPException) as ei:
        metrics_router.get_dashboard_metrics(
            period_days=7,
            trade_mode="nope",
            db=FakeDBWithOrders([], {}),
            current=SimpleNamespace(id=1),
        )
    assert ei.value.status_code == 400


def test_get_daily_metrics_invalid_trade_mode(monkeypatch):
    monkeypatch.setattr(
        metrics_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(ensure_default=lambda uid: SimpleNamespace()),
    )
    with pytest.raises(HTTPException) as ei:
        metrics_router.get_daily_metrics(
            date_str="2026-01-15",
            trade_mode="invalid-mode",
            db=FakeDBWithOrders([], {}),
            current=SimpleNamespace(id=1),
        )
    assert ei.value.status_code == 400


def test_get_dashboard_metrics_execute_raises(monkeypatch):
    monkeypatch.setattr(
        metrics_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(ensure_default=lambda uid: SimpleNamespace()),
    )

    class _Bad:
        def execute(self, stmt):
            raise RuntimeError("exec")

    with pytest.raises(HTTPException) as ei:
        metrics_router.get_dashboard_metrics(
            period_days=5,
            trade_mode=None,
            db=_Bad(),
            current=SimpleNamespace(id=1),
        )
    assert ei.value.status_code == 500


def test_get_daily_metrics_trade_mode_and_success(monkeypatch):
    monkeypatch.setattr(
        metrics_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(ensure_default=lambda uid: SimpleNamespace()),
    )
    day = datetime(2026, 3, 10, 14, 0, 0)
    pos = SimpleNamespace(
        user_id=2,
        closed_at=day,
        opened_at=day - timedelta(hours=1),
        realized_pnl=25.0,
        symbol="Z",
        buy_order_id=None,
    )
    db = FakeDBWithOrders([pos], {})
    out = metrics_router.get_daily_metrics(
        date_str="2026-03-10",
        trade_mode=None,
        db=db,
        current=SimpleNamespace(id=2),
    )
    assert out["trades"] == 1
    assert out["daily_pnl"] == 25.0


def test_get_daily_metrics_wraps_non_value_errors(monkeypatch):
    monkeypatch.setattr(
        metrics_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(ensure_default=lambda uid: SimpleNamespace()),
    )

    class _Bad:
        def execute(self, stmt):
            raise OSError("db")

    with pytest.raises(HTTPException) as ei:
        metrics_router.get_daily_metrics(
            date_str="2026-01-01",
            trade_mode=None,
            db=_Bad(),
            current=SimpleNamespace(id=1),
        )
    assert ei.value.status_code == 500


def test_get_db_connection_pool_status_failure(monkeypatch):
    monkeypatch.setattr(
        metrics_router,
        "get_pool_status",
        lambda engine: (_ for _ in ()).throw(RuntimeError("pool")),
    )
    with pytest.raises(HTTPException) as ei:
        metrics_router.get_db_connection_pool_status(current=SimpleNamespace(id=1))
    assert ei.value.status_code == 500


def test_get_dashboard_metrics_trade_mode_filters_positions(monkeypatch):
    """When ``trade_mode`` is set, only positions whose buy order matches are counted."""
    monkeypatch.setattr(
        metrics_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(ensure_default=lambda uid: SimpleNamespace()),
    )
    monkeypatch.setattr(metrics_router, "ist_now_naive", lambda: datetime(2026, 4, 15, 12, 0, 0))
    from src.infrastructure.db.models import Orders, TradeMode

    day = datetime(2026, 4, 1, 12, 0, 0)
    pos_no_buy = SimpleNamespace(
        user_id=1,
        closed_at=day,
        opened_at=day,
        realized_pnl=99.0,
        symbol="SKIP",
        buy_order_id=None,
    )
    pos_paper = SimpleNamespace(
        user_id=1,
        closed_at=day,
        opened_at=day,
        realized_pnl=10.0,
        symbol="KEEP",
        buy_order_id=42,
    )
    buy = SimpleNamespace(id=42, trade_mode=TradeMode.PAPER)

    class _Lookup:
        def filter(self, *a, **k):
            return self

        def first(self):
            return buy

    class _DB:
        def execute(self, stmt):
            return FakeResult([pos_no_buy, pos_paper])

        def query(self, model):
            if model is Orders:
                return _Lookup()
            return _Lookup()

    out = metrics_router.get_dashboard_metrics(
        period_days=30,
        trade_mode="paper",
        db=_DB(),
        current=SimpleNamespace(id=1),
    )
    assert out.total_trades == 1
    assert out.total_realized_pnl == 10.0


def test_get_daily_metrics_trade_mode_filters_positions(monkeypatch):
    monkeypatch.setattr(
        metrics_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(ensure_default=lambda uid: SimpleNamespace()),
    )
    from src.infrastructure.db.models import TradeMode

    day = datetime(2026, 5, 2, 15, 0, 0)
    pos = SimpleNamespace(
        user_id=1,
        closed_at=day,
        opened_at=day,
        realized_pnl=3.0,
        symbol="X",
        buy_order_id=7,
    )
    buy = SimpleNamespace(id=7, trade_mode=TradeMode.BROKER)

    class _Lookup:
        def filter(self, *a, **k):
            return self

        def first(self):
            return buy

    class _DB:
        def execute(self, stmt):
            return FakeResult([pos])

        def query(self, model):
            return _Lookup()

    out = metrics_router.get_daily_metrics(
        date_str="2026-05-02",
        trade_mode="broker",
        db=_DB(),
        current=SimpleNamespace(id=1),
    )
    assert out["trades"] == 1
    assert out["daily_pnl"] == 3.0
