"""
API Tests for Notifications Endpoints

Tests the REST API endpoints for managing in-app notifications.
"""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_get_notifications_requires_auth():
    """Test that getting notifications requires authentication"""
    resp = client.get("/api/v1/user/notifications")
    assert resp.status_code == 401


def test_get_notifications_empty(client):
    """Test getting notifications for a new user (should be empty)"""
    # Create user via signup
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "notif1@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Get notifications
    resp = client.get(
        "/api/v1/user/notifications",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_notifications_with_filters(client):
    """Test getting notifications with filters"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "notif2@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Get notifications with type filter
    resp = client.get(
        "/api/v1/user/notifications?type=service",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

    # Get notifications with level filter
    resp = client.get(
        "/api/v1/user/notifications?level=info",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

    # Get notifications with read filter
    resp = client.get(
        "/api/v1/user/notifications?read=false",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_get_unread_notifications(client):
    """Test getting unread notifications"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "notif3@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Get unread notifications
    resp = client.get(
        "/api/v1/user/notifications/unread",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # All should be unread (empty list for new user)
    for notification in data:
        assert notification["read"] is False


def test_get_notification_count(client):
    """Test getting notification count"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "notif4@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Get notification count
    resp = client.get(
        "/api/v1/user/notifications/count",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "unread_count" in data
    assert isinstance(data["unread_count"], int)
    assert data["unread_count"] >= 0


def test_mark_notification_read_requires_auth():
    """Test that marking notification as read requires authentication"""
    resp = client.post("/api/v1/user/notifications/1/read")
    assert resp.status_code == 401


def test_mark_notification_read_not_found(client):
    """Test marking a non-existent notification as read"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "notif5@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Try to mark non-existent notification as read
    resp = client.post(
        "/api/v1/user/notifications/99999/read",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_mark_all_notifications_read(client):
    """Test marking all notifications as read"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "notif6@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Mark all as read (should work even with no notifications)
    resp = client.post(
        "/api/v1/user/notifications/read-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "marked_read" in data
    assert isinstance(data["marked_read"], int)


def test_notifications_user_isolation(client):
    """Test that notifications are isolated per user"""
    # Create two users
    resp1 = client.post(
        "/api/v1/auth/signup", json={"email": "user1@example.com", "password": "Secret123"}
    )
    token1 = resp1.json()["access_token"]

    resp2 = client.post(
        "/api/v1/auth/signup", json={"email": "user2@example.com", "password": "Secret123"}
    )
    token2 = resp2.json()["access_token"]

    # Get notifications for both users (should be empty)
    resp1 = client.get(
        "/api/v1/user/notifications",
        headers={"Authorization": f"Bearer {token1}"},
    )
    data1 = resp1.json()
    assert isinstance(data1, list)

    resp2 = client.get(
        "/api/v1/user/notifications",
        headers={"Authorization": f"Bearer {token2}"},
    )
    data2 = resp2.json()
    assert isinstance(data2, list)

    # Both should be empty for new users
    assert len(data1) == 0
    assert len(data2) == 0


def test_notifications_response_structure(client):
    """Test that notification response has correct structure"""
    # Create user
    resp = client.post(
        "/api/v1/auth/signup", json={"email": "notif7@example.com", "password": "Secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Get notifications
    resp = client.get(
        "/api/v1/user/notifications",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

    # If there are notifications, verify structure
    if len(data) > 0:
        notification = data[0]
        required_fields = [
            "id",
            "user_id",
            "type",
            "level",
            "title",
            "message",
            "read",
            "read_at",
            "created_at",
            "telegram_sent",
            "email_sent",
            "in_app_delivered",
        ]
        for field in required_fields:
            assert field in notification, f"Missing field: {field}"

        # Verify types
        assert isinstance(notification["id"], int)
        assert isinstance(notification["user_id"], int)
        assert notification["type"] in ["service", "trading", "system", "error"]
        assert notification["level"] in ["info", "warning", "error", "critical"]
        assert isinstance(notification["title"], str)
        assert isinstance(notification["message"], str)
        assert isinstance(notification["read"], bool)
        assert isinstance(notification["telegram_sent"], bool)
        assert isinstance(notification["email_sent"], bool)
        assert isinstance(notification["in_app_delivered"], bool)
