import os

from fastapi.testclient import TestClient

os.environ["DB_URL"] = os.getenv("DB_URL", "sqlite:///./data/test_api_orders.db")

from server.app.main import app  # noqa: E402


def test_health_and_basic_endpoints():
    client = TestClient(app)

    # health
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

    # signup + auth
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "coverage_smoke@example.com", "password": "secret123"},
    )
    assert s.status_code == 200, s.text
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # me
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200

    # settings get/put
    g = client.get("/api/v1/user/settings", headers=headers)
    assert g.status_code == 200
    u = client.put(
        "/api/v1/user/settings",
        json={"trade_mode": "paper", "broker": None},
        headers=headers,
    )
    assert u.status_code == 200

    # signals list (buying zone)
    sig = client.get("/api/v1/signals/buying-zone", headers=headers)
    assert sig.status_code == 200
