"""
Tests for CaseInsensitiveEnum to ensure it doesn't introduce bugs.
"""

import pytest
from sqlalchemy import Column, Integer, create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.infrastructure.db.case_insensitive_enum import CaseInsensitiveEnum
from src.infrastructure.db.models import SignalStatus

Base = declarative_base()


class TestSignal(Base):
    __tablename__ = "test_signals"

    id = Column(Integer, primary_key=True)
    status = Column(CaseInsensitiveEnum(SignalStatus), nullable=False)


@pytest.fixture
def db_session():
    """Create an in-memory database for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_case_insensitive_enum_stores_lowercase_values(db_session: Session):
    """Test that enum values are stored as lowercase in database"""
    signal = TestSignal(status=SignalStatus.ACTIVE)
    db_session.add(signal)
    db_session.commit()

    # Check raw database value
    result = db_session.execute(
        text("SELECT status FROM test_signals WHERE id = :id"), {"id": signal.id}
    ).fetchone()
    assert result[0] == "active"  # Should be lowercase value, not "ACTIVE"


def test_case_insensitive_enum_reads_lowercase_values(db_session: Session):
    """Test that lowercase database values are correctly converted to enum"""
    # Insert lowercase value directly
    db_session.execute(
        text("INSERT INTO test_signals (status) VALUES (:status)"), {"status": "active"}
    )
    db_session.commit()

    # Read back and verify it's converted to enum
    signal = db_session.query(TestSignal).first()
    assert signal.status == SignalStatus.ACTIVE
    assert isinstance(signal.status, SignalStatus)


def test_case_insensitive_enum_reads_uppercase_values(db_session: Session):
    """Test that CaseInsensitiveEnum can handle uppercase values in process_result_value"""
    # Note: After migration, database should only have lowercase values
    # This test verifies our handler can convert uppercase if needed (legacy data)
    # SQLAlchemy validates before process_result_value, so we test the handler directly
    converter = CaseInsensitiveEnum(SignalStatus)

    # Test that our handler can convert uppercase to enum
    enum_value = converter.process_result_value("ACTIVE", None)
    assert enum_value == SignalStatus.ACTIVE

    # Test lowercase (normal case)
    enum_value_lower = converter.process_result_value("active", None)
    assert enum_value_lower == SignalStatus.ACTIVE


def test_case_insensitive_enum_all_statuses(db_session: Session):
    """Test all enum values work correctly"""
    statuses = [
        SignalStatus.ACTIVE,
        SignalStatus.EXPIRED,
        SignalStatus.TRADED,
        SignalStatus.REJECTED,
    ]

    for status in statuses:
        signal = TestSignal(status=status)
        db_session.add(signal)
    db_session.commit()

    # Verify all were stored correctly
    signals = db_session.query(TestSignal).all()
    assert len(signals) == 4
    for signal in signals:
        assert isinstance(signal.status, SignalStatus)
        assert signal.status in statuses


def test_case_insensitive_enum_comparison_works(db_session: Session):
    """Test that enum comparisons work correctly after reading from DB"""
    signal = TestSignal(status=SignalStatus.ACTIVE)
    db_session.add(signal)
    db_session.commit()

    # Refresh to read from DB
    db_session.refresh(signal)

    # Comparisons should work
    assert signal.status == SignalStatus.ACTIVE
    assert signal.status != SignalStatus.EXPIRED
    assert signal.status in [SignalStatus.ACTIVE, SignalStatus.TRADED]


def test_case_insensitive_enum_query_filtering(db_session: Session):
    """Test that query filtering with enum works correctly"""
    # Add signals with different statuses
    db_session.add(TestSignal(status=SignalStatus.ACTIVE))
    db_session.add(TestSignal(status=SignalStatus.EXPIRED))
    db_session.add(TestSignal(status=SignalStatus.ACTIVE))
    db_session.commit()

    # Query with enum comparison
    active_signals = (
        db_session.query(TestSignal).filter(TestSignal.status == SignalStatus.ACTIVE).all()
    )

    assert len(active_signals) == 2
    for signal in active_signals:
        assert signal.status == SignalStatus.ACTIVE


def test_case_insensitive_enum_in_clause(db_session: Session):
    """Test that 'in' clause with enum list works correctly"""
    # Add signals with different statuses
    db_session.add(TestSignal(status=SignalStatus.ACTIVE))
    db_session.add(TestSignal(status=SignalStatus.EXPIRED))
    db_session.add(TestSignal(status=SignalStatus.TRADED))
    db_session.commit()

    # Query with 'in' clause
    filtered_signals = (
        db_session.query(TestSignal)
        .filter(TestSignal.status.in_([SignalStatus.ACTIVE, SignalStatus.TRADED]))
        .all()
    )

    assert len(filtered_signals) == 2
    statuses = {s.status for s in filtered_signals}
    assert statuses == {SignalStatus.ACTIVE, SignalStatus.TRADED}
