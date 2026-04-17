"""
Tests for signals API with status filtering and rejection
"""

import base64
import json
import os
import uuid
from datetime import datetime, timedelta

import pytest
from jose import jwt
from sqlalchemy import text

os.environ["DB_URL"] = "sqlite:///:memory:"

from fastapi import status  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from server.app.main import app  # noqa: E402
from src.infrastructure.db.models import Signals, SignalStatus, UserSignalStatus  # noqa: E402
from src.infrastructure.db.timezone_utils import IST  # noqa: E402
from src.infrastructure.persistence.signals_repository import SignalsRepository  # noqa: E402

# Fixed IST timestamp so mark_time_expired_signals() never treats test rows as past market expiry
# (CI clocks / timezones must not shrink the buying-zone active list or reject flow).
_STABLE_SIGNAL_TS = datetime(2030, 6, 15, 10, 30, tzinfo=IST)


@pytest.fixture(autouse=True)
def _signals_status_api_uses_shared_engine():
    """
    This module relies on the `client`/`db_session` fixtures from tests/conftest.py
    so API requests and direct DB seeding use the same SQLAlchemy session/engine.
    """
    yield


def _create_authenticated_client(client: TestClient):
    """Helper to create authenticated test client"""
    # Signup with unique email
    unique_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": unique_email, "password": "testpass123", "name": "Test User"},
    )
    assert response.status_code == 200, f"Signup failed: {response.json()}"

    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Decode token to get user_id (python-jose requires key but we bypass verification)
    try:
        # Try to decode without verification (python-jose style)
        decoded = jwt.decode(token, key="", options={"verify_signature": False})
    except Exception:
        # Fallback: manually parse JWT payload (base64 decode middle part)
        payload = token.split(".")[1]
        # Add padding if needed
        payload += "=" * (4 - len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))

    user_id = decoded.get("uid")

    return client, headers, user_id


def _create_sample_signals(db_session):
    """Create sample signals with different statuses"""
    # Clear per-user overrides first, then base signals.
    db_session.execute(text("DELETE FROM user_signal_status"))
    db_session.execute(text("DELETE FROM signals"))
    db_session.commit()

    now = _STABLE_SIGNAL_TS

    signals = [
        Signals(symbol="ACTIVE1", status=SignalStatus.ACTIVE, ts=now, rsi10=25.0),
        Signals(symbol="ACTIVE2", status=SignalStatus.ACTIVE, ts=now, rsi10=28.0),
        Signals(
            symbol="EXPIRED1",
            status=SignalStatus.EXPIRED,
            ts=now - timedelta(days=1),
            rsi10=30.0,
        ),
        Signals(
            symbol="TRADED1",
            status=SignalStatus.TRADED,
            ts=now - timedelta(hours=2),
            rsi10=27.0,
        ),
        Signals(symbol="REJECTED1", status=SignalStatus.REJECTED, ts=now, rsi10=32.0),
    ]

    db_session.add_all(signals)
    db_session.commit()

    count = db_session.query(Signals).count()
    assert count == 5, f"Expected 5 signals but got {count}"

    return [s.symbol for s in signals]


class TestBuyingZoneStatusFilter:
    def test_default_returns_only_active_signals(self, client, db_session):
        """Default behavior: return only ACTIVE signals"""
        client, headers, user_id = _create_authenticated_client(client)
        _create_sample_signals(db_session)

        response = client.get("/api/v1/signals/buying-zone", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Default status_filter='active' should return only ACTIVE signals
        assert len(data) == 2
        symbols = {item["symbol"] for item in data}
        assert "ACTIVE1" in symbols
        assert "ACTIVE2" in symbols
        assert "EXPIRED1" not in symbols
        assert "TRADED1" not in symbols
        assert "REJECTED1" not in symbols

    def test_filter_by_expired_status(self, client, db_session):
        """Should return only EXPIRED signals when status_filter='expired'"""
        client, headers, user_id = _create_authenticated_client(client)
        _create_sample_signals(db_session)

        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "expired"}
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["symbol"] == "EXPIRED1"
        assert data[0]["status"] == "expired"

    def test_filter_by_traded_status(self, client, db_session):
        """Should return only TRADED signals when status_filter='traded'"""
        client, headers, user_id = _create_authenticated_client(client)
        _create_sample_signals(db_session)

        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "traded"}
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["symbol"] == "TRADED1"
        assert data[0]["status"] == "traded"

    def test_filter_by_rejected_status(self, client, db_session):
        """Should return only REJECTED signals when status_filter='rejected'"""
        client, headers, user_id = _create_authenticated_client(client)
        _create_sample_signals(db_session)

        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "rejected"}
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["symbol"] == "REJECTED1"
        assert data[0]["status"] == "rejected"

    def test_filter_all_returns_all_signals(self, client, db_session):
        """Should return all signals when status_filter='all'"""
        client, headers, user_id = _create_authenticated_client(client)
        _create_sample_signals(db_session)

        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "all"}
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 5  # All signals
        symbols = {item["symbol"] for item in data}
        assert "ACTIVE1" in symbols
        assert "EXPIRED1" in symbols
        assert "TRADED1" in symbols
        assert "REJECTED1" in symbols

    def test_status_field_included_in_response(self, client, db_session):
        """Response should include status field"""
        client, headers, user_id = _create_authenticated_client(client)
        _create_sample_signals(db_session)

        response = client.get("/api/v1/signals/buying-zone", headers=headers)

        assert response.status_code == 200
        data = response.json()

        for item in data:
            assert "status" in item
            assert item["status"] in ["active", "expired", "traded", "rejected"]


class TestRejectSignalEndpoint:
    def test_reject_active_signal(self, client, db_session):
        """Should successfully reject an active signal (per-user)"""
        client, headers, user_id = _create_authenticated_client(client)
        _create_sample_signals(db_session)

        response = client.patch("/api/v1/signals/signals/ACTIVE1/reject", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "ACTIVE1"
        assert data["status"] == "rejected"

        # Verify in database - base signal should still be ACTIVE (per-user status)
        signal = db_session.query(Signals).filter(Signals.symbol == "ACTIVE1").first()
        assert signal is not None
        # Base signal remains ACTIVE (per-user status is in UserSignalStatus table)
        assert signal.status == SignalStatus.ACTIVE

        # Verify user-specific status was created
        user_status = (
            db_session.query(UserSignalStatus)
            .filter(UserSignalStatus.signal_id == signal.id, UserSignalStatus.user_id == user_id)
            .first()
        )
        assert user_status is not None
        assert user_status.status == SignalStatus.REJECTED

    def test_can_reject_expired_signal(self, client, db_session):
        """Should allow rejecting expired signal (creates per-user status)"""
        client, headers, user_id = _create_authenticated_client(client)
        _create_sample_signals(db_session)

        response = client.patch("/api/v1/signals/signals/EXPIRED1/reject", headers=headers)

        # Now succeeds (per-user status allows rejecting expired signals)
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "EXPIRED1"
        assert data["status"] == "rejected"

    def test_cannot_reject_nonexistent_signal(self, client):
        """Should return 404 for nonexistent symbol"""
        client, headers, user_id = _create_authenticated_client(client)

        response = client.patch("/api/v1/signals/signals/NONEXISTENT/reject", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_reject_requires_authentication(self):
        """Should require authentication"""
        client = TestClient(app)

        response = client.patch("/api/v1/signals/signals/ACTIVE1/reject")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestSignalStatusInBuyingZoneWorkflow:
    """Integration tests for complete signal status workflow"""

    def test_complete_workflow_active_to_traded(self, client, db_session):
        """Test: Signal created as active, gets traded, shows in traded filter"""
        client, headers, user_id = _create_authenticated_client(client)

        # Create active signal
        db_session.execute(text("DELETE FROM user_signal_status"))
        db_session.execute(text("DELETE FROM signals"))
        db_session.commit()

        signal = Signals(
            symbol="WORKFLOW1", status=SignalStatus.ACTIVE, ts=_STABLE_SIGNAL_TS, rsi10=25.0
        )
        db_session.add(signal)
        db_session.commit()

        # 1. Verify shows in active filter
        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "active"}
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["symbol"] == "WORKFLOW1"

        # 2. Mark as traded (simulating order placement)
        repo = SignalsRepository(db_session, user_id=user_id)
        repo.mark_as_traded("WORKFLOW1", user_id=user_id)

        # 3. Verify no longer shows in active filter
        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "active"}
        )
        assert response.status_code == 200
        assert len(response.json()) == 0

        # 4. Verify shows in traded filter
        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "traded"}
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["symbol"] == "WORKFLOW1"
        assert response.json()[0]["status"] == "traded"

    def test_complete_workflow_active_to_rejected(self, client, db_session):
        """Test: Signal created as active, user rejects it, shows in rejected filter"""
        client, headers, user_id = _create_authenticated_client(client)

        # Create active signal
        db_session.execute(text("DELETE FROM user_signal_status"))
        db_session.execute(text("DELETE FROM signals"))
        db_session.commit()

        signal = Signals(
            symbol="WORKFLOW2", status=SignalStatus.ACTIVE, ts=_STABLE_SIGNAL_TS, rsi10=25.0
        )
        db_session.add(signal)
        db_session.commit()

        # 1. User rejects signal via API
        response = client.patch("/api/v1/signals/signals/WORKFLOW2/reject", headers=headers)
        assert response.status_code == 200

        # 2. Verify no longer shows in active filter
        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "active"}
        )
        assert response.status_code == 200
        assert len(response.json()) == 0

        # 3. Verify shows in rejected filter
        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "rejected"}
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["symbol"] == "WORKFLOW2"
        assert response.json()[0]["status"] == "rejected"
