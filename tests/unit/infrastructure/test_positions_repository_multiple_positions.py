"""
Tests for Multiple Positions Per Symbol Support

Tests verify that:
1. get_by_symbol() returns only open positions (most recent)
2. get_by_symbol_for_update() returns only open positions (most recent)
3. get_by_symbol_any() can query any position (open or closed)
4. upsert() creates new position when only closed positions exist
5. Multiple closed positions can exist for the same symbol
6. Only one open position per symbol is allowed
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.base import Base
from src.infrastructure.db.models import Positions, UserRole, Users
from src.infrastructure.persistence.positions_repository import PositionsRepository


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
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
def positions_repo(db_session):
    """Create PositionsRepository instance"""
    session, _ = db_session
    return PositionsRepository(session)


@pytest.fixture
def user_id(db_session):
    """Get user ID from session"""
    _, user_id = db_session
    return user_id


class TestGetBySymbolMultiplePositions:
    """Test get_by_symbol() with multiple positions"""

    def test_get_by_symbol_returns_open_position_only(self, positions_repo, user_id):
        """Test that get_by_symbol() returns only open positions"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # Create closed position (older)
        closed_pos = Positions(
            user_id=user_id,
            symbol=symbol,
            quantity=0.0,
            avg_price=2500.0,
            opened_at=datetime.now() - timedelta(days=10),
            closed_at=datetime.now() - timedelta(days=5),
        )
        positions_repo.db.add(closed_pos)
        positions_repo.db.commit()

        # Create open position (newer)
        open_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2600.0,
        )

        # get_by_symbol() should return the open position
        result = positions_repo.get_by_symbol(user_id, symbol)
        assert result is not None
        assert result.id == open_pos.id
        assert result.closed_at is None
        assert result.quantity == 10.0

    def test_get_by_symbol_returns_none_when_only_closed_positions_exist(
        self, positions_repo, user_id
    ):
        """Test that get_by_symbol() returns None when only closed positions exist"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # Create closed position
        closed_pos = Positions(
            user_id=user_id,
            symbol=symbol,
            quantity=0.0,
            avg_price=2500.0,
            opened_at=datetime.now() - timedelta(days=10),
            closed_at=datetime.now() - timedelta(days=5),
        )
        positions_repo.db.add(closed_pos)
        positions_repo.db.commit()

        # get_by_symbol() should return None
        result = positions_repo.get_by_symbol(user_id, symbol)
        assert result is None

    def test_get_by_symbol_returns_most_recent_open_position(self, positions_repo, user_id):
        """Test that get_by_symbol() returns the most recent open position"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # Create multiple closed positions
        for i in range(3):
            closed_pos = Positions(
                user_id=user_id,
                symbol=symbol,
                quantity=0.0,
                avg_price=2500.0 + i * 100,
                opened_at=datetime.now() - timedelta(days=10 - i),
                closed_at=datetime.now() - timedelta(days=5 - i),
            )
            positions_repo.db.add(closed_pos)

        # Create open position (most recent)
        open_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2600.0,
        )

        positions_repo.db.commit()

        # get_by_symbol() should return the open position
        result = positions_repo.get_by_symbol(user_id, symbol)
        assert result is not None
        assert result.id == open_pos.id
        assert result.closed_at is None


class TestGetBySymbolForUpdateMultiplePositions:
    """Test get_by_symbol_for_update() with multiple positions"""

    def test_get_by_symbol_for_update_returns_open_position_only(self, positions_repo, user_id):
        """Test that get_by_symbol_for_update() returns only open positions"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # Create closed position
        closed_pos = Positions(
            user_id=user_id,
            symbol=symbol,
            quantity=0.0,
            avg_price=2500.0,
            opened_at=datetime.now() - timedelta(days=10),
            closed_at=datetime.now() - timedelta(days=5),
        )
        positions_repo.db.add(closed_pos)
        positions_repo.db.commit()

        # Create open position
        open_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2600.0,
        )

        # get_by_symbol_for_update() should return the open position
        result = positions_repo.get_by_symbol_for_update(user_id, symbol)
        assert result is not None
        assert result.id == open_pos.id
        assert result.closed_at is None

    def test_get_by_symbol_for_update_returns_none_when_only_closed(self, positions_repo, user_id):
        """Test that get_by_symbol_for_update() returns None when only closed positions exist"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # Create closed position
        closed_pos = Positions(
            user_id=user_id,
            symbol=symbol,
            quantity=0.0,
            avg_price=2500.0,
            opened_at=datetime.now() - timedelta(days=10),
            closed_at=datetime.now() - timedelta(days=5),
        )
        positions_repo.db.add(closed_pos)
        positions_repo.db.commit()

        # get_by_symbol_for_update() should return None
        result = positions_repo.get_by_symbol_for_update(user_id, symbol)
        assert result is None


class TestGetBySymbolAny:
    """Test get_by_symbol_any() method"""

    def test_get_by_symbol_any_with_include_closed_false(self, positions_repo, user_id):
        """Test get_by_symbol_any() with include_closed=False (same as get_by_symbol())"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # Create closed position
        closed_pos = Positions(
            user_id=user_id,
            symbol=symbol,
            quantity=0.0,
            avg_price=2500.0,
            opened_at=datetime.now() - timedelta(days=10),
            closed_at=datetime.now() - timedelta(days=5),
        )
        positions_repo.db.add(closed_pos)
        positions_repo.db.commit()

        # Create open position
        open_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2600.0,
        )

        # get_by_symbol_any(include_closed=False) should return open position
        result = positions_repo.get_by_symbol_any(user_id, symbol, include_closed=False)
        assert result is not None
        assert result.id == open_pos.id
        assert result.closed_at is None

    def test_get_by_symbol_any_with_include_closed_true(self, positions_repo, user_id):
        """Test get_by_symbol_any() with include_closed=True returns closed positions"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # Create closed position (older)
        closed_pos = Positions(
            user_id=user_id,
            symbol=symbol,
            quantity=0.0,
            avg_price=2500.0,
            opened_at=datetime.now() - timedelta(days=10),
            closed_at=datetime.now() - timedelta(days=5),
        )
        positions_repo.db.add(closed_pos)
        positions_repo.db.commit()

        # Create open position (newer)
        open_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2600.0,
        )

        # get_by_symbol_any(include_closed=True) should return most recent (open)
        result = positions_repo.get_by_symbol_any(user_id, symbol, include_closed=True)
        assert result is not None
        assert result.id == open_pos.id  # Most recent is open

    def test_get_by_symbol_any_returns_closed_when_only_closed_exists(
        self, positions_repo, user_id
    ):
        """Test get_by_symbol_any() returns closed position when only closed positions exist"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # Create closed position
        closed_pos = Positions(
            user_id=user_id,
            symbol=symbol,
            quantity=0.0,
            avg_price=2500.0,
            opened_at=datetime.now() - timedelta(days=10),
            closed_at=datetime.now() - timedelta(days=5),
        )
        positions_repo.db.add(closed_pos)
        positions_repo.db.commit()

        # get_by_symbol_any(include_closed=True) should return closed position
        result = positions_repo.get_by_symbol_any(user_id, symbol, include_closed=True)
        assert result is not None
        assert result.id == closed_pos.id
        assert result.closed_at is not None


class TestUpsertWithMultiplePositions:
    """Test upsert() behavior with multiple positions"""

    def test_upsert_creates_new_position_when_only_closed_exists(self, positions_repo, user_id):
        """Test that upsert() creates a new position when only closed positions exist"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # Create closed position
        closed_pos = Positions(
            user_id=user_id,
            symbol=symbol,
            quantity=0.0,
            avg_price=2500.0,
            opened_at=datetime.now() - timedelta(days=10),
            closed_at=datetime.now() - timedelta(days=5),
        )
        positions_repo.db.add(closed_pos)
        positions_repo.db.commit()
        closed_pos_id = closed_pos.id

        # upsert() should create a new position
        new_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2600.0,
        )

        assert new_pos is not None
        assert new_pos.id != closed_pos_id
        assert new_pos.closed_at is None
        assert new_pos.quantity == 10.0

        # Verify old closed position still exists
        old_pos = positions_repo.get_by_symbol_any(user_id, symbol, include_closed=True)
        # Should get the new open position (most recent)
        assert old_pos.id == new_pos.id

        # Verify we can get the closed position by querying all
        all_positions = (
            positions_repo.db.query(Positions)
            .filter(Positions.user_id == user_id, Positions.symbol == symbol)
            .all()
        )
        assert len(all_positions) == 2
        closed_found = [p for p in all_positions if p.closed_at is not None]
        assert len(closed_found) == 1
        assert closed_found[0].id == closed_pos_id

    def test_upsert_updates_existing_open_position(self, positions_repo, user_id):
        """Test that upsert() updates existing open position"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # Create open position
        open_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2500.0,
        )
        open_pos_id = open_pos.id

        # upsert() should update the existing open position
        updated_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=20.0,
            avg_price=2550.0,
        )

        assert updated_pos.id == open_pos_id
        assert updated_pos.quantity == 20.0
        assert updated_pos.avg_price == 2550.0
        assert updated_pos.closed_at is None

    def test_upsert_with_multiple_closed_positions(self, positions_repo, user_id):
        """Test that upsert() works correctly when multiple closed positions exist"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # Create multiple closed positions
        for i in range(3):
            closed_pos = Positions(
                user_id=user_id,
                symbol=symbol,
                quantity=0.0,
                avg_price=2500.0 + i * 100,
                opened_at=datetime.now() - timedelta(days=10 - i),
                closed_at=datetime.now() - timedelta(days=5 - i),
            )
            positions_repo.db.add(closed_pos)
        positions_repo.db.commit()

        # upsert() should create a new open position
        new_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2600.0,
        )

        assert new_pos is not None
        assert new_pos.closed_at is None
        assert new_pos.quantity == 10.0

        # Verify all positions exist
        all_positions = (
            positions_repo.db.query(Positions)
            .filter(Positions.user_id == user_id, Positions.symbol == symbol)
            .all()
        )
        assert len(all_positions) == 4  # 3 closed + 1 open


class TestCompleteBuyCloseBuyCycle:
    """Test complete flow: Buy → Close → Buy again"""

    def test_buy_close_buy_again_creates_multiple_positions(self, positions_repo, user_id):
        """Test that buying, closing, and buying again creates multiple position records"""
        symbol = "RELIANCE-EQ"  # Full symbol after migration

        # First buy
        pos1 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2500.0,
        )
        pos1_id = pos1.id

        # Close first position
        positions_repo.mark_closed(user_id, symbol)
        positions_repo.db.commit()

        # Verify first position is closed
        closed_pos1 = positions_repo.db.query(Positions).filter(Positions.id == pos1_id).first()
        assert closed_pos1.closed_at is not None
        assert closed_pos1.quantity == 0.0

        # Second buy (should create new position)
        pos2 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=15.0,
            avg_price=2600.0,
        )
        pos2_id = pos2.id

        assert pos2_id != pos1_id
        assert pos2.closed_at is None
        assert pos2.quantity == 15.0

        # Verify get_by_symbol() returns the new open position
        current_pos = positions_repo.get_by_symbol(user_id, symbol)
        assert current_pos is not None
        assert current_pos.id == pos2_id
        assert current_pos.closed_at is None

        # Verify both positions exist
        all_positions = (
            positions_repo.db.query(Positions)
            .filter(Positions.user_id == user_id, Positions.symbol == symbol)
            .all()
        )
        assert len(all_positions) == 2

        # Verify one is closed, one is open
        closed_count = sum(1 for p in all_positions if p.closed_at is not None)
        open_count = sum(1 for p in all_positions if p.closed_at is None)
        assert closed_count == 1
        assert open_count == 1
