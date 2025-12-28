"""
Unit tests for Phase 0.3: Portfolio Snapshots

Tests cover:
- Creating snapshots
- Querying by date range
- Unique constraint (user_id, date, snapshot_type)
- Edge cases and negative scenarios
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.base import Base
from src.infrastructure.db.models import PortfolioSnapshot, UserRole, Users
from src.infrastructure.persistence.portfolio_snapshot_repository import PortfolioSnapshotRepository


@pytest.fixture
def db_session():
    """Create in-memory test database"""
    engine = create_engine("sqlite:///:memory:")
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
def snapshot_repo(db_session):
    session, _ = db_session
    return PortfolioSnapshotRepository(session)


class TestPortfolioSnapshots:
    """Test portfolio snapshot functionality"""

    def test_create_snapshot(self, snapshot_repo, db_session):
        """Test creating a portfolio snapshot"""
        session, user_id = db_session

        snapshot = PortfolioSnapshot(
            user_id=user_id,
            date=date.today(),
            total_value=100000.0,
            invested_value=95000.0,
            available_cash=5000.0,
            unrealized_pnl=2000.0,
            realized_pnl=3000.0,
            open_positions_count=5,
            closed_positions_count=10,
            total_return=5.0,
            daily_return=0.5,
            snapshot_type="eod",
        )

        created = snapshot_repo.create(snapshot)
        assert created.id is not None
        assert created.user_id == user_id
        assert created.total_value == 100000.0

    def test_get_by_date_range(self, snapshot_repo, db_session):
        """Test querying snapshots by date range"""
        session, user_id = db_session

        today = date.today()
        dates = [today - timedelta(days=i) for i in range(5)]

        for i, d in enumerate(dates):
            snapshot = PortfolioSnapshot(
                user_id=user_id,
                date=d,
                total_value=100000.0 + i * 1000,
                invested_value=95000.0,
                available_cash=5000.0,
                snapshot_type="eod",
            )
            snapshot_repo.create(snapshot)

        # Query last 3 days
        start = today - timedelta(days=3)
        snapshots = snapshot_repo.get_by_date_range(user_id, start, today)

        assert len(snapshots) == 4  # Including today
        assert all(s.date >= start for s in snapshots)
        assert all(s.date <= today for s in snapshots)

    def test_get_latest(self, snapshot_repo, db_session):
        """Test getting latest snapshot"""
        session, user_id = db_session

        today = date.today()
        for i in range(3):
            snapshot = PortfolioSnapshot(
                user_id=user_id,
                date=today - timedelta(days=i),
                total_value=100000.0,
                invested_value=95000.0,
                available_cash=5000.0,
                snapshot_type="eod",
            )
            snapshot_repo.create(snapshot)

        latest = snapshot_repo.get_latest(user_id)
        assert latest is not None
        assert latest.date == today

    def test_get_by_date(self, snapshot_repo, db_session):
        """Test getting snapshot by specific date"""
        session, user_id = db_session

        target_date = date.today()
        snapshot = PortfolioSnapshot(
            user_id=user_id,
            date=target_date,
            total_value=100000.0,
            invested_value=95000.0,
            available_cash=5000.0,
            snapshot_type="eod",
        )
        snapshot_repo.create(snapshot)

        found = snapshot_repo.get_by_date(user_id, target_date)
        assert found is not None
        assert found.date == target_date

    def test_unique_constraint_same_date_type(self, snapshot_repo, db_session):
        """Test unique constraint on (user_id, date, snapshot_type)"""
        session, user_id = db_session

        target_date = date.today()
        snapshot1 = PortfolioSnapshot(
            user_id=user_id,
            date=target_date,
            total_value=100000.0,
            invested_value=95000.0,
            available_cash=5000.0,
            snapshot_type="eod",
        )
        snapshot_repo.create(snapshot1)

        # Try to create duplicate
        snapshot2 = PortfolioSnapshot(
            user_id=user_id,
            date=target_date,
            total_value=110000.0,
            invested_value=100000.0,
            available_cash=10000.0,
            snapshot_type="eod",
        )

        # Should raise integrity error or use upsert
        with pytest.raises(Exception):  # Unique constraint violation
            snapshot_repo.create(snapshot2)
            session.commit()

    def test_different_snapshot_types_same_date(self, snapshot_repo, db_session):
        """Test that different snapshot types can exist for same date"""
        session, user_id = db_session

        target_date = date.today()
        eod_snapshot = PortfolioSnapshot(
            user_id=user_id,
            date=target_date,
            total_value=100000.0,
            invested_value=95000.0,
            available_cash=5000.0,
            snapshot_type="eod",
        )
        intraday_snapshot = PortfolioSnapshot(
            user_id=user_id,
            date=target_date,
            total_value=101000.0,
            invested_value=95000.0,
            available_cash=6000.0,
            snapshot_type="intraday",
        )

        snapshot_repo.create(eod_snapshot)
        snapshot_repo.create(intraday_snapshot)

        # Both should exist
        eod = snapshot_repo.get_by_date(user_id, target_date, "eod")
        intraday = snapshot_repo.get_by_date(user_id, target_date, "intraday")

        assert eod is not None
        assert intraday is not None
        assert eod.snapshot_type == "eod"
        assert intraday.snapshot_type == "intraday"

    def test_upsert_daily(self, snapshot_repo, db_session):
        """Test upsert_daily method"""
        session, user_id = db_session

        target_date = date.today()
        snapshot = PortfolioSnapshot(
            user_id=user_id,
            date=target_date,
            total_value=100000.0,
            invested_value=95000.0,
            available_cash=5000.0,
            snapshot_type="eod",
        )

        # First create using dict
        created = snapshot_repo.upsert_daily(
            user_id,
            target_date,
            {
                "total_value": 100000.0,
                "invested_value": 95000.0,
                "available_cash": 5000.0,
            },
        )
        assert created.id is not None

        # Update with new values
        updated = snapshot_repo.upsert_daily(
            user_id,
            target_date,
            {
                "total_value": 110000.0,
                "invested_value": 100000.0,
                "available_cash": 10000.0,
            },
        )

        # Should update existing
        assert updated.id == created.id
        assert updated.total_value == 110000.0


class TestPortfolioSnapshotsEdgeCases:
    """Test edge cases and negative scenarios"""

    def test_snapshot_with_zero_values(self, snapshot_repo, db_session):
        """Test snapshot with zero portfolio values"""
        session, user_id = db_session

        snapshot = PortfolioSnapshot(
            user_id=user_id,
            date=date.today(),
            total_value=0.0,
            invested_value=0.0,
            available_cash=0.0,
            snapshot_type="eod",
        )

        created = snapshot_repo.create(snapshot)
        assert created.total_value == 0.0

    def test_snapshot_with_negative_pnl(self, snapshot_repo, db_session):
        """Test snapshot with negative P&L"""
        session, user_id = db_session

        snapshot = PortfolioSnapshot(
            user_id=user_id,
            date=date.today(),
            total_value=90000.0,
            invested_value=100000.0,
            available_cash=0.0,
            unrealized_pnl=-5000.0,
            realized_pnl=-5000.0,
            snapshot_type="eod",
        )

        created = snapshot_repo.create(snapshot)
        assert created.unrealized_pnl < 0
        assert created.realized_pnl < 0

    def test_snapshot_with_very_large_values(self, snapshot_repo, db_session):
        """Test snapshot with very large portfolio values"""
        session, user_id = db_session

        snapshot = PortfolioSnapshot(
            user_id=user_id,
            date=date.today(),
            total_value=1000000000.0,  # 1 billion
            invested_value=950000000.0,
            available_cash=50000000.0,
            snapshot_type="eod",
        )

        created = snapshot_repo.create(snapshot)
        assert created.total_value == 1000000000.0

    def test_get_by_date_range_empty_result(self, snapshot_repo, db_session):
        """Test querying date range with no results"""
        session, user_id = db_session

        start = date.today() - timedelta(days=10)
        end = date.today() - timedelta(days=5)

        snapshots = snapshot_repo.get_by_date_range(user_id, start, end)
        assert len(snapshots) == 0

    def test_get_latest_no_snapshots(self, snapshot_repo, db_session):
        """Test getting latest when no snapshots exist"""
        session, user_id = db_session

        latest = snapshot_repo.get_latest(user_id)
        assert latest is None

    def test_multiple_users_same_date(self, snapshot_repo, db_session):
        """Test multiple users can have snapshots for same date"""
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
        session.refresh(user2)

        target_date = date.today()
        snapshot1 = PortfolioSnapshot(
            user_id=user_id,
            date=target_date,
            total_value=100000.0,
            invested_value=95000.0,
            available_cash=5000.0,
            snapshot_type="eod",
        )
        snapshot2 = PortfolioSnapshot(
            user_id=user2.id,
            date=target_date,
            total_value=200000.0,
            invested_value=190000.0,
            available_cash=10000.0,
            snapshot_type="eod",
        )

        snapshot_repo.create(snapshot1)
        snapshot_repo.create(snapshot2)

        # Both should exist
        found1 = snapshot_repo.get_by_date(user_id, target_date)
        found2 = snapshot_repo.get_by_date(user2.id, target_date)

        assert found1 is not None
        assert found2 is not None
        assert found1.user_id == user_id
        assert found2.user_id == user2.id
