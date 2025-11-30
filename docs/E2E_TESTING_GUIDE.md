# E2E Testing Guide

Complete guide for running and maintaining E2E tests for Rebound — Modular Trade Agent.

## 📊 Test Overview

**Total Tests**: 67 E2E tests across 13 test files

### Test Files

1. **auth.spec.ts** (5 tests) - Authentication flows
2. **dashboard.spec.ts** (4 tests) - Dashboard and navigation
3. **trading.spec.ts** (8 tests) - Trading features
4. **settings.spec.ts** (7 tests) - Settings and configuration
5. **notifications.spec.ts** (5 tests) - Notifications
6. **system.spec.ts** (5 tests) - System monitoring
7. **admin.spec.ts** (5 tests) - Admin features
8. **errors.spec.ts** (5 tests) - Error handling
9. **smoke.spec.ts** (1 test) - Smoke test
10. **trading-config.spec.ts** (13 tests) - Trading configuration
11. **service-status.spec.ts** (6 tests) - Service status
12. **log-viewer.spec.ts** (2 tests) - Log viewer
13. **ml-training.spec.ts** (2 tests) - ML training

## 🚀 Quick Start

### Option 1: Automated Script (Recommended)

**Windows (PowerShell):**
```powershell
cd web
.\run-e2e-tests.ps1
```

**Linux/Mac (Bash):**
```bash
cd web
chmod +x run-e2e-tests.sh
./run-e2e-tests.sh
```

The script will:
- ✅ Check if API server is running (start if needed)
- ✅ Check if web frontend is running (start if needed)
- ✅ Install Playwright browsers
- ✅ Run all E2E tests
- ✅ Clean up started services

### Option 2: Manual Setup

**1. Start API Server**

```bash
# Set environment variables
$env:DB_URL="sqlite:///./data/e2e.db"
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="Admin@123"

# Start API server
python -m uvicorn server.app.main:app --port 8000 --reload
```

**2. Start Web Frontend** (in another terminal)

```bash
cd web
$env:VITE_API_URL="http://localhost:8000"
npm run dev
```

**3. Run Tests** (in another terminal)

```bash
cd web
npm run test:e2e
```

## 📝 Running Specific Tests

### Run Single Test File

```bash
cd web
npx playwright test tests/e2e/auth.spec.ts
```

### Run Single Test

```bash
cd web
npx playwright test tests/e2e/auth.spec.ts -g "user can login"
```

### Run Tests Matching Pattern

```bash
cd web
npx playwright test -g "authentication"
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

## 🔍 Test Results

### View Test Report

After tests complete, view the HTML report:

```bash
cd web
npx playwright show-report
```

### View Test Traces

Test traces are saved on failure. View them:

```bash
cd web
npx playwright show-trace trace.zip
```

## 🐛 Troubleshooting

### Tests Fail: "Connection Refused"

**Problem**: API server or web frontend not running

**Solution**:
1. Verify API server: `curl http://localhost:8000/health`
2. Verify web frontend: `curl http://localhost:5173`
3. Start missing services (see Manual Setup above)

### Tests Fail: "Element Not Found"

**Problem**: UI has changed or selector is incorrect

**Solution**:
1. Run test in debug mode: `npx playwright test --debug`
2. Use Playwright Inspector to find correct selectors
3. Update test file with correct selectors

### Tests Fail: "Timeout"

**Problem**: Page takes too long to load

**Solution**:
1. Increase timeout in test: `await page.waitForTimeout(5000)`
2. Check network connectivity
3. Verify services are responding quickly

### Tests Fail: "Login Failed"

**Problem**: Admin credentials incorrect

**Solution**:
1. Verify admin user exists in database
2. Check `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables
3. Create admin user if needed

## 📋 Test Maintenance

### Adding New Tests

1. Create new test file in `web/tests/e2e/`
2. Follow existing test patterns
3. Use descriptive test names
4. Add to appropriate test suite

### Updating Tests

When UI changes:
1. Run tests to identify failures
2. Use Playwright Inspector to find new selectors
3. Update test files with correct selectors
4. Verify tests pass

### Test Data

- Tests use in-memory database (`e2e.db`)
- Each test should be independent
- Clean up test data after each test
- Use fixtures for common setup

## 🎯 Test Coverage

### Current Coverage

- ✅ Authentication flows
- ✅ Dashboard navigation
- ✅ Trading features
- ✅ Settings management
- ✅ Notifications
- ✅ System monitoring
- ✅ Admin features
- ✅ Error handling

### Missing Coverage

Consider adding tests for:
- Data integrity across pages
- Performance benchmarks
- Concurrent user actions
- Large dataset handling

## 🔄 CI/CD Integration

Tests run automatically in GitHub Actions (`.github/workflows/web-e2e.yml`).

### Local CI Simulation

```bash
# Start services
$env:DB_URL="sqlite:///./data/e2e.db"
python -m uvicorn server.app.main:app --port 8000 &
cd web
$env:VITE_API_URL="http://localhost:8000"
npm run dev &

# Run tests
$env:PLAYWRIGHT_BASE_URL="http://localhost:5173"
npm run test:e2e
```

## 📚 Best Practices

1. **Test Independence**: Each test should work in isolation
2. **Clear Assertions**: Use descriptive expect statements
3. **Wait for Elements**: Always wait for elements before interacting
4. **Error Handling**: Test both success and failure paths
5. **Cleanup**: Clean up test data after each test
6. **Documentation**: Document complex test scenarios

## 🆘 Getting Help

If tests fail:
1. Check test output for error messages
2. View test traces: `npx playwright show-trace`
3. Run in debug mode: `npx playwright test --debug`
4. Check service logs
5. Review test plan: `docs/E2E_TEST_PLAN.md`

---

**Note**: E2E tests require both API server and web frontend to be running. Use the automated scripts for easiest setup.

