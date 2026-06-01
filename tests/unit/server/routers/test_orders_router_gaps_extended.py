"""Extra branch tests for ``orders`` router helpers and ``list_orders``."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from server.app.routers import orders as orders_router
from src.infrastructure.db.models import OrderStatus, TradeMode


def test_normalize_repo_list_result_tuple_and_plain_list():
    items = [object()]
    assert orders_router._normalize_repo_list_result((items, 5)) == (items, 5)
    assert orders_router._normalize_repo_list_result(items) == (items, 1)


def test_is_order_monitoring_active_returns_false_on_conflict_error(monkeypatch):
    class _Boom:
        def is_unified_service_running(self, user_id):
            raise RuntimeError("db")

    monkeypatch.setattr(orders_router, "ConflictDetectionService", lambda db: _Boom())
    assert orders_router._is_order_monitoring_active(1, MagicMock()) is False


def test_recalculate_order_quantity_empty_history_uses_order_price(monkeypatch):
    class _Hist:
        @property
        def empty(self):
            return True

    class _Ticker:
        def history(self, period):
            return _Hist()

    monkeypatch.setitem(
        __import__("sys").modules, "yfinance", SimpleNamespace(Ticker=lambda t: _Ticker())
    )
    monkeypatch.setattr(
        orders_router,
        "UserTradingConfigRepository",
        lambda db: SimpleNamespace(get=lambda uid: None),
    )

    order = SimpleNamespace(
        symbol="AAA-EQ",
        ticker=None,
        quantity=1,
        price=55.0,
    )
    orders_router._recalculate_order_quantity(order, 1, MagicMock(), 99)
    assert order.price == 55.0


def test_recalculate_order_quantity_swallows_calc_errors(monkeypatch):
    monkeypatch.setitem(
        __import__("sys").modules,
        "yfinance",
        SimpleNamespace(Ticker=lambda t: (_ for _ in ()).throw(RuntimeError("net"))),
    )
    order = SimpleNamespace(symbol="X", ticker=None, quantity=3, price=10.0)
    orders_router._recalculate_order_quantity(order, 1, MagicMock(), 1)
    assert order.quantity == 3


def _make_list_order(symbol="S", oid=1, placed_at=None, **extra):
    return SimpleNamespace(
        id=oid,
        symbol=symbol,
        side="buy",
        quantity=1.0,
        price=1.0,
        status=OrderStatus.PENDING,
        placed_at=placed_at or datetime(2025, 1, 1, 12, 0, 0),
        closed_at=None,
        trade_mode=TradeMode.PAPER,
        reason=None,
        first_failed_at=None,
        last_retry_attempt=None,
        retry_count=0,
        last_status_check=None,
        execution_price=None,
        execution_qty=None,
        execution_time=None,
        entry_type=None,
        orig_source=None,
        **extra,
    )


def test_list_orders_typeerror_fallback(monkeypatch):
    good = _make_list_order(oid=2)

    class _Repo:
        def list(self, user_id, status=None, **kwargs):
            if kwargs:
                raise TypeError("legacy signature")
            return [good]

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(get_by_user_id=lambda uid: SimpleNamespace(broker="kotak-neo")),
    )

    out = orders_router.list_orders(
        status=None,
        reason=None,
        from_date=None,
        to_date=None,
        page=1,
        page_size=50,
        db=MagicMock(),
        current=SimpleNamespace(id=7),
    )
    assert out.total == 1
    assert out.items[0].id == 2


def test_list_orders_invalid_date(monkeypatch):
    class _Repo:
        def list(self, user_id, status=None, **kwargs):
            if kwargs:
                raise TypeError()
            return [_make_list_order()]

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(get_by_user_id=lambda uid: None),
    )

    with pytest.raises(HTTPException) as ei:
        orders_router.list_orders(
            status=None,
            reason=None,
            from_date="not-a-date",
            to_date=None,
            page=1,
            page_size=50,
            db=MagicMock(),
            current=SimpleNamespace(id=7),
        )
    assert ei.value.status_code == 500
    assert "Invalid date format" in str(ei.value.detail)


def test_list_orders_skips_serialize_errors(monkeypatch, caplog):
    bad = _make_list_order(oid=1)
    bad.status = object()
    good = _make_list_order(oid=2)

    class _Repo:
        def list(self, user_id, status=None, **kwargs):
            if kwargs:
                raise TypeError()
            return [bad, good]

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(get_by_user_id=lambda uid: None),
    )

    with caplog.at_level("ERROR"):
        out = orders_router.list_orders(
            status=None,
            reason=None,
            from_date=None,
            to_date=None,
            page=1,
            page_size=50,
            db=MagicMock(),
            current=SimpleNamespace(id=1),
        )
    assert len(out.items) == 1
    assert out.items[0].id == 2


def test_list_orders_format_datetime_non_datetime_branch(monkeypatch):
    o = _make_list_order(oid=3, placed_at=12345)

    class _Repo:
        def list(self, user_id, status=None, **kwargs):
            if kwargs:
                raise TypeError()
            return [o]

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(get_by_user_id=lambda uid: None),
    )

    out = orders_router.list_orders(
        status=None,
        reason=None,
        from_date=None,
        to_date=None,
        page=1,
        page_size=50,
        db=MagicMock(),
        current=SimpleNamespace(id=1),
    )
    assert out.items[0].created_at == "12345"


def test_list_orders_broker_trade_mode_display_fallback(monkeypatch):
    o = _make_list_order(oid=4)
    o.trade_mode = TradeMode.BROKER

    class _Repo:
        def list(self, user_id, status=None, **kwargs):
            if kwargs:
                raise TypeError()
            return [o]

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(get_by_user_id=lambda uid: None),
    )

    out = orders_router.list_orders(
        status=None,
        reason=None,
        from_date=None,
        to_date=None,
        page=1,
        page_size=50,
        db=MagicMock(),
        current=SimpleNamespace(id=1),
    )
    assert out.items[0].trade_mode_display == "Broker"


def test_list_orders_reason_partial_match_case_insensitive(monkeypatch):
    o1 = _make_list_order(oid=1)
    o1.reason = "Alpha miss"
    o2 = _make_list_order(oid=2)
    o2.reason = "other"

    class _Repo:
        def list(self, user_id, status=None, **kwargs):
            if kwargs:
                raise TypeError()
            return [o1, o2]

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(get_by_user_id=lambda uid: None),
    )

    out = orders_router.list_orders(
        status=None,
        reason="ALPHA",
        from_date=None,
        to_date=None,
        page=1,
        page_size=50,
        db=MagicMock(),
        current=SimpleNamespace(id=1),
    )
    assert len(out.items) == 1
    assert out.items[0].id == 1


def test_recalculate_order_quantity_invalid_close_price_swallows(monkeypatch):
    """History with non-positive close hits ``ValueError`` and is swallowed."""

    class _Hist:
        @property
        def empty(self):
            return False

        def __getitem__(self, key):
            class _ILoc:
                def __getitem__(self, idx):
                    return 0.0

            return SimpleNamespace(iloc=_ILoc())

    class _Ticker:
        def history(self, period):
            return _Hist()

    monkeypatch.setattr(orders_router, "yf", SimpleNamespace(Ticker=lambda t: _Ticker()))
    monkeypatch.setattr(
        orders_router,
        "UserTradingConfigRepository",
        lambda db: SimpleNamespace(get=lambda uid: None),
    )

    order = SimpleNamespace(symbol="AAA-EQ", ticker=None, quantity=7, price=10.0)
    orders_router._recalculate_order_quantity(order, 1, MagicMock(), 42)
    assert order.quantity == 7


def test_retry_order_format_datetime_non_datetime(monkeypatch):
    order = SimpleNamespace(
        id=1,
        user_id=1,
        symbol="S",
        side="buy",
        quantity=1,
        price=10.0,
        status=OrderStatus.FAILED,
        placed_at=999,
        closed_at=None,
        retry_count=0,
        first_failed_at=None,
        last_retry_attempt=None,
        last_status_check=None,
        orig_source=None,
        execution_price=None,
        execution_qty=None,
        execution_time=None,
        entry_type=None,
        reason=None,
    )

    class _Repo:
        def get(self, oid):
            return order

        def update(self, o):
            return o

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(orders_router, "_recalculate_order_quantity", lambda *a, **k: None)
    monkeypatch.setattr(
        orders_router,
        "ist_now",
        lambda: datetime(2026, 1, 1, 12, 0, 0),
    )

    resp = orders_router.retry_order(
        order_id=1,
        db=MagicMock(),
        current=SimpleNamespace(id=1),
    )
    assert resp.created_at == "999"


def test_list_orders_format_datetime_isoformat_for_datetime(monkeypatch):
    o = _make_list_order(oid=1)
    o.placed_at = datetime(2026, 3, 1, 10, 30, 0)
    o.closed_at = datetime(2026, 3, 2, 11, 0, 0)
    o.trade_mode = TradeMode.PAPER

    class _Repo:
        def list(self, user_id, status=None, **kwargs):
            if kwargs:
                raise TypeError()
            return [o]

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(get_by_user_id=lambda uid: SimpleNamespace(broker="kotak-neo")),
    )

    out = orders_router.list_orders(
        status=None,
        reason=None,
        from_date=None,
        to_date=None,
        page=1,
        page_size=50,
        db=MagicMock(),
        current=SimpleNamespace(id=1),
    )
    assert out.items[0].created_at.startswith("2026-03-01T10:30:00")
    assert out.items[0].updated_at.startswith("2026-03-02T11:00:00")


def test_list_orders_broker_trade_mode_display_kebab_title(monkeypatch):
    o = _make_list_order(oid=2)
    o.trade_mode = TradeMode.BROKER

    class _Repo:
        def list(self, user_id, status=None, **kwargs):
            if kwargs:
                raise TypeError()
            return [o]

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(get_by_user_id=lambda uid: SimpleNamespace(broker="kotak-neo")),
    )

    out = orders_router.list_orders(
        status=None,
        reason=None,
        from_date=None,
        to_date=None,
        page=1,
        page_size=50,
        db=MagicMock(),
        current=SimpleNamespace(id=1),
    )
    assert out.items[0].trade_mode_display == "Kotak Neo"


def test_list_orders_format_datetime_str_fallback_for_unknown_type(monkeypatch):
    o = _make_list_order(oid=3)
    o.placed_at = object()

    class _Repo:
        def list(self, user_id, status=None, **kwargs):
            if kwargs:
                raise TypeError()
            return [o]

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: SimpleNamespace(get_by_user_id=lambda uid: None),
    )

    out = orders_router.list_orders(
        status=None,
        reason=None,
        from_date=None,
        to_date=None,
        page=1,
        page_size=50,
        db=MagicMock(),
        current=SimpleNamespace(id=1),
    )
    assert "object at" in out.items[0].created_at
