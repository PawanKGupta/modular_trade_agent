"""
API Tests for Notification Preferences Endpoints

Phase 5: Notification Preferences Implementation

Tests the REST API endpoints for managing notification preferences.
"""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_get_notification_preferences_requires_auth():
    """Test that getting notification preferences requires authentication"""
    resp = client.get("/api/v1/user/notification-preferences")
    assert resp.status_code == 401


def test_get_notification_preferences_defaults(client):
    """Test getting notification preferences returns defaults for new user"""
    # Create user via signup
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "prefs1@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Get preferences
    resp = client.get(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Check defaults
    assert data["in_app_enabled"] is True
    assert data["telegram_enabled"] is False
    assert data["email_enabled"] is False
    assert data["notify_order_placed"] is True
    assert data["notify_order_modified"] is False  # Opt-in
    assert data["notify_system_warnings"] is False  # Opt-in
    assert data["notify_system_info"] is False  # Opt-in


def test_update_notification_preferences_requires_auth():
    """Test that updating notification preferences requires authentication"""
    resp = client.put(
        "/api/v1/user/notification-preferences",
        json={"telegram_enabled": True},
    )
    assert resp.status_code == 401


def test_update_notification_preferences_partial(client):
    """Test updating only some notification preferences"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "prefs2@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Update only telegram settings
    resp = client.put(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "telegram_enabled": True,
            "telegram_chat_id": "123456789",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram_enabled"] is True
    assert data["telegram_chat_id"] == "123456789"
    # Other fields should remain at defaults
    assert data["in_app_enabled"] is True
    assert data["email_enabled"] is False


def test_update_notification_preferences_all_fields(client):
    """Test updating all notification preference fields"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "prefs3@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Update all fields
    update_data = {
        "telegram_enabled": True,
        "telegram_chat_id": "987654321",
        "email_enabled": True,
        "email_address": "test@example.com",
        "in_app_enabled": True,
        "notify_order_placed": True,
        "notify_order_rejected": False,
        "notify_order_executed": True,
        "notify_order_cancelled": False,
        "notify_order_modified": True,  # Opt-in
        "notify_retry_queue_added": True,
        "notify_retry_queue_updated": False,
        "notify_retry_queue_removed": True,
        "notify_retry_queue_retried": False,
        "notify_partial_fill": True,
        "notify_system_errors": True,
        "notify_system_warnings": True,  # Opt-in
        "notify_system_info": False,
        "quiet_hours_start": "22:00:00",
        "quiet_hours_end": "08:00:00",
    }

    resp = client.put(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token}"},
        json=update_data,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify all fields were updated
    assert data["telegram_enabled"] is True
    assert data["telegram_chat_id"] == "987654321"
    assert data["email_enabled"] is True
    assert data["email_address"] == "test@example.com"
    assert data["notify_order_placed"] is True
    assert data["notify_order_rejected"] is False
    assert data["notify_order_executed"] is True
    assert data["notify_order_cancelled"] is False
    assert data["notify_order_modified"] is True
    assert data["notify_retry_queue_added"] is True
    assert data["notify_retry_queue_updated"] is False
    assert data["notify_retry_queue_removed"] is True
    assert data["notify_retry_queue_retried"] is False
    assert data["notify_partial_fill"] is True
    assert data["notify_system_errors"] is True
    assert data["notify_system_warnings"] is True
    assert data["notify_system_info"] is False
    assert data["quiet_hours_start"] == "22:00:00"
    assert data["quiet_hours_end"] == "08:00:00"


def test_update_notification_preferences_persists(client):
    """Test that updated preferences persist across requests"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "prefs4@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Update preferences
    resp = client.put(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "telegram_enabled": True,
            "notify_order_modified": True,
        },
    )
    assert resp.status_code == 200

    # Get preferences again
    resp = client.get(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram_enabled"] is True
    assert data["notify_order_modified"] is True


def test_update_notification_preferences_empty_payload(client):
    """Test that empty update payload returns current preferences"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "prefs5@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Update with empty payload
    resp = client.put(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Should return defaults
    assert data["in_app_enabled"] is True
    assert data["telegram_enabled"] is False


def test_notification_preferences_user_isolation(client):
    """Test that notification preferences are isolated per user"""
    # Create two users
    resp1 = client.post(
        "/api/v1/auth/signup", json={"email": "user1@example.com", "password": "Secret123"}
    )
    token1 = resp1.json()["access_token"]

    resp2 = client.post(
        "/api/v1/auth/signup", json={"email": "user2@example.com", "password": "Secret123"}
    )
    token2 = resp2.json()["access_token"]

    # Update user1 preferences
    client.put(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token1}"},
        json={"telegram_enabled": True, "notify_order_modified": True},
    )

    # Update user2 preferences differently
    client.put(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token2}"},
        json={"email_enabled": True, "notify_order_modified": False},
    )

    # Verify isolation
    resp1 = client.get(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token1}"},
    )
    data1 = resp1.json()
    assert data1["telegram_enabled"] is True
    assert data1["notify_order_modified"] is True
    assert data1["email_enabled"] is False

    resp2 = client.get(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token2}"},
    )
    data2 = resp2.json()
    assert data2["email_enabled"] is True
    assert data2["notify_order_modified"] is False
    assert data2["telegram_enabled"] is False


def test_update_notification_preferences_quiet_hours(client):
    """Test updating quiet hours"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "prefs6@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Set quiet hours
    resp = client.put(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "quiet_hours_start": "22:00:00",
            "quiet_hours_end": "08:00:00",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quiet_hours_start"] == "22:00:00"
    assert data["quiet_hours_end"] == "08:00:00"

    # Clear quiet hours
    resp = client.put(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "quiet_hours_start": None,
            "quiet_hours_end": None,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quiet_hours_start"] is None
    assert data["quiet_hours_end"] is None


def test_update_notification_preferences_granular_events(client):
    """Test updating granular event preferences"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "prefs7@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Disable some events, enable others
    resp = client.put(
        "/api/v1/user/notification-preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "notify_order_placed": False,
            "notify_order_executed": True,
            "notify_order_rejected": False,
            "notify_order_cancelled": True,
            "notify_order_modified": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["notify_order_placed"] is False
    assert data["notify_order_executed"] is True
    assert data["notify_order_rejected"] is False
    assert data["notify_order_cancelled"] is True
    assert data["notify_order_modified"] is True
