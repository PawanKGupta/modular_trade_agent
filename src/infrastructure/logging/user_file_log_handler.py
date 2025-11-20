"""
User File Logging Handler

Writes logs to per-user log files organized by date.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class UserFileLogHandler(logging.FileHandler):
    """
    Logging handler that writes logs to per-user log files.

    File structure:
    logs/
    ??? users/
    ?   ??? user_1/
    ?   ?   ??? service_20250115.log
    ?   ?   ??? service_20250116.log
    ?   ?   ??? errors_20250115.log
    ?   ??? user_2/
    ?   ?   ??? ...
    """

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
        # Create log directory structure
        log_dir = Path("logs") / "users" / f"user_{user_id}"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create date-based log filename
        today = datetime.now().strftime("%Y%m%d")
        log_filename = log_dir / f"{log_type}_{today}.log"

        # Initialize file handler with UTF-8 encoding
        super().__init__(
            filename=str(log_filename),
            mode="a",
            encoding="utf-8",
            delay=False,
        )

        self.user_id = user_id
        self.log_type = log_type

        # Set formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(module)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.setFormatter(formatter)
        self.setLevel(level)

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to the file.

        Args:
            record: LogRecord to emit
        """
        try:
            # Check if we need to rotate to a new file (new day)
            today = datetime.now().strftime("%Y%m%d")
            current_file = Path(self.baseFilename)
            expected_file = current_file.parent / f"{self.log_type}_{today}.log"

            if current_file != expected_file:
                # Day changed, close old file and open new one
                if self.stream:
                    self.stream.close()
                self.baseFilename = str(expected_file)
                self.stream = self._open()

            # Add user context to message if not already present
            msg = record.getMessage()
            if f"[User {self.user_id}]" not in msg:
                # Update the message in the record
                record.msg = f"[User {self.user_id}] {record.msg}"
                record.args = ()  # Clear args since we've formatted the message

            super().emit(record)

        except Exception:
            # Don't let logging errors break the application
            self.handleError(record)


class UserErrorFileLogHandler(UserFileLogHandler):
    """
    Specialized handler for error logs only.

    Writes to errors_YYYYMMDD.log files.
    """

    def __init__(self, user_id: int, level: int = logging.ERROR):
        """
        Initialize error file log handler.

        Args:
            user_id: User ID for log file organization
            level: Minimum logging level (default: ERROR)
        """
        super().__init__(user_id=user_id, log_type="errors", level=level)
