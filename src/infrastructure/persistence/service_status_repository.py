"""Repository for ServiceStatus management"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.infrastructure.db.models import ServiceStatus
from src.infrastructure.db.timezone_utils import ist_now


class ServiceStatusRepository:
    """Repository for managing service status per user"""

    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> ServiceStatus | None:
        """Get service status for a user"""
        return self.db.query(ServiceStatus).filter(ServiceStatus.user_id == user_id).first()

    def get_or_create(self, user_id: int) -> ServiceStatus:
        """Get or create service status for a user"""
        status = self.get(user_id)
        if not status:
            status = ServiceStatus(
                user_id=user_id,
                service_running=False,
                error_count=0,
            )
            self.db.add(status)
            self.db.commit()
            self.db.refresh(status)
        return status

    def update_running(self, user_id: int, running: bool) -> ServiceStatus:
        """Update service running status"""
        status = self.get_or_create(user_id)
        status.service_running = running
        status.updated_at = ist_now()
        self.db.flush()  # Flush changes without committing (let caller manage transaction)
        self.db.refresh(status)
        return status

    def update_heartbeat(self, user_id: int) -> ServiceStatus:
        """Update last heartbeat timestamp"""
        status = self.get_or_create(user_id)
        status.last_heartbeat = ist_now()
        status.updated_at = ist_now()
        self.db.flush()  # Flush changes without committing (let caller manage transaction)
        self.db.refresh(status)
        return status

    def update_task_execution(self, user_id: int) -> ServiceStatus:
        """Update last task execution timestamp"""
        status = self.get_or_create(user_id)
        status.last_task_execution = ist_now()
        status.updated_at = ist_now()
        self.db.flush()  # Flush changes without committing (let caller manage transaction)
        self.db.refresh(status)
        return status

    def increment_error(self, user_id: int, error_message: str | None = None) -> ServiceStatus:
        """Increment error count and update last error"""
        status = self.get_or_create(user_id)
        status.error_count += 1
        if error_message:
            status.last_error = error_message[:512]  # Truncate to max length
        status.updated_at = ist_now()
        self.db.flush()  # Flush changes without committing (let caller manage transaction)
        self.db.refresh(status)
        return status

    def reset_errors(self, user_id: int) -> ServiceStatus:
        """Reset error count"""
        status = self.get_or_create(user_id)
        status.error_count = 0
        status.last_error = None
        status.updated_at = ist_now()
        self.db.flush()  # Flush changes without committing (let caller manage transaction)
        self.db.refresh(status)
        return status
