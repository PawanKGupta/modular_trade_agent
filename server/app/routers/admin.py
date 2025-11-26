# ruff: noqa: B008
from datetime import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application.services.schedule_manager import ScheduleManager
from src.infrastructure.db.models import UserRole, Users
from src.infrastructure.persistence.service_schedule_repository import (
    ServiceScheduleRepository,
)
from src.infrastructure.persistence.settings_repository import SettingsRepository
from src.infrastructure.persistence.user_repository import UserRepository

from ..core.deps import get_current_user, get_db, require_admin
from ..schemas.admin import AdminUserCreate, AdminUserResponse, AdminUserUpdate
from ..schemas.service import (
    ServiceScheduleResponse,
    ServiceSchedulesResponse,
    UpdateServiceScheduleRequest,
    UpdateServiceScheduleResponse,
)

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(db: Session = Depends(get_db)):
    users = UserRepository(db).list_users(active_only=False)
    return [
        AdminUserResponse(
            id=u.id, email=u.email, name=u.name, role=u.role.value, is_active=u.is_active
        )
        for u in users
    ]


@router.post("/users", response_model=AdminUserResponse)
def create_user(payload: AdminUserCreate, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    if repo.get_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    role = UserRole(payload.role)
    u = repo.create_user(
        email=payload.email, password=payload.password, name=payload.name, role=role
    )

    # Create default settings for new user (required for trading service)
    SettingsRepository(db).ensure_default(u.id)

    return AdminUserResponse(
        id=u.id, email=u.email, name=u.name, role=u.role.value, is_active=u.is_active
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(user_id: int, payload: AdminUserUpdate, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    role = UserRole(payload.role) if payload.role else None
    u = repo.update_user(user, name=payload.name, role=role, is_active=payload.is_active)
    return AdminUserResponse(
        id=u.id, email=u.email, name=u.name, role=u.role.value, is_active=u.is_active
    )


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent deleting last admin
    def is_admin(u) -> bool:
        try:
            return getattr(u.role, "value", str(u.role)).lower() == "admin"
        except Exception:
            return False

    if is_admin(user):
        admins = [u for u in repo.list_users(active_only=False) if is_admin(u) and u.is_active]
        if len(admins) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete last admin"
            )
    repo.update_user(user, is_active=False)
    return {"status": "ok"}


# Service Schedule Management Endpoints


def get_schedule_manager(db: Session = Depends(get_db)) -> ScheduleManager:
    """Dependency to get ScheduleManager instance"""
    return ScheduleManager(db)


@router.get("/schedules", response_model=ServiceSchedulesResponse)
def list_service_schedules(
    db: Session = Depends(get_db),
    schedule_manager: ScheduleManager = Depends(get_schedule_manager),
):
    """List all service schedules (admin only)"""
    try:
        schedules = schedule_manager.get_all_schedules()
        schedule_responses = []
        for schedule in schedules:
            next_execution = schedule_manager.calculate_next_execution(schedule.task_name)
            schedule_responses.append(
                ServiceScheduleResponse(
                    id=schedule.id,
                    task_name=schedule.task_name,
                    schedule_time=schedule.schedule_time.strftime("%H:%M"),
                    enabled=schedule.enabled,
                    is_hourly=schedule.is_hourly,
                    is_continuous=schedule.is_continuous,
                    end_time=schedule.end_time.strftime("%H:%M") if schedule.end_time else None,
                    schedule_type=schedule.schedule_type,
                    description=schedule.description,
                    updated_by=schedule.updated_by,
                    updated_at=schedule.updated_at,
                    next_execution_at=next_execution,
                )
            )
        return ServiceSchedulesResponse(schedules=schedule_responses)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing schedules: {str(e)}",
        ) from e


@router.get("/schedules/{task_name}", response_model=ServiceScheduleResponse)
def get_service_schedule(
    task_name: str,
    db: Session = Depends(get_db),
    schedule_manager: ScheduleManager = Depends(get_schedule_manager),
):
    """Get service schedule for a specific task (admin only)"""
    try:
        schedule = schedule_manager.get_schedule(task_name)
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule not found for task: {task_name}",
            )

        next_execution = schedule_manager.calculate_next_execution(task_name)
        return ServiceScheduleResponse(
            id=schedule.id,
            task_name=schedule.task_name,
            schedule_time=schedule.schedule_time.strftime("%H:%M"),
            enabled=schedule.enabled,
            is_hourly=schedule.is_hourly,
            is_continuous=schedule.is_continuous,
            end_time=schedule.end_time.strftime("%H:%M") if schedule.end_time else None,
            schedule_type=schedule.schedule_type,
            description=schedule.description,
            updated_by=schedule.updated_by,
            updated_at=schedule.updated_at,
            next_execution_at=next_execution,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting schedule: {str(e)}",
        ) from e


@router.put("/schedules/{task_name}", response_model=UpdateServiceScheduleResponse)
def update_service_schedule(
    task_name: str,
    payload: UpdateServiceScheduleRequest,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    schedule_manager: ScheduleManager = Depends(get_schedule_manager),
):
    """Update service schedule for a task (admin only)"""
    try:
        # Parse time strings
        try:
            schedule_time_parts = payload.schedule_time.split(":")
            schedule_time_obj = time(
                hour=int(schedule_time_parts[0]), minute=int(schedule_time_parts[1])
            )
        except (ValueError, IndexError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid schedule_time format. Expected HH:MM, got: {payload.schedule_time}"
                ),
            ) from e

        end_time_obj = None
        if payload.end_time:
            try:
                end_time_parts = payload.end_time.split(":")
                end_time_obj = time(hour=int(end_time_parts[0]), minute=int(end_time_parts[1]))
            except (ValueError, IndexError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid end_time format. Expected HH:MM, got: {payload.end_time}",
                ) from e

        # Validate schedule
        is_valid, error_message = schedule_manager.validate_schedule(
            task_name=task_name,
            schedule_time=schedule_time_obj,
            is_hourly=payload.is_hourly,
            is_continuous=payload.is_continuous,
            end_time=end_time_obj,
            schedule_type=payload.schedule_type,
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message,
            )

        # Update schedule
        schedule_repo = ServiceScheduleRepository(db)
        schedule = schedule_repo.create_or_update(
            task_name=task_name,
            schedule_time=schedule_time_obj,
            enabled=payload.enabled,
            is_hourly=payload.is_hourly,
            is_continuous=payload.is_continuous,
            end_time=end_time_obj,
            schedule_type=payload.schedule_type,
            description=payload.description,
            updated_by=current.id,
        )

        next_execution = schedule_manager.calculate_next_execution(task_name)
        schedule_response = ServiceScheduleResponse(
            id=schedule.id,
            task_name=schedule.task_name,
            schedule_time=schedule.schedule_time.strftime("%H:%M"),
            enabled=schedule.enabled,
            is_hourly=schedule.is_hourly,
            is_continuous=schedule.is_continuous,
            end_time=schedule.end_time.strftime("%H:%M") if schedule.end_time else None,
            schedule_type=schedule.schedule_type,
            description=schedule.description,
            updated_by=schedule.updated_by,
            updated_at=schedule.updated_at,
            next_execution_at=next_execution,
        )

        return UpdateServiceScheduleResponse(
            success=True,
            message=f"Schedule for '{task_name}' updated successfully",
            schedule=schedule_response,
            requires_restart=True,  # Unified service should restart to pick up new schedule
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating schedule: {str(e)}",
        ) from e


@router.post("/schedules/{task_name}/enable", response_model=UpdateServiceScheduleResponse)
def enable_service_schedule(
    task_name: str,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    schedule_manager: ScheduleManager = Depends(get_schedule_manager),
):
    """Enable a service schedule (admin only)"""
    try:
        schedule_repo = ServiceScheduleRepository(db)
        schedule = schedule_repo.update_enabled(task_name, enabled=True, updated_by=current.id)
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule not found for task: {task_name}",
            )

        next_execution = schedule_manager.calculate_next_execution(task_name)
        schedule_response = ServiceScheduleResponse(
            id=schedule.id,
            task_name=schedule.task_name,
            schedule_time=schedule.schedule_time.strftime("%H:%M"),
            enabled=schedule.enabled,
            is_hourly=schedule.is_hourly,
            is_continuous=schedule.is_continuous,
            end_time=schedule.end_time.strftime("%H:%M") if schedule.end_time else None,
            schedule_type=schedule.schedule_type,
            description=schedule.description,
            updated_by=schedule.updated_by,
            updated_at=schedule.updated_at,
            next_execution_at=next_execution,
        )

        return UpdateServiceScheduleResponse(
            success=True,
            message=f"Schedule for '{task_name}' enabled",
            schedule=schedule_response,
            requires_restart=True,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error enabling schedule: {str(e)}",
        ) from e


@router.post("/schedules/{task_name}/disable", response_model=UpdateServiceScheduleResponse)
def disable_service_schedule(
    task_name: str,
    db: Session = Depends(get_db),
    current: Users = Depends(get_current_user),
    schedule_manager: ScheduleManager = Depends(get_schedule_manager),
):
    """Disable a service schedule (admin only)"""
    try:
        schedule_repo = ServiceScheduleRepository(db)
        schedule = schedule_repo.update_enabled(task_name, enabled=False, updated_by=current.id)
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule not found for task: {task_name}",
            )

        next_execution = schedule_manager.calculate_next_execution(task_name)
        schedule_response = ServiceScheduleResponse(
            id=schedule.id,
            task_name=schedule.task_name,
            schedule_time=schedule.schedule_time.strftime("%H:%M"),
            enabled=schedule.enabled,
            is_hourly=schedule.is_hourly,
            is_continuous=schedule.is_continuous,
            end_time=schedule.end_time.strftime("%H:%M") if schedule.end_time else None,
            schedule_type=schedule.schedule_type,
            description=schedule.description,
            updated_by=schedule.updated_by,
            updated_at=schedule.updated_at,
            next_execution_at=next_execution,
        )

        return UpdateServiceScheduleResponse(
            success=True,
            message=f"Schedule for '{task_name}' disabled",
            schedule=schedule_response,
            requires_restart=True,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error disabling schedule: {str(e)}",
        ) from e
