from pydantic_settings import BaseSettings, SettingsConfigDict


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
    auth_cookie_secure: bool = False  # set True in production behind HTTPS
    auth_cookie_samesite: str = "lax"  # lax for dev; strict in prod HTTPS

    # MFA
    mfa_required_for_broker_mode: bool = False
    mfa_required_for_admin: bool = False

    # Registration: reject known disposable / temporary email domains
    block_disposable_emails: bool = True
    disposable_email_allowlist: list[str] = []


settings = Settings()
