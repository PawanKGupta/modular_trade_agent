"""
Test add_missing_broker_positions.py script

Tests that the script correctly adds positions with proper metadata.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.add_missing_broker_positions import add_missing_position  # noqa: E402
from src.infrastructure.db.base import Base  # noqa: E402
from src.infrastructure.db.models import Orders, OrderStatus, Positions  # noqa: E402


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


def test_add_missing_position_creates_order_with_correct_metadata(
    db_session: Session,
):
    """Test that add_missing_position creates order with correct metadata"""
    user_id = 1
    symbol = "ASTERDM-EQ"
    quantity = 16
    buy_price = 633.05
    trade_date = "11 Dec 2025"

    order, position = add_missing_position(
        db=db_session,
        user_id=user_id,
        symbol=symbol,
        quantity=quantity,
        buy_price=buy_price,
        trade_date=trade_date,
        dry_run=False,
    )

    # Verify order was created
    assert order is not None
    assert order.user_id == user_id
    assert order.symbol == symbol.upper()
    assert order.side == "buy"
    assert order.quantity == quantity
    assert order.price == buy_price
    assert order.status == OrderStatus.ONGOING
    assert order.entry_type == "initial"
    assert order.orig_source == "signal"
    assert "missed" in order.reason.lower() or "service" in order.reason.lower()

    # Verify order_metadata
    assert order.order_metadata is not None
    assert "ticker" in order.order_metadata
    assert "exchange" in order.order_metadata
    assert "base_symbol" in order.order_metadata
    assert "full_symbol" in order.order_metadata
    assert order.order_metadata["full_symbol"] == symbol.upper()
    assert order.order_metadata["base_symbol"] == "ASTERDM"
    assert order.order_metadata["exchange"] in ["NSE", "BSE"]


def test_add_missing_position_creates_position_with_correct_data(
    db_session: Session,
):
    """Test that add_missing_position creates position with correct data"""
    user_id = 1
    symbol = "EMKAY-BE"
    quantity = 376
    buy_price = 267.95
    trade_date = "16 Dec 2025"

    order, position = add_missing_position(
        db=db_session,
        user_id=user_id,
        symbol=symbol,
        quantity=quantity,
        buy_price=buy_price,
        trade_date=trade_date,
        dry_run=False,
    )

    # Verify position was created
    assert position is not None
    assert position.user_id == user_id
    assert position.symbol == symbol.upper()
    assert position.quantity == quantity
    assert position.avg_price == buy_price
    assert position.initial_entry_price == buy_price
    assert position.opened_at is not None


def test_add_missing_position_dry_run_does_not_create_records(
    db_session: Session,
):
    """Test that dry_run mode doesn't create any records"""
    user_id = 1
    symbol = "ASTERDM-EQ"
    quantity = 16
    buy_price = 633.05
    trade_date = "11 Dec 2025"

    order, position = add_missing_position(
        db=db_session,
        user_id=user_id,
        symbol=symbol,
        quantity=quantity,
        buy_price=buy_price,
        trade_date=trade_date,
        dry_run=True,  # Dry run
    )

    # Verify nothing was created
    assert order is None
    assert position is None

    # Verify no records in database
    orders_count = db_session.query(Orders).filter_by(user_id=user_id).count()
    positions_count = db_session.query(Positions).filter_by(user_id=user_id).count()
    assert orders_count == 0
    assert positions_count == 0


def test_add_missing_position_handles_existing_order(db_session: Session):
    """Test that script handles existing orders gracefully"""
    user_id = 1
    symbol = "ASTERDM-EQ"
    quantity = 16
    buy_price = 633.05
    trade_date = "11 Dec 2025"

    # Create existing order
    existing_order = Orders(
        user_id=user_id,
        symbol=symbol.upper(),
        side="buy",
        order_type="market",
        quantity=quantity,
        price=buy_price,
        status=OrderStatus.ONGOING,
        placed_at=datetime(2025, 12, 11, 9, 15),
        entry_type="initial",
        orig_source="signal",
    )
    db_session.add(existing_order)
    db_session.commit()

    # Try to add same position
    order, position = add_missing_position(
        db=db_session,
        user_id=user_id,
        symbol=symbol,
        quantity=quantity,
        buy_price=buy_price,
        trade_date=trade_date,
        dry_run=False,
    )

    # Should return existing order, not create duplicate
    assert order is not None
    assert order.id == existing_order.id

    # Verify only one order exists
    orders_count = (
        db_session.query(Orders).filter_by(user_id=user_id, symbol=symbol.upper()).count()
    )
    assert orders_count == 1


def test_add_missing_position_handles_existing_position(db_session: Session):
    """Test that script updates existing position if data differs"""
    user_id = 1
    symbol = "EMKAY-BE"
    quantity = 376
    buy_price = 267.95
    trade_date = "16 Dec 2025"

    # Create existing position with different quantity
    existing_position = Positions(
        user_id=user_id,
        symbol=symbol.upper(),
        quantity=300,  # Different quantity
        avg_price=250.0,  # Different price
        unrealized_pnl=0.0,
        opened_at=datetime(2025, 12, 16, 9, 15),
        reentry_count=0,
    )
    db_session.add(existing_position)
    db_session.commit()

    # Try to add same position with updated data
    order, position = add_missing_position(
        db=db_session,
        user_id=user_id,
        symbol=symbol,
        quantity=quantity,
        buy_price=buy_price,
        trade_date=trade_date,
        dry_run=False,
    )

    # Should update existing position
    assert position is not None
    assert position.id == existing_position.id
    assert position.quantity == quantity
    assert position.avg_price == buy_price

    # Verify only one position exists
    positions_count = (
        db_session.query(Positions).filter_by(user_id=user_id, symbol=symbol.upper()).count()
    )
    assert positions_count == 1


def test_add_missing_position_handles_bse_symbols(db_session: Session):
    """Test that script correctly handles BSE symbols (-BE suffix)"""
    user_id = 1
    symbol = "EMKAY-BE"  # BSE symbol
    quantity = 376
    buy_price = 267.95
    trade_date = "16 Dec 2025"

    order, position = add_missing_position(
        db=db_session,
        user_id=user_id,
        symbol=symbol,
        quantity=quantity,
        buy_price=buy_price,
        trade_date=trade_date,
        dry_run=False,
    )

    # Verify order metadata has correct exchange
    assert order.order_metadata["exchange"] == "BSE"
    assert order.order_metadata["ticker"].endswith(".BO")  # BSE ticker format


def test_add_missing_position_handles_nse_symbols(db_session: Session):
    """Test that script correctly handles NSE symbols (-EQ suffix)"""
    user_id = 1
    symbol = "ASTERDM-EQ"  # NSE symbol
    quantity = 16
    buy_price = 633.05
    trade_date = "11 Dec 2025"

    order, position = add_missing_position(
        db=db_session,
        user_id=user_id,
        symbol=symbol,
        quantity=quantity,
        buy_price=buy_price,
        trade_date=trade_date,
        dry_run=False,
    )

    # Verify order metadata has correct exchange
    assert order.order_metadata["exchange"] == "NSE"
    assert order.order_metadata["ticker"].endswith(".NS")  # NSE ticker format


def test_add_missing_position_parses_trade_date_correctly(db_session: Session):
    """Test that script correctly parses trade date and sets opened_at"""
    user_id = 1
    symbol = "ASTERDM-EQ"
    quantity = 16
    buy_price = 633.05
    trade_date = "11 Dec 2025"

    order, position = add_missing_position(
        db=db_session,
        user_id=user_id,
        symbol=symbol,
        quantity=quantity,
        buy_price=buy_price,
        trade_date=trade_date,
        dry_run=False,
    )

    # Verify opened_at is set to market open time (9:15 AM)
    assert position.opened_at is not None
    assert position.opened_at.hour == 9
    assert position.opened_at.minute == 15
    assert position.opened_at.day == 11
    assert position.opened_at.month == 12
    assert position.opened_at.year == 2025

    # Verify order placed_at matches
    assert order.placed_at == position.opened_at
