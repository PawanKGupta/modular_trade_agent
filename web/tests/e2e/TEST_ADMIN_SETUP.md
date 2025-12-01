# Test Admin User Setup

## Problem

E2E tests require a specific admin user (`testadmin@rebound.com`) to authenticate, but the API server might not have this user in the database.

## Solution

The test runner script now automatically ensures the test admin user exists:

1. **Auto-creates** test admin user if it doesn't exist
2. **Verifies** the user exists before running tests
3. **Matches** test configuration (`test-config.ts`)

## Test Admin Credentials

**Default credentials** (matches `test-config.ts`):
- **Email**: `testadmin@rebound.com`
- **Password**: `testadmin@123`
- **Role**: `admin`

**Customization**: You can override with environment variables:
```powershell
$env:TEST_ADMIN_EMAIL="custom@example.com"
$env:TEST_ADMIN_PASSWORD="CustomPassword123"
```

## How It Works

### Automatic (Recommended)

When you run the test runner script:
```powershell
.\run-e2e-tests.ps1
```

The script will:
1. Start API server with test admin credentials configured
2. After API server starts, run `ensure-test-admin.py` script
3. Script checks if `testadmin@rebound.com` exists
4. Creates the user if it doesn't exist
5. Ensures user has admin role and settings

### Manual Setup

If you need to ensure the test admin user exists manually:

```powershell
# From project root
python web/tests/e2e/utils/ensure-test-admin.py
```

Or with custom credentials:
```powershell
$env:TEST_ADMIN_EMAIL="testadmin@rebound.com"
$env:TEST_ADMIN_PASSWORD="testadmin@123"
python web/tests/e2e/utils/ensure-test-admin.py
```

## What the Script Does

The `ensure-test-admin.py` script:

1. ✅ Connects to `e2e.db` database
2. ✅ Checks if `testadmin@rebound.com` exists
3. ✅ Creates user if missing
4. ✅ Ensures user has admin role
5. ✅ Ensures user is active
6. ✅ Creates default settings for the user

## Troubleshooting

### Issue: "User does not exist" error in tests

**Cause**: Test admin user not created in database

**Solution**:
```powershell
# Run the ensure script manually
python web/tests/e2e/utils/ensure-test-admin.py

# Or use the test runner script which does it automatically
.\run-e2e-tests.ps1
```

### Issue: "Authentication failed"

**Cause**: Wrong credentials or user not admin

**Check**:
1. Verify credentials match `test-config.ts`
2. Verify user exists: `python web/tests/e2e/utils/ensure-test-admin.py`
3. Check user role is admin

### Issue: "Permission denied" errors

**Cause**: User exists but doesn't have admin role

**Solution**: The ensure script automatically fixes this:
```powershell
python web/tests/e2e/utils/ensure-test-admin.py
```

## Database Considerations

- **Test database**: `e2e.db` (used by E2E tests)
- **Script creates user in**: `e2e.db`
- **API server must use**: `e2e.db` (configured by test runner script)

If your API server is using `app.db` instead of `e2e.db`, the test admin user won't be found. Use the test runner script to ensure correct database configuration.

## Summary

✅ **Test runner script automatically handles this** - just run `.\run-e2e-tests.ps1`

✅ **Manual setup available** - run `ensure-test-admin.py` if needed

✅ **Credentials match test config** - `testadmin@rebound.com` / `testadmin@123`

✅ **Works with both scenarios** - new database or existing database
