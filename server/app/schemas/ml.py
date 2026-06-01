from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, constr


class MLTrainingRequest(BaseModel):
    """Request payload for starting an ML training job."""

    model_config = ConfigDict(protected_namespaces=())

    model_type: Literal["verdict_classifier", "price_regressor"]
    algorithm: Literal["random_forest", "xgboost", "logistic_regression"]
    training_data_path: constr(min_length=1, strip_whitespace=True, max_length=512)
    hyperparameters: dict[str, float | int | str | bool] = Field(default_factory=dict)
    notes: constr(max_length=512) | None = None
    auto_activate: bool = False
    incremental_training: bool = Field(
        default=True,
        description=(
            "When true and an active model has a watermark, require baseline + new CSV rows "
            "for supervised refits."
        ),
    )
    training_run_end_date: date | None = Field(
        default=None,
        description=(
            "Inclusive cap on row dates (entry/backtest). Defaults to server today (IST)."
        ),
    )


class MLTrainingJobResponse(BaseModel):
    """Serialized ML training job."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    started_by: int
    status: Literal["pending", "running", "completed", "failed"]
    model_type: str
    algorithm: str
    training_data_path: str
    started_at: datetime
    completed_at: datetime | None
    model_path: str | None
    accuracy: float | None
    error_message: str | None
    logs: str | None


class MLTrainingJobsResponse(BaseModel):
    jobs: list[MLTrainingJobResponse]


class MLModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    model_type: str
    version: str
    model_path: str
    training_data_through_date: date | None = None
    accuracy: float | None
    training_job_id: int
    is_active: bool
    created_at: datetime
    created_by: int


class MLModelsResponse(BaseModel):
    models: list[MLModelResponse]


class ActivateModelResponse(BaseModel):
    message: str
    model: MLModelResponse
