"""
Notification Preference Service

Service for managing and checking user notification preferences.
Phase 2: Notification Preferences Implementation

This service provides:
- Getting user notification preferences
- Checking if notifications should be sent for specific events
- Checking quiet hours
- Getting enabled notification channels
"""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.infrastructure.db.models import UserNotificationPreferences
from utils.logger import logger


class NotificationEventType:
    """Notification event type constants"""

    # Order events
    ORDER_PLACED = "order_placed"
    ORDER_REJECTED = "order_rejected"
    ORDER_EXECUTED = "order_executed"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_MODIFIED = "order_modified"
    ORDER_SKIPPED = "order_skipped"
    RETRY_QUEUE_ADDED = "retry_queue_added"
    RETRY_QUEUE_UPDATED = "retry_queue_updated"
    RETRY_QUEUE_REMOVED = "retry_queue_removed"
    RETRY_QUEUE_RETRIED = "retry_queue_retried"
    PARTIAL_FILL = "partial_fill"

    # System events
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_INFO = "system_info"

    # Service events (granular)
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    SERVICE_EXECUTION_COMPLETED = "service_execution_completed"

    # Legacy event types (for backward compatibility)
    SERVICE_EVENT = "service_event"
    TRADING_EVENT = "trading_event"
    SYSTEM_EVENT = "system_event"
    ERROR = "error"

    @classmethod
    def all_event_types(cls) -> list[str]:
        """Get all event type constants"""
        return [
            cls.ORDER_PLACED,
            cls.ORDER_REJECTED,
            cls.ORDER_EXECUTED,
            cls.ORDER_CANCELLED,
            cls.ORDER_MODIFIED,
            cls.ORDER_SKIPPED,
            cls.RETRY_QUEUE_ADDED,
            cls.RETRY_QUEUE_UPDATED,
            cls.RETRY_QUEUE_REMOVED,
            cls.RETRY_QUEUE_RETRIED,
            cls.PARTIAL_FILL,
            cls.SYSTEM_ERROR,
            cls.SYSTEM_WARNING,
            cls.SYSTEM_INFO,
            cls.SERVICE_STARTED,
            cls.SERVICE_STOPPED,
            cls.SERVICE_EXECUTION_COMPLETED,
            cls.SERVICE_EVENT,  # Legacy
        ]


class NotificationPreferenceService:
    """
    Service for managing and checking user notification preferences.

    Provides methods to:
    - Get user notification preferences
    - Check if notifications should be sent for specific events
    - Check quiet hours
    - Get enabled notification channels
    - Update preferences
    """

    def __init__(self, db_session: Session):
        """
        Initialize notification preference service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self._preference_cache: dict[int, UserNotificationPreferences] = {}
        self._cache_ttl_seconds = 300  # 5 minutes cache TTL

    def get_preferences(self, user_id: int) -> UserNotificationPreferences | None:
        """
        Get notification preferences for a user.

        Args:
            user_id: User ID

        Returns:
            UserNotificationPreferences object or None if not found
        """
        # Check cache first
        if user_id in self._preference_cache:
            cached = self._preference_cache[user_id]
            # Cache is valid (we'll implement TTL if needed)
            return cached

        # Query database
        preferences = (
            self.db.query(UserNotificationPreferences)
            .filter(UserNotificationPreferences.user_id == user_id)
            .first()
        )

        # Cache result
        if preferences:
            self._preference_cache[user_id] = preferences

        return preferences

    def get_or_create_default_preferences(self, user_id: int) -> UserNotificationPreferences:
        """
        Get notification preferences for a user, creating default if not exists.

        Args:
            user_id: User ID

        Returns:
            UserNotificationPreferences object (always returns a value)
        """
        preferences = self.get_preferences(user_id)

        if preferences is None:
            # Create default preferences
            preferences = UserNotificationPreferences(
                user_id=user_id,
                # Channels default to False (user must enable)
                telegram_enabled=False,
                email_enabled=False,
                in_app_enabled=True,  # In-app enabled by default
                # Legacy types default to True (backward compatibility)
                notify_service_events=True,
                notify_trading_events=True,
                notify_system_events=True,
                notify_errors=True,
                # Granular preferences default to True (maintain current behavior)
                notify_order_placed=True,
                notify_order_rejected=True,
                notify_order_executed=True,
                notify_order_cancelled=True,
                notify_order_modified=False,  # New event, opt-in
                notify_retry_queue_added=True,
                notify_retry_queue_updated=True,
                notify_retry_queue_removed=True,
                notify_retry_queue_retried=True,
                notify_partial_fill=True,
                notify_system_errors=True,
                notify_system_warnings=False,  # Reduce noise
                notify_system_info=False,  # Reduce noise
                # Granular service event preferences
                notify_service_started=True,
                notify_service_stopped=True,
                notify_service_execution_completed=True,
            )
            self.db.add(preferences)
            try:
                self.db.commit()
                self.db.refresh(preferences)
                # Cache the new preferences
                self._preference_cache[user_id] = preferences
                logger.info(f"Created default notification preferences for user {user_id}")
            except Exception as e:
                self.db.rollback()
                logger.error(
                    f"Failed to create default notification preferences for user {user_id}: {e}"
                )
                raise

        return preferences

    def update_preferences(
        self, user_id: int, preferences_dict: dict[str, Any]
    ) -> UserNotificationPreferences:
        """
        Update notification preferences for a user.

        Args:
            user_id: User ID
            preferences_dict: Dictionary of preference fields to update

        Returns:
            Updated UserNotificationPreferences object
        """
        preferences = self.get_or_create_default_preferences(user_id)

        # Update fields from dictionary
        for key, value in preferences_dict.items():
            if hasattr(preferences, key):
                # Handle None values - they should clear optional fields
                # For time fields, None is valid (clears quiet hours)
                # For boolean fields, None should not be set (keep existing value)
                if value is None:
                    # Only allow None for optional fields (time, string fields)
                    if key in (
                        "quiet_hours_start",
                        "quiet_hours_end",
                        "telegram_chat_id",
                        "email_address",
                    ):
                        setattr(preferences, key, value)
                    # For boolean fields, skip None (don't update)
                else:
                    setattr(preferences, key, value)
            else:
                logger.warning(f"Unknown preference field: {key}")

        try:
            self.db.commit()
            self.db.refresh(preferences)
            # Update cache
            self._preference_cache[user_id] = preferences
            logger.info(f"Updated notification preferences for user {user_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update notification preferences for user {user_id}: {e}")
            raise

        return preferences

    def should_notify(self, user_id: int, event_type: str, channel: str = "telegram") -> bool:
        """
        Check if a notification should be sent for a specific event type.

        Args:
            user_id: User ID
            event_type: Event type (from NotificationEventType constants)
            channel: Notification channel ("telegram", "email", "in_app")

        Returns:
            True if notification should be sent, False otherwise
        """
        preferences = self.get_preferences(user_id)

        # If no preferences exist, use defaults (all enabled for backward compatibility)
        if preferences is None:
            logger.debug(f"No preferences found for user {user_id}, using defaults (all enabled)")
            return True

        # Check channel is enabled
        channel_enabled = self._is_channel_enabled(preferences, channel)
        if not channel_enabled:
            logger.debug(f"Channel {channel} not enabled for user {user_id}")
            return False

        # Check quiet hours
        if self.is_quiet_hours(user_id):
            logger.debug(f"Quiet hours active for user {user_id}, skipping notification")
            return False

        # Check event-specific preference
        event_enabled = self._is_event_enabled(preferences, event_type)
        if not event_enabled:
            logger.debug(f"Event {event_type} not enabled for user {user_id}")
            return False

        return True

    def _is_channel_enabled(self, preferences: UserNotificationPreferences, channel: str) -> bool:
        """Check if a notification channel is enabled"""
        channel_map = {
            "telegram": preferences.telegram_enabled,
            "email": preferences.email_enabled,
            "in_app": preferences.in_app_enabled,
        }
        return channel_map.get(channel, False)

    def _is_event_enabled(self, preferences: UserNotificationPreferences, event_type: str) -> bool:
        """Check if a specific event type is enabled"""
        # Map event types to preference fields
        event_map = {
            NotificationEventType.ORDER_PLACED: preferences.notify_order_placed,
            NotificationEventType.ORDER_REJECTED: preferences.notify_order_rejected,
            NotificationEventType.ORDER_EXECUTED: preferences.notify_order_executed,
            NotificationEventType.ORDER_CANCELLED: preferences.notify_order_cancelled,
            NotificationEventType.ORDER_MODIFIED: preferences.notify_order_modified,
            # ORDER_SKIPPED: Map to notify_trading_events for now (until dedicated field is added)
            NotificationEventType.ORDER_SKIPPED: preferences.notify_trading_events,
            NotificationEventType.RETRY_QUEUE_ADDED: preferences.notify_retry_queue_added,
            NotificationEventType.RETRY_QUEUE_UPDATED: preferences.notify_retry_queue_updated,
            NotificationEventType.RETRY_QUEUE_REMOVED: preferences.notify_retry_queue_removed,
            NotificationEventType.RETRY_QUEUE_RETRIED: preferences.notify_retry_queue_retried,
            NotificationEventType.PARTIAL_FILL: preferences.notify_partial_fill,
            NotificationEventType.SYSTEM_ERROR: preferences.notify_system_errors,
            NotificationEventType.SYSTEM_WARNING: preferences.notify_system_warnings,
            NotificationEventType.SYSTEM_INFO: preferences.notify_system_info,
            # Granular service event types
            NotificationEventType.SERVICE_STARTED: preferences.notify_service_started,
            NotificationEventType.SERVICE_STOPPED: preferences.notify_service_stopped,
            NotificationEventType.SERVICE_EXECUTION_COMPLETED: preferences.notify_service_execution_completed,
            # Legacy event types (for backward compatibility)
            NotificationEventType.SERVICE_EVENT: preferences.notify_service_events,
            NotificationEventType.TRADING_EVENT: preferences.notify_trading_events,
            NotificationEventType.SYSTEM_EVENT: preferences.notify_system_events,
            NotificationEventType.ERROR: preferences.notify_errors,
        }

        if event_type in event_map:
            return event_map[event_type]

        # Unknown event type - default to enabled for backward compatibility
        logger.warning(f"Unknown event type: {event_type}, defaulting to enabled")
        return True

    def is_quiet_hours(self, user_id: int) -> bool:
        """
        Check if current time is within quiet hours for a user.

        Args:
            user_id: User ID

        Returns:
            True if currently in quiet hours, False otherwise
        """
        preferences = self.get_preferences(user_id)

        # If no preferences or no quiet hours set, not in quiet hours
        if (
            preferences is None
            or preferences.quiet_hours_start is None
            or preferences.quiet_hours_end is None
        ):
            return False

        now = datetime.now().time()
        start = preferences.quiet_hours_start
        end = preferences.quiet_hours_end

        # Handle quiet hours that span midnight (e.g., 22:00 - 08:00)
        if start <= end:
            # Normal case: quiet hours within same day (e.g., 22:00 - 23:00)
            return start <= now <= end
        else:
            # Quiet hours span midnight (e.g., 22:00 - 08:00)
            return now >= start or now <= end

    def get_enabled_channels(self, user_id: int) -> list[str]:
        """
        Get list of enabled notification channels for a user.

        Args:
            user_id: User ID

        Returns:
            List of enabled channel names (e.g., ["telegram", "in_app"])
        """
        preferences = self.get_preferences(user_id)

        if preferences is None:
            # Default: only in-app enabled
            return ["in_app"]

        enabled = []
        if preferences.telegram_enabled:
            enabled.append("telegram")
        if preferences.email_enabled:
            enabled.append("email")
        if preferences.in_app_enabled:
            enabled.append("in_app")

        return enabled

    def clear_cache(self, user_id: int | None = None) -> None:
        """
        Clear preference cache for a user or all users.

        Args:
            user_id: User ID to clear cache for, or None to clear all
        """
        if user_id is None:
            self._preference_cache.clear()
            logger.debug("Cleared all notification preference cache")
        else:
            self._preference_cache.pop(user_id, None)
            logger.debug(f"Cleared notification preference cache for user {user_id}")
