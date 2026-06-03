"""Who may run shared market analysis (admin-only operator, shared Signals for all users)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.infrastructure.db.models import UserRole, Users
from src.infrastructure.persistence.user_repository import UserRepository

# Must cover subprocess budget in _run_analysis_task (default 1800s) plus persistence.
ANALYSIS_RUN_ONCE_TIMEOUT_SECONDS = 1800


def is_analysis_operator(user_id: int, db: Session) -> bool:
    """Return True if this user is allowed to run the shared analysis task."""
    user = UserRepository(db).get_by_id(user_id)
    return bool(user and user.is_active and user.role == UserRole.ADMIN)


def require_analysis_operator(user_id: int, db: Session) -> Users:
    """Raise ValueError if user_id is not an active admin."""
    user = UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise ValueError("User not found or inactive")
    if user.role != UserRole.ADMIN:
        raise ValueError("Analysis is restricted to admin users")
    return user
