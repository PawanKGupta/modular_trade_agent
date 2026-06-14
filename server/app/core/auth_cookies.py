"""HttpOnly cookie helpers for JWT auth."""

from __future__ import annotations

from fastapi import Request, Response

from .config import settings

ACCESS_COOKIE = "ta_access"
REFRESH_COOKIE = "ta_refresh"
CSRF_COOKIE = "ta_csrf"
CSRF_HEADER = "X-CSRF-Token"


def _cookie_secure() -> bool:
    return settings.auth_cookie_secure


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str | None = None,
) -> None:
    """Set httpOnly auth cookies on the response."""
    if not settings.auth_use_cookies:
        return
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite=settings.auth_cookie_samesite,
        max_age=settings.jwt_access_minutes * 60,
        path="/api/v1",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite=settings.auth_cookie_samesite,
        max_age=settings.jwt_refresh_days * 86400,
        path="/api/v1/auth",
    )
    if csrf_token:
        response.set_cookie(
            key=CSRF_COOKIE,
            value=csrf_token,
            httponly=False,
            secure=_cookie_secure(),
            samesite=settings.auth_cookie_samesite,
            max_age=settings.jwt_refresh_days * 86400,
            path="/api/v1",
        )


def clear_auth_cookies(response: Response) -> None:
    """Remove auth cookies on logout."""
    for name, path in (
        (ACCESS_COOKIE, "/api/v1"),
        (REFRESH_COOKIE, "/api/v1/auth"),
        (CSRF_COOKIE, "/api/v1"),
    ):
        response.delete_cookie(key=name, path=path)


def get_access_token_from_request(request: Request) -> str | None:
    """Read access token from cookie when cookie auth is enabled."""
    if settings.auth_use_cookies:
        token = request.cookies.get(ACCESS_COOKIE)
        if token:
            return token
    return None


def get_refresh_token_from_request(request: Request) -> str | None:
    """Read refresh token from cookie."""
    if settings.auth_use_cookies:
        return request.cookies.get(REFRESH_COOKIE)
    return None


def validate_csrf(request: Request) -> bool:
    """Double-submit CSRF check for cookie-based mutating requests."""
    if not settings.auth_use_cookies:
        return True
    cookie_val = request.cookies.get(CSRF_COOKIE)
    header_val = request.headers.get(CSRF_HEADER)
    if not cookie_val or not header_val:
        return False
    return cookie_val == header_val
