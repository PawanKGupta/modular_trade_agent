from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.error_log_repository import ErrorLogRepository
from src.infrastructure.persistence.service_log_repository import ServiceLogRepository


class LogRetentionService:
    """Prunes service and error logs older than the configured retention window."""

    def __init__(self, db: Session):
        self.db = db
        self.service_logs = ServiceLogRepository(db)
        self.error_logs = ErrorLogRepository(db)

    def purge_older_than(self, days: int) -> dict[str, int]:
        """Delete logs older than the provided number of days."""
        cutoff = ist_now() - timedelta(days=days)
        removed_service = self.service_logs.delete_old_logs_for_all(cutoff)
        removed_errors = self.error_logs.delete_old_errors_for_all(cutoff, resolved_only=False)
        return {"service_logs": removed_service, "error_logs": removed_errors}
