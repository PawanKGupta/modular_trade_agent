"""
Integration tests for Phase 2 Logging System

Tests the full logging flow from service operations to files.
"""

import threading
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.application.services.service_lifecycle_generation import reset_service_generation
from src.infrastructure.db.models import TradeMode, Users, UserSettings
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.logging import FileLogReader, get_user_logger


def _clear_multi_user_shared_state() -> None:
    """Reset module-level service state so start_service always hits the log path."""
    from src.application.services import multi_user_trading_service as _mus

    _mus._shared_services.clear()
    _mus._shared_service_threads.clear()
    _mus._shared_locks.clear()
    _mus._shared_start_locks.clear()
    _mus._shared_lock_keys.clear()
    reset_service_generation()


def _wait_for_file_logs(
    reader: FileLogReader,
    user_id: int,
    *,
    message_substring: str,
    timeout_s: float = 8.0,
    interval_s: float = 0.25,
) -> list[dict]:
    """Poll file logs until expected content appears (CI can be slower than local)."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        logs = reader.read_logs(user_id=user_id, limit=20, days_back=1)
        if logs and any(message_substring in log["message"] for log in logs):
            return logs
        time.sleep(interval_s)
    return reader.read_logs(user_id=user_id, limit=20, days_back=1)


@pytest.fixture(autouse=True)
def _isolate_multi_user_service_state():
    _clear_multi_user_shared_state()
    yield
    _clear_multi_user_shared_state()


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
        trade_mode=TradeMode.PAPER,
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
        _clear_multi_user_shared_state()

        class _NoOpThread:
            def __init__(self, *args, **kwargs):
                self._target = kwargs.get("target")
                self._args = kwargs.get("args", ())

            def start(self):
                return None

            def join(self, timeout=None):  # noqa: ARG002
                return None

            def is_alive(self):
                return False

        fake_threading = types.SimpleNamespace(
            Thread=_NoOpThread,
            Lock=threading.Lock,
        )
        monkeypatch.setattr(
            "src.application.services.multi_user_trading_service.threading",
            fake_threading,
        )

        service = MultiUserTradingService(db=db_session)
        user_id = sample_user_with_full_setup.id

        with patch(
            "src.application.services.multi_user_trading_service.PaperTradingServiceAdapter"
        ) as mock_paper_adapter:
            mock_adapter = MagicMock()
            mock_adapter.initialize.return_value = True
            mock_paper_adapter.return_value = mock_adapter

            try:
                service.start_service(user_id)
            except Exception:
                pass  # Logging must still occur before downstream failures
            finally:
                try:
                    service.stop_service(user_id)
                except Exception:
                    pass

        reader = FileLogReader(base_dir="logs")
        logs = _wait_for_file_logs(
            reader,
            user_id,
            message_substring="Starting trading service",
        )

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
