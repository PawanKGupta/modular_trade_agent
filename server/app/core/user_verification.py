"""Shared email verification checks for auth routes and dependencies."""

from src.infrastructure.db.models import Users

EMAIL_NOT_VERIFIED_DETAIL = (
    "Please verify your email before logging in. Check your inbox or request a new verification link."
)


def user_is_email_verified(user: Users) -> bool:
    """True when verified, or legacy/admin account without a pending verification token."""
    if user.email_verified_at is not None:
        return True
    return user.email_verification_token_hash is None


def require_verified_email(user: Users) -> None:
    from fastapi import HTTPException, status

    if not user_is_email_verified(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=EMAIL_NOT_VERIFIED_DETAIL,
        )
