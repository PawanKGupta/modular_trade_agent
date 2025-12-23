"""Export API router (Phase 0.7)"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.infrastructure.db.models import ExportJob, Users
from src.infrastructure.persistence.export_job_repository import ExportJobRepository

from ..core.deps import get_current_user, get_db

router = APIRouter()


@router.get("/jobs", response_model=list[dict])
def list_export_jobs(
    status: str | None = Query(default=None, description="Filter by status"),
    data_type: str | None = Query(default=None, description="Filter by data type"),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of jobs to return"),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    List export jobs for the current user (Phase 0.7).

    Returns list of export job records showing status, progress, and results.
    """
    try:
        job_repo = ExportJobRepository(db)

        # Get jobs filtered by status if provided
        if status:
            jobs = job_repo.get_by_user(current.id, status=status, limit=limit)
        else:
            jobs = job_repo.get_by_user(current.id, limit=limit)

        # Filter by data_type if provided
        if data_type:
            jobs = [job for job in jobs if job.data_type == data_type]

        # Convert to dict for response
        return [
            {
                "id": job.id,
                "export_type": job.export_type,
                "data_type": job.data_type,
                "date_range_start": job.date_range_start.isoformat()
                if job.date_range_start
                else None,
                "date_range_end": job.date_range_end.isoformat()
                if job.date_range_end
                else None,
                "status": job.status,
                "progress": job.progress,
                "file_path": job.file_path,
                "file_size": job.file_size,
                "records_exported": job.records_exported,
                "duration_seconds": job.duration_seconds,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
            for job in jobs
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch export jobs: {str(e)}"
        ) from e


@router.get("/jobs/{job_id}", response_model=dict)
def get_export_job(
    job_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Get details of a specific export job (Phase 0.7).

    Returns full details of the export job including status, progress, and results.
    """
    try:
        job_repo = ExportJobRepository(db)
        job = job_repo.get_by_id(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Export job not found")

        # Verify job belongs to current user
        if job.user_id != current.id:
            raise HTTPException(status_code=403, detail="Access denied")

        return {
            "id": job.id,
            "export_type": job.export_type,
            "data_type": job.data_type,
            "date_range_start": job.date_range_start.isoformat()
            if job.date_range_start
            else None,
            "date_range_end": job.date_range_end.isoformat()
            if job.date_range_end
            else None,
            "status": job.status,
            "progress": job.progress,
            "file_path": job.file_path,
            "file_size": job.file_size,
            "records_exported": job.records_exported,
            "duration_seconds": job.duration_seconds,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch export job: {str(e)}"
        ) from e

