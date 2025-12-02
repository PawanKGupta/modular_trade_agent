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


def _test_telegram_connection(bot_token: str, chat_id: str) -> tuple[bool, str]:
    """
    Test Telegram bot connection by sending a test message.
    
    Args:
        bot_token: Telegram bot token
        chat_id: Telegram chat ID
        
    Returns:
        tuple[bool, str]: (success, message)
    """
    try:
        import requests
        
        # Validate inputs
        if not bot_token or not chat_id:
            return False, "Bot token and chat ID are required"
        
        # Test by sending a message
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "✅ Telegram connection test successful!\n\nYour bot is configured correctly.",
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True, "Test message sent successfully! Check your Telegram chat."
        else:
            error_data = response.json()
            error_desc = error_data.get("description", "Unknown error")
            
            # Provide helpful error messages
            if "bot token" in error_desc.lower() or "unauthorized" in error_desc.lower():
                return False, f"Invalid bot token. Please check your token. Error: {error_desc}"
            elif "chat not found" in error_desc.lower():
                return False, f"Invalid chat ID. Make sure you've started a chat with the bot. Error: {error_desc}"
            else:
                return False, f"Telegram API error: {error_desc}"
                
    except requests.exceptions.Timeout:
        return False, "Connection timeout. Please check your internet connection."
    except requests.exceptions.RequestException as e:
        return False, f"Network error: {str(e)}"
    except Exception as e:
        logger.error(f"Telegram test error: {e}", exc_info=True)
        return False, f"Test failed: {str(e)}"


def _preferences_to_response(prefs: UserNotificationPreferences) -> NotificationPreferencesResponse:
    """Convert UserNotificationPreferences model to response schema"""
    return NotificationPreferencesResponse(
        telegram_enabled=prefs.telegram_enabled,
        telegram_bot_token=prefs.telegram_bot_token,
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
        notify_service_started=prefs.notify_service_started,
        notify_service_stopped=prefs.notify_service_stopped,
        notify_service_execution_completed=prefs.notify_service_execution_completed,
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


@router.post("/notification-preferences/telegram/test")
def test_telegram_connection(
    bot_token: str,
    chat_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Test Telegram bot connection by sending a test message.
    
    Args:
        bot_token: Telegram bot token
        chat_id: Telegram chat ID
        
    Returns:
        {"success": bool, "message": str}
    """
    try:
        success, message = _test_telegram_connection(bot_token, chat_id)
        return {"success": success, "message": message}
    except Exception as e:
        logger.exception(f"Error testing Telegram connection for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test Telegram connection: {str(e)}",
        ) from e
