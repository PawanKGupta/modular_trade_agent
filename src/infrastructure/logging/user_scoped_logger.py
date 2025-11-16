"""
User-Scoped Logging System

Provides user-aware logging with database and file handlers.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.infrastructure.logging.database_log_handler import DatabaseLogHandler
from src.infrastructure.logging.error_capture import capture_exception
from src.infrastructure.logging.user_file_log_handler import (
    UserErrorFileLogHandler,
    UserFileLogHandler,
)


class UserScopedLogger:
    """
    Logger wrapper that adds user context to all logs.

    Provides:
    - Database logging (structured logs in ServiceLog table)
    - File logging (per-user log files)
    - Error capture (exceptions stored in ErrorLog table)
    - Context injection (user_id, module, task, etc.)
    """

    def __init__(
        self,
        user_id: int,
        base_logger: logging.Logger,
        db: Session,
        module: str = "unknown",
    ):
        """
        Initialize user-scoped logger.

        Args:
            user_id: User ID for log context
            base_logger: Base Python logger to wrap
            db: Database session for database logging
            module: Module/component name (default: "unknown")
        """
        self.user_id = user_id
        self.logger = base_logger
        self.module = module
        self.db = db

        # Create handlers
        self.db_handler = DatabaseLogHandler(user_id=user_id, db=db)
        self.file_handler = UserFileLogHandler(user_id=user_id)
        self.error_file_handler = UserErrorFileLogHandler(user_id=user_id)

        # Note: We don't add handlers to the base logger directly
        # Instead, we emit records through the handlers manually
        # This prevents handler duplication across multiple UserScopedLogger instances

    def debug(self, message: str, **context: Any) -> None:
        """Log debug message with user context"""
        self._log(logging.DEBUG, message, context)

    def info(self, message: str, **context: Any) -> None:
        """Log info message with user context"""
        self._log(logging.INFO, message, context)

    def warning(self, message: str, **context: Any) -> None:
        """Log warning message with user context"""
        self._log(logging.WARNING, message, context)

    def error(
        self,
        message: str,
        exc_info: Exception | None = None,
        **context: Any,
    ) -> None:
        """
        Log error message with user context and exception capture.

        Args:
            message: Error message
            exc_info: Exception object to capture (optional)
            **context: Additional context data
        """
        self._log(logging.ERROR, message, context, exc_info=exc_info)
        if exc_info:
            self._capture_exception(exc_info, context)

    def critical(
        self,
        message: str,
        exc_info: Exception | None = None,
        **context: Any,
    ) -> None:
        """
        Log critical message with user context and exception capture.

        Args:
            message: Critical message
            exc_info: Exception object to capture (optional)
            **context: Additional context data
        """
        self._log(logging.CRITICAL, message, context, exc_info=exc_info)
        if exc_info:
            self._capture_exception(exc_info, context)

    def _log(
        self,
        level: int,
        message: str,
        context: dict[str, Any],
        exc_info: Exception | None = None,
    ) -> None:
        """
        Internal logging with user context.

        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            context: Additional context data
            exc_info: Exception object (optional)
        """
        # Add user context (use 'log_module' instead of 'module' to avoid conflict)
        log_context = context.copy()
        log_context["user_id"] = self.user_id
        log_context["log_module"] = self.module  # Use 'log_module' to avoid LogRecord conflict

        # Convert exc_info to proper format if it's an Exception object
        # Python logging expects exc_info to be: None, True, or (type, value, traceback) tuple
        if exc_info and isinstance(exc_info, BaseException):
            exc_info = (type(exc_info), exc_info, exc_info.__traceback__)

        # Create log record with context
        record = logging.LogRecord(
            name=self.logger.name,
            level=level,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=exc_info,
        )
        record.__dict__.update(log_context)

        # Emit to base logger (console/file if configured)
        # Use 'extra' parameter but exclude 'module' to avoid LogRecord conflict
        safe_extra = {k: v for k, v in log_context.items() if k != "module"}
        self.logger.log(level, message, extra=safe_extra, exc_info=exc_info)

        # Emit to database handler
        self.db_handler.emit(record)

        # Emit to file handler (all logs)
        self.file_handler.emit(record)

        # Emit to error file handler (ERROR and CRITICAL only)
        if level >= logging.ERROR:
            self.error_file_handler.emit(record)

    def _capture_exception(self, exception: Exception, context: dict[str, Any]) -> None:
        """
        Capture exception with full context to ErrorLog table.

        Args:
            exception: Exception to capture
            context: Additional context data
        """
        try:
            capture_exception(
                user_id=self.user_id,
                exception=exception,
                context=context,
                db=self.db,
            )
        except Exception as e:
            # Fallback: log to base logger if error capture fails
            self.logger.error(
                f"Failed to capture exception: {e}",
                exc_info=True,
                extra={"original_exception": str(exception)},
            )

    def set_module(self, module: str) -> None:
        """
        Update module name for subsequent logs.

        Args:
            module: New module name
        """
        self.module = module

    def close(self) -> None:
        """Close handlers and cleanup resources"""
        if self.db_handler in self.logger.handlers:
            self.logger.removeHandler(self.db_handler)
        if self.file_handler in self.logger.handlers:
            self.logger.removeHandler(self.file_handler)
        if self.error_file_handler in self.logger.handlers:
            self.logger.removeHandler(self.error_file_handler)
        self.file_handler.close()
        self.error_file_handler.close()


def get_user_logger(user_id: int, db: Session, module: str = "unknown") -> UserScopedLogger:
    """
    Factory function to create a user-scoped logger.

    Args:
        user_id: User ID for log context
        db: Database session
        module: Module/component name

    Returns:
        UserScopedLogger instance
    """
    base_logger = logging.getLogger(f"TradeAgent.User{user_id}")
    return UserScopedLogger(user_id=user_id, base_logger=base_logger, db=db, module=module)
