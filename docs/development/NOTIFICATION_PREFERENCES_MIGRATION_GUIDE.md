# Notification Preferences Migration Guide

**Date:** 2025-11-30
**Version:** 1.0
**Status:** Complete

## Overview

This guide documents the migration to the new Notification Preferences system, including database schema changes, API changes, and code migration steps.

## What Changed

### Database Schema

**Migration:** `alembic/versions/53c66ed1105b_add_granular_notification_preferences.py`

**New Columns Added to `user_notification_preferences`:**

1. **Order Event Preferences** (10 columns):
   - `notify_order_placed` (default: `TRUE`)
   - `notify_order_rejected` (default: `TRUE`)
   - `notify_order_executed` (default: `TRUE`)
   - `notify_order_cancelled` (default: `TRUE`)
   - `notify_order_modified` (default: `FALSE` - opt-in)
   - `notify_retry_queue_added` (default: `TRUE`)
   - `notify_retry_queue_updated` (default: `TRUE`)
   - `notify_retry_queue_removed` (default: `TRUE`)
   - `notify_retry_queue_retried` (default: `TRUE`)
   - `notify_partial_fill` (default: `TRUE`)

2. **System Event Preferences** (3 columns):
   - `notify_system_errors` (default: `TRUE`)
   - `notify_system_warnings` (default: `FALSE` - opt-in)
   - `notify_system_info` (default: `FALSE` - opt-in)

**Total:** 13 new columns

### API Changes

**New Endpoints:**
- `GET /api/v1/user/notification-preferences` - Get user preferences
- `PUT /api/v1/user/notification-preferences` - Update user preferences

**New Schemas:**
- `NotificationPreferencesResponse` - Response model
- `NotificationPreferencesUpdate` - Request model

### Code Changes

**New Service:**
- `NotificationPreferenceService` - Centralized preference management

**Updated Components:**
- `TelegramNotifier` - Now checks preferences before sending
- `AutoTradeEngine` - Passes `user_id` to notifications
- `UnifiedOrderMonitor` - Passes `user_id` to notifications
- `OrderStateManager` - Passes `user_id` and detects modifications

## Migration Steps

### Step 1: Database Migration

**Run Alembic Migration:**

```bash
# Check current revision
alembic current

# Upgrade to latest
alembic upgrade head

# Verify migration
alembic current
# Should show: 53c66ed1105b (head)
```

**What Happens:**
- 13 new columns are added to `user_notification_preferences` table
- All existing users get default preferences (backward compatible)
- No data loss - all existing preferences are preserved

**Rollback (if needed):**
```bash
alembic downgrade -1
```

### Step 2: Code Updates

**No Breaking Changes Required:**

The implementation is backward compatible. Existing code continues to work:

```python
# Old code (still works)
notifier.notify_order_placed("RELIANCE", "123", 10)
# Notification is sent (no user_id = legacy behavior)

# New code (with preferences)
notifier.notify_order_placed("RELIANCE", "123", 10, user_id=1)
# Notification respects user preferences
```

**Optional: Update to Use Preferences**

If you want to enable preference checking:

1. **Pass `user_id` to notification methods:**
   ```python
   # Before
   telegram_notifier.notify_order_placed(symbol, order_id, quantity)

   # After
   telegram_notifier.notify_order_placed(symbol, order_id, quantity, user_id=self.user_id)
   ```

2. **Initialize TelegramNotifier with db_session:**
   ```python
   # Before
   notifier = TelegramNotifier(bot_token=token, chat_id=chat_id, enabled=True)

   # After
   notifier = TelegramNotifier(
       bot_token=token,
       chat_id=chat_id,
       enabled=True,
       db_session=db  # Enables preference checking
   )
   ```

### Step 3: Frontend Updates

**New Page:**
- Navigate to `/dashboard/notification-preferences` to configure preferences

**No Changes Required:**
- Existing pages continue to work
- New preferences page is optional

## Backward Compatibility

### Default Behavior

**If preferences don't exist:**
- All notifications are sent (current behavior)
- No breaking changes

**If `user_id` is not provided:**
- Notifications are sent (legacy behavior)
- Preference checking is skipped

**Default Preferences:**
- Most events enabled (`TRUE`)
- Opt-in events disabled (`FALSE`): `ORDER_MODIFIED`, `SYSTEM_WARNING`, `SYSTEM_INFO`
- All channels disabled except `in_app_enabled` (`TRUE`)

### Legacy Event Types

The system supports legacy event types for backward compatibility:

- `SERVICE_EVENT` → Maps to service-related events
- `TRADING_EVENT` → Maps to trading-related events
- `SYSTEM_EVENT` → Maps to system events
- `ERROR` → Maps to error events

## Breaking Changes

**None** - All changes are additive and backward compatible.

## Testing After Migration

### 1. Verify Database Migration

```sql
-- Check columns exist
PRAGMA table_info(user_notification_preferences);

-- Should show 13 new columns
```

### 2. Test Default Preferences

```python
from services.notification_preference_service import NotificationPreferenceService

service = NotificationPreferenceService(db_session)
prefs = service.get_or_create_default_preferences(user_id=1)

# Verify defaults
assert prefs.notify_order_placed is True
assert prefs.notify_order_modified is False  # Opt-in
```

### 3. Test API Endpoints

```bash
# Get preferences
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/user/notification-preferences

# Update preferences
curl -X PUT \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"telegram_enabled": true}' \
  http://localhost:8000/api/v1/user/notification-preferences
```

### 4. Test Notification Flow

1. Configure preferences via UI
2. Trigger a notification event
3. Verify notification respects preferences

## Troubleshooting

### Migration Fails

**Error:** `duplicate column name: notify_order_placed`

**Solution:** Column already exists. Check if migration was partially applied:
```bash
alembic current
alembic history
```

### Preferences Not Working

**Check:**
1. Is `user_id` being passed to notification methods?
2. Is `db_session` provided to `TelegramNotifier`?
3. Are preferences saved in database?
4. Check logs for preference service errors

### Notifications Not Sent

**Check:**
1. Are preferences enabled for the event type?
2. Is the channel enabled?
3. Are quiet hours active?
4. Check `should_notify()` return value

## Rollback Plan

If you need to rollback:

1. **Database Rollback:**
   ```bash
   alembic downgrade -1
   ```

2. **Code Rollback:**
   - Remove `user_id` parameters from notification calls
   - Remove `db_session` from `TelegramNotifier` initialization
   - Code will work in legacy mode (all notifications sent)

3. **Frontend Rollback:**
   - Remove notification preferences page (optional)
   - No other changes needed

## Post-Migration Checklist

- [ ] Database migration completed successfully
- [ ] All existing users have default preferences
- [ ] API endpoints are accessible
- [ ] Frontend page loads correctly
- [ ] Notifications respect preferences
- [ ] Quiet hours work correctly
- [ ] Multi-user isolation works
- [ ] Tests pass

## Support

For issues or questions:
1. Check logs: `logs/server_api.log`
2. Review test files for examples
3. See API documentation: `docs/NOTIFICATION_PREFERENCES_API.md`
4. See architecture docs: `docs/ARCHITECTURE.md`

## See Also

- [Notification Preferences API Documentation](NOTIFICATION_PREFERENCES_API.md)
- [User Guide - Notification Preferences](USER_GUIDE.md#notification-preferences)
- [Architecture - Notification System](ARCHITECTURE.md#6-notification-system)
- [Implementation Plan](NOTIFICATION_PREFERENCES_IMPLEMENTATION_PLAN.md)
