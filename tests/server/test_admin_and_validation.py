# ruff: noqa: PLC0415
import os
import random
import sys

import pytest
from fastapi.testclient import TestClient


def make_client():
    os.environ["DB_URL"] = "sqlite:///:memory:"
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root not in sys.path:
        sys.path.append(root)
    import src.infrastructure.db.models  # noqa
    from src.infrastructure.db.base import Base
    from src.infrastructure.db.session import engine

    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)
    from server.app.main import app

    return TestClient(app)


@pytest.mark.unit
def test_admin_create_and_update_and_forbidden_for_non_admin():
    client = make_client()
    # create admin directly via repo and get token
    from server.app.core.security import create_jwt_token
    from src.infrastructure.db.models import UserRole
    from src.infrastructure.db.session import SessionLocal
    from src.infrastructure.persistence.user_repository import UserRepository

    db = SessionLocal()
    repo = UserRepository(db)
    admin = repo.create_user(
        f"adm{random.randint(1, 1_000_000)}@example.com", "Admin123", role=UserRole.ADMIN
    )
    db.close()
    admin_token = create_jwt_token(str(admin.id), extra={"uid": admin.id, "roles": ["admin"]})
    ah = {"Authorization": f"Bearer {admin_token}"}
    # admin: create user
    email_new = f"user{random.randint(1, 1_000_000)}@example.com"
    resp = client.post(
        "/api/v1/admin/users",
        headers=ah,
        json={"email": email_new, "password": "Secret123", "role": "user"},
    )
    assert resp.status_code == 200
    new_user = resp.json()
    assert new_user["email"] == email_new
    # admin: update user -> deactivate
    uid = new_user["id"]
    up = client.patch(f"/api/v1/admin/users/{uid}", headers=ah, json={"is_active": False})
    assert up.status_code == 200
    assert up.json()["is_active"] is False
    # non-admin forbidden
    # sign up normal user
    normal_signup = client.post(
        "/api/v1/auth/signup",
        json={"email": f"n{random.randint(1, 1_000_000)}@example.com", "password": "Secret123"},
    )
    ntok = normal_signup.json()["access_token"]
    nh = {"Authorization": f"Bearer {ntok}"}
    for path, method in [("/api/v1/admin/users", "GET"), ("/api/v1/admin/users", "POST")]:
        r = (
            client.request(method, path, headers=nh, json={"email": "x@y.com", "password": "x"})
            if method == "POST"
            else client.request(method, path, headers=nh)
        )
        assert r.status_code == 403


@pytest.mark.unit
def test_auth_guards_and_validation_errors():
    client = make_client()
    # Missing token on protected endpoints -> 401
    for path in ["/api/v1/user/settings", "/api/v1/signals/buying-zone"]:
        r = client.get(path)
        assert r.status_code == 401
    # Invalid signup payload -> 422
    bad = client.post("/api/v1/auth/signup", json={"email": "not-an-email", "password": "123"})
    assert bad.status_code == 422
    # Valid signup
    ok = client.post(
        "/api/v1/auth/signup",
        json={"email": f"ok{random.randint(1, 1_000_000)}@example.com", "password": "Secret123"},
    )
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    # Invalid settings payload -> 422
    inv = client.put("/api/v1/user/settings", headers=h, json={"trade_mode": "invalid-mode"})
    assert inv.status_code == 422
