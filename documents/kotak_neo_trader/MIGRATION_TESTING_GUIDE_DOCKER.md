# Full Symbols Migration - Testing Guide (Docker)

**Date**: 2025-01-17
**Environment**: Docker (PostgreSQL)
**Purpose**: Test the full symbols migration before production deployment

## Prerequisites

1. **Docker is running**
   ```bash
   docker info
   ```

2. **Database container is running**
   ```bash
   docker-compose -f docker/docker-compose.yml up -d tradeagent-db
   ```

3. **Database is accessible**
   - Default connection: `postgresql+psycopg2://trader:changeme@localhost:5432/tradeagent`
   - Port 5432 should be accessible from host

## Pre-Migration Checklist

### 1. Backup Database

**Option A: Docker volume backup**
```bash
# Create backup
docker run --rm \
  -v tradeagent_postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .

# Or on Windows PowerShell:
docker run --rm `
  -v tradeagent_postgres_data:/data `
  -v ${PWD}:/backup `
  alpine tar czf /backup/postgres_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').tar.gz -C /data .
```

**Option B: pg_dump (if PostgreSQL client is installed)**
```bash
docker exec tradeagent-db pg_dump -U trader tradeagent > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Option C: Using Docker exec**
```bash
docker exec tradeagent-db pg_dumpall -U trader > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 2. Check Current State

Run the test script to see current state:
```bash
python scripts/test_migration_docker.py
```

This will show:
- Total positions
- Positions with base symbols (need migration)
- Positions with full symbols (already migrated)
- Matching orders for base symbols

### 3. Review Active Positions

Check which positions will be affected:
```bash
# Connect to database
docker exec -it tradeagent-db psql -U trader -d tradeagent

# Query positions with base symbols
SELECT user_id, symbol, quantity, avg_price, closed_at
FROM positions
WHERE symbol NOT LIKE '%-EQ'
  AND symbol NOT LIKE '%-BE'
  AND symbol NOT LIKE '%-BL'
  AND symbol NOT LIKE '%-BZ'
ORDER BY user_id, symbol;
```

## Migration Testing Steps

### Step 1: Run Test Script

```bash
# From project root
python scripts/test_migration_docker.py
```

The script will:
1. Show current state
2. Ask for confirmation
3. Run migration
4. Verify results
5. Optionally rollback

### Step 2: Verify Migration Results

After migration, verify:

```sql
-- Check all positions have full symbols
SELECT COUNT(*) as total,
       COUNT(CASE WHEN symbol LIKE '%-EQ' OR symbol LIKE '%-BE' OR symbol LIKE '%-BL' OR symbol LIKE '%-BZ' THEN 1 END) as full_symbols,
       COUNT(CASE WHEN symbol NOT LIKE '%-EQ' AND symbol NOT LIKE '%-BE' AND symbol NOT LIKE '%-BL' AND symbol NOT LIKE '%-BZ' THEN 1 END) as base_symbols
FROM positions;

-- Should show: base_symbols = 0
```

### Step 3: Test Application

1. **Start API server** (if not running):
   ```bash
   docker-compose -f docker/docker-compose.yml up -d api-server
   ```

2. **Check logs** for any symbol-related errors:
   ```bash
   docker logs tradeagent-api --tail 100
   ```

3. **Test key functionalities**:
   - View positions in web UI
   - Check reconciliation
   - Verify order placement
   - Test manual sell detection

### Step 4: Rollback Test (Optional)

Test rollback to ensure it works:
```bash
python scripts/test_migration_docker.py --rollback
```

This will:
1. Run migration
2. Verify results
3. Rollback migration
4. Verify rollback

## Manual Migration (Alternative)

If you prefer to run migration manually:

### Using Alembic CLI

```bash
# Set database URL
export DB_URL="postgresql+psycopg2://trader:changeme@localhost:5432/tradeagent"

# Run migration
alembic upgrade head

# Or specific revision
alembic upgrade 20250117_migrate_positions_to_full_symbols
```

### Using Python Script

```python
from alembic import command
from alembic.config import Config

alembic_cfg = Config("alembic.ini")
alembic_cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg2://trader:changeme@localhost:5432/tradeagent")

command.upgrade(alembic_cfg, "head")
```

## Verification Queries

### Check Migration Status

```sql
-- All positions should have full symbols
SELECT user_id, symbol, quantity
FROM positions
WHERE symbol NOT LIKE '%-EQ'
  AND symbol NOT LIKE '%-BE'
  AND symbol NOT LIKE '%-BL'
  AND symbol NOT LIKE '%-BZ';
-- Should return 0 rows
```

### Check Symbol Distribution

```sql
-- Distribution by segment
SELECT
    CASE
        WHEN symbol LIKE '%-EQ' THEN 'EQ'
        WHEN symbol LIKE '%-BE' THEN 'BE'
        WHEN symbol LIKE '%-BL' THEN 'BL'
        WHEN symbol LIKE '%-BZ' THEN 'BZ'
        ELSE 'UNKNOWN'
    END as segment,
    COUNT(*) as count
FROM positions
GROUP BY segment
ORDER BY count DESC;
```

### Verify Order Matching

```sql
-- Check positions have matching orders
SELECT
    p.user_id,
    p.symbol as position_symbol,
    o.symbol as order_symbol,
    o.status
FROM positions p
LEFT JOIN orders o ON o.user_id = p.user_id
    AND o.side = 'buy'
    AND o.status = 'ONGOING'
    AND o.symbol = p.symbol  -- Exact match after migration
WHERE p.closed_at IS NULL
ORDER BY p.user_id, p.symbol;
```

## Troubleshooting

### Issue: Migration fails with "table does not exist"

**Solution**: Ensure positions table exists:
```sql
SELECT table_name FROM information_schema.tables WHERE table_name = 'positions';
```

### Issue: Migration completes but positions still have base symbols

**Possible causes**:
1. No matching orders found (positions defaulted to -EQ)
2. Migration script bug

**Check**:
```sql
-- Check positions without matching orders
SELECT p.user_id, p.symbol
FROM positions p
WHERE p.symbol LIKE '%-EQ'
  AND NOT EXISTS (
      SELECT 1 FROM orders o
      WHERE o.user_id = p.user_id
        AND o.side = 'buy'
        AND o.status = 'ONGOING'
        AND UPPER(SPLIT_PART(o.symbol, '-', 1)) = UPPER(SPLIT_PART(p.symbol, '-', 1))
  );
```

### Issue: Cannot connect to database

**Check**:
1. Database container is running: `docker ps | grep tradeagent-db`
2. Port 5432 is accessible: `telnet localhost 5432`
3. Credentials are correct (trader/changeme)

**Fix**:
```bash
# Restart database
docker-compose -f docker/docker-compose.yml restart tradeagent-db

# Check logs
docker logs tradeagent-db
```

## Rollback Procedure

If migration causes issues:

### Option 1: Using Test Script

```bash
python scripts/test_migration_docker.py --rollback
```

### Option 2: Using Alembic CLI

```bash
export DB_URL="postgresql+psycopg2://trader:changeme@localhost:5432/tradeagent"
alembic downgrade d1e2f3a4b5c6
```

### Option 3: Restore from Backup

```bash
# Restore from pg_dump backup
docker exec -i tradeagent-db psql -U trader -d tradeagent < backup_YYYYMMDD_HHMMSS.sql
```

## Post-Migration Validation

After successful migration:

1. ✅ All positions have full symbols
2. ✅ Application starts without errors
3. ✅ Positions display correctly in web UI
4. ✅ Reconciliation works correctly
5. ✅ Order placement works
6. ✅ Manual sell detection works
7. ✅ No symbol-related errors in logs

## Production Deployment

Once testing is successful:

1. **Backup production database** (critical!)
2. **Schedule maintenance window** (low-traffic period)
3. **Run migration** using same procedure
4. **Monitor logs** for 24 hours
5. **Verify all functionalities** work correctly

## Notes

- Migration is **idempotent**: Safe to run multiple times
- Migration is **reversible**: Downgrade available
- Default segment is **-EQ** if no matching order found
- Migration handles both **SQLite** and **PostgreSQL**
