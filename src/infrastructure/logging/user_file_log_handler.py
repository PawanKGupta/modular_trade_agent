"""
User File Logging Handler (JSONL)

Writes per-user JSONL logs organized by date.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.infrastructure.db.timezone_utils import ist_now

logger = logging.getLogger(__name__)


class UserFileLogHandler(logging.Handler):
    """
    Logging handler that writes logs to per-user JSONL files.

    File structure:
    logs/
      users/
        user_{id}/
          service_YYYYMMDD.jsonl
          errors_YYYYMMDD.jsonl
    """

    STANDARD_FIELDS = {
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
        "taskName",
        "user_id",
        "log_module",
    }

    def __init__(
        self,
        user_id: int,
        log_type: str = "service",
        level: int = logging.NOTSET,
    ):
        """
        Initialize user file log handler.

        Args:
            user_id: User ID for log file organization
            log_type: Type of log file ('service' or 'errors')
            level: Minimum logging level (default: NOTSET = all levels)
        """
        super().__init__(level)
        self.user_id = user_id
        self.log_type = log_type

        log_dir = Path("logs") / "users" / f"user_{user_id}"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        self.base_path = log_dir
        self.baseFilename = str(log_dir / f"{log_type}_{today}.jsonl")
        self.stream = open(self.baseFilename, "a", encoding="utf-8")

    def _ensure_current_file(self) -> None:
        today = datetime.now().strftime("%Y%m%d")
        expected = self.base_path / f"{self.log_type}_{today}.jsonl"
        if self.baseFilename != str(expected):
            try:
                if self.stream:
                    self.stream.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to rotate log file handle: %s", exc, exc_info=False)
            self.baseFilename = str(expected)
            self.stream = open(self.baseFilename, "a", encoding="utf-8")

    def _build_context(self, record: logging.LogRecord) -> dict[str, Any] | None:
        context: dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key in self.STANDARD_FIELDS:
                continue
            try:
                json.dumps(value)  # test serializability
                context[key] = value
            except (TypeError, ValueError):
                context[key] = str(value)
        return context or None

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to JSONL file.
        """
        try:
            self._ensure_current_file()

            module_name = getattr(record, "log_module", getattr(record, "module", record.name))
            payload = {
                "timestamp": ist_now().isoformat(),
                "level": record.levelname,
                "module": module_name,
                "message": record.getMessage(),
                "context": self._build_context(record),
                "user_id": self.user_id,
            }

            line = json.dumps(payload, ensure_ascii=False)
            self.stream.write(line + "\n")
            self.stream.flush()

        except Exception:
            self.handleError(record)

    def close(self) -> None:
        try:
            if self.stream and not self.stream.closed:
                self.stream.close()
        finally:
            super().close()


class UserErrorFileLogHandler(UserFileLogHandler):
    """
    Specialized handler for error logs only.

    Writes to errors_YYYYMMDD.jsonl files.
    """

    def __init__(self, user_id: int, level: int = logging.ERROR):
        """
        Initialize error file log handler.

        Args:
            user_id: User ID for log file organization
            level: Minimum logging level (default: ERROR)
        """
        super().__init__(user_id=user_id, log_type="errors", level=level)
