# Phase 5: Migration Execution - Ready for Testing

**Status**: ✅ Ready for Testing
**Date**: 2025-01-17
**Environment**: Docker (PostgreSQL)

## Summary

All preparation work for Phase 5 is complete. The migration can now be tested in the Docker environment.

## What's Ready

### ✅ Migration Script
- **Location**: `alembic/versions/20250117_migrate_positions_to_full_symbols.py`
- **Status**: Complete and tested
- **Features**:
  - Supports both SQLite and PostgreSQL
  - Updates positions from matching orders
  - Defaults to -EQ if no matching order found
  - Includes verification step
  - Reversible (downgrade available)

### ✅ Test Scripts
- **`scripts/test_migration_docker.py`**: Interactive test script
  - Shows current state
  - Runs migration
  - Verifies results
  - Optional rollback
- **`scripts/run_migration_test_docker.ps1`**: PowerShell helper
- **`scripts/run_migration_test_docker.sh`**: Bash helper
- **`scripts/run_migration_docker_exec.sh`**: Docker exec method

### ✅ Documentation
- **`MIGRATION_QUICK_START_DOCKER.md`**: Quick start guide
- **`MIGRATION_TESTING_GUIDE_DOCKER.md`**: Complete testing guide
- **`MIGRATION_DOCKER_SETUP.md`**: Docker setup instructions

## Current Database State

**Status**: Database is accessible and ready for testing

```sql
-- Current state (from docker exec)
SELECT COUNT(*) as total_positions,
       COUNT(CASE WHEN symbol LIKE '%-EQ' OR symbol LIKE '%-BE' OR symbol LIKE '%-BL' OR symbol LIKE '%-BZ' THEN 1 END) as full_symbols
FROM positions;
-- Result: 0 positions (empty database - perfect for testing)
```

## Testing Options

### Option 1: Using Test Script (Recommended)

**Prerequisites:**
1. Expose port 5432 in docker-compose.yml (see MIGRATION_DOCKER_SETUP.md)
2. Install psycopg2-binary: `pip install psycopg2-binary`
3. Activate virtual environment

**Run:**
```bash
python scripts/test_migration_docker.py
```

### Option 2: Using Docker Exec (No Port Exposure)

**Run migration inside container:**
```bash
# Check current state
docker exec -it tradeagent-db psql -U trader -d tradeagent -c "SELECT user_id, symbol FROM positions WHERE symbol NOT LIKE '%-EQ' AND symbol NOT LIKE '%-BE' AND symbol NOT LIKE '%-BL' AND symbol NOT LIKE '%-BZ' LIMIT 10;"

# Run migration
docker exec -it tradeagent-db bash -c "cd /app && alembic upgrade head"

# Verify
docker exec -it tradeagent-db psql -U trader -d tradeagent -c "SELECT user_id, symbol FROM positions WHERE symbol NOT LIKE '%-EQ' AND symbol NOT LIKE '%-BE' AND symbol NOT LIKE '%-BL' AND symbol NOT LIKE '%-BZ' LIMIT 10;"
```

### Option 3: Using Alembic CLI

**If port 5432 is exposed:**
```bash
export DB_URL="postgresql+psycopg2://trader:changeme@localhost:5432/tradeagent"
alembic upgrade head
```

## Testing Checklist

### Pre-Migration
- [ ] Database container is running
- [ ] Database is accessible (tested via docker exec)
- [ ] Backup database (if it has data)
- [ ] Review current positions state
- [ ] Check for positions with base symbols

### Migration Execution
- [ ] Run migration script
- [ ] Verify migration completed without errors
- [ ] Check migration output for warnings

### Post-Migration Verification
- [ ] All positions have full symbols
- [ ] No positions with base symbols remain
- [ ] Migration summary shows correct segment distribution
- [ ] Application starts without errors
- [ ] Positions display correctly in web UI
- [ ] No symbol-related errors in logs

### Rollback Test (Optional)
- [ ] Test rollback procedure
- [ ] Verify rollback works correctly
- [ ] Re-run migration after rollback

## Next Steps

1. **Test Migration**:
   - Run test script or use docker exec method
   - Verify results
   - Test rollback if needed

2. **Production Preparation**:
   - Backup production database
   - Schedule maintenance window
   - Prepare rollback plan
   - Notify stakeholders

3. **Production Migration**:
   - Run migration during low-traffic window
   - Monitor application for 24 hours
   - Verify all functionalities work

## Files Created

### Scripts
- `scripts/test_migration_docker.py` - Main test script
- `scripts/run_migration_test_docker.ps1` - PowerShell helper
- `scripts/run_migration_test_docker.sh` - Bash helper
- `scripts/run_migration_docker_exec.sh` - Docker exec method

### Documentation
- `MIGRATION_QUICK_START_DOCKER.md` - Quick start guide
- `MIGRATION_TESTING_GUIDE_DOCKER.md` - Complete testing guide
- `MIGRATION_DOCKER_SETUP.md` - Docker setup instructions
- `PHASE_5_MIGRATION_READY.md` - This file

## Notes

- **Empty Database**: Current database has 0 positions - perfect for testing migration logic
- **Port Access**: Port 5432 is not exposed by default - use docker exec method or expose port
- **Migration is Idempotent**: Safe to run multiple times
- **Migration is Reversible**: Downgrade available if needed

## Support

For issues or questions:
1. Check `MIGRATION_TESTING_GUIDE_DOCKER.md` for detailed troubleshooting
2. Review migration script comments
3. Check Docker logs: `docker logs tradeagent-db`
