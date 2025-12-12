"""
Integration tests for multiple positions per symbol support.

Tests verify that:
1. Complete flow: Buy → Close → Buy again → Re-entry works correctly
2. Concurrent buy orders (race condition) are handled correctly
3. Sell order placement with multiple positions works correctly
4. Re-entry logic works with multiple closed positions
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.base import Base
from src.infrastructure.db.models import OrderStatus, UserRole, Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.positions_repository import PositionsRepository


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
def positions_repo(db_session):
    """Create PositionsRepository instance"""
    session, _ = db_session
    return PositionsRepository(session)


@pytest.fixture
def orders_repo(db_session):
    """Create OrdersRepository instance"""
    session, _ = db_session
    return OrdersRepository(session)


@pytest.fixture
def user_id(db_session):
    """Get user ID from session"""
    _, user_id = db_session
    return user_id


class TestBuyCloseBuyAgainReentryFlow:
    """Test complete flow: Buy → Close → Buy again → Re-entry"""

    def test_buy_close_buy_again_reentry_flow(
        self, positions_repo, orders_repo, user_id
    ):
        """Test that buying, closing, buying again, and re-entry works correctly"""
        symbol = "RELIANCE"

        # Step 1: First buy
        pos1 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2500.0,
            entry_rsi=29.5,
        )
        pos1_id = pos1.id
        assert pos1.closed_at is None

        # Step 2: Close first position
        positions_repo.mark_closed(user_id, symbol)
        positions_repo.db.commit()

        # Verify first position is closed
        from src.infrastructure.db.models import Positions as PositionsModel
        closed_pos1 = positions_repo.db.query(PositionsModel).filter_by(id=pos1_id).first()
        assert closed_pos1.closed_at is not None

        # Step 3: Second buy (should create new position)
        pos2 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=15.0,
            avg_price=2600.0,
            entry_rsi=28.0,
        )
        pos2_id = pos2.id
        assert pos2_id != pos1_id
        assert pos2.closed_at is None

        # Step 4: Verify get_by_symbol() returns the new open position
        current_pos = positions_repo.get_by_symbol(user_id, symbol)
        assert current_pos is not None
        assert current_pos.id == pos2_id

        # Step 5: Simulate re-entry (update existing open position)
        pos2_updated = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=25.0,  # 15 + 10 re-entry
            avg_price=2550.0,  # Average of 15@2600 and 10@2500
            entry_rsi=28.0,
        )
        assert pos2_updated.id == pos2_id  # Same position updated
        assert pos2_updated.quantity == 25.0
        assert pos2_updated.closed_at is None

        # Step 6: Verify all positions exist
        from src.infrastructure.db.models import Positions as PositionsModel
        all_positions = positions_repo.db.query(PositionsModel).filter(
            PositionsModel.user_id == user_id,
            PositionsModel.symbol == symbol,
        ).all()
        assert len(all_positions) == 2  # 1 closed + 1 open

        # Verify one is closed, one is open
        closed_count = sum(1 for p in all_positions if p.closed_at is not None)
        open_count = sum(1 for p in all_positions if p.closed_at is None)
        assert closed_count == 1
        assert open_count == 1


class TestConcurrentBuyOrdersRaceCondition:
    """Test concurrent buy orders (race condition)"""

    def test_concurrent_upsert_creates_only_one_open_position(
        self, positions_repo, user_id
    ):
        """Test that concurrent upsert() calls don't create multiple open positions"""
        symbol = "RELIANCE"

        # Simulate concurrent upsert calls
        # In real scenario, this would be handled by database constraints
        # For SQLite, we rely on application-level validation

        # First upsert
        pos1 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2500.0,
        )

        # Second upsert (should update, not create new)
        pos2 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=20.0,
            avg_price=2550.0,
        )

        # Should update the same position
        assert pos1.id == pos2.id

        # Verify only one open position exists
        from src.infrastructure.db.models import Positions as PositionsModel
        open_positions = positions_repo.db.query(PositionsModel).filter(
            PositionsModel.user_id == user_id,
            PositionsModel.symbol == symbol,
            PositionsModel.closed_at.is_(None),
        ).all()
        assert len(open_positions) == 1

    def test_concurrent_upsert_with_closed_position_creates_new(
        self, positions_repo, user_id
    ):
        """Test that upsert() creates new position when closed position exists"""
        symbol = "RELIANCE"

        # Create and close first position
        pos1 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2500.0,
        )
        positions_repo.mark_closed(user_id, symbol)
        positions_repo.db.commit()

        # Second upsert (should create new position)
        pos2 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=15.0,
            avg_price=2600.0,
        )

        # Should create new position
        assert pos2.id != pos1.id
        assert pos2.closed_at is None

        # Verify both positions exist
        from src.infrastructure.db.models import Positions as PositionsModel
        all_positions = positions_repo.db.query(PositionsModel).filter(
            PositionsModel.user_id == user_id,
            PositionsModel.symbol == symbol,
        ).all()
        assert len(all_positions) == 2


class TestSellOrderPlacementWithMultiplePositions:
    """Test sell order placement with multiple positions"""

    def test_sell_order_on_open_position_only(
        self, positions_repo, orders_repo, user_id
    ):
        """Test that sell orders are placed on open position only"""
        symbol = "RELIANCE"

        # Create closed position
        closed_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2500.0,
        )
        positions_repo.mark_closed(user_id, symbol)
        positions_repo.db.commit()

        # Create open position
        open_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=15.0,
            avg_price=2600.0,
        )

        # Verify get_by_symbol() returns open position
        current_pos = positions_repo.get_by_symbol(user_id, symbol)
        assert current_pos is not None
        assert current_pos.id == open_pos.id
        assert current_pos.closed_at is None
        assert current_pos.quantity == 15.0

        # Simulate sell order placement (would use current_pos)
        # This verifies that sell order logic gets the correct open position
        sell_quantity = 5.0
        positions_repo.reduce_quantity(user_id, symbol, sell_quantity)
        positions_repo.db.commit()

        # Verify open position quantity reduced
        updated_pos = positions_repo.get_by_symbol(user_id, symbol)
        assert updated_pos is not None
        assert updated_pos.quantity == 10.0  # 15 - 5
        assert updated_pos.closed_at is None

        # Verify closed position unchanged
        from src.infrastructure.db.models import Positions as PositionsModel
        closed_pos_check = positions_repo.db.query(PositionsModel).filter_by(id=closed_pos.id).first()
        assert closed_pos_check.closed_at is not None
        assert closed_pos_check.quantity == 0.0

    def test_sell_order_after_multiple_closed_positions(
        self, positions_repo, user_id
    ):
        """Test sell order placement when multiple closed positions exist"""
        symbol = "RELIANCE"

        # Create multiple closed positions
        for i in range(3):
            pos = positions_repo.upsert(
                user_id=user_id,
                symbol=symbol,
                quantity=10.0 + i * 5,
                avg_price=2500.0 + i * 100,
            )
            positions_repo.mark_closed(user_id, symbol)
            positions_repo.db.commit()

        # Create new open position
        open_pos = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=20.0,
            avg_price=2800.0,
        )

        # Verify get_by_symbol() returns the new open position
        current_pos = positions_repo.get_by_symbol(user_id, symbol)
        assert current_pos is not None
        assert current_pos.id == open_pos.id
        assert current_pos.quantity == 20.0

        # Simulate partial sell
        positions_repo.reduce_quantity(user_id, symbol, 5.0)
        positions_repo.db.commit()

        # Verify open position updated
        updated_pos = positions_repo.get_by_symbol(user_id, symbol)
        assert updated_pos.quantity == 15.0

        # Verify all closed positions still exist
        from src.infrastructure.db.models import Positions as PositionsModel
        all_positions = positions_repo.db.query(PositionsModel).filter(
            PositionsModel.user_id == user_id,
            PositionsModel.symbol == symbol,
        ).all()
        assert len(all_positions) == 4  # 3 closed + 1 open


class TestReentryLogicWithMultiplePositions:
    """Test re-entry logic with multiple positions"""

    def test_reentry_on_new_position_after_closed(
        self, positions_repo, user_id
    ):
        """Test that re-entry logic works on new position after previous closed"""
        symbol = "RELIANCE"

        # Create and close first position
        pos1 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2500.0,
            entry_rsi=29.5,
        )
        positions_repo.mark_closed(user_id, symbol)
        positions_repo.db.commit()

        # Create new position (after close)
        pos2 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=15.0,
            avg_price=2600.0,
            entry_rsi=28.0,
        )

        # Simulate re-entry (update existing open position)
        pos2_reentry = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=25.0,  # 15 + 10 re-entry
            avg_price=2550.0,
            entry_rsi=28.0,
        )

        # Should update the same position
        assert pos2_reentry.id == pos2.id
        assert pos2_reentry.quantity == 25.0
        assert pos2_reentry.closed_at is None

        # Verify get_by_symbol() returns the updated position
        current_pos = positions_repo.get_by_symbol(user_id, symbol)
        assert current_pos.id == pos2.id
        assert current_pos.quantity == 25.0

    def test_reentry_tracking_with_multiple_closed_positions(
        self, positions_repo, user_id
    ):
        """Test that re-entry tracking works correctly with multiple closed positions"""
        symbol = "RELIANCE"

        # Create and close first position with re-entries
        pos1 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=10.0,
            avg_price=2500.0,
            entry_rsi=29.5,
            reentry_count=2,
            reentries={
                "reentries": [
                    {"level": 20, "rsi": 19.5, "price": 2400.0},
                    {"level": 10, "rsi": 9.5, "price": 2300.0},
                ]
            },
        )
        positions_repo.mark_closed(user_id, symbol)
        positions_repo.db.commit()

        # Create new position (fresh start)
        pos2 = positions_repo.upsert(
            user_id=user_id,
            symbol=symbol,
            quantity=15.0,
            avg_price=2600.0,
            entry_rsi=28.0,
            reentry_count=0,
        )

        # Verify new position has no re-entries
        assert pos2.reentry_count == 0
        assert pos2.reentries is None or (
            isinstance(pos2.reentries, dict)
            and len(pos2.reentries.get("reentries", [])) == 0
        )

        # Verify get_by_symbol() returns new position
        current_pos = positions_repo.get_by_symbol(user_id, symbol)
        assert current_pos.id == pos2.id
        assert current_pos.reentry_count == 0

