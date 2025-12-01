# Which Database Will E2E Tests Use?

## Quick Answer

**E2E tests use whatever database the API server is connected to.**

The tests don't directly access a database - they make HTTP requests to the API server, and the API server reads/writes to its configured database.

## The Flow

```
E2E Tests → HTTP Requests → API Server → Database File
                              ↓
                         (DB_URL env var)
```

## Scenarios

### Scenario 1: Using Test Runner Script (Recommended)

**Command:**
```powershell
.\run-e2e-tests.ps1
```

**What happens:**
1. Script checks if API server is running on port 8000
2. If NOT running:
   - Starts API server with `DB_URL=sqlite:///./data/e2e.db`
   - **Database used: `e2e.db`** ✅
3. If already running:
   - Uses existing API server
   - **Database depends on how it was started** ⚠️

**Result:** Tests use `e2e.db` (if script starts the server)

---

### Scenario 2: Docker Already Running

**Setup:**
```powershell
docker-compose up
# Docker starts API server with DB_URL=sqlite:///./data/app.db
```

**Then run tests:**
```powershell
npm run test:e2e
```

**What happens:**
1. Tests connect to existing API server (from Docker)
2. Docker API server uses `app.db`
3. **Database used: `app.db`** ❌ (Not ideal!)

**Result:** Tests use `app.db` - might not see seeded test data

---

### Scenario 3: Manual API Server with e2e.db

**Start API server manually:**
```powershell
$env:DB_URL="sqlite:///./data/e2e.db"
python -m uvicorn server.app.main:app --port 8000
```

**Then run tests:**
```powershell
npm run test:e2e
```

**What happens:**
1. Tests connect to existing API server
2. API server uses `e2e.db`
3. **Database used: `e2e.db`** ✅

**Result:** Tests use `e2e.db` correctly

---

### Scenario 4: Manual API Server with app.db (Wrong!)

**Start API server manually:**
```powershell
$env:DB_URL="sqlite:///./data/app.db"  # Or no DB_URL (defaults to app.db)
python -m uvicorn server.app.main:app --port 8000
```

**Then run tests:**
```powershell
npm run test:e2e
```

**What happens:**
1. Tests connect to existing API server
2. API server uses `app.db`
3. **Database used: `app.db`** ❌

**Result:** Tests use `app.db` - will affect your development data!

---

## How to Check Which Database is Being Used

### Method 1: Check API Server Logs

When the API server starts, it reads `DB_URL` environment variable:
- Default: `sqlite:///./data/app.db`
- E2E tests should use: `sqlite:///./data/e2e.db`

Look for the database file path in startup logs.

### Method 2: Check Environment Variables

```powershell
# Check what DB_URL is set to (before starting API server)
echo $env:DB_URL

# Or check Docker container
docker exec tradeagent-api env | grep DB_URL
```

### Method 3: Check Database Files

```powershell
# Check if e2e.db exists and has data
Test-Path data\e2e.db

# Check modification time
(Get-Item data\e2e.db).LastWriteTime
```

### Method 4: Check Seeded Data

If you seeded data into `e2e.db`, try to see it in the UI:
- If you see seeded test signals/orders → Using `e2e.db` ✅
- If you see your development data → Using `app.db` ❌

---

## Recommended Approach

### ✅ Best Practice: Use Test Runner Scripts

**Why:**
- Automatically starts API server with correct database
- Handles cleanup after tests
- Ensures correct configuration

**How:**
```powershell
# This automatically uses e2e.db
.\run-e2e-tests.ps1
```

### ⚠️ If API Server Already Running

**Option A: Stop and let script start it**
```powershell
# Stop Docker or manual API server
docker-compose down
# Or kill the API server process

# Then run tests (script will start API server with e2e.db)
.\run-e2e-tests.ps1
```

**Option B: Check which database it's using**
```powershell
# Check Docker
docker exec tradeagent-api env | grep DB_URL

# If using app.db, you have two choices:
# 1. Stop Docker and use test runner script
# 2. Change Docker to use e2e.db (not recommended)
```

---

## Summary Table

| Scenario | API Server Source | Database Used | Result |
|----------|------------------|---------------|--------|
| Test runner script starts API | Script sets `DB_URL=e2e.db` | `e2e.db` | ✅ Correct |
| Docker already running | Docker sets `DB_URL=app.db` | `app.db` | ❌ Wrong |
| Manual start with e2e.db | You set `DB_URL=e2e.db` | `e2e.db` | ✅ Correct |
| Manual start with app.db | Default or `DB_URL=app.db` | `app.db` | ❌ Wrong |

---

## Quick Decision Tree

```
Are you running E2E tests?
├─ Yes
   ├─ Is API server already running?
   │  ├─ No → Use test runner script (auto-starts with e2e.db) ✅
   │  └─ Yes
   │     ├─ Started by Docker? → Stop Docker first, then use test runner ✅
   │     ├─ Started manually with e2e.db? → Continue, tests will use e2e.db ✅
   │     └─ Started manually with app.db? → Stop it, use test runner ✅
```

---

## Bottom Line

**For E2E tests to use `e2e.db`:**

1. ✅ **Best**: Use `.\run-e2e-tests.ps1` (automatically handles it)
2. ✅ **Alternative**: Start API server manually with `DB_URL=sqlite:///./data/e2e.db`
3. ❌ **Avoid**: Running tests when Docker is using `app.db`

**Remember**: Tests use whatever database the API server is connected to!
