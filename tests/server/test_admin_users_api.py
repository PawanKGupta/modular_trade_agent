# ruff: noqa: PLC0415
"""Admin users API tests — in-memory DB aligned with tests/conftest.py."""

from __future__ import annotations

import os
import sys

from fastapi.testclient import TestClient


def _make_client() -> TestClient:
    """In-memory DB with explicit schema reset (same engine for API + SessionLocal)."""
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


def _signup(client: TestClient, email: str, password: str = "secret123") -> dict:
    s = client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    assert s.status_code == 200, s.text
    return {"Authorization": f"Bearer {s.json()['access_token']}"}


def _promote_to_admin(email: str) -> None:
    from src.infrastructure.db.models import UserRole, Users
    from src.infrastructure.db.session import SessionLocal

    with SessionLocal() as db:
        user = db.query(Users).filter(Users.email == email).first()
        assert user is not None, f"signup user not found in DB: {email}"
        user.role = UserRole.ADMIN
        user.is_active = True
        db.commit()


def test_admin_create_and_update_user():
    client = _make_client()
    admin_headers = _signup(client, "admin_update@example.com")
    _promote_to_admin("admin_update@example.com")

    r = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={"email": "target@example.com", "password": "secret123", "name": "Target"},
    )
    assert r.status_code == 200, r.text
    user_id = r.json()["id"]

    u = client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=admin_headers,
        json={"role": "admin", "is_active": True},
    )
    assert u.status_code == 200, u.text
    assert u.json()["role"] == "admin"
    assert u.json()["is_active"] is True

    lst = client.get("/api/v1/admin/users", headers=admin_headers)
    assert lst.status_code == 200
    emails = [x["email"] for x in lst.json()]
    assert "admin_update@example.com" in emails and "target@example.com" in emails

    found = client.get(
        "/api/v1/admin/users",
        headers=admin_headers,
        params={"q": "target@", "limit": 20},
    )
    assert found.status_code == 200
    found_emails = [x["email"] for x in found.json()]
    assert "target@example.com" in found_emails
    assert "admin_update@example.com" not in found_emails
