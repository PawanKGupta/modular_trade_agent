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

In one terminal:

```bash
# Set environment variables
$env:DB_URL="sqlite:///./data/e2e.db"
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="Admin@123"

# Start API server
python -m uvicorn server.app.main:app --port 8000 --reload
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

