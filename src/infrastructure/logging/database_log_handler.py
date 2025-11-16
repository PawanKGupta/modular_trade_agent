"""
Database Logging Handler

Writes structured logs to ServiceLog table in database.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.infrastructure.persistence.service_log_repository import ServiceLogRepository


class DatabaseLogHandler(logging.Handler):
    """
    Logging handler that writes logs to ServiceLog table.
    
    Provides structured logging with user context, level, module, message,
    and additional context data stored as JSON.
    """

    def __init__(self, user_id: int, db: Session, level: int = logging.NOTSET):
        """
        Initialize database log handler.
        
        Args:
            user_id: User ID for log entries
            db: Database session
            level: Minimum logging level (default: NOTSET = all levels)
        """
        super().__init__(level)
        self.user_id = user_id
        self.db = db
        self.repository = ServiceLogRepository(db)

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to the database.
        
        Args:
            record: LogRecord to emit
        """
        try:
            # Extract level name - map to standard levels
            level_map = {
                logging.DEBUG: "DEBUG",
                logging.INFO: "INFO",
                logging.WARNING: "WARNING",
                logging.ERROR: "ERROR",
                logging.CRITICAL: "CRITICAL",
            }
            level_name = level_map.get(record.levelno, "INFO")

            # Extract module from record (prefer log_module, fallback to name)
            module = getattr(record, "log_module", getattr(record, "module", record.name))

            # Extract context (all extra fields except standard logging fields)
            context = {}
            standard_fields = {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "user_id",  # We'll add this separately
            }

            for key, value in record.__dict__.items():
                if key not in standard_fields:
                    # Only include JSON-serializable values
                    try:
                        import json

                        json.dumps(value)  # Test if serializable
                        context[key] = value
                    except (TypeError, ValueError):
                        # Convert non-serializable to string
                        context[key] = str(value)

            # Create log entry
            self.repository.create(
                user_id=self.user_id,
                level=level_name,  # type: ignore
                module=module[:128],  # Truncate to max length
                message=str(record.getMessage())[:1024],  # Truncate to max length
                context=context if context else None,
            )

        except Exception:
            # Don't let logging errors break the application
            # Use handleError to log the issue
            self.handleError(record)

