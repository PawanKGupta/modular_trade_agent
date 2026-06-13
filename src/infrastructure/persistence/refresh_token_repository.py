"""Repository for refresh token rotation and reuse detection."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from server.app.core.config import settings
from src.infrastructure.db.models import RefreshToken
from src.infrastructure.db.timezone_utils import as_ist_aware, ist_now, ist_now_naive


class RefreshTokenRepository:
    """Manage refresh token families for rotation and revocation."""

    def __init__(self, db: Session):
        self.db = db

    def create_family(self, user_id: int, token_hash: str) -> RefreshToken:
        """Store initial refresh token for a new session family."""
        family_id = str(uuid.uuid4())
        expires_at = ist_now_naive() + timedelta(days=settings.jwt_refresh_days)
        row = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def find_active_by_hash(self, token_hash: str) -> RefreshToken | None:
        row = (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
            .first()
        )
        if not row:
            return None
        if row.expires_at and as_ist_aware(row.expires_at) < ist_now():
            return None
        return row

    def find_any_by_hash(self, token_hash: str) -> RefreshToken | None:
        return (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )

    def rotate(self, old_row: RefreshToken, new_token_hash: str) -> RefreshToken:
        """Revoke old token and issue new one in the same family."""
        old_row.revoked_at = ist_now_naive()
        expires_at = ist_now_naive() + timedelta(days=settings.jwt_refresh_days)
        new_row = RefreshToken(
            user_id=old_row.user_id,
            token_hash=new_token_hash,
            family_id=old_row.family_id,
            expires_at=expires_at,
        )
        self.db.add(new_row)
        self.db.commit()
        self.db.refresh(new_row)
        return new_row

    def revoke_family(self, family_id: str) -> int:
        """Revoke all tokens in a family (reuse detection)."""
        now = ist_now_naive()
        rows = (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .all()
        )
        for row in rows:
            row.revoked_at = now
        self.db.commit()
        return len(rows)

    def revoke_all_for_user(self, user_id: int) -> int:
        """Revoke every active refresh token for a user."""
        now = ist_now_naive()
        rows = (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .all()
        )
        for row in rows:
            row.revoked_at = now
        self.db.commit()
        return len(rows)

    def list_active_families(self, user_id: int) -> list[str]:
        stmt = (
            select(RefreshToken.family_id)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .distinct()
        )
        return list(self.db.execute(stmt).scalars().all())
