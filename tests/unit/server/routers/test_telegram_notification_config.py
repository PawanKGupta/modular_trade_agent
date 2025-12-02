"""
Tests for Telegram notification configuration
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.core.deps import get_current_user, get_db


def test_telegram_test_connection_success():
    """Test successful Telegram connection test"""
    
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=1, email="test@example.com")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    
    try:
        with patch("server.app.routers.notification_preferences._test_telegram_connection") as mock_test:
            # Mock successful test
            mock_test.return_value = (True, "Test message sent successfully! Check your Telegram chat.")
            
            client = TestClient(app)
            response = client.post(
                "/api/v1/user/notification-preferences/telegram/test",
                params={"bot_token": "123456:ABC-DEF", "chat_id": "123456789"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "successful" in data["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_telegram_test_connection_invalid_token():
    """Test Telegram connection with invalid bot token"""
    
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=1, email="test@example.com")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    
    try:
        with patch("server.app.routers.notification_preferences._test_telegram_connection") as mock_test:
            # Mock invalid token error
            mock_test.return_value = (False, "Invalid bot token. Please check your token. Error: Unauthorized")
            
            client = TestClient(app)
            response = client.post(
                "/api/v1/user/notification-preferences/telegram/test",
                params={"bot_token": "invalid_token", "chat_id": "123456789"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "invalid bot token" in data["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_telegram_test_connection_invalid_chat_id():
    """Test Telegram connection with invalid chat ID"""
    
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=1, email="test@example.com")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    
    try:
        with patch("server.app.routers.notification_preferences._test_telegram_connection") as mock_test:
            # Mock invalid chat ID error
            mock_test.return_value = (False, "Invalid chat ID. Make sure you've started a chat with the bot. Error: chat not found")
            
            client = TestClient(app)
            response = client.post(
                "/api/v1/user/notification-preferences/telegram/test",
                params={"bot_token": "123456:ABC-DEF", "chat_id": "invalid"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "chat" in data["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_telegram_test_connection_missing_params():
    """Test Telegram connection with missing parameters"""
    
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=1, email="test@example.com")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    
    try:
        client = TestClient(app)
        
        # Test with empty bot_token
        response = client.post(
            "/api/v1/user/notification-preferences/telegram/test",
            params={"bot_token": "", "chat_id": "123456789"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "required" in data["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_telegram_test_connection_network_error():
    """Test Telegram connection with network error"""
    
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=1, email="test@example.com")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    
    try:
        with patch("server.app.routers.notification_preferences._test_telegram_connection") as mock_test:
            # Mock network error
            mock_test.return_value = (False, "Network error: Connection failed")
            
            client = TestClient(app)
            response = client.post(
                "/api/v1/user/notification-preferences/telegram/test",
                params={"bot_token": "123456:ABC-DEF", "chat_id": "123456789"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "network" in data["message"].lower() or "error" in data["message"].lower()
    finally:
        app.dependency_overrides.clear()

