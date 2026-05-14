# ruff: noqa: E501, PLC0415
"""Branch coverage for orders router: sync paths, statistics, list fallbacks, helpers."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from server.app.routers import orders as orders_router
from src.infrastructure.db.models import OrderStatus as DbOrderStatus


def test_normalize_repo_list_result_plain_list():
    items, total = orders_router._normalize_repo_list_result([1, 2, 3])
    assert items == [1, 2, 3]
    assert total == 3


def test_is_order_monitoring_active_unified_running(monkeypatch):
    class _CS:
        def __init__(self, db):
            pass

        def is_unified_service_running(self, user_id):
            return True

    monkeypatch.setattr(orders_router, "ConflictDetectionService", _CS)
    monkeypatch.setattr(
        orders_router,
        "IndividualServiceStatusRepository",
        lambda db: MagicMock(get_by_user_and_task=MagicMock(return_value=None)),
    )
    assert orders_router._is_order_monitoring_active(1, SimpleNamespace()) is True


def test_is_order_monitoring_active_sell_monitor_running(monkeypatch):
    class _CS:
        def __init__(self, db):
            pass

        def is_unified_service_running(self, user_id):
            return False

    st = SimpleNamespace(is_running=True)
    monkeypatch.setattr(orders_router, "ConflictDetectionService", _CS)
    monkeypatch.setattr(
        orders_router,
        "IndividualServiceStatusRepository",
        lambda db: MagicMock(get_by_user_and_task=MagicMock(return_value=st)),
    )
    assert orders_router._is_order_monitoring_active(2, SimpleNamespace()) is True


def test_is_order_monitoring_active_logs_on_exception(monkeypatch):
    class _CS:
        def __init__(self, db):
            pass

        def is_unified_service_running(self, user_id):
            raise RuntimeError("boom")

    monkeypatch.setattr(orders_router, "ConflictDetectionService", _CS)
    assert orders_router._is_order_monitoring_active(3, SimpleNamespace()) is False


def test_recalculate_order_quantity_logs_on_failure(monkeypatch):
    order = SimpleNamespace(symbol="TEST-EQ", quantity=1, price=10.0, ticker=None)
    monkeypatch.setattr(
        orders_router,
        "UserTradingConfigRepository",
        lambda db: MagicMock(get=MagicMock(return_value=None)),
    )
    monkeypatch.setattr(
        orders_router, "yf", MagicMock(Ticker=MagicMock(side_effect=RuntimeError("no yf")))
    )
    orders_router._recalculate_order_quantity(order, 1, SimpleNamespace(), 99)
    assert order.quantity == 1


def test_get_order_statistics(monkeypatch):
    monkeypatch.setattr(
        orders_router,
        "OrdersRepository",
        lambda db: MagicMock(get_order_statistics=MagicMock(return_value={"ok": True})),
    )
    out = orders_router.get_order_statistics(
        current_user=SimpleNamespace(id=5), db=SimpleNamespace()
    )
    assert out == {"ok": True}


class _ListRepoTypeErrorThenLegacy:
    """First list() uses limit/offset and raises TypeError; fallback uses legacy signature."""

    def __init__(self, orders):
        self._orders = list(orders)

    def list(self, user_id, status=None, *args, **kwargs):
        if "limit" in kwargs:
            raise TypeError("legacy signature")
        return [o for o in self._orders if getattr(o, "user_id", None) == user_id]


def test_list_orders_typeerror_fallback_pagination(monkeypatch):
    o = SimpleNamespace(
        id=1,
        user_id=10,
        symbol="X",
        side="buy",
        quantity=1,
        price=1.0,
        status=DbOrderStatus.PENDING,
        placed_at=datetime(2024, 6, 15, 12, 0, 0),
        closed_at=None,
        reason=None,
        trade_mode="paper",
        orig_source="auto",
    )
    monkeypatch.setattr(
        orders_router, "OrdersRepository", lambda db: _ListRepoTypeErrorThenLegacy([o])
    )
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(get_by_user_id=MagicMock(return_value=SimpleNamespace(broker=None))),
    )
    resp = orders_router.list_orders(
        status=None,
        reason=None,
        from_date=None,
        to_date=None,
        page=1,
        page_size=10,
        db=SimpleNamespace(),
        current=SimpleNamespace(id=10),
    )
    assert len(resp.items) == 1


def test_list_orders_serialize_skips_bad_row(monkeypatch):
    good = SimpleNamespace(
        id=1,
        user_id=11,
        symbol="OK",
        side="buy",
        quantity=1,
        price=1.0,
        status=DbOrderStatus.PENDING,
        placed_at=datetime(2024, 6, 1),
        closed_at=None,
        reason=None,
        trade_mode=SimpleNamespace(value="paper"),
        orig_source="manual",
    )
    bad = SimpleNamespace(
        id=2,
        user_id=11,
        symbol="BAD",
        side="buy",
        quantity=1,
        price=1.0,
        status=object(),
        placed_at=datetime(2024, 6, 2),
        closed_at=None,
        reason=None,
        trade_mode=None,
        orig_source="manual",
    )

    class _R:
        def list(self, user_id, status=None, *, limit=50, offset=0):
            return [good, bad], 2

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _R())
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(
            get_by_user_id=MagicMock(return_value=SimpleNamespace(broker="kotak-neo"))
        ),
    )
    resp = orders_router.list_orders(db=SimpleNamespace(), current=SimpleNamespace(id=11))
    assert len(resp.items) == 1
    assert resp.items[0].symbol == "OK"


def test_retry_order_format_datetime_string_paths(monkeypatch):
    order = SimpleNamespace(
        id=20,
        user_id=3,
        symbol="R",
        side="buy",
        quantity=1,
        price=1.0,
        status=DbOrderStatus.FAILED,
        retry_count=0,
        reason="x",
        placed_at="2024-01-01T00:00:00",
        closed_at="2024-01-02T00:00:00",
        orig_source="manual",
        first_failed_at="2024-01-01T01:00:00",
        last_retry_attempt=None,
        last_status_check=None,
    )
    monkeypatch.setattr(
        orders_router,
        "OrdersRepository",
        lambda db: MagicMock(
            get=MagicMock(return_value=order), update=MagicMock(side_effect=lambda o: o)
        ),
    )
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(get_by_user_id=MagicMock(return_value=None)),
    )
    monkeypatch.setattr(orders_router, "_recalculate_order_quantity", lambda *a, **k: None)
    monkeypatch.setattr(orders_router, "ist_now", lambda: datetime(2024, 1, 3, 0, 0, 0))
    r = orders_router.retry_order(order_id=20, db=SimpleNamespace(), current=SimpleNamespace(id=3))
    assert r.created_at == "2024-01-01T00:00:00"
    assert r.first_failed_at == "2024-01-01T01:00:00"


def _patch_sync_common(monkeypatch, tmp_path, *, settings, orders_repo):
    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: orders_repo)
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(get_by_user_id=MagicMock(return_value=settings)),
    )
    env_path = tmp_path / "broker.env"
    env_path.write_text("X=1", encoding="utf-8")
    monkeypatch.setattr(orders_router, "decrypt_broker_credentials", lambda blob: {"k": "v"})
    monkeypatch.setattr(orders_router, "create_temp_env_file", lambda creds: str(env_path))
    monkeypatch.setattr(orders_router, "_is_order_monitoring_active", lambda uid, db: False)

    class _SM:
        def get_or_create_session(self, user_id, env_file, db):
            return object()

    monkeypatch.setattr(orders_router, "get_shared_session_manager", lambda: _SM())

    class _BF:
        @staticmethod
        def create_broker(name, auth):
            b = MagicMock()
            b.connect.return_value = True
            return b

    monkeypatch.setattr(orders_router, "BrokerFactory", _BF)


def test_sync_order_status_paper_single_order_ok(monkeypatch, tmp_path):
    o = SimpleNamespace(
        id=5,
        user_id=9,
        status=DbOrderStatus.PENDING,
        trade_mode=SimpleNamespace(value="paper"),
        broker_order_id="b1",
    )
    repo = MagicMock(
        get=MagicMock(return_value=o),
        list=MagicMock(return_value=([o], 1)),
    )
    settings = SimpleNamespace(trade_mode="paper", broker_creds_encrypted=None)
    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: repo)
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(get_by_user_id=MagicMock(return_value=settings)),
    )
    out = orders_router.sync_order_status(
        order_id=5, db=SimpleNamespace(), current=SimpleNamespace(id=9)
    )
    assert out["synced"] == 1
    assert out["sync_performed"] is False


def test_sync_order_status_paper_single_not_found(monkeypatch):
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(
            get_by_user_id=MagicMock(return_value=SimpleNamespace(trade_mode="paper"))
        ),
    )
    monkeypatch.setattr(
        orders_router,
        "OrdersRepository",
        lambda db: MagicMock(
            get=MagicMock(return_value=None), list=MagicMock(return_value=([], 0))
        ),
    )
    with pytest.raises(HTTPException) as ei:
        orders_router.sync_order_status(
            order_id=99, db=SimpleNamespace(), current=SimpleNamespace(id=1)
        )
    assert ei.value.status_code == 404


def test_sync_order_status_paper_single_wrong_trade_mode(monkeypatch):
    o = SimpleNamespace(
        id=1,
        user_id=1,
        status=DbOrderStatus.PENDING,
        trade_mode=SimpleNamespace(value="broker"),
        broker_order_id="x",
    )
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(
            get_by_user_id=MagicMock(return_value=SimpleNamespace(trade_mode="paper"))
        ),
    )
    monkeypatch.setattr(
        orders_router, "OrdersRepository", lambda db: MagicMock(get=MagicMock(return_value=o))
    )
    with pytest.raises(HTTPException) as ei:
        orders_router.sync_order_status(
            order_id=1, db=SimpleNamespace(), current=SimpleNamespace(id=1)
        )
    assert ei.value.status_code == 400


def test_sync_order_status_trade_mode_parsed_from_repr_string(monkeypatch, tmp_path):
    class _TM:
        def __str__(self):
            # Exercises the `':' in s and "'" in s` branch that extracts the quoted value.
            return "TradeMode: 'broker'"

    settings = SimpleNamespace(trade_mode=_TM(), broker_creds_encrypted=b"enc")
    orders = [
        SimpleNamespace(
            id=1,
            user_id=7,
            status=DbOrderStatus.PENDING,
            trade_mode="broker",
            broker_order_id="neo-1",
            order_id=None,
            price=100.0,
            quantity=2,
        )
    ]

    class _Repo:
        def __init__(self):
            self.updated = []

        def list(self, user_id, status=None, **kwargs):
            return orders, len(orders)

        def get(self, oid):
            return orders[0] if oid == 1 else None

        def mark_executed(self, order, **kwargs):
            self.updated.append("executed")

        def mark_rejected(self, order, reason):
            self.updated.append("rejected")

        def mark_cancelled(self, order, reason):
            self.updated.append("cancelled")

        def update_status_check(self, order):
            self.updated.append("check")

    repo = _Repo()
    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=settings,
        orders_repo=repo,
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {
                "data": [
                    {"nOrdNo": "neo-1", "status": "complete", "prc": 101.0, "fldQty": 2},
                ]
            }

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    out = orders_router.sync_order_status(
        order_id=1, db=SimpleNamespace(), current=SimpleNamespace(id=7)
    )
    assert out["sync_performed"] is True
    assert out["executed"] >= 1
    assert "executed" in repo.updated


def test_sync_order_status_invalid_trade_mode_not_broker(monkeypatch):
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(
            get_by_user_id=MagicMock(
                return_value=SimpleNamespace(
                    trade_mode="something_else", broker_creds_encrypted=b"x"
                )
            )
        ),
    )
    with pytest.raises(HTTPException) as ei:
        orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 400


def test_sync_order_status_broker_missing_creds(monkeypatch):
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(
            get_by_user_id=MagicMock(
                return_value=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=None)
            )
        ),
    )
    with pytest.raises(HTTPException) as ei:
        orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 400


def test_sync_order_status_monitoring_active_short_circuits(monkeypatch):
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(
            get_by_user_id=MagicMock(
                return_value=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"enc")
            )
        ),
    )
    monkeypatch.setattr(orders_router, "_is_order_monitoring_active", lambda uid, db: True)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=1))
    assert out["monitoring_active"] is True
    assert out["sync_performed"] is False


def test_sync_order_status_decrypt_raises(monkeypatch):
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(
            get_by_user_id=MagicMock(
                return_value=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"enc")
            )
        ),
    )
    monkeypatch.setattr(orders_router, "_is_order_monitoring_active", lambda uid, db: False)
    monkeypatch.setattr(
        orders_router, "decrypt_broker_credentials", MagicMock(side_effect=ValueError("bad"))
    )
    with pytest.raises(HTTPException) as ei:
        orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 500


def test_sync_order_status_create_env_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(
            get_by_user_id=MagicMock(
                return_value=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"enc")
            )
        ),
    )
    monkeypatch.setattr(orders_router, "_is_order_monitoring_active", lambda uid, db: False)
    monkeypatch.setattr(orders_router, "decrypt_broker_credentials", lambda x: {})
    monkeypatch.setattr(
        orders_router, "create_temp_env_file", MagicMock(side_effect=OSError("disk"))
    )
    with pytest.raises(HTTPException) as ei:
        orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 500


def test_sync_order_status_session_manager_raises_non_http(monkeypatch, tmp_path):
    settings = SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"enc")
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(get_by_user_id=MagicMock(return_value=settings)),
    )
    monkeypatch.setattr(orders_router, "_is_order_monitoring_active", lambda uid, db: False)
    monkeypatch.setattr(orders_router, "decrypt_broker_credentials", lambda x: {})
    monkeypatch.setattr(orders_router, "create_temp_env_file", lambda c: str(tmp_path / "e.env"))
    (tmp_path / "e.env").write_text("a=b")

    class _SM:
        def get_or_create_session(self, *a, **k):
            raise RuntimeError("session down")

    monkeypatch.setattr(orders_router, "get_shared_session_manager", lambda: _SM())
    with pytest.raises(HTTPException) as ei:
        orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 503


def test_sync_order_status_auth_none(monkeypatch, tmp_path):
    settings = SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"enc")
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(get_by_user_id=MagicMock(return_value=settings)),
    )
    monkeypatch.setattr(orders_router, "_is_order_monitoring_active", lambda uid, db: False)
    monkeypatch.setattr(orders_router, "decrypt_broker_credentials", lambda x: {})
    monkeypatch.setattr(orders_router, "create_temp_env_file", lambda c: str(tmp_path / "e.env"))
    (tmp_path / "e.env").write_text("a=b")

    class _SM:
        def get_or_create_session(self, *a, **k):
            return None

    monkeypatch.setattr(orders_router, "get_shared_session_manager", lambda: _SM())
    with pytest.raises(HTTPException) as ei:
        orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 503


def test_sync_order_status_broker_connect_fails(monkeypatch, tmp_path):
    orders = [
        SimpleNamespace(
            id=1,
            user_id=3,
            status=DbOrderStatus.PENDING,
            broker_order_id="z",
            order_id=None,
            price=1.0,
            quantity=1,
        )
    ]

    class _Repo:
        def list(self, *a, **k):
            return orders, 1

        def get(self, oid):
            return orders[0]

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _BF:
        @staticmethod
        def create_broker(name, auth):
            b = MagicMock()
            b.connect.return_value = False
            return b

    monkeypatch.setattr(orders_router, "BrokerFactory", _BF)
    with pytest.raises(HTTPException) as ei:
        orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=3))
    assert ei.value.status_code == 503


def test_sync_order_status_get_orders_raises(monkeypatch, tmp_path):
    orders = [
        SimpleNamespace(
            id=1,
            user_id=4,
            status=DbOrderStatus.PENDING,
            broker_order_id="z",
            order_id=None,
            price=1.0,
            quantity=1,
        )
    ]

    class _Repo:
        def list(self, *a, **k):
            return orders, 1

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            raise ConnectionError("nope")

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    with pytest.raises(HTTPException) as ei:
        orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=4))
    assert ei.value.status_code == 500


def test_sync_order_status_broker_orders_none_coerced(monkeypatch, tmp_path):
    orders = [
        SimpleNamespace(
            id=1,
            user_id=5,
            status=DbOrderStatus.PENDING,
            broker_order_id="bid",
            order_id=None,
            price=1.0,
            quantity=1,
        )
    ]

    class _Repo:
        def list(self, *a, **k):
            return orders, 1

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return None

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=5))
    assert out["synced"] == 1
    assert out["sync_performed"] is True


def test_sync_order_status_no_broker_id_on_order(monkeypatch, tmp_path):
    orders = [
        SimpleNamespace(
            id=9,
            user_id=6,
            status=DbOrderStatus.PENDING,
            broker_order_id=None,
            order_id=None,
            price=1.0,
            quantity=1,
        )
    ]

    class _Repo:
        def list(self, *a, **k):
            return orders, 1

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {"data": []}

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=6))
    assert any("no broker_order_id" in e for e in out["errors"])


def test_sync_mark_rejected_default_reason_when_reason_extract_fails(monkeypatch, tmp_path):
    o = SimpleNamespace(
        id=1,
        user_id=8,
        status=DbOrderStatus.PENDING,
        broker_order_id="R1",
        order_id=None,
        price=10.0,
        quantity=1,
    )

    class _Repo:
        def list(self, *a, **k):
            return [o], 1

        def mark_rejected(self, order, reason):
            assert "Rejected" in reason or reason == "Rejected by broker"

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {"data": [{"nOrdNo": "R1", "status": "reject"}]}

    class _FE:
        @staticmethod
        def get_order_id(bo):
            return str(bo.get("nOrdNo", ""))

        @staticmethod
        def get_status(bo):
            return "rejected"

        @staticmethod
        def get_rejection_reason(bo):
            raise RuntimeError("no reason")

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    monkeypatch.setattr(orders_router, "OrderFieldExtractor", _FE)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=8))
    assert out["rejected"] == 1


def test_sync_mark_cancelled_default_reason_when_reason_extract_fails(monkeypatch, tmp_path):
    o = SimpleNamespace(
        id=1,
        user_id=8,
        status=DbOrderStatus.PENDING,
        broker_order_id="C1",
        order_id=None,
        price=10.0,
        quantity=1,
    )

    class _Repo:
        def list(self, *a, **k):
            return [o], 1

        def mark_cancelled(self, order, reason):
            assert reason == "Cancelled"

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {"data": [{"nOrdNo": "C1", "status": "cancel"}]}

    class _FE:
        @staticmethod
        def get_order_id(bo):
            return str(bo.get("nOrdNo", ""))

        @staticmethod
        def get_status(bo):
            return "cancelled"

        @staticmethod
        def get_rejection_reason(bo):
            raise RuntimeError("no cancel msg")

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    monkeypatch.setattr(orders_router, "OrderFieldExtractor", _FE)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=8))
    assert out["cancelled"] == 1


def test_sync_pending_updates_status_check(monkeypatch, tmp_path):
    o = SimpleNamespace(
        id=1,
        user_id=8,
        status=DbOrderStatus.PENDING,
        broker_order_id="P1",
        order_id=None,
        price=10.0,
        quantity=1,
    )

    class _Repo:
        def __init__(self):
            self.checks = 0

        def list(self, *a, **k):
            return [o], 1

        def update_status_check(self, order):
            self.checks += 1

    repo = _Repo()
    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=repo,
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {"data": [{"nOrdNo": "P1", "status": "trigger_pending"}]}

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=8))
    assert out["updated"] >= 1
    assert repo.checks == 1


def test_sync_order_status_executed_invalid_price_qty(monkeypatch, tmp_path):
    o = SimpleNamespace(
        id=1,
        user_id=8,
        status=DbOrderStatus.PENDING,
        broker_order_id="E1",
        order_id=None,
        price=5.0,
        quantity=3,
    )

    class _Repo:
        def list(self, *a, **k):
            return [o], 1

        def mark_executed(self, order, execution_price=None, execution_qty=None):
            pass

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {"data": [{"nOrdNo": "E1", "status": "filled", "prc": -1, "fldQty": 0}]}

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=8))
    assert out["executed"] == 1


def test_sync_order_status_mark_executed_raises_recorded(monkeypatch, tmp_path):
    o = SimpleNamespace(
        id=1,
        user_id=8,
        status=DbOrderStatus.PENDING,
        broker_order_id="E2",
        order_id=None,
        price=5.0,
        quantity=3,
    )

    class _Repo:
        def list(self, *a, **k):
            return [o], 1

        def mark_executed(self, *a, **k):
            raise RuntimeError("db")

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {"data": [{"nOrdNo": "E2", "status": "executed", "prc": 9.0, "fldQty": 3}]}

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=8))
    assert any("Failed to mark as executed" in e for e in out["errors"])


class _EvilStr(str):
    """``str`` that raises on ``split`` so sync falls back to ``.lower()`` for trade_mode."""

    def split(self, sep=None, maxsplit=-1):
        if ":" in self and "'" in self:
            raise RuntimeError("forced split failure")
        return str.split(self, sep, maxsplit)

    def lower(self):
        return "broker"


class _TradeModeEvilStr:
    def __str__(self):
        return _EvilStr("Enum: 'x'")


def test_sync_order_status_trade_mode_repr_parse_split_error_falls_back(monkeypatch, tmp_path):
    """Covers ``except`` on repr-style trade_mode parsing (lines ~523--526)."""
    settings = SimpleNamespace(trade_mode=_TradeModeEvilStr(), broker_creds_encrypted=b"enc")
    orders = [
        SimpleNamespace(
            id=1,
            user_id=71,
            status=DbOrderStatus.PENDING,
            trade_mode="broker",
            broker_order_id="neo-71",
            order_id=None,
            price=1.0,
            quantity=1,
        )
    ]

    class _Repo:
        def list(self, user_id, status=None, **kwargs):
            return orders, len(orders)

        def mark_executed(self, *a, **k):
            pass

    _patch_sync_common(monkeypatch, tmp_path, settings=settings, orders_repo=_Repo())

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {"data": [{"nOrdNo": "neo-71", "status": "filled", "prc": 2.0, "fldQty": 1}]}

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=71))
    assert out["sync_performed"] is True


def test_sync_order_status_get_order_id_skips_broken_broker_row(monkeypatch, tmp_path):
    o = SimpleNamespace(
        id=1,
        user_id=81,
        status=DbOrderStatus.PENDING,
        broker_order_id="GOOD",
        order_id=None,
        price=1.0,
        quantity=1,
    )

    class _Repo:
        def list(self, *a, **k):
            return [o], 1

        def mark_executed(self, *a, **k):
            pass

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {
                "data": [
                    {"nOrdNo": "BAD", "status": "filled"},
                    {"nOrdNo": "GOOD", "status": "filled", "prc": 3.0, "fldQty": 1},
                ]
            }

    class _FE:
        @staticmethod
        def get_order_id(bo):
            if bo.get("nOrdNo") == "BAD":
                raise RuntimeError("bad row")
            return str(bo.get("nOrdNo", ""))

        @staticmethod
        def get_status(bo):
            return str(bo.get("status", ""))

        @staticmethod
        def get_price(bo):
            return float(bo.get("prc", 0))

        @staticmethod
        def get_filled_quantity(bo):
            return float(bo.get("fldQty", 0))

        @staticmethod
        def get_quantity(bo):
            return float(bo.get("fldQty", 0))

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    monkeypatch.setattr(orders_router, "OrderFieldExtractor", _FE)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=81))
    assert out["executed"] == 1


def test_sync_order_status_skips_broker_row_with_empty_status(monkeypatch, tmp_path):
    o = SimpleNamespace(
        id=1,
        user_id=82,
        status=DbOrderStatus.PENDING,
        broker_order_id="E",
        order_id=None,
        price=1.0,
        quantity=1,
    )

    class _Repo:
        def list(self, *a, **k):
            return [o], 1

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {"data": [{"nOrdNo": "E", "status": ""}]}

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=82))
    assert out["executed"] == 0
    assert out["updated"] == 0


def test_sync_order_status_executed_invalid_qty_uses_db_quantity(monkeypatch, tmp_path):
    o = SimpleNamespace(
        id=1,
        user_id=83,
        status=DbOrderStatus.PENDING,
        broker_order_id="Q1",
        order_id=None,
        price=5.0,
        quantity=4,
    )

    class _Repo:
        def list(self, *a, **k):
            return [o], 1

        def mark_executed(self, order, execution_price=None, execution_qty=None):
            assert execution_qty == 4

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {"data": [{"nOrdNo": "Q1", "status": "filled", "prc": 9.0, "fldQty": 0}]}

    class _FE:
        @staticmethod
        def get_order_id(bo):
            return str(bo.get("nOrdNo", ""))

        @staticmethod
        def get_status(bo):
            return "filled"

        @staticmethod
        def get_price(bo):
            return 9.0

        @staticmethod
        def get_filled_quantity(bo):
            return -1

        @staticmethod
        def get_quantity(bo):
            return 0.0

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    monkeypatch.setattr(orders_router, "OrderFieldExtractor", _FE)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=83))
    assert out["executed"] == 1


def test_sync_order_status_mark_rejected_outer_error_recorded(monkeypatch, tmp_path):
    o = SimpleNamespace(
        id=1,
        user_id=84,
        status=DbOrderStatus.PENDING,
        broker_order_id="R2",
        order_id=None,
        price=1.0,
        quantity=1,
    )

    class _Repo:
        def list(self, *a, **k):
            return [o], 1

        def mark_rejected(self, *a, **k):
            raise RuntimeError("db down")

    _patch_sync_common(
        monkeypatch,
        tmp_path,
        settings=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e"),
        orders_repo=_Repo(),
    )

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {"data": [{"nOrdNo": "R2", "status": "reject", "rejRsn": "x"}]}

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    out = orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=84))
    assert any("Error updating order" in e for e in out["errors"])


def test_sync_order_status_temp_env_cleanup_unlink_failure_logged(monkeypatch, tmp_path):
    o = SimpleNamespace(
        id=1,
        user_id=85,
        status=DbOrderStatus.PENDING,
        broker_order_id="U1",
        order_id=None,
        price=1.0,
        quantity=1,
    )

    class _Repo:
        def list(self, *a, **k):
            return [o], 1

        def mark_executed(self, *a, **k):
            pass

    env_path = tmp_path / "broker.env"
    env_path.write_text("X=1", encoding="utf-8")

    class _RaisingPath:
        def __init__(self, p):
            self._p = p

        def unlink(self, missing_ok=True):
            raise OSError("no unlink")

    debug_msgs: list[str] = []
    monkeypatch.setattr(
        orders_router.logger, "debug", lambda msg, *a, **k: debug_msgs.append(str(msg))
    )

    monkeypatch.setattr(orders_router, "OrdersRepository", lambda db: _Repo())
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(
            get_by_user_id=MagicMock(
                return_value=SimpleNamespace(trade_mode="broker", broker_creds_encrypted=b"e")
            )
        ),
    )
    monkeypatch.setattr(orders_router, "decrypt_broker_credentials", lambda blob: {"k": "v"})
    monkeypatch.setattr(orders_router, "create_temp_env_file", lambda creds: str(env_path))
    monkeypatch.setattr(orders_router, "_is_order_monitoring_active", lambda uid, db: False)

    class _SM:
        def get_or_create_session(self, user_id, env_file, db):
            return object()

    monkeypatch.setattr(orders_router, "get_shared_session_manager", lambda: _SM())

    class _BF:
        @staticmethod
        def create_broker(name, auth):
            b = MagicMock()
            b.connect.return_value = True
            return b

    monkeypatch.setattr(orders_router, "BrokerFactory", _BF)

    class _KO:
        def __init__(self, auth):
            pass

        def get_orders(self):
            return {"data": [{"nOrdNo": "U1", "status": "filled", "prc": 2.0, "fldQty": 1}]}

    monkeypatch.setattr(orders_router, "KotakNeoOrders", _KO)
    monkeypatch.setattr(orders_router, "Path", _RaisingPath)
    orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=85))
    assert any("Failed to cleanup temp env file" in m for m in debug_msgs)


def test_sync_order_status_settings_repo_raises_500(monkeypatch):
    monkeypatch.setattr(
        orders_router,
        "SettingsRepository",
        lambda db: MagicMock(get_by_user_id=MagicMock(side_effect=RuntimeError("db"))),
    )
    with pytest.raises(HTTPException) as ei:
        orders_router.sync_order_status(db=SimpleNamespace(), current=SimpleNamespace(id=1))
    assert ei.value.status_code == 500
