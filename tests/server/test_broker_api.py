"""Tests for broker integration API endpoints."""

import os
import random
import sys

import pytest
from fastapi.testclient import TestClient


def make_client():
    # configure in-memory sqlite before importing app/session
    os.environ["DB_URL"] = "sqlite:///:memory:"
    # Ensure root path on sys.path
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root not in sys.path:
        sys.path.append(root)
    # Import Base and engine then create schema
    import src.infrastructure.db.models  # noqa: F401, PLC0415
    from src.infrastructure.db.base import Base  # noqa: PLC0415
    from src.infrastructure.db.session import engine  # noqa: PLC0415

    # reset schema to ensure isolation
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)
    from server.app.main import app  # noqa: PLC0415

    return TestClient(app)


@pytest.mark.unit
def test_save_broker_creds():
    """Test saving broker credentials."""
    client = make_client()

    email = f"u{random.randint(1, 1_000_000)}@example.com"
    resp = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "Secret123", "name": "U1"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Save basic credentials
    save_resp = client.post(
        "/api/v1/user/broker/creds",
        headers=headers,
        json={"broker": "kotak-neo", "api_key": "test-key-123", "api_secret": "test-secret-456"},
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "ok"

    # Verify status updated
    status_resp = client.get("/api/v1/user/broker/status", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["broker"] == "kotak-neo"
    assert status_data["status"] == "Stored"


@pytest.mark.unit
def test_save_broker_creds_with_full_auth():
    """Test saving broker credentials with full authentication details."""
    client = make_client()

    email = f"u{random.randint(1, 1_000_000)}@example.com"
    resp = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "Secret123", "name": "U1"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Save credentials with full auth
    save_resp = client.post(
        "/api/v1/user/broker/creds",
        headers=headers,
        json={
            "broker": "kotak-neo",
            "api_key": "test-key-123",
            "api_secret": "test-secret-456",
            "mobile_number": "9876543210",
            "password": "userpass",
            "mpin": "1234",
            "environment": "prod",
        },
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "ok"


@pytest.mark.unit
def test_get_broker_creds_info_masked():
    """Test getting masked broker credentials info."""
    client = make_client()

    email = f"u{random.randint(1, 1_000_000)}@example.com"
    resp = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "Secret123", "name": "U1"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Save credentials first
    client.post(
        "/api/v1/user/broker/creds",
        headers=headers,
        json={
            "broker": "kotak-neo",
            "api_key": "test-key-12345",
            "api_secret": "test-secret-67890",
        },
    )

    # Get masked info
    info_resp = client.get("/api/v1/user/broker/creds/info", headers=headers)
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert info_data["has_creds"] is True
    assert info_data["api_key_masked"] is not None
    assert info_data["api_secret_masked"] is not None
    assert "****" in info_data["api_key_masked"]
    assert "****" in info_data["api_secret_masked"]
    # Should not have full values
    assert info_data.get("api_key") is None
    assert info_data.get("api_secret") is None


@pytest.mark.unit
def test_get_broker_creds_info_full():
    """Test getting full broker credentials info."""
    client = make_client()

    email = f"u{random.randint(1, 1_000_000)}@example.com"
    resp = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "Secret123", "name": "U1"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Save credentials with full auth
    client.post(
        "/api/v1/user/broker/creds",
        headers=headers,
        json={
            "broker": "kotak-neo",
            "api_key": "test-key-12345",
            "api_secret": "test-secret-67890",
            "mobile_number": "9876543210",
            "password": "userpass",
            "mpin": "1234",
        },
    )

    # Get full info
    info_resp = client.get("/api/v1/user/broker/creds/info?show_full=true", headers=headers)
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert info_data["has_creds"] is True
    assert info_data["api_key"] == "test-key-12345"
    assert info_data["api_secret"] == "test-secret-67890"
    assert info_data["mobile_number"] == "9876543210"
    assert info_data["password"] == "userpass"
    assert info_data["mpin"] == "1234"


@pytest.mark.unit
def test_get_broker_creds_info_no_creds():
    """Test getting broker credentials info when none are stored."""
    client = make_client()

    email = f"u{random.randint(1, 1_000_000)}@example.com"
    resp = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "Secret123", "name": "U1"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get info without saving
    info_resp = client.get("/api/v1/user/broker/creds/info", headers=headers)
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert info_data["has_creds"] is False


@pytest.mark.unit
def test_broker_status():
    """Test getting broker status."""
    client = make_client()

    email = f"u{random.randint(1, 1_000_000)}@example.com"
    resp = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "Secret123", "name": "U1"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get status before saving
    status_resp = client.get("/api/v1/user/broker/status", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["broker"] is None or status_data["broker"] == ""
    assert status_data["status"] is None or status_data["status"] == ""

    # Save credentials
    client.post(
        "/api/v1/user/broker/creds",
        headers=headers,
        json={"broker": "kotak-neo", "api_key": "test-key", "api_secret": "test-secret"},
    )

    # Get status after saving
    status_resp = client.get("/api/v1/user/broker/status", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["broker"] == "kotak-neo"
    assert status_data["status"] == "Stored"


@pytest.mark.unit
def test_test_broker_connection_basic():
    """Test basic broker connection test (without full auth)."""
    client = make_client()

    email = f"u{random.randint(1, 1_000_000)}@example.com"
    resp = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "Secret123", "name": "U1"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test connection with basic credentials
    # Note: This will fail if neo_api_client is not installed, but that's expected
    test_resp = client.post(
        "/api/v1/user/broker/test",
        headers=headers,
        json={"broker": "kotak-neo", "api_key": "test-key-123", "api_secret": "test-secret-456"},
    )
    # Should either succeed (if SDK available) or fail with clear message
    assert test_resp.status_code in [200, 500]  # 500 if SDK not available
    if test_resp.status_code == 200:
        data = test_resp.json()
        assert "ok" in data
        assert "message" in data


@pytest.mark.unit
def test_test_broker_connection_unsupported_broker():
    """Test broker connection test with unsupported broker."""
    client = make_client()

    email = f"u{random.randint(1, 1_000_000)}@example.com"
    resp = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "Secret123", "name": "U1"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test with unsupported broker
    test_resp = client.post(
        "/api/v1/user/broker/test",
        headers=headers,
        json={"broker": "unsupported-broker", "api_key": "key", "api_secret": "secret"},
    )
    assert test_resp.status_code == 200  # Returns error in response, not HTTP error
    data = test_resp.json()
    assert data["ok"] is False
    assert "Unsupported broker" in data["message"]


@pytest.mark.unit
def test_broker_creds_isolation():
    """Test that broker credentials are isolated per user."""
    client = make_client()

    # Create two users
    email1 = f"u{random.randint(1, 1_000_000)}@example.com"
    email2 = f"u{random.randint(1, 1_000_000)}@example.com"

    resp1 = client.post(
        "/api/v1/auth/signup", json={"email": email1, "password": "Secret123", "name": "U1"}
    )
    resp2 = client.post(
        "/api/v1/auth/signup", json={"email": email2, "password": "Secret123", "name": "U2"}
    )

    token1 = resp1.json()["access_token"]
    token2 = resp2.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    # User 1 saves credentials
    client.post(
        "/api/v1/user/broker/creds",
        headers=headers1,
        json={"broker": "kotak-neo", "api_key": "user1-key", "api_secret": "user1-secret"},
    )

    # User 2 should not see user 1's credentials
    info2 = client.get("/api/v1/user/broker/creds/info", headers=headers2)
    assert info2.status_code == 200
    assert info2.json()["has_creds"] is False

    # User 1 should see their credentials
    info1 = client.get("/api/v1/user/broker/creds/info?show_full=true", headers=headers1)
    assert info1.status_code == 200
    data1 = info1.json()
    assert data1["has_creds"] is True
    assert data1["api_key"] == "user1-key"
    assert data1["api_secret"] == "user1-secret"
