"""
Tests for Phase 11: Order Statistics API Endpoint

Tests GET /api/v1/user/orders/statistics endpoint.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Users
from src.infrastructure.persistence.orders_repository import OrdersRepository
from server.app.main import app

client = TestClient(app)


@pytest.fixture
def mock_user(db_session):
    """Create a test user"""
    from src.infrastructure.db.models import Users
    from server.app.core.security import hash_password

    user = Users(
        email="test@example.com",
        password_hash=hash_password("password123"),
        username="testuser",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(mock_user):
    """Get authentication headers"""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": mock_user.email, "password": "password123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestOrderStatisticsEndpointPhase11:
    """Test Phase 11 order statistics endpoint"""

    def test_get_order_statistics_success(self, db_session, mock_user, auth_headers):
        """Test getting order statistics successfully"""
        with patch("server.app.routers.orders.OrdersRepository") as mock_repo_class:
            mock_repo = Mock(spec=OrdersRepository)
            mock_repo_class.return_value = mock_repo

            # Mock statistics
            mock_stats = {
                "total_orders": 50,
                "status_distribution": {
                    "amo": 5,
                    "ongoing": 10,
                    "closed": 20,
                    "failed": 3,
                    "retry_pending": 2,
                },
                "pending_execution": 8,
                "failed_orders": 3,
                "retry_pending": 2,
                "rejected_orders": 1,
                "cancelled_orders": 4,
                "executed_orders": 10,
                "closed_orders": 20,
                "amo_orders": 5,
            }

            mock_repo.get_order_statistics.return_value = mock_stats

            response = client.get("/api/v1/user/orders/statistics", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()

            # Verify statistics
            assert data["total_orders"] == 50
            assert data["status_distribution"]["amo"] == 5
            assert data["status_distribution"]["ongoing"] == 10
            assert data["status_distribution"]["closed"] == 20
            assert data["status_distribution"]["failed"] == 3
            assert data["status_distribution"]["retry_pending"] == 2
            assert data["pending_execution"] == 8
            assert data["failed_orders"] == 3
            assert data["retry_pending"] == 2
            assert data["executed_orders"] == 10
            assert data["closed_orders"] == 20
            assert data["amo_orders"] == 5

            # Verify repository was called with correct user_id
            mock_repo.get_order_statistics.assert_called_once_with(mock_user.id)

    def test_get_order_statistics_unauthorized(self):
        """Test getting order statistics without authentication"""
        response = client.get("/api/v1/user/orders/statistics")

        assert response.status_code == 401

    def test_get_order_statistics_empty_stats(self, db_session, mock_user, auth_headers):
        """Test getting order statistics when user has no orders"""
        with patch("server.app.routers.orders.OrdersRepository") as mock_repo_class:
            mock_repo = Mock(spec=OrdersRepository)
            mock_repo_class.return_value = mock_repo

            # Mock empty statistics
            mock_stats = {
                "total_orders": 0,
                "status_distribution": {},
                "pending_execution": 0,
                "failed_orders": 0,
                "retry_pending": 0,
                "rejected_orders": 0,
                "cancelled_orders": 0,
                "executed_orders": 0,
                "closed_orders": 0,
                "amo_orders": 0,
            }

            mock_repo.get_order_statistics.return_value = mock_stats

            response = client.get("/api/v1/user/orders/statistics", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()

            # Verify statistics are all zeros
            assert data["total_orders"] == 0
            assert data["status_distribution"] == {}
            assert data["pending_execution"] == 0
            assert data["failed_orders"] == 0
            assert data["retry_pending"] == 0

