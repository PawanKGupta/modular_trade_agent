"""
Notification Preferences API Router

Phase 5: Notification Preferences Implementation

Provides REST API endpoints for managing user notification preferences.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from services.notification_preference_service import NotificationPreferenceService
from src.infrastructure.db.models import UserNotificationPreferences, Users

from ..core.deps import get_current_user, get_db
from ..schemas.notification_preferences import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _preferences_to_response(prefs: UserNotificationPreferences) -> NotificationPreferencesResponse:
    """Convert UserNotificationPreferences model to response schema"""
    return NotificationPreferencesResponse(
        telegram_enabled=prefs.telegram_enabled,
        telegram_chat_id=prefs.telegram_chat_id,
        email_enabled=prefs.email_enabled,
        email_address=prefs.email_address,
        in_app_enabled=prefs.in_app_enabled,
        notify_service_events=prefs.notify_service_events,
        notify_trading_events=prefs.notify_trading_events,
        notify_system_events=prefs.notify_system_events,
        notify_errors=prefs.notify_errors,
        notify_order_placed=prefs.notify_order_placed,
        notify_order_rejected=prefs.notify_order_rejected,
        notify_order_executed=prefs.notify_order_executed,
        notify_order_cancelled=prefs.notify_order_cancelled,
        notify_order_modified=prefs.notify_order_modified,
        notify_retry_queue_added=prefs.notify_retry_queue_added,
        notify_retry_queue_updated=prefs.notify_retry_queue_updated,
        notify_retry_queue_removed=prefs.notify_retry_queue_removed,
        notify_retry_queue_retried=prefs.notify_retry_queue_retried,
        notify_partial_fill=prefs.notify_partial_fill,
        notify_system_errors=prefs.notify_system_errors,
        notify_system_warnings=prefs.notify_system_warnings,
        notify_system_info=prefs.notify_system_info,
        quiet_hours_start=prefs.quiet_hours_start,
        quiet_hours_end=prefs.quiet_hours_end,
    )


@router.get("/notification-preferences", response_model=NotificationPreferencesResponse)
def get_notification_preferences(
    db: Session = Depends(get_db), current_user: Users = Depends(get_current_user)
) -> NotificationPreferencesResponse:
    """
    Get notification preferences for the current user.

    Returns default preferences if user has not configured any preferences yet.
    """
    try:
        preference_service = NotificationPreferenceService(db_session=db)
        preferences = preference_service.get_or_create_default_preferences(current_user.id)
        return _preferences_to_response(preferences)
    except Exception as e:
        logger.exception(f"Error getting notification preferences for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notification preferences",
        ) from e


@router.put("/notification-preferences", response_model=NotificationPreferencesResponse)
def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> NotificationPreferencesResponse:
    """
    Update notification preferences for the current user.

    Only provided fields will be updated. Fields set to None will be ignored.
    """
    try:
        preference_service = NotificationPreferenceService(db_session=db)

        # Convert Pydantic model to dict
        # Include all set fields, including None values for optional fields
        # None values are valid for optional fields (quiet_hours, telegram_chat_id, email_address)
        update_dict: dict[str, Any] = {}
        for field, value in payload.model_dump(exclude_unset=True).items():
            # Include all values, including None for optional fields
            # The service layer will handle None values appropriately
            update_dict[field] = value

        if not update_dict:
            # No fields to update, just return current preferences
            preferences = preference_service.get_or_create_default_preferences(current_user.id)
            return _preferences_to_response(preferences)

        # Update preferences
        updated_preferences = preference_service.update_preferences(
            user_id=current_user.id, preferences_dict=update_dict
        )

        # Clear cache to ensure fresh data on next request
        preference_service.clear_cache(user_id=current_user.id)

        return _preferences_to_response(updated_preferences)
    except Exception as e:
        logger.exception(f"Error updating notification preferences for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification preferences",
        ) from e
