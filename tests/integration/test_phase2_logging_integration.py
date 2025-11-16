"""
Integration tests for Phase 2 Logging System

Tests the full logging flow from service operations to database and files.
"""

import tempfile
from pathlib import Path

import pytest

from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.infrastructure.db.models import ServiceStatus, TradeMode, UserSettings, Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.logging import get_user_logger


@pytest.fixture
def sample_user_with_full_setup(db_session):
    """Create a user with complete setup"""
    user = Users(
        email="integration@example.com",
        password_hash="hash",
        created_at=ist_now(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    settings = UserSettings(
        user_id=user.id,
        trade_mode=TradeMode.BROKER,
        broker_creds_encrypted=b"encrypted_creds",
    )
    db_session.add(settings)
    db_session.commit()

    return user


class TestLoggingIntegration:
    """Integration tests for logging system"""

    def test_service_start_logs_to_database_and_file(
        self, db_session, sample_user_with_full_setup, tmp_path, monkeypatch
    ):
        """Test that service start creates logs in both database and files"""
        monkeypatch.chdir(tmp_path)

        service = MultiUserTradingService(db=db_session)

        # Start service
        try:
            service.start_service(sample_user_with_full_setup.id)
        except Exception:
            pass  # May fail at TradingService init, but logging should work

        # Check database logs
        from src.infrastructure.persistence.service_log_repository import (
            ServiceLogRepository,
        )

        log_repo = ServiceLogRepository(db_session)
        logs = log_repo.list(user_id=sample_user_with_full_setup.id, limit=10)

        assert len(logs) > 0
        assert any("Starting trading service" in log.message for log in logs)

        # Check file logs
        log_dir = Path("logs") / "users" / f"user_{sample_user_with_full_setup.id}"
        log_files = list(log_dir.glob("service_*.log"))
        assert len(log_files) > 0

        # Check log file content
        content = log_files[0].read_text(encoding="utf-8")
        assert "Starting trading service" in content

    def test_error_logging_integration(self, db_session, sample_user_with_full_setup):
        """Test that errors are logged to both ServiceLog and ErrorLog"""
        logger = get_user_logger(
            user_id=sample_user_with_full_setup.id,
            db=db_session,
            module="integration_test",
        )

        exception = ValueError("Integration test error")
        logger.error("Test error occurred", exc_info=exception, symbol="RELIANCE")

        # Check ServiceLog
        from src.infrastructure.persistence.service_log_repository import (
            ServiceLogRepository,
        )

        log_repo = ServiceLogRepository(db_session)
        service_logs = log_repo.get_errors(
            user_id=sample_user_with_full_setup.id, limit=10
        )
        assert len(service_logs) > 0
        assert any("Test error occurred" in log.message for log in service_logs)

        # Check ErrorLog
        from src.infrastructure.persistence.error_log_repository import (
            ErrorLogRepository,
        )

        error_repo = ErrorLogRepository(db_session)
        error_logs = error_repo.list(user_id=sample_user_with_full_setup.id, limit=10)
        assert len(error_logs) > 0
        assert any("Integration test error" in error.error_message for error in error_logs)
        assert any("RELIANCE" in str(error.context) for error in error_logs)

    def test_log_context_preservation(self, db_session, sample_user_with_full_setup):
        """Test that log context is preserved through the full flow"""
        logger = get_user_logger(
            user_id=sample_user_with_full_setup.id,
            db=db_session,
            module="context_test",
        )

        context = {
            "symbol": "RELIANCE",
            "order_id": 12345,
            "action": "place_order",
            "price": 2500.50,
        }

        logger.info("Order placed", **context)

        # Check context is preserved in database
        from src.infrastructure.persistence.service_log_repository import (
            ServiceLogRepository,
        )

        log_repo = ServiceLogRepository(db_session)
        logs = log_repo.list(user_id=sample_user_with_full_setup.id, limit=1)
        assert len(logs) == 1

        log_context = logs[0].context
        assert log_context["symbol"] == "RELIANCE"
        assert log_context["order_id"] == 12345
        assert log_context["action"] == "place_order"
        assert log_context["price"] == 2500.50
        # user_id is stored in the record, not context JSON
        assert logs[0].user_id == sample_user_with_full_setup.id
        assert log_context["log_module"] == "context_test"

    def test_multiple_users_log_isolation(
        self, db_session, tmp_path, monkeypatch
    ):
        """Test that logs from multiple users are isolated"""
        monkeypatch.chdir(tmp_path)

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

        # Create loggers for both
        logger1 = get_user_logger(user_id=user1.id, db=db_session, module="test")
        logger2 = get_user_logger(user_id=user2.id, db=db_session, module="test")

        logger1.info("User 1 message", user="user1")
        logger2.info("User 2 message", user="user2")

        # Check database isolation
        from src.infrastructure.persistence.service_log_repository import (
            ServiceLogRepository,
        )

        log_repo = ServiceLogRepository(db_session)
        user1_logs = log_repo.list(user_id=user1.id, limit=10)
        user2_logs = log_repo.list(user_id=user2.id, limit=10)

        assert len(user1_logs) == 1
        assert len(user2_logs) == 1
        assert user1_logs[0].user_id == user1.id
        assert user2_logs[0].user_id == user2.id

        # Check file isolation
        user1_log_dir = Path("logs") / "users" / f"user_{user1.id}"
        user2_log_dir = Path("logs") / "users" / f"user_{user2.id}"

        user1_files = list(user1_log_dir.glob("service_*.log"))
        user2_files = list(user2_log_dir.glob("service_*.log"))

        assert len(user1_files) > 0
        assert len(user2_files) > 0

        # Check content isolation
        user1_content = user1_files[0].read_text(encoding="utf-8")
        user2_content = user2_files[0].read_text(encoding="utf-8")

        assert "User 1 message" in user1_content
        assert "User 2 message" not in user1_content
        assert "User 2 message" in user2_content
        assert "User 1 message" not in user2_content

    def test_error_capture_with_user_state(
        self, db_session, sample_user_with_full_setup
    ):
        """Test that error capture includes user configuration state"""
        from src.infrastructure.db.models import UserTradingConfig

        # Create user config
        config = UserTradingConfig(
            user_id=sample_user_with_full_setup.id,
            rsi_oversold=25.0,
            user_capital=300000.0,
            max_portfolio_size=8,
        )
        db_session.add(config)
        db_session.commit()

        logger = get_user_logger(
            user_id=sample_user_with_full_setup.id,
            db=db_session,
            module="error_test",
        )

        exception = RuntimeError("Service error with context")
        logger.error("Service failed", exc_info=exception, task="analysis")

        # Check error log includes user config
        from src.infrastructure.persistence.error_log_repository import (
            ErrorLogRepository,
        )

        error_repo = ErrorLogRepository(db_session)
        errors = error_repo.list(user_id=sample_user_with_full_setup.id, limit=1)
        assert len(errors) == 1

        error_context = errors[0].context
        assert "user_config" in error_context
        assert error_context["user_config"]["rsi_oversold"] == 25.0
        assert error_context["user_config"]["user_capital"] == 300000.0
        assert error_context["task"] == "analysis"

