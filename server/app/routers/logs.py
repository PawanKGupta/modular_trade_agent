# ruff: noqa: B008, PLR0913, PLR2004, E501

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from server.app.core.deps import get_current_user, get_db, require_admin
from server.app.schemas.logs import (
    ErrorLogEntry,
    ErrorLogsResponse,
    ErrorResolutionRequest,
    ErrorResolutionResponse,
    ServiceLogsResponse,
)
from src.infrastructure.persistence.error_log_repository import ErrorLogRepository
from src.infrastructure.persistence.service_log_repository import ServiceLogRepository

router = APIRouter()

DATE_ONLY_LENGTH = 10


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Support both date-only (YYYY-MM-DD) and full ISO strings.
        if len(value) == DATE_ONLY_LENGTH:
            return datetime.fromisoformat(f"{value}T00:00:00")
        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        return datetime.fromisoformat(normalized)
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid datetime format. Use ISO 8601 strings.",
        ) from exc


@router.get("/user/logs", response_model=ServiceLogsResponse)
def get_user_logs(
    level: str | None = Query(
        None,
        description="Filter by log level (e.g., INFO, ERROR).",
    ),
    module: str | None = Query(None, description="Filter by module/component name."),
    start_time: str | None = Query(None, description="ISO start timestamp filter."),
    end_time: str | None = Query(None, description="ISO end timestamp filter."),
    search: str | None = Query(
        None, description="Search message/module substring.", max_length=120
    ),
    limit: int = Query(200, ge=1, le=1000),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return service logs for the authenticated user."""
    repo = ServiceLogRepository(db)
    logs = repo.list(
        user_id=current_user.id,
        level=level,
        module=module,
        start_time=_parse_datetime(start_time),
        end_time=_parse_datetime(end_time),
        search=search,
        limit=limit,
    )
    return ServiceLogsResponse(logs=logs)


@router.get("/user/logs/errors", response_model=ErrorLogsResponse)
def get_user_error_logs(
    resolved: bool | None = Query(None, description="Filter by resolved state."),
    error_type: str | None = Query(None, description="Filter by error type/class name."),
    start_time: str | None = Query(None, description="ISO start timestamp filter."),
    end_time: str | None = Query(None, description="ISO end timestamp filter."),
    search: str | None = Query(None, description="Search error message substring.", max_length=120),
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return error logs for the authenticated user."""
    repo = ErrorLogRepository(db)
    errors = repo.list(
        user_id=current_user.id,
        resolved=resolved,
        error_type=error_type,
        start_time=_parse_datetime(start_time),
        end_time=_parse_datetime(end_time),
        search=search,
        limit=limit,
    )
    return ErrorLogsResponse(errors=errors)


@router.get("/admin/logs", response_model=ServiceLogsResponse)
def get_admin_logs(
    user_id: int | None = Query(None, description="Filter by user ID."),
    level: str | None = Query(None, description="Filter by log level."),
    module: str | None = Query(None, description="Filter by module/component."),
    start_time: str | None = Query(None, description="ISO start timestamp filter."),
    end_time: str | None = Query(None, description="ISO end timestamp filter."),
    search: str | None = Query(
        None, description="Search message/module substring.", max_length=120
    ),
    limit: int = Query(500, ge=1, le=2000),
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin endpoint to list logs across users."""
    _ = admin
    repo = ServiceLogRepository(db)
    logs = repo.list_all(
        user_id=user_id,
        level=level,
        module=module,
        start_time=_parse_datetime(start_time),
        end_time=_parse_datetime(end_time),
        search=search,
        limit=limit,
    )
    return ServiceLogsResponse(logs=logs)


@router.get("/admin/logs/errors", response_model=ErrorLogsResponse)
def get_admin_error_logs(
    user_id: int | None = Query(None, description="Filter by user ID."),
    resolved: bool | None = Query(None, description="Filter by resolved state."),
    error_type: str | None = Query(None, description="Filter by error type."),
    start_time: str | None = Query(None, description="ISO start timestamp filter."),
    end_time: str | None = Query(None, description="ISO end timestamp filter."),
    search: str | None = Query(None, description="Search error message substring.", max_length=120),
    limit: int = Query(200, ge=1, le=1000),
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin endpoint to list error logs across users."""
    _ = admin
    repo = ErrorLogRepository(db)
    errors = repo.list_all(
        user_id=user_id,
        resolved=resolved,
        error_type=error_type,
        start_time=_parse_datetime(start_time),
        end_time=_parse_datetime(end_time),
        search=search,
        limit=limit,
    )
    return ErrorLogsResponse(errors=errors)


@router.post(
    "/admin/logs/errors/{error_id}/resolve",
    response_model=ErrorResolutionResponse,
    status_code=status.HTTP_200_OK,
)
def resolve_error_log(
    error_id: int,
    payload: ErrorResolutionRequest,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Mark an error log as resolved and optionally attach notes."""
    repo = ErrorLogRepository(db)
    try:
        error = repo.resolve(
            error_id=error_id, resolved_by=admin.id, resolution_notes=payload.notes
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Error log not found"
        ) from None
    return ErrorResolutionResponse(
        message="Error marked as resolved",
        error=ErrorLogEntry.model_validate(error),
    )
