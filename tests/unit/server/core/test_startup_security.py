"""Production startup secret guards."""

import pytest

from server.app.core import startup_security


def test_is_production_detects_env(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    assert startup_security.is_production() is False
    monkeypatch.setenv("ENV", "production")
    assert startup_security.is_production() is True


def test_validate_production_secrets_exits_on_default_jwt(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("APP_DATA_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("BROKER_SECRET_KEY", raising=False)
    from server.app.core import config

    monkeypatch.setattr(config.settings, "jwt_secret", "dev-secret-change")
    with pytest.raises(SystemExit):
        startup_security.validate_production_secrets()


def test_validate_production_secrets_ok_in_dev(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    startup_security.validate_production_secrets()
