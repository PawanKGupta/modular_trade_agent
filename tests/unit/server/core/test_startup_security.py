"""Production startup secret guards."""

import pytest

from server.app.core import startup_security


def test_is_production_detects_env(monkeypatch):
    # Unset defaults to production (default-deny)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    assert startup_security.is_production() is True

    # Explicit dev/local environments are treated as dev (non-production)
    monkeypatch.setenv("ENV", "development")
    assert startup_security.is_production() is False

    monkeypatch.setenv("ENV", "local")
    assert startup_security.is_production() is False

    # Unknown or production environments are treated as production
    monkeypatch.setenv("ENV", "production")
    assert startup_security.is_production() is True

    monkeypatch.setenv("ENV", "staging")
    assert startup_security.is_production() is True


def test_validate_production_secrets_exits_on_default_jwt(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BROKER_SECRET_KEY", raising=False)
    from server.app.core import config

    monkeypatch.setattr(config.settings, "jwt_secret", "dev-secret-change")
    monkeypatch.setattr(config.settings, "auth_cookie_secure", True)
    with pytest.raises(SystemExit):
        startup_security.validate_production_secrets()


def test_validate_production_secrets_ok_in_dev(monkeypatch):
    # Require explicit dev environment opt-in to bypass validation when defaults are active
    monkeypatch.setenv("ENV", "development")
    startup_security.validate_production_secrets()


def test_validate_production_secrets_exits_on_insecure_cookie(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    # A non-empty value is all the encryption-key check needs (presence, not validity),
    # so use an obviously-fake placeholder rather than a real-looking Fernet key.
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", "placeholder-not-a-real-key")
    from server.app.core import config

    monkeypatch.setattr(config.settings, "jwt_secret", "non-default-test-jwt-secret")
    monkeypatch.setattr(config.settings, "auth_cookie_secure", False)

    with pytest.raises(SystemExit):
        startup_security.validate_production_secrets()
