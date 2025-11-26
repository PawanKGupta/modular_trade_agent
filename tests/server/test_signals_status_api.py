"""
Tests for signals API with status filtering and rejection
"""

import os
from datetime import timedelta

os.environ["DB_URL"] = "sqlite:///:memory:"

from fastapi import status  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from server.app.main import app  # noqa: E402
from src.infrastructure.db.models import Signals, SignalStatus  # noqa: E402
from src.infrastructure.db.session import SessionLocal  # noqa: E402
from src.infrastructure.db.timezone_utils import ist_now  # noqa: E402


def _create_authenticated_client():
    """Helper to create authenticated test client"""
    import uuid

    client = TestClient(app)

    # Signup with unique email
    unique_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": unique_email, "password": "testpass123", "name": "Test User"},
    )
    assert response.status_code == 200, f"Signup failed: {response.json()}"

    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    return client, headers


def _create_sample_signals():
    """Create sample signals with different statuses"""
    with SessionLocal() as db:
        # Clear existing signals first
        db.query(Signals).delete()
        db.commit()

        now = ist_now()

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

        db.add_all(signals)
        db.commit()

        return [s.symbol for s in signals]


class TestBuyingZoneStatusFilter:
    def test_default_returns_only_active_signals(self):
        """Default behavior: return only ACTIVE signals"""
        client, headers = _create_authenticated_client()
        _create_sample_signals()

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

    def test_filter_by_expired_status(self):
        """Should return only EXPIRED signals when status_filter='expired'"""
        client, headers = _create_authenticated_client()
        _create_sample_signals()

        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "expired"}
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["symbol"] == "EXPIRED1"
        assert data[0]["status"] == "expired"

    def test_filter_by_traded_status(self):
        """Should return only TRADED signals when status_filter='traded'"""
        client, headers = _create_authenticated_client()
        _create_sample_signals()

        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "traded"}
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["symbol"] == "TRADED1"
        assert data[0]["status"] == "traded"

    def test_filter_by_rejected_status(self):
        """Should return only REJECTED signals when status_filter='rejected'"""
        client, headers = _create_authenticated_client()
        _create_sample_signals()

        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "rejected"}
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["symbol"] == "REJECTED1"
        assert data[0]["status"] == "rejected"

    def test_filter_all_returns_all_signals(self):
        """Should return all signals when status_filter='all'"""
        client, headers = _create_authenticated_client()
        _create_sample_signals()

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

    def test_status_field_included_in_response(self):
        """Response should include status field"""
        client, headers = _create_authenticated_client()
        _create_sample_signals()

        response = client.get("/api/v1/signals/buying-zone", headers=headers)

        assert response.status_code == 200
        data = response.json()

        for item in data:
            assert "status" in item
            assert item["status"] in ["active", "expired", "traded", "rejected"]


class TestRejectSignalEndpoint:
    def test_reject_active_signal(self):
        """Should successfully reject an active signal"""
        client, headers = _create_authenticated_client()
        _create_sample_signals()

        response = client.patch("/api/v1/signals/signals/ACTIVE1/reject", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "ACTIVE1"
        assert data["status"] == "rejected"

        # Verify in database
        with SessionLocal() as db:
            signal = db.query(Signals).filter(Signals.symbol == "ACTIVE1").first()
            assert signal.status == SignalStatus.REJECTED

    def test_cannot_reject_expired_signal(self):
        """Should return 404 when trying to reject an expired signal"""
        client, headers = _create_authenticated_client()
        _create_sample_signals()

        response = client.patch("/api/v1/signals/signals/EXPIRED1/reject", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_reject_nonexistent_signal(self):
        """Should return 404 for nonexistent symbol"""
        client, headers = _create_authenticated_client()

        response = client.patch("/api/v1/signals/signals/NONEXISTENT/reject", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_reject_requires_authentication(self):
        """Should require authentication"""
        client = TestClient(app)

        response = client.patch("/api/v1/signals/signals/ACTIVE1/reject")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestSignalStatusInBuyingZoneWorkflow:
    """Integration tests for complete signal status workflow"""

    def test_complete_workflow_active_to_traded(self):
        """Test: Signal created as active, gets traded, shows in traded filter"""
        client, headers = _create_authenticated_client()

        # Create active signal
        with SessionLocal() as db:
            # Clear existing signals
            db.query(Signals).delete()
            db.commit()

            signal = Signals(
                symbol="WORKFLOW1", status=SignalStatus.ACTIVE, ts=ist_now(), rsi10=25.0
            )
            db.add(signal)
            db.commit()

        # 1. Verify shows in active filter
        response = client.get(
            "/api/v1/signals/buying-zone", headers=headers, params={"status_filter": "active"}
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["symbol"] == "WORKFLOW1"

        # 2. Mark as traded (simulating order placement)
        with SessionLocal() as db:
            from src.infrastructure.persistence.signals_repository import SignalsRepository

            repo = SignalsRepository(db)
            repo.mark_as_traded("WORKFLOW1")

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

    def test_complete_workflow_active_to_rejected(self):
        """Test: Signal created as active, user rejects it, shows in rejected filter"""
        client, headers = _create_authenticated_client()

        # Create active signal
        with SessionLocal() as db:
            # Clear existing signals
            db.query(Signals).delete()
            db.commit()

            signal = Signals(
                symbol="WORKFLOW2", status=SignalStatus.ACTIVE, ts=ist_now(), rsi10=25.0
            )
            db.add(signal)
            db.commit()

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
