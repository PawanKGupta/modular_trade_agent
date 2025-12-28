"""Repository for ExportJob management (Phase 0.7)"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.infrastructure.db.models import ExportJob

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class ExportJobRepository:
    """Repository for managing export job records"""

    def __init__(self, db: Session):
        self.db = db

    def create(self, job: ExportJob) -> ExportJob:
        """Create a new export job record"""
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_by_id(self, job_id: int) -> ExportJob | None:
        """Get export job by ID"""
        return self.db.get(ExportJob, job_id)

    def get_by_user(
        self, user_id: int, status: str | None = None, limit: int = 100
    ) -> list[ExportJob]:
        """Get export jobs for a user, optionally filtered by status"""
        stmt = select(ExportJob).where(ExportJob.user_id == user_id)

        if status:
            stmt = stmt.where(ExportJob.status == status)

        stmt = stmt.order_by(ExportJob.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_latest(self, user_id: int, data_type: str | None = None) -> ExportJob | None:
        """Get the most recent export job for a user"""
        stmt = select(ExportJob).where(ExportJob.user_id == user_id)

        if data_type:
            stmt = stmt.where(ExportJob.data_type == data_type)

        stmt = stmt.order_by(ExportJob.created_at.desc()).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()

    def update_status(
        self,
        job_id: int,
        status: str,
        progress: int | None = None,
        error_message: str | None = None,
    ) -> ExportJob | None:
        """Update export job status"""
        job = self.get_by_id(job_id)
        if not job:
            return None

        job.status = status

        if progress is not None:
            job.progress = progress

        if error_message is not None:
            job.error_message = error_message

        if status == "processing" and job.started_at is None:
            job.started_at = datetime.now()
        elif status in ("completed", "failed") and job.completed_at is None:
            job.completed_at = datetime.now()
            if job.started_at:
                duration = (job.completed_at - job.started_at).total_seconds()
                job.duration_seconds = duration

        self.db.commit()
        self.db.refresh(job)
        return job

    def update_progress(self, job_id: int, progress: int) -> ExportJob | None:
        """Update export job progress (0-100)"""
        job = self.get_by_id(job_id)
        if not job:
            return None

        job.progress = max(0, min(100, progress))  # Clamp to 0-100
        self.db.commit()
        self.db.refresh(job)
        return job

    def complete_job(
        self,
        job_id: int,
        file_path: str | None = None,
        file_size: int | None = None,
        records_exported: int | None = None,
    ) -> ExportJob | None:
        """Mark export job as completed with results"""
        job = self.get_by_id(job_id)
        if not job:
            return None

        job.status = "completed"
        job.progress = 100
        job.file_path = file_path
        job.file_size = file_size
        job.records_exported = records_exported

        if job.completed_at is None:
            job.completed_at = datetime.now()
            if job.started_at:
                duration = (job.completed_at - job.started_at).total_seconds()
                job.duration_seconds = duration

        self.db.commit()
        self.db.refresh(job)
        return job

    def fail_job(self, job_id: int, error_message: str) -> ExportJob | None:
        """Mark export job as failed"""
        return self.update_status(job_id, "failed", error_message=error_message)

