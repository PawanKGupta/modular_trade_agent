# E2E Test Database Configuration

## Overview

E2E tests use a **separate database** (`e2e.db`) from the main application database (`app.db`) to ensure test isolation and data safety.

## Database Separation

### Two Databases

- **`data/app.db`** - Production/Development Database
  - Used by Docker containers
  - Used for normal development
  - Contains your real development data

- **`data/e2e.db`** - E2E Test Database
  - Used **only** by E2E tests
  - Separate from development database
  - Tests can reset/modify without affecting dev data

### Why Separate Databases?

1. **Data Isolation**: Test data doesn't affect development/production data
2. **Clean State**: Tests can reset/modify data safely
3. **Parallel Usage**: Run Docker app and E2E tests simultaneously
4. **Safety**: Protect your development data from test operations

## Which Database Do Tests Use?

**E2E tests use whatever database the API server is connected to.**

```
E2E Tests → HTTP Requests → API Server → Database File
                              ↓
                         (DB_URL env var)
```

The tests make HTTP requests to the API server. The API server reads/writes to its configured database (via `DB_URL`).

## Configuration

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `DB_URL` | Database URL for API server | `sqlite:///./data/app.db` |
| `E2E_DB_URL` | Database URL for E2E tests/seeding | `sqlite:///./data/e2e.db` |
| `E2E_SEED_DATA` | Enable automatic seeding in global-setup | `false` |

### Test Runner Scripts (Recommended)

The test runner scripts automatically configure the correct database:

**PowerShell (Windows):**
```powershell
.\run-e2e-tests.ps1
```

**Bash (Linux/Mac):**
```bash
./run-e2e-tests.sh
```

These scripts:
- ✅ Check if API server is running
- ✅ Start API server with `DB_URL=sqlite:///./data/e2e.db` if not running
- ✅ Ensure test admin user exists
- ✅ Run tests with correct configuration

### Manual Setup

If running tests manually:

**1. Start API server with e2e.db:**
```powershell
$env:DB_URL="sqlite:///./data/e2e.db"
$env:ADMIN_EMAIL="testadmin@rebound.com"
$env:ADMIN_PASSWORD="testadmin@123"
python -m uvicorn server.app.main:app --port 8000
```

**2. Seed test data (optional):**
```powershell
python web/tests/e2e/utils/seed-db.py --signals 10 --orders 5 --notifications 10
```

**3. Run tests:**
```powershell
cd web
npm run test:e2e
```

## Common Scenarios

### Scenario 1: Using Test Runner Script ✅

```powershell
.\run-e2e-tests.ps1
```

- Script starts API server with `e2e.db`
- Tests use `e2e.db` ✅
- Clean and simple

### Scenario 2: Docker Already Running

If Docker is running with `app.db`:

**Option A: Stop Docker, use test runner**
```powershell
docker-compose down
.\run-e2e-tests.ps1
```

**Option B: Check which database Docker is using**
```powershell
docker exec tradeagent-api env | grep DB_URL
```

If using `app.db`, stop Docker first - tests should use `e2e.db`.

### Scenario 3: API Server Already Running

**If API server is using `e2e.db`:**
- ✅ Tests will use `e2e.db` correctly
- Continue with tests

**If API server is using `app.db`:**
- ❌ Tests will use `app.db` (not ideal)
- Stop API server and use test runner script

## Frequently Asked Questions

### Q: Do I need to use e2e.db for development?

**A: NO!** Keep using `app.db` for development.

- ✅ **Docker/Development**: Use `app.db`
- ✅ **E2E Tests**: Use `e2e.db`

The `e2e.db` is **ONLY** for E2E tests.

### Q: Can I run Docker and E2E tests simultaneously?

**A: YES!** That's the benefit of separate databases.

- Docker uses `app.db` → Your development environment
- E2E tests use `e2e.db` → Your test environment
- They don't interfere with each other

### Q: How do I know which database is being used?

**Check the API server's `DB_URL` environment variable:**

```powershell
# Check environment
echo $env:DB_URL

# Check Docker container
docker exec tradeagent-api env | grep DB_URL

# Check if e2e.db exists and was recently modified
Test-Path data\e2e.db
(Get-Item data\e2e.db).LastWriteTime
```

### Q: Where does seeded data go?

**A: Into `e2e.db` (the test database)**

Seeding script always seeds into the E2E test database, keeping your dev data safe.

### Q: Will seeding affect my Docker app data?

**A: NO.** Seeding only affects `e2e.db`, not `app.db`.

Your Docker app continues using `app.db` with your development data untouched.

### Q: Can I use the same database for both?

**A: Not recommended.**

If you really want to:
```powershell
$env:E2E_DB_URL="sqlite:///./data/app.db"
```

**Warning**: This means:
- Test data will mix with development data
- Tests might modify/delete your development data
- Can't run Docker and tests simultaneously safely

**Better approach**: Keep them separate.

## Verifying Database Configuration

### Check API Server Logs

When the API server starts, it logs the database URL. Look for:
- `sqlite:///./data/e2e.db` ✅ (correct for tests)
- `sqlite:///./data/app.db` ❌ (wrong for tests)

### Check Environment Variables

```powershell
# Before starting API server
echo $env:DB_URL

# In Docker container
docker exec tradeagent-api env | grep DB_URL
```

### Check Database Files

```powershell
# Check if databases exist
Test-Path data\e2e.db
Test-Path data\app.db

# Check modification times
(Get-Item data\e2e.db).LastWriteTime
(Get-Item data\app.db).LastWriteTime
```

### Check Seeded Data

- If you see seeded test signals/orders in the UI → Using `e2e.db` ✅
- If you see your development data → Using `app.db` ❌

## Troubleshooting

### Tests don't see seeded data

**Causes:**
1. API server is using `app.db` instead of `e2e.db`
2. Data was seeded into wrong database
3. API server was started before seeding

**Solution:**
```powershell
# 1. Stop API server
# 2. Ensure correct database
$env:DB_URL="sqlite:///./data/e2e.db"

# 3. Seed data
python web/tests/e2e/utils/seed-db.py --signals 10

# 4. Start API server
python -m uvicorn server.app.main:app --port 8000

# 5. Run tests
cd web
npm run test:e2e
```

### Tests see production data

**Cause**: API server is using `app.db` instead of `e2e.db`

**Solution**:
- Use test runner scripts that automatically configure `e2e.db`
- Or manually set `DB_URL=sqlite:///./data/e2e.db` before starting API server

### Database file not found

**Solution**:
```powershell
# Create data directory if missing
New-Item -ItemType Directory -Force -Path data

# Run seeding script (creates database automatically)
python web/tests/e2e/utils/seed-db.py --signals 5
```

## Best Practices

1. ✅ **Always use test runner scripts** (`run-e2e-tests.ps1` or `.sh`)
   - Automatically configure correct database
   - Manage API server lifecycle
   - Ensure test admin user exists

2. ✅ **Use separate databases**
   - `app.db` for Docker/production
   - `e2e.db` for E2E tests

3. ✅ **Seed data explicitly** when needed
   - Use `E2E_SEED_DATA=true` for automatic seeding
   - Or run seeding script manually before tests

4. ⚠️ **Don't mix databases**
   - Don't seed into `app.db` when running tests
   - Don't use `e2e.db` for production

## Summary

- **Docker App**: Uses `app.db` (`DB_URL=sqlite:///./data/app.db`)
- **E2E Tests**: Use `e2e.db` (`E2E_DB_URL=sqlite:///./data/e2e.db`)
- **Seeding**: Always seeds into `e2e.db`
- **Best Practice**: Use test runner scripts that handle database configuration automatically

For more details, see:
- [Data Management Guide](./DATA_MANAGEMENT.md) - Test data seeding and management
- [Test Cleanup Guide](./CLEANUP_GUIDE.md) - How tests clean up after themselves
