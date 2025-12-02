"""
Schemas for Notification Preferences API

Phase 5: Notification Preferences Implementation
"""

from datetime import time

from pydantic import BaseModel, Field


class NotificationPreferencesResponse(BaseModel):
    """Response schema for notification preferences"""

    # Notification channels
    telegram_enabled: bool = Field(default=False, description="Enable Telegram notifications")
    telegram_bot_token: str | None = Field(default=None, description="Telegram bot token")
    telegram_chat_id: str | None = Field(default=None, description="Telegram chat ID")
    email_enabled: bool = Field(default=False, description="Enable email notifications")
    email_address: str | None = Field(default=None, description="Email address")
    in_app_enabled: bool = Field(default=True, description="Enable in-app notifications")

    # Legacy notification types (kept for backward compatibility)
    notify_service_events: bool = Field(default=True, description="Notify on service events")
    notify_trading_events: bool = Field(default=True, description="Notify on trading events")
    notify_system_events: bool = Field(default=True, description="Notify on system events")
    notify_errors: bool = Field(default=True, description="Notify on errors")

    # Granular order event preferences
    notify_order_placed: bool = Field(default=True, description="Notify when order is placed")
    notify_order_rejected: bool = Field(default=True, description="Notify when order is rejected")
    notify_order_executed: bool = Field(default=True, description="Notify when order is executed")
    notify_order_cancelled: bool = Field(default=True, description="Notify when order is cancelled")
    notify_order_modified: bool = Field(
        default=False, description="Notify when order is manually modified (opt-in)"
    )
    notify_retry_queue_added: bool = Field(
        default=True, description="Notify when order added to retry queue"
    )
    notify_retry_queue_updated: bool = Field(
        default=True, description="Notify when retry queue is updated"
    )
    notify_retry_queue_removed: bool = Field(
        default=True, description="Notify when order removed from retry queue"
    )
    notify_retry_queue_retried: bool = Field(
        default=True, description="Notify when order is retried"
    )
    notify_partial_fill: bool = Field(default=True, description="Notify on partial order fill")

    # System event preferences
    notify_system_errors: bool = Field(default=True, description="Notify on system errors")
    notify_system_warnings: bool = Field(
        default=False, description="Notify on system warnings (opt-in)"
    )
    notify_system_info: bool = Field(default=False, description="Notify on system info (opt-in)")

    # Granular service event preferences
    notify_service_started: bool = Field(
        default=True, description="Notify when a service is started"
    )
    notify_service_stopped: bool = Field(
        default=True, description="Notify when a service is stopped"
    )
    notify_service_execution_completed: bool = Field(
        default=True, description="Notify when a service execution completes"
    )

    # Quiet hours
    quiet_hours_start: time | None = Field(
        default=None, description="Start time for quiet hours (HH:MM format)"
    )
    quiet_hours_end: time | None = Field(
        default=None, description="End time for quiet hours (HH:MM format)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "telegram_enabled": True,
                "telegram_chat_id": "123456789",
                "email_enabled": False,
                "in_app_enabled": True,
                "notify_order_placed": True,
                "notify_order_rejected": True,
                "notify_order_executed": True,
                "notify_order_cancelled": True,
                "notify_order_modified": False,
                "notify_retry_queue_added": True,
                "notify_retry_queue_updated": True,
                "notify_retry_queue_removed": True,
                "notify_retry_queue_retried": True,
                "notify_partial_fill": True,
                "notify_system_errors": True,
                "notify_system_warnings": False,
                "notify_system_info": False,
                "quiet_hours_start": "22:00:00",
                "quiet_hours_end": "08:00:00",
            }
        }


class NotificationPreferencesUpdate(BaseModel):
    """Request schema for updating notification preferences"""

    # Notification channels
    telegram_enabled: bool | None = Field(default=None, description="Enable Telegram notifications")
    telegram_bot_token: str | None = Field(default=None, description="Telegram bot token")
    telegram_chat_id: str | None = Field(default=None, description="Telegram chat ID")
    email_enabled: bool | None = Field(default=None, description="Enable email notifications")
    email_address: str | None = Field(default=None, description="Email address")
    in_app_enabled: bool | None = Field(default=None, description="Enable in-app notifications")

    # Legacy notification types
    notify_service_events: bool | None = Field(default=None, description="Notify on service events")
    notify_trading_events: bool | None = Field(default=None, description="Notify on trading events")
    notify_system_events: bool | None = Field(default=None, description="Notify on system events")
    notify_errors: bool | None = Field(default=None, description="Notify on errors")

    # Granular order event preferences
    notify_order_placed: bool | None = Field(
        default=None, description="Notify when order is placed"
    )
    notify_order_rejected: bool | None = Field(
        default=None, description="Notify when order is rejected"
    )
    notify_order_executed: bool | None = Field(
        default=None, description="Notify when order is executed"
    )
    notify_order_cancelled: bool | None = Field(
        default=None, description="Notify when order is cancelled"
    )
    notify_order_modified: bool | None = Field(
        default=None, description="Notify when order is manually modified"
    )
    notify_retry_queue_added: bool | None = Field(
        default=None, description="Notify when order added to retry queue"
    )
    notify_retry_queue_updated: bool | None = Field(
        default=None, description="Notify when retry queue is updated"
    )
    notify_retry_queue_removed: bool | None = Field(
        default=None, description="Notify when order removed from retry queue"
    )
    notify_retry_queue_retried: bool | None = Field(
        default=None, description="Notify when order is retried"
    )
    notify_partial_fill: bool | None = Field(
        default=None, description="Notify on partial order fill"
    )

    # System event preferences
    notify_system_errors: bool | None = Field(default=None, description="Notify on system errors")
    notify_system_warnings: bool | None = Field(
        default=None, description="Notify on system warnings"
    )
    notify_system_info: bool | None = Field(default=None, description="Notify on system info")

    # Granular service event preferences
    notify_service_started: bool | None = Field(
        default=None, description="Notify when a service is started"
    )
    notify_service_stopped: bool | None = Field(
        default=None, description="Notify when a service is stopped"
    )
    notify_service_execution_completed: bool | None = Field(
        default=None, description="Notify when a service execution completes"
    )

    # Quiet hours
    quiet_hours_start: time | None = Field(
        default=None, description="Start time for quiet hours (HH:MM format)"
    )
    quiet_hours_end: time | None = Field(
        default=None, description="End time for quiet hours (HH:MM format)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "telegram_enabled": True,
                "notify_order_placed": True,
                "notify_order_modified": True,
                "notify_system_warnings": False,
                "quiet_hours_start": "22:00:00",
                "quiet_hours_end": "08:00:00",
            }
        }
