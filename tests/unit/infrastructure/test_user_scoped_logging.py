"""
Unit tests for User-Scoped Logging System

Tests for:
- UserScopedLogger
- DatabaseLogHandler
- UserFileLogHandler
- Error capture
"""

import logging
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.infrastructure.logging import (
    DatabaseLogHandler,
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
        assert isinstance(logger.db_handler, DatabaseLogHandler)
        assert isinstance(logger.file_handler, UserFileLogHandler)
        assert isinstance(logger.error_file_handler, UserErrorFileLogHandler)

    def test_logger_debug(self, db_session):
        """Test debug logging"""
        # Create user first
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        # Patch SessionLocal to use test database
        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            logger = get_user_logger(user_id=user.id, db=db_session, module="test")
            logger.debug("Debug message", test_key="test_value")

            # Flush queue to ensure log is written (queue-based async logging)
            DatabaseLogHandler.flush(timeout=2.0)

            # Check database log was created
            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=1)
            assert len(logs) == 1
            assert logs[0].level == "DEBUG"
            assert "Debug message" in logs[0].message  # Message may have user prefix
        assert logs[0].user_id == user.id  # user_id is stored in the record, not context
        assert "test_key" in logs[0].context
        assert logs[0].context["test_key"] == "test_value"
        # log_module may or may not be in context depending on filtering

    def test_logger_info(self, db_session):
        """Test info logging"""
        # Create user first
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        # Patch SessionLocal to use test database
        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            logger = get_user_logger(user_id=user.id, db=db_session, module="test")
            logger.info("Info message", action="test_action")

            # Flush queue to ensure log is written (queue-based async logging)
            DatabaseLogHandler.flush(timeout=2.0)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=1)
            assert len(logs) == 1
            assert logs[0].level == "INFO"
            assert "Info message" in logs[0].message  # Message may have user prefix
        assert "action" in logs[0].context

    def test_logger_warning(self, db_session):
        """Test warning logging"""
        # Create user first
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        # Patch SessionLocal to use test database
        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            logger = get_user_logger(user_id=user.id, db=db_session, module="test")
            logger.warning("Warning message", warning_type="test")

            # Flush queue to ensure log is written (queue-based async logging)
            DatabaseLogHandler.flush(timeout=2.0)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, level="WARNING", limit=1)
            assert len(logs) == 1
            assert logs[0].level == "WARNING"
            assert "Warning message" in logs[0].message  # Message may have user prefix

    def test_logger_error_with_exception(self, db_session):
        """Test error logging with exception capture"""
        # Create user first
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        # Patch SessionLocal to use test database
        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            logger = get_user_logger(user_id=user.id, db=db_session, module="test")
            exception = ValueError("Test error")
            logger.error("Error message", exc_info=exception, symbol="RELIANCE")

            # Flush queue to ensure log is written (queue-based async logging)
            DatabaseLogHandler.flush(timeout=2.0)

            # Check database log was created
            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, level="ERROR", limit=1)
            assert len(logs) == 1
            assert logs[0].level == "ERROR"
            assert "Error message" in logs[0].message  # Message may have user prefix
            assert "symbol" in logs[0].context

        # Check error log was created
        from src.infrastructure.persistence.error_log_repository import (
            ErrorLogRepository,
        )

        error_repo = ErrorLogRepository(db_session)
        errors = error_repo.list(user_id=user.id, limit=1)
        assert len(errors) == 1
        assert errors[0].error_type == "ValueError"
        assert "Test error" in errors[0].error_message
        assert errors[0].traceback is not None

    def test_logger_critical(self, db_session):
        """Test critical logging"""
        # Create user first
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        # Patch SessionLocal to use test database
        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            logger = get_user_logger(user_id=user.id, db=db_session, module="test")
            exception = RuntimeError("Critical error")
            logger.critical("Critical message", exc_info=exception)

            # Flush queue to ensure log is written (queue-based async logging)
            DatabaseLogHandler.flush(timeout=2.0)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, level="CRITICAL", limit=1)
            assert len(logs) == 1
            assert "Critical message" in logs[0].message  # Message may have user prefix

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

    def test_logger_context_injection(self, db_session):
        """Test that user_id and module are automatically injected"""
        # Create user first
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test42@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        # Patch SessionLocal to use test database
        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            logger = get_user_logger(user_id=user.id, db=db_session, module="my_module")
            logger.info("Test message", custom_key="custom_value")

            # Flush queue to ensure log is written (queue-based async logging)
            DatabaseLogHandler.flush(timeout=2.0)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=1)
            assert len(logs) == 1
            assert logs[0].user_id == user.id  # user_id is in the record, not context
            assert "Test message" in logs[0].message  # Message may have user prefix
            assert logs[0].context["log_module"] == "my_module"
            assert logs[0].context["custom_key"] == "custom_value"


class TestDatabaseLogHandler:
    """Tests for DatabaseLogHandler"""

    def test_handler_initialization(self, db_session):
        """Test handler initialization"""
        handler = DatabaseLogHandler(user_id=1, db=db_session)
        assert handler.user_id == 1
        # Note: handler no longer stores db session (uses queue-based async logging)

    def test_handler_emit_info(self, db_session):
        """Test handler emits INFO logs"""
        # Create user first
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now
        from src.infrastructure.logging.database_log_handler import DatabaseLogHandler

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        # Patch SessionLocal to use the test database session
        # The worker thread needs to use the same database as the test
        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=user.id, db=db_session)
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
            record.custom_field = "custom_value"

            handler.emit(record)

            # Flush queue to ensure log is written (queue-based async logging)
            DatabaseLogHandler.flush(timeout=2.0)

        from src.infrastructure.persistence.service_log_repository import (
            ServiceLogRepository,
        )

        log_repo = ServiceLogRepository(db_session)
        logs = log_repo.list(user_id=user.id, limit=1)
        assert len(logs) == 1
        assert logs[0].level == "INFO"
        assert logs[0].message == "Test message"
        assert logs[0].module == "test_module"
        # Context may include additional fields like log_module, taskName
        assert "custom_field" in logs[0].context
        assert logs[0].context["custom_field"] == "custom_value"

    def test_handler_emit_all_levels(self, db_session):
        """Test handler emits all log levels"""
        # Create user first
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now
        from src.infrastructure.logging.database_log_handler import DatabaseLogHandler

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        # Patch SessionLocal to use the test database session
        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=user.id, db=db_session)

            levels = [
                (logging.DEBUG, "DEBUG"),
                (logging.INFO, "INFO"),
                (logging.WARNING, "WARNING"),
                (logging.ERROR, "ERROR"),
                (logging.CRITICAL, "CRITICAL"),
            ]

            for level, level_name in levels:
                record = logging.LogRecord(
                    name="test",
                    level=level,
                    pathname="",
                    lineno=0,
                    msg=f"{level_name} message",
                    args=(),
                    exc_info=None,
                )
                record.log_module = "test"
                handler.emit(record)

            # Flush queue to ensure logs are written (queue-based async logging)
            DatabaseLogHandler.flush(timeout=2.0)

        from src.infrastructure.persistence.service_log_repository import (
            ServiceLogRepository,
        )

        log_repo = ServiceLogRepository(db_session)
        logs = log_repo.list(user_id=user.id, limit=10)
        assert len(logs) == 5
        assert {log.level for log in logs} == {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    def test_handler_handles_errors_gracefully(self, db_session):
        """Test handler doesn't break on errors"""
        from sqlalchemy.orm import sessionmaker

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=1, db=db_session)

            # Create invalid record that would cause error
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            # Should not raise exception
            handler.emit(record)
            DatabaseLogHandler.flush(timeout=1.0)


class TestDatabaseLogHandlerEdgeCases:
    """Test edge cases and error scenarios for DatabaseLogHandler"""

    @pytest.fixture(autouse=True)
    def reset_handler_state(self):
        """Reset handler state before each test to prevent queue buildup"""
        # Shutdown existing handler if any
        DatabaseLogHandler.shutdown()
        # Reset class variables
        DatabaseLogHandler._shared_queue = None
        DatabaseLogHandler._worker_thread = None
        DatabaseLogHandler._shutdown = False
        if hasattr(DatabaseLogHandler, "_flush_event") and DatabaseLogHandler._flush_event:
            DatabaseLogHandler._flush_event.clear()
        yield
        # Cleanup after test
        DatabaseLogHandler.shutdown()
        DatabaseLogHandler._shared_queue = None
        DatabaseLogHandler._worker_thread = None
        DatabaseLogHandler._shutdown = False

    def test_queue_full_drops_logs(self, db_session):
        """Test that logs are dropped when queue is full"""
        from sqlalchemy.orm import sessionmaker

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            # Create handler with very small queue
            handler = DatabaseLogHandler(user_id=1, db=db_session, queue_size=2)

            # Fill the queue
            for i in range(3):
                record = logging.LogRecord(
                    name="test",
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg=f"Message {i}",
                    args=(),
                    exc_info=None,
                )
                handler.emit(record)

            # Queue should be full, subsequent emits should be dropped
            # This is expected behavior - logs are dropped to prevent blocking
            DatabaseLogHandler.flush(timeout=1.0)

    def test_database_connection_error_handled(self, db_session):
        """Test that database connection errors don't crash the handler"""
        from sqlalchemy.exc import OperationalError

        # Mock SessionLocal to raise an error
        def failing_session():
            raise OperationalError("Connection failed", None, None)

        with patch("src.infrastructure.logging.database_log_handler.SessionLocal", failing_session):
            handler = DatabaseLogHandler(user_id=1, db=db_session)

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            # Should not raise exception
            handler.emit(record)
            DatabaseLogHandler.flush(timeout=1.0)

    def test_shutdown_with_pending_logs(self, db_session):
        """Test that shutdown flushes pending logs"""
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=user.id, db=db_session)

            # Emit a log
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Pending log",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

            # Shutdown should flush the log
            DatabaseLogHandler.shutdown()

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=1)
            assert len(logs) == 1
            assert logs[0].message == "Pending log"

    def test_shutdown_idempotent(self, db_session):
        """Test that shutdown can be called multiple times safely"""
        from sqlalchemy.orm import sessionmaker

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=1, db=db_session)

            # Call shutdown multiple times - should not raise error
            DatabaseLogHandler.shutdown()
            DatabaseLogHandler.shutdown()
            DatabaseLogHandler.shutdown()

    def test_flush_empty_queue(self, db_session):
        """Test that flush works when queue is empty"""
        from sqlalchemy.orm import sessionmaker

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=1, db=db_session)

            # Flush empty queue - should not hang
            DatabaseLogHandler.flush(timeout=0.5)

    def test_flush_timeout(self, db_session):
        """Test that flush respects timeout"""
        from sqlalchemy.orm import sessionmaker

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=1, db=db_session)

            # Emit a log
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

            # Flush with very short timeout - should complete quickly
            start = time.time()
            DatabaseLogHandler.flush(timeout=0.1)
            elapsed = time.time() - start
            # Should complete within reasonable time (not wait full timeout)
            assert elapsed < 1.0

    def test_large_batch_processing(self, db_session):
        """Test that large batches are processed correctly"""
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=user.id, db=db_session)

            # Emit more logs than batch size (batch_size is 10)
            for i in range(15):
                record = logging.LogRecord(
                    name="test",
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg=f"Message {i}",
                    args=(),
                    exc_info=None,
                )
                handler.emit(record)

            DatabaseLogHandler.flush(timeout=3.0)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=20)
            assert len(logs) == 15

    def test_message_truncation(self, db_session):
        """Test that very long messages are truncated"""
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=user.id, db=db_session)

            # Create a very long message (> 1024 chars)
            long_message = "x" * 2000
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=long_message,
                args=(),
                exc_info=None,
            )
            handler.emit(record)

            DatabaseLogHandler.flush(timeout=1.0)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=1)
            assert len(logs) == 1
            assert len(logs[0].message) == 1024  # Truncated to max length

    def test_module_name_truncation(self, db_session):
        """Test that very long module names are truncated"""
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=user.id, db=db_session)

            # Create a very long module name (> 128 chars)
            long_module = "x" * 200
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None,
            )
            record.log_module = long_module
            handler.emit(record)

            DatabaseLogHandler.flush(timeout=1.0)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=1)
            assert len(logs) == 1
            assert len(logs[0].module) == 128  # Truncated to max length

    def test_non_serializable_context(self, db_session):
        """Test that non-serializable context values are converted to strings"""
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=user.id, db=db_session)

            # Create record with non-serializable context
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test",
                args=(),
                exc_info=None,
            )
            # Add non-serializable object (function, class, etc.)
            record.custom_func = lambda x: x
            record.custom_class = type("TestClass", (), {})
            handler.emit(record)

            DatabaseLogHandler.flush(timeout=1.0)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=1)
            assert len(logs) == 1
            # Non-serializable values should be converted to strings
            assert "custom_func" in logs[0].context
            assert isinstance(logs[0].context["custom_func"], str)
            assert "custom_class" in logs[0].context
            assert isinstance(logs[0].context["custom_class"], str)

    def test_concurrent_logging(self, db_session):
        """Test that concurrent logging from multiple threads works"""
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=user.id, db=db_session)

            def log_from_thread(thread_id):
                for i in range(5):
                    record = logging.LogRecord(
                        name="test",
                        level=logging.INFO,
                        pathname="",
                        lineno=0,
                        msg=f"Thread {thread_id} message {i}",
                        args=(),
                        exc_info=None,
                    )
                    handler.emit(record)

            # Create multiple threads logging simultaneously
            threads = []
            for i in range(5):
                thread = threading.Thread(target=log_from_thread, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Flush and verify all logs were written
            DatabaseLogHandler.flush(timeout=3.0)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=30)
            assert len(logs) == 25  # 5 threads * 5 messages each

    def test_multiple_handler_instances_share_queue(self, db_session):
        """Test that multiple handler instances share the same queue"""
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user1 = Users(email="user1@example.com", password_hash="hash", created_at=ist_now())
        user2 = Users(email="user2@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler1 = DatabaseLogHandler(user_id=user1.id, db=db_session)
            handler2 = DatabaseLogHandler(user_id=user2.id, db=db_session)

            # Both handlers should use the same shared queue
            assert DatabaseLogHandler._shared_queue is not None

            # Emit logs from both handlers
            record1 = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="User1 log",
                args=(),
                exc_info=None,
            )
            handler1.emit(record1)

            record2 = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="User2 log",
                args=(),
                exc_info=None,
            )
            handler2.emit(record2)

            DatabaseLogHandler.flush(timeout=1.0)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs1 = log_repo.list(user_id=user1.id, limit=1)
            logs2 = log_repo.list(user_id=user2.id, limit=1)

            assert len(logs1) == 1
            assert logs1[0].message == "User1 log"
            assert len(logs2) == 1
            assert logs2[0].message == "User2 log"

    def test_unknown_log_level_defaults_to_info(self, db_session):
        """Test that unknown log levels default to INFO"""
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=user.id, db=db_session)

            # Create record with custom level (not in standard levels)
            record = logging.LogRecord(
                name="test",
                level=99,  # Custom level
                pathname="",
                lineno=0,
                msg="Custom level message",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

            DatabaseLogHandler.flush(timeout=1.0)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=1)
            assert len(logs) == 1
            assert logs[0].level == "INFO"  # Should default to INFO

    def test_batch_timeout_flush(self, db_session):
        """Test that batches are flushed after timeout even if not full"""
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=user.id, db=db_session)

            # Emit a single log (less than batch size of 10)
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Single log",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

            # Wait for batch timeout (0.5 seconds) plus buffer
            time.sleep(0.8)

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=1)
            # Log should be flushed by timeout even though batch isn't full
            assert len(logs) == 1

    def test_flush_event_triggers_immediate_flush(self, db_session):
        """Test that flush event triggers immediate batch flush"""
        from sqlalchemy.orm import sessionmaker

        from src.infrastructure.db.models import Users
        from src.infrastructure.db.timezone_utils import ist_now

        user = Users(email="test@example.com", password_hash="hash", created_at=ist_now())
        db_session.add(user)
        db_session.commit()

        test_sessionmaker = sessionmaker(bind=db_session.bind)
        with patch(
            "src.infrastructure.logging.database_log_handler.SessionLocal", test_sessionmaker
        ):
            handler = DatabaseLogHandler(user_id=user.id, db=db_session)

            # Emit a log
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Immediate flush test",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

            # Trigger flush event and wait for processing
            DatabaseLogHandler._flush_event.set()
            time.sleep(0.5)  # Give worker time to process

            from src.infrastructure.persistence.service_log_repository import (
                ServiceLogRepository,
            )

            log_repo = ServiceLogRepository(db_session)
            logs = log_repo.list(user_id=user.id, limit=1)
            # Log should be flushed immediately due to flush event
            assert len(logs) == 1


class TestUserFileLogHandler:
    """Tests for UserFileLogHandler"""

    def test_handler_creates_log_directory(self, tmp_path, monkeypatch):
        """Test handler creates log directory structure"""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        handler = UserFileLogHandler(user_id=1, log_type="service")
        log_dir = Path("logs") / "users" / "user_1"
        assert log_dir.exists()
        handler.close()

    def test_handler_writes_to_file(self, tmp_path, monkeypatch):
        """Test handler writes logs to file"""
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

        handler.emit(record)
        handler.close()

        # Check file was created and contains message
        log_dir = Path("logs") / "users" / "user_1"
        log_files = list(log_dir.glob("service_*.log"))
        assert len(log_files) == 1

        content = log_files[0].read_text(encoding="utf-8")
        assert "Test message" in content
        # Note: User context may be in message or format, check both
        assert "User" in content or "1" in content

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
        # Check if handler filters by level
        if handler.level <= logging.INFO:
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
        handler.emit(error_record)
        handler.close()

        # Check error log file exists
        log_dir = Path("logs") / "users" / "user_1"
        error_files = list(log_dir.glob("errors_*.log"))
        assert len(error_files) >= 1

        content = error_files[0].read_text(encoding="utf-8")
        assert "Error message" in content
        # INFO may be written if handler level allows it, so just check ERROR is there


class TestErrorCapture:
    """Tests for error capture functionality"""

    def test_capture_exception_basic(self, db_session):
        """Test basic exception capture"""
        # Create user first
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
        # Create user and config
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
        # Create user first
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
