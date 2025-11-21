"""
Tests for reentry tracking in Positions table.

Tests the new reentry_count, reentries, initial_entry_price, and last_reentry_price fields.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.models import Positions
from src.infrastructure.persistence.positions_repository import PositionsRepository


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    from src.infrastructure.db.models import Base
    
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def positions_repo(db_session):
    """Create PositionsRepository instance"""
    return PositionsRepository(db_session)


@pytest.fixture
def user_id():
    return 1


class TestReentryTrackingInPositions:
    """Test reentry tracking in Positions table"""

    def test_upsert_position_with_reentry_fields(self, positions_repo, user_id):
        """Test upserting position with reentry tracking fields"""
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
            opened_at=datetime.now(),
            reentry_count=2,
            reentries=[
                {"qty": 5, "level": 30, "rsi": 29.5, "price": 2480.0, "time": "2024-01-01T10:00:00"},
                {"qty": 3, "level": 20, "rsi": 19.5, "price": 2450.0, "time": "2024-01-02T10:00:00"},
            ],
            initial_entry_price=2500.0,
            last_reentry_price=2450.0,
        )
        
        assert position.reentry_count == 2
        assert len(position.reentries) == 2
        assert position.initial_entry_price == 2500.0
        assert position.last_reentry_price == 2450.0

    def test_upsert_position_without_reentry_fields(self, positions_repo, user_id):
        """Test upserting position without reentry fields (backward compatibility)"""
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
        )
        
        assert position.reentry_count == 0
        assert position.reentries is None
        # initial_entry_price should be set to avg_price for new positions
        assert position.initial_entry_price == 2500.0

    def test_update_existing_position_with_reentry(self, positions_repo, user_id):
        """Test updating existing position with reentry data"""
        # Create initial position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
            initial_entry_price=2500.0,
        )
        
        initial_entry_price = position.initial_entry_price
        
        # Update with reentry
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=15,  # Updated quantity
            avg_price=2480.0,  # Updated average price
            reentry_count=1,
            reentries=[
                {"qty": 5, "level": 30, "rsi": 29.5, "price": 2450.0, "time": "2024-01-01T10:00:00"},
            ],
            last_reentry_price=2450.0,
        )
        
        assert position.quantity == 15
        assert position.avg_price == 2480.0
        assert position.reentry_count == 1
        assert len(position.reentries) == 1
        # initial_entry_price should be preserved
        assert position.initial_entry_price == initial_entry_price
        assert position.last_reentry_price == 2450.0

    def test_multiple_reentries_tracking(self, positions_repo, user_id):
        """Test tracking multiple reentries"""
        reentries = [
            {"qty": 5, "level": 30, "rsi": 29.5, "price": 2480.0, "time": "2024-01-01T10:00:00"},
            {"qty": 3, "level": 20, "rsi": 19.5, "price": 2450.0, "time": "2024-01-02T10:00:00"},
            {"qty": 2, "level": 10, "rsi": 9.5, "price": 2400.0, "time": "2024-01-03T10:00:00"},
        ]
        
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=20,  # 10 initial + 5 + 3 + 2
            avg_price=2460.0,
            reentry_count=3,
            reentries=reentries,
            initial_entry_price=2500.0,
            last_reentry_price=2400.0,
        )
        
        assert position.reentry_count == 3
        assert len(position.reentries) == 3
        assert position.last_reentry_price == 2400.0
        assert position.reentries[0]["level"] == 30
        assert position.reentries[1]["level"] == 20
        assert position.reentries[2]["level"] == 10

    def test_initial_entry_price_preserved(self, positions_repo, user_id):
        """Test that initial_entry_price is preserved when updating position"""
        # Create initial position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
            initial_entry_price=2500.0,
        )
        
        original_initial_price = position.initial_entry_price
        
        # Update position (should preserve initial_entry_price)
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=15,
            avg_price=2480.0,
            reentry_count=1,
            last_reentry_price=2450.0,
        )
        
        # initial_entry_price should not be updated if position exists
        # (Only set for new positions)
        assert position.initial_entry_price == original_initial_price

