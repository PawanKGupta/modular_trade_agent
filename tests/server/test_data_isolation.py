# ruff: noqa: PLC0415
import os
import sys
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient


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
    s = client.post("/api/v1/auth/signup", json={"email": email, "password": "secret123"})
    assert s.status_code == 200, s.text
    token = s.json()["access_token"]
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
