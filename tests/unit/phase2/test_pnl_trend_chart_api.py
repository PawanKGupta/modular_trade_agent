"""Unit tests for P&L Trend Chart API (Phase 2.1)"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from server.app.core.security import create_jwt_token
from src.infrastructure.db.models import PnlDaily, UserRole, Users
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


class TestPnlTrendChartAPI:
    """Test P&L Trend Chart API endpoints"""

    def test_daily_pnl_with_date_range(
        self, client: TestClient, test_user, db_session, auth_headers
    ):
        """Test daily P&L endpoint with date range"""
        session = db_session
        pnl_repo = PnlRepository(session)

        # Create P&L records for last 10 days
        today = date.today()
        for i in range(10):
            pnl_date = today - timedelta(days=i)
            pnl_record = PnlDaily(
                user_id=test_user.id,
                date=pnl_date,
                realized_pnl=100.0 + i * 10,
                unrealized_pnl=50.0 + i * 5,
                fees=5.0,
            )
            pnl_repo.upsert(pnl_record)

        start_date = today - timedelta(days=7)
        end_date = today

        response = client.get(
            f"/api/v1/user/pnl/daily?start={start_date}&end={end_date}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 8  # 7 days + today
        assert all("date" in item for item in data)
        assert all("pnl" in item for item in data)

    def test_daily_pnl_defaults_to_last_30_days(
        self, client: TestClient, test_user, db_session, auth_headers
    ):
        """Test that daily P&L defaults to last 30 days"""
        session = db_session
        pnl_repo = PnlRepository(session)

        # Create P&L records for last 35 days
        today = date.today()
        for i in range(35):
            pnl_date = today - timedelta(days=i)
            pnl_record = PnlDaily(
                user_id=test_user.id,
                date=pnl_date,
                realized_pnl=100.0,
                unrealized_pnl=50.0,
                fees=5.0,
            )
            pnl_repo.upsert(pnl_record)

        response = client.get("/api/v1/user/pnl/daily", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Should return 31 days (30 days + today, inclusive)
        assert len(data) == 31
        # Verify dates are in range
        dates = [item["date"] for item in data]
        assert min(dates) <= (today - timedelta(days=30)).isoformat()
        assert max(dates) >= today.isoformat()

    def test_daily_pnl_calculates_total_correctly(
        self, client: TestClient, test_user, db_session, auth_headers
    ):
        """Test that daily P&L calculates total correctly"""
        session = db_session
        pnl_repo = PnlRepository(session)

        today = date.today()
        pnl_record = PnlDaily(
            user_id=test_user.id,
            date=today,
            realized_pnl=100.0,
            unrealized_pnl=50.0,
            fees=5.0,
        )
        pnl_repo.upsert(pnl_record)

        response = client.get(
            f"/api/v1/user/pnl/daily?start={today}&end={today}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        # pnl = realized + unrealized - fees = 100 + 50 - 5 = 145
        assert data[0]["pnl"] == 145.0

    def test_daily_pnl_sorted_by_date(
        self, client: TestClient, test_user, db_session, auth_headers
    ):
        """Test that daily P&L is sorted by date"""
        session = db_session
        pnl_repo = PnlRepository(session)

        today = date.today()
        # Create records in reverse order
        for i in range(5):
            pnl_date = today - timedelta(days=4 - i)
            pnl_record = PnlDaily(
                user_id=test_user.id,
                date=pnl_date,
                realized_pnl=100.0,
                unrealized_pnl=50.0,
                fees=5.0,
            )
            pnl_repo.upsert(pnl_record)

        response = client.get(
            f"/api/v1/user/pnl/daily?start={today - timedelta(days=4)}&end={today}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        # Verify dates are in ascending order
        dates = [item["date"] for item in data]
        assert dates == sorted(dates)

    def test_daily_pnl_user_isolation(
        self, client: TestClient, test_user, db_session, auth_headers
    ):
        """Test that users can only see their own P&L data"""
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

        pnl_repo = PnlRepository(session)
        today = date.today()

        # Create P&L for test_user
        pnl_record = PnlDaily(
            user_id=test_user.id,
            date=today,
            realized_pnl=100.0,
            unrealized_pnl=50.0,
            fees=5.0,
        )
        pnl_repo.upsert(pnl_record)

        # Create P&L for other_user
        other_pnl = PnlDaily(
            user_id=other_user.id,
            date=today,
            realized_pnl=999.0,
            unrealized_pnl=999.0,
            fees=0.0,
        )
        pnl_repo.upsert(other_pnl)

        response = client.get(
            f"/api/v1/user/pnl/daily?start={today}&end={today}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["pnl"] == 145.0  # test_user's P&L, not other_user's
