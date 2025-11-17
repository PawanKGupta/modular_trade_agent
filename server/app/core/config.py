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


settings = Settings()
