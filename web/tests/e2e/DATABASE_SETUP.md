# E2E Test Database Setup

## Database Isolation

E2E tests use a **separate database** from the main application to ensure test isolation:

- **Production/Development Database**: `data/app.db` (used by Docker and regular app)
  - ✅ **Keep using this for normal development**
  - ✅ **Docker should continue using `app.db`**
  - This is your regular development database with your real data

- **E2E Test Database**: `data/e2e.db` (used only by E2E tests)
  - ✅ **Only used by E2E tests**
  - ✅ **Separate from development database**
  - Tests can reset/modify this without affecting your dev data

## Important: Database Separation

⚠️ **CRITICAL**: The Docker app uses `app.db` and E2E tests use `e2e.db`. These are **separate databases**.

### Why This Matters

1. **Data Isolation**: Test data doesn't affect production/development data
2. **Clean State**: Tests can reset/modify data without affecting your app
3. **Parallel Usage**: You can run the Docker app and E2E tests simultaneously

### Current Configuration

- **Docker/Production**: Uses `DB_URL=sqlite:///./data/app.db`
- **E2E Tests**: Uses `E2E_DB_URL=sqlite:///./data/e2e.db` (default)
- **Seeding Script**: Seeds into `e2e.db` (configured via `E2E_DB_URL`)

## Running E2E Tests

### Option 1: Use Test Runner Scripts (Recommended)

The test runner scripts automatically configure the correct database:

```powershell
# PowerShell (Windows)
.\run-e2e-tests.ps1
```

```bash
# Bash (Linux/Mac)
./run-e2e-tests.sh
```

These scripts will:
- ✅ Check if API server is running
- ✅ Start API server with `e2e.db` if not running
- ✅ Ensure web frontend is running
- ✅ Run tests with correct configuration

### Option 2: Manual Setup

If you want to run tests manually:

**1. Ensure API server uses e2e.db:**

```powershell
# Stop any existing API server first
# Then start with e2e database
$env:DB_URL="sqlite:///./data/e2e.db"
python -m uvicorn server.app.main:app --port 8000
```

**2. Seed test data (optional):**

```powershell
.venv\Scripts\python.exe web/tests/e2e/utils/seed-db.py --signals 10 --orders 5 --notifications 10
```

**3. Run tests:**

```powershell
cd web
npm run test:e2e
```

### Option 3: Docker + E2E Tests

If you're running the Docker app simultaneously:

**⚠️ Important**: The Docker app uses `app.db`, so:
- E2E tests will use a different database (`e2e.db`)
- Seeded data goes into `e2e.db`, not `app.db`
- Tests won't see Docker app data, and vice versa

To test with Docker app data, you have two options:

1. **Copy data from app.db to e2e.db** (advanced, not recommended)
2. **Use separate test instances** (recommended - use test runner scripts)

## Seeding Test Data

The seeding script always seeds into the E2E database:

```powershell
# Seeds into e2e.db (default)
python web/tests/e2e/utils/seed-db.py --signals 10 --orders 5 --notifications 10

# Or specify custom database
$env:E2E_DB_URL="sqlite:///./data/e2e.db"
python web/tests/e2e/utils/seed-db.py --signals 10
```

## Verifying Database Configuration

Check which database the API server is using:

```python
import os
print(os.environ.get("DB_URL", "sqlite:///./data/app.db"))
```

Or check the database file directly:

```powershell
# Check e2e.db exists
Test-Path data\e2e.db

# Check app.db exists (Docker/production)
Test-Path data\app.db
```

## Troubleshooting

### Problem: Tests don't see seeded data

**Possible Causes:**
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

### Problem: "Cannot connect to database" error

**Cause**: Database file doesn't exist or wrong path

**Solution:**
```powershell
# Create data directory if missing
New-Item -ItemType Directory -Force -Path data

# Run seeding script (creates database automatically)
python web/tests/e2e/utils/seed-db.py --signals 5
```

### Problem: Tests see production data

**Cause**: API server is using `app.db` instead of `e2e.db`

**Solution:**
- Use test runner scripts that automatically configure `e2e.db`
- Or manually set `DB_URL=sqlite:///./data/e2e.db` before starting API server

## Best Practices

1. ✅ **Always use test runner scripts** (`run-e2e-tests.ps1` or `.sh`)
   - They automatically configure the correct database
   - They manage API server lifecycle

2. ✅ **Use separate databases** for tests and production
   - `app.db` for Docker/production
   - `e2e.db` for E2E tests

3. ✅ **Seed data explicitly** when needed
   - Use `E2E_SEED_DATA=true` for automatic seeding
   - Or run seeding script manually before tests

4. ⚠️ **Don't mix databases**
   - Don't seed into `app.db` when running tests
   - Don't use `e2e.db` for production

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `DB_URL` | Database URL for API server | `sqlite:///./data/app.db` |
| `E2E_DB_URL` | Database URL for E2E tests/seeding | `sqlite:///./data/e2e.db` |
| `E2E_SEED_DATA` | Enable automatic seeding in global-setup | `false` |

## Summary

- **Docker App**: Uses `app.db` (`DB_URL=sqlite:///./data/app.db`)
- **E2E Tests**: Use `e2e.db` (`E2E_DB_URL=sqlite:///./data/e2e.db`)
- **Seeding**: Always seeds into `e2e.db`
- **Best Practice**: Use test runner scripts that handle database configuration automatically
