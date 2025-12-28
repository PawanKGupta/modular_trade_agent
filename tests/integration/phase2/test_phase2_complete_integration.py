"""Integration tests for Phase 2 complete flow"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from server.app.core.security import create_jwt_token
from src.infrastructure.db.models import (
    PnlDaily,
    Targets,
    TradeMode,
    UserRole,
    Users,
)
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.pnl_repository import PnlRepository


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


class TestPhase2CompleteIntegration:
    """Test Phase 2 features work together"""

    def test_pnl_and_targets_integration(
        self, client: TestClient, test_user, db_session, auth_headers
    ):
        """Test that P&L and Targets APIs work together"""
        session = db_session
        pnl_repo = PnlRepository(session)

        # Create P&L data
        today = date.today()
        pnl_record = PnlDaily(
            user_id=test_user.id,
            date=today,
            realized_pnl=100.0,
            unrealized_pnl=50.0,
            fees=5.0,
        )
        pnl_repo.upsert(pnl_record)

        # Create target
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

        # Test P&L endpoint
        pnl_response = client.get("/api/v1/user/pnl/daily", headers=auth_headers)
        assert pnl_response.status_code == 200
        pnl_data = pnl_response.json()
        assert len(pnl_data) >= 1

        # Test Targets endpoint
        targets_response = client.get("/api/v1/user/targets", headers=auth_headers)
        assert targets_response.status_code == 200
        targets_data = targets_response.json()
        assert len(targets_data) >= 1

    def test_pnl_date_range_filtering(
        self, client: TestClient, test_user, db_session, auth_headers
    ):
        """Test P&L date range filtering works correctly"""
        session = db_session
        pnl_repo = PnlRepository(session)

        # Create P&L records for different dates
        today = date.today()
        for i in range(10):
            pnl_date = today - timedelta(days=i)
            pnl_record = PnlDaily(
                user_id=test_user.id,
                date=pnl_date,
                realized_pnl=100.0,
                unrealized_pnl=50.0,
                fees=5.0,
            )
            pnl_repo.upsert(pnl_record)

        # Test with date range
        start_date = today - timedelta(days=5)
        end_date = today - timedelta(days=2)

        response = client.get(
            f"/api/v1/user/pnl/daily?start={start_date}&end={end_date}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Should return 4 days (start, end, and 2 days in between)
        assert len(data) == 4

    def test_targets_user_isolation(self, client: TestClient, test_user, db_session, auth_headers):
        """Test that targets are properly isolated per user"""
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
        target1 = Targets(
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
        session.add(target1)

        # Create target for other_user
        target2 = Targets(
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
        session.add(target2)
        session.commit()

        # Test that test_user only sees their own targets
        response = client.get("/api/v1/user/targets", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "RELIANCE-EQ"
