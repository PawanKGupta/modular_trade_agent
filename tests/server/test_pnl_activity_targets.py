import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

from server.app.main import app
from src.infrastructure.db.models import PnlDaily, Users
from src.infrastructure.db.session import SessionLocal
from tests.support.auth_flow import signup_and_verify_payload


def test_pnl_daily_and_summary():
    """PnL API returns seeded daily rows and summary for the authenticated user."""
    client = TestClient(app)
    unique_email = f"pat_tester_{uuid.uuid4().hex[:8]}@example.com"
    tokens = signup_and_verify_payload(
        client, None, {"email": unique_email, "password": "Secret123!"}
    )
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    with SessionLocal() as db:
        user = db.query(Users).filter(Users.email == unique_email).one()
        today = date.today()
        db.add(
            PnlDaily(
                user_id=user.id,
                date=today - timedelta(days=2),
                realized_pnl=100,
                unrealized_pnl=0,
                fees=5,
            )
        )
        db.add(
            PnlDaily(
                user_id=user.id,
                date=today - timedelta(days=1),
                realized_pnl=-50,
                unrealized_pnl=0,
                fees=0,
            )
        )
        db.commit()

    r = client.get("/api/v1/user/pnl/daily", headers=headers)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    assert len(rows) >= 2

    s = client.get("/api/v1/user/pnl/summary", headers=headers)
    assert s.status_code == 200
    sm = s.json()
    assert "totalPnl" in sm and "daysGreen" in sm and "daysRed" in sm


def test_targets():
    client = TestClient(app)
    unique_email = f"pat_targets_{uuid.uuid4().hex[:8]}@example.com"
    tokens = signup_and_verify_payload(
        client, None, {"email": unique_email, "password": "Secret123!"}
    )
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    t = client.get("/api/v1/user/targets/", headers=headers)
    assert t.status_code == 200
    assert isinstance(t.json(), list)
