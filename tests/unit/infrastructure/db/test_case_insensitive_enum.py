"""
Tests for CaseInsensitiveEnum to ensure it doesn't introduce bugs.
"""

import pytest
from sqlalchemy import Column, Integer, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.infrastructure.db.base import Base
from src.infrastructure.db.case_insensitive_enum import CaseInsensitiveEnum
from src.infrastructure.db.models import SignalStatus


class TestSignal(Base):
    __tablename__ = "test_signals"

    id = Column(Integer, primary_key=True)
    status = Column(CaseInsensitiveEnum(SignalStatus), nullable=False)


@pytest.fixture
def db_session():
    """Create an in-memory database for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    # Use project's Base which includes all models (needed for ensure_system_user)
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


def test_process_bind_param_with_none():
    """Test process_bind_param handles None value"""
    converter = CaseInsensitiveEnum(SignalStatus)
    result = converter.process_bind_param(None, None)
    assert result is None


def test_process_bind_param_with_string_matching_value():
    """Test process_bind_param with string that matches enum value"""
    converter = CaseInsensitiveEnum(SignalStatus)
    # Test lowercase value
    result = converter.process_bind_param("active", None)
    assert result == "active"
    # Test uppercase value (should match and return lowercase)
    result = converter.process_bind_param("ACTIVE", None)
    assert result == "active"


def test_process_bind_param_with_string_matching_name():
    """Test process_bind_param with string that matches enum name but not value"""
    converter = CaseInsensitiveEnum(SignalStatus)
    # If we pass a string that matches the name, it should find by name and return value
    # SignalStatus.ACTIVE has value "active", so "ACTIVE" (name) should match and return "active"
    result = converter.process_bind_param("ACTIVE", None)  # Matches name
    assert result == "active"  # Returns value


def test_process_bind_param_with_non_string_non_enum():
    """Test process_bind_param with value that's neither enum nor string"""
    converter = CaseInsensitiveEnum(SignalStatus)
    # Should return value as-is
    result = converter.process_bind_param(123, None)
    assert result == 123


def test_process_result_value_with_none():
    """Test process_result_value handles None"""
    converter = CaseInsensitiveEnum(SignalStatus)
    result = converter.process_result_value(None, None)
    assert result is None


def test_process_result_value_with_enum_instance():
    """Test process_result_value with already enum instance"""
    converter = CaseInsensitiveEnum(SignalStatus)
    result = converter.process_result_value(SignalStatus.ACTIVE, None)
    assert result == SignalStatus.ACTIVE


def test_process_result_value_with_non_string():
    """Test process_result_value with non-string value"""
    converter = CaseInsensitiveEnum(SignalStatus)
    result = converter.process_result_value(123, None)
    assert result == 123


def test_process_result_value_with_invalid_value():
    """Test process_result_value with value that doesn't match any enum"""
    converter = CaseInsensitiveEnum(SignalStatus)
    # Should try direct lookup, fail, and return value as-is
    result = converter.process_result_value("invalid_status", None)
    assert result == "invalid_status"


def test_find_enum_member_by_value():
    """Test _find_enum_member finds enum by value (case-insensitive)"""
    converter = CaseInsensitiveEnum(SignalStatus)
    # Test lowercase
    result = converter._find_enum_member("active")
    assert result == SignalStatus.ACTIVE
    # Test uppercase
    result = converter._find_enum_member("ACTIVE")
    assert result == SignalStatus.ACTIVE


def test_find_enum_member_by_name():
    """Test _find_enum_member finds enum by name when value doesn't match"""
    converter = CaseInsensitiveEnum(SignalStatus)
    # This should match by name (case-insensitive)
    # SignalStatus.ACTIVE has name "ACTIVE" and value "active"
    result = converter._find_enum_member("ACTIVE")  # Matches name
    assert result == SignalStatus.ACTIVE


def test_find_enum_member_not_found():
    """Test _find_enum_member returns None when no match found"""
    converter = CaseInsensitiveEnum(SignalStatus)
    result = converter._find_enum_member("nonexistent")
    assert result is None
