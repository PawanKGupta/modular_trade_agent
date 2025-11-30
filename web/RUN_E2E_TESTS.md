# Running E2E Tests Manually

## ✅ Prerequisites Checklist

Before running E2E tests, ensure:

- [x] **Playwright browsers installed** - Run: `npx playwright install chromium`
- [x] **API server running** on `http://localhost:8000`
- [x] **Web frontend running** on `http://localhost:5173`

## 🚀 Quick Start

### 1. Verify Services Are Running

**Check API Server:**
```powershell
# Should return True
Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Quiet

# Or check health endpoint
curl http://localhost:8000/health
```

**Check Web Frontend:**
```powershell
# Should return True
Test-NetConnection -ComputerName localhost -Port 5173 -InformationLevel Quiet

# Or open in browser
Start-Process http://localhost:5173
```

### 2. Run All E2E Tests

```powershell
cd web
npm run test:e2e
```

Or with Playwright directly:
```powershell
cd web
npx playwright test
```

### 3. Run Specific Tests

**Single test file:**
```powershell
cd web
npx playwright test tests/e2e/auth.spec.ts
```

**Single test:**
```powershell
cd web
npx playwright test tests/e2e/auth.spec.ts -g "user can login"
```

**Multiple test files:**
```powershell
cd web
npx playwright test tests/e2e/auth.spec.ts tests/e2e/dashboard.spec.ts
```

## 📊 Test Reports

### View HTML Report

After tests complete:
```powershell
cd web
npx playwright show-report
```

### View Test Traces (on failure)

```powershell
cd web
npx playwright show-trace test-results/[test-name]/trace.zip
```

## 🎯 Common Commands

### Run with UI Mode (Interactive)
```powershell
cd web
npx playwright test --ui
```

### Run in Debug Mode
```powershell
cd web
npx playwright test --debug
```

### Run in Headed Mode (See Browser)
```powershell
cd web
npx playwright test --headed
```

### Run Tests Matching Pattern
```powershell
cd web
npx playwright test -g "authentication"
```

### Run with More Workers (Faster)
```powershell
cd web
npx playwright test --workers=4
```

### List All Tests
```powershell
cd web
npx playwright test --list
```

## 🔧 Troubleshooting

### Tests Fail: Connection Refused

**Problem**: Services not running

**Solution**:
1. Start API server:
   ```powershell
   $env:DB_URL="sqlite:///./data/e2e.db"
   $env:ADMIN_EMAIL="admin@example.com"
   $env:ADMIN_PASSWORD="Admin@123"
   python -m uvicorn server.app.main:app --port 8000 --reload
   ```

2. Start web frontend (in another terminal):
   ```powershell
   cd web
   $env:VITE_API_URL="http://localhost:8000"
   npm run dev
   ```

### Tests Fail: Browser Not Found

**Problem**: Playwright browsers not installed

**Solution**:
```powershell
cd web
npx playwright install chromium
```

### Tests Timeout

**Problem**: Services are slow to respond

**Solution**:
1. Increase timeout in `playwright.config.ts`:
   ```typescript
   use: {
     actionTimeout: 30000, // 30 seconds
   }
   ```

2. Or in individual tests:
   ```typescript
   test.setTimeout(60000); // 60 seconds
   ```

## 📝 Test Files Overview

| File | Tests | Description |
|------|-------|-------------|
| `auth.spec.ts` | 5 | Authentication flows |
| `dashboard.spec.ts` | 4 | Dashboard navigation |
| `trading.spec.ts` | 8 | Trading features |
| `settings.spec.ts` | 7 | Settings pages |
| `notifications.spec.ts` | 5 | Notifications |
| `system.spec.ts` | 5 | System monitoring |
| `admin.spec.ts` | 5 | Admin features |
| `errors.spec.ts` | 5 | Error handling |
| `trading-config.spec.ts` | 13 | Trading configuration |
| `service-status.spec.ts` | 6 | Service status |
| `log-viewer.spec.ts` | 2 | Log viewer |
| `ml-training.spec.ts` | 2 | ML training |
| `smoke.spec.ts` | 1 | Smoke test |

**Total: 67 tests**

## 🎬 Example: Running Tests Step-by-Step

```powershell
# 1. Navigate to web directory
cd C:\Personal\Projects\TradingView\modular_trade_agent\web

# 2. Verify services (in separate terminals)
# Terminal 1: API server running on :8000
# Terminal 2: Web frontend running on :5173

# 3. Run all tests
npm run test:e2e

# 4. Or run specific test file
npx playwright test tests/e2e/auth.spec.ts

# 5. View results
npx playwright show-report
```

## 📚 Additional Resources

- Full test plan: `docs/E2E_TEST_PLAN.md`
- Complete testing guide: `docs/E2E_TESTING_GUIDE.md`
- Test setup README: `web/tests/e2e/README.md`

