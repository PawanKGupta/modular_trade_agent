# ruff: noqa: B008
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from src.application.services.auth_email_service import AuthEmailService
from src.infrastructure.db.models import Orders, PnlDaily, TradeMode, UserRole, Users
from src.infrastructure.persistence.refresh_token_repository import RefreshTokenRepository
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.user_repository import UserRepository

from ..core.audit import record_audit, record_audit_user
from ..core.auth_cookies import (
    clear_auth_cookies,
    get_refresh_token_from_request,
    validate_csrf,
)
from ..core.auth_session import issue_tokens, rotate_refresh_token
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
from ..core.mfa import (
    backup_codes_from_json,
    backup_codes_to_json,
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    generate_backup_codes,
    generate_totp_secret,
    get_totp_uri,
    hash_backup_codes,
    verify_backup_code,
    verify_totp,
)
from ..core.rate_limit import (
    check_rate_limit,
    clear_rate_limit,
    login_failure_detail,
    record_rate_limit_failure,
)
from ..core.security import (
    create_jwt_token,
    decode_token,
    is_passlib_password_hash,
    password_needs_rehash,
    verify_password,
)
from ..core.user_verification import require_verified_email, user_is_email_verified
from ..schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    MfaDisableRequest,
    MfaLoginRequest,
    MfaSetupResponse,
    MfaVerifyRequest,
    ProfileUpdateResponse,
    RefreshRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
    UpdateProfileRequest,
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
PROFILE_UPDATED_MESSAGE = "Profile updated successfully."
PROFILE_EMAIL_VERIFY_MESSAGE = (
    "Profile updated. Check your new email and click the verification link before using the app."
)
PROFILE_EMAIL_SEND_FAILED_MESSAGE = (
    "Could not send verification email. Your email address was not changed. Try again later."
)
PROFILE_EMAIL_PASSWORD_REQUIRED = "Current password is required to change email"


def _send_verification(user_repo: UserRepository, user: Users, email_service: AuthEmailService) -> None:
    if is_rate_limited(user.email_verification_sent_at):
        return
    token = generate_token()
    user_repo.set_verification_token(user, hash_token(token), auth_sent_at())
    email_service.send_verification_email(user.email, token)


def _send_verification_to_new_email(
    user_repo: UserRepository,
    user: Users,
    new_email: str,
    email_service: AuthEmailService,
) -> None:
    token = generate_token()
    sent = email_service.send_verification_email(new_email, token)
    if not sent and email_service.is_smtp_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=PROFILE_EMAIL_SEND_FAILED_MESSAGE,
        )
    user_repo.update_profile(
        user,
        email=new_email,
        update_email=True,
        reset_email_verification=True,
    )
    user_repo.set_verification_token(user, hash_token(token), auth_sent_at())


def _signup_message_response() -> SignupResponse:
    return SignupResponse(message=SIGNUP_VERIFY_MESSAGE)


def _maybe_rehash_password(user_repo: UserRepository, user: Users, plain: str) -> None:
    if password_needs_rehash(user.password_hash):
        user_repo.set_password(user, plain)


def _issue_mfa_challenge(user: Users) -> TokenResponse:
    mfa_token = create_jwt_token(
        str(user.id),
        extra={"uid": user.id, "type": "mfa"},
        expires_minutes=5,
        token_version=getattr(user, "token_version", 0) or 0,
    )
    return TokenResponse(
        access_token="",
        refresh_token=None,
        mfa_required=True,
        mfa_token=mfa_token,
    )


def _verify_mfa_code(user: Users, code: str) -> bool:
    secret = decrypt_mfa_secret(user.mfa_secret_encrypted)
    if secret and verify_totp(secret, code):
        return True
    hashes = backup_codes_from_json(user.mfa_backup_codes_hash)
    idx = verify_backup_code(code, hashes)
    if idx is not None:
        hashes.pop(idx)
        user.mfa_backup_codes_hash = backup_codes_to_json(hashes)
        return True
    return False


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
                existing,
                password=payload.password,
                name=payload.name,
                mobile_number=payload.mobile_number,
            )
            _send_verification(user_repo, existing, email_service)
            return _signup_message_response()
        token = generate_token()
        user = user_repo.create_pending_verification_user(
            email=payload.email,
            password=payload.password,
            name=payload.name,
            token_hash=hash_token(token),
            sent_at=auth_sent_at(),
            role=UserRole.USER,
            mobile_number=payload.mobile_number,
        )
        SettingsRepository(db).ensure_default(user.id)
        email_service.send_verification_email(user.email, token)
        return _signup_message_response()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Signup failed: %s", e)
        raise HTTPException(status_code=500, detail="Signup failed") from e


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    check_rate_limit(
        request,
        "login",
        payload.email.lower(),
        max_attempts=settings.rate_limit_login_max,
    )
    try:
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(payload.email)
        if not user or not user.is_active or user.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=login_failure_detail(request, payload.email),
            )
        if not is_passlib_password_hash(user.password_hash or ""):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=login_failure_detail(request, payload.email),
            )
        if not verify_password(payload.password, user.password_hash):
            record_audit(
                db,
                user_id=user.id,
                action="login",
                resource_type="user",
                request=request,
                changes={"success": False},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=login_failure_detail(request, payload.email),
            )
        _maybe_rehash_password(user_repo, user, payload.password)
        require_verified_email(user)
        clear_rate_limit(request, "login", payload.email.lower())
        record_audit(
            db,
            user_id=user.id,
            action="login",
            resource_type="user",
            request=request,
            changes={"success": True},
        )
        if user.mfa_enabled:
            return _issue_mfa_challenge(user)
        return issue_tokens(db, user, response=response)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Login failed")
        raise HTTPException(status_code=500, detail="Login failed") from e


@router.post("/mfa/login", response_model=TokenResponse)
def mfa_login(
    payload: MfaLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    decoded = decode_token(payload.mfa_token)
    if not decoded or decoded.get("type") != "mfa":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA session")
    user_id = decoded.get("uid")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA session")
    user = UserRepository(db).get_by_id(int(user_id))
    if not user or not user.is_active or not user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA session")
    if not _verify_mfa_code(user, payload.code):
        record_rate_limit_failure(request, "mfa", str(user.id))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
    db.commit()
    return issue_tokens(db, user, response=response)


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(current: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA already enabled")
    secret = generate_totp_secret()
    backup = generate_backup_codes()
    current.mfa_secret_encrypted = encrypt_mfa_secret(secret)
    current.mfa_backup_codes_hash = backup_codes_to_json(hash_backup_codes(backup))
    db.commit()
    return MfaSetupResponse(
        secret=secret,
        provisioning_uri=get_totp_uri(secret, current.email),
        backup_codes=backup,
    )


@router.post("/mfa/verify", response_model=MessageResponse)
def mfa_verify(
    payload: MfaVerifyRequest,
    current: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    secret = decrypt_mfa_secret(current.mfa_secret_encrypted)
    if not secret or not verify_totp(secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")
    current.mfa_enabled = True
    db.commit()
    return MessageResponse(message="MFA enabled successfully")


@router.post("/mfa/disable", response_model=MessageResponse)
def mfa_disable(
    payload: MfaDisableRequest,
    current: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password")
    if not _verify_mfa_code(current, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")
    current.mfa_enabled = False
    current.mfa_secret_encrypted = None
    current.mfa_backup_codes_hash = None
    db.commit()
    return MessageResponse(message="MFA disabled")


@router.get("/me", response_model=MeResponse)
def me(current: Users = Depends(get_current_user)):
    return MeResponse(
        id=current.id,
        email=current.email,
        name=current.name,
        mobile_number=current.mobile_number,
        roles=[current.role.value],
        email_verified=user_is_email_verified(current),
        must_change_password=current.must_change_password,
        mfa_enabled=current.mfa_enabled,
    )


@router.patch("/profile", response_model=ProfileUpdateResponse)
def update_profile(
    payload: UpdateProfileRequest,
    request: Request,
    current: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if settings.auth_use_cookies and not validate_csrf(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    user_repo = UserRepository(db)
    fields_set = payload.model_fields_set
    update_mobile = "mobile_number" in fields_set
    update_email = "email" in fields_set and payload.email is not None
    new_email = str(payload.email).strip() if update_email else None
    email_changed = (
        update_email
        and new_email is not None
        and new_email.lower() != (current.email or "").lower()
    )

    if email_changed:
        existing = user_repo.get_by_email(new_email)
        if existing and existing.id != current.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        if not payload.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=PROFILE_EMAIL_PASSWORD_REQUIRED,
            )
        if not verify_password(payload.current_password, current.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

    mobile_value = payload.mobile_number if update_mobile else None
    if email_changed:
        email_service = AuthEmailService()
        _send_verification_to_new_email(user_repo, current, new_email, email_service)
        if update_mobile:
            user_repo.update_profile(current, mobile_number=mobile_value, update_mobile=True)
        record_audit_user(
            db,
            current,
            action="update",
            resource_type="user",
            request=request,
            changes={"email_changed": True},
        )
    elif update_mobile:
        user_repo.update_profile(current, mobile_number=mobile_value, update_mobile=True)

    verification_required = email_changed
    message = PROFILE_EMAIL_VERIFY_MESSAGE if email_changed else PROFILE_UPDATED_MESSAGE
    return ProfileUpdateResponse(
        message=message,
        email=current.email,
        mobile_number=current.mobile_number,
        email_verified=user_is_email_verified(current),
        verification_required=verification_required,
    )


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if settings.auth_use_cookies and not validate_csrf(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
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
    RefreshTokenRepository(db).revoke_all_for_user(current.id)
    record_audit_user(
        db,
        current,
        action="update",
        resource_type="user",
        request=request,
        changes={"password_changed": True},
    )
    return MessageResponse(message="Password updated successfully")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    check_rate_limit(
        request,
        "forgot",
        payload.email.lower(),
        max_attempts=settings.rate_limit_login_max,
    )
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
    RefreshTokenRepository(db).revoke_all_for_user(user.id)
    return MessageResponse(message="Password reset successfully")


@router.post("/verify-email", response_model=TokenResponse)
def verify_email(
    payload: VerifyEmailRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user_repo = UserRepository(db)
    token_hash = hash_token(payload.token)
    user = user_repo.find_by_verification_token_hash(token_hash)
    if not user or not user.is_active:
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
    return issue_tokens(db, user, response=response)


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    check_rate_limit(
        request,
        "resend",
        payload.email.lower(),
        max_attempts=settings.rate_limit_login_max,
    )
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(payload.email)
    if user and user.is_active and not user_is_email_verified(user):
        if is_rate_limited(user.email_verification_sent_at):
            return MessageResponse(message=RESEND_VERIFICATION_MESSAGE)
        _send_verification(user_repo, user, AuthEmailService())
    return MessageResponse(message=RESEND_VERIFICATION_MESSAGE)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    payload: RefreshRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        check_rate_limit(
            request,
            "refresh",
            get_client_ip_safe(request),
            max_attempts=settings.rate_limit_refresh_max,
        )
        refresh_raw = payload.refresh_token or get_refresh_token_from_request(request)
        if not refresh_raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Missing refresh token"
            )
        decoded = decode_token(refresh_raw)
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
        token_tv = decoded.get("tv")
        user_tv = getattr(user, "token_version", 0) or 0
        if token_tv is not None and int(token_tv) != int(user_tv):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
        require_verified_email(user)
        return rotate_refresh_token(db, user, refresh_raw, response=response)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Refresh token exchange failed")
        raise HTTPException(status_code=500, detail="Refresh failed") from exc


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    current: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    refresh_raw = get_refresh_token_from_request(request)
    if refresh_raw:
        repo = RefreshTokenRepository(db)
        row = repo.find_any_by_hash(hash_token(refresh_raw))
        if row:
            repo.revoke_family(row.family_id)
    clear_auth_cookies(response)
    record_audit_user(
        db,
        current,
        action="logout",
        resource_type="user",
        request=request,
    )
    return MessageResponse(message="Logged out")


@router.get("/export")
def export_account_data(
    current: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export user profile and trading summary (broker creds redacted)."""
    orders = (
        db.query(Orders)
        .filter(Orders.user_id == current.id)
        .order_by(Orders.placed_at.desc())
        .limit(5000)
        .all()
    )
    pnl = db.query(PnlDaily).filter(PnlDaily.user_id == current.id).all()
    settings_row = SettingsRepository(db).get_by_user_id(current.id)
    return {
        "profile": {
            "id": current.id,
            "email": current.email,
            "name": current.name,
            "mobile_number": current.mobile_number,
            "role": current.role.value,
            "created_at": current.created_at.isoformat() if current.created_at else None,
        },
        "settings": {
            "trade_mode": settings_row.trade_mode.value if settings_row else None,
            "broker": settings_row.broker if settings_row else None,
            "broker_creds_stored": bool(settings_row and settings_row.broker_creds_encrypted),
        },
        "orders": [
            {
                "symbol": o.symbol,
                "side": o.side,
                "quantity": o.quantity,
                "status": o.status.value,
                "placed_at": o.placed_at.isoformat() if o.placed_at else None,
            }
            for o in orders
        ],
        "pnl_daily": [
            {
                "date": str(p.date),
                "realized_pnl": p.realized_pnl,
                "unrealized_pnl": p.unrealized_pnl,
            }
            for p in pnl
        ],
    }


@router.delete("/account", response_model=MessageResponse)
def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    response: Response,
    current: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if settings.auth_use_cookies and not validate_csrf(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    if not verify_password(payload.current_password, current.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password")
    if current.mfa_enabled:
        if not payload.code or not _verify_mfa_code(current, payload.code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA code required")
        db.commit()
    settings_row = SettingsRepository(db).get_by_user_id(current.id)
    if settings_row:
        settings_row.broker_creds_encrypted = None
        settings_row.trade_mode = TradeMode.PAPER
    RefreshTokenRepository(db).revoke_all_for_user(current.id)
    UserRepository(db).soft_delete_user(current)
    clear_auth_cookies(response)
    record_audit_user(
        db,
        current,
        action="delete",
        resource_type="user",
        request=request,
        resource_id=current.id,
    )
    return MessageResponse(message="Account deleted")


def get_client_ip_safe(request: Request) -> str:
    from ..core.rate_limit import get_client_ip

    return get_client_ip(request)
