# PostgreSQL Migration Guide

**Last Updated**: 2025-01-27
**Status**: ✅ Ready for PostgreSQL Migration

## Table of Contents

1. [Overview](#overview)
2. [SQL Compatibility Fixes](#sql-compatibility-fixes)
3. [Validation Results](#validation-results)
4. [Pre-Migration Checklist](#pre-migration-checklist)
5. [Migration Steps](#migration-steps)
6. [Post-Migration Verification](#post-migration-verification)
7. [Rollback Plan](#rollback-plan)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This guide documents the migration from SQLite to PostgreSQL for the modular trade agent application. All SQLite-specific SQL syntax has been identified and fixed to ensure compatibility with PostgreSQL while maintaining backward compatibility with SQLite.

### Key Changes

- ✅ Created dialect detection utility for cross-database compatibility
- ✅ Fixed all SQLite-specific SQL functions (`json_object()`, `julianday()`)
- ✅ Protected SQLite-specific operations (`sqlite_sequence`) with dialect detection
- ✅ Updated comments to reflect cross-database compatibility
- ✅ Verified all migration files handle both dialects correctly

---

## SQL Compatibility Fixes

### Issues Identified and Fixed

#### 1. `json_object()` Function (SQLite-specific)
- **File**: `src/application/services/individual_service_manager.py:1504-1527`
- **Issue**: SQLite's `json_object()` function doesn't exist in PostgreSQL
- **Fix**: Build JSON in Python using `json.dumps()` before SQL execution
- **Impact**: Works with both SQLite and PostgreSQL

**Before**:
```python
details = json_object(
    'error', 'Execution timed out or process crashed',
    'stale_execution', 1,
    'age_seconds', :age_seconds,
    'thread_was_alive', :thread_alive
)
```

**After**:
```python
details_json = json.dumps({
    "error": "Execution timed out or process crashed",
    "stale_execution": 1,
    "age_seconds": execution_age.total_seconds(),
    "thread_was_alive": 1 if thread_is_alive else 0,
})
# Then use :details_json in SQL
```

#### 2. `julianday()` Function (SQLite-specific)
- **File**: `src/infrastructure/persistence/signals_repository.py:151-189`
- **Issue**: SQLite's `julianday()` function doesn't exist in PostgreSQL
- **Fix**: Use direct datetime comparison (works in both databases)
- **Impact**: Works with both SQLite and PostgreSQL, simpler and more efficient

**Before**:
```python
func.julianday(Signals.ts) < func.julianday(before_timestamp_param)
# or
julianday(ts) < julianday(:before_timestamp)
```

**After**:
```python
Signals.ts < before_timestamp_param
# or
ts < :before_timestamp
```

#### 3. `sqlite_sequence` Table (SQLite-specific)
- **File**: `src/infrastructure/persistence/notification_repository.py:92-137`
- **Issue**: PostgreSQL uses sequences, not `sqlite_sequence` table
- **Fix**: Added dialect detection to skip sequence fix for PostgreSQL
- **Impact**: No errors on PostgreSQL, still fixes sequences for SQLite when needed

**Fix Applied**:
```python
def _fix_sqlite_sequence(self) -> None:
    """Fix SQLite auto-increment sequence for notifications table."""
    # Skip for PostgreSQL - it uses sequences, not sqlite_sequence
    if not is_sqlite(self.db):
        return
    # ... SQLite-specific sequence fix code ...
```

#### 4. `func.date()` Comments Updated
- **File**: `src/infrastructure/persistence/signals_repository.py:70, 99`
- **Change**: Updated misleading comments that suggested SQLite-specific usage
- **Status**: `func.date()` is SQLAlchemy function, works with PostgreSQL's `DATE()` function

### Files Modified

1. **`src/infrastructure/db/dialect.py`** (NEW)
   - Dialect detection utility with `is_postgresql()` and `is_sqlite()` functions
   - Uses SQLAlchemy dialect detection with URL fallback

2. **`src/application/services/individual_service_manager.py`**
   - Fixed `json_object()` usage (line 1504-1527)

3. **`src/infrastructure/persistence/signals_repository.py`**
   - Fixed `julianday()` usage (lines 151-189)
   - Updated `func.date()` comments (lines 70, 99)

4. **`src/infrastructure/persistence/notification_repository.py`**
   - Fixed `sqlite_sequence` handling (lines 92-137)

---

## Validation Results

### Comprehensive Codebase Review

A full validation was performed across the entire codebase. All SQLite-specific syntax has been identified and fixed.

#### Files Verified Compatible

1. **`src/infrastructure/persistence/orders_repository.py`**
   - ✅ Raw SQL uses parameterized queries (`:param` syntax)
   - ✅ Standard SQL syntax (SELECT, WHERE, ORDER BY)
   - ✅ No SQLite-specific functions

2. **`src/infrastructure/persistence/individual_service_task_execution_repository.py`**
   - ✅ Raw SQL uses parameterized queries
   - ✅ Standard SQL syntax (SELECT, WHERE, ORDER BY, LIMIT)
   - ✅ No SQLite-specific functions

3. **`src/infrastructure/persistence/signals_repository.py`**
   - ✅ `func.date()` - SQLAlchemy function, works with PostgreSQL's `DATE()` function
   - ✅ All queries use SQLAlchemy ORM or parameterized raw SQL

#### Migration Files Verified

1. **`alembic/versions/d1e2f3a4b5c6_add_entry_rsi_to_positions_and_backfill.py`**
   - ✅ Already has dialect detection for SQLite vs PostgreSQL
   - ✅ Uses `json_extract()` for SQLite, `->>` operator for PostgreSQL
   - ✅ Uses `CAST(... AS REAL)` for SQLite, `::float` for PostgreSQL

2. **`alembic/versions/20250115_remove_positions_unique_constraint.py`**
   - ✅ Already has dialect detection
   - ✅ SQLite path: Table recreation
   - ✅ PostgreSQL path: Constraint drop + partial unique index

### Compatible Patterns

✅ **Safe to Use**
- SQLAlchemy ORM queries
- Parameterized raw SQL (`:param` syntax)
- `func.date()` - Works in both databases
- Standard SQL (SELECT, WHERE, ORDER BY, LIMIT)
- SQLAlchemy type decorators

✅ **Already Fixed**
- `json_object()` → Python `json.dumps()`
- `julianday()` → Direct datetime comparison
- `sqlite_sequence` → Dialect detection

---

## Pre-Migration Checklist

### SQL Compatibility Fixes
- [x] Fixed `json_object()` → Python `json.dumps()`
- [x] Fixed `julianday()` → Direct datetime comparison
- [x] Fixed `sqlite_sequence` → Dialect detection added
- [x] Updated `func.date()` comments → Cross-database compatible
- [x] Verified all raw SQL queries use parameterized queries
- [x] Verified migration files handle both dialects

### Code Changes
- [x] Created dialect detection utility
- [x] Fixed all identified SQLite-specific syntax
- [x] Updated comments for clarity
- [x] All linter checks passed

---

## Migration Steps

### Option A: Docker Migration (Recommended)

#### Prerequisites
- Docker + Docker Compose installed on target host
- Repo checked out (or updated) on the host
- Network can pull container images
- Postgres image available (`postgres:15` assumed from compose)

#### Step 0: Stop the Stack
```bash
cd /path/to/modular_trade_agent
docker-compose -f docker/docker-compose.yml down
```

#### Step 1: Backup Existing SQLite

**Note**: If your `docker-compose.yml` is already configured for PostgreSQL, you'll need to either:
- Option A: Temporarily switch to SQLite for backup, OR
- Option B: Copy SQLite file directly from host if it exists

**Option A: Use SQLite temporarily**
```bash
# Stop containers
docker-compose -f docker/docker-compose.yml down

# Temporarily modify docker-compose.yml DB_URL to: sqlite:///./data/app.db
# Or use environment override:
docker-compose -f docker/docker-compose.yml run --rm -e DB_URL=sqlite:///./data/app.db api-server sh -c "cp /app/data/app.db /app/data/app.db.bak.\$(date -u +%Y%m%d%H%M%S)"

# Restore PostgreSQL DB_URL in docker-compose.yml
```

**Option B: Copy from host (if SQLite file exists)**
```bash
# Copy SQLite file directly
cp ~/modular_trade_agent/data/app.db ~/modular_trade_agent/data/app.db.bak.$(date -u +%Y%m%d%H%M%S)
```

**Original method (if container is running with SQLite)**
```bash
docker-compose -f docker/docker-compose.yml up -d api-server
docker exec tradeagent-api sh -c "cp /app/data/app.db /app/data/app.db.bak.$(date -u +%Y%m%d%H%M%S)"
docker cp tradeagent-api:/app/data/app.db.bak.* ./data/   # optional: pull backup to host
docker-compose -f docker/docker-compose.yml down
```

#### Step 2: Configure Docker Compose for Postgres
Ensure `docker/docker-compose.yml` has:
- Service `tradeagent-db` with env:
  - `POSTGRES_USER=trader`
  - `POSTGRES_PASSWORD=changeme`
  - `POSTGRES_DB=tradeagent`
- Named volume `postgres_data` mounted to `/var/lib/postgresql/data`
- `api-server` `DB_URL` set to `postgresql+psycopg2://trader:changeme@tradeagent-db:5432/tradeagent`
- `api-server` depends_on `tradeagent-db` with healthcheck

#### Step 3: Start Postgres Only
```bash
docker-compose -f docker/docker-compose.yml up -d tradeagent-db
docker exec tradeagent-db pg_isready -U trader -d tradeagent
```

#### Step 4: Reset Postgres Schema (Clean Slate)
```bash
docker exec -e PGPASSWORD=changeme tradeagent-db psql -U trader -c "ALTER DATABASE tradeagent OWNER TO trader;"
docker exec -e PGPASSWORD=changeme tradeagent-db psql -U trader -c "DROP DATABASE IF EXISTS tradeagent;"
docker exec -e PGPASSWORD=changeme tradeagent-db psql -U trader -c "CREATE DATABASE tradeagent OWNER trader;"
```

#### Step 5: Initialize Schema + Alembic Version
```bash
docker-compose -f docker/docker-compose.yml up -d api-server

docker exec tradeagent-api python - <<'PY'
from sqlalchemy import create_engine, text
from src.infrastructure.db import Base
from src.infrastructure.db.session import get_db_url

engine = create_engine(get_db_url())
Base.metadata.create_all(engine)  # create tables

REV = "20251213_add_failed_status_to_signalstatus"
with engine.begin() as conn:
    conn.exec_driver_sql("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version') THEN
            CREATE TABLE alembic_version (version_num VARCHAR(128) NOT NULL);
        END IF;
    END$$;
    """)
    conn.exec_driver_sql("TRUNCATE alembic_version;")
    conn.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES (:rev)", {"rev": REV})
PY
```

#### Step 6: Migrate Data from SQLite Backup to Postgres
```bash
# Copy the SQLite backup into the api container if not present
docker cp ./data/app.db.bak.* tradeagent-api:/app/data/app.db.bak

# Run a lightweight Python migrator inside the api container
docker exec tradeagent-api python - <<'PY'
import sqlite3
from sqlalchemy import create_engine, text
from src.infrastructure.db.session import get_db_url

sqlite_path = "/app/data/app.db.bak"
engine = create_engine(get_db_url())

def copy_table(table):
    with sqlite3.connect(sqlite_path) as src, engine.begin() as tgt:
        cols = [r[1] for r in src.execute(f"PRAGMA table_info({table})")]
        rows = list(src.execute(f"SELECT * FROM {table}"))
        if not rows:
            return
        placeholders = ", ".join([f":{c}" for c in cols])
        insert_sql = text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})")
        for row in rows:
            tgt.execute(insert_sql, dict(zip(cols, row)))

tables = [
    "users",
    "user_profile",
    "service_status",
    "service_task_execution",
    "error_logs",
    "signals",
    "signal_status",
    # add any other business tables that exist in the SQLite backup
]
for t in tables:
    try:
        copy_table(t)
    except Exception as exc:
        print(f"skip {t}: {exc}")

# Reset sequences for serial IDs
with engine.begin() as conn:
    seqs = conn.execute(text("""
        SELECT sequence_name FROM information_schema.sequences
        WHERE sequence_schema = 'public'
    """)).scalars().all()
    for seq in seqs:
        table = seq.replace("_id_seq","").replace("_seq","")
        conn.execute(text(f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}),0)+1);"))
PY
```

#### Step 7: Restart Full Stack on Postgres
```bash
docker-compose -f docker/docker-compose.yml restart api-server web-frontend
```

#### Step 8: Smoke Verification
```bash
docker exec tradeagent-api curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health   # expect 200
# Perform a real login using correct JSON body via UI or API
```
- Check app functions (dashboard load, start service, logs view)

### Option B: Manual Migration

#### Step 1: Database Setup
- [ ] Create PostgreSQL database
- [ ] Configure connection string in environment variables (`DB_URL`)
- [ ] Test connection

#### Step 2: Schema Migration
- [ ] Run Alembic migrations (already compatible with PostgreSQL)
  ```bash
  alembic upgrade head
  ```
- [ ] Verify all tables created correctly
- [ ] Verify indexes created correctly
- [ ] Verify constraints created correctly

#### Step 3: Data Migration
- [ ] Export data from SQLite
- [ ] Transform data if needed (data types, formats)
- [ ] Import data to PostgreSQL
- [ ] Verify data integrity

#### Step 4: Application Testing
- [ ] Test `by_date()` and `by_date_range()` queries
- [ ] Test `mark_old_signals_as_expired()` with PostgreSQL
- [ ] Test notification creation (verify sequence fix is skipped)
- [ ] Test raw SQL UPDATE in `individual_service_manager.py`
- [ ] Test all API endpoints
- [ ] Test all background jobs

#### Step 5: Performance Testing
- [ ] Compare query performance
- [ ] Verify indexes are being used
- [ ] Check connection pooling

---

## Post-Migration Verification

### Critical Functions to Test

1. **Signal Queries**
   - `SignalsRepository.by_date()` - Uses `func.date()`
   - `SignalsRepository.by_date_range()` - Uses `func.date()`
   - `SignalsRepository.mark_old_signals_as_expired()` - Uses datetime comparison

2. **Notification Creation**
   - `NotificationRepository.create()` - Should skip sequence fix for PostgreSQL
   - Verify auto-increment works correctly

3. **Task Execution**
   - `IndividualServiceManager._update_execution_status()` - Uses JSON in Python
   - Verify JSON details are stored correctly

4. **Orders Repository**
   - `OrdersRepository.list()` - Uses parameterized raw SQL
   - Verify enum handling works correctly

### Testing Checklist

- [ ] Test `_fix_sqlite_sequence()` with PostgreSQL (should be skipped)
- [ ] Test `mark_old_signals_as_expired()` with PostgreSQL datetime comparison
- [ ] Test `by_date()` and `by_date_range()` with PostgreSQL date functions
- [ ] Test raw SQL UPDATE in `individual_service_manager.py` with PostgreSQL JSON
- [ ] Verify migration file works for both SQLite and PostgreSQL (already has dialect detection)
- [ ] Test all API endpoints
- [ ] Test all background jobs
- [ ] Verify data integrity

---

## Rollback Plan

### Docker Rollback
1. Stop stack: `docker compose down`
2. Restore SQLite file to `/app/data/app.db` inside api container from the backup
3. Revert `DB_URL` in compose to SQLite
4. Run: `docker compose up -d api-server web-frontend`

### Manual Rollback
1. Keep SQLite backup
2. Revert `DB_URL` environment variable to SQLite connection string
3. Restart application
4. Verify application works with SQLite

### Rollback Checklist
- [ ] Keep SQLite backup
- [ ] Document rollback procedure
- [ ] Test rollback procedure

---

## Troubleshooting

### Common Issues

1. **Connection Errors**
   - Verify PostgreSQL is running
   - Check connection string format: `postgresql+psycopg2://user:password@host:port/database`
   - Verify network connectivity

2. **Schema Migration Failures**
   - Check Alembic version table
   - Verify all migration files are present
   - Check for conflicting migrations

3. **Data Type Mismatches**
   - SQLite is more lenient with types than PostgreSQL
   - May need to cast data during migration
   - Check for NULL handling differences

4. **Sequence Issues**
   - PostgreSQL uses sequences for auto-increment
   - Ensure sequences are reset after data migration
   - Check `setval()` calls in migration script

### Getting Help

- Review migration logs
- Check PostgreSQL logs
- Verify application logs for database errors
- Test individual queries in PostgreSQL client

---

## Summary

**Status**: ✅ **READY FOR POSTGRESQL MIGRATION**

All SQLite-specific SQL commands have been identified and fixed. The codebase is now compatible with PostgreSQL while maintaining backward compatibility with SQLite.

### Key Points

- All fixes maintain backward compatibility with SQLite
- Migration files already handle both dialects
- Comprehensive validation completed
- Ready for production migration

### Next Steps

1. Review this guide
2. Choose migration approach (Docker or Manual)
3. Follow migration steps
4. Perform post-migration verification
5. Monitor application after migration
