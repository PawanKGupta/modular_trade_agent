"""API schemas for service and authentication monitoring"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# Service Execution Monitoring Schemas


class ServiceHealthStatus(BaseModel):
    """Service health status for a user"""

    user_id: int
    user_email: str | None = None
    service_running: bool
    last_heartbeat: datetime | None = None
    heartbeat_age_seconds: float | None = None
    last_task_execution: datetime | None = None
    last_task_name: str | None = None
    error_count: int = 0
    last_error: str | None = None
    updated_at: datetime | None = None


class ServicesHealthResponse(BaseModel):
    """Response for services health overview"""

    services: list[ServiceHealthStatus]
    total_running: int
    total_stopped: int
    services_with_recent_errors: int


class TaskExecutionWithSchedule(BaseModel):
    """Task execution with schedule information"""

    id: int
    user_id: int
    user_email: str | None = None
    task_name: str
    scheduled_time: str | None = None  # HH:MM from schedule
    executed_at: datetime
    time_difference_seconds: float | None = None  # actual - scheduled
    status: Literal["success", "failed", "skipped", "running"]
    duration_seconds: float
    execution_type: Literal["scheduled", "run_once", "manual"] = "scheduled"
    details: dict[str, Any] | None = None


class TaskExecutionsResponse(BaseModel):
    """Paginated task executions response"""

    items: list[TaskExecutionWithSchedule]
    total: int
    page: int
    page_size: int
    total_pages: int


class TaskMetrics(BaseModel):
    """Task performance metrics"""

    task_name: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    skipped_executions: int
    success_rate: float
    avg_duration_seconds: float
    p95_duration_seconds: float | None = None
    p99_duration_seconds: float | None = None
    on_time_percentage: float | None = None  # % within ±5min of scheduled
    last_execution_at: datetime | None = None
    last_execution_status: str | None = None


class TaskMetricsResponse(BaseModel):
    """Task metrics response"""

    metrics: list[TaskMetrics]
    period_days: int = Field(default=1, description="Period for metrics calculation")


class ScheduleCompliance(BaseModel):
    """Schedule compliance information for a task"""

    task_name: str
    scheduled_time: str  # HH:MM
    enabled: bool
    is_continuous: bool
    end_time: str | None = None
    last_execution_at: datetime | None = None
    next_expected_execution: datetime | None = None
    execution_count_today: int
    expected_count_today: int | None = None  # None for continuous
    compliance_status: Literal["on_track", "delayed", "missed", "not_applicable"]
    last_execution_status: str | None = None


class ScheduleComplianceResponse(BaseModel):
    """Schedule compliance response"""

    tasks: list[ScheduleCompliance]
    total_missed: int
    total_delayed: int


class RunningTask(BaseModel):
    """Currently running task"""

    id: int
    user_id: int
    user_email: str | None = None
    task_name: str
    started_at: datetime
    duration_seconds: float
    estimated_completion: datetime | None = None


class RunningTasksResponse(BaseModel):
    """Currently running tasks response"""

    tasks: list[RunningTask]
    total: int


# Authentication Monitoring Schemas


class ActiveSession(BaseModel):
    """Active authentication session"""

    user_id: int
    user_email: str | None = None
    session_created_at: datetime | None = None
    session_age_minutes: float | None = None
    session_status: Literal["valid", "expiring_soon", "expired"]
    ttl_remaining_minutes: float | None = None
    is_authenticated: bool
    client_available: bool


class ActiveSessionsResponse(BaseModel):
    """Active sessions response"""

    sessions: list[ActiveSession]
    total_active: int
    expiring_soon: int
    expired: int


class ReauthEvent(BaseModel):
    """Re-authentication event"""

    id: int | None = None  # May not have ID if from logs
    user_id: int
    user_email: str | None = None
    timestamp: datetime
    triggered_by: str | None = None  # Method/API call that triggered re-auth
    status: Literal["success", "failed", "rate_limited"]
    duration_seconds: float | None = None
    reason: str | None = None  # JWT expired, invalid token, etc.
    error_message: str | None = None


class ReauthHistoryResponse(BaseModel):
    """Re-authentication history response"""

    events: list[ReauthEvent]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReauthStatistics(BaseModel):
    """Re-authentication statistics"""

    user_id: int
    user_email: str | None = None
    reauth_count_24h: int
    reauth_count_7d: int
    reauth_count_30d: int
    reauth_rate_per_hour: float
    success_rate: float
    avg_time_between_reauth_minutes: float | None = None
    rate_limited: bool
    cooldown_remaining_seconds: float | None = None
    blocked: bool = False  # 3+ failures in 60s window


class ReauthStatisticsResponse(BaseModel):
    """Re-authentication statistics response"""

    statistics: list[ReauthStatistics]
    period_days: int = Field(default=1, description="Period for statistics calculation")


class AuthError(BaseModel):
    """Authentication error log entry"""

    id: int | None = None
    user_id: int
    user_email: str | None = None
    timestamp: datetime
    error_type: str  # JWT expired, invalid credentials, unauthorized, etc.
    error_code: str | None = None  # 900901, etc.
    error_message: str
    api_endpoint: str | None = None
    method_name: str | None = None
    reauth_attempted: bool
    reauth_success: bool | None = None


class AuthErrorsResponse(BaseModel):
    """Authentication errors response"""

    errors: list[AuthError]
    total: int
    page: int
    page_size: int
    total_pages: int


# Combined Dashboard Schemas


class DashboardSummary(BaseModel):
    """Dashboard summary statistics"""

    # Service execution stats
    total_services: int
    services_running: int
    services_stopped: int
    tasks_executed_today: int
    tasks_successful_today: int
    tasks_failed_today: int
    services_with_errors: int

    # Authentication stats
    active_sessions: int
    sessions_expiring_soon: int
    reauth_count_24h: int
    reauth_success_rate: float
    auth_errors_24h: int

    # Combined stats
    tasks_failed_due_to_auth: int


class DashboardAlerts(BaseModel):
    """Dashboard alerts"""

    alerts: list[dict[str, Any]]  # List of alert objects
    critical_count: int
    warning_count: int
    info_count: int


class MonitoringDashboardResponse(BaseModel):
    """Complete monitoring dashboard response"""

    summary: DashboardSummary
    alerts: DashboardAlerts
    recent_task_executions: list[TaskExecutionWithSchedule]  # Last 20
    recent_reauth_events: list[ReauthEvent]  # Last 20
    running_tasks: list[RunningTask]
    updated_at: datetime
