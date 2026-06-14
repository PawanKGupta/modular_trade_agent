# ruff: noqa: PLC0415
import os
import sys
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from tests.support.auth_flow import signup_and_verify_payload


def _make_client() -> TestClient:
    """In-memory DB with explicit schema reset (includes orders, pnl_daily)."""
    os.environ["DB_URL"] = "sqlite:///:memory:"
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root not in sys.path:
        sys.path.append(root)

    import src.infrastructure.db.models  # noqa: F401
    from src.infrastructure.db.base import Base
    from src.infrastructure.db.session import engine

    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)

    from server.app.main import app

    return TestClient(app)


def _signup(client: TestClient, email: str) -> tuple[dict, int]:
    _auth_tokens = signup_and_verify_payload(client, None, {"email": email, "password": "Secret123!"})
    token = _auth_tokens["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    user_id = me.json()["id"]
    return headers, user_id


@pytest.mark.unit
def test_orders_and_pnl_are_isolated_by_user_id():
    client = _make_client()

    # create two users
    headers_a, user_a = _signup(client, "iso_a@example.com")
    headers_b, _user_b = _signup(client, "iso_b@example.com")

    from src.infrastructure.db.models import Orders, OrderStatus, PnlDaily
    from src.infrastructure.db.session import SessionLocal

    # seed data for user A only
    with SessionLocal() as db:
        db.add(
            Orders(
                user_id=user_a,
                symbol="INFY",
                side="buy",
                order_type="limit",
                quantity=10,
                price=1500.0,
                status=OrderStatus.PENDING,  # AMO merged into PENDING
                placed_at=datetime.utcnow(),
            )
        )
        db.add(
            PnlDaily(
                user_id=user_a,
                date=date.today() - timedelta(days=1),
                realized_pnl=25.0,
                unrealized_pnl=0.0,
                fees=1.0,
            )
        )
        db.commit()

    # user B should not see user A data
    r_orders_b = client.get(
        "/api/v1/user/orders/?status=pending", headers=headers_b
    )  # AMO merged into PENDING
    assert r_orders_b.status_code == 200
    payload = r_orders_b.json()
    assert isinstance(payload, dict)
    assert payload.get("items") == []  # no leakage

    r_pnl_b = client.get("/api/v1/user/pnl/daily", headers=headers_b)
    assert r_pnl_b.status_code == 200
    assert isinstance(r_pnl_b.json(), list)
    assert len(r_pnl_b.json()) == 0


@pytest.mark.unit
def test_notifications_are_isolated_by_user_id():
    client = _make_client()
    headers_a, user_a = _signup(client, "iso_notif_a@example.com")
    headers_b, _user_b = _signup(client, "iso_notif_b@example.com")

    from src.infrastructure.db.models import Notification
    from src.infrastructure.db.session import SessionLocal

    with SessionLocal() as db:
        db.add(
            Notification(
                user_id=user_a,
                title="User A only",
                message="private",
                type="system",
                level="info",
            )
        )
        db.commit()

    r_b = client.get("/api/v1/user/notifications", headers=headers_b)
    assert r_b.status_code == 200
    items = r_b.json().get("items", r_b.json()) if isinstance(r_b.json(), dict) else r_b.json()
    if isinstance(items, list):
        assert all(n.get("title") != "User A only" for n in items)


@pytest.mark.unit
def test_trading_config_isolated_by_user():
    client = _make_client()
    headers_a, _user_a = _signup(client, "iso_cfg_a@example.com")
    headers_b, _user_b = _signup(client, "iso_cfg_b@example.com")

    set_a = client.put(
        "/api/v1/user/trading-config",
        headers=headers_a,
        json={"max_positions": 3},
    )
    assert set_a.status_code in (200, 201, 422)

    get_b = client.get("/api/v1/user/trading-config", headers=headers_b)
    assert get_b.status_code == 200
    if set_a.status_code in (200, 201):
        cfg_b = get_b.json()
        assert cfg_b.get("max_positions") != 3 or cfg_b.get("max_positions") is None

