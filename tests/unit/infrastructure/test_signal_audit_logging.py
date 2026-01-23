"""
Unit tests for audit logging of signal status changes
"""

import pytest

from src.infrastructure.db.models import AuditLog, Signals, SignalStatus
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.audit_log_repository import AuditLogRepository
from src.infrastructure.persistence.signals_repository import SignalsRepository


@pytest.fixture
def signals_repo(db_session):
    return SignalsRepository(db_session)


@pytest.fixture
def audit_log_repo(db_session):
    return AuditLogRepository(db_session)


@pytest.fixture
def test_user(db_session):
    from src.infrastructure.db.models import Users

    user = Users(email="auditlog@example.com", password_hash="test_hash", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_audit_log_on_status_change(signals_repo, audit_log_repo, test_user, db_session):
    # Create a signal
    signal = Signals(symbol="TCS", status=SignalStatus.ACTIVE, ts=ist_now())
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)

    # Mark as traded
    signals_repo.mark_as_traded("TCS", user_id=test_user.id, reason="order_placed")
    audit_logs = (
        db_session.query(AuditLog).filter_by(resource_type="signal", resource_id=signal.id).all()
    )
    assert any(
        log.action == "update" and log.changes and log.changes.get("new_status") == "traded"
        for log in audit_logs
    )

    # Mark as rejected
    signals_repo.mark_as_rejected("TCS", user_id=test_user.id, reason="manual_reject")
    audit_logs = (
        db_session.query(AuditLog).filter_by(resource_type="signal", resource_id=signal.id).all()
    )
    assert any(
        log.action == "update" and log.changes and log.changes.get("new_status") == "rejected"
        for log in audit_logs
    )

    # Mark as active (reactivate) - need to mark as rejected first to reactivate
    signals_repo.mark_as_rejected("TCS", user_id=test_user.id, reason="manual_reject")
    signals_repo.mark_as_active("TCS", user_id=test_user.id, reason="manual_reactivate")
    audit_logs = (
        db_session.query(AuditLog).filter_by(resource_type="signal", resource_id=signal.id).all()
    )
    assert any(
        log.action == "update" and log.changes and log.changes.get("new_status") == "active"
        for log in audit_logs
    )

    # Mark as failed - requires signal to be TRADED first
    signals_repo.mark_as_traded("TCS", user_id=test_user.id, reason="order_placed")
    signals_repo.mark_as_failed(signal.id, test_user.id, reason="order_failed")
    audit_logs = (
        db_session.query(AuditLog).filter_by(resource_type="signal", resource_id=signal.id).all()
    )
    assert any(
        log.action == "update" and log.changes and log.changes.get("new_status") == "failed"
        for log in audit_logs
    )
