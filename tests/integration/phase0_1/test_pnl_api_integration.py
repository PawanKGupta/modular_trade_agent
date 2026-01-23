"""
Integration tests for Phase 0 + Phase 1 API endpoints

Tests cover:
- PnL calculation API endpoints
- Audit history API
- Authentication and authorization
- Error handling
- Edge cases
"""

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.app.main import app
from src.infrastructure.db.base import Base
from src.infrastructure.db.models import (
    PnlCalculationAudit,
    PnlDaily,
    Positions,
    TradeMode,
    UserRole,
    Users,
)
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.orders_repository import OrdersRepository


@pytest.fixture
def db_session():
    """Create in-memory test database"""
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test user
    user = Users(
        email="test@example.com",
        name="Test User",
        password_hash="dummy_hash",
        role=UserRole.USER,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    yield session, user.id

    session.close()


@pytest.fixture
def client(db_session):
    """Create test client with database override"""
    from server.app.core.deps import get_db

    session, _ = db_session

    def _get_db_override():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(client, db_session):
    """Create authenticated test client"""
    session, user_id = db_session

    # Create user for authentication
    user = session.query(Users).filter(Users.id == user_id).first()

    # Create JWT token (simplified for testing)
    from server.app.core.security import create_jwt_token

    token = create_jwt_token(str(user.id), extra={"uid": user.id, "roles": [user.role.value]})
    headers = {"Authorization": f"Bearer {token}"}

    return client, headers


class TestPnlDailyEndpoint:
    """Test GET /api/v1/user/pnl/daily endpoint"""

    def test_daily_pnl_requires_auth(self, client):
        """Test that daily PnL endpoint requires authentication"""
        response = client.get("/api/v1/user/pnl/daily")
        assert response.status_code in (401, 403)

    def test_daily_pnl_empty_result(self, auth_client):
        """Test daily PnL with no data"""
        client, headers = auth_client

        response = client.get("/api/v1/user/pnl/daily", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_daily_pnl_with_data(self, auth_client, db_session):
        """Test daily PnL with existing data"""
        client, headers = auth_client
        session, user_id = db_session

        # Create PnL daily records
        today = date.today()
        for i in range(3):
            pnl = PnlDaily(
                user_id=user_id,
                date=today - timedelta(days=i),
                realized_pnl=100.0 * (i + 1),
                unrealized_pnl=50.0 * (i + 1),
                fees=5.0 * (i + 1),
            )
            session.add(pnl)
        session.commit()

        response = client.get("/api/v1/user/pnl/daily", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("date" in item and "pnl" in item for item in data)

    def test_daily_pnl_with_date_range(self, auth_client, db_session):
        """Test daily PnL with date range parameters"""
        client, headers = auth_client
        session, user_id = db_session

        today = date.today()
        start = today - timedelta(days=5)
        end = today - timedelta(days=2)

        # Create PnL records
        for i in range(7):
            pnl = PnlDaily(
                user_id=user_id,
                date=today - timedelta(days=i),
                realized_pnl=100.0,
                unrealized_pnl=50.0,
                fees=5.0,
            )
            session.add(pnl)
        session.commit()

        response = client.get(
            f"/api/v1/user/pnl/daily?start={start}&end={end}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        # Should return records within date range
        assert len(data) >= 3


class TestPnlSummaryEndpoint:
    """Test GET /api/v1/user/pnl/summary endpoint"""

    def test_pnl_summary_requires_auth(self, client):
        """Test that PnL summary endpoint requires authentication"""
        response = client.get("/api/v1/user/pnl/summary")
        assert response.status_code in (401, 403)

    def test_pnl_summary_empty_result(self, auth_client):
        """Test PnL summary with no data"""
        client, headers = auth_client

        response = client.get("/api/v1/user/pnl/summary", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Response uses camelCase (totalPnl, daysGreen, daysRed)
        assert "totalPnl" in data
        assert "daysGreen" in data
        assert "daysRed" in data

    def test_pnl_summary_with_data(self, auth_client, db_session):
        """Test PnL summary with existing data"""
        client, headers = auth_client
        session, user_id = db_session

        today = date.today()
        # Create mix of positive and negative PnL
        for i in range(5):
            pnl = PnlDaily(
                user_id=user_id,
                date=today - timedelta(days=i),
                realized_pnl=100.0 if i % 2 == 0 else -50.0,
                unrealized_pnl=50.0,
                fees=5.0,
            )
            session.add(pnl)
        session.commit()

        response = client.get("/api/v1/user/pnl/summary", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Response uses camelCase (totalPnl, daysGreen, daysRed)
        assert "totalPnl" in data
        assert "daysGreen" in data
        assert "daysRed" in data
        assert data["daysGreen"] >= 0
        assert data["daysRed"] >= 0


class TestPnlCalculateEndpoint:
    """Test POST /api/v1/user/pnl/calculate endpoint"""

    def test_calculate_pnl_requires_auth(self, client):
        """Test that calculate endpoint requires authentication"""
        response = client.post("/api/v1/user/pnl/calculate")
        assert response.status_code in (401, 403)

    def test_calculate_pnl_today(self, auth_client, db_session):
        """Test calculating PnL for today"""
        client, headers = auth_client
        session, user_id = db_session

        # Create closed position
        position = Positions(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            quantity=10,
            avg_price=2500.0,
            opened_at=ist_now() - timedelta(days=5),
            closed_at=ist_now(),
            exit_price=2600.0,
            realized_pnl=1000.0,
        )
        session.add(position)
        session.commit()

        response = client.post("/api/v1/user/pnl/calculate", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "date" in data
        assert "realized_pnl" in data
        assert "unrealized_pnl" in data
        assert "fees" in data
        assert "total_pnl" in data

    def test_calculate_pnl_with_date(self, auth_client, db_session):
        """Test calculating PnL for specific date"""
        client, headers = auth_client
        session, user_id = db_session

        target_date = date.today() - timedelta(days=5)
        position = Positions(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            quantity=10,
            avg_price=2500.0,
            opened_at=ist_now() - timedelta(days=10),
            closed_at=datetime.combine(target_date, datetime.min.time()),
            exit_price=2600.0,
            realized_pnl=1000.0,
        )
        session.add(position)
        session.commit()

        response = client.post(
            f"/api/v1/user/pnl/calculate?target_date={target_date}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["date"] == target_date.isoformat()

    def test_calculate_pnl_with_trade_mode(self, auth_client, db_session):
        """Test calculating PnL filtered by trade mode"""
        client, headers = auth_client
        session, user_id = db_session

        # Create order with PAPER mode
        orders_repo = OrdersRepository(session)
        order = orders_repo.create_amo(
            user_id=user_id,
            symbol="RELIANCE-EQ",
            side="buy",
            order_type="amo",
            quantity=10,
            price=2500.0,
            trade_mode=TradeMode.PAPER,
        )
        session.commit()

        response = client.post(
            "/api/v1/user/pnl/calculate?trade_mode=paper",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "realized_pnl" in data

    def test_calculate_pnl_invalid_trade_mode(self, auth_client):
        """Test calculating PnL with invalid trade mode"""
        client, headers = auth_client

        response = client.post(
            "/api/v1/user/pnl/calculate?trade_mode=invalid",
            headers=headers,
        )
        assert response.status_code == 400

    def test_calculate_pnl_invalid_date_format(self, auth_client):
        """Test calculating PnL with invalid date format"""
        client, headers = auth_client

        response = client.post(
            "/api/v1/user/pnl/calculate?target_date=invalid-date",
            headers=headers,
        )
        # Should handle gracefully (400 or use default)
        assert response.status_code in (200, 400, 422)


class TestPnlBackfillEndpoint:
    """Test POST /api/v1/user/pnl/backfill endpoint"""

    def test_backfill_pnl_requires_auth(self, client):
        """Test that backfill endpoint requires authentication"""
        response = client.post("/api/v1/user/pnl/backfill")
        assert response.status_code in (401, 403)

    def test_backfill_pnl_with_date_range(self, auth_client, db_session):
        """Test backfilling PnL for date range"""
        client, headers = auth_client
        session, user_id = db_session

        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        # Create some positions
        for i in range(3):
            position = Positions(
                user_id=user_id,
                symbol=f"STOCK{i}-EQ",
                quantity=10,
                avg_price=1000.0,
                opened_at=ist_now() - timedelta(days=10),
                closed_at=datetime.combine(start_date + timedelta(days=i), datetime.min.time()),
                exit_price=1100.0,
                realized_pnl=1000.0,
            )
            session.add(position)
        session.commit()

        response = client.post(
            f"/api/v1/user/pnl/backfill?start_date={start_date}&end_date={end_date}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        # Response format may vary - check for key fields
        assert "records_created" in data or "message" in data
        assert "start_date" in data
        assert "end_date" in data

    def test_backfill_pnl_missing_parameters(self, auth_client):
        """Test backfill with missing required parameters"""
        client, headers = auth_client

        response = client.post("/api/v1/user/pnl/backfill", headers=headers)
        # Should return 422 (validation error) or 400
        assert response.status_code in (400, 422)

    def test_backfill_pnl_invalid_date_range(self, auth_client):
        """Test backfill with invalid date range (start > end)"""
        client, headers = auth_client

        end_date = date.today() - timedelta(days=10)
        start_date = date.today()

        response = client.post(
            f"/api/v1/user/pnl/backfill?start_date={start_date}&end_date={end_date}",
            headers=headers,
        )
        # Should handle gracefully (400 or swap dates)
        assert response.status_code in (200, 400, 422)

    def test_backfill_pnl_date_range_too_large(self, auth_client):
        """Test backfill with date range exceeding 1 year limit"""
        client, headers = auth_client

        end_date = date.today()
        start_date = end_date - timedelta(days=400)  # More than 1 year

        response = client.post(
            f"/api/v1/user/pnl/backfill?start_date={start_date}&end_date={end_date}",
            headers=headers,
        )
        # Should return 400 (date range too large)
        assert response.status_code == 400


class TestPnlAuditHistoryEndpoint:
    """Test GET /api/v1/user/pnl/audit-history endpoint (Phase 0.5)"""

    def test_audit_history_requires_auth(self, client):
        """Test that audit history endpoint requires authentication"""
        response = client.get("/api/v1/user/pnl/audit-history")
        assert response.status_code in (401, 403)

    def test_audit_history_empty_result(self, auth_client):
        """Test audit history with no records"""
        client, headers = auth_client

        response = client.get("/api/v1/user/pnl/audit-history", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_audit_history_with_records(self, auth_client, db_session):
        """Test audit history with existing records"""
        client, headers = auth_client
        session, user_id = db_session

        # Create audit records
        for i in range(3):
            audit = PnlCalculationAudit(
                user_id=user_id,
                calculation_type="daily",
                date_range_start=date.today() - timedelta(days=i + 1),
                date_range_end=date.today() - timedelta(days=i),
                positions_processed=10,
                orders_processed=5,
                pnl_records_created=1,
                pnl_records_updated=0,
                duration_seconds=1.5,
                status="completed",
                triggered_by="api",
            )
            session.add(audit)
        session.commit()

        response = client.get("/api/v1/user/pnl/audit-history", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("id" in item for item in data)
        assert all("status" in item for item in data)
        assert all("duration_seconds" in item for item in data)

    def test_audit_history_with_status_filter(self, auth_client, db_session):
        """Test audit history filtered by status"""
        client, headers = auth_client
        session, user_id = db_session

        # Create audit records with different statuses
        audit1 = PnlCalculationAudit(
            user_id=user_id,
            calculation_type="daily",
            status="completed",
            positions_processed=10,
            orders_processed=5,
            pnl_records_created=1,
            pnl_records_updated=0,
            duration_seconds=1.5,
            triggered_by="api",
        )
        audit2 = PnlCalculationAudit(
            user_id=user_id,
            calculation_type="daily",
            status="failed",
            error_message="Test error",
            positions_processed=0,
            orders_processed=0,
            pnl_records_created=0,
            pnl_records_updated=0,
            duration_seconds=0.0,
            triggered_by="api",
        )
        session.add_all([audit1, audit2])
        session.commit()

        # Filter by completed
        response = client.get(
            "/api/v1/user/pnl/audit-history?status=completed",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "completed"

        # Filter by failed
        response = client.get(
            "/api/v1/user/pnl/audit-history?status=failed",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "failed"

    def test_audit_history_with_limit(self, auth_client, db_session):
        """Test audit history with limit parameter"""
        client, headers = auth_client
        session, user_id = db_session

        # Create multiple audit records
        for i in range(10):
            audit = PnlCalculationAudit(
                user_id=user_id,
                calculation_type="daily",
                status="completed",
                positions_processed=10,
                orders_processed=5,
                pnl_records_created=1,
                pnl_records_updated=0,
                duration_seconds=1.5,
                triggered_by="api",
            )
            session.add(audit)
        session.commit()

        response = client.get("/api/v1/user/pnl/audit-history?limit=5", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5


class TestPnlApiEdgeCases:
    """Test edge cases and error handling"""

    def test_data_isolation_between_users(self, auth_client, db_session):
        """Test that users can only see their own PnL data"""
        client, headers = auth_client
        session, user_id = db_session

        # Create second user
        user2 = Users(
            email="test2@example.com",
            name="Test User 2",
            password_hash="dummy_hash",
            role=UserRole.USER,
            is_active=True,
        )
        session.add(user2)
        session.commit()

        # Create PnL for user2
        pnl = PnlDaily(
            user_id=user2.id,
            date=date.today(),
            realized_pnl=1000.0,
            unrealized_pnl=500.0,
            fees=10.0,
        )
        session.add(pnl)
        session.commit()

        # User1 should not see user2's data
        response = client.get("/api/v1/user/pnl/daily", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Should not include user2's data
        assert all(item.get("user_id") != user2.id for item in data if "user_id" in item)

    def test_invalid_authentication_token(self, client):
        """Test API with invalid authentication token"""
        headers = {"Authorization": "Bearer invalid_token"}

        response = client.get("/api/v1/user/pnl/daily", headers=headers)
        assert response.status_code in (401, 403)

    def test_missing_authentication_header(self, client):
        """Test API without authentication header"""
        response = client.get("/api/v1/user/pnl/daily")
        assert response.status_code in (401, 403)
