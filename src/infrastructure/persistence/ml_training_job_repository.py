"""Repository for MLTrainingJob management"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import MLTrainingJob
from src.infrastructure.db.timezone_utils import ist_now


class MLTrainingJobRepository:
    """Repository for managing ML training jobs"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        started_by: int,
        model_type: str,
        algorithm: str,
        training_data_path: str,
    ) -> MLTrainingJob:
        """Create a new training job"""
        job = MLTrainingJob(
            started_by=started_by,
            status="pending",
            model_type=model_type,
            algorithm=algorithm,
            training_data_path=training_data_path,
            started_at=ist_now(),
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: int) -> MLTrainingJob | None:
        """Get training job by ID"""
        return self.db.get(MLTrainingJob, job_id)

    def list(
        self,
        started_by: int | None = None,
        status: Literal["pending", "running", "completed", "failed"] | None = None,
        model_type: str | None = None,
        limit: int = 100,
    ) -> list[MLTrainingJob]:
        """List training jobs with filters"""
        stmt = select(MLTrainingJob)

        if started_by:
            stmt = stmt.where(MLTrainingJob.started_by == started_by)
        if status:
            stmt = stmt.where(MLTrainingJob.status == status)
        if model_type:
            stmt = stmt.where(MLTrainingJob.model_type == model_type)

        stmt = stmt.order_by(desc(MLTrainingJob.started_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def update_status(
        self,
        job_id: int,
        status: Literal["pending", "running", "completed", "failed"],
        error_message: str | None = None,
        model_path: str | None = None,
        accuracy: float | None = None,
        logs: str | None = None,
    ) -> MLTrainingJob:
        """Update training job status"""
        job = self.get(job_id)
        if not job:
            raise ValueError(f"Training job {job_id} not found")

        job.status = status
        if status == "completed":
            job.completed_at = ist_now()
        if error_message:
            job.error_message = error_message[:1024]  # Truncate to max length
        if model_path:
            job.model_path = model_path
        if accuracy is not None:
            job.accuracy = accuracy
        if logs:
            job.logs = logs[:16384]  # Truncate to max length

        self.db.commit()
        self.db.refresh(job)
        return job

    def get_running(self) -> list[MLTrainingJob]:
        """Get all running training jobs"""
        return self.list(status="running")
