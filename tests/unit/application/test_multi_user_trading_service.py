"""
Unit tests for MultiUserTradingService

Tests for:
- Service start/stop
- Service status
- Error handling
- Thread safety
"""

import threading
import time

import pytest

from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.infrastructure.db.models import ServiceStatus, TradeMode, UserSettings, Users
from src.infrastructure.db.timezone_utils import ist_now


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    user = Users(
        email="test@example.com",
        password_hash="hashed_password",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_user_with_settings(db_session, sample_user):
    """Create a user with settings configured"""
    settings = UserSettings(
        user_id=sample_user.id,
        trade_mode=TradeMode.BROKER,
        broker_creds_encrypted=b"encrypted_creds",
    )
    db_session.add(settings)
    db_session.commit()
    return sample_user


class TestMultiUserTradingService:
    """Tests for MultiUserTradingService"""

    def test_service_initialization(self, db_session):
        """Test service initialization"""
        service = MultiUserTradingService(db=db_session)
        assert service.db == db_session
        assert service._services == {}
        assert service._locks == {}

    def test_start_service_missing_settings(self, db_session, sample_user):
        """Test starting service without user settings"""
        service = MultiUserTradingService(db=db_session)

        with pytest.raises(ValueError, match="User settings not found"):
            service.start_service(sample_user.id)

    def test_start_service_wrong_trade_mode(self, db_session, sample_user):
        """Test starting service with wrong trade mode"""
        settings = UserSettings(
            user_id=sample_user.id,
            trade_mode=TradeMode.PAPER,
            broker_creds_encrypted=b"encrypted",
        )
        db_session.add(settings)
        db_session.commit()

        service = MultiUserTradingService(db=db_session)

        with pytest.raises(ValueError, match="broker mode required"):
            service.start_service(sample_user.id)

    def test_start_service_missing_credentials(self, db_session, sample_user):
        """Test starting service without broker credentials"""
        settings = UserSettings(
            user_id=sample_user.id,
            trade_mode=TradeMode.BROKER,
            broker_creds_encrypted=None,
        )
        db_session.add(settings)
        db_session.commit()

        service = MultiUserTradingService(db=db_session)

        with pytest.raises(ValueError, match="No broker credentials stored"):
            service.start_service(sample_user.id)

    def test_start_service_success(self, db_session, sample_user_with_settings):
        """Test successful service start"""
        service = MultiUserTradingService(db=db_session)

        # Start service (will fail at actual TradingService init, but should update status)
        result = service.start_service(sample_user_with_settings.id)

        # Service status should be updated
        from src.infrastructure.persistence.service_status_repository import (
            ServiceStatusRepository,
        )

        status_repo = ServiceStatusRepository(db_session)
        status = status_repo.get(sample_user_with_settings.id)
        assert status is not None
        assert status.service_running is True

        # Check logs were created
        from src.infrastructure.persistence.service_log_repository import (
            ServiceLogRepository,
        )

        log_repo = ServiceLogRepository(db_session)
        logs = log_repo.list(user_id=sample_user_with_settings.id, limit=10)
        assert len(logs) > 0
        assert any("Starting trading service" in log.message for log in logs)

    def test_start_service_already_running(self, db_session, sample_user_with_settings):
        """Test starting service that's already running"""
        service = MultiUserTradingService(db=db_session)

        # Start service first time
        service.start_service(sample_user_with_settings.id)

        # Try to start again (should return True if already running)
        result = service.start_service(sample_user_with_settings.id)
        assert result is True

    def test_stop_service_not_started(self, db_session, sample_user):
        """Test stopping service that was never started"""
        service = MultiUserTradingService(db=db_session)

        result = service.stop_service(sample_user.id)
        assert result is False

    def test_stop_service_success(self, db_session, sample_user_with_settings):
        """Test successful service stop"""
        service = MultiUserTradingService(db=db_session)

        # Start service first
        service.start_service(sample_user_with_settings.id)

        # Stop service
        result = service.stop_service(sample_user_with_settings.id)
        assert result is True

        # Service status should be updated
        from src.infrastructure.persistence.service_status_repository import (
            ServiceStatusRepository,
        )

        status_repo = ServiceStatusRepository(db_session)
        status = status_repo.get(sample_user_with_settings.id)
        assert status.service_running is False

    def test_get_service_status_not_started(self, db_session, sample_user):
        """Test getting status for service that was never started"""
        service = MultiUserTradingService(db=db_session)

        status = service.get_service_status(sample_user.id)
        assert status is None

    def test_get_service_status_started(self, db_session, sample_user_with_settings):
        """Test getting status for started service"""
        service = MultiUserTradingService(db=db_session)

        service.start_service(sample_user_with_settings.id)

        status = service.get_service_status(sample_user_with_settings.id)
        assert status is not None
        # get_service_status returns ServiceStatus object, not dict
        assert status.user_id == sample_user_with_settings.id
        assert status.service_running is True

    def test_thread_safety(self, db_session, sample_user_with_settings):
        """Test thread-safe operations"""
        service = MultiUserTradingService(db=db_session)
        results = []

        def start_service():
            try:
                result = service.start_service(sample_user_with_settings.id)
                results.append(("start", result))
            except Exception as e:
                results.append(("start_error", str(e)))

        def stop_service():
            time.sleep(0.1)  # Small delay
            try:
                result = service.stop_service(sample_user_with_settings.id)
                results.append(("stop", result))
            except Exception as e:
                results.append(("stop_error", str(e)))

        # Run concurrent operations
        threads = [
            threading.Thread(target=start_service),
            threading.Thread(target=start_service),
            threading.Thread(target=stop_service),
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should not have raised exceptions
        assert not any("error" in r[0] for r in results)

    def test_error_logging_on_start_failure(self, db_session, sample_user):
        """Test that errors are logged when service start fails"""
        service = MultiUserTradingService(db=db_session)

        # Try to start without settings (will fail)
        try:
            service.start_service(sample_user.id)
        except ValueError:
            pass  # Expected

        # Check error was logged
        from src.infrastructure.persistence.service_log_repository import (
            ServiceLogRepository,
        )

        log_repo = ServiceLogRepository(db_session)
        error_logs = log_repo.get_errors(user_id=sample_user.id, limit=10)
        assert len(error_logs) > 0
        assert any("User settings not found" in log.message for log in error_logs)

    def test_multiple_users_isolation(self, db_session):
        """Test that multiple users' services are isolated"""
        # Create two users
        user1 = Users(
            email="user1@example.com",
            password_hash="hash1",
            created_at=ist_now(),
        )
        user2 = Users(
            email="user2@example.com",
            password_hash="hash2",
            created_at=ist_now(),
        )
        db_session.add_all([user1, user2])
        db_session.commit()

        # Create settings for both
        settings1 = UserSettings(
            user_id=user1.id,
            trade_mode=TradeMode.BROKER,
            broker_creds_encrypted=b"creds1",
        )
        settings2 = UserSettings(
            user_id=user2.id,
            trade_mode=TradeMode.BROKER,
            broker_creds_encrypted=b"creds2",
        )
        db_session.add_all([settings1, settings2])
        db_session.commit()

        service = MultiUserTradingService(db=db_session)

        # Start both services
        service.start_service(user1.id)
        service.start_service(user2.id)

        # Check both have separate status
        status1 = service.get_service_status(user1.id)
        status2 = service.get_service_status(user2.id)

        assert status1 is not None
        assert status2 is not None
        # get_service_status returns ServiceStatus object, not dict
        assert status1.user_id == user1.id
        assert status2.user_id == user2.id

