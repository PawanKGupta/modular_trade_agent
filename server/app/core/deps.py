# ruff: noqa: B008
from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.application.services.subscription_entitlement_service import SubscriptionEntitlementService
from src.infrastructure.db.models import UserRole, Users
from src.infrastructure.db.session import get_session
from src.infrastructure.persistence.user_repository import UserRepository

from .auth_cookies import get_access_token_from_request
from .config import settings
from .security import decode_token
from .user_verification import require_verified_email

_PASSWORD_CHANGE_ALLOWED_PATHS = frozenset(
    {
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
    }
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    yield from get_session()


def _resolve_bearer_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return get_access_token_from_request(request)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Users:
    token = _resolve_bearer_token(request, credentials)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("type") in ("refresh", "mfa"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("uid")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = UserRepository(db).get_by_id(int(user_id))
    if not user or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    token_tv = payload.get("tv")
    user_tv = getattr(user, "token_version", 0) or 0
    if token_tv is not None and int(token_tv) != int(user_tv):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    require_verified_email(user)
    if user.must_change_password and request.url.path not in _PASSWORD_CHANGE_ALLOWED_PATHS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required before continuing",
        )
    return user


def require_admin(user: Users = Depends(get_current_user)) -> Users:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    if settings.mfa_required_for_admin and not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA must be enabled for admin access",
        )
    return user


def require_entitlement(feature: str):
    """
    Require an active subscription feature (see SubscriptionEntitlementService).
    Usage: Depends(require_entitlement("broker_execution"))
    """

    def _check(
        user: Users = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Users:
        if not SubscriptionEntitlementService(db).user_has_feature(user, feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Active subscription with '{feature}' is required",
            )
        return user

    return _check
