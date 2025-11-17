import os
import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

os.environ["DB_URL"] = os.getenv("DB_URL", "sqlite:///./data/test_api_pat.db")

from server.app.main import app  # noqa: E402
from src.infrastructure.db.models import PnlDaily  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402


def _auth_client() -> tuple[TestClient, dict]:
    client = TestClient(app)
    # Use unique email to avoid conflicts
    unique_email = f"pat_tester_{uuid.uuid4().hex[:8]}@example.com"
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": unique_email, "password": "secret123"},
    )
    assert s.status_code == 200, s.text
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


def test_pnl_daily_and_summary():
    client, headers = _auth_client()

    # seed some pnl rows
    with SessionLocal() as db:
        today = date.today()
        db.add(
            PnlDaily(
                user_id=1,
                date=today - timedelta(days=2),
                realized_pnl=100,
                unrealized_pnl=0,
                fees=5,
            )
        )
        db.add(
            PnlDaily(
                user_id=1,
                date=today - timedelta(days=1),
                realized_pnl=-50,
                unrealized_pnl=0,
                fees=0,
            )
        )
        db.commit()

    # daily
    r = client.get("/api/v1/user/pnl/daily", headers=headers)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)

    # summary
    s = client.get("/api/v1/user/pnl/summary", headers=headers)
    assert s.status_code == 200
    sm = s.json()
    assert "totalPnl" in sm and "daysGreen" in sm and "daysRed" in sm


def test_activity_and_targets():
    client, headers = _auth_client()

    # activity list (empty ok)
    a = client.get("/api/v1/user/activity/", headers=headers)
    assert a.status_code == 200

    # targets list (empty ok for now)
    t = client.get("/api/v1/user/targets/", headers=headers)
    assert t.status_code == 200
    assert isinstance(t.json(), list)
