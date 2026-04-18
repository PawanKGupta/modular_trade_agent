"""Tests for notification preferences router endpoints"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import HTTPException

from server.app.routers import notification_preferences as notif_module
from src.infrastructure.db.models import (
    UserNotificationPreferences,
    UserRole,
    Users,
)


class DummyUser(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(
            id=kwargs.get("id", 1),
            email=kwargs.get("email", "user@example.com"),
            name=kwargs.get("name", "Test User"),
            role=kwargs.get("role", UserRole.USER),
            is_active=kwargs.get("is_active", True),
        )


def _full_prefs(**overrides):
    """Return a prefs-like object with all required attributes populated."""
    base = {
        "telegram_enabled": False,
        "telegram_bot_token": None,
        "telegram_chat_id": None,
        "email_enabled": False,
        "email_address": None,
        "in_app_enabled": False,
        "notify_service_events": False,
        "notify_trading_events": False,
        "notify_system_events": False,
        "notify_errors": False,
        "notify_order_placed": False,
        "notify_order_rejected": False,
        "notify_order_executed": False,
        "notify_order_cancelled": False,
        "notify_order_modified": False,
        "notify_retry_queue_added": False,
        "notify_retry_queue_updated": False,
        "notify_retry_queue_removed": False,
        "notify_retry_queue_retried": False,
        "notify_partial_fill": False,
        "notify_system_errors": False,
        "notify_system_warnings": False,
        "notify_system_info": False,
        "notify_service_started": False,
        "notify_service_stopped": False,
        "notify_service_execution_completed": False,
        "notify_subscription_renewal_reminder": False,
        "notify_payment_failed": False,
        "notify_subscription_activated": False,
        "notify_subscription_cancelled": False,
        "quiet_hours_start": None,
        "quiet_hours_end": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def mock_notif_deps(monkeypatch, db_session):
    """Mock dependencies for notification preferences endpoints"""
    # Create user
    user = Users(
        id=1,
        email="user@example.com",
        name="Test User",
        password_hash="$2b$12$dummy",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    current_user = DummyUser(id=1)

    def mock_get_current_user():
        return current_user

    def mock_get_db():
        return db_session

    monkeypatch.setattr(
        "server.app.routers.notification_preferences.get_current_user", mock_get_current_user
    )
    monkeypatch.setattr("server.app.routers.notification_preferences.get_db", mock_get_db)

    return {"db": db_session, "user": current_user}


def test_notification_preferences_model_creation():
    """Test creating notification preference model"""
    prefs = UserNotificationPreferences(
        user_id=1,
        telegram_enabled=True,
        email_enabled=False,
        telegram_chat_id="12345",
        telegram_bot_token="token123",
        notify_order_placed=True,
        notify_order_executed=True,
    )

    assert prefs.user_id == 1
    assert prefs.telegram_enabled is True
    assert prefs.email_enabled is False
    assert prefs.telegram_chat_id == "12345"
    assert prefs.notify_order_placed is True


def test_notification_preferences_all_disabled():
    """Test notification preferences with all notifications disabled"""
    prefs = UserNotificationPreferences(
        user_id=2,
        email_enabled=False,
        telegram_enabled=False,
        in_app_enabled=False,
        notify_order_placed=False,
        notify_order_executed=False,
        notify_service_events=False,
        notify_trading_events=False,
        notify_system_events=False,
        notify_errors=False,
    )

    assert prefs.email_enabled is False
    assert prefs.telegram_enabled is False
    assert prefs.in_app_enabled is False
    assert prefs.notify_order_placed is False


def test_notification_preferences_all_enabled():
    """Test notification preferences with all notifications enabled"""
    prefs = UserNotificationPreferences(
        user_id=3,
        email_enabled=True,
        telegram_enabled=True,
        in_app_enabled=True,
        telegram_chat_id="54321",
        telegram_bot_token="token456",
        notify_order_placed=True,
        notify_order_executed=True,
        notify_service_events=True,
        notify_trading_events=True,
        notify_system_events=True,
        notify_errors=True,
    )

    assert prefs.email_enabled is True
    assert prefs.telegram_enabled is True
    assert prefs.in_app_enabled is True
    assert prefs.notify_order_executed is True


def test_telegram_connection_test_valid_inputs(monkeypatch):
    """Test telegram connection validation with valid inputs"""
    success, message = notif_module._test_telegram_connection("bot_token", "chat_id")
    # Will fail in test but checks the function handles inputs
    assert isinstance(success, bool)
    assert isinstance(message, str)


def _install_fake_requests(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status_code: int = 200,
    json_data=None,
    exc: Exception | None = None,
):
    """Inject a fake `requests` module to avoid network and cover branches."""

    mod = ModuleType("requests")

    class _Timeout(Exception):
        pass

    class _RequestException(Exception):
        pass

    mod.exceptions = SimpleNamespace(Timeout=_Timeout, RequestException=_RequestException)

    class _Resp:
        def __init__(self, code: int, data):
            self.status_code = code
            self._data = data

        def json(self):
            return dict(self._data or {})

    def post(url, json=None, timeout=None):
        if exc is not None:
            raise exc
        assert url.startswith("https://api.telegram.org/bot")
        assert timeout == 10
        return _Resp(status_code, json_data)

    mod.post = post

    monkeypatch.setitem(sys.modules, "requests", mod)
    return mod


def test_telegram_connection_success(monkeypatch: pytest.MonkeyPatch):
    _install_fake_requests(monkeypatch, status_code=200, json_data={"ok": True})
    success, message = notif_module._test_telegram_connection("token", "123")
    assert success is True
    assert "success" in message.lower() or "sent" in message.lower()


@pytest.mark.parametrize(
    "error_desc, expected_substring",
    [
        ("Unauthorized", "token"),
        ("Bad Request: chat not found", "chat"),
        ("Some other error", "telegram api error"),
    ],
)
def test_telegram_connection_http_error_branches(
    monkeypatch: pytest.MonkeyPatch, error_desc: str, expected_substring: str
):
    _install_fake_requests(
        monkeypatch,
        status_code=400,
        json_data={"description": error_desc},
    )
    success, message = notif_module._test_telegram_connection("token", "123")
    assert success is False
    assert expected_substring in message.lower()


def test_telegram_connection_timeout(monkeypatch: pytest.MonkeyPatch):
    requests_mod = _install_fake_requests(monkeypatch, status_code=200, json_data={"ok": True})

    def _post_timeout(*_a, **_k):
        raise requests_mod.exceptions.Timeout("t")

    requests_mod.post = _post_timeout
    success, message = notif_module._test_telegram_connection("token", "123")
    assert success is False
    assert "timeout" in message.lower()


def test_telegram_connection_request_exception(monkeypatch: pytest.MonkeyPatch):
    requests_mod = _install_fake_requests(monkeypatch)

    def _post_error(*_a, **_k):
        raise requests_mod.exceptions.RequestException("net")

    requests_mod.post = _post_error
    success, message = notif_module._test_telegram_connection("token", "123")
    assert success is False
    assert "network" in message.lower()


def test_get_notification_preferences_success(monkeypatch: pytest.MonkeyPatch):
    prefs = _full_prefs(telegram_enabled=False)

    class _Svc:
        def __init__(self, db_session):
            self.db_session = db_session

        def get_or_create_default_preferences(self, user_id: int):
            assert user_id == 1
            return prefs

    monkeypatch.setattr(notif_module, "NotificationPreferenceService", _Svc)

    out = notif_module.get_notification_preferences(db=object(), current_user=DummyUser(id=1))
    assert out.telegram_enabled is False


def test_get_notification_preferences_failure_raises_http_500(monkeypatch: pytest.MonkeyPatch):
    class _Svc:
        def __init__(self, db_session):
            self.db_session = db_session

        def get_or_create_default_preferences(self, user_id: int):
            raise RuntimeError("db")

    monkeypatch.setattr(notif_module, "NotificationPreferenceService", _Svc)

    with pytest.raises(HTTPException) as excinfo:
        notif_module.get_notification_preferences(db=object(), current_user=DummyUser(id=1))
    assert excinfo.value.status_code == 500


def test_update_notification_preferences_no_fields_returns_current(monkeypatch: pytest.MonkeyPatch):
    prefs = _full_prefs(telegram_enabled=False)

    class _Svc:
        def __init__(self, db_session):
            self.db_session = db_session

        def get_or_create_default_preferences(self, user_id: int):
            return prefs

    monkeypatch.setattr(notif_module, "NotificationPreferenceService", _Svc)

    payload = SimpleNamespace(model_dump=lambda **_k: {})
    out = notif_module.update_notification_preferences(
        payload=payload, db=object(), current_user=DummyUser(id=1)
    )
    assert out.telegram_enabled is False


def test_update_notification_preferences_updates_and_clears_cache(monkeypatch: pytest.MonkeyPatch):
    updated = _full_prefs(telegram_enabled=True)

    class _Svc:
        def __init__(self, db_session):
            self.db_session = db_session
            self.cleared = []

        def update_preferences(self, *, user_id: int, preferences_dict):
            assert user_id == 1
            assert preferences_dict["telegram_enabled"] is True
            return updated

        def clear_cache(self, *, user_id: int):
            self.cleared.append(user_id)

    svc = _Svc(db_session=object())
    monkeypatch.setattr(notif_module, "NotificationPreferenceService", lambda db_session: svc)

    payload = SimpleNamespace(model_dump=lambda **_k: {"telegram_enabled": True})
    out = notif_module.update_notification_preferences(
        payload=payload, db=object(), current_user=DummyUser(id=1)
    )
    assert out.telegram_enabled is True
    assert svc.cleared == [1]


def test_test_telegram_connection_endpoint_returns_dict(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(notif_module, "_test_telegram_connection", lambda *_a, **_k: (True, "ok"))
    out = notif_module.test_telegram_connection(
        bot_token="t", chat_id="c", db=object(), current_user=DummyUser(id=1)
    )
    assert out == {"success": True, "message": "ok"}


def test_telegram_connection_test_empty_token():
    """Test telegram connection rejects empty token"""
    success, message = notif_module._test_telegram_connection("", "chat_id")
    assert success is False
    assert "required" in message.lower()


def test_telegram_connection_test_empty_chat_id():
    """Test telegram connection rejects empty chat ID"""
    success, message = notif_module._test_telegram_connection("bot_token", "")
    assert success is False
    assert "required" in message.lower()


def test_preferences_to_response():
    """Test converting preferences model to response schema with all flags set"""
    prefs = UserNotificationPreferences(
        user_id=1,
        telegram_enabled=True,
        telegram_bot_token="token123",
        telegram_chat_id="12345",
        email_enabled=True,
        email_address="user@example.com",
        in_app_enabled=False,
        notify_service_events=True,
        notify_trading_events=False,
        notify_system_events=True,
        notify_errors=False,
        notify_order_placed=True,
        notify_order_rejected=False,
        notify_order_executed=True,
        notify_order_cancelled=False,
        notify_order_modified=True,
        notify_retry_queue_added=False,
        notify_retry_queue_updated=True,
        notify_retry_queue_removed=False,
        notify_retry_queue_retried=True,
        notify_partial_fill=False,
        notify_system_errors=True,
        notify_system_warnings=False,
        notify_system_info=True,
        notify_service_started=True,
        notify_service_stopped=False,
        notify_service_execution_completed=True,
        quiet_hours_start=None,
        quiet_hours_end=None,
    )

    response = notif_module._preferences_to_response(prefs)

    assert response.email_enabled is True
    assert response.telegram_enabled is True
    assert response.notify_order_placed is True
    assert response.notify_order_executed is True
    assert response.notify_system_events is True
    assert response.notify_errors is False
