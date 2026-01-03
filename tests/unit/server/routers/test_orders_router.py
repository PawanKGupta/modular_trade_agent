from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server.app.routers import orders as orders_router
from src.infrastructure.db.models import OrderStatus as DbOrderStatus


class DummyOrdersRepository:
    def __init__(self, *, orders=None):
        self._orders = {o.id: o for o in (orders or [])}

    def list(self, user_id, status):
        return list(self._orders.values())

    def get(self, order_id):
        return self._orders.get(order_id)

    def update(self, order):
        return order


class DummySettingsRepository:
    def __init__(self, settings):
        self._settings = settings

    def get_by_user_id(self, user_id):
        return self._settings


def _patch_repositories(monkeypatch, orders=None, settings=None):
    monkeypatch.setattr(
        orders_router,
        "OrdersRepository",
        lambda db: DummyOrdersRepository(orders=orders),
    )
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: DummySettingsRepository(settings),
    )


def test_list_orders_filters_and_formats(monkeypatch):
    order = SimpleNamespace(
        id=1,
        symbol="TEST",
        side="sell",
        quantity=8,
        price=101.5,
        status=DbOrderStatus.PENDING,
        placed_at=datetime(2024, 1, 1, 10, 0, 0),
        closed_at=None,
        reason="Matching reason",
        trade_mode="paper",
        orig_source="manual",
    )
    settings = SimpleNamespace(broker="kotak-neo")
    _patch_repositories(monkeypatch, orders=[order], settings=settings)

    current = SimpleNamespace(id=41)
    response = orders_router.list_orders(
        status="pending",
        reason="matching",
        from_date="2024-01-01",
        to_date="2024-01-02",
        db=SimpleNamespace(),
        current=current,
    )

    assert len(response) == 1
    result = response[0]
    assert result.trade_mode_display == "Paper"
    assert result.reason == "Matching reason"
    assert result.is_manual is True


def test_list_orders_invalid_date(monkeypatch):
    _patch_repositories(monkeypatch, orders=[], settings=SimpleNamespace(broker=None))
    current = SimpleNamespace(id=12)

    with pytest.raises(HTTPException):
        orders_router.list_orders(
            from_date="not-a-date",
            db=SimpleNamespace(),
            current=current,
        )


def test_retry_order_updates_reason_and_retry_count(monkeypatch):
    order = SimpleNamespace(
        id=7,
        user_id=99,
        symbol="RETRY",
        side="buy",
        quantity=5,
        price=12.0,
        status=DbOrderStatus.FAILED,
        retry_count=1,
        reason="First fail",
        placed_at=datetime(2024, 1, 1),
        closed_at=None,
        orig_source="manual",
        first_failed_at=None,
        last_retry_attempt=None,
        last_status_check=None,
    )
    repo = DummyOrdersRepository(orders=[order])
    monkeypatch.setattr(
        orders_router,
        "OrdersRepository",
        lambda db: repo,
    )
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: DummySettingsRepository(None),
    )

    def fake_recalculate_quantity(target_order, user_id, db, order_id):
        target_order.quantity = 10
        target_order.price = 42.5

    monkeypatch.setattr(orders_router, "_recalculate_order_quantity", fake_recalculate_quantity)
    monkeypatch.setattr(orders_router, "ist_now", lambda: datetime(2024, 1, 1, 12, 0, 0))

    response = orders_router.retry_order(
        order_id=7,
        db=SimpleNamespace(),
        current=SimpleNamespace(id=99),
    )

    assert response.retry_count == 2
    assert response.quantity == 10
    assert response.price == 42.5
    assert "Manual retry requested" in response.reason


def test_drop_order_success(monkeypatch):
    order = SimpleNamespace(id=33, user_id=55, status=DbOrderStatus.FAILED)
    repo = DummyOrdersRepository(orders=[order])
    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: repo)
    monkeypatch.setattr(
        orders_router, "SettingsRepository", lambda db: DummySettingsRepository(None)
    )

    result = orders_router.drop_order(
        order_id=33,
        db=SimpleNamespace(),
        current=SimpleNamespace(id=55),
    )

    assert "dropped from retry queue" in result["message"]


def test_sync_order_status_paper_mode(monkeypatch):
    orders = [
        SimpleNamespace(
            id=1,
            user_id=77,
            status=DbOrderStatus.PENDING,
            trade_mode="paper",
            broker_order_id="abc1",
        ),
        SimpleNamespace(
            id=2,
            user_id=77,
            status=DbOrderStatus.ONGOING,
            trade_mode="paper",
            broker_order_id="abc2",
        ),
        SimpleNamespace(
            id=3,
            user_id=77,
            status=DbOrderStatus.CLOSED,
            trade_mode="paper",
            broker_order_id="abc3",
        ),
    ]
    _patch_repositories(
        monkeypatch,
        orders=orders,
        settings=SimpleNamespace(
            trade_mode="paper",
            broker_creds_encrypted=None,
        ),
    )
    current = SimpleNamespace(id=77)

    response = orders_router.sync_order_status(order_id=None, db=SimpleNamespace(), current=current)

    assert response["synced"] == 2
    assert response["monitoring_active"] is False


def test_sync_order_status_missing_settings(monkeypatch):
    _patch_repositories(monkeypatch, orders=[], settings=None)
    current = SimpleNamespace(id=88)

    with pytest.raises(HTTPException):
        orders_router.sync_order_status(order_id=None, db=SimpleNamespace(), current=current)
