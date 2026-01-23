"""API endpoints for service management"""

# ruff: noqa: B008
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.application.services.conflict_detection_service import ConflictDetectionService
from src.application.services.individual_service_manager import IndividualServiceManager
from src.application.services.multi_user_trading_service import MultiUserTradingService
from src.infrastructure.db.models import Users
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.logging.file_log_reader import FileLogReader
from src.infrastructure.persistence.service_status_repository import ServiceStatusRepository
from src.infrastructure.persistence.service_task_repository import ServiceTaskRepository
from src.infrastructure.utils.holiday_calendar import (
    get_holiday_name,
    is_nse_holiday,
    is_trading_day,
)

from ..core.deps import get_current_user, get_db
from ..schemas.service import (
    IndividualServicesStatusResponse,
    IndividualServiceStatus,
    PositionCreationMetricsResponse,
    PositionsWithoutSellOrdersResponse,
    PositionWithoutSellOrder,
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
    TradingDayInfoResponse,
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
        db.commit()  # Explicitly commit status changes
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
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        db.rollback()
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
        db.commit()  # Explicitly commit status changes
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
        db.rollback()
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

        # CRITICAL: Ensure timestamps are timezone-aware (UTC) for proper frontend display
        # PostgreSQL stores timestamps in UTC, but they may be returned as naive datetimes
        # Making them timezone-aware ensures FastAPI serializes them correctly with 'Z' suffix
        # If naive, assume they're UTC (PostgreSQL default) and mark them as such
        # If timezone-aware but not UTC, convert to UTC
        if status_obj.last_heartbeat:
            if status_obj.last_heartbeat.tzinfo is None:
                status_obj.last_heartbeat = status_obj.last_heartbeat.replace(tzinfo=UTC)
            elif status_obj.last_heartbeat.tzinfo != UTC:
                # Convert to UTC if in different timezone
                status_obj.last_heartbeat = status_obj.last_heartbeat.astimezone(UTC)
        if status_obj.last_task_execution:
            if status_obj.last_task_execution.tzinfo is None:
                status_obj.last_task_execution = status_obj.last_task_execution.replace(tzinfo=UTC)
            elif status_obj.last_task_execution.tzinfo != UTC:
                # Convert to UTC if in different timezone
                status_obj.last_task_execution = status_obj.last_task_execution.astimezone(UTC)
        if status_obj.updated_at:
            if status_obj.updated_at.tzinfo is None:
                status_obj.updated_at = status_obj.updated_at.replace(tzinfo=UTC)
            elif status_obj.updated_at.tzinfo != UTC:
                # Convert to UTC if in different timezone
                status_obj.updated_at = status_obj.updated_at.astimezone(UTC)

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

        # Helper function to ensure datetime is timezone-aware (UTC)
        def ensure_utc_datetime(dt_value):
            """Convert ISO string or datetime to UTC timezone-aware datetime"""
            if dt_value is None:
                return None
            if isinstance(dt_value, str):
                # Parse ISO string - handle both with and without 'Z' suffix
                try:
                    # Replace 'Z' with '+00:00' for fromisoformat compatibility
                    iso_str = dt_value.replace("Z", "+00:00")
                    # Try parsing with timezone info first
                    try:
                        dt = datetime.fromisoformat(iso_str)
                    except ValueError:
                        # If that fails, try parsing as naive and assume UTC
                        dt = datetime.fromisoformat(dt_value)
                        dt = dt.replace(tzinfo=UTC)
                except (ValueError, AttributeError):
                    # Fallback: try parsing as naive datetime and assume UTC
                    try:
                        dt = datetime.fromisoformat(dt_value)
                        dt = dt.replace(tzinfo=UTC)
                    except ValueError:
                        # If all parsing fails, return None
                        return None
            else:
                dt = dt_value

            # Ensure timezone-aware and in UTC
            if dt.tzinfo is None:
                # Assume naive datetime is UTC (PostgreSQL default)
                dt = dt.replace(tzinfo=UTC)
            elif dt.tzinfo != UTC:
                # Convert to UTC if in different timezone
                dt = dt.astimezone(UTC)
            return dt

        services = {
            task_name: IndividualServiceStatus(
                task_name=task_name,
                is_running=info["is_running"],
                started_at=ensure_utc_datetime(info["started_at"]),
                last_execution_at=ensure_utc_datetime(info["last_execution_at"]),
                next_execution_at=ensure_utc_datetime(info["next_execution_at"]),
                process_id=info["process_id"],
                schedule_enabled=info["schedule_enabled"],
                last_execution_status=info.get("last_execution_status"),
                last_execution_duration=info.get("last_execution_duration"),
                last_execution_details=info.get("last_execution_details"),
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
    limit: int = Query(100, ge=1, le=500, description="Maximum number of logs to return"),
    tail: bool = Query(False, description="Return last 200 lines from latest file."),
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
):
    """Get recent service logs for current user"""
    try:
        _ = db  # Not used for file logs
        reader = FileLogReader()

        if tail:
            log_dicts = reader.tail_logs(user_id=current.id, log_type="service", tail_lines=200)
        else:
            start_time = ist_now() - timedelta(hours=hours)
            days_back = min(14, (hours + 23) // 24)  # ceil hours to days, cap at 14

            log_dicts = reader.read_logs(
                user_id=current.id,
                level=level,
                module=module,
                start_time=start_time,
                limit=min(limit, 500),
                days_back=days_back,
            )

        logs = [
            ServiceLogResponse(
                id=str(log_dict.get("id", "")),  # Coerce to string for file:line format
                level=log_dict["level"],
                module=log_dict["module"],
                message=log_dict["message"],
                context=log_dict.get("context"),
                timestamp=log_dict["timestamp"],
            )
            for log_dict in log_dicts
        ]

        return ServiceLogsResponse(
            logs=logs,
            total=len(logs),
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting service logs: {str(e)}",
        ) from e


@router.get("/service/metrics/position-creation", response_model=PositionCreationMetricsResponse)
def get_position_creation_metrics(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    trading_service: MultiUserTradingService = Depends(get_trading_service),
):
    """
    Get position creation metrics for current user's trading service.

    Issue #1 Fix: Returns metrics tracking position creation success/failure rates.
    """
    try:
        metrics = trading_service.get_position_creation_metrics(current.id)

        if metrics is None:
            # Service not running or unified_order_monitor not available
            return PositionCreationMetricsResponse(
                success=0,
                failed_missing_repos=0,
                failed_missing_symbol=0,
                failed_exception=0,
                success_rate=0.0,
                total_attempts=0,
            )

        # Calculate totals and success rate
        total_attempts = (
            metrics.get("success", 0)
            + metrics.get("failed_missing_repos", 0)
            + metrics.get("failed_missing_symbol", 0)
            + metrics.get("failed_exception", 0)
        )

        success_count = metrics.get("success", 0)
        success_rate = (success_count / total_attempts * 100.0) if total_attempts > 0 else 0.0

        return PositionCreationMetricsResponse(
            success=success_count,
            failed_missing_repos=metrics.get("failed_missing_repos", 0),
            failed_missing_symbol=metrics.get("failed_missing_symbol", 0),
            failed_exception=metrics.get("failed_exception", 0),
            success_rate=round(success_rate, 2),
            total_attempts=total_attempts,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting position creation metrics: {str(e)}",
        ) from e


@router.get(
    "/service/positions/without-sell-orders",
    response_model=PositionsWithoutSellOrdersResponse,
)
def get_positions_without_sell_orders(
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    trading_service: MultiUserTradingService = Depends(get_trading_service),
):
    """
    Issue #5: Get positions without sell orders for current user.

    Returns detailed list of positions that don't have sell orders,
    including reasons why orders weren't placed.

    Useful for dashboard visibility and troubleshooting.
    """
    try:
        positions = trading_service.get_positions_without_sell_orders(current.id)

        # Convert to response format
        position_list = [
            PositionWithoutSellOrder(
                symbol=pos["symbol"],
                entry_price=pos["entry_price"],
                quantity=pos["quantity"],
                reason=pos["reason"],
                ticker=pos["ticker"],
                broker_symbol=pos["broker_symbol"],
            )
            for pos in positions
        ]

        return PositionsWithoutSellOrdersResponse(
            positions=position_list,
            count=len(position_list),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting positions without sell orders: {str(e)}",
        ) from e


WEEKEND_START_DAY = 5  # Saturday=5, Sunday=6


@router.get("/service/trading-day-info", response_model=TradingDayInfoResponse)
def get_trading_day_info(
    current: Users = Depends(get_current_user),  # noqa: B008, ARG001
):
    """
    Get trading day information for today.

    Returns whether today is a trading day, if it's a holiday, holiday name, and if it's a weekend.
    """
    try:
        today = ist_now().date()
        is_holiday = is_nse_holiday(today)
        holiday_name = get_holiday_name(today) if is_holiday else None
        is_weekend = today.weekday() >= WEEKEND_START_DAY
        is_trading = is_trading_day(today)

        return TradingDayInfoResponse(
            is_trading_day=is_trading,
            is_holiday=is_holiday,
            holiday_name=holiday_name,
            is_weekend=is_weekend,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting trading day info: {str(e)}",
        ) from e
