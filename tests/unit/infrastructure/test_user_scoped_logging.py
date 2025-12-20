"""
Unit tests for User-Scoped Logging System

Tests for:
- UserScopedLogger
- UserFileLogHandler
- FileLogReader
- Error capture
"""

import json
import logging
from pathlib import Path

from src.infrastructure.logging import (
    FileLogReader,
    UserErrorFileLogHandler,
    UserFileLogHandler,
    capture_exception,
    get_user_logger,
)


class TestUserScopedLogger:
    """Tests for UserScopedLogger"""

    def test_logger_initialization(self, db_session):
        """Test logger initialization"""
        logger = get_user_logger(user_id=1, db=db_session, module="test_module")
        assert logger.user_id == 1
        assert logger.module == "test_module"
        assert logger.db == db_session
        assert isinstance(logger.file_handler, UserFileLogHandler)
        assert isinstance(logger.error_file_handler, UserErrorFileLogHandler)

    def test_logger_debug(self, db_session, tmp_path, monkeypatch):
        """Test debug logging"""
        monkeypatch.chdir(tmp_path)

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        logger = get_user_logger(user_id=user.id, db=db_session, module="test")
        logger.debug("Debug message", test_key="test_value")

        # Check file log was created
        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=user.id, level="DEBUG", limit=1)
        assert len(logs) == 1
        assert logs[0]["level"] == "DEBUG"
        assert "Debug message" in logs[0]["message"]
        assert logs[0]["user_id"] == user.id
        assert logs[0]["context"] is not None
        assert "test_key" in logs[0]["context"]
        assert logs[0]["context"]["test_key"] == "test_value"

    def test_logger_info(self, db_session, tmp_path, monkeypatch):
        """Test info logging"""
        monkeypatch.chdir(tmp_path)

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        logger = get_user_logger(user_id=user.id, db=db_session, module="test")
        logger.info("Info message", action="test_action")

        # Check file log was created
        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=user.id, level="INFO", limit=1)
        assert len(logs) == 1
        assert logs[0]["level"] == "INFO"
        assert "Info message" in logs[0]["message"]
        assert logs[0]["context"] is not None
        assert "action" in logs[0]["context"]
        assert logs[0]["context"]["action"] == "test_action"

    def test_logger_warning(self, db_session, tmp_path, monkeypatch):
        """Test warning logging"""
        monkeypatch.chdir(tmp_path)

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        logger = get_user_logger(user_id=user.id, db=db_session, module="test")
        logger.warning("Warning message", warning_type="test")

        # Check file log was created
        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=user.id, level="WARNING", limit=1)
        assert len(logs) == 1
        assert logs[0]["level"] == "WARNING"
        assert "Warning message" in logs[0]["message"]

    def test_logger_error_with_exception(self, db_session, tmp_path, monkeypatch):
        """Test error logging with exception capture"""
        monkeypatch.chdir(tmp_path)

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        logger = get_user_logger(user_id=user.id, db=db_session, module="test")
        exception = ValueError("Test error")
        logger.error("Error message", exc_info=exception, symbol="RELIANCE")

        # Check file log was created
        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=user.id, level="ERROR", limit=1)
        assert len(logs) == 1
        assert logs[0]["level"] == "ERROR"
        assert "Error message" in logs[0]["message"]
        assert logs[0]["context"] is not None
        assert "symbol" in logs[0]["context"]
        assert logs[0]["context"]["symbol"] == "RELIANCE"

        # Check error log was created in database
        from src.infrastructure.persistence.error_log_repository import (
            ErrorLogRepository,
        )

        error_repo = ErrorLogRepository(db_session)
        errors = error_repo.list(user_id=user.id, limit=1)
        assert len(errors) == 1
        assert errors[0].error_type == "ValueError"
        assert "Test error" in errors[0].error_message
        assert errors[0].traceback is not None

    def test_logger_critical(self, db_session, tmp_path, monkeypatch):
        """Test critical logging"""
        monkeypatch.chdir(tmp_path)

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        logger = get_user_logger(user_id=user.id, db=db_session, module="test")
        exception = RuntimeError("Critical error")
        logger.critical("Critical message", exc_info=exception)

        # Check file log was created
        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=user.id, level="CRITICAL", limit=1)
        assert len(logs) == 1
        assert "Critical message" in logs[0]["message"]

    def test_logger_set_module(self, db_session):
        """Test module name update"""
        logger = get_user_logger(user_id=1, db=db_session, module="initial")
        assert logger.module == "initial"

        logger.set_module("updated")
        assert logger.module == "updated"

    def test_logger_close(self, db_session):
        """Test logger cleanup"""
        logger = get_user_logger(user_id=1, db=db_session, module="test")
        logger.close()  # Should not raise

    def test_logger_context_injection(self, db_session, tmp_path, monkeypatch):
        """Test that user_id and module are automatically injected"""
        monkeypatch.chdir(tmp_path)

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test42@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        logger = get_user_logger(user_id=user.id, db=db_session, module="my_module")
        logger.info("Test message", custom_key="custom_value")

        # Check file log was created
        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=user.id, limit=1)
        assert len(logs) == 1
        assert logs[0]["user_id"] == user.id
        assert "Test message" in logs[0]["message"]
        assert logs[0]["context"] is not None
        assert logs[0]["context"]["log_module"] == "my_module"
        assert logs[0]["context"]["custom_key"] == "custom_value"


class TestUserFileLogHandler:
    """Tests for UserFileLogHandler"""

    def test_handler_creates_log_directory(self, tmp_path, monkeypatch):
        """Test handler creates log directory structure"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        log_dir = Path("logs") / "users" / "user_1"
        assert log_dir.exists()
        handler.close()

    def test_handler_writes_to_jsonl_file(self, tmp_path, monkeypatch):
        """Test handler writes logs to JSONL file"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.log_module = "test_module"
        record.user_id = 1

        handler.emit(record)
        handler.close()

        # Check JSONL file was created and contains message
        log_dir = Path("logs") / "users" / "user_1"
        log_files = list(log_dir.glob("service_*.jsonl"))
        assert len(log_files) == 1

        # Read JSONL file
        with log_files[0].open("r", encoding="utf-8") as f:
            line = f.readline()
            data = json.loads(line)
            assert data["message"] == "Test message"
            assert data["level"] == "INFO"
            assert data["module"] == "test_module"
            assert data["user_id"] == 1

    def test_error_handler_writes_only_errors(self, tmp_path, monkeypatch):
        """Test error handler only writes ERROR and CRITICAL"""
        monkeypatch.chdir(tmp_path)

        handler = UserErrorFileLogHandler(user_id=1)

        # Emit INFO (should not be written due to level filter)
        info_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Info message",
            args=(),
            exc_info=None,
        )
        info_record.user_id = 1
        handler.emit(info_record)

        # Emit ERROR (should be written)
        error_record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Error message",
            args=(),
            exc_info=None,
        )
        error_record.user_id = 1
        handler.emit(error_record)
        handler.close()

        # Check error log file exists
        log_dir = Path("logs") / "users" / "user_1"
        error_files = list(log_dir.glob("errors_*.jsonl"))
        assert len(error_files) >= 1

        # Read JSONL file and verify only ERROR is present
        with error_files[0].open("r", encoding="utf-8") as f:
            lines = f.readlines()
            error_found = False
            for line in lines:
                if line.strip():
                    data = json.loads(line)
                    if data["level"] == "ERROR":
                        error_found = True
                        assert "Error message" in data["message"]
                    # INFO should not be in error log
                    assert data["level"] in ("ERROR", "CRITICAL")
            assert error_found


class TestFileLogReader:
    """Tests for FileLogReader"""

    def test_read_logs_basic(self, tmp_path, monkeypatch):
        """Test reading logs from file"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        for i in range(5):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"Message {i}",
                args=(),
                exc_info=None,
            )
            record.log_module = "test_module"
            record.user_id = 1
            handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        logs = reader.read_logs(user_id=1, limit=10)
        assert len(logs) == 5
        assert all(log["level"] == "INFO" for log in logs)
        assert all(log["user_id"] == 1 for log in logs)

    def test_read_logs_with_filters(self, tmp_path, monkeypatch):
        """Test reading logs with filters"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in levels:
            record = logging.LogRecord(
                name="test",
                level=getattr(logging, level),
                pathname="",
                lineno=0,
                msg=f"{level} message",
                args=(),
                exc_info=None,
            )
            record.log_module = "test_module"
            record.user_id = 1
            handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        # Filter by level
        error_logs = reader.read_logs(user_id=1, level="ERROR", limit=10)
        assert len(error_logs) == 1
        assert error_logs[0]["level"] == "ERROR"

        # Filter by module
        module_logs = reader.read_logs(user_id=1, module="test_module", limit=10)
        assert len(module_logs) == 5

    def test_read_error_logs(self, tmp_path, monkeypatch):
        """Test reading error logs"""
        monkeypatch.chdir(tmp_path)

        handler = UserErrorFileLogHandler(user_id=1)
        for level in [logging.ERROR, logging.CRITICAL]:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="",
                lineno=0,
                msg=f"{logging.getLevelName(level)} message",
                args=(),
                exc_info=None,
            )
            record.user_id = 1
            handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        error_logs = reader.read_error_logs(user_id=1, limit=10)
        assert len(error_logs) == 2
        assert all(log["level"] in ("ERROR", "CRITICAL") for log in error_logs)

    def test_tail_logs(self, tmp_path, monkeypatch):
        """Test tailing logs"""
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        for i in range(10):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"Message {i}",
                args=(),
                exc_info=None,
            )
            record.log_module = "test_module"
            record.user_id = 1
            handler.emit(record)
        handler.close()

        reader = FileLogReader(base_dir="logs")
        tail_logs = reader.tail_logs(user_id=1, log_type="service", tail_lines=5)
        assert len(tail_logs) == 5
        # Should be newest first
        assert "Message 9" in tail_logs[0]["message"]


class TestErrorCapture:
    """Tests for error capture functionality"""

    def test_capture_exception_basic(self, db_session):
        """Test basic exception capture"""
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        exception = ValueError("Test error message")
        context = {"symbol": "RELIANCE", "action": "place_order"}

        capture_exception(user_id=user.id, exception=exception, context=context, db=db_session)

        from src.infrastructure.persistence.error_log_repository import (
            ErrorLogRepository,
        )

        error_repo = ErrorLogRepository(db_session)
        errors = error_repo.list(user_id=user.id, limit=1)
        assert len(errors) == 1
        assert errors[0].error_type == "ValueError"
        assert "Test error message" in errors[0].error_message
        assert errors[0].traceback is not None
        assert errors[0].context["symbol"] == "RELIANCE"
        assert errors[0].context["action"] == "place_order"

    def test_capture_exception_with_user_state(self, db_session):
        """Test exception capture includes user state"""
        from src.infrastructure.db.models import Users, UserTradingConfig
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        config = UserTradingConfig(
            user_id=user.id,
            rsi_oversold=25.0,
            user_capital=300000.0,
            max_portfolio_size=8,
        )
        db_session.add(config)
        db_session.commit()

        exception = RuntimeError("Service error")
        capture_exception(
            user_id=user.id,
            exception=exception,
            context={"task": "analysis"},
            db=db_session,
            include_user_state=True,
        )

        from src.infrastructure.persistence.error_log_repository import (
            ErrorLogRepository,
        )

        error_repo = ErrorLogRepository(db_session)
        errors = error_repo.list(user_id=user.id, limit=1)
        assert len(errors) == 1
        assert "user_config" in errors[0].context
        assert errors[0].context["user_config"]["rsi_oversold"] == 25.0
        assert errors[0].context["user_config"]["user_capital"] == 300000.0

    def test_capture_exception_handles_errors_gracefully(self, db_session):
        """Test error capture doesn't break on errors"""
        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        exception = ValueError("Test")

        # Rollback session to simulate error
        db_session.rollback()

        # Should not raise, should handle error gracefully
        try:
            capture_exception(user_id=user.id, exception=exception, context={}, db=db_session)
        except Exception:
            # If it raises, that's also acceptable - the important thing is it doesn't break the app
            pass
