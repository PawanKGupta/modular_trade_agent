# E2E Tests Setup and Running Guide

## Quick Start

The easiest way to run E2E tests is using the test runner script:

```powershell
# Windows
cd web
.\run-e2e-tests.ps1
```

```bash
# Linux/Mac
cd web
./run-e2e-tests.sh
```

The script automatically:
- ✅ Starts API server with correct database (`e2e.db`)
- ✅ Ensures test admin user exists
- ✅ Starts web frontend (if needed)
- ✅ Runs all tests
- ✅ Cleans up after tests

## Prerequisites

Before running E2E tests manually, you need:

1. **API Server** running on `http://localhost:8000`
2. **Web Frontend** running on `http://localhost:5173`
3. **Playwright browsers** installed

## Setup

### 1. Install Playwright Browsers

```bash
cd web
npx playwright install chromium
```

### 2. Start Services

#### Option A: Use Test Runner Script (Recommended)

```powershell
.\run-e2e-tests.ps1
```

The script handles everything automatically.

#### Option B: Manual Setup

**Start API Server:**
```powershell
$env:DB_URL="sqlite:///./data/e2e.db"
$env:ADMIN_EMAIL="testadmin@rebound.com"
$env:ADMIN_PASSWORD="testadmin@123"
python -m uvicorn server.app.main:app --port 8000 --reload
```

**Start Web Frontend:**
```powershell
cd web
$env:VITE_API_URL="http://localhost:8000"
npm run dev
```

### 3. Test Admin User

E2E tests require a specific admin user to authenticate. The test runner script automatically creates this user.

**Default credentials** (matches `test-config.ts`):
- **Email**: `testadmin@rebound.com`
- **Password**: `testadmin@123`
- **Role**: `admin`

**Manual setup:**
```powershell
python web/tests/e2e/utils/ensure-test-admin.py
```

For details, see the [Test Admin Setup](#test-admin-user-setup) section below.

## Running Tests

### Run All E2E Tests

```bash
cd web
npm run test:e2e
```

Or use the test runner script:
```powershell
.\run-e2e-tests.ps1
```

### Run Specific Test File

```bash
cd web
npx playwright test tests/e2e/auth.spec.ts
```

### Run Tests in UI Mode (Interactive)

```bash
cd web
npx playwright test --ui
```

### Run Tests in Debug Mode

```bash
cd web
npx playwright test --debug
```

### Run Tests with Specific Browser

```bash
cd web
npx playwright test --project=chromium
```

## Database Configuration

⚠️ **IMPORTANT**: E2E tests use a **separate database** (`e2e.db`) from the Docker app (`app.db`).

- **Docker/Production**: Uses `data/app.db`
- **E2E Tests**: Uses `data/e2e.db`

These are separate databases - test data doesn't affect production data.

**For detailed database information, see [DATABASE.md](./DATABASE.md)**

## Test Data Seeding (Optional)

For comprehensive testing with real data, you can enable test data seeding:

```powershell
# Enable seeding
$env:E2E_SEED_DATA="true"

# Optional: Configure amounts
$env:E2E_SEED_SIGNALS="10"
$env:E2E_SEED_ORDERS="5"
$env:E2E_SEED_NOTIFICATIONS="10"

# Optional: Clear existing data before seeding
$env:E2E_CLEAR_BEFORE_SEED="true"

# Run tests
npm run test:e2e
```

**What gets seeded:**
- Test signals (various statuses, symbols, dates)
- Test orders (different statuses and types)
- Test notifications (various types and levels)

**For details, see [DATA_MANAGEMENT.md](./DATA_MANAGEMENT.md)**

## Test Admin User Setup

E2E tests require a specific admin user (`testadmin@rebound.com`) to authenticate.

### Automatic Setup (Recommended)

The test runner script automatically ensures the test admin user exists:

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

### Test Admin Credentials

**Default credentials** (matches `test-config.ts`):
- **Email**: `testadmin@rebound.com`
- **Password**: `testadmin@123`
- **Role**: `admin`

**Customization**: You can override with environment variables:
```powershell
$env:TEST_ADMIN_EMAIL="custom@example.com"
$env:TEST_ADMIN_PASSWORD="CustomPassword123"
```

### What the Script Does

The `ensure-test-admin.py` script:

1. ✅ Connects to `e2e.db` database
2. ✅ Checks if `testadmin@rebound.com` exists
3. ✅ Creates user if missing
4. ✅ Ensures user has admin role
5. ✅ Ensures user is active
6. ✅ Creates default settings for the user

### Troubleshooting

**Issue: "User does not exist" error in tests**

Solution:
```powershell
# Run the ensure script manually
python web/tests/e2e/utils/ensure-test-admin.py

# Or use the test runner script which does it automatically
.\run-e2e-tests.ps1
```

**Issue: "Authentication failed"**

Check:
1. Verify credentials match `test-config.ts`
2. Verify user exists: `python web/tests/e2e/utils/ensure-test-admin.py`
3. Check user role is admin

## Test Structure

- `auth.spec.ts` - Authentication flows
- `dashboard.spec.ts` - Dashboard and navigation
- `trading.spec.ts` - Trading features
- `settings.spec.ts` - Settings and configuration
- `notifications.spec.ts` - Notifications
- `system.spec.ts` - System monitoring
- `admin.spec.ts` - Admin features
- `errors.spec.ts` - Error handling
- `ml-training.spec.ts` - ML Training Management
- `log-viewer.spec.ts` - Log Viewer
- `service-status.spec.ts` - Service Status
- `trading-config.spec.ts` - Trading Configuration

## Documentation

- **[DATABASE.md](./DATABASE.md)** - Database configuration and FAQs
- **[DATA_MANAGEMENT.md](./DATA_MANAGEMENT.md)** - Test data seeding and management
- **[CLEANUP_GUIDE.md](./CLEANUP_GUIDE.md)** - Test cleanup strategy
- **[README_POM.md](./README_POM.md)** - Page Object Model architecture

## Troubleshooting

### Tests Fail with Connection Errors

- Verify API server is running: `curl http://localhost:8000/health`
- Verify web frontend is running: `curl http://localhost:5173`
- Check firewall settings

### Tests Fail with Timeout

- Increase timeout in `playwright.config.ts`
- Check network connectivity
- Verify services are responding

### Tests Fail with Element Not Found

- Check if UI has changed
- Verify selectors are correct
- Use Playwright Inspector: `npx playwright test --debug`

### Tests Fail with Authentication Errors

- Verify test admin user exists: `python web/tests/e2e/utils/ensure-test-admin.py`
- Check credentials match `test-config.ts`
- Ensure API server is using `e2e.db` database

### Tests Don't See Seeded Data

- Verify API server is using `e2e.db` (not `app.db`)
- Check if data was seeded: `python web/tests/e2e/utils/seed-db.py --signals 10`
- Ensure API server was started after seeding

For more troubleshooting, see [DATABASE.md](./DATABASE.md).

## CI/CD

Tests run automatically in CI/CD pipeline (see `.github/workflows/web-e2e.yml`).
