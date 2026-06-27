import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def is_production_env() -> bool:
    """
    True unless ENV or APP_ENV is explicitly set to a known development/local/testing environment.
    This implements a default-deny security model where unset or unknown environments
    default to production constraints.
    """
    env_val = os.getenv("ENV")
    app_env_val = os.getenv("APP_ENV")

    # Normalize env values
    envs = []
    if env_val is not None:
        envs.append(env_val.strip().lower())
    if app_env_val is not None:
        envs.append(app_env_val.strip().lower())

    if not envs:
        # Both unset -> treat as production (default-deny)
        return True

    allowed_dev_envs = {"development", "dev", "local", "test", "testing"}

    # If any set environment variable is not explicitly in the allowed dev environments,
    # treat the environment as production.
    for env in envs:
        if env not in allowed_dev_envs:
            return True

    return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # jwt_secret is expected from environment in non-dev; default is for local dev only
    jwt_secret: str = "dev-secret-change"  # noqa: S105
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = 60
    admin_email: str | None = None
    admin_password: str | None = None
    admin_name: str | None = None
    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]
    log_retention_days: int = 90
    jwt_refresh_days: int = 30
    frontend_base_url: str = "http://localhost:5173"

    # Billing (Razorpay). Enforcement off => non-admin users keep full access (backward compatible).
    subscription_enforcement_enabled: bool = False
    # ISO 8601 end instant for grandfathering full entitlements (optional)
    subscription_grandfather_until: str | None = None
    # Optional env overrides; else admin can store key id + encrypted secrets in DB (see crypto.py).
    # When True, RAZORPAY_KEY_* and RAZORPAY_WEBHOOK_SECRET env vars are ignored (DB only).
    razorpay_use_db_only: bool = False
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None

    # Auth rate limiting
    rate_limit_enabled: bool = True
    rate_limit_login_max: int = 5
    rate_limit_refresh_max: int = 20
    rate_limit_window_seconds: int = 900
    rate_limit_backend: str = "memory"  # memory | redis
    redis_url: str | None = None

    # Password hashing (PBKDF2 rounds; re-hash on login when lower)
    password_hash_rounds: int = 290000

    # Cookie-based auth (httpOnly); Bearer still supported for transition
    auth_use_cookies: bool = True
    # secure in prod, overridable in dev
    auth_cookie_secure: bool = Field(default_factory=is_production_env)
    auth_cookie_samesite: str = "lax"  # lax for dev; strict in prod HTTPS

    # MFA
    mfa_required_for_broker_mode: bool = False
    mfa_required_for_admin: bool = False

    # Registration: only allow email domains on the bundled provider allowlist
    email_domain_allowlist_enabled: bool = True
    email_domain_allowlist_extra: list[str] = []


settings = Settings()
