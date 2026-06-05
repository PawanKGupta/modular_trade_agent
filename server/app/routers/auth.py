# ruff: noqa: B008
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application.services.auth_email_service import AuthEmailService
from src.infrastructure.db.models import UserRole, Users
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.user_repository import UserRepository

from ..core.auth_tokens import (
    RESET_TOKEN_HOURS,
    auth_sent_at,
    generate_token,
    hash_token,
    is_expired,
    is_rate_limited,
    is_still_valid,
    is_verification_expired,
    reset_expiry,
)
from ..core.config import settings
from ..core.deps import get_current_user, get_db
from ..core.security import create_jwt_token, decode_token, verify_password
from ..core.user_verification import require_verified_email, user_is_email_verified
from ..schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    RefreshRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
    VerifyEmailRequest,
)

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

FORGOT_PASSWORD_MESSAGE = (
    "If an account exists for that email, we sent password reset instructions."
)
SIGNUP_VERIFY_MESSAGE = (
    "Account created. Check your email and click the verification link before logging in."
)
RESEND_VERIFICATION_MESSAGE = (
    "If an account exists and is not yet verified, we sent a verification link."
)


def _issue_tokens(user: Users) -> TokenResponse:
    access_token = create_jwt_token(
        str(user.id),
        extra={"uid": user.id, "roles": [user.role.value]},
    )
    refresh_token = create_jwt_token(
        str(user.id),
        extra={"uid": user.id, "roles": [user.role.value], "type": "refresh"},
        expires_days=settings.jwt_refresh_days,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


def _send_verification(user_repo: UserRepository, user: Users, email_service: AuthEmailService) -> None:
    if is_rate_limited(user.email_verification_sent_at):
        return
    token = generate_token()
    user_repo.set_verification_token(user, hash_token(token), auth_sent_at())
    email_service.send_verification_email(user.email, token)


def _signup_message_response() -> SignupResponse:
    return SignupResponse(message=SIGNUP_VERIFY_MESSAGE)


@router.post("/signup", response_model=SignupResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    try:
        user_repo = UserRepository(db)
        existing = user_repo.get_by_email(payload.email)
        email_service = AuthEmailService()
        if existing:
            if user_is_email_verified(existing):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
                )
            if not existing.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
                )
            user_repo.update_unverified_signup_credentials(
                existing, password=payload.password, name=payload.name
            )
            _send_verification(user_repo, existing, email_service)
            logger.info("Unverified signup refresh user_id=%s — verification email sent", existing.id)
            return _signup_message_response()
        token = generate_token()
        user = user_repo.create_pending_verification_user(
            email=payload.email,
            password=payload.password,
            name=payload.name,
            token_hash=hash_token(token),
            sent_at=auth_sent_at(),
            role=UserRole.USER,
        )
        logger.info("User created id=%s, creating default settings...", user.id)
        SettingsRepository(db).ensure_default(user.id)
        email_service.send_verification_email(user.email, token)
        logger.info("Signup success user_id=%s — verification email sent", user.id)
        return _signup_message_response()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Signup failed: {e}")
        raise HTTPException(status_code=500, detail="Signup failed") from e


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(payload.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        pwh = user.password_hash or ""
        is_passlib_hash = (
            pwh.startswith("$2a$")
            or pwh.startswith("$2b$")
            or pwh.startswith("$2y$")
            or pwh.startswith("$bcrypt-sha256$")
            or pwh.startswith("$pbkdf2-sha256$")
        )
        if not is_passlib_hash:
            if payload.password == pwh:
                user_repo.set_password(user, payload.password)
                logger.info(f"Upgraded password hash for user id={user.id}")
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
                )
        elif not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        require_verified_email(user)
        return _issue_tokens(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Login failed")
        raise HTTPException(status_code=500, detail="Login failed") from e


@router.get("/me", response_model=MeResponse)
def me(current: Users = Depends(get_current_user)):
    return MeResponse(
        id=current.id,
        email=current.email,
        name=current.name,
        roles=[current.role.value],
        email_verified=user_is_email_verified(current),
    )


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    current: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_repo = UserRepository(db)
    if not verify_password(payload.current_password, current.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )
    user_repo.set_password(current, payload.new_password)
    return MessageResponse(message="Password updated successfully")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(payload.email)
    if user and user.is_active:
        if is_still_valid(user.password_reset_expires_at):
            sent_at = user.password_reset_expires_at - timedelta(hours=RESET_TOKEN_HOURS)
            if is_rate_limited(sent_at):
                return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)
        token = generate_token()
        expires_at = reset_expiry()
        user_repo.set_password_reset_token(user, hash_token(token), expires_at)
        AuthEmailService().send_password_reset_email(user.email, token)
    return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    token_hash = hash_token(payload.token)
    user = user_repo.find_by_reset_token_hash(token_hash)
    if not user or not user.password_reset_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link",
        )
    if is_expired(user.password_reset_expires_at):
        user_repo.clear_password_reset_token(user)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link",
        )
    user_repo.set_password(user, payload.new_password)
    user_repo.clear_password_reset_token(user)
    return MessageResponse(message="Password reset successfully")


@router.post("/verify-email", response_model=TokenResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    token_hash = hash_token(payload.token)
    user = user_repo.find_by_verification_token_hash(token_hash)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )
    if is_verification_expired(user.email_verification_sent_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )
    user_repo.clear_verification(user)
    return _issue_tokens(user)


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(payload.email)
    if user and user.is_active and not user_is_email_verified(user):
        if is_rate_limited(user.email_verification_sent_at):
            return MessageResponse(message=RESEND_VERIFICATION_MESSAGE)
        _send_verification(user_repo, user, AuthEmailService())
    return MessageResponse(message=RESEND_VERIFICATION_MESSAGE)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    """
    Exchange a valid refresh token for a new access token pair.
    """
    try:
        if not payload.refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Missing refresh token"
            )
        decoded = decode_token(payload.refresh_token)
        if not decoded or decoded.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        user_id = decoded.get("uid")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        user = UserRepository(db).get_by_id(int(user_id))
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        require_verified_email(user)
        return _issue_tokens(user)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Refresh token exchange failed")
        raise HTTPException(status_code=500, detail="Refresh failed") from exc
