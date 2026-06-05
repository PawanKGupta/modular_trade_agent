"""Helpers for creating test users directly via UserRepository."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.infrastructure.db.models import UserRole, Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.user_repository import UserRepository


def ensure_email_verified(user: Users, db: Session | None = None) -> Users:
    """Set email_verified_at when missing (API auth and JWT tests require verified users)."""
    if user.email_verified_at is None:
        user.email_verified_at = ist_now()
        if db is not None:
            db.add(user)
            db.commit()
            db.refresh(user)
    return user


def create_verified_user(
    repo: UserRepository,
    email: str,
    password: str,
    *,
    name: str | None = None,
    role: UserRole = UserRole.USER,
) -> Users:
    """Create a user marked verified, matching admin/bootstrap and legacy backfill behavior."""
    user = repo.create_user(email=email, password=password, name=name, role=role)
    repo.mark_email_verified(user)
    return user
