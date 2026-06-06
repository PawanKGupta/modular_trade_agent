"""Helpers for integration tests with hard email verification."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from server.app.core.auth_tokens import auth_sent_at, generate_token, hash_token
from src.infrastructure.db.models import Users

DEFAULT_TEST_USER_NAME = "Test User"


def _signup_payload(email: str, password: str, name: str | None = None) -> dict[str, Any]:
    return {
        "email": email,
        "password": password,
        "name": (name or DEFAULT_TEST_USER_NAME).strip() or DEFAULT_TEST_USER_NAME,
    }


def _resolve_db(db: Session | None) -> tuple[Session, bool]:
    if db is not None:
        return db, False
    from src.infrastructure.db.session import SessionLocal

    return SessionLocal(), True


def verify_user_email(client: TestClient, db: Session | None, email: str) -> dict[str, Any]:
    """Complete email verification and return token response JSON."""
    session, should_close = _resolve_db(db)
    try:
        user = session.query(Users).filter(Users.email == email).one()
        raw_token = generate_token()
        user.email_verification_token_hash = hash_token(raw_token)
        user.email_verification_sent_at = auth_sent_at()
        session.commit()
        response = client.post("/api/v1/auth/verify-email", json={"token": raw_token})
        assert response.status_code == 200, response.text
        return response.json()
    finally:
        if should_close:
            session.close()


def signup_and_verify(
    client: TestClient,
    db: Session | None,
    email: str,
    password: str,
    name: str | None = None,
) -> dict[str, Any]:
    """Register via signup, verify email, return token response JSON."""
    payload = _signup_payload(email, password, name)
    signup = client.post("/api/v1/auth/signup", json=payload)
    assert signup.status_code == 200, signup.text
    assert "message" in signup.json()
    return verify_user_email(client, db, email)


def signup_and_verify_payload(
    client: TestClient, db: Session | None, payload: dict[str, Any]
) -> dict[str, Any]:
    """Signup with a JSON payload dict, verify email, return tokens."""
    body = dict(payload)
    if not str(body.get("name", "")).strip():
        body["name"] = DEFAULT_TEST_USER_NAME
    signup = client.post("/api/v1/auth/signup", json=body)
    assert signup.status_code == 200, signup.text
    return verify_user_email(client, db, str(payload["email"]))


def auth_headers_from_signup(
    client: TestClient,
    db: Session | None,
    email: str,
    password: str,
    name: str | None = None,
) -> dict[str, str]:
    tokens = signup_and_verify(client, db, email, password, name)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def get_access_token(
    client: TestClient,
    db: Session | None,
    email: str,
    password: str,
    name: str | None = None,
) -> str:
    """Signup (or re-signup) + verify, or login when already verified."""
    payload = _signup_payload(email, password, name)
    signup = client.post("/api/v1/auth/signup", json=payload)
    if signup.status_code == 200 and "message" in signup.json():
        return verify_user_email(client, db, email)["access_token"]
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if login.status_code == 200:
        return login.json()["access_token"]
    if login.status_code == 403:
        return verify_user_email(client, db, email)["access_token"]
    raise AssertionError(
        f"Could not authenticate {email}: signup={signup.status_code} login={login.status_code} {login.text}"
    )
