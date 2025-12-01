# E2E Test Data Management

## Current Approach: Resilient Tests with Optional Data

Our E2E tests are designed to work **with or without existing data** in the database. This makes them more robust and able to handle different database states.

## How Tests Handle Missing Data

### 1. **Empty State Checks**

Most tests check for **both** data presence AND empty states:

```typescript
// Example from trading.spec.ts
const signalsTable = authenticatedPage.locator('table, [role="table"]');
const emptyState = authenticatedPage.getByText(/No signals found/i);

const hasTable = await signalsTable.first().isVisible().catch(() => false);
const hasEmptyState = await emptyState.isVisible().catch(() => false);

// Either table or empty state should be visible - test passes either way
expect(hasTable || hasEmptyState).toBe(true);
```

This pattern is used in:
- ✅ `trading.spec.ts` - Buying Zone, Orders, Paper Trading History
- ✅ `admin.spec.ts` - Users table, ML Training jobs
- ✅ `notifications.spec.ts` - Notification list
- ✅ `system.spec.ts` - Activity logs

### 2. **Conditional Test Execution**

Some tests skip if no data is available:

```typescript
// Example: "can reject a buying signal" test
if (rejectCount > 0) {
    // Test signal rejection
} else {
    test.skip(); // Skip if no signals exist
}
```

### 3. **Data Creation During Tests**

Tests create their own data when needed:

- **User Creation**: `admin.spec.ts` creates test users during the test
- **Configuration Changes**: `trading-config.spec.ts` modifies configs and resets them
- **Test Data Tracking**: Uses `testDataTracker` fixture to clean up created data

## Database State

### Test Database

E2E tests use a **separate SQLite database**: `./data/e2e.db`

⚠️ **IMPORTANT**: This is different from the Docker/production database (`app.db`)

- **NOT** an in-memory database
- **Persists** between test runs (unless manually deleted)
- **Can accumulate data** from multiple test runs
- **Separate** from Docker/production database (`app.db`)

### Initial Database State

Currently, the database starts with:
- ✅ **Admin user** (created during app startup)
  - Email: `admin@example.com`
  - Password: `Admin@123`
- ❌ **No test data seeding** - database may be empty

### Database Separation

**Critical**: E2E tests use `e2e.db`, while Docker/production uses `app.db`. These are **separate databases**.

- **Docker App**: Uses `sqlite:///./data/app.db`
- **E2E Tests**: Uses `sqlite:///./data/e2e.db`
- **Seeding Script**: Seeds into `e2e.db` (configured via `E2E_DB_URL`)

See [DATABASE_SETUP.md](./DATABASE_SETUP.md) for detailed information about database configuration.

## What Tests Validate

### ✅ Tests That Work Without Data

1. **Page Load Tests**
   - Verify pages render correctly
   - Check for empty states
   - Validate UI structure (tables, filters, buttons)

2. **Navigation Tests**
   - Menu navigation
   - Route changes
   - Active state highlighting

3. **Configuration Tests**
   - Form validation
   - Save/reset functionality
   - Settings modifications

4. **Error Handling Tests**
   - API error scenarios
   - Network failures
   - Loading states

### ⚠️ Tests That Need Data (or Skip)

1. **Data Interaction Tests**
   - `can reject a buying signal` - Skips if no signals
   - Filter tests - Work with empty filters or existing data
   - Status change tests - Need data to interact with

2. **Data Display Tests**
   - Show data when available
   - Show empty state when not
   - Test passes either way

## Data Cleanup

### Automatic Cleanup

The `testDataTracker` fixture automatically cleans up:

1. **Test Users** - Only users created during tests (matching test email patterns)
2. **Config Changes** - Resets to original values (only if tracked)
3. **Notifications** - Marks tracked notifications as read

### Protected Data

The cleanup system **NEVER** deletes:
- Admin users
- System users
- Existing production data
- Data not explicitly tracked

### Cleanup Pattern

```typescript
test('creates and cleans up test user', async ({ authenticatedPage, testDataTracker }) => {
    const email = `test${Date.now()}@rebound.com`;

    // Track BEFORE creating
    testDataTracker.trackUser(email);

    // Create user...
    // ... test logic ...

    // Automatic cleanup after test (via fixture)
});
```

## Current Limitations

### ❌ No Test Data Seeding

- Database may be completely empty
- Tests validate empty states but don't test full data workflows
- Some tests skip when no data is available

### ⚠️ Database Persistence

- `e2e.db` persists between runs
- Data accumulates over time
- May affect test isolation if not managed

### 📝 Test Coverage Gaps

- Limited testing of data-heavy workflows
- Some features only tested in "empty" state
- No comprehensive data interaction tests

## Test Data Seeding (NEW!)

Test data seeding is now **available** as an optional feature! This allows comprehensive testing of data workflows.

### Enabling Test Data Seeding

Set environment variable before running tests:

```bash
# Enable seeding
export E2E_SEED_DATA=true

# Optional: Configure amounts
export E2E_SEED_SIGNALS=10
export E2E_SEED_ORDERS=5
export E2E_SEED_NOTIFICATIONS=10

# Optional: Clear existing data before seeding
export E2E_CLEAR_BEFORE_SEED=true

# Optional: Specify database URL
export E2E_DB_URL=sqlite:///./data/e2e.db

# Run tests
npm run test:e2e
```

Or in PowerShell:

```powershell
$env:E2E_SEED_DATA="true"
$env:E2E_SEED_SIGNALS="10"
$env:E2E_SEED_ORDERS="5"
$env:E2E_SEED_NOTIFICATIONS="10"
npm run test:e2e
```

### What Gets Seeded

The seeding script creates:

1. **Test Signals** (default: 5)
   - Mix of ACTIVE and REJECTED statuses
   - Various symbols (TCS, INFY, RELIANCE, etc.)
   - Different dates (today, yesterday, last 5 days)
   - Realistic technical indicators (RSI, EMA9, EMA200)
   - ML verdicts and confidence scores

2. **Test Orders** (default: 3)
   - Mix of BUY and SELL orders
   - Various statuses (PENDING, ONGOING, CLOSED, FAILED)
   - Different symbols and quantities
   - Realistic timestamps

3. **Test Notifications** (default: 5)
   - Mix of types (service, trading, system, error)
   - Different levels (info, warning, error)
   - Mix of read and unread
   - Realistic timestamps

### Seeding Script

The seeding is done via Python script: `web/tests/e2e/utils/seed-db.py`

You can also run it manually:

```bash
python web/tests/e2e/utils/seed-db.py --signals 10 --orders 5 --notifications 10 --clear
```

### Fixing Outdated Database Schema

If you encounter an error about missing columns (e.g., "table signals has no column named status"), the database schema is outdated. Recreate it:

```bash
# Recreate schema and seed data
python web/tests/e2e/utils/seed-db.py --recreate-schema --signals 10 --orders 5 --notifications 10 --clear
```

Or delete the database file and let it be recreated:

```bash
# Delete old database (Windows PowerShell)
Remove-Item data\e2e.db -ErrorAction SilentlyContinue

# Then run seeding (creates fresh database)
python web/tests/e2e/utils/seed-db.py --signals 10 --orders 5 --notifications 10
```

### How It Works

1. **Global Setup** (`global-setup.ts`) checks if `E2E_SEED_DATA=true`
2. If enabled, it calls the Python seeding script
3. Script directly seeds the database with test data
4. Tests run with seeded data available
5. Test data persists in `./data/e2e.db` (unless cleared)

## Recommendations

### Option 1: Keep Current Approach (Simple)

**Pros:**
- ✅ Tests work immediately without setup
- ✅ Validates empty states (important UX)
- ✅ Simple to maintain

**Cons:**
- ❌ Limited data workflow testing
- ❌ Some tests skip when no data

**When to Use:**
- Quick smoke tests
- CI/CD with empty databases
- Testing UI structure and empty states

### Option 2: Use Test Data Seeding (Comprehensive) ✅ RECOMMENDED

**Pros:**
- ✅ Test full workflows with data
- ✅ More comprehensive coverage
- ✅ Test data interactions
- ✅ Realistic test scenarios

**Cons:**
- ⚠️ Requires enabling via environment variable
- ⚠️ Database must exist and be accessible

**When to Use:**
- Comprehensive testing
- Testing data workflows
- Testing filters, sorting, pagination
- CI/CD with seeded data

**Usage:**
```bash
E2E_SEED_DATA=true npm run test:e2e
```

### Option 3: Hybrid Approach (Best Practice)

**Combine both:**
1. **Basic tests** - Work with empty state (current approach)
2. **Data workflow tests** - Use seeded data for comprehensive testing
3. **Data creation tests** - Create data during tests and clean up

**Benefits:**
- ✅ Tests work without setup (empty state)
- ✅ Comprehensive data workflow coverage (with seeding)
- ✅ Best of both worlds

**Implementation:**
- Keep all current resilient tests (they work either way)
- Enable seeding for comprehensive test runs
- Some tests create data during execution (already implemented)

## Summary

**Current State:**
- ✅ Tests are resilient - work with or without data
- ✅ Validate empty states (important UX)
- ✅ Create data when needed and clean up
- ✅ **Test data seeding is now available!** (enable with `E2E_SEED_DATA=true`)
- ✅ Comprehensive workflow testing possible with seeded data

**Recommendation:**
- Keep current resilient approach for basic tests (works either way)
- **Enable test data seeding for comprehensive test runs** (`E2E_SEED_DATA=true`)
- Use `testDataTracker` for all test-created data
- Run both modes:
  - **Quick tests**: Without seeding (empty state validation)
  - **Full tests**: With seeding (comprehensive workflow testing)
