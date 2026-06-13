"""Session token issuance with refresh rotation and cookies."""

from __future__ import annotations

import secrets

from fastapi import Response
from sqlalchemy.orm import Session

from server.app.core.auth_cookies import set_auth_cookies
from server.app.core.auth_tokens import hash_token
from server.app.core.config import settings
from server.app.core.security_metrics import increment as security_metric_increment
from server.app.core.security import create_jwt_token
from server.app.schemas.auth import TokenResponse
from src.infrastructure.db.models import Users
from src.infrastructure.persistence.refresh_token_repository import RefreshTokenRepository


def _refresh_token_extra(user: Users) -> dict:
    """Build refresh JWT claims; jti ensures each rotation gets a unique DB hash."""
    return {
        "uid": user.id,
        "roles": [user.role.value],
        "type": "refresh",
        "jti": secrets.token_urlsafe(16),
    }


def issue_tokens(
    db: Session,
    user: Users,
    *,
    response: Response | None = None,
) -> TokenResponse:
    """Issue access + refresh JWT pair and persist refresh token hash for rotation."""
    tv = getattr(user, "token_version", 0) or 0
    access_token = create_jwt_token(
        str(user.id),
        extra={"uid": user.id, "roles": [user.role.value]},
        token_version=tv,
    )
    refresh_raw = create_jwt_token(
        str(user.id),
        extra=_refresh_token_extra(user),
        expires_days=settings.jwt_refresh_days,
        token_version=tv,
    )
    RefreshTokenRepository(db).create_family(user.id, hash_token(refresh_raw))
    csrf = secrets.token_urlsafe(32) if settings.auth_use_cookies else None
    if response is not None:
        set_auth_cookies(
            response,
            access_token=access_token,
            refresh_token=refresh_raw,
            csrf_token=csrf,
        )
    return TokenResponse(access_token=access_token, refresh_token=refresh_raw, csrf_token=csrf)


def rotate_refresh_token(
    db: Session,
    user: Users,
    refresh_raw: str,
    *,
    response: Response | None = None,
) -> TokenResponse:
    """Validate refresh token, rotate family, return new pair."""
    repo = RefreshTokenRepository(db)
    token_hash = hash_token(refresh_raw)
    active = repo.find_active_by_hash(token_hash)
    if not active:
        revoked = repo.find_any_by_hash(token_hash)
        if revoked and revoked.revoked_at is not None:
            repo.revoke_family(revoked.family_id)
            from src.infrastructure.persistence.user_repository import UserRepository

            UserRepository(db).bump_token_version(user)
            security_metric_increment("refresh_token_reuse")
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    tv = getattr(user, "token_version", 0) or 0
    access_token = create_jwt_token(
        str(user.id),
        extra={"uid": user.id, "roles": [user.role.value]},
        token_version=tv,
    )
    new_refresh = create_jwt_token(
        str(user.id),
        extra=_refresh_token_extra(user),
        expires_days=settings.jwt_refresh_days,
        token_version=tv,
    )
    repo.rotate(active, hash_token(new_refresh))
    csrf = secrets.token_urlsafe(32) if settings.auth_use_cookies else None
    if response is not None:
        set_auth_cookies(
            response,
            access_token=access_token,
            refresh_token=new_refresh,
            csrf_token=csrf,
        )
    return TokenResponse(access_token=access_token, refresh_token=new_refresh, csrf_token=csrf)
