# Full Symbols Migration - Quick Start (Docker)

**Quick guide to test the migration in Docker environment.**

## Prerequisites

1. **Docker is running**
   ```bash
   docker info
   ```

2. **Database container is running**
   ```bash
   docker ps | grep tradeagent-db
   ```

   If not running:
   ```bash
   docker-compose -f docker/docker-compose.yml up -d tradeagent-db
   ```

3. **Python dependencies installed**
   ```bash
   # Activate virtual environment
   .venv\Scripts\activate  # Windows
   # or
   source .venv/bin/activate  # Linux/Mac

   # Install dependencies (if not already installed)
   pip install -r requirements.txt
   ```

## Quick Test

### Option 1: Using Test Script (Recommended)

**Windows (PowerShell):**
```powershell
.venv\Scripts\python.exe scripts\test_migration_docker.py
```

**Linux/Mac:**
```bash
python scripts/test_migration_docker.py
```

**Or use helper script:**
```powershell
# Windows
.\scripts\run_migration_test_docker.ps1

# Linux/Mac
./scripts/run_migration_test_docker.sh
```

### Option 2: Using Alembic CLI

```bash
# Set database URL
$env:DB_URL = "postgresql+psycopg2://trader:changeme@localhost:5432/tradeagent"  # PowerShell
# or
export DB_URL="postgresql+psycopg2://trader:changeme@localhost:5432/tradeagent"  # Bash

# Check current state
docker exec -it tradeagent-db psql -U trader -d tradeagent -c "SELECT COUNT(*) as total, COUNT(CASE WHEN symbol LIKE '%-EQ' OR symbol LIKE '%-BE' OR symbol LIKE '%-BL' OR symbol LIKE '%-BZ' THEN 1 END) as full_symbols FROM positions;"

# Run migration
alembic upgrade head

# Verify
docker exec -it tradeagent-db psql -U trader -d tradeagent -c "SELECT user_id, symbol FROM positions WHERE symbol NOT LIKE '%-EQ' AND symbol NOT LIKE '%-BE' AND symbol NOT LIKE '%-BL' AND symbol NOT LIKE '%-BZ' LIMIT 10;"
```

## What the Test Script Does

1. **Connects to Docker database** (default: `postgresql+psycopg2://trader:changeme@localhost:5432/tradeagent`)
2. **Shows current state**:
   - Total positions
   - Positions with base symbols (need migration)
   - Positions with full symbols (already migrated)
   - Matching orders for base symbols
3. **Asks for confirmation** before running migration
4. **Runs migration** using Alembic
5. **Verifies results**:
   - All positions have full symbols
   - Migration summary by segment
6. **Optionally rolls back** (if `--rollback` flag is used)

## Test with Rollback

To test migration and then rollback:

```bash
python scripts/test_migration_docker.py --rollback
```

## Custom Database URL

If using a different database URL:

```bash
python scripts/test_migration_docker.py --db-url "postgresql+psycopg2://user:pass@host:port/dbname"
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'psycopg2'"

**Solution:**
```bash
pip install psycopg2-binary
```

Or activate virtual environment:
```bash
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

### Issue: "Failed to connect to database"

**Check:**
1. Database container is running: `docker ps | grep tradeagent-db`
2. Port 5432 is accessible: `telnet localhost 5432` (or `Test-NetConnection localhost -Port 5432` on Windows)
3. Credentials are correct (default: trader/changeme)

**Fix:**
```bash
# Restart database
docker-compose -f docker/docker-compose.yml restart tradeagent-db

# Check logs
docker logs tradeagent-db
```

### Issue: "Positions table does not exist"

**Solution:** This is normal if the database is empty. Migration will be skipped safely.

## Next Steps

After successful testing:

1. **Backup production database** (critical!)
2. **Review migration results** from test run
3. **Schedule production migration** during low-traffic window
4. **Run migration on production** using same procedure
5. **Monitor application** for 24 hours after migration

## Full Documentation

For detailed information, see:
- `MIGRATION_TESTING_GUIDE_DOCKER.md` - Complete testing guide
- `FULL_SYMBOLS_MIGRATION_PLAN.md` - Full migration plan
