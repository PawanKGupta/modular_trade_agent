"""Unit tests for trading configuration API endpoints (Phase 1.4)

Tests cover:
- GET /api/v1/user/trading-config
- PUT /api/v1/user/trading-config
- POST /api/v1/user/trading-config/reset
- Validation logic
- Error handling
"""

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.db.models import UserRole
from src.infrastructure.persistence.config_factory import create_default_user_config


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
def test_user_with_config(db_session, test_user):
    """Create a test user with trading config"""
    config = create_default_user_config(test_user.id)
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return test_user, config


@pytest.fixture
def auth_token(client, test_user):
    """Get auth token for test user"""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "Test123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


class TestTradingConfigAPI:
    """Tests for trading configuration API endpoints"""

    def test_get_trading_config_creates_default(self, client, test_user, auth_token):
        """Test that GET creates default config if none exists"""
        response = client.get(
            "/api/v1/user/trading-config",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rsi_period"] == 10
        assert data["user_capital"] == 100000.0
        assert data["max_portfolio_size"] == 6
        assert data["chart_quality_enabled"] is True

    def test_get_trading_config_returns_existing(
        self, client, db_session, test_user_with_config, auth_token
    ):
        """Test GET returns existing config"""
        test_user, config = test_user_with_config
        # Modify config
        config.rsi_period = 14
        config.user_capital = 300000.0
        db_session.commit()

        response = client.get(
            "/api/v1/user/trading-config",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rsi_period"] == 14
        assert data["user_capital"] == 300000.0

    def test_update_trading_config_partial(self, client, test_user_with_config, auth_token):
        """Test partial update of trading config"""
        response = client.put(
            "/api/v1/user/trading-config",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "rsi_period": 14,
                "user_capital": 300000.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rsi_period"] == 14
        assert data["user_capital"] == 300000.0
        # Other fields should remain unchanged
        assert data["max_portfolio_size"] == 6

    def test_update_trading_config_full(self, client, test_user_with_config, auth_token):
        """Test full update of trading config"""
        response = client.put(
            "/api/v1/user/trading-config",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "rsi_period": 20,
                "rsi_oversold": 25.0,
                "user_capital": 500000.0,
                "max_portfolio_size": 10,
                "chart_quality_enabled": False,
                "ml_enabled": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rsi_period"] == 20
        assert data["rsi_oversold"] == 25.0
        assert data["user_capital"] == 500000.0
        assert data["max_portfolio_size"] == 10
        assert data["chart_quality_enabled"] is False
        assert data["ml_enabled"] is True

    def test_update_trading_config_validation_rsi_order(
        self, client, test_user_with_config, auth_token
    ):
        """Test that RSI thresholds must be in correct order"""
        # Update with invalid order (extreme > oversold)
        # First set oversold to a value, then try to set extreme higher
        response = client.put(
            "/api/v1/user/trading-config",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "rsi_oversold": 25.0,  # Set oversold first
            },
        )
        assert response.status_code == 200

        # Now try to set extreme higher than oversold
        response = client.put(
            "/api/v1/user/trading-config",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "rsi_extreme_oversold": 30.0,  # Should be < oversold (25.0)
            },
        )

        assert response.status_code == 400
        assert "RSI thresholds" in response.json()["detail"]

    def test_update_trading_config_validation_stop_loss_order(
        self, client, test_user_with_config, auth_token
    ):
        """Test that stop loss percentages must be in correct order"""
        # All three must be provided for validation
        response = client.put(
            "/api/v1/user/trading-config",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "min_stop_loss_pct": 0.10,  # Should be < tight
                "tight_stop_loss_pct": 0.05,
                "default_stop_loss_pct": 0.08,  # Should be > tight
            },
        )

        assert response.status_code == 400
        assert "Stop loss percentages" in response.json()["detail"]

    def test_update_trading_config_validation_ranges(
        self, client, test_user_with_config, auth_token
    ):
        """Test field range validation"""
        # Test invalid RSI period
        response = client.put(
            "/api/v1/user/trading-config",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"rsi_period": 100},  # Should be <= 50
        )
        assert response.status_code == 422  # Validation error

        # Test invalid capital
        response = client.put(
            "/api/v1/user/trading-config",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"user_capital": -1000},  # Should be > 0
        )
        assert response.status_code == 422

    def test_reset_trading_config(self, client, db_session, test_user_with_config, auth_token):
        """Test resetting config to defaults"""
        # First modify config
        test_user, config = test_user_with_config
        config.rsi_period = 20
        config.user_capital = 500000.0
        db_session.commit()

        # Reset
        response = client.post(
            "/api/v1/user/trading-config/reset",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        # Should be back to defaults
        assert data["rsi_period"] == 10
        assert data["user_capital"] == 100000.0

    def test_get_trading_config_requires_auth(self, client):
        """Test that GET requires authentication"""
        response = client.get("/api/v1/user/trading-config")
        assert response.status_code == 401

    def test_update_trading_config_requires_auth(self, client):
        """Test that PUT requires authentication"""
        response = client.put(
            "/api/v1/user/trading-config",
            json={"rsi_period": 14},
        )
        assert response.status_code == 401

    def test_reset_trading_config_requires_auth(self, client):
        """Test that POST reset requires authentication"""
        response = client.post("/api/v1/user/trading-config/reset")
        assert response.status_code == 401
