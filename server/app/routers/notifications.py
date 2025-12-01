"""
Notifications API Router

Provides REST API endpoints for managing in-app notifications.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Users
from src.infrastructure.persistence.notification_repository import NotificationRepository

from ..core.deps import get_current_user, get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/notifications")
def get_notifications(
    type: Literal["service", "trading", "system", "error"] | None = Query(
        None, description="Filter by notification type"
    ),
    level: Literal["info", "warning", "error", "critical"] | None = Query(
        None, description="Filter by notification level"
    ),
    read: bool | None = Query(None, description="Filter by read status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of notifications to return"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> list[dict]:
    """
    Get notifications for the current user.

    Returns a list of notifications, optionally filtered by type, level, and read status.
    """
    try:
        notification_repo = NotificationRepository(db)
        notifications = notification_repo.list(
            user_id=current_user.id,
            type=type,
            level=level,
            read=read,
            limit=limit,
        )

        return [
            {
                "id": n.id,
                "user_id": n.user_id,
                "type": n.type,
                "level": n.level,
                "title": n.title,
                "message": n.message,
                "read": n.read,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat(),
                "telegram_sent": n.telegram_sent,
                "email_sent": n.email_sent,
                "in_app_delivered": n.in_app_delivered,
            }
            for n in notifications
        ]
    except Exception as e:
        logger.exception(f"Error getting notifications for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notifications",
        ) from e


@router.get("/notifications/unread")
def get_unread_notifications(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of notifications to return"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> list[dict]:
    """Get unread notifications for the current user."""
    try:
        notification_repo = NotificationRepository(db)
        notifications = notification_repo.get_unread(user_id=current_user.id, limit=limit)

        return [
            {
                "id": n.id,
                "user_id": n.user_id,
                "type": n.type,
                "level": n.level,
                "title": n.title,
                "message": n.message,
                "read": n.read,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat(),
                "telegram_sent": n.telegram_sent,
                "email_sent": n.email_sent,
                "in_app_delivered": n.in_app_delivered,
            }
            for n in notifications
        ]
    except Exception as e:
        logger.exception(f"Error getting unread notifications for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve unread notifications",
        ) from e


@router.get("/notifications/count")
def get_notification_count(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """Get count of unread notifications for the current user."""
    try:
        notification_repo = NotificationRepository(db)
        count = notification_repo.count_unread(user_id=current_user.id)
        return {"unread_count": count}
    except Exception as e:
        logger.exception(f"Error getting notification count for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notification count",
        ) from e


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """Mark a notification as read."""
    try:
        notification_repo = NotificationRepository(db)
        notification = notification_repo.get(notification_id)

        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification {notification_id} not found",
            )

        if notification.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this notification",
            )

        updated = notification_repo.mark_read(notification_id)

        return {
            "id": updated.id,
            "read": updated.read,
            "read_at": updated.read_at.isoformat() if updated.read_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error marking notification {notification_id} as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read",
        ) from e


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict:
    """Mark all notifications as read for the current user."""
    try:
        notification_repo = NotificationRepository(db)
        count = notification_repo.mark_all_read(user_id=current_user.id)
        return {"marked_read": count}
    except Exception as e:
        logger.exception(f"Error marking all notifications as read for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark all notifications as read",
        ) from e
