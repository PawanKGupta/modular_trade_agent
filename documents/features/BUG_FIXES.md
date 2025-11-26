## Bug #77: New Users Missing Default Settings - Service Start Fails (HIGH)

**Date Fixed**: November 27, 2025
**Status**: ✅ Fixed

### Description
When an admin created a new user through the admin panel, the user could not start the unified trading service. The service failed with error:
```
ValueError: User settings not found for user_id=X
```

The user had to manually navigate to the Settings page and click "Save" (even with default values) before they could start the service. This created a poor user experience and confusion.

### Steps to Reproduce
1. Admin logs in
2. Admin creates a new user via Admin Panel
3. New user logs in
4. New user navigates to Service Status page
5. New user clicks "Start" on unified service
6. **ERROR**: "User settings not found for user_id=X"
7. User navigates to Settings page
8. User clicks "Save" (no changes needed)
9. Now service starts successfully

### Root Cause
The admin user creation endpoint (`POST /api/v1/admin/users`) was not creating the default `UserSettings` record. The `UserSettings` table is required by the trading service to determine:
- Trade mode (paper vs. broker)
- Broker configuration
- Encrypted credentials

Meanwhile, the signup flow (`POST /api/v1/auth/signup`) **was** correctly creating default settings via `SettingsRepository.ensure_default()`.

This inconsistency meant:
- ✅ Users who signed up themselves: Had default settings, service worked
- ❌ Users created by admin: No default settings, service failed

### Fix Applied

**File Modified**: `server/app/routers/admin.py`

Added `SettingsRepository.ensure_default()` call to admin user creation:

```python
@router.post("/users", response_model=AdminUserResponse)
def create_user(payload: AdminUserCreate, db: Session = Depends(get_db)):
    from src.infrastructure.persistence.settings_repository import SettingsRepository

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
```

### Test Coverage

**File Added**: `tests/server/test_admin_user_creation_with_settings.py`

Three comprehensive tests:
1. **`test_admin_create_user_creates_default_settings`**: Verifies admin-created users have UserSettings
2. **`test_signup_also_creates_default_settings`**: Regression test for signup flow
3. **`test_service_can_find_settings_for_new_user`**: Simulates the actual service startup scenario

All tests pass ✅

### Impact
- ✅ Admin-created users can immediately start trading service
- ✅ No manual "Save Settings" step required
- ✅ Consistent behavior between signup and admin creation
- ✅ Better user experience
- ✅ Reduced support requests

### Related Components
- `UserSettings` table (required for service)
- `UserTradingConfig` table (optional, for strategy config)
- `SettingsRepository.ensure_default()` - creates default UserSettings
- `MultiUserTradingService.start_service()` - requires UserSettings

### Before/After

**Before Fix:**
```
Admin creates user → User logs in → Start service → ERROR ❌
→ User must go to Settings → Click Save → Start service → Success ✅
```

**After Fix:**
```
Admin creates user → User logs in → Start service → Success ✅
```

---
