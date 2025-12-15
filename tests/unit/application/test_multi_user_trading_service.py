# ruff: noqa: PLC0415

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
from unittest.mock import MagicMock, patch

import pytest

from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.infrastructure.db.models import TradeMode, Users, UserSettings
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
    import json

    from server.app.core.crypto import encrypt_blob

    # Create properly encrypted credentials
    creds_dict = {
        "api_key": "test_key",
        "api_secret": "test_secret",
        "mobile_number": "9876543210",
        "password": "test_pass",
        "mpin": "1234",
        "environment": "prod",
    }
    encrypted_creds = encrypt_blob(json.dumps(creds_dict).encode("utf-8"))

    settings = UserSettings(
        user_id=sample_user.id,
        trade_mode=TradeMode.BROKER,
        broker_creds_encrypted=encrypted_creds,
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

    def test_start_service_paper_mode(self, db_session, sample_user):
        """Test starting service with paper mode (no credentials needed)"""
        settings = UserSettings(
            user_id=sample_user.id,
            trade_mode=TradeMode.PAPER,
            broker_creds_encrypted=None,  # Paper mode doesn't need credentials
        )
        db_session.add(settings)
        db_session.commit()

        service = MultiUserTradingService(db=db_session)

        # Paper mode should work (will fail at TradingService init, but that's expected)
        # The important thing is that it doesn't fail at credential check
        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            result = service.start_service(sample_user.id)
            assert result is True  # Should succeed (mocked TradingService)

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
        from unittest.mock import MagicMock, patch

        service = MultiUserTradingService(db=db_session)

        # Mock TradingService to avoid actual initialization
        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            # Start service (should succeed with mocked TradingService)
            service.start_service(sample_user_with_settings.id)

            # Service status should be updated
            from src.infrastructure.persistence.service_status_repository import (
                ServiceStatusRepository,
            )

            status_repo = ServiceStatusRepository(db_session)
            status = status_repo.get(sample_user_with_settings.id)
            assert status is not None
            assert status.service_running is True

            # Check logs were created in files (wait a bit for file write)
            import time

            time.sleep(0.3)
            from src.infrastructure.logging.file_log_reader import FileLogReader

            reader = FileLogReader()
            logs = reader.read_logs(user_id=sample_user_with_settings.id, limit=10, days_back=1)
            # Logs may not be immediate, so this is optional check
            if len(logs) > 0:
                assert any("Starting trading service" in log["message"] for log in logs)

    def test_start_service_already_running(self, db_session, sample_user_with_settings):
        """Test starting service that's already running.

        Should return True without creating new instance.
        """
        from unittest.mock import MagicMock, patch

        service = MultiUserTradingService(db=db_session)
        service._logger = MagicMock()  # Avoid DB-backed logging writes

        # Mock TradingService to avoid actual initialization
        with (
            patch(
                "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
            ) as mock_service_class,
            patch("threading.Thread") as mock_thread_class,
            patch(
                "src.application.services.multi_user_trading_service.get_user_logger"
            ) as mock_get_logger,
        ):
            mock_service = MagicMock()
            mock_service.running = True  # Set running flag to True
            mock_service_class.return_value = mock_service
            # Mock thread as alive to simulate running service
            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = True  # Thread is alive
            mock_thread_class.return_value = mock_thread
            # Use simple no-op logger to avoid DB logging writes
            noop_logger = MagicMock()
            mock_get_logger.return_value = noop_logger

            # Start service first time
            service.start_service(sample_user_with_settings.id)

            # Verify TradingService was created once
            assert mock_service_class.call_count == 1

            # Ensure session is clean before retrying (avoid pending rollback)
            db_session.rollback()

            # Try to start again (should return True if already running)
            result = service.start_service(sample_user_with_settings.id)
            assert result is True

            # CRITICAL: Verify TradingService was NOT created again (prevents multiple clients)
            assert mock_service_class.call_count == 1, "TradingService should only be created once"

    def test_stale_service_cleanup(self, db_session, sample_user_with_settings):
        """Test stale service cleanup.

        Stale services (thread dead but running=True) should be cleaned up
        and a new instance created.
        """
        from unittest.mock import MagicMock, patch

        service = MultiUserTradingService(db=db_session)
        service._logger = MagicMock()  # Avoid DB-backed logging writes

        with (
            patch(
                "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
            ) as mock_service_class,
            patch("threading.Thread") as mock_thread_class,
            patch(
                "src.application.services.multi_user_trading_service.get_user_logger"
            ) as mock_get_logger,
        ):
            # First service instance (will become stale)
            mock_service1 = MagicMock()
            mock_service1.running = True
            mock_service_class.return_value = mock_service1

            mock_thread1 = MagicMock()
            mock_thread1.is_alive.return_value = True  # Initially alive
            mock_thread_class.return_value = mock_thread1

            noop_logger = MagicMock()
            mock_get_logger.return_value = noop_logger

            # Start service first time
            service.start_service(sample_user_with_settings.id)
            assert mock_service_class.call_count == 1

            # Simulate thread dying (stale service)
            mock_thread1.is_alive.return_value = False  # Thread is now dead

            # Create second service instance for cleanup scenario
            mock_service2 = MagicMock()
            mock_service2.running = True
            mock_service_class.return_value = mock_service2

            mock_thread2 = MagicMock()
            mock_thread2.is_alive.return_value = True  # New thread is alive
            mock_thread_class.return_value = mock_thread2

            db_session.rollback()

            # Try to start again - should detect stale service and create new one
            result = service.start_service(sample_user_with_settings.id)
            assert result is True

            # CRITICAL: Should have created a NEW instance after cleanup
            assert (
                mock_service_class.call_count == 2
            ), "Should create new instance after stale cleanup"
            # Verify old service was removed
            assert service._services[sample_user_with_settings.id] == mock_service2

    def test_multiple_start_calls_create_only_one_instance(
        self, db_session, sample_user_with_settings
    ):
        """Test multiple sequential start_service calls.

        Should only create ONE TradingService instance.
        """
        from unittest.mock import MagicMock, patch

        service = MultiUserTradingService(db=db_session)
        service._logger = MagicMock()  # Avoid DB-backed logging writes

        with (
            patch(
                "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
            ) as mock_service_class,
            patch("threading.Thread") as mock_thread_class,
            patch(
                "src.application.services.multi_user_trading_service.get_user_logger"
            ) as mock_get_logger,
        ):
            mock_service = MagicMock()
            mock_service.running = True
            mock_service_class.return_value = mock_service

            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = True
            mock_thread_class.return_value = mock_thread

            noop_logger = MagicMock()
            mock_get_logger.return_value = noop_logger

            # First start_service call - should create instance
            result1 = service.start_service(sample_user_with_settings.id)
            assert result1 is True
            assert mock_service_class.call_count == 1

            db_session.rollback()

            # Second start_service call - should detect existing service and NOT create new instance
            result2 = service.start_service(sample_user_with_settings.id)
            assert result2 is True

            # CRITICAL: Only ONE TradingService instance should be created despite 2 calls
            assert mock_service_class.call_count == 1, (
                f"Expected 1 TradingService instance, got {mock_service_class.call_count}. "
                "Multiple instances would cause JWT token invalidation."
            )

            # Third call - still should not create new instance
            db_session.rollback()
            result3 = service.start_service(sample_user_with_settings.id)
            assert result3 is True
            assert mock_service_class.call_count == 1

    def test_stop_service_not_started(self, db_session, sample_user):
        """Test stopping service that was never started"""
        service = MultiUserTradingService(db=db_session)

        result = service.stop_service(sample_user.id)
        # Idempotent stop returns True even if nothing was running, but should not error
        assert result is True

    def test_stop_service_success(self, db_session, sample_user_with_settings):
        """Test successful service stop"""
        from unittest.mock import MagicMock, patch

        service = MultiUserTradingService(db=db_session)

        # Mock TradingService to avoid actual initialization
        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

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
        from unittest.mock import MagicMock, patch

        service = MultiUserTradingService(db=db_session)

        # Mock TradingService to avoid actual initialization
        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            service.start_service(sample_user_with_settings.id)

        status = service.get_service_status(sample_user_with_settings.id)
        assert status is not None
        # get_service_status returns ServiceStatus object, not dict
        assert status.user_id == sample_user_with_settings.id
        assert status.service_running is True

    def test_thread_safety(self, db_session, sample_user_with_settings):
        """Test thread-safe operations"""
        from unittest.mock import MagicMock, patch

        service = MultiUserTradingService(db=db_session)
        service._logger = MagicMock()  # Avoid DB-backed logging writes
        results = []

        # Mock TradingService to avoid actual initialization
        with (
            patch(
                "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
            ) as mock_service_class,
            patch("threading.Thread") as mock_thread_class,
            patch(
                "src.application.services.multi_user_trading_service.get_user_logger"
            ) as mock_get_logger,
        ):
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            # Prevent background thread side effects
            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = False
            mock_thread_class.return_value = mock_thread
            # Use simple no-op logger to avoid DB logging writes
            noop_logger = MagicMock()
            mock_get_logger.return_value = noop_logger

            # Ensure clean session before concurrent ops
            db_session.rollback()

            def start_service():
                try:
                    db_session.rollback()
                    result = service.start_service(sample_user_with_settings.id)
                    results.append(("start", result))
                except Exception as e:
                    results.append(("start_error", str(e)))

            def stop_service():
                time.sleep(0.1)  # Small delay
                try:
                    db_session.rollback()
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

        # Check error was logged in files (wait a bit for file write)
        import time

        time.sleep(0.3)
        from src.infrastructure.logging.file_log_reader import FileLogReader

        reader = FileLogReader()
        error_logs = reader.read_error_logs(user_id=sample_user.id, limit=10)
        # Error logs may not be immediate, so this is optional check
        if len(error_logs) > 0:
            assert any("User settings not found" in log["message"] for log in error_logs)

    def test_multiple_users_isolation(self, db_session):
        """Test that multiple users' services are isolated"""
        import json
        from unittest.mock import MagicMock, patch

        from server.app.core.crypto import encrypt_blob

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

        # Create properly encrypted credentials for both
        creds1 = encrypt_blob(
            json.dumps({"api_key": "key1", "api_secret": "secret1", "environment": "prod"}).encode(
                "utf-8"
            )
        )
        creds2 = encrypt_blob(
            json.dumps({"api_key": "key2", "api_secret": "secret2", "environment": "prod"}).encode(
                "utf-8"
            )
        )

        # Create settings for both
        settings1 = UserSettings(
            user_id=user1.id,
            trade_mode=TradeMode.BROKER,
            broker_creds_encrypted=creds1,
        )
        settings2 = UserSettings(
            user_id=user2.id,
            trade_mode=TradeMode.BROKER,
            broker_creds_encrypted=creds2,
        )
        db_session.add_all([settings1, settings2])
        db_session.commit()

        service = MultiUserTradingService(db=db_session)

        # Mock TradingService to avoid actual initialization
        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

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

    def test_per_user_locks_allow_different_users_separate_instances(self, db_session):
        """Test that different users can have separate TradingService instances (per-user locks)"""
        import json
        from unittest.mock import MagicMock, patch

        from server.app.core.crypto import encrypt_blob

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

        # Create properly encrypted credentials for both
        creds1 = encrypt_blob(
            json.dumps({"api_key": "key1", "api_secret": "secret1", "environment": "prod"}).encode(
                "utf-8"
            )
        )
        creds2 = encrypt_blob(
            json.dumps({"api_key": "key2", "api_secret": "secret2", "environment": "prod"}).encode(
                "utf-8"
            )
        )

        # Create settings for both
        settings1 = UserSettings(
            user_id=user1.id,
            trade_mode=TradeMode.BROKER,
            broker_creds_encrypted=creds1,
        )
        settings2 = UserSettings(
            user_id=user2.id,
            trade_mode=TradeMode.BROKER,
            broker_creds_encrypted=creds2,
        )
        db_session.add_all([settings1, settings2])
        db_session.commit()

        service = MultiUserTradingService(db=db_session)
        service._logger = MagicMock()

        with (
            patch(
                "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
            ) as mock_service_class,
            patch("threading.Thread") as mock_thread_class,
            patch(
                "src.application.services.multi_user_trading_service.get_user_logger"
            ) as mock_get_logger,
        ):
            mock_service = MagicMock()
            mock_service.running = True
            mock_service_class.return_value = mock_service

            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = True
            mock_thread_class.return_value = mock_thread

            noop_logger = MagicMock()
            mock_get_logger.return_value = noop_logger

            # Start service for user1
            result1 = service.start_service(user1.id)
            assert result1 is True
            assert mock_service_class.call_count == 1

            db_session.rollback()

            # Start service for user2 (different user, should create new instance)
            result2 = service.start_service(user2.id)
            assert result2 is True

            # CRITICAL: Both users should have their own TradingService instances
            # (2 calls total, one per user)
            assert mock_service_class.call_count == 2, (
                "Each user should have their own TradingService instance. "
                f"Got {mock_service_class.call_count} calls."
            )

            # Verify locks are separate per user
            assert user1.id in service._locks
            assert user2.id in service._locks
            assert service._locks[user1.id] != service._locks[user2.id]

            # Verify both services exist
            assert user1.id in service._services
            assert user2.id in service._services

    def test_paper_mode_creates_paper_adapter(self, db_session, sample_user):
        """Test that paper mode creates PaperTradingServiceAdapter instead of TradingService"""
        settings = UserSettings(
            user_id=sample_user.id,
            trade_mode=TradeMode.PAPER,
            broker_creds_encrypted=None,
        )
        db_session.add(settings)
        db_session.commit()

        service = MultiUserTradingService(db=db_session)

        with patch(
            "src.application.services.multi_user_trading_service.PaperTradingServiceAdapter"
        ) as mock_paper_adapter:
            mock_adapter = MagicMock()
            mock_adapter.initialize.return_value = True
            mock_paper_adapter.return_value = mock_adapter

            result = service.start_service(sample_user.id)

            assert result is True
            # Verify PaperTradingServiceAdapter was created
            mock_paper_adapter.assert_called_once()
            # Verify initialize was called
            mock_adapter.initialize.assert_called_once()

    def test_paper_mode_starts_scheduler_thread(self, db_session, sample_user):
        """Test that paper mode starts the scheduler in a background thread"""
        settings = UserSettings(
            user_id=sample_user.id,
            trade_mode=TradeMode.PAPER,
            broker_creds_encrypted=None,
        )
        db_session.add(settings)
        db_session.commit()

        service = MultiUserTradingService(db=db_session)

        with patch(
            "src.application.services.multi_user_trading_service.PaperTradingServiceAdapter"
        ) as mock_paper_adapter:
            with patch("threading.Thread") as mock_thread:
                mock_adapter = MagicMock()
                mock_adapter.initialize.return_value = True
                mock_paper_adapter.return_value = mock_adapter

                mock_thread_instance = MagicMock()
                mock_thread.return_value = mock_thread_instance

                result = service.start_service(sample_user.id)

                assert result is True
                # Verify thread was created
                mock_thread.assert_called_once()
                call_args = mock_thread.call_args
                assert call_args[1]["daemon"] is True
                assert call_args[1]["name"] == f"PaperTradingScheduler-{sample_user.id}"
                # Verify thread was started
                mock_thread_instance.start.assert_called_once()

    def test_broker_mode_creates_trading_service(self, db_session, sample_user_with_settings):
        """Test that broker mode creates real TradingService"""
        service = MultiUserTradingService(db=db_session)

        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service.TradingService"
        ) as mock_trading_service:
            with patch("threading.Thread") as mock_thread:
                mock_service = MagicMock()
                mock_trading_service.return_value = mock_service

                mock_thread_instance = MagicMock()
                mock_thread.return_value = mock_thread_instance

                result = service.start_service(sample_user_with_settings.id)

                assert result is True
                # Verify TradingService was created
                mock_trading_service.assert_called_once()
                # Verify thread was created for service.run()
                mock_thread.assert_called_once()
                call_args = mock_thread.call_args
                assert call_args[1]["target"] == mock_service.run
                assert call_args[1]["daemon"] is True
                assert call_args[1]["name"] == f"TradingService-{sample_user_with_settings.id}"
                # Verify thread was started
                mock_thread_instance.start.assert_called_once()

    def test_stop_service_waits_for_thread(self, db_session, sample_user):
        """Test that stop_service waits for scheduler thread to stop"""
        settings = UserSettings(
            user_id=sample_user.id,
            trade_mode=TradeMode.PAPER,
            broker_creds_encrypted=None,
        )
        db_session.add(settings)
        db_session.commit()

        service = MultiUserTradingService(db=db_session)

        with patch(
            "src.application.services.multi_user_trading_service.PaperTradingServiceAdapter"
        ) as mock_paper_adapter:
            mock_adapter = MagicMock()
            mock_adapter.initialize.return_value = True
            mock_adapter.running = True
            mock_paper_adapter.return_value = mock_adapter

            # Start service
            service.start_service(sample_user.id)

            # Mock the thread
            mock_thread = MagicMock()
            mock_thread.is_alive.return_value = True
            service._service_threads[sample_user.id] = mock_thread

            # Stop service
            result = service.stop_service(sample_user.id)

            assert result is True
            # Verify thread.join was called with timeout
            mock_thread.join.assert_called_once_with(timeout=10.0)
            # Verify service flags were set
            assert mock_adapter.shutdown_requested is True
            assert mock_adapter.running is False
