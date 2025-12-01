# Test Cleanup Guide

This guide explains the test cleanup strategy for E2E tests.

## 🧹 Cleanup Strategy

### Overview

E2E tests create data during execution (users, configurations, notifications, etc.). To ensure tests are independent and don't interfere with each other, we need to clean up this data.

### Cleanup Levels

1. **Per-Test Cleanup** (Recommended)
   - Clean up data after each test
   - Ensures test isolation
   - Uses `testDataTracker` fixture

2. **Per-Suite Cleanup**
   - Clean up data after each test suite
   - Uses `afterEach` or `afterAll` hooks

3. **Global Cleanup**
   - Clean up data after all tests
   - Uses `global-teardown.ts`

## 📋 What Gets Cleaned Up

### ⚠️ IMPORTANT: Only Test Data is Cleaned

**The cleanup system ONLY removes data that was:**
1. **Explicitly tracked** during the test
2. **Matches test patterns** (e.g., test emails)
3. **Has original values saved** (for configs)

**Protected Data (Never Cleaned):**
- Admin users
- System users
- Existing production data
- Data not explicitly tracked

### 1. Test Users
- **ONLY** users created during signup tests
- **ONLY** if email matches test patterns (e.g., `test*@rebound.com`)
- Tracked via `testDataTracker.trackUser(email)`
- Automatically deleted after test
- **Protected**: Admin/system emails are never deleted

### 2. Trading Configuration
- **ONLY** if original value was saved before modification
- Tracked via `testDataTracker.trackConfig(page, 'trading-config')`
- **Saves original value** before modification
- Automatically reset to **original values** (not defaults) after test
- **Safe**: Only resets if you explicitly tracked it

### 3. Notification Preferences
- **ONLY** if original value was saved before modification
- Tracked via `testDataTracker.trackConfig(page, 'notification-preferences')`
- **Saves original value** before modification
- Automatically reset to **original values** (not defaults) after test
- **Safe**: Only resets if you explicitly tracked it

### 4. Notifications
- **ONLY** notifications explicitly tracked via `trackNotificationId()`
- Not automatically cleaned up (must be tracked)
- **Safe**: Only cleans up tracked notifications

### 5. Browser Storage
- localStorage, sessionStorage, cookies
- Cleared per test (safe - only affects test browser context)

## 🚀 Usage

### Using TestDataTracker Fixture

The `testDataTracker` fixture is automatically available in all tests:

```typescript
import { test, expect } from './fixtures/test-fixtures';

test('my test', async ({ testDataTracker, page }) => {
  // Track a user for cleanup
  const email = 'test@example.com';
  testDataTracker.trackUser(email);

  // Create user...

  // User will be automatically cleaned up after test
});
```

### Tracking Config Changes

```typescript
test('update config', async ({ testDataTracker, authenticatedPage }) => {
  // IMPORTANT: Track config BEFORE modifying (saves original)
  await testDataTracker.trackConfig(authenticatedPage, 'trading-config');

  // Now modify config...

  // Config will be automatically reset to ORIGINAL values after test
});
```

### Manual Cleanup

If you need manual cleanup:

```typescript
import { cleanupTestUser, resetTradingConfig } from './utils/test-cleanup';

test('my test', async ({ page }) => {
  // Create test data...

  // Clean up manually
  await cleanupTestUser(page, 'test@example.com');
  await resetTradingConfig(page);
});
```

## 🔧 Cleanup Utilities

### Available Functions

- `cleanupTestUser(page, email)` - Delete a test user (only if test email)
- `cleanupTestUsers(page, emails)` - Delete multiple test users (only test emails)
- `saveOriginalTradingConfig(page)` - Save original config before modification
- `resetTradingConfig(page)` - Reset trading config to original (only if saved)
- `saveOriginalNotificationPreferences(page)` - Save original prefs before modification
- `resetNotificationPreferences(page)` - Reset prefs to original (only if saved)
- `trackNotificationId(id)` - Track a notification for cleanup
- `cleanupTestNotifications(page)` - Clean up tracked notifications only
- `clearBrowserStorage(page)` - Clear browser storage (safe - test context only)
- `isTestEmail(email)` - Check if email is a test email (safety check)

### TestDataTracker Class

```typescript
const tracker = new TestDataTracker();

// Track data
tracker.trackUser('user@example.com');
tracker.trackConfig('trading-config');

// Clean up
await tracker.cleanup(page);
```

## 📝 Best Practices

1. **Always Track Test Data**
   - Use `testDataTracker` to track all created data
   - Don't rely on manual cleanup unless necessary

2. **Use Unique Test Data**
   - Generate unique emails/names for each test
   - Prevents conflicts between tests

3. **Clean Up in Fixtures**
   - Prefer fixture cleanup over manual cleanup
   - More reliable and consistent

4. **Don't Clean Up Shared Data**
   - Don't delete admin users or system data
   - Only clean up test-specific data

5. **Handle Cleanup Failures Gracefully**
   - Cleanup functions log warnings but don't fail tests
   - This prevents cleanup failures from masking test failures

## 🐛 Troubleshooting

### Cleanup Not Working

1. **Check API Endpoints**
   - Ensure cleanup endpoints exist in the API
   - Check API authentication/authorization

2. **Check Test Data Tracker**
   - Verify data is being tracked
   - Check fixture is being used correctly

3. **Check Global Setup/Teardown**
   - Verify global setup runs successfully
   - Check for errors in global teardown

### Data Persisting Between Tests

1. **Verify Test Isolation**
   - Each test should use unique data
   - Check for shared state between tests

2. **Check Cleanup Execution**
   - Verify cleanup runs after each test
   - Check cleanup logs for errors

## 📚 Examples

### Example 1: Signup Test with Cleanup

```typescript
test('user can sign up', async ({ signupPage, page, testDataTracker }) => {
  const email = generateTestEmail('signup');
  testDataTracker.trackUser(email);

  await signupPage.signup(email, 'password', 'Name');
  // User will be cleaned up automatically
});
```

### Example 2: Config Test with Cleanup

```typescript
test('update config', async ({ authenticatedPage, testDataTracker }) => {
  testDataTracker.trackConfig('trading-config');

  // Update config...
  // Config will be reset automatically
});
```

### Example 3: Multiple Data Types

```typescript
test('complex test', async ({ page, testDataTracker }) => {
  const email = generateTestEmail('test');
  testDataTracker.trackUser(email);
  testDataTracker.trackConfig('trading-config');
  testDataTracker.trackConfig('notification-preferences');

  // Create test data...
  // All will be cleaned up automatically
});
```

## 🔄 Migration

If you have existing tests without cleanup:

1. Add `testDataTracker` to test parameters
2. Track created data: `testDataTracker.trackUser(email)`
3. Track modified configs: `testDataTracker.trackConfig('config-name')`
4. Cleanup happens automatically!

## 📖 Related Documentation

- [Test Configuration](./config/test-config.ts)
- [Test Helpers](./utils/test-helpers.ts)
- [Test Fixtures](./fixtures/test-fixtures.ts)
- [POM Architecture](./README_POM.md)
