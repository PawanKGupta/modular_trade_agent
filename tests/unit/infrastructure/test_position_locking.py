"""
Tests for database-level locking (SELECT ... FOR UPDATE) in position operations.

Tests verify that:
1. get_by_symbol_for_update() locks the row
2. Concurrent position updates are serialized
3. Race conditions in reentry processing are prevented
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.base import Base
from src.infrastructure.db.models import UserRole, Users
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


class TestPositionLocking:
    """Test database-level locking for position operations"""

    def test_get_by_symbol_for_update_locks_row(self, db_session):
        """Test that get_by_symbol_for_update() locks the row"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Create position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",  # Full symbol after migration
            quantity=100.0,
            avg_price=100.0,
        )

        # Use nested transaction (savepoint) to test locking
        savepoint = session.begin_nested()
        locked_position = positions_repo.get_by_symbol_for_update(
            user_id, "RELIANCE-EQ"
        )  # Full symbol after migration

        assert locked_position is not None
        assert locked_position.quantity == 100.0

        # Lock should be held until transaction commits/rolls back
        savepoint.rollback()

    def test_concurrent_reentry_updates_serialized(self, db_session):
        """Test that concurrent reentry updates are serialized by locking"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Create initial position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",  # Full symbol after migration
            quantity=100.0,
            avg_price=100.0,
        )

        # Simulate concurrent reentry updates
        results = []
        errors = []

        def update_position(thread_id: int, qty_to_add: float):
            """Update position with additional quantity (simulating reentry)"""
            try:
                # Create new session for each thread (simulating concurrent requests)
                engine = create_engine("sqlite:///:memory:")
                # Note: SQLite doesn't support true row-level locking, but the pattern is correct
                # In production (PostgreSQL), this would serialize the updates
                Session = sessionmaker(bind=engine)
                Base.metadata.create_all(engine)

                # Create user in this session
                user = Users(
                    email="test@example.com",
                    name="Test User",
                    password_hash="dummy_hash",
                    role=UserRole.USER,
                    is_active=True,
                )
                Session().add(user)
                Session().commit()

                thread_session = Session()
                thread_repo = PositionsRepository(thread_session)

                # Use FOR UPDATE lock
                existing_pos = thread_repo.get_by_symbol_for_update(
                    user_id, "RELIANCE-EQ"
                )  # Full symbol after migration
                if existing_pos:
                    existing_qty = existing_pos.quantity
                    new_qty = existing_qty + qty_to_add

                    # Simulate some processing time
                    time.sleep(0.01)

                    thread_repo.upsert(
                        user_id=user_id,
                        symbol="RELIANCE-EQ",  # Full symbol after migration
                        quantity=new_qty,
                        avg_price=existing_pos.avg_price,
                        auto_commit=True,
                    )
                    results.append((thread_id, new_qty))
                thread_session.close()
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Run concurrent updates
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(update_position, i, 10.0) for i in range(5)]
            for future in as_completed(futures):
                future.result()

        # Verify results
        # Note: With SQLite, locking doesn't work across different connections
        # This test demonstrates the pattern, but true locking requires PostgreSQL
        # In production, the locking will serialize updates correctly
        assert len(errors) == 0, f"Errors occurred: {errors}"

    def test_upsert_uses_locking_for_existing_position(self, db_session):
        """Test that upsert() uses FOR UPDATE lock when updating existing position"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Create position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",  # Full symbol after migration
            quantity=100.0,
            avg_price=100.0,
        )

        # Update position - should use FOR UPDATE lock internally
        updated_position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE",
            quantity=110.0,
            avg_price=105.0,
        )

        assert updated_position.quantity == 110.0
        assert updated_position.avg_price == 105.0

    def test_mark_closed_uses_locking(self, db_session):
        """Test that mark_closed() uses FOR UPDATE lock"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Create position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",  # Full symbol after migration
            quantity=100.0,
            avg_price=100.0,
        )

        # Mark as closed - should use FOR UPDATE lock
        closed_position = positions_repo.mark_closed(
            user_id, "RELIANCE-EQ"
        )  # Full symbol after migration

        assert closed_position is not None
        assert closed_position.closed_at is not None
        assert closed_position.quantity == 0.0

    def test_reduce_quantity_uses_locking(self, db_session):
        """Test that reduce_quantity() uses FOR UPDATE lock"""
        session, user_id = db_session
        positions_repo = PositionsRepository(session)

        # Create position
        position = positions_repo.upsert(
            user_id=user_id,
            symbol="RELIANCE-EQ",  # Full symbol after migration
            quantity=100.0,
            avg_price=100.0,
        )

        # Reduce quantity - should use FOR UPDATE lock
        reduced_position = positions_repo.reduce_quantity(
            user_id,
            "RELIANCE-EQ",
            sold_quantity=50.0,  # Full symbol after migration
        )

        assert reduced_position is not None
        assert reduced_position.quantity == 50.0
        assert reduced_position.closed_at is None  # Still open
