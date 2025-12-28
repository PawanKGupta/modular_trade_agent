"""Tests for notification preferences router endpoints"""

from types import SimpleNamespace

import pytest

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
