from server.app.core.security import create_access_token
from src.infrastructure.db.models import UserRole
from src.infrastructure.persistence.user_repository import UserRepository


def test_signup_and_login_flow(client):
    # Signup
    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": "t1@example.com", "password": "Secret123", "name": "T1"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    assert token

    # Me
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    me = resp.json()
    assert me["email"] == "t1@example.com"
    assert me["roles"] == ["user"]

    # Login
    resp = client.post(
        "/api/v1/auth/login", json={"email": "t1@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_admin_users_requires_admin(client, db_session):
    # Create admin directly in DB and mint token
    u = UserRepository(db_session).create_user(
        email="admin@example.com", password="Secret123", role=UserRole.ADMIN
    )
    admin_token = create_access_token(str(u.id), extra={"uid": u.id, "roles": [u.role.value]})

    # Access admin list
    resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
