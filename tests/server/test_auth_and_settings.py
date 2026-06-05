# ruff: noqa: PLC0415
import os
import sys

import pytest
from fastapi.testclient import TestClient

from tests.support.auth_flow import signup_and_verify


def make_client():
    # configure in-memory sqlite before importing app/session
    os.environ["DB_URL"] = "sqlite:///:memory:"
    # Ensure root path on sys.path
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root not in sys.path:
        sys.path.append(root)
    # Import Base and engine then create schema
    import src.infrastructure.db.models  # noqa: F401
    from src.infrastructure.db.base import Base
    from src.infrastructure.db.session import engine

    # reset schema to ensure isolation
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)
    from server.app.main import app

    return TestClient(app)


@pytest.mark.unit
def test_signup_verify_login_me_and_settings():
    client = make_client()
    import random

    email = f"u{random.randint(1, 1_000_000)}@example.com"
    password = "Secret123!"
    signup = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": password, "name": "U1"}
    )
    assert signup.status_code == 200, signup.text
    assert "message" in signup.json()
    assert "access_token" not in signup.json()

    blocked = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert blocked.status_code == 403

    tokens = signup_and_verify(client, None, email, password, "U1")
    token = tokens["access_token"]
    assert tokens["refresh_token"]
    headers = {"Authorization": f"Bearer {token}"}

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 200
    refreshed = refresh.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"]

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    data = me.json()
    assert data["email"] == email
    assert data["email_verified"] is True
    assert "user" in data["roles"]

    s = client.get("/api/v1/user/settings", headers=headers)
    assert s.status_code == 200
    assert s.json()["trade_mode"] == "paper"

    upd = client.put(
        "/api/v1/user/settings",
        headers=headers,
        json={"trade_mode": "broker", "broker": "kotak-neo"},
    )
    assert upd.status_code == 200
    out = upd.json()
    assert out["trade_mode"] == "broker"
    assert out["broker"] == "kotak-neo"


@pytest.mark.unit
def test_admin_endpoints_and_constraints():
    client = make_client()
    import random

    client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"n{random.randint(1, 1_000_000)}@example.com",
            "password": "Secret123!",
            "name": "Normal User",
        },
    )
    from server.app.core.security import create_jwt_token
    from src.infrastructure.db.models import UserRole
    from src.infrastructure.db.session import SessionLocal
    from src.infrastructure.persistence.user_repository import UserRepository

    db = SessionLocal()
    repo = UserRepository(db)
    a1 = repo.create_user(
        f"a{random.randint(1, 1_000_000)}@example.com",
        "Admin123!",
        name="Admin One",
        role=UserRole.ADMIN,
    )
    a2 = repo.create_user(
        f"a{random.randint(1, 1_000_000)}@example.com",
        "Admin123!",
        name="Admin Two",
        role=UserRole.ADMIN,
    )
    repo.mark_email_verified(a1)
    repo.mark_email_verified(a2)
    a1_id, a2_id = a1.id, a2.id
    db.close()
    # token for a1
    admin_token = create_jwt_token(str(a1_id), extra={"uid": a1_id, "roles": ["admin"]})
    ah = {"Authorization": f"Bearer {admin_token}"}
    # list users
    lst = client.get("/api/v1/admin/users", headers=ah)
    assert lst.status_code == 200
    items = lst.json()
    assert any(u["id"] == a1_id for u in items)
    # delete a2 ok
    del_ok = client.delete(f"/api/v1/admin/users/{a2_id}", headers=ah)
    assert del_ok.status_code == 200
    # attempt delete last admin should fail
    del_last = client.delete(f"/api/v1/admin/users/{a1_id}", headers=ah)
    assert del_last.status_code == 400
