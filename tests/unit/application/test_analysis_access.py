"""Tests for admin-only analysis operator helpers."""

import pytest

from src.application.services.analysis_access import (
    ANALYSIS_RUN_ONCE_TIMEOUT_SECONDS,
    is_analysis_operator,
    require_analysis_operator,
)
from src.application.services.individual_service_manager import IndividualServiceManager
from src.infrastructure.db.models import UserRole, Users


@pytest.fixture
def regular_user(db_session):
    user = Users(
        email="user_analysis_gate@test.com",
        password_hash="hash",
        role=UserRole.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    user = Users(
        email="admin_analysis_gate@test.com",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_is_analysis_operator_true_for_admin(db_session, admin_user):
    assert is_analysis_operator(admin_user.id, db_session) is True


def test_is_analysis_operator_false_for_regular_user(db_session, regular_user):
    assert is_analysis_operator(regular_user.id, db_session) is False


def test_require_analysis_operator_raises_for_non_admin(db_session, regular_user):
    with pytest.raises(ValueError, match="restricted to admin"):
        require_analysis_operator(regular_user.id, db_session)


def test_run_once_rejects_analysis_for_non_admin(db_session, regular_user):
    manager = IndividualServiceManager(db_session)
    success, message, details = manager.run_once(regular_user.id, "analysis")
    assert success is False
    assert "admin" in message.lower()
    assert details == {}


def test_analysis_run_once_timeout_covers_subprocess_budget():
    assert ANALYSIS_RUN_ONCE_TIMEOUT_SECONDS >= 1800
