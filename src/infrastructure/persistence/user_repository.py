from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from server.app.core.security import hash_password
from src.infrastructure.db.models import UserRole, Users

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Users | None:
        return self.db.get(Users, user_id)

    def get_by_email(self, email: str) -> Users | None:
        return self.db.query(Users).filter(Users.email == email).first()

    def list_users(self, active_only: bool = True) -> list[Users]:
        q = self.db.query(Users)
        if active_only:
            q = q.filter(Users.is_active.is_(True))
        return q.order_by(Users.created_at.desc()).all()

    def search_users(self, q: str, *, limit: int = 50) -> list[Users]:
        """Match email, name, or id substring (case-insensitive)."""
        needle = q.strip()
        if not needle:
            return []
        # Avoid user-supplied % / _ becoming LIKE wildcards
        safe = needle.replace("%", "").replace("_", "")
        if not safe:
            return []
        term = f"%{safe}%"
        id_filters = []
        if safe.isdigit():
            id_filters.append(Users.id == int(safe))
        id_filters.append(cast(Users.id, String).ilike(term))
        return (
            self.db.query(Users)
            .filter(
                or_(
                    Users.email.ilike(term),
                    Users.name.ilike(term),
                    *id_filters,
                )
            )
            .order_by(Users.created_at.desc())
            .limit(limit)
            .all()
        )

    def create_user(
        self,
        email: str,
        password: str,
        name: str | None = None,
        role: UserRole = UserRole.USER,
        mobile_number: str | None = None,
    ) -> Users:
        hashed = hash_password(password)
        user = Users(
            email=email,
            name=name,
            role=role,
            is_active=True,
            password_hash=hashed,
            mobile_number=mobile_number,
        )
        self.db.add(user)
        try:
            self.db.commit()
        except Exception as e:
            logger.exception("UserRepository create_user commit failed")
            raise
        self.db.refresh(user)
        return user

    def create_pending_verification_user(
        self,
        email: str,
        password: str,
        name: str,
        token_hash: str,
        sent_at: datetime,
        role: UserRole = UserRole.USER,
        mobile_number: str | None = None,
    ) -> Users:
        """Create an unverified user with a pending verification token in one commit."""
        user = Users(
            email=email,
            name=name,
            role=role,
            is_active=True,
            password_hash=hash_password(password),
            email_verified_at=None,
            email_verification_token_hash=token_hash,
            email_verification_sent_at=sent_at,
            mobile_number=mobile_number,
        )
        self.db.add(user)
        try:
            self.db.commit()
        except Exception:
            logger.exception("UserRepository create_pending_verification_user commit failed")
            raise
        self.db.refresh(user)
        return user

    def update_unverified_signup_credentials(
        self,
        user: Users,
        *,
        password: str,
        name: str,
        mobile_number: str | None = None,
    ) -> Users:
        user.name = name.strip()
        user.password_hash = hash_password(password)
        user.mobile_number = mobile_number
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_profile(
        self,
        user: Users,
        *,
        email: str | None = None,
        mobile_number: str | None = None,
        update_email: bool = False,
        update_mobile: bool = False,
        reset_email_verification: bool = False,
    ) -> Users:
        if update_mobile:
            user.mobile_number = mobile_number
        if update_email and email is not None:
            user.email = email
        if reset_email_verification:
            user.email_verified_at = None
            user.email_verification_token_hash = None
            user.email_verification_sent_at = None
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_password(self, user: Users, new_password: str) -> None:
        user.password_hash = hash_password(new_password)
        self.db.commit()

    def set_password_reset_token(self, user: Users, token_hash: str, expires_at) -> None:
        user.password_reset_token_hash = token_hash
        user.password_reset_expires_at = expires_at
        self.db.commit()

    def clear_password_reset_token(self, user: Users) -> None:
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        self.db.commit()

    def find_by_reset_token_hash(self, token_hash: str) -> Users | None:
        return (
            self.db.query(Users)
            .filter(Users.password_reset_token_hash == token_hash)
            .first()
        )

    def set_verification_token(self, user: Users, token_hash: str, sent_at) -> None:
        user.email_verification_token_hash = token_hash
        user.email_verification_sent_at = sent_at
        self.db.commit()

    def mark_email_verified(self, user: Users) -> None:
        from src.infrastructure.db.timezone_utils import ist_now_naive

        user.email_verified_at = ist_now_naive()
        user.email_verification_token_hash = None
        user.email_verification_sent_at = None
        self.db.commit()

    def clear_verification(self, user: Users) -> None:
        self.mark_email_verified(user)

    def find_by_verification_token_hash(self, token_hash: str) -> Users | None:
        return (
            self.db.query(Users)
            .filter(Users.email_verification_token_hash == token_hash)
            .first()
        )

    def update_user(
        self,
        user: Users,
        *,
        name: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> Users:
        if name is not None:
            user.name = name
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        self.db.commit()
        self.db.refresh(user)
        return user
