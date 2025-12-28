"""Unit tests for Targets API (Phase 2.5)"""

import pytest
from fastapi.testclient import TestClient

from server.app.core.security import create_jwt_token
from src.infrastructure.db.models import Targets, TradeMode, UserRole, Users
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def test_user(db_session):
    """Get test user from db_session"""

    # db_session is just the session, not a tuple
    # Create a test user if one doesn't exist
    user = db_session.query(Users).first()
    if not user:
        user = Users(
            email="test@example.com",
            name="Test User",
            password_hash="dummy_hash",
            role=UserRole.USER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers for test user"""
    token = create_jwt_token(
        str(test_user.id), extra={"uid": test_user.id, "roles": [test_user.role.value]}
    )
    return {"Authorization": f"Bearer {token}"}


class TestTargetsAPI:
    """Test Targets API endpoints"""

    def test_list_targets_returns_active_targets(
        self, client: TestClient, test_user, db_session, auth_headers
    ):
        """Test that list targets returns active targets"""

        # Create active target
        target = Targets(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            target_price=2750.0,
            entry_price=2500.0,
            current_price=2600.0,
            quantity=10,
            distance_to_target=5.77,  # (2750 - 2600) / 2600 * 100
            distance_to_target_absolute=150.0,
            target_type="ema9",
            is_active=True,
            trade_mode=TradeMode.PAPER,
            created_at=ist_now(),
            updated_at=ist_now(),
        )
        db_session.add(target)
        db_session.commit()

        response = client.get(
            "/api/v1/user/targets",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "RELIANCE-EQ"
        assert data[0]["target_price"] == 2750.0
        assert data[0]["entry_price"] == 2500.0
        assert data[0]["current_price"] == 2600.0
        assert data[0]["quantity"] == 10
        assert data[0]["distance_to_target"] == 5.77

    def test_list_targets_excludes_inactive_targets(
        self, client: TestClient, test_user, db_session, auth_headers
    ):
        """Test that list targets excludes inactive targets"""

        # Create active target
        active_target = Targets(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            target_price=2750.0,
            entry_price=2500.0,
            current_price=2600.0,
            quantity=10,
            distance_to_target=5.77,
            distance_to_target_absolute=150.0,
            target_type="ema9",
            is_active=True,
            trade_mode=TradeMode.PAPER,
            created_at=ist_now(),
            updated_at=ist_now(),
        )
        db_session.add(active_target)

        # Create inactive target
        inactive_target = Targets(
            user_id=test_user.id,
            symbol="TCS-EQ",
            target_price=3000.0,
            entry_price=2800.0,
            current_price=3000.0,
            quantity=5,
            distance_to_target=0.0,
            distance_to_target_absolute=0.0,
            target_type="ema9",
            is_active=False,
            trade_mode=TradeMode.PAPER,
            achieved_at=ist_now(),
            created_at=ist_now(),
            updated_at=ist_now(),
        )
        db_session.add(inactive_target)
        db_session.commit()

        response = client.get(
            "/api/v1/user/targets",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "RELIANCE-EQ"
        assert data[0]["is_active"] is True

    def test_list_targets_user_isolation(
        self, client: TestClient, test_user, db_session, auth_headers
    ):
        """Test that users can only see their own targets"""
        session = db_session

        # Create another user
        other_user = Users(
            email="other@example.com",
            name="Other User",
            password_hash="dummy_hash",
            role=UserRole.USER,
            is_active=True,
        )
        session.add(other_user)
        session.commit()
        session.refresh(other_user)

        # Create target for test_user
        target = Targets(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            target_price=2750.0,
            entry_price=2500.0,
            current_price=2600.0,
            quantity=10,
            distance_to_target=5.77,
            distance_to_target_absolute=150.0,
            target_type="ema9",
            is_active=True,
            trade_mode=TradeMode.PAPER,
            created_at=ist_now(),
            updated_at=ist_now(),
        )
        session.add(target)

        # Create target for other_user
        other_target = Targets(
            user_id=other_user.id,
            symbol="TCS-EQ",
            target_price=3000.0,
            entry_price=2800.0,
            current_price=2900.0,
            quantity=5,
            distance_to_target=3.45,
            distance_to_target_absolute=100.0,
            target_type="ema9",
            is_active=True,
            trade_mode=TradeMode.PAPER,
            created_at=ist_now(),
            updated_at=ist_now(),
        )
        session.add(other_target)
        session.commit()

        response = client.get(
            "/api/v1/user/targets",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "RELIANCE-EQ"
        assert data[0]["user_id"] != other_user.id if "user_id" in data[0] else True

    def test_list_targets_returns_correct_fields(
        self, client: TestClient, test_user, db_session, auth_headers
    ):
        """Test that list targets returns all required fields"""
        session = db_session

        target = Targets(
            user_id=test_user.id,
            symbol="RELIANCE-EQ",
            target_price=2750.0,
            entry_price=2500.0,
            current_price=2600.0,
            quantity=10,
            distance_to_target=5.77,
            distance_to_target_absolute=150.0,
            target_type="ema9",
            is_active=True,
            trade_mode=TradeMode.PAPER,
            created_at=ist_now(),
            updated_at=ist_now(),
        )
        session.add(target)
        session.commit()

        response = client.get(
            "/api/v1/user/targets",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        target_data = data[0]

        # Check all required fields are present
        required_fields = [
            "id",
            "symbol",
            "target_price",
            "entry_price",
            "current_price",
            "quantity",
            "distance_to_target",
            "distance_to_target_absolute",
            "target_type",
            "is_active",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in target_data, f"Missing field: {field}"
