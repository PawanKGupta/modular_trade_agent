# Notification Preferences API Documentation

**Service:** `NotificationPreferenceService`
**Location:** `services/notification_preference_service.py`
**Phase:** 2 (Notification Preferences Implementation)

## Overview

The `NotificationPreferenceService` provides a centralized interface for managing and checking user notification preferences. It handles preference retrieval, caching, quiet hours checking, and notification decision logic.

## Initialization

```python
from services.notification_preference_service import NotificationPreferenceService
from sqlalchemy.orm import Session

# Initialize with database session
service = NotificationPreferenceService(db_session=db)
```

**Parameters:**
- `db_session` (Session): SQLAlchemy database session

**Features:**
- In-memory caching (5-minute TTL) to reduce database queries
- Automatic cache invalidation on updates
- Thread-safe cache operations

## Methods

### `get_preferences(user_id: int) -> UserNotificationPreferences | None`

Get notification preferences for a user from cache or database.

**Parameters:**
- `user_id` (int): User ID

**Returns:**
- `UserNotificationPreferences | None`: User preferences or None if not found

**Example:**
```python
preferences = service.get_preferences(user_id=1)
if preferences:
    print(f"Telegram enabled: {preferences.telegram_enabled}")
```

### `get_or_create_default_preferences(user_id: int) -> UserNotificationPreferences`

Get existing preferences or create default preferences for a user.

**Parameters:**
- `user_id` (int): User ID

**Returns:**
- `UserNotificationPreferences`: User preferences (existing or newly created)

**Default Values:**
- Most events enabled (`TRUE`)
- Opt-in events disabled (`FALSE`): `ORDER_MODIFIED`, `SYSTEM_WARNING`, `SYSTEM_INFO`
- All channels disabled except `in_app_enabled` (`TRUE`)
- Quiet hours not set (`None`)

**Example:**
```python
preferences = service.get_or_create_default_preferences(user_id=1)
# Always returns preferences (creates if needed)
```

### `update_preferences(user_id: int, preferences_dict: dict) -> UserNotificationPreferences`

Update user notification preferences.

**Parameters:**
- `user_id` (int): User ID
- `preferences_dict` (dict): Dictionary of preference fields to update

**Returns:**
- `UserNotificationPreferences`: Updated preferences

**Example:**
```python
updated = service.update_preferences(
    user_id=1,
    preferences_dict={
        "telegram_enabled": True,
        "telegram_chat_id": "123456789",
        "notify_order_placed": True,
        "notify_order_modified": True,
        "quiet_hours_start": "22:00:00",
        "quiet_hours_end": "08:00:00",
    }
)
```

**Note:** Only provided fields are updated. `None` values clear optional fields (quiet hours, chat IDs, email addresses).

### `should_notify(user_id: int, event_type: str, channel: str = "telegram") -> bool`

Check if a notification should be sent for a specific event type.

**Parameters:**
- `user_id` (int): User ID
- `event_type` (str): Event type (use `NotificationEventType` constants)
- `channel` (str): Notification channel ("telegram", "email", "in_app") - default: "telegram"

**Returns:**
- `bool`: `True` if notification should be sent, `False` otherwise

**Decision Logic:**
1. If no preferences exist → Returns `True` (backward compatibility)
2. Check if channel is enabled → Returns `False` if disabled
3. Check if event type is enabled → Returns `False` if disabled
4. Check quiet hours → Returns `False` if within quiet hours
5. Returns `True` if all checks pass

**Example:**
```python
from services.notification_preference_service import NotificationEventType

should_send = service.should_notify(
    user_id=1,
    event_type=NotificationEventType.ORDER_PLACED,
    channel="telegram"
)

if should_send:
    # Send notification
    pass
```

### `is_quiet_hours(user_id: int) -> bool`

Check if the current time falls within the user's quiet hours.

**Parameters:**
- `user_id` (int): User ID

**Returns:**
- `bool`: `True` if within quiet hours, `False` otherwise

**Quiet Hours Logic:**
- If not set → Returns `False`
- Same day range (e.g., 14:00 - 16:00) → Checks if current time is within range
- Spanning midnight (e.g., 22:00 - 08:00) → Checks if current time is after start OR before end

**Example:**
```python
if service.is_quiet_hours(user_id=1):
    # Suppress notification
    pass
```

### `get_enabled_channels(user_id: int) -> list[str]`

Get list of enabled notification channels for a user.

**Parameters:**
- `user_id` (int): User ID

**Returns:**
- `list[str]`: List of enabled channels (e.g., `["telegram", "in_app"]`)

**Example:**
```python
channels = service.get_enabled_channels(user_id=1)
# Returns: ["telegram", "in_app"] if both are enabled
```

### `clear_cache(user_id: int | None = None) -> None`

Clear preference cache for a specific user or all users.

**Parameters:**
- `user_id` (int | None): User ID to clear cache for, or `None` to clear all

**Example:**
```python
# Clear cache for specific user
service.clear_cache(user_id=1)

# Clear all caches
service.clear_cache()
```

## Event Type Constants

**Class:** `NotificationEventType`

**Order Events:**
- `ORDER_PLACED` - Order placed successfully
- `ORDER_REJECTED` - Order rejected
- `ORDER_EXECUTED` - Order executed
- `ORDER_CANCELLED` - Order cancelled
- `ORDER_MODIFIED` - Order manually modified
- `RETRY_QUEUE_ADDED` - Order added to retry queue
- `RETRY_QUEUE_UPDATED` - Retry queue updated
- `RETRY_QUEUE_REMOVED` - Order removed from retry queue
- `RETRY_QUEUE_RETRIED` - Order retried successfully
- `PARTIAL_FILL` - Partial order fill

**System Events:**
- `SYSTEM_ERROR` - System errors
- `SYSTEM_WARNING` - System warnings
- `SYSTEM_INFO` - System information

**Legacy Events (Backward Compatibility):**
- `SERVICE_EVENT` - Service events
- `TRADING_EVENT` - Trading events
- `SYSTEM_EVENT` - System events
- `ERROR` - Error events

**Usage:**
```python
from services.notification_preference_service import NotificationEventType

# Use constants
event_type = NotificationEventType.ORDER_PLACED

# Get all event types
all_events = NotificationEventType.all_event_types()
```

## Integration with TelegramNotifier

The `TelegramNotifier` automatically uses `NotificationPreferenceService` when initialized with a database session:

```python
from modules.kotak_neo_auto_trader.telegram_notifier import TelegramNotifier

notifier = TelegramNotifier(
    bot_token="your_token",
    chat_id="your_chat_id",
    enabled=True,
    db_session=db  # Enables preference checking
)

# All notification methods check preferences automatically
notifier.notify_order_placed("RELIANCE", "123", 10, user_id=1)
```

**Event Type Mapping:**
- `notify_order_placed()` → `ORDER_PLACED`
- `notify_order_rejection()` → `ORDER_REJECTED`
- `notify_order_execution()` → `ORDER_EXECUTED`
- `notify_order_cancelled()` → `ORDER_CANCELLED`
- `notify_order_modified()` → `ORDER_MODIFIED`
- `notify_partial_fill()` → `PARTIAL_FILL`
- `notify_retry_queue_updated()` → `RETRY_QUEUE_*` (based on action)
- `notify_system_alert()` → `SYSTEM_ERROR/WARNING/INFO` (based on severity)

## Error Handling

**Database Errors:**
- All database operations are wrapped in try-except blocks
- Errors are logged and exceptions are raised
- Cache is not updated on errors

**Missing Preferences:**
- If preferences don't exist, defaults are used (backward compatibility)
- `get_or_create_default_preferences()` creates defaults automatically

**Invalid Event Types:**
- Unknown event types return `False` (notification not sent)
- Legacy event types are mapped to appropriate granular events

## Performance Considerations

**Caching:**
- Preferences are cached in memory for 5 minutes
- Cache is automatically invalidated on updates
- Cache can be manually cleared with `clear_cache()`

**Database Queries:**
- First access: Database query + cache update
- Subsequent access: Cache lookup (no database query)
- After 5 minutes: Cache expires, next access queries database

**Best Practices:**
- Use `get_or_create_default_preferences()` for guaranteed preferences
- Clear cache after bulk updates
- Use `should_notify()` before sending notifications (not after)

## Testing

**Unit Tests:**
- `tests/unit/services/test_notification_preference_service.py` (28 tests)

**Integration Tests:**
- `tests/integration/test_phase3_notification_preferences.py` (16 tests)

**Example Test:**
```python
def test_should_notify_with_preferences():
    service = NotificationPreferenceService(db_session)
    preferences = service.get_or_create_default_preferences(user_id=1)

    # Enable order placed, disable order rejected
    service.update_preferences(user_id=1, preferences_dict={
        "notify_order_placed": True,
        "notify_order_rejected": False,
    })

    assert service.should_notify(1, NotificationEventType.ORDER_PLACED) is True
    assert service.should_notify(1, NotificationEventType.ORDER_REJECTED) is False
```

## See Also

- [User Guide - Notification Preferences](../USER_GUIDE.md#notification-preferences)
- [Architecture - Notification System](../ARCHITECTURE.md#6-notification-system)
- [Migration Guide](../ARCHITECTURE.md#notification-preferences-migration)
