"""API endpoints for service management"""

# ruff: noqa: B008
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.application.services.individual_service_manager import IndividualServiceManager
from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.infrastructure.db.models import Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.service_log_repository import ServiceLogRepository
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository
from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository

from ..core.deps import get_current_user, get_db
from ..schemas.service import (
    IndividualServiceStatus,
    IndividualServicesStatusResponse,
    RunOnceRequest,
    RunOnceResponse,
    ServiceLogResponse,
    ServiceLogsResponse,
    ServiceStartResponse,
    ServiceStatusResponse,
    ServiceStopResponse,
    StartIndividualServiceRequest,
    StartIndividualServiceResponse,
    StopIndividualServiceRequest,
    StopIndividualServiceResponse,
    TaskExecutionResponse,
    TaskHistoryResponse,
)

router = APIRouter()


def get_trading_service(db: Session = Depends(get_db)) -> MultiUserTradingService:
    """Dependency to get MultiUserTradingService instance"""
    return MultiUserTradingService(db)


def get_individual_service_manager(
    db: Session = Depends(get_db),
) -> IndividualServiceManager:
    """Dependency to get IndividualServiceManager instance"""
    return IndividualServiceManager(db)


@router.post("/service/start", response_model=ServiceStartResponse)
def start_service(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    trading_service: MultiUserTradingService = Depends(get_trading_service),
):
    """Start trading service for current user"""
    try:
        success = trading_service.start_service(current.id)
        if success:
            return ServiceStartResponse(
                success=True,
                message="Trading service started successfully",
                service_running=True,
            )
        else:
            return ServiceStartResponse(
                success=False,
                message="Failed to start trading service",
                service_running=False,
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting service: {str(e)}",
        ) from e


@router.post("/service/stop", response_model=ServiceStopResponse)
def stop_service(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    trading_service: MultiUserTradingService = Depends(get_trading_service),
):
    """Stop trading service for current user"""
    try:
        success = trading_service.stop_service(current.id)
        if success:
            return ServiceStopResponse(
                success=True,
                message="Trading service stopped successfully",
                service_running=False,
            )
        else:
            return ServiceStopResponse(
                success=False,
                message="Failed to stop trading service",
                service_running=True,
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping service: {str(e)}",
        ) from e


@router.get("/service/status", response_model=ServiceStatusResponse)
def get_service_status(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    trading_service: MultiUserTradingService = Depends(get_trading_service),
):
    """Get unified service status and health for current user"""
    try:
        status_obj = trading_service.get_service_status(current.id)
        if not status_obj:
            # Return default status if not found
            status_repo = ServiceStatusRepository(db)
            status_obj = status_repo.get_or_create(current.id)

        return ServiceStatusResponse(
            service_running=status_obj.service_running,
            last_heartbeat=status_obj.last_heartbeat,
            last_task_execution=status_obj.last_task_execution,
            error_count=status_obj.error_count,
            last_error=status_obj.last_error,
            updated_at=status_obj.updated_at,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting service status: {str(e)}",
        ) from e


@router.get("/service/individual/status", response_model=IndividualServicesStatusResponse)
def get_individual_services_status(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    service_manager: IndividualServiceManager = Depends(get_individual_service_manager),
):
    """Get status of all individual services for current user"""
    try:
        status_dict = service_manager.get_status(current.id)
        services = {
            task_name: IndividualServiceStatus(
                task_name=task_name,
                is_running=info["is_running"],
                started_at=info["started_at"],
                last_execution_at=info["last_execution_at"],
                next_execution_at=info["next_execution_at"],
                process_id=info["process_id"],
                schedule_enabled=info["schedule_enabled"],
            )
            for task_name, info in status_dict.items()
        }
        return IndividualServicesStatusResponse(services=services)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting individual services status: {str(e)}",
        ) from e


@router.post("/service/individual/start", response_model=StartIndividualServiceResponse)
def start_individual_service(
    request: StartIndividualServiceRequest,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    service_manager: IndividualServiceManager = Depends(get_individual_service_manager),
):
    """Start an individual service for current user"""
    try:
        success, message = service_manager.start_service(current.id, request.task_name)
        return StartIndividualServiceResponse(success=success, message=message)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting individual service: {str(e)}",
        ) from e


@router.post("/service/individual/stop", response_model=StopIndividualServiceResponse)
def stop_individual_service(
    request: StopIndividualServiceRequest,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    service_manager: IndividualServiceManager = Depends(get_individual_service_manager),
):
    """Stop an individual service for current user"""
    try:
        success, message = service_manager.stop_service(current.id, request.task_name)
        return StopIndividualServiceResponse(success=success, message=message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping individual service: {str(e)}",
        ) from e


@router.post("/service/individual/run-once", response_model=RunOnceResponse)
def run_task_once(
    request: RunOnceRequest,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    service_manager: IndividualServiceManager = Depends(get_individual_service_manager),
):
    """Run a task once immediately (run once execution)"""
    try:
        from src.application.services.conflict_detection_service import ConflictDetectionService

        conflict_service = ConflictDetectionService(db)
        has_conflict, conflict_message = conflict_service.check_conflict(
            current.id, request.task_name
        )

        success, message, details = service_manager.run_once(
            current.id, request.task_name, request.execution_type
        )

        return RunOnceResponse(
            success=success,
            message=message,
            execution_id=details.get("execution_id"),
            has_conflict=has_conflict,
            conflict_message=conflict_message if has_conflict else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error running task: {str(e)}",
        ) from e


@router.get("/service/tasks", response_model=TaskHistoryResponse)
def get_task_history(
    task_name: str | None = Query(None, description="Filter by task name"),
    status: Literal["success", "failed", "skipped"] | None = Query(
        None, description="Filter by status"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tasks to return"),
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """Get task execution history for current user"""
    try:
        task_repo = ServiceTaskRepository(db)
        tasks = task_repo.list(
            user_id=current.id,
            task_name=task_name,
            status=status,
            limit=limit,
        )

        return TaskHistoryResponse(
            tasks=[
                TaskExecutionResponse(
                    id=task.id,
                    task_name=task.task_name,
                    executed_at=task.executed_at,
                    status=task.status,
                    duration_seconds=task.duration_seconds,
                    details=task.details,
                )
                for task in tasks
            ],
            total=len(tasks),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting task history: {str(e)}",
        ) from e


@router.get("/service/logs", response_model=ServiceLogsResponse)
def get_service_logs(  # noqa: PLR0913
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = Query(
        None, description="Filter by log level"
    ),
    module: str | None = Query(None, description="Filter by module name"),
    hours: int = Query(
        24, ge=1, le=168, description="Number of hours to look back (max 168 = 7 days)"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return"),
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """Get recent service logs for current user"""
    try:
        log_repo = ServiceLogRepository(db)
        start_time = ist_now() - timedelta(hours=hours)

        logs = log_repo.list(
            user_id=current.id,
            level=level,
            module=module,
            start_time=start_time,
            limit=limit,
        )

        return ServiceLogsResponse(
            logs=[
                ServiceLogResponse(
                    id=log.id,
                    level=log.level,
                    module=log.module,
                    message=log.message,
                    context=log.context,
                    timestamp=log.timestamp,
                )
                for log in logs
            ],
            total=len(logs),
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting service logs: {str(e)}",
        ) from e
