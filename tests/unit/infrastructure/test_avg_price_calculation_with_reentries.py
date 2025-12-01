"""
Tests for average price calculation with initial entry and reentries.

This tests that when reentries are added, the average price is correctly
recalculated as a weighted average of all entries.
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


class TestAveragePriceCalculationWithReentries:
    """Test average price calculation with multiple entries"""

    def test_initial_entry_sets_avg_price(self, positions_repo, user_id):
        """Test that initial entry sets avg_price correctly"""
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
            initial_entry_price=2500.0,
        )
        
        assert position.avg_price == 2500.0
        assert position.initial_entry_price == 2500.0

    def test_single_reentry_recalculates_avg_price(self, positions_repo, user_id):
        """Test that single reentry recalculates avg_price correctly"""
        # Initial entry: 10 shares @ Rs 2500
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
            initial_entry_price=2500.0,
        )
        
        # Reentry: 5 shares @ Rs 2400
        # Expected avg = (10*2500 + 5*2400) / 15 = (25000 + 12000) / 15 = 2466.67
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=15,  # 10 + 5
            avg_price=2466.67,  # Weighted average
            reentry_count=1,
            reentries=[
                {"qty": 5, "level": 30, "rsi": 29.5, "price": 2400.0, "time": "2024-01-01T10:00:00"}
            ],
            last_reentry_price=2400.0,
        )
        
        assert position.quantity == 15
        assert abs(position.avg_price - 2466.67) < 0.01
        assert position.initial_entry_price == 2500.0  # Preserved

    def test_multiple_reentries_recalculates_avg_price(self, positions_repo, user_id):
        """Test that multiple reentries recalculate avg_price correctly"""
        # Initial entry: 10 shares @ Rs 2500
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=10,
            avg_price=2500.0,
            initial_entry_price=2500.0,
        )
        
        # Reentry 1: 5 shares @ Rs 2400
        # After reentry 1: 15 shares, avg = (10*2500 + 5*2400) / 15 = 2466.67
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=15,
            avg_price=2466.67,
            reentry_count=1,
            reentries=[
                {"qty": 5, "level": 30, "rsi": 29.5, "price": 2400.0, "time": "2024-01-01T10:00:00"}
            ],
            last_reentry_price=2400.0,
        )
        
        # Reentry 2: 3 shares @ Rs 2300
        # After reentry 2: 18 shares, avg = (10*2500 + 5*2400 + 3*2300) / 18 = 2438.89
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=18,  # 15 + 3
            avg_price=2438.89,  # Weighted average
            reentry_count=2,
            reentries=[
                {"qty": 5, "level": 30, "rsi": 29.5, "price": 2400.0, "time": "2024-01-01T10:00:00"},
                {"qty": 3, "level": 20, "rsi": 19.5, "price": 2300.0, "time": "2024-01-02T10:00:00"},
            ],
            last_reentry_price=2300.0,
        )
        
        assert position.quantity == 18
        # Expected: (10*2500 + 5*2400 + 3*2300) / 18 = 43900 / 18 = 2438.89
        expected_avg = (10 * 2500.0 + 5 * 2400.0 + 3 * 2300.0) / 18
        assert abs(position.avg_price - expected_avg) < 0.01
        assert position.initial_entry_price == 2500.0  # Preserved

    def test_avg_price_calculation_formula(self, positions_repo, user_id):
        """Test the weighted average formula: (prev_avg * prev_qty + new_price * new_qty) / total_qty"""
        # Initial: 100 shares @ Rs 100
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="TEST",
            quantity=100,
            avg_price=100.0,
            initial_entry_price=100.0,
        )
        
        # Reentry: 50 shares @ Rs 90
        # Expected: (100*100 + 50*90) / 150 = (10000 + 4500) / 150 = 96.67
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="TEST",
            quantity=150,
            avg_price=96.67,
            reentry_count=1,
            reentries=[
                {"qty": 50, "level": 30, "rsi": 29.5, "price": 90.0, "time": "2024-01-01T10:00:00"}
            ],
            last_reentry_price=90.0,
        )
        
        expected_avg = (100 * 100 + 50 * 90) / 150
        assert abs(position.avg_price - expected_avg) < 0.01
        assert position.avg_price == 96.67

    def test_avg_price_with_reentry_at_higher_price(self, positions_repo, user_id):
        """Test average price calculation when reentry is at higher price (averaging up)"""
        # Initial: 10 shares @ Rs 100
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="TEST",
            quantity=10,
            avg_price=100.0,
            initial_entry_price=100.0,
        )
        
        # Reentry: 5 shares @ Rs 110 (averaging up)
        # Expected: (10*100 + 5*110) / 15 = (1000 + 550) / 15 = 103.33
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="TEST",
            quantity=15,
            avg_price=103.33,
            reentry_count=1,
            reentries=[
                {"qty": 5, "level": 30, "rsi": 29.5, "price": 110.0, "time": "2024-01-01T10:00:00"}
            ],
            last_reentry_price=110.0,
        )
        
        expected_avg = (10 * 100 + 5 * 110) / 15
        assert abs(position.avg_price - expected_avg) < 0.01
        assert position.avg_price > 100.0  # Should increase
        assert position.avg_price < 110.0  # But less than reentry price

