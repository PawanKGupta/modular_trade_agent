# E2E Tests Setup and Running Guide

## Prerequisites

Before running E2E tests, you need:

1. **API Server** running on `http://localhost:8000`
2. **Web Frontend** running on `http://localhost:5173`
3. **Playwright browsers** installed

## Setup

### 1. Install Playwright Browsers

```bash
cd web
npx playwright install chromium
```

### 2. Start API Server

**IMPORTANT**: Use the test admin credentials that match `test-config.ts`:

```bash
# Set environment variables
$env:DB_URL="sqlite:///./data/e2e.db"
$env:ADMIN_EMAIL="testadmin@rebound.com"
$env:ADMIN_PASSWORD="testadmin@123"

# Start API server
python -m uvicorn server.app.main:app --port 8000 --reload
```

**Note**: The API server will auto-create the admin user if the database is empty. If the database already has users, ensure the test admin exists using:

```bash
python web/tests/e2e/utils/ensure-test-admin.py
```

Or using Docker:

```bash
cd docker
docker-compose -f docker-compose.yml up -d api-server
```

### 3. Start Web Frontend

In another terminal:

```bash
cd web
$env:VITE_API_URL="http://localhost:8000"
npm run dev
```

## Running Tests

### Run All E2E Tests

```bash
cd web
npm run test:e2e
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

See [DATABASE_SETUP.md](./DATABASE_SETUP.md) for detailed database configuration guide.

## Test Data Seeding (Optional)

For comprehensive testing with real data, you can enable test data seeding:

```bash
# Enable seeding
export E2E_SEED_DATA=true

# Optional: Configure amounts
export E2E_SEED_SIGNALS=10
export E2E_SEED_ORDERS=5
export E2E_SEED_NOTIFICATIONS=10

# Optional: Clear existing data before seeding
export E2E_CLEAR_BEFORE_SEED=true

# Run tests
npm run test:e2e
```

**What gets seeded:**
- Test signals (various statuses, symbols, dates)
- Test orders (different statuses and types)
- Test notifications (various types and levels)

See [DATA_MANAGEMENT.md](./DATA_MANAGEMENT.md) for details.

## Test Structure

- `auth.spec.ts` - Authentication flows
- `dashboard.spec.ts` - Dashboard and navigation
- `trading.spec.ts` - Trading features
- `settings.spec.ts` - Settings and configuration
- `notifications.spec.ts` - Notifications
- `system.spec.ts` - System monitoring
- `admin.spec.ts` - Admin features
- `errors.spec.ts` - Error handling

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

## CI/CD

Tests run automatically in CI/CD pipeline (see `.github/workflows/web-e2e.yml`).
