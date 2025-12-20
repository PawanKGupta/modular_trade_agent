from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.error_log_repository import ErrorLogRepository

logger = logging.getLogger(__name__)


class LogRetentionService:
    """Prunes service and error logs older than the configured retention window."""

    def __init__(self, db: Session):
        self.db = db
        self.error_logs = ErrorLogRepository(db)

    def _prune_file_logs(self, log_base_dir: Path, days: int) -> int:
        """Delete JSONL log files older than the provided number of days."""
        cutoff_date = ist_now().date() - timedelta(days=days)
        removed = 0
        log_dir = log_base_dir / "users"
        if not log_dir.exists():
            return removed

        for path in log_dir.glob("user_*/**/*.jsonl"):
            try:
                # Expect filenames like service_YYYYMMDD.jsonl or errors_YYYYMMDD.jsonl
                name = path.name
                if "_" not in name:
                    continue
                date_part = name.split("_")[-1].replace(".jsonl", "")
                file_date = datetime.strptime(date_part, "%Y%m%d").date()
                if file_date < cutoff_date:
                    path.unlink(missing_ok=True)
                    removed += 1
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to prune log file %s: %s", path, exc, exc_info=False)
                continue
        return removed

    def purge_older_than(self, days: int, log_base_dir: str | Path = "logs") -> dict[str, int]:
        """Delete logs older than the provided number of days."""
        cutoff = ist_now() - timedelta(days=days)
        removed_errors = self.error_logs.delete_old_errors_for_all(cutoff, resolved_only=False)
        removed_files = self._prune_file_logs(Path(log_base_dir), days)
        return {"service_logs_files": removed_files, "error_logs": removed_errors}
