"""
Unit tests for PortfolioSnapshotRepository (Phase 0.3)
Tests snapshot creation, retrieval, and historical data queries
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.infrastructure.db.models import TradeMode, Users, UserSettings
from src.infrastructure.persistence.portfolio_snapshot_repository import (
    PortfolioSnapshotRepository,
)


class TestPortfolioSnapshotRepository:
    """Test suite for PortfolioSnapshotRepository"""

    @pytest.fixture
    def repository(self, db_session: Session):
        """Create repository instance"""
        return PortfolioSnapshotRepository(db_session)

    @pytest.fixture
    def test_user(self, db_session: Session):
        """Create test user"""
        user = Users(
            email="portfolio@example.com",
            name="Portfolio User",
            password_hash="hash",
            role="user",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        settings = UserSettings(
            user_id=user.id,
            trade_mode=TradeMode.PAPER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(settings)
        db_session.commit()
        return user

    def test_create_snapshot(self, repository, test_user):
        """Test creating a portfolio snapshot"""
        data = {
            "total_value": Decimal("100000.00"),
            "available_cash": Decimal("50000.00"),
            "invested_value": Decimal("50000.00"),
            "realized_pnl": Decimal("5000.00"),
            "unrealized_pnl": Decimal("2000.00"),
            "open_positions_count": 5,
        }
        snapshot = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=date.today(),
            snapshot_data=data,
            snapshot_type="eod",
        )

        assert snapshot.id is not None
        assert snapshot.user_id == test_user.id
        assert snapshot.total_value == Decimal("100000.00")
        assert snapshot.available_cash == Decimal("50000.00")
        assert snapshot.invested_value == Decimal("50000.00")
        assert snapshot.realized_pnl == Decimal("5000.00")
        assert snapshot.unrealized_pnl == Decimal("2000.00")
        assert snapshot.open_positions_count == 5
        assert snapshot.date is not None

    def test_create_snapshot_with_custom_date(self, repository, test_user):
        """Test creating snapshot with specific date"""
        custom_date = date(2024, 1, 15)
        snapshot = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=custom_date,
            snapshot_data={"total_value": Decimal("200000.00")},
            snapshot_type="intraday",
        )

        assert snapshot.date == custom_date
        assert snapshot.snapshot_type == "intraday"

    def test_get_latest_snapshot(self, repository, test_user):
        """Test retrieving latest snapshot"""
        # Create multiple snapshots
        repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=date.today() - timedelta(days=2),
            snapshot_data={"total_value": Decimal("100000.00")},
            snapshot_type="eod",
        )
        latest = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=date.today(),
            snapshot_data={"total_value": Decimal("110000.00")},
            snapshot_type="eod",
        )

        retrieved = repository.get_latest(test_user.id, snapshot_type="eod")
        assert retrieved is not None
        assert retrieved.id == latest.id
        assert retrieved.total_value == Decimal("110000.00")

    def test_get_latest_snapshot_none(self, repository, test_user):
        """Test retrieving latest snapshot when none exist"""
        result = repository.get_latest(test_user.id, snapshot_type="eod")
        assert result is None

    def test_get_snapshots_date_range(self, repository, test_user):
        """Test retrieving snapshots within date range"""
        start_date = date.today() - timedelta(days=10)
        end_date = date.today()

        # Create snapshots within and outside range
        repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=start_date - timedelta(days=5),  # Before range
            snapshot_data={"total_value": Decimal("95000.00")},
            snapshot_type="eod",
        )
        repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=start_date,
            snapshot_data={"total_value": Decimal("100000.00")},
            snapshot_type="eod",
        )
        repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=start_date + timedelta(days=5),
            snapshot_data={"total_value": Decimal("105000.00")},
            snapshot_type="eod",
        )
        repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=end_date,
            snapshot_data={"total_value": Decimal("110000.00")},
            snapshot_type="eod",
        )

        snapshots = repository.get_by_date_range(
            test_user.id, start_date, end_date, snapshot_type="eod"
        )

        assert len(snapshots) == 3
        assert all(start_date <= s.date <= end_date for s in snapshots)
        # Should be ordered by date
        assert snapshots[0].date < snapshots[-1].date

    def test_get_snapshot_for_date(self, repository, test_user):
        """Test retrieving snapshot for specific date"""
        target_date = date(2024, 6, 15)
        snapshot = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=target_date,
            snapshot_data={"total_value": Decimal("100000.00")},
            snapshot_type="eod",
        )

        retrieved = repository.get_by_date(test_user.id, target_date, snapshot_type="eod")
        assert retrieved is not None
        assert retrieved.id == snapshot.id
        assert retrieved.date == target_date

    def test_get_snapshot_for_date_not_found(self, repository, test_user):
        """Test retrieving snapshot for date with no snapshot"""
        result = repository.get_by_date(test_user.id, date(2024, 1, 1), snapshot_type="eod")
        assert result is None

    def test_daily_snapshot_deduplication(self, repository, test_user):
        """Test that only one snapshot per day is kept"""
        target_date = date.today()

        # Create first snapshot
        first = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=target_date,
            snapshot_data={"total_value": Decimal("100000.00")},
            snapshot_type="eod",
        )

        # Create second snapshot for same date (should replace/update)
        second = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=target_date,
            snapshot_data={"total_value": Decimal("105000.00")},
            snapshot_type="eod",
        )

        # Should only have one snapshot for that date with updated values
        snapshot = repository.get_by_date(test_user.id, target_date, snapshot_type="eod")
        assert snapshot.total_value == Decimal("105000.00")

        # Count total snapshots for date
        all_snapshots = repository.get_by_date_range(
            test_user.id, target_date, target_date, snapshot_type="eod"
        )
        assert len(all_snapshots) <= 1

    def test_separate_trade_modes(self, repository, test_user):
        """Test snapshots are separate for paper vs broker mode"""
        target_date = date.today()

        paper_snapshot = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=target_date,
            snapshot_data={"total_value": Decimal("100000.00")},
            snapshot_type="eod",
        )

        broker_snapshot = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=target_date,
            snapshot_data={"total_value": Decimal("200000.00")},
            snapshot_type="intraday",
        )

        # Retrieve separately
        paper_retrieved = repository.get_by_date(test_user.id, target_date, snapshot_type="eod")
        broker_retrieved = repository.get_by_date(
            test_user.id, target_date, snapshot_type="intraday"
        )

        assert paper_retrieved.total_value == Decimal("100000.00")
        assert broker_retrieved.total_value == Decimal("200000.00")
        assert paper_retrieved.id != broker_retrieved.id

    def test_delete_old_snapshots(self, repository, test_user):
        """Test deleting snapshots older than retention period"""
        # Create snapshots across time range
        old_date = date.today() - timedelta(days=400)  # Over 1 year old
        recent_date = date.today() - timedelta(days=30)

        old_snapshot = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=old_date,
            snapshot_data={"total_value": Decimal("90000.00")},
            snapshot_type="eod",
        )

        recent_snapshot = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=recent_date,
            snapshot_data={"total_value": Decimal("100000.00")},
            snapshot_type="eod",
        )

        # Manually delete snapshots older than 365 days for this test
        cutoff_date = date.today() - timedelta(days=365)
        to_delete = repository.get_by_date_range(
            test_user.id, date.min, cutoff_date, snapshot_type="eod"
        )
        deleted_count = 0
        for s in to_delete:
            repository.db.delete(s)
            deleted_count += 1
        repository.db.commit()

        assert deleted_count >= 1

        # Verify old snapshot deleted
        old_retrieved = repository.get_by_date(test_user.id, old_date, snapshot_type="eod")
        assert old_retrieved is None

        # Verify recent snapshot still exists
        recent_retrieved = repository.get_by_date(test_user.id, recent_date, snapshot_type="eod")
        assert recent_retrieved is not None

    def test_negative_values_edge_case(self, repository, test_user):
        """Test snapshot with negative values (losses)"""
        snapshot = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=date.today(),
            snapshot_data={
                "total_value": Decimal("95000.00"),
                "available_cash": Decimal("50000.00"),
                "invested_value": Decimal("45000.00"),
                "realized_pnl": Decimal("-3000.00"),
                "unrealized_pnl": Decimal("-2000.00"),
                "open_positions_count": 3,
            },
            snapshot_type="eod",
        )

        assert snapshot.realized_pnl == Decimal("-3000.00")
        assert snapshot.unrealized_pnl == Decimal("-2000.00")

    def test_zero_values_edge_case(self, repository, test_user):
        """Test snapshot with zero values"""
        snapshot = repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=date.today(),
            snapshot_data={
                "total_value": Decimal("0.00"),
                "available_cash": Decimal("0.00"),
                "invested_value": Decimal("0.00"),
                "open_positions_count": 0,
            },
            snapshot_type="eod",
        )

        assert snapshot.total_value == Decimal("0.00")
        assert snapshot.open_positions_count == 0

    def test_get_snapshots_empty_date_range(self, repository, test_user):
        """Test retrieving snapshots with inverted date range"""
        start_date = date.today()
        end_date = date.today() - timedelta(days=10)

        snapshots = repository.get_by_date_range(
            test_user.id, start_date, end_date, snapshot_type="eod"
        )

        assert len(snapshots) == 0

    def test_calculate_pnl_growth(self, repository, test_user):
        """Test calculating P&L growth between snapshots"""
        date1 = date.today() - timedelta(days=7)
        date2 = date.today()

        repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=date1,
            snapshot_data={"total_value": Decimal("100000.00"), "realized_pnl": Decimal("5000.00")},
            snapshot_type="eod",
        )

        repository.upsert_daily(
            user_id=test_user.id,
            snapshot_date=date2,
            snapshot_data={"total_value": Decimal("108000.00"), "realized_pnl": Decimal("8000.00")},
            snapshot_type="eod",
        )

        snapshots = repository.get_by_date_range(test_user.id, date1, date2, snapshot_type="eod")

        # Calculate growth
        if len(snapshots) >= 2:
            first = snapshots[0]
            last = snapshots[-1]
            total_growth = last.total_value - first.total_value
            pnl_growth = last.realized_pnl - first.realized_pnl

            assert total_growth == Decimal("8000.00")
            assert pnl_growth == Decimal("3000.00")

    def test_bulk_create_snapshots(self, repository, test_user):
        """Test creating multiple snapshots efficiently"""
        snapshots_data = []
        for i in range(30):  # 30 days
            snapshot_date = date.today() - timedelta(days=30 - i)
            data = {
                "total_value": Decimal(f"{100000 + i * 1000}.00"),
            }
            snapshot = repository.upsert_daily(
                user_id=test_user.id,
                snapshot_date=snapshot_date,
                snapshot_data=data,
                snapshot_type="eod",
            )
            snapshots_data.append(snapshot)

        assert len(snapshots_data) == 30

        # Retrieve all
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()
        all_snapshots = repository.get_by_date_range(
            test_user.id, start_date, end_date, snapshot_type="eod"
        )

        assert len(all_snapshots) == 30
