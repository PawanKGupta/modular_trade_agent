"""API endpoints for service and authentication monitoring (Admin only)"""

# ruff: noqa: B008, PLR0912, PLR0915
import logging
import traceback
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, or_, text
from sqlalchemy.orm import Session

from modules.kotak_neo_auto_trader.shared_session_manager import (
    get_shared_session_manager,
)
from src.infrastructure.db.models import (
    ErrorLog,
    IndividualServiceTaskExecution,
    ServiceStatus,
    Users,
)
from src.infrastructure.db.timezone_utils import IST, ist_now, utc_to_ist
from src.infrastructure.persistence.service_schedule_repository import (
    ServiceScheduleRepository,
)

from ..core.deps import get_db, require_admin
from ..schemas.monitoring import (
    ActiveSession,
    ActiveSessionsResponse,
    AuthError,
    AuthErrorsResponse,
    DashboardAlerts,
    DashboardSummary,
    MonitoringDashboardResponse,
    ReauthEvent,
    ReauthHistoryResponse,
    ReauthStatistics,
    ReauthStatisticsResponse,
    RunningTask,
    RunningTasksResponse,
    ScheduleCompliance,
    ScheduleComplianceResponse,
    ServiceHealthStatus,
    ServicesHealthResponse,
    TaskExecutionsResponse,
    TaskExecutionWithSchedule,
    TaskMetrics,
    TaskMetricsResponse,
)

router = APIRouter(dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)


def _get_user_email_map(db: Session, user_ids: list[int]) -> dict[int, str]:
    """Get email map for user IDs"""
    users = db.query(Users).filter(Users.id.in_(user_ids)).all()
    return {u.id: u.email for u in users}


# Service Execution Monitoring Endpoints


def _get_services_health_impl(db: Session) -> ServicesHealthResponse:
    """Internal implementation to get health status for all services"""
    try:
        # CRITICAL: Use raw SQL query to bypass SQLAlchemy's identity map/cache entirely
        # This ensures we always read the absolute latest data from the database
        # The service updates heartbeat in another thread/connection, so we need fresh data

        # Query service_status table directly using raw SQL to bypass ORM cache
        result = db.execute(
            text(
                """
                SELECT
                    id, user_id, service_running, last_heartbeat,
                    last_task_execution, error_count, last_error,
                    created_at, updated_at
                FROM service_status
            """
            )
        )
        raw_rows = result.fetchall()

        # Convert raw rows to ServiceStatus objects (but they won't be in identity map)
        all_statuses = []
        for row in raw_rows:
            status = ServiceStatus()
            status.id = row.id
            status.user_id = row.user_id
            status.service_running = row.service_running
            status.last_heartbeat = row.last_heartbeat
            status.last_task_execution = row.last_task_execution
            status.error_count = row.error_count
            status.last_error = row.last_error
            status.created_at = row.created_at
            status.updated_at = row.updated_at
            all_statuses.append(status)

        services = []
        total_running = 0
        total_stopped = 0
        services_with_recent_errors = 0

        now = ist_now()
        user_ids = [s.user_id for s in all_statuses]
        user_email_map = _get_user_email_map(db, user_ids)

        for status in all_statuses:
            heartbeat_age = None
            if status.last_heartbeat:
                # CRITICAL: PostgreSQL stores timestamps in UTC, but we need IST for comparison
                # Convert last_heartbeat from UTC (database storage) to IST for age calc
                last_heartbeat = status.last_heartbeat

                # If naive, assume it's UTC (PostgreSQL default)
                if last_heartbeat.tzinfo is None:
                    last_heartbeat = last_heartbeat.replace(tzinfo=UTC)

                # Convert UTC to IST for comparison with ist_now()
                if last_heartbeat.tzinfo != IST:
                    last_heartbeat = utc_to_ist(last_heartbeat)

                age_delta = now - last_heartbeat
                heartbeat_age = age_delta.total_seconds()

            # CRITICAL: Ensure timestamps are timezone-aware (UTC) for proper frontend display
            # PostgreSQL stores timestamps in UTC, but they may be returned as naive datetimes
            # Making them timezone-aware ensures FastAPI serializes them correctly with 'Z' suffix
            # If naive, assume they're UTC (PostgreSQL default) and mark them as such
            # If timezone-aware but not UTC, convert to UTC
            if status.last_heartbeat:
                if status.last_heartbeat.tzinfo is None:
                    status.last_heartbeat = status.last_heartbeat.replace(tzinfo=UTC)
                elif status.last_heartbeat.tzinfo != UTC:
                    # Convert to UTC if in different timezone
                    status.last_heartbeat = status.last_heartbeat.astimezone(UTC)
            if status.last_task_execution:
                if status.last_task_execution.tzinfo is None:
                    status.last_task_execution = status.last_task_execution.replace(tzinfo=UTC)
                elif status.last_task_execution.tzinfo != UTC:
                    # Convert to UTC if in different timezone
                    status.last_task_execution = status.last_task_execution.astimezone(UTC)
            if status.updated_at:
                if status.updated_at.tzinfo is None:
                    status.updated_at = status.updated_at.replace(tzinfo=UTC)
                elif status.updated_at.tzinfo != UTC:
                    # Convert to UTC if in different timezone
                    status.updated_at = status.updated_at.astimezone(UTC)

            # Report stale services: if heartbeat is very old (>10 minutes) and
            # service shows as running, report it (monitoring should only observe, not fix)
            # The service itself should update its status properly when thread exits
            if status.service_running and heartbeat_age and heartbeat_age > 600:
                # Report as stale (but don't fix - monitoring should only observe)
                logger.warning(
                    f"Service for user {status.user_id} appears stale: "
                    f"heartbeat age {heartbeat_age:.0f}s > 10 minutes. "
                    "Service should update its status when thread exits."
                )

            services.append(
                ServiceHealthStatus(
                    user_id=status.user_id,
                    user_email=user_email_map.get(status.user_id),
                    service_running=status.service_running,
                    last_heartbeat=status.last_heartbeat,
                    heartbeat_age_seconds=heartbeat_age,
                    last_task_execution=status.last_task_execution,
                    last_task_name=None,  # Would need to query from task execution
                    error_count=status.error_count,
                    last_error=status.last_error,
                    updated_at=status.updated_at,
                )
            )

            if status.service_running:
                total_running += 1
            else:
                total_stopped += 1

            if status.error_count > 0:
                services_with_recent_errors += 1

        return ServicesHealthResponse(
            services=services,
            total_running=total_running,
            total_stopped=total_stopped,
            services_with_recent_errors=services_with_recent_errors,
        )
    except Exception:
        # Don't raise HTTPException here - let caller handle it
        raise


@router.get("/services/health", response_model=ServicesHealthResponse)
def get_services_health(
    db: Session = Depends(get_db),
):
    """Get health status for all services"""
    return _get_services_health_impl(db)


@router.get("/tasks/executions", response_model=TaskExecutionsResponse)
def get_task_executions(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    user_id: int | None = Query(None, description="Filter by user ID"),
    task_name: str | None = Query(None, description="Filter by task name"),
    status: str | None = Query(None, description="Filter by status"),
    start_date: date | None = Query(None, description="Filter by start date"),
    end_date: date | None = Query(None, description="Filter by end date"),
    db: Session = Depends(get_db),
):
    """Get paginated task execution history with schedule information"""
    try:
        schedule_repo = ServiceScheduleRepository(db)

        # Get schedules for task_name mapping
        all_schedules = schedule_repo.get_all()
        schedule_map = {s.task_name: s for s in all_schedules}

        # Build query
        query = db.query(IndividualServiceTaskExecution)

        if user_id:
            query = query.filter(IndividualServiceTaskExecution.user_id == user_id)
        if task_name:
            query = query.filter(IndividualServiceTaskExecution.task_name == task_name)
        if status:
            query = query.filter(IndividualServiceTaskExecution.status == status)
        if start_date:
            start_datetime = datetime.combine(start_date, dt_time.min, tzinfo=IST)
            query = query.filter(IndividualServiceTaskExecution.executed_at >= start_datetime)
        if end_date:
            end_datetime = datetime.combine(end_date, dt_time.max, tzinfo=IST)
            query = query.filter(IndividualServiceTaskExecution.executed_at <= end_datetime)

        # Get total count
        total_count = query.count()

        # Apply pagination and sorting
        offset = (page - 1) * page_size
        executions = (
            query.order_by(desc(IndividualServiceTaskExecution.executed_at))
            .offset(offset)
            .limit(page_size)
            .all()
        )

        # Get user emails
        user_ids = list({e.user_id for e in executions})
        user_email_map = _get_user_email_map(db, user_ids)

        items = []
        for exec in executions:
            schedule = schedule_map.get(exec.task_name)
            scheduled_time = None
            time_diff = None

            if schedule and exec.executed_at:
                # Calculate time difference from scheduled time
                exec_date = exec.executed_at.date()
                scheduled_datetime = datetime.combine(exec_date, schedule.schedule_time, tzinfo=IST)
                if exec.executed_at:
                    # Ensure executed_at is timezone-aware for comparison
                    exec_dt = exec.executed_at
                    if exec_dt.tzinfo is None:
                        exec_dt = exec_dt.replace(tzinfo=IST)
                    time_diff = (exec_dt - scheduled_datetime).total_seconds()
                    scheduled_time = schedule.schedule_time.strftime("%H:%M")

            # Ensure executed_at is timezone-aware (UTC) for proper frontend display
            executed_at_utc = exec.executed_at
            if executed_at_utc:
                if executed_at_utc.tzinfo is None:
                    executed_at_utc = executed_at_utc.replace(tzinfo=UTC)
                elif executed_at_utc.tzinfo != UTC:
                    executed_at_utc = executed_at_utc.astimezone(UTC)

            items.append(
                TaskExecutionWithSchedule(
                    id=exec.id,
                    user_id=exec.user_id,
                    user_email=user_email_map.get(exec.user_id),
                    task_name=exec.task_name,
                    scheduled_time=scheduled_time,
                    executed_at=executed_at_utc,
                    time_difference_seconds=time_diff,
                    status=exec.status,
                    duration_seconds=exec.duration_seconds,
                    execution_type=exec.execution_type,
                    details=exec.details,
                )
            )

        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

        return TaskExecutionsResponse(
            items=items,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching task executions: {str(e)}",
        ) from e


def _get_running_tasks_impl(db: Session, user_id: int | None = None) -> RunningTasksResponse:
    """Internal implementation to get currently running tasks"""
    try:
        # Query running tasks directly
        query = db.query(IndividualServiceTaskExecution).filter(
            IndividualServiceTaskExecution.status == "running"
        )

        if user_id:
            query = query.filter(IndividualServiceTaskExecution.user_id == user_id)

        running = query.all()

        user_ids = list({r.user_id for r in running})
        user_email_map = _get_user_email_map(db, user_ids)

        tasks = []
        now = ist_now()
        for r in running:
            exec_started_at = r.executed_at
            if exec_started_at:
                # Ensure executed_at is timezone-aware
                exec_dt = exec_started_at
                if exec_dt.tzinfo is None:
                    exec_dt = exec_dt.replace(tzinfo=IST)
                duration = (now - exec_dt).total_seconds()
                # Use timezone-aware datetime for started_at
                started_at = exec_dt
                # Estimate completion based on average duration (would need metrics)
                estimated_completion = None
            else:
                duration = 0.0
                started_at = now
                estimated_completion = None

            tasks.append(
                RunningTask(
                    id=r.id,
                    user_id=r.user_id,
                    user_email=user_email_map.get(r.user_id),
                    task_name=r.task_name,
                    started_at=started_at,
                    duration_seconds=duration,
                    estimated_completion=estimated_completion,
                )
            )

        return RunningTasksResponse(tasks=tasks, total=len(tasks))
    except Exception:
        # Don't raise HTTPException here - let caller handle it
        raise


@router.get("/tasks/running", response_model=RunningTasksResponse)
def get_running_tasks(
    user_id: int | None = Query(None, description="Filter by user ID"),
    db: Session = Depends(get_db),
):
    """Get currently running tasks"""
    try:
        return _get_running_tasks_impl(db, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching running tasks: {str(e)}",
        ) from e


@router.get("/tasks/metrics", response_model=TaskMetricsResponse)
def get_task_metrics(
    period_days: int = Query(7, ge=1, le=90, description="Period in days"),
    user_id: int | None = Query(None, description="Filter by user ID"),
    task_name: str | None = Query(None, description="Filter by task name"),
    db: Session = Depends(get_db),
):
    """Get task performance metrics"""
    try:
        start_date = ist_now().date() - timedelta(days=period_days)

        query = db.query(IndividualServiceTaskExecution).filter(
            IndividualServiceTaskExecution.executed_at >= datetime.combine(start_date, dt_time.min)
        )

        if user_id:
            query = query.filter(IndividualServiceTaskExecution.user_id == user_id)
        if task_name:
            query = query.filter(IndividualServiceTaskExecution.task_name == task_name)

        executions = query.all()

        # Group by task_name
        task_stats: dict[str, dict] = defaultdict(
            lambda: {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "durations": [],
                "last_execution": None,
                "last_status": None,
            }
        )

        for exec in executions:
            stats = task_stats[exec.task_name]
            stats["total"] += 1
            if exec.status == "success":
                stats["success"] += 1
            elif exec.status == "failed":
                stats["failed"] += 1
            elif exec.status == "skipped":
                stats["skipped"] += 1

            stats["durations"].append(exec.duration_seconds)
            if not stats["last_execution"] or (
                exec.executed_at and exec.executed_at > stats["last_execution"]
            ):
                # Ensure executed_at is timezone-aware (UTC) for proper frontend display
                exec_dt = exec.executed_at
                if exec_dt:
                    if exec_dt.tzinfo is None:
                        exec_dt = exec_dt.replace(tzinfo=UTC)
                    elif exec_dt.tzinfo != UTC:
                        exec_dt = exec_dt.astimezone(UTC)
                stats["last_execution"] = exec_dt
                stats["last_status"] = exec.status

        metrics = []
        for task, stats in task_stats.items():
            durations = stats["durations"]
            avg_duration = sum(durations) / len(durations) if durations else 0.0
            sorted_durations = sorted(durations)
            p95_duration = (
                sorted_durations[int(len(sorted_durations) * 0.95)] if sorted_durations else None
            )
            p99_duration = (
                sorted_durations[int(len(sorted_durations) * 0.99)] if sorted_durations else None
            )

            success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0.0

            metrics.append(
                TaskMetrics(
                    task_name=task,
                    total_executions=stats["total"],
                    successful_executions=stats["success"],
                    failed_executions=stats["failed"],
                    skipped_executions=stats["skipped"],
                    success_rate=success_rate,
                    avg_duration_seconds=avg_duration,
                    p95_duration_seconds=p95_duration,
                    p99_duration_seconds=p99_duration,
                    on_time_percentage=None,  # Would need schedule comparison
                    last_execution_at=stats["last_execution"],
                    last_execution_status=stats["last_status"],
                )
            )

        return TaskMetricsResponse(metrics=metrics, period_days=period_days)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching task metrics: {str(e)}",
        ) from e


@router.get("/tasks/compliance", response_model=ScheduleComplianceResponse)
def get_schedule_compliance(
    db: Session = Depends(get_db),
):
    """Get schedule compliance for all tasks"""
    try:
        schedule_repo = ServiceScheduleRepository(db)

        schedules = schedule_repo.get_enabled()
        now = ist_now()
        today = now.date()
        today_start = datetime.combine(today, dt_time.min, tzinfo=IST)
        today_end = datetime.combine(today, dt_time.max, tzinfo=IST)

        compliance_list = []
        total_missed = 0
        total_delayed = 0

        for schedule in schedules:
            # Get executions for this task today
            today_executions = (
                db.query(IndividualServiceTaskExecution)
                .filter(
                    and_(
                        IndividualServiceTaskExecution.task_name == schedule.task_name,
                        IndividualServiceTaskExecution.executed_at >= today_start,
                        IndividualServiceTaskExecution.executed_at <= today_end,
                    )
                )
                .all()
            )

            execution_count = len(today_executions)
            # Get last execution and ensure it's timezone-aware (UTC) for proper frontend display
            last_execution = None
            if today_executions:
                last_execution = max((e.executed_at for e in today_executions), default=None)
                if last_execution:
                    if last_execution.tzinfo is None:
                        last_execution = last_execution.replace(tzinfo=UTC)
                    elif last_execution.tzinfo != UTC:
                        last_execution = last_execution.astimezone(UTC)

            # Determine expected count
            expected_count = None
            if schedule.is_continuous:
                expected_count = None  # Continuous tasks don't have fixed count
            elif schedule.is_hourly:
                # Would need to calculate based on hours
                expected_count = None
            else:
                expected_count = 1  # Daily tasks expected once

            # Calculate next expected execution
            next_expected = None
            current_time = None
            schedule_time = schedule.schedule_time
            if schedule.enabled:
                now = ist_now()
                current_time = now.time()

                if current_time < schedule_time:
                    # Today's execution hasn't happened yet
                    next_expected = datetime.combine(today, schedule_time, tzinfo=IST)
                # Today's execution should have happened, or tomorrow
                elif not last_execution or last_execution.date() < today:
                    next_expected = datetime.combine(today, schedule_time, tzinfo=IST)
                else:
                    # Next execution is tomorrow
                    next_expected = datetime.combine(
                        today + timedelta(days=1), schedule_time, tzinfo=IST
                    )

                # Convert next_expected to UTC for proper frontend display
                if next_expected:
                    if next_expected.tzinfo is None:
                        next_expected = next_expected.replace(tzinfo=UTC)
                    elif next_expected.tzinfo != UTC:
                        next_expected = next_expected.astimezone(UTC)

            # Determine compliance status
            compliance_status = "not_applicable"
            if schedule.enabled and current_time:
                if execution_count == 0 and current_time > schedule_time:
                    compliance_status = "missed"
                    total_missed += 1
                elif last_execution:
                    exec_time = last_execution.time()
                    if exec_time > schedule_time:
                        scheduled_dt = datetime.combine(today, schedule_time, tzinfo=IST)
                        # Ensure last_execution is timezone-aware for comparison
                        last_exec_dt = last_execution
                        if last_exec_dt.tzinfo is None:
                            last_exec_dt = last_exec_dt.replace(tzinfo=IST)
                        delay_minutes = (last_exec_dt - scheduled_dt).total_seconds() / 60
                        if delay_minutes > 5:  # More than 5 minutes late
                            compliance_status = "delayed"
                            total_delayed += 1
                        else:
                            compliance_status = "on_track"
                    else:
                        compliance_status = "on_track"
                else:
                    compliance_status = "on_track"

            last_status = None
            if today_executions:
                last_status = today_executions[-1].status

            compliance_list.append(
                ScheduleCompliance(
                    task_name=schedule.task_name,
                    scheduled_time=schedule.schedule_time.strftime("%H:%M"),
                    enabled=schedule.enabled,
                    is_continuous=schedule.is_continuous,
                    end_time=schedule.end_time.strftime("%H:%M") if schedule.end_time else None,
                    last_execution_at=last_execution,
                    next_expected_execution=next_expected,
                    execution_count_today=execution_count,
                    expected_count_today=expected_count,
                    compliance_status=compliance_status,
                    last_execution_status=last_status,
                )
            )

        return ScheduleComplianceResponse(
            tasks=compliance_list, total_missed=total_missed, total_delayed=total_delayed
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching schedule compliance: {str(e)}",
        ) from e


# Authentication Monitoring Endpoints


def _get_active_sessions_impl(db: Session) -> ActiveSessionsResponse:
    """Internal implementation to get active authentication sessions"""
    try:
        session_manager = get_shared_session_manager()
        now = ist_now()

        sessions = []
        total_active = 0
        expiring_soon = 0
        expired = 0

        # Access internal sessions dict - wrap in try-except to handle threading issues
        try:
            # Check if _sessions exists and is accessible
            if not hasattr(session_manager, "_sessions"):
                logger.debug("Session manager has no _sessions attribute")
                return ActiveSessionsResponse(
                    sessions=[],
                    total_active=0,
                    expiring_soon=0,
                    expired=0,
                )

            # Make a snapshot of sessions to avoid holding lock during iteration
            # This prevents deadlocks if session manager is being updated
            session_items = list(session_manager._sessions.items())

            # Early return if no sessions exist (common case - avoids unnecessary processing)
            if not session_items:
                logger.debug("No active sessions in session manager")
                return ActiveSessionsResponse(
                    sessions=[],
                    total_active=0,
                    expiring_soon=0,
                    expired=0,
                )

            user_ids = [user_id for user_id, _ in session_items]
        except (AttributeError, RuntimeError, KeyError) as e:
            logger.warning(f"Error accessing session manager sessions: {e}")
            return ActiveSessionsResponse(
                sessions=[],
                total_active=0,
                expiring_soon=0,
                expired=0,
            )

        user_email_map = _get_user_email_map(db, user_ids)

        for user_id, auth in session_items:  # Use snapshot instead of direct access
            try:
                # Wrap these calls in try-except as they might block
                is_authenticated = (
                    auth.is_authenticated() if hasattr(auth, "is_authenticated") else False
                )
                client_available = (
                    auth.get_client() is not None if hasattr(auth, "get_client") else False
                )
            except Exception as e:
                logger.debug(f"Error checking auth status for user {user_id}: {e}")
                is_authenticated = False
                client_available = False

            session_created_at = None
            session_age_minutes = None
            session_status = "expired"
            ttl_remaining_minutes = None

            if hasattr(auth, "session_created_at") and auth.session_created_at:
                session_created_at = datetime.fromtimestamp(auth.session_created_at, tz=IST)
                age_delta = now - session_created_at
                session_age_minutes = age_delta.total_seconds() / 60

                if hasattr(auth, "session_ttl"):
                    ttl_minutes = auth.session_ttl / 60  # Convert to minutes
                    remaining = ttl_minutes - session_age_minutes

                    if remaining > 10:
                        session_status = "valid"
                        total_active += 1
                    elif remaining > 0:
                        session_status = "expiring_soon"
                        expiring_soon += 1
                    else:
                        session_status = "expired"
                        expired += 1

                    ttl_remaining_minutes = max(0, remaining)
                else:
                    # Default TTL assumption (55 minutes)
                    remaining = 55 - session_age_minutes
                    if remaining > 0:
                        session_status = "valid" if remaining > 10 else "expiring_soon"
                        total_active += 1 if remaining > 10 else 0
                        expiring_soon += 1 if 0 < remaining <= 10 else 0
                    else:
                        expired += 1

                    ttl_remaining_minutes = max(0, remaining)

            sessions.append(
                ActiveSession(
                    user_id=user_id,
                    user_email=user_email_map.get(user_id),
                    session_created_at=session_created_at,
                    session_age_minutes=session_age_minutes,
                    session_status=session_status,
                    ttl_remaining_minutes=ttl_remaining_minutes,
                    is_authenticated=is_authenticated,
                    client_available=client_available,
                )
            )

        return ActiveSessionsResponse(
            sessions=sessions,
            total_active=total_active,
            expiring_soon=expiring_soon,
            expired=expired,
        )
    except Exception as e:
        logger.warning(f"Error in _get_active_sessions_impl: {e}", exc_info=True)
        return ActiveSessionsResponse(
            sessions=[],
            total_active=0,
            expiring_soon=0,
            expired=0,
        )


@router.get("/auth/sessions", response_model=ActiveSessionsResponse)
def get_active_sessions(
    db: Session = Depends(get_db),
):
    """Get active authentication sessions"""
    try:
        return _get_active_sessions_impl(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching active sessions: {str(e)}",
        ) from e


@router.get("/auth/reauth-history", response_model=ReauthHistoryResponse)
def get_reauth_history(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    user_id: int | None = Query(None, description="Filter by user ID"),
    start_date: date | None = Query(None, description="Filter by start date"),
    end_date: date | None = Query(None, description="Filter by end date"),
    db: Session = Depends(get_db),
):
    """Get re-authentication history from error logs"""
    try:
        # Query error logs for auth-related errors
        query = db.query(ErrorLog).filter(
            or_(
                ErrorLog.error_message.ilike("%jwt%"),
                ErrorLog.error_message.ilike("%reauth%"),
                ErrorLog.error_message.ilike("%re-authentication%"),
                ErrorLog.error_message.ilike("%token expired%"),
                ErrorLog.error_message.ilike("%unauthorized%"),
            )
        )

        if user_id:
            query = query.filter(ErrorLog.user_id == user_id)
        if start_date:
            start_datetime = datetime.combine(start_date, dt_time.min)
            query = query.filter(ErrorLog.occurred_at >= start_datetime)
        if end_date:
            end_datetime = datetime.combine(end_date, dt_time.max)
            query = query.filter(ErrorLog.occurred_at <= end_datetime)

        total_count = query.count()

        offset = (page - 1) * page_size
        errors = query.order_by(desc(ErrorLog.occurred_at)).offset(offset).limit(page_size).all()

        user_ids = list({e.user_id for e in errors})
        user_email_map = _get_user_email_map(db, user_ids)

        events = []
        for error in errors:
            message_lower = error.error_message.lower() if error.error_message else ""
            reauth_status = "failed"
            reason = None

            if "reauth" in message_lower or "re-authentication" in message_lower:
                if "successful" in message_lower or "success" in message_lower:
                    reauth_status = "success"
                elif "cooldown" in message_lower or "rate" in message_lower:
                    reauth_status = "rate_limited"

            if "jwt" in message_lower:
                reason = "JWT token expired"
            elif "token expired" in message_lower:
                reason = "Token expired"
            elif "unauthorized" in message_lower:
                reason = "Unauthorized"

            # Extract method/API from error message if available
            triggered_by = None
            if error.context:
                triggered_by = error.context.get("method") or error.context.get("action")

            events.append(
                ReauthEvent(
                    id=error.id,
                    user_id=error.user_id,
                    user_email=user_email_map.get(error.user_id),
                    timestamp=error.occurred_at,
                    triggered_by=triggered_by,
                    status=reauth_status,
                    duration_seconds=None,  # Not available in error logs
                    reason=reason,
                    error_message=error.error_message,
                )
            )

        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

        return ReauthHistoryResponse(
            events=events,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching re-auth history: {str(e)}",
        ) from e


@router.get("/auth/errors", response_model=AuthErrorsResponse)
def get_auth_errors(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    user_id: int | None = Query(None, description="Filter by user ID"),
    start_date: date | None = Query(None, description="Filter by start date"),
    end_date: date | None = Query(None, description="Filter by end date"),
    db: Session = Depends(get_db),
):
    """Get authentication errors"""
    try:
        query = db.query(ErrorLog).filter(
            or_(
                ErrorLog.error_message.ilike("%jwt%"),
                ErrorLog.error_message.ilike("%unauthorized%"),
                ErrorLog.error_message.ilike("%token expired%"),
                ErrorLog.error_message.ilike("%invalid credentials%"),
                ErrorLog.error_message.ilike("%authentication%"),
                ErrorLog.error_type.ilike("%auth%"),
            )
        )

        if user_id:
            query = query.filter(ErrorLog.user_id == user_id)
        if start_date:
            start_datetime = datetime.combine(start_date, dt_time.min)
            query = query.filter(ErrorLog.occurred_at >= start_datetime)
        if end_date:
            end_datetime = datetime.combine(end_date, dt_time.max)
            query = query.filter(ErrorLog.occurred_at <= end_datetime)

        total_count = query.count()

        offset = (page - 1) * page_size
        errors = query.order_by(desc(ErrorLog.occurred_at)).offset(offset).limit(page_size).all()

        user_ids = list({e.user_id for e in errors})
        user_email_map = _get_user_email_map(db, user_ids)

        auth_errors = []
        for error in errors:
            message = error.error_message or ""
            message_lower = message.lower()

            error_type = "Unknown"
            error_code = None

            if "900901" in message or "jwt token expired" in message_lower:
                error_type = "JWT expired"
                error_code = "900901"
            elif "invalid jwt token" in message_lower:
                error_type = "Invalid JWT token"
            elif "invalid credentials" in message_lower:
                error_type = "Invalid credentials"
            elif "unauthorized" in message_lower:
                error_type = "Unauthorized"

            # Extract API endpoint/method from context
            api_endpoint = None
            method_name = None
            if error.context:
                api_endpoint = error.context.get("endpoint") or error.context.get("path")
                method_name = error.context.get("method") or error.context.get("action")

            # Determine if re-auth was attempted
            reauth_attempted = "reauth" in message_lower or "re-authentication" in message_lower
            reauth_success = None
            if reauth_attempted:
                reauth_success = "successful" in message_lower or "success" in message_lower

            auth_errors.append(
                AuthError(
                    id=error.id,
                    user_id=error.user_id,
                    user_email=user_email_map.get(error.user_id),
                    timestamp=error.occurred_at,
                    error_type=error_type,
                    error_code=error_code,
                    error_message=message,
                    api_endpoint=api_endpoint,
                    method_name=method_name,
                    reauth_attempted=reauth_attempted,
                    reauth_success=reauth_success,
                )
            )

        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

        return AuthErrorsResponse(
            errors=auth_errors,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching auth errors: {str(e)}",
        ) from e


@router.get("/auth/stats", response_model=ReauthStatisticsResponse)
def get_reauth_statistics(
    period_days: int = Query(1, ge=1, le=30, description="Period in days"),
    user_id: int | None = Query(None, description="Filter by user ID"),
    db: Session = Depends(get_db),
):
    """Get re-authentication statistics"""
    try:
        start_date = ist_now().date() - timedelta(days=period_days)
        start_datetime = datetime.combine(start_date, dt_time.min)

        # Query error logs for re-auth events
        query = db.query(ErrorLog).filter(
            and_(
                ErrorLog.occurred_at >= start_datetime,
                or_(
                    ErrorLog.error_message.ilike("%reauth%"),
                    ErrorLog.error_message.ilike("%re-authentication%"),
                ),
            )
        )

        if user_id:
            query = query.filter(ErrorLog.user_id == user_id)

        errors = query.all()

        # Group by user_id
        user_stats: dict[int, dict] = defaultdict(
            lambda: {
                "events": [],
                "success_count": 0,
                "failed_count": 0,
                "total_count": 0,
            }
        )

        for error in errors:
            stats = user_stats[error.user_id]
            stats["events"].append(error)
            stats["total_count"] += 1

            message_lower = (error.error_message or "").lower()
            if "successful" in message_lower or "success" in message_lower:
                stats["success_count"] += 1
            else:
                stats["failed_count"] += 1

        user_ids = list(user_stats.keys())
        user_email_map = _get_user_email_map(db, user_ids)

        statistics = []
        now = ist_now()
        period_hours = period_days * 24

        for uid, stats in user_stats.items():
            events = stats["events"]
            # Ensure occurred_at is timezone-aware for comparison
            events_24h = []
            for e in events:
                occurred_at = e.occurred_at
                if occurred_at.tzinfo is None:
                    occurred_at = occurred_at.replace(tzinfo=IST)
                if (now - occurred_at).total_seconds() < 86400:
                    events_24h.append(e)

            events_7d = []
            for e in events:
                occurred_at = e.occurred_at
                if occurred_at.tzinfo is None:
                    occurred_at = occurred_at.replace(tzinfo=IST)
                if (now - occurred_at).total_seconds() < 604800:
                    events_7d.append(e)

            events_30d = events if period_days >= 30 else []

            success_rate = (
                (stats["success_count"] / stats["total_count"] * 100)
                if stats["total_count"] > 0
                else 0.0
            )

            # Calculate average time between re-auths
            avg_time_between = None
            if len(events) > 1:
                sorted_events = sorted(events, key=lambda e: e.occurred_at)
                time_diffs = []
                for i in range(1, len(sorted_events)):
                    occurred_at1 = sorted_events[i].occurred_at
                    occurred_at2 = sorted_events[i - 1].occurred_at
                    # Ensure both are timezone-aware
                    if occurred_at1.tzinfo is None:
                        occurred_at1 = occurred_at1.replace(tzinfo=IST)
                    if occurred_at2.tzinfo is None:
                        occurred_at2 = occurred_at2.replace(tzinfo=IST)
                    diff = (occurred_at1 - occurred_at2).total_seconds()
                    time_diffs.append(diff / 60)  # Convert to minutes
                if time_diffs:
                    avg_time_between = sum(time_diffs) / len(time_diffs)

            reauth_rate_per_hour = stats["total_count"] / period_hours if period_hours > 0 else 0.0

            # Check rate limiting status (would need access to shared_session_manager)
            rate_limited = False
            cooldown_remaining = None

            statistics.append(
                ReauthStatistics(
                    user_id=uid,
                    user_email=user_email_map.get(uid),
                    reauth_count_24h=len(events_24h),
                    reauth_count_7d=len(events_7d),
                    reauth_count_30d=len(events_30d),
                    reauth_rate_per_hour=reauth_rate_per_hour,
                    success_rate=success_rate,
                    avg_time_between_reauth_minutes=avg_time_between,
                    rate_limited=rate_limited,
                    cooldown_remaining_seconds=cooldown_remaining,
                    blocked=False,  # Would need to check from shared_session_manager
                )
            )

        return ReauthStatisticsResponse(statistics=statistics, period_days=period_days)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching re-auth statistics: {str(e)}",
        ) from e


# Combined Dashboard Endpoint


@router.get("/dashboard", response_model=MonitoringDashboardResponse)
def get_monitoring_dashboard(
    db: Session = Depends(get_db),
):
    """Get complete monitoring dashboard data"""
    try:
        now = ist_now()
        today = now.date()
        # Create timezone-aware datetime for today_start
        today_start = datetime.combine(today, dt_time.min, tzinfo=IST)

        # Get service health
        services_health = _get_services_health_impl(db)
        total_services = len(services_health.services)
        services_running = services_health.total_running
        services_stopped = services_health.total_stopped

        # Get task executions today - use count() queries for performance
        # These queries use indexes and don't load all records into memory
        tasks_executed_today = (
            db.query(IndividualServiceTaskExecution)
            .filter(IndividualServiceTaskExecution.executed_at >= today_start)
            .count()
        )

        tasks_successful_today = (
            db.query(IndividualServiceTaskExecution)
            .filter(
                IndividualServiceTaskExecution.executed_at >= today_start,
                IndividualServiceTaskExecution.status == "success",
            )
            .count()
        )

        tasks_failed_today = (
            db.query(IndividualServiceTaskExecution)
            .filter(
                IndividualServiceTaskExecution.executed_at >= today_start,
                IndividualServiceTaskExecution.status == "failed",
            )
            .count()
        )

        # Get active sessions - with error handling to prevent hanging
        try:
            active_sessions = _get_active_sessions_impl(db)
        except Exception as e:
            logger.warning(f"Error getting active sessions (using fallback): {e}", exc_info=True)
            # Fallback to empty response to prevent dashboard from hanging
            active_sessions = ActiveSessionsResponse(
                sessions=[],
                total_active=0,
                expiring_soon=0,
                expired=0,
            )

        # Get re-auth count in last 24h - optimized for performance
        reauth_start = now - timedelta(hours=24)

        # Use count() for total count (fast, uses index)
        reauth_count_24h = (
            db.query(ErrorLog)
            .filter(
                and_(
                    ErrorLog.occurred_at >= reauth_start,
                    or_(
                        ErrorLog.error_message.ilike("%reauth%"),
                        ErrorLog.error_message.ilike("%re-authentication%"),
                    ),
                )
            )
            .count()
        )

        # For success rate calculation, use limited sample (approximate but fast)
        # This prevents loading thousands of records into memory
        reauth_errors_sample = (
            db.query(ErrorLog)
            .filter(
                and_(
                    ErrorLog.occurred_at >= reauth_start,
                    or_(
                        ErrorLog.error_message.ilike("%reauth%"),
                        ErrorLog.error_message.ilike("%re-authentication%"),
                    ),
                )
            )
            .order_by(desc(ErrorLog.occurred_at))  # Use index on occurred_at
            .limit(1000)  # Reasonable limit for approximate calculation
            .all()
        )

        reauth_success_count = len(
            [
                e
                for e in reauth_errors_sample
                if "successful" in (e.error_message or "").lower()
                or "success" in (e.error_message or "").lower()
            ]
        )

        # Approximate success rate (from sample if count > 1000, otherwise exact)
        if reauth_count_24h > 0:
            if reauth_count_24h <= 1000:
                # Exact calculation (sample size matches total)
                reauth_success_rate = reauth_success_count / reauth_count_24h * 100
            else:
                # Approximate calculation (from sample)
                reauth_success_rate = reauth_success_count / len(reauth_errors_sample) * 100
        else:
            reauth_success_rate = 0.0

        # Get auth errors in last 24h
        auth_errors_24h = (
            db.query(ErrorLog)
            .filter(
                and_(
                    ErrorLog.occurred_at >= reauth_start,
                    or_(
                        ErrorLog.error_message.ilike("%jwt%"),
                        ErrorLog.error_message.ilike("%unauthorized%"),
                        ErrorLog.error_message.ilike("%token expired%"),
                    ),
                )
            )
            .count()
        )

        # Count tasks failed due to auth (would need more sophisticated analysis)
        tasks_failed_due_to_auth = 0  # Placeholder

        # Create summary
        summary = DashboardSummary(
            total_services=total_services,
            services_running=services_running,
            services_stopped=services_stopped,
            tasks_executed_today=tasks_executed_today,
            tasks_successful_today=tasks_successful_today,
            tasks_failed_today=tasks_failed_today,
            services_with_errors=services_health.services_with_recent_errors,
            active_sessions=active_sessions.total_active,
            sessions_expiring_soon=active_sessions.expiring_soon,
            reauth_count_24h=reauth_count_24h,
            reauth_success_rate=reauth_success_rate,
            auth_errors_24h=auth_errors_24h,
            tasks_failed_due_to_auth=tasks_failed_due_to_auth,
        )

        # Generate alerts
        alerts = []
        critical_count = 0
        warning_count = 0
        info_count = 0

        # Check for critical issues
        for service in services_health.services:
            if service.service_running and service.heartbeat_age_seconds:
                if service.heartbeat_age_seconds > 300:  # > 5 minutes
                    alerts.append(
                        {
                            "severity": "critical",
                            "type": "service_stale",
                            "message": (
                                f"Service for user {service.user_id} stale "
                                f"(no heartbeat for {service.heartbeat_age_seconds:.0f}s)"
                            ),
                            "user_id": service.user_id,
                        }
                    )
                    critical_count += 1
                elif service.heartbeat_age_seconds > 120:  # > 2 minutes
                    alerts.append(
                        {
                            "severity": "warning",
                            "type": "service_delayed_heartbeat",
                            "message": (
                                f"Service for user {service.user_id} delayed heartbeat "
                                f"({service.heartbeat_age_seconds:.0f}s)"
                            ),
                            "user_id": service.user_id,
                        }
                    )
                    warning_count += 1

            if service.error_count > 5:  # > 5 errors
                alerts.append(
                    {
                        "severity": "warning",
                        "type": "service_errors",
                        "message": (
                            f"Service for user {service.user_id} has {service.error_count} errors"
                        ),
                        "user_id": service.user_id,
                    }
                )
                warning_count += 1

        # Check for expired sessions
        for session in active_sessions.sessions:
            if session.session_status == "expired":
                alerts.append(
                    {
                        "severity": "critical",
                        "type": "session_expired",
                        "message": f"Session expired for user {session.user_id}",
                        "user_id": session.user_id,
                    }
                )
                critical_count += 1

        # Get recent task executions (last 20)
        recent_executions_query = (
            db.query(IndividualServiceTaskExecution)
            .order_by(desc(IndividualServiceTaskExecution.executed_at))
            .limit(20)
        )
        recent_executions = recent_executions_query.all()

        schedule_repo = ServiceScheduleRepository(db)
        all_schedules = schedule_repo.get_all()
        schedule_map = {s.task_name: s for s in all_schedules}
        user_ids = list({e.user_id for e in recent_executions})
        user_email_map = _get_user_email_map(db, user_ids)

        recent_task_executions = []
        for exec in recent_executions:
            schedule = schedule_map.get(exec.task_name)
            scheduled_time = None
            time_diff = None

            if schedule and exec.executed_at:
                exec_date = exec.executed_at.date()
                scheduled_datetime = datetime.combine(exec_date, schedule.schedule_time, tzinfo=IST)
                if exec.executed_at:
                    # Ensure executed_at is timezone-aware for comparison
                    exec_dt = exec.executed_at
                    if exec_dt.tzinfo is None:
                        exec_dt = exec_dt.replace(tzinfo=IST)
                    time_diff = (exec_dt - scheduled_datetime).total_seconds()
                    scheduled_time = schedule.schedule_time.strftime("%H:%M")

            # Ensure executed_at is timezone-aware (UTC) for proper frontend display
            executed_at_utc = exec.executed_at
            if executed_at_utc:
                if executed_at_utc.tzinfo is None:
                    executed_at_utc = executed_at_utc.replace(tzinfo=UTC)
                elif executed_at_utc.tzinfo != UTC:
                    executed_at_utc = executed_at_utc.astimezone(UTC)

            recent_task_executions.append(
                TaskExecutionWithSchedule(
                    id=exec.id,
                    user_id=exec.user_id,
                    user_email=user_email_map.get(exec.user_id),
                    task_name=exec.task_name,
                    scheduled_time=scheduled_time,
                    executed_at=executed_at_utc,
                    time_difference_seconds=time_diff,
                    status=exec.status,
                    duration_seconds=exec.duration_seconds,
                    execution_type=exec.execution_type,
                    details=exec.details,
                )
            )

        # Get recent re-auth events (last 20) - ADD TIME FILTER
        recent_reauth_query = (
            db.query(ErrorLog)
            .filter(
                and_(
                    ErrorLog.occurred_at >= reauth_start,  # Filter by time to avoid full table scan
                    or_(
                        ErrorLog.error_message.ilike("%reauth%"),
                        ErrorLog.error_message.ilike("%re-authentication%"),
                    ),
                )
            )
            .order_by(desc(ErrorLog.occurred_at))
            .limit(20)
        )
        recent_reauth_errors = recent_reauth_query.all()

        user_ids_reauth = list({e.user_id for e in recent_reauth_errors})
        user_email_map_reauth = _get_user_email_map(db, user_ids_reauth)

        recent_reauth_events = []
        for error in recent_reauth_errors:
            message_lower = (error.error_message or "").lower()
            reauth_status = "failed"
            reason = None

            if "successful" in message_lower or "success" in message_lower:
                reauth_status = "success"
            elif "cooldown" in message_lower:
                reauth_status = "rate_limited"

            if "jwt" in message_lower:
                reason = "JWT token expired"

            triggered_by = None
            if error.context:
                triggered_by = error.context.get("method") or error.context.get("action")

            recent_reauth_events.append(
                ReauthEvent(
                    id=error.id,
                    user_id=error.user_id,
                    user_email=user_email_map_reauth.get(error.user_id),
                    timestamp=error.occurred_at,
                    triggered_by=triggered_by,
                    status=reauth_status,
                    duration_seconds=None,
                    reason=reason,
                    error_message=error.error_message,
                )
            )

        # Get running tasks - with error handling
        try:
            running_tasks_response = _get_running_tasks_impl(db, None)
            running_tasks = running_tasks_response.tasks
        except Exception as e:
            logger.warning(f"Error getting running tasks (using fallback): {e}", exc_info=True)
            # Fallback to empty list
            running_tasks = []

        return MonitoringDashboardResponse(
            summary=summary,
            alerts=DashboardAlerts(
                alerts=alerts,
                critical_count=critical_count,
                warning_count=warning_count,
                info_count=info_count,
            ),
            recent_task_executions=recent_task_executions,
            recent_reauth_events=recent_reauth_events,
            running_tasks=running_tasks,
            updated_at=now,
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full exception for debugging
        logger.exception(f"Error in get_monitoring_dashboard: {str(e)}")
        logger.error(traceback.format_exc())

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching monitoring dashboard: {str(e)}",
        ) from e
