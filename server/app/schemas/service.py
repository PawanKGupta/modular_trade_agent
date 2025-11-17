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
