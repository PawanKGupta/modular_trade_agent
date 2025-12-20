"""
Test Alembic migration: migrate_positions_to_full_symbols

Tests that the migration correctly converts base symbols to full symbols.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.base import Base
from src.infrastructure.db.models import Orders, OrderStatus, Positions


@pytest.fixture
def test_db():
    """Create a temporary in-memory database for testing"""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(test_db):
    """Create a database session"""
    SessionLocal = sessionmaker(bind=test_db)
    session = SessionLocal()
    yield session
    session.close()


def test_migration_converts_base_symbols_from_matching_orders(db_session: Session):
    """Test that migration converts base symbols to full symbols from matching orders"""
    # Create test data: positions with base symbols and matching orders with full symbols
    user_id = 1

    # Create orders with full symbols
    order1 = Orders(
        user_id=user_id,
        symbol="RELIANCE-EQ",
        side="buy",
        order_type="market",
        quantity=10,
        price=2500.0,
        status=OrderStatus.ONGOING,
        placed_at=datetime(2025, 1, 15, 9, 15),
    )
    order2 = Orders(
        user_id=user_id,
        symbol="SALSTEEL-BE",
        side="buy",
        order_type="market",
        quantity=100,
        price=35.0,
        status=OrderStatus.ONGOING,
        placed_at=datetime(2025, 1, 15, 9, 20),
    )
    db_session.add_all([order1, order2])
    db_session.commit()

    # Create positions with base symbols (before migration)
    pos1 = Positions(
        user_id=user_id,
        symbol="RELIANCE",  # Base symbol
        quantity=10,
        avg_price=2500.0,
        unrealized_pnl=0.0,
        opened_at=datetime(2025, 1, 15, 9, 15),
        reentry_count=0,
    )
    pos2 = Positions(
        user_id=user_id,
        symbol="SALSTEEL",  # Base symbol
        quantity=100,
        avg_price=35.0,
        unrealized_pnl=0.0,
        opened_at=datetime(2025, 1, 15, 9, 20),
        reentry_count=0,
    )
    db_session.add_all([pos1, pos2])
    db_session.commit()

    # Run migration by directly executing SQL (simpler than mocking Alembic context)

    conn = db_session.connection()

    # Execute migration SQL directly (SQLite version)
    # Step 1: Update positions from matching orders
    conn.execute(
        text(
            """
        UPDATE positions
        SET symbol = (
            SELECT o.symbol
            FROM orders o
            WHERE o.user_id = positions.user_id
              AND o.side = 'buy'
              AND o.status = 'ongoing'
              AND UPPER(SUBSTR(o.symbol, 1, INSTR(o.symbol || '-', '-') - 1)) = \
                  UPPER(positions.symbol)
            ORDER BY o.placed_at DESC
            LIMIT 1
        )
        WHERE positions.symbol NOT LIKE '%-EQ'
          AND positions.symbol NOT LIKE '%-BE'
          AND positions.symbol NOT LIKE '%-BL'
          AND positions.symbol NOT LIKE '%-BZ'
          AND EXISTS (
              SELECT 1 FROM orders o
              WHERE o.user_id = positions.user_id
                AND o.side = 'buy'
                AND o.status = 'ongoing'
                AND UPPER(SUBSTR(o.symbol, 1, INSTR(o.symbol || '-', '-') - 1)) = \
                  UPPER(positions.symbol)
          )
    """
        )
    )

    # Step 2: Default remaining base symbols to -EQ
    conn.execute(
        text(
            """
        UPDATE positions
        SET symbol = symbol || '-EQ'
        WHERE symbol NOT LIKE '%-EQ'
          AND symbol NOT LIKE '%-BE'
          AND symbol NOT LIKE '%-BL'
          AND symbol NOT LIKE '%-BZ'
    """
        )
    )
    db_session.commit()

    # Verify positions were updated
    updated_pos1 = db_session.query(Positions).filter_by(id=pos1.id).first()
    updated_pos2 = db_session.query(Positions).filter_by(id=pos2.id).first()

    assert updated_pos1.symbol == "RELIANCE-EQ"
    assert updated_pos2.symbol == "SALSTEEL-BE"


def test_migration_defaults_to_eq_when_no_matching_order(db_session: Session):
    """Test that migration defaults to -EQ suffix when no matching order found"""
    user_id = 1

    # Create position with base symbol but NO matching order
    pos = Positions(
        user_id=user_id,
        symbol="TCS",  # Base symbol, no matching order
        quantity=50,
        avg_price=3500.0,
        unrealized_pnl=0.0,
        opened_at=datetime(2025, 1, 15, 9, 15),
        reentry_count=0,
    )
    db_session.add(pos)
    db_session.commit()

    # Run migration by directly executing SQL

    conn = db_session.connection()

    # Step 2: Default remaining base symbols to -EQ (no matching order, so skip step 1)
    conn.execute(
        text(
            """
        UPDATE positions
        SET symbol = symbol || '-EQ'
        WHERE symbol NOT LIKE '%-EQ'
          AND symbol NOT LIKE '%-BE'
          AND symbol NOT LIKE '%-BL'
          AND symbol NOT LIKE '%-BZ'
    """
        )
    )
    db_session.commit()

    # Verify position was updated with -EQ suffix
    updated_pos = db_session.query(Positions).filter_by(id=pos.id).first()
    assert updated_pos.symbol == "TCS-EQ"


def test_migration_leaves_full_symbols_unchanged(db_session: Session):
    """Test that migration leaves positions with full symbols unchanged"""
    user_id = 1

    # Create position with full symbol (already migrated)
    pos = Positions(
        user_id=user_id,
        symbol="INFY-EQ",  # Already full symbol
        quantity=20,
        avg_price=1500.0,
        unrealized_pnl=0.0,
        opened_at=datetime(2025, 1, 15, 9, 15),
        reentry_count=0,
    )
    db_session.add(pos)
    db_session.commit()
    original_symbol = pos.symbol

    # Run migration by directly executing SQL

    conn = db_session.connection()

    # Migration should skip positions that already have full symbols
    # Step 1: Update positions from matching orders (should skip INFY-EQ)
    conn.execute(
        text(
            """
        UPDATE positions
        SET symbol = (
            SELECT o.symbol
            FROM orders o
            WHERE o.user_id = positions.user_id
              AND o.side = 'buy'
              AND o.status = 'ongoing'
              AND UPPER(SUBSTR(o.symbol, 1, INSTR(o.symbol || '-', '-') - 1)) = \
                  UPPER(positions.symbol)
            ORDER BY o.placed_at DESC
            LIMIT 1
        )
        WHERE positions.symbol NOT LIKE '%-EQ'
          AND positions.symbol NOT LIKE '%-BE'
          AND positions.symbol NOT LIKE '%-BL'
          AND positions.symbol NOT LIKE '%-BZ'
          AND EXISTS (
              SELECT 1 FROM orders o
              WHERE o.user_id = positions.user_id
                AND o.side = 'buy'
                AND o.status = 'ongoing'
                AND UPPER(SUBSTR(o.symbol, 1, INSTR(o.symbol || '-', '-') - 1)) = \
                  UPPER(positions.symbol)
          )
    """
        )
    )

    # Step 2: Default remaining base symbols to -EQ (should skip INFY-EQ)
    conn.execute(
        text(
            """
        UPDATE positions
        SET symbol = symbol || '-EQ'
        WHERE symbol NOT LIKE '%-EQ'
          AND symbol NOT LIKE '%-BE'
          AND symbol NOT LIKE '%-BL'
          AND symbol NOT LIKE '%-BZ'
    """
        )
    )
    db_session.commit()

    # Verify position symbol unchanged
    updated_pos = db_session.query(Positions).filter_by(id=pos.id).first()
    assert updated_pos.symbol == original_symbol


def test_migration_handles_different_segments(db_session: Session):
    """Test that migration handles different segment suffixes (-EQ, -BE, -BL, -BZ)"""
    user_id = 1

    # Create orders with different segments
    orders = [
        Orders(
            user_id=user_id,
            symbol="STOCK1-EQ",
            side="buy",
            order_type="market",
            quantity=10,
            price=100.0,
            status=OrderStatus.ONGOING,
            placed_at=datetime(2025, 1, 15, 9, 15),
        ),
        Orders(
            user_id=user_id,
            symbol="STOCK2-BE",
            side="buy",
            order_type="market",
            quantity=20,
            price=200.0,
            status=OrderStatus.ONGOING,
            placed_at=datetime(2025, 1, 15, 9, 16),
        ),
    ]
    db_session.add_all(orders)
    db_session.commit()

    # Create positions with base symbols
    positions = [
        Positions(
            user_id=user_id,
            symbol="STOCK1",
            quantity=10,
            avg_price=100.0,
            unrealized_pnl=0.0,
            opened_at=datetime(2025, 1, 15, 9, 15),
            reentry_count=0,
        ),
        Positions(
            user_id=user_id,
            symbol="STOCK2",
            quantity=20,
            avg_price=200.0,
            unrealized_pnl=0.0,
            opened_at=datetime(2025, 1, 15, 9, 16),
            reentry_count=0,
        ),
    ]
    db_session.add_all(positions)
    db_session.commit()

    # Run migration by directly executing SQL

    conn = db_session.connection()

    # Step 1: Update positions from matching orders
    conn.execute(
        text(
            """
        UPDATE positions
        SET symbol = (
            SELECT o.symbol
            FROM orders o
            WHERE o.user_id = positions.user_id
              AND o.side = 'buy'
              AND o.status = 'ongoing'
              AND UPPER(SUBSTR(o.symbol, 1, INSTR(o.symbol || '-', '-') - 1)) = \
                  UPPER(positions.symbol)
            ORDER BY o.placed_at DESC
            LIMIT 1
        )
        WHERE positions.symbol NOT LIKE '%-EQ'
          AND positions.symbol NOT LIKE '%-BE'
          AND positions.symbol NOT LIKE '%-BL'
          AND positions.symbol NOT LIKE '%-BZ'
          AND EXISTS (
              SELECT 1 FROM orders o
              WHERE o.user_id = positions.user_id
                AND o.side = 'buy'
                AND o.status = 'ongoing'
                AND UPPER(SUBSTR(o.symbol, 1, INSTR(o.symbol || '-', '-') - 1)) = \
                  UPPER(positions.symbol)
          )
    """
        )
    )

    # Step 2: Default remaining base symbols to -EQ
    conn.execute(
        text(
            """
        UPDATE positions
        SET symbol = symbol || '-EQ'
        WHERE symbol NOT LIKE '%-EQ'
          AND symbol NOT LIKE '%-BE'
          AND symbol NOT LIKE '%-BL'
          AND symbol NOT LIKE '%-BZ'
    """
        )
    )
    db_session.commit()

    # Verify positions were updated correctly
    updated_pos1 = db_session.query(Positions).filter_by(id=positions[0].id).first()
    updated_pos2 = db_session.query(Positions).filter_by(id=positions[1].id).first()

    assert updated_pos1.symbol == "STOCK1-EQ"
    assert updated_pos2.symbol == "STOCK2-BE"


def test_migration_handles_empty_positions_table(db_session: Session):
    """Test that migration handles empty positions table"""
    # No positions in table
    positions_count = db_session.query(Positions).count()
    assert positions_count == 0

    # Run migration SQL (should not error)

    conn = db_session.connection()
    conn.execute(
        text(
            """
        UPDATE positions
        SET symbol = symbol || '-EQ'
        WHERE symbol NOT LIKE '%-EQ'
    """
        )
    )
    db_session.commit()

    # Should complete without error
    assert True
