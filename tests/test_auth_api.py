from server.app.core.security import create_jwt_token
from src.infrastructure.db.models import UserRole
from src.infrastructure.persistence.user_repository import UserRepository
from tests.support.auth_flow import signup_and_verify, verify_user_email
from tests.support.test_users import create_verified_user


def test_signup_verify_and_login_flow(client, db_session):
    email = "t1@example.com"
    password = "Secret123!"

    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "name": "T1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "message" in body
    assert "access_token" not in body

    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 403
    assert "verify your email" in resp.json()["detail"].lower()

    tokens = verify_user_email(client, db_session, email)
    token = tokens["access_token"]
    assert token

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    me = resp.json()
    assert me["email"] == email
    assert me["roles"] == ["user"]
    assert me["email_verified"] is True

    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_signup_and_verify_returns_tokens(client, db_session):
    tokens = signup_and_verify(client, db_session, "t2@example.com", "Secret123!", "T2")
    assert tokens["access_token"]
    assert tokens.get("refresh_token")


def test_admin_users_requires_admin(client, db_session):
    repo = UserRepository(db_session)
    u = create_verified_user(
        repo,
        email="admin-users-test@example.com",
        password="Secret123!",
        role=UserRole.ADMIN,
    )
    admin_token = create_jwt_token(str(u.id), extra={"uid": u.id, "roles": [u.role.value]})

    resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
