# Full Symbols Migration - Production Deployment Checklist

**Ensure smooth migration deployment in production environment.**

## Pre-Deployment Verification

### ✅ Code Changes Committed
- [x] Migration file `20250117_migrate_positions_to_full_symbols.py` has correct `down_revision`
- [x] Migration file uses correct enum value `'ongoing'` (lowercase)
- [x] All fixes committed to repository

### ✅ Migration Chain Verification
Before deploying, verify the migration chain is correct:
```bash
# Check current database revision
docker exec tradeagent-api python -m alembic current

# Check migration heads (should show only one head)
docker exec tradeagent-api python -m alembic heads

# Verify migration history
docker exec tradeagent-api python -m alembic history
```

**Expected Result**:
- Current revision: `20251213_add_failed_status_to_signalstatus` (or earlier)
- Heads: Should show `20250117_migrate_positions_to_full_symbols` as the only head after deployment

## Production Deployment Steps

### 1. Backup Database (CRITICAL)
```bash
# Create backup before migration
docker exec tradeagent-db pg_dump -U trader tradeagent > backup_before_full_symbols_migration_$(date +%Y%m%d_%H%M%S).sql

# Or if using Docker volume
docker run --rm -v tradeagent_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup_$(date +%Y%m%d_%H%M%S).tar.gz /data
```

### 2. Pull Latest Code
```bash
git pull origin main  # or your production branch
# Verify migration file is present
ls -la alembic/versions/20250117_migrate_positions_to_full_symbols.py
```

### 3. Rebuild API Container
```bash
cd docker
docker-compose -f docker-compose.yml build api-server
```

### 4. Check Migration Status (Before Restart)
```bash
# Check current database state
docker exec tradeagent-db psql -U trader -d tradeagent -c "
SELECT
    COUNT(*) as total_positions,
    COUNT(CASE WHEN symbol LIKE '%-EQ' OR symbol LIKE '%-BE' OR symbol LIKE '%-BL' OR symbol LIKE '%-BZ' THEN 1 END) as full_symbols,
    COUNT(CASE WHEN symbol NOT LIKE '%-EQ' AND symbol NOT LIKE '%-BE' AND symbol NOT LIKE '%-BL' AND symbol NOT LIKE '%-BZ' THEN 1 END) as base_symbols
FROM positions;
"

# Check current Alembic revision
docker exec tradeagent-api python -m alembic current
```

### 5. Restart API Container (Migration Runs Automatically)
```bash
docker-compose -f docker-compose.yml restart api-server

# Monitor logs for migration
docker-compose -f docker-compose.yml logs -f api-server | grep -i migration
```

### 6. Verify Migration Success
```bash
# Check Alembic revision (should be 20250117_migrate_positions_to_full_symbols)
docker exec tradeagent-api python -m alembic current

# Verify all positions now have full symbols
docker exec tradeagent-db psql -U trader -d tradeagent -c "
SELECT
    COUNT(*) as total_positions,
    COUNT(CASE WHEN symbol LIKE '%-EQ' OR symbol LIKE '%-BE' OR symbol LIKE '%-BL' OR symbol LIKE '%-BZ' THEN 1 END) as full_symbols,
    COUNT(CASE WHEN symbol NOT LIKE '%-EQ' AND symbol NOT LIKE '%-BE' AND symbol NOT LIKE '%-BL' AND symbol NOT LIKE '%-BZ' THEN 1 END) as base_symbols
FROM positions;
"

# Sample positions to verify
docker exec tradeagent-db psql -U trader -d tradeagent -c "
SELECT user_id, symbol, quantity, closed_at IS NULL as is_open
FROM positions
ORDER BY user_id, symbol
LIMIT 20;
"
```

## Issues We Fixed (Won't Occur in Production)

### ✅ Issue 1: Multiple Heads Error
**Problem**: Migration had `down_revision = "d1e2f3a4b5c6"` which created a branch.
**Fix**: Changed to `down_revision = "20251213_add_failed_status_to_signalstatus"`.
**Status**: ✅ Fixed in codebase - production will use correct revision.

### ✅ Issue 2: Invalid Enum Value
**Problem**: Migration used `'ONGOING'` (uppercase) but enum value is `'ongoing'` (lowercase).
**Fix**: Changed all occurrences to `'ongoing'`.
**Status**: ✅ Fixed in codebase - production will use correct enum value.

### ✅ Issue 3: Container Missing Updated File
**Problem**: Had to manually copy migration file into container.
**Fix**: File is now in repository, Dockerfile uses `COPY . .` which includes all files.
**Status**: ✅ Fixed - production build will include migration file automatically.

## Rollback Plan (If Needed)

If migration fails or causes issues:

### 1. Stop API Container
```bash
docker-compose -f docker-compose.yml stop api-server
```

### 2. Restore Database Backup
```bash
# Restore from backup
docker exec -i tradeagent-db psql -U trader tradeagent < backup_before_full_symbols_migration_YYYYMMDD_HHMMSS.sql
```

### 3. Downgrade Migration (Optional)
```bash
docker exec tradeagent-api python -m alembic downgrade -1
```

### 4. Revert Code
```bash
git revert <migration-commit-hash>
docker-compose -f docker-compose.yml build api-server
docker-compose -f docker-compose.yml restart api-server
```

## Post-Migration Verification

### Application Functionality
- [ ] Verify positions are displayed correctly in UI
- [ ] Verify sell orders are created correctly
- [ ] Verify manual sell detection works
- [ ] Verify reconciliation works correctly
- [ ] Check logs for any symbol-related errors

### Database Integrity
- [ ] All positions have full symbols (no base symbols remaining)
- [ ] Orders and positions match correctly
- [ ] No orphaned positions
- [ ] No duplicate positions for same symbol

## Troubleshooting

### Migration Doesn't Run
**Symptom**: API starts but migration doesn't execute.
**Check**:
```bash
docker logs tradeagent-api | grep -i migration
docker exec tradeagent-api python -m alembic current
```
**Solution**: Migration may already be applied. Check current revision.

### Multiple Heads Error
**Symptom**: `FAILED: Multiple head revisions are present`
**Cause**: Migration file has incorrect `down_revision`.
**Solution**: Verify migration file in container:
```bash
docker exec tradeagent-api cat alembic/versions/20250117_migrate_positions_to_full_symbols.py | grep down_revision
```
Should show: `down_revision = "20251213_add_failed_status_to_signalstatus"`

### Enum Value Error
**Symptom**: `invalid input value for enum orderstatus: "ONGOING"`
**Cause**: Migration uses uppercase enum value.
**Solution**: Verify migration file uses lowercase `'ongoing'`:
```bash
docker exec tradeagent-api grep -n "status = 'ongoing'" alembic/versions/20250117_migrate_positions_to_full_symbols.py
```

## Notes

- **Migration is idempotent**: Safe to run multiple times (only updates positions without suffixes)
- **Migration is backward compatible**: Old code can still read full symbols (they're just strings)
- **No downtime required**: Migration runs during API startup
- **Automatic rollback**: If migration fails, API startup script continues (but logs warning)
