"""
User-Scoped Logging Infrastructure (file-only)

Provides logging with user context and file logging. Activity logs are stored
as per-user JSONL files; ErrorLog remains in the database.
"""

from src.infrastructure.logging.error_capture import capture_exception
from src.infrastructure.logging.file_log_reader import FileLogReader
from src.infrastructure.logging.user_file_log_handler import (
    UserErrorFileLogHandler,
    UserFileLogHandler,
)
from src.infrastructure.logging.user_scoped_logger import (
    UserScopedLogger,
    get_user_logger,
)

__all__ = [
    "UserScopedLogger",
    "get_user_logger",
    "UserFileLogHandler",
    "UserErrorFileLogHandler",
    "FileLogReader",
    "capture_exception",
]
