# ruff: noqa: E402, PLC0415, E501

"""Unit tests for service management API endpoints (Phase 3.1)

Tests cover:
- POST /api/v1/user/service/start
- POST /api/v1/user/service/stop
- GET /api/v1/user/service/status
- GET /api/v1/user/service/tasks
- GET /api/v1/user/service/logs
- Error handling
- Authentication/authorization
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.db.models import ServiceLog, UserRole
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def client(db_session):
    """Create test client with database override"""
    from server.app.core.deps import get_db
    from server.app.main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    from src.infrastructure.persistence import UserRepository

    repo = UserRepository(db_session)
    user = repo.create_user(
        email="test@example.com",
        password="Test123!",
        name="Test User",
        role=UserRole.USER,
    )
    return user


@pytest.fixture
def auth_token(client, test_user):
    """Get auth token for test user"""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "Test123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def test_user_with_settings(db_session, test_user):
    """Create a test user with settings"""
    from src.infrastructure.db.models import TradeMode
    from src.infrastructure.persistence.settings_repository import SettingsRepository

    settings_repo = SettingsRepository(db_session)
    settings = settings_repo.ensure_default(test_user.id)
    settings.trade_mode = TradeMode.PAPER  # Use paper mode for tests
    db_session.commit()
    db_session.refresh(settings)
    return test_user, settings


class TestServiceStartAPI:
    """Tests for service start endpoint"""

    @patch("server.app.routers.service.MultiUserTradingService")
    def test_start_service_success(
        self, mock_service_class, client, test_user_with_settings, auth_token
    ):
        """Test successful service start"""
        test_user, settings = test_user_with_settings
        mock_service = MagicMock()
        mock_service.start_service.return_value = True
        mock_service_class.return_value = mock_service

        # Override the dependency
        from server.app.main import app
        from server.app.routers.service import get_trading_service

        app.dependency_overrides[get_trading_service] = lambda: mock_service

        response = client.post(
            "/api/v1/user/service/start",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["service_running"] is True
        assert "started successfully" in data["message"]
        mock_service.start_service.assert_called_once_with(test_user.id)

        app.dependency_overrides.pop(get_trading_service, None)

    @patch("server.app.routers.service.MultiUserTradingService")
    def test_start_service_failure(
        self, mock_service_class, client, test_user_with_settings, auth_token
    ):
        """Test service start failure"""
        test_user, settings = test_user_with_settings
        mock_service = MagicMock()
        mock_service.start_service.return_value = False
        mock_service_class.return_value = mock_service

        from server.app.main import app
        from server.app.routers.service import get_trading_service

        app.dependency_overrides[get_trading_service] = lambda: mock_service

        response = client.post(
            "/api/v1/user/service/start",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["service_running"] is False

        app.dependency_overrides.pop(get_trading_service, None)

    @patch("server.app.routers.service.MultiUserTradingService")
    def test_start_service_value_error(
        self, mock_service_class, client, test_user_with_settings, auth_token
    ):
        """Test service start with ValueError (e.g., missing credentials)"""
        test_user, settings = test_user_with_settings
        mock_service = MagicMock()
        mock_service.start_service.side_effect = ValueError("No broker credentials stored")
        mock_service_class.return_value = mock_service

        from server.app.main import app
        from server.app.routers.service import get_trading_service

        app.dependency_overrides[get_trading_service] = lambda: mock_service

        response = client.post(
            "/api/v1/user/service/start",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 400
        assert "No broker credentials stored" in response.json()["detail"]

        app.dependency_overrides.pop(get_trading_service, None)

    def test_start_service_requires_auth(self, client):
        """Test that start service requires authentication"""
        response = client.post("/api/v1/user/service/start")
        assert response.status_code == 401


class TestServiceStopAPI:
    """Tests for service stop endpoint"""

    @patch("server.app.routers.service.MultiUserTradingService")
    def test_stop_service_success(self, mock_service_class, client, test_user, auth_token):
        """Test successful service stop"""
        mock_service = MagicMock()
        mock_service.stop_service.return_value = True
        mock_service_class.return_value = mock_service

        from server.app.main import app
        from server.app.routers.service import get_trading_service

        app.dependency_overrides[get_trading_service] = lambda: mock_service

        response = client.post(
            "/api/v1/user/service/stop",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["service_running"] is False
        assert "stopped successfully" in data["message"]
        mock_service.stop_service.assert_called_once_with(test_user.id)

        app.dependency_overrides.pop(get_trading_service, None)

    def test_stop_service_requires_auth(self, client):
        """Test that stop service requires authentication"""
        response = client.post("/api/v1/user/service/stop")
        assert response.status_code == 401


class TestServiceStatusAPI:
    """Tests for service status endpoint"""

    def test_get_service_status_success(self, client, db_session, test_user, auth_token):
        """Test getting service status"""
        from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository

        # Create service status
        status_repo = ServiceStatusRepository(db_session)
        status = status_repo.get_or_create(test_user.id)
        status.service_running = True
        status.last_heartbeat = ist_now()
        status.error_count = 0
        db_session.commit()

        response = client.get(
            "/api/v1/user/service/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["service_running"] is True
        assert data["error_count"] == 0
        assert "last_heartbeat" in data

    def test_get_service_status_creates_default(self, client, db_session, test_user, auth_token):
        """Test that status endpoint creates default status if none exists"""
        response = client.get(
            "/api/v1/user/service/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["service_running"] is False
        assert data["error_count"] == 0

    def test_get_service_status_requires_auth(self, client):
        """Test that get status requires authentication"""
        response = client.get("/api/v1/user/service/status")
        assert response.status_code == 401


class TestServiceTasksAPI:
    """Tests for service tasks endpoint"""

    def test_get_task_history_success(self, client, db_session, test_user, auth_token):
        """Test getting task history"""
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        task_repo = ServiceTaskRepository(db_session)
        task_repo.create(
            user_id=test_user.id,
            task_name="premarket_retry",
            status="success",
            duration_seconds=1.5,
            details={"symbols_processed": 5},
        )

        response = client.get(
            "/api/v1/user/service/tasks",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert data["total"] == 1
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_name"] == "premarket_retry"
        assert data["tasks"][0]["status"] == "success"
        assert data["tasks"][0]["duration_seconds"] == 1.5

    def test_get_task_history_with_filters(self, client, db_session, test_user, auth_token):
        """Test getting task history with filters"""
        from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

        task_repo = ServiceTaskRepository(db_session)
        # Create multiple tasks
        task_repo.create(
            user_id=test_user.id,
            task_name="premarket_retry",
            status="success",
            duration_seconds=1.5,
        )
        task_repo.create(
            user_id=test_user.id,
            task_name="analysis",
            status="failed",
            duration_seconds=2.0,
        )

        # Filter by task name
        response = client.get(
            "/api/v1/user/service/tasks?task_name=premarket_retry",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["tasks"][0]["task_name"] == "premarket_retry"

        # Filter by status
        response = client.get(
            "/api/v1/user/service/tasks?status=failed",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["tasks"][0]["status"] == "failed"

    def test_get_task_history_requires_auth(self, client):
        """Test that get tasks requires authentication"""
        response = client.get("/api/v1/user/service/tasks")
        assert response.status_code == 401


class TestServiceLogsAPI:
    """Tests for service logs endpoint"""

    def test_get_service_logs_success(self, client, db_session, test_user, auth_token):
        """Test getting service logs"""
        from src.infrastructure.persistence.service_log_repository import ServiceLogRepository

        log_repo = ServiceLogRepository(db_session)
        log_repo.create(
            user_id=test_user.id,
            level="INFO",
            module="TradingService",
            message="Service started successfully",
            context={"action": "start_service"},
        )

        response = client.get(
            "/api/v1/user/service/logs",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert data["total"] == 1
        assert len(data["logs"]) == 1
        assert data["logs"][0]["level"] == "INFO"
        assert data["logs"][0]["module"] == "TradingService"
        assert "Service started successfully" in data["logs"][0]["message"]

    def test_get_service_logs_with_filters(self, client, db_session, test_user, auth_token):
        """Test getting service logs with filters"""
        from src.infrastructure.persistence.service_log_repository import ServiceLogRepository

        log_repo = ServiceLogRepository(db_session)
        log_repo.create(
            user_id=test_user.id,
            level="INFO",
            module="TradingService",
            message="Info message",
        )
        log_repo.create(
            user_id=test_user.id,
            level="ERROR",
            module="TradingService",
            message="Error message",
        )

        # Filter by level
        response = client.get(
            "/api/v1/user/service/logs?level=ERROR",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["logs"][0]["level"] == "ERROR"

        # Filter by module
        response = client.get(
            "/api/v1/user/service/logs?module=TradingService",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Both logs are from TradingService

    def test_get_service_logs_with_hours_filter(self, client, db_session, test_user, auth_token):
        """Test getting service logs with hours filter"""
        from src.infrastructure.persistence.service_log_repository import ServiceLogRepository

        log_repo = ServiceLogRepository(db_session)
        # Create old log (outside 24 hour window)
        old_log = ServiceLog(
            user_id=test_user.id,
            level="INFO",
            module="TradingService",
            message="Old log",
            timestamp=ist_now() - timedelta(hours=25),
        )
        db_session.add(old_log)
        # Create recent log
        log_repo.create(
            user_id=test_user.id,
            level="INFO",
            module="TradingService",
            message="Recent log",
        )
        db_session.commit()

        # Get logs from last 24 hours (default)
        response = client.get(
            "/api/v1/user/service/logs",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        # Should only get the recent log
        assert data["total"] == 1
        assert "Recent log" in data["logs"][0]["message"]

    def test_get_service_logs_requires_auth(self, client):
        """Test that get logs requires authentication"""
        response = client.get("/api/v1/user/service/logs")
        assert response.status_code == 401
