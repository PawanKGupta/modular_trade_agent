import os

import pytest
from fastapi.testclient import TestClient

os.environ["DB_URL"] = os.getenv("DB_URL", "sqlite:///./data/test_api_orders.db")

from server.app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_orders_list_requires_auth(client: TestClient):
    r = client.get("/api/v1/user/orders")
    assert r.status_code in (401, 403)


def test_orders_list_with_auth(client: TestClient):
    # signup
    s = client.post(
        "/api/v1/auth/signup",
        json={"email": "orders_tester@example.com", "password": "secret123"},
    )
    assert s.status_code == 200, s.text
    token = s.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # initially empty
    r = client.get("/api/v1/user/orders", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # Filter by status param (should still work and return list, possibly empty)
    r2 = client.get("/api/v1/user/orders?status=amo", headers=headers)
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)
