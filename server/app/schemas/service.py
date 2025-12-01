"""API schemas for service management"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ServiceStatusResponse(BaseModel):
    """Service status response"""

    service_running: bool
    last_heartbeat: datetime | None = None
    last_task_execution: datetime | None = None
    error_count: int = 0
    last_error: str | None = None
    updated_at: datetime | None = None


class ServiceStartResponse(BaseModel):
    """Response for service start operation"""

    success: bool
    message: str
    service_running: bool


class ServiceStopResponse(BaseModel):
    """Response for service stop operation"""

    success: bool
    message: str
    service_running: bool


class TaskExecutionResponse(BaseModel):
    """Task execution history item"""

    id: int
    task_name: str
    executed_at: datetime
    status: Literal["success", "failed", "skipped"]
    duration_seconds: float
    details: dict[str, Any] | None = None


class TaskHistoryResponse(BaseModel):
    """Task execution history response"""

    tasks: list[TaskExecutionResponse]
    total: int


class ServiceLogResponse(BaseModel):
    """Service log entry"""

    id: int
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    module: str
    message: str
    context: dict[str, Any] | None = None
    timestamp: datetime


class ServiceLogsResponse(BaseModel):
    """Service logs response"""

    logs: list[ServiceLogResponse]
    total: int
    limit: int = Field(default=100, description="Number of logs returned")


# Individual Service Management Schemas


class IndividualServiceStatus(BaseModel):
    """Individual service status"""

    task_name: str
    is_running: bool
    started_at: datetime | None = None
    last_execution_at: datetime | None = None
    next_execution_at: datetime | None = None
    process_id: int | None = None
    schedule_enabled: bool = True
    last_execution_status: Literal["success", "failed", "skipped", "running"] | None = None
    last_execution_duration: float | None = None
    last_execution_details: dict[str, Any] | None = None


class IndividualServicesStatusResponse(BaseModel):
    """Response for individual services status"""

    services: dict[str, IndividualServiceStatus]


class StartIndividualServiceRequest(BaseModel):
    """Request to start individual service"""

    task_name: str = Field(
        ...,
        description=(
            "Task name: premarket_retry, sell_monitor, position_monitor, buy_orders, eod_cleanup"
        ),
    )


class StartIndividualServiceResponse(BaseModel):
    """Response for starting individual service"""

    success: bool
    message: str


class StopIndividualServiceRequest(BaseModel):
    """Request to stop individual service"""

    task_name: str = Field(..., description="Task name to stop")


class StopIndividualServiceResponse(BaseModel):
    """Response for stopping individual service"""

    success: bool
    message: str


class RunOnceRequest(BaseModel):
    """Request to run task once"""

    task_name: str = Field(..., description="Task name to run")
    execution_type: Literal["run_once", "manual"] = Field(
        default="run_once", description="Execution type"
    )


class RunOnceResponse(BaseModel):
    """Response for run once execution"""

    success: bool
    message: str
    execution_id: int | None = None
    has_conflict: bool = False
    conflict_message: str | None = None


# Service Schedule Management Schemas (Admin)


class ServiceScheduleResponse(BaseModel):
    """Service schedule response"""

    id: int
    task_name: str
    schedule_time: str  # HH:MM format
    enabled: bool
    is_hourly: bool
    is_continuous: bool
    end_time: str | None = None  # HH:MM format
    schedule_type: str = "daily"  # "daily" or "once"
    description: str | None = None
    updated_by: int | None = None
    updated_at: datetime
    next_execution_at: datetime | None = None


class ServiceSchedulesResponse(BaseModel):
    """List of service schedules"""

    schedules: list[ServiceScheduleResponse]


class UpdateServiceScheduleRequest(BaseModel):
    """Request to update service schedule"""

    schedule_time: str = Field(..., description="Time in HH:MM format (IST)")
    enabled: bool = Field(default=True)
    is_hourly: bool = Field(default=False)
    is_continuous: bool = Field(default=False)
    end_time: str | None = Field(
        None, description="End time in HH:MM format (for continuous tasks)"
    )
    schedule_type: str = Field(
        default="daily", description="'daily' runs every day, 'once' runs once and stops"
    )
    description: str | None = None


class UpdateServiceScheduleResponse(BaseModel):
    """Response for updating service schedule"""

    success: bool
    message: str
    schedule: ServiceScheduleResponse
    requires_restart: bool = Field(
        default=True, description="Whether unified service needs to restart to apply changes"
    )
