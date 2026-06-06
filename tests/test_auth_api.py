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


def test_signup_accepts_optional_mobile(client, db_session):
    email = "mobile-signup@example.com"
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "Secret123!",
            "name": "Mobile User",
            "mobile_number": "9876543210",
        },
    )
    assert resp.status_code == 200, resp.text
    user = UserRepository(db_session).get_by_email(email)
    assert user is not None
    assert user.mobile_number == "9876543210"


def test_profile_update_mobile(client, db_session):
    tokens = signup_and_verify(client, db_session, "profile@example.com", "Secret123!", "Profile User")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = client.patch(
        "/api/v1/auth/profile",
        headers=headers,
        json={"email": "profile@example.com", "mobile_number": "9123456789"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mobile_number"] == "9123456789"
    assert body["verification_required"] is False

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["mobile_number"] == "9123456789"


def test_profile_email_change_requires_password(client, db_session):
    tokens = signup_and_verify(client, db_session, "email@example.com", "Secret123!", "Email User")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = client.patch(
        "/api/v1/auth/profile",
        headers=headers,
        json={"email": "newemail@example.com"},
    )
    assert resp.status_code == 400
    assert "password" in resp.json()["detail"].lower()

    resp = client.patch(
        "/api/v1/auth/profile",
        headers=headers,
        json={
            "email": "newemail@example.com",
            "current_password": "Secret123!",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["verification_required"] is True
