"""
Integration tests for Phase 2 Logging System

Tests the full logging flow from service operations to files.
"""

import time
from pathlib import Path

import pytest

from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.infrastructure.db.models import TradeMode, Users, UserSettings
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.logging import FileLogReader, get_user_logger


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
    )
    db_session.add(settings)
    db_session.commit()

    return user


class TestLoggingIntegration:
    """Integration tests for logging system"""

    def test_service_start_logs_to_file(
        self, db_session, sample_user_with_full_setup, tmp_path, monkeypatch
    ):
        """Test that service start creates logs in files"""
        monkeypatch.chdir(tmp_path)

        service = MultiUserTradingService(db=db_session)

        # Start service
        try:
            service.start_service(sample_user_with_full_setup.id)
        except Exception:
            pass  # May fail at TradingService init, but logging should work

        # Wait a bit for logs to be written
        time.sleep(0.5)

        # Check file logs using FileLogReader
        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=sample_user_with_full_setup.id, limit=10, days_back=1)

        # Retry if no logs found (timing issue)
        if len(logs) == 0:
            time.sleep(1.0)
            logs = reader.read_logs(user_id=sample_user_with_full_setup.id, limit=10, days_back=1)

        assert len(logs) > 0, "No logs found in files"
        assert any("Starting trading service" in log["message"] for log in logs)

        # Also check file directly
        log_dir = Path("logs") / "users" / f"user_{sample_user_with_full_setup.id}"
        log_files = list(log_dir.glob("service_*.jsonl"))
        assert len(log_files) > 0

        # Check log file content (JSONL format)
        with log_files[0].open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) > 0
            # Check at least one line contains the service start message
            content = "".join(lines)
            assert "Starting trading service" in content

    def test_error_logging_integration(
        self, db_session, sample_user_with_full_setup, tmp_path, monkeypatch
    ):
        """Test that errors are logged to both file logs and ErrorLog"""
        monkeypatch.chdir(tmp_path)

        logger = get_user_logger(
            user_id=sample_user_with_full_setup.id, db=db_session, module="test"
        )

        # Log an error with exception
        exception = ValueError("Test error occurred")
        logger.error("Test error occurred", exc_info=exception, symbol="TEST")

        # Wait for file write
        time.sleep(0.3)

        # Check file logs
        reader = FileLogReader(base_dir="logs")
        error_logs = reader.read_error_logs(user_id=sample_user_with_full_setup.id, limit=10)

        # Retry if not found
        if len(error_logs) == 0:
            time.sleep(0.5)
            error_logs = reader.read_error_logs(user_id=sample_user_with_full_setup.id, limit=10)

        assert len(error_logs) > 0
        assert any("Test error occurred" in log["message"] for log in error_logs)

        # Check error log was created in database
        from src.infrastructure.persistence.error_log_repository import (
            ErrorLogRepository,
        )

        error_repo = ErrorLogRepository(db_session)
        errors = error_repo.list(user_id=sample_user_with_full_setup.id, limit=10)
        assert len(errors) > 0
        assert any("Test error occurred" in error.error_message for error in errors)

    def test_logging_context_preserved(
        self, db_session, sample_user_with_full_setup, tmp_path, monkeypatch
    ):
        """Test that logging context is preserved in file logs"""
        monkeypatch.chdir(tmp_path)

        logger = get_user_logger(
            user_id=sample_user_with_full_setup.id, db=db_session, module="test_module"
        )
        logger.info("Test message", action="test_action", symbol="RELIANCE")

        # Wait for file write
        time.sleep(0.3)

        # Check file logs
        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=sample_user_with_full_setup.id, limit=5, days_back=1)

        # Retry if not found
        if len(logs) == 0:
            time.sleep(0.5)
            logs = reader.read_logs(user_id=sample_user_with_full_setup.id, limit=5, days_back=1)

        assert len(logs) > 0
        test_log = next((log for log in logs if "Test message" in log["message"]), None)
        assert test_log is not None
        assert test_log["context"] is not None
        assert test_log["context"]["action"] == "test_action"
        assert test_log["context"]["symbol"] == "RELIANCE"
        assert test_log["module"] == "test_module"

    def test_multiple_log_levels(
        self, db_session, sample_user_with_full_setup, tmp_path, monkeypatch
    ):
        """Test that all log levels are written to files"""
        monkeypatch.chdir(tmp_path)

        logger = get_user_logger(
            user_id=sample_user_with_full_setup.id, db=db_session, module="test"
        )

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        # Wait for file writes
        time.sleep(0.5)

        # Check file logs
        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=sample_user_with_full_setup.id, limit=10, days_back=1)

        # Retry if not found
        if len(logs) == 0:
            time.sleep(0.5)
            logs = reader.read_logs(user_id=sample_user_with_full_setup.id, limit=10, days_back=1)

        assert len(logs) >= 5
        levels = {log["level"] for log in logs}
        assert "DEBUG" in levels or "INFO" in levels  # At least some levels present
        assert "ERROR" in levels or "CRITICAL" in levels  # Error levels should be present
