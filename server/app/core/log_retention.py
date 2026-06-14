"""Per-user log file retention cleanup."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from server.app.core.config import settings

logger = logging.getLogger(__name__)


def cleanup_user_log_files(logs_root: str | Path | None = None) -> int:
    """
    Delete per-user log files older than log_retention_days.

    Returns:
        Number of files removed.
    """
    root = Path(logs_root or os.getenv("LOG_DIR", "logs"))
    if not root.exists():
        return 0

    retention_seconds = settings.log_retention_days * 86400
    cutoff = time.time() - retention_seconds
    removed = 0

    for path in root.rglob("*.log"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            logger.warning("Could not remove old log file: %s", path)

    if removed:
        logger.info("Log retention: removed %s files older than %s days", removed, settings.log_retention_days)
    return removed
