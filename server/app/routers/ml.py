# ruff: noqa: B008

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from server.app.core.deps import get_db, require_admin
from server.app.schemas.ml import (
    ActivateModelResponse,
    MLModelsResponse,
    MLTrainingJobResponse,
    MLTrainingJobsResponse,
    MLTrainingRequest,
)
from src.application.services.ml_training_service import MLTrainingService, TrainingJobConfig
from src.infrastructure.db.session import SessionLocal

router = APIRouter(prefix="/admin/ml", tags=["admin-ml"])


def get_ml_training_service(db: Session = Depends(get_db)) -> MLTrainingService:
    return MLTrainingService(db)


def _to_config(request: MLTrainingRequest) -> TrainingJobConfig:
    return TrainingJobConfig(
        model_type=request.model_type,
        algorithm=request.algorithm,
        training_data_path=request.training_data_path,
        hyperparameters=request.hyperparameters or {},
        notes=request.notes,
        auto_activate=request.auto_activate,
    )


def _run_training_job_async(job_id: int, config_data: dict[str, Any]) -> None:
    """Execute a training job using a fresh DB session (runs in background)."""
    db = SessionLocal()
    try:
        service = MLTrainingService(db)
        service.run_training_job(job_id=job_id, config=TrainingJobConfig(**config_data))
    finally:
        db.close()


@router.post("/train", response_model=MLTrainingJobResponse, status_code=status.HTTP_201_CREATED)
def start_ml_training(
    request: MLTrainingRequest,
    background_tasks: BackgroundTasks,
    admin=Depends(require_admin),
    service: MLTrainingService = Depends(get_ml_training_service),
) -> MLTrainingJobResponse:
    """
    Start a new ML training job (admin only).

    Jobs execute asynchronously and will update their status once complete.
    """
    config = _to_config(request)
    job = service.start_training_job(started_by=admin.id, config=config)
    background_tasks.add_task(_run_training_job_async, job.id, asdict(config))
    return job


@router.get("/jobs", response_model=MLTrainingJobsResponse)
def list_training_jobs(
    status_filter: str | None = Query(
        None, alias="status", description="Optional status filter (pending/running/...)"
    ),
    model_type: str | None = Query(None, description="Filter by model type"),
    limit: int = Query(100, ge=1, le=250),
    admin=Depends(require_admin),
    service: MLTrainingService = Depends(get_ml_training_service),
):
    """List ML training jobs."""
    _ = admin  # Admin dependency ensures authorization
    jobs = service.job_repo.list(status=status_filter, model_type=model_type, limit=limit)
    return MLTrainingJobsResponse(jobs=jobs)


@router.get("/jobs/{job_id}", response_model=MLTrainingJobResponse)
def get_training_job(
    job_id: int,
    admin=Depends(require_admin),
    service: MLTrainingService = Depends(get_ml_training_service),
):
    """Retrieve a specific training job."""
    _ = admin
    job = service.job_repo.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training job not found")
    return job


@router.get("/models", response_model=MLModelsResponse)
def list_models(
    model_type: str | None = Query(None),
    active_only: bool | None = Query(
        None, description="Set to true to only include active models", alias="active"
    ),
    admin=Depends(require_admin),
    service: MLTrainingService = Depends(get_ml_training_service),
):
    """List trained ML models."""
    _ = admin
    models = service.model_repo.list(model_type=model_type, is_active=active_only)
    return MLModelsResponse(models=models)


@router.post(
    "/models/{model_id}/activate",
    response_model=ActivateModelResponse,
)
def activate_model(
    model_id: int,
    admin=Depends(require_admin),
    service: MLTrainingService = Depends(get_ml_training_service),
):
    """Activate a trained model version."""
    _ = admin
    model = service.model_repo.get(model_id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    updated_model = service.model_repo.set_active(model_id)
    return ActivateModelResponse(
        message=f"Model {updated_model.version} activated for {updated_model.model_type}",
        model=updated_model,
    )
