import os
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

os.environ["DB_URL"] = os.getenv("DB_URL", "sqlite:///./data/test_api_isolation.db")

from server.app.main import app  # noqa: E402
from src.infrastructure.db.models import Activity, Orders, OrderStatus, PnlDaily  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402


def _signup(email: str) -> tuple[TestClient, dict, int]:
    client = TestClient(app)
    s = client.post("/api/v1/auth/signup", json={"email": email, "password": "secret123"})
    assert s.status_code == 200, s.text
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    user_id = me.json()["id"]
    return client, headers, user_id


def test_orders_pnl_activity_are_isolated_by_user_id():
    # create two users
    client, headers_a, user_a = _signup("iso_a@example.com")
    _, headers_b, _user_b = _signup("iso_b@example.com")

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
        db.add(
            Activity(
                user_id=user_a,
                type="info",
                ref_id=None,
                details_json={"detail": "seed for isolation test"},
                ts=datetime.utcnow(),
            )
        )
        db.commit()

    # user B should not see user A data
    r_orders_b = client.get("/api/v1/user/orders/?status=pending", headers=headers_b)  # AMO merged into PENDING
    assert r_orders_b.status_code == 200
    assert r_orders_b.json() == []  # no leakage

    r_pnl_b = client.get("/api/v1/user/pnl/daily", headers=headers_b)
    assert r_pnl_b.status_code == 200
    assert isinstance(r_pnl_b.json(), list)
    assert len(r_pnl_b.json()) == 0

    r_act_b = client.get("/api/v1/user/activity/", headers=headers_b)
    assert r_act_b.status_code == 200
    assert isinstance(r_act_b.json(), list)
    assert len(r_act_b.json()) == 0
