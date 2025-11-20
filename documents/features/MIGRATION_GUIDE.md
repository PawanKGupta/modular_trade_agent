# Unified Order Monitoring - Migration Guide

This guide covers the steps to complete the migration and enable all new features.

## Prerequisites

1. Ensure all 11 phases are complete and tested
2. Backup your database
3. Review the implementation summary

## Step 1: Apply Database Indexes Migration

The indexes migration improves query performance for order lookups.

### Using Alembic

```bash
# Check current migration status
alembic current

# Apply the indexes migration
alembic upgrade c9d8e7f6g5h6

# Verify indexes were created
alembic history
```

### Manual SQL (if Alembic fails)

```sql
-- Check existing indexes
SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='orders';

-- Add indexes for broker_order_id and order_id
CREATE INDEX IF NOT EXISTS ix_orders_broker_order_id ON orders(broker_order_id);
CREATE INDEX IF NOT EXISTS ix_orders_order_id ON orders(order_id);

-- Add composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS ix_orders_user_broker_order_id ON orders(user_id, broker_order_id);
CREATE INDEX IF NOT EXISTS ix_orders_user_order_id ON orders(user_id, order_id);

-- Verify indexes
SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='orders';
```

### Expected Indexes

After migration, you should have these indexes on the `orders` table:
- `ix_orders_broker_order_id`
- `ix_orders_order_id`
- `ix_orders_user_broker_order_id`
- `ix_orders_user_order_id`

## Step 2: Enable DB-Only Mode

DB-only mode removes JSON dependency and uses only the database for order tracking.

### Option A: Environment Variable

Set an environment variable:

```bash
# Linux/Mac
export ORDER_TRACKER_DB_ONLY_MODE=true

# Windows
set ORDER_TRACKER_DB_ONLY_MODE=true
```

### Option B: Configuration File

Update your configuration file:

```python
# config.py or settings
ORDER_TRACKER_DB_ONLY_MODE = True
```

### Option C: Update Code Directly

Update `OrderTracker` initialization in your code:

```python
# Before
order_tracker = OrderTracker(
    data_dir="data",
    db_session=db_session,
    user_id=user_id,
    use_db=True,
)

# After
order_tracker = OrderTracker(
    data_dir="data",
    db_session=db_session,
    user_id=user_id,
    use_db=True,
    db_only_mode=True,  # Enable DB-only mode
)
```

### Locations to Update

1. **OrderTracker initialization** in `modules/kotak_neo_auto_trader/order_tracker.py`
2. **OrderStateManager** initialization (if it creates OrderTracker)
3. **TradingService** initialization (if it creates OrderTracker)

### Verification

After enabling DB-only mode:

1. Verify no JSON reads/writes occur:
   ```bash
   # Check logs for "DB-only mode" messages
   grep "DB-only mode" logs/*.log
   ```

2. Verify JSON file is not accessed:
   - `data/pending_orders.json` should not be modified
   - Only DB operations should occur

3. Test order operations:
   - Place a test order
   - Verify it appears in DB only
   - Check that no JSON updates occur

## Step 3: Cleanup Pending Orders JSON

After verifying DB-only mode works, clean up the old JSON file.

### Backup First

```bash
# Run cleanup script with backup only
python scripts/cleanup_pending_orders_json.py --file data/pending_orders.json
```

### Review Backup

Check the backup file:
- `data/pending_orders.json.backup.<timestamp>`
- Verify all orders are in the database

### Remove JSON File

```bash
# Remove after backup
python scripts/cleanup_pending_orders_json.py --file data/pending_orders.json --remove

# Or with dry-run first
python scripts/cleanup_pending_orders_json.py --file data/pending_orders.json --remove --dry-run
```

### Manual Cleanup

If you prefer manual cleanup:

```bash
# Create backup
cp data/pending_orders.json data/pending_orders.json.backup.$(date +%Y%m%d_%H%M%S)

# Verify orders are in DB
# Then remove JSON file
rm data/pending_orders.json
```

## Step 4: Verify Migration

### Database Verification

1. **Check order statuses**:
   ```sql
   SELECT status, COUNT(*) 
   FROM orders 
   GROUP BY status;
   ```

2. **Check indexes**:
   ```sql
   SELECT name FROM sqlite_master 
   WHERE type='index' AND tbl_name='orders';
   ```

3. **Check order tracking fields**:
   ```sql
   SELECT COUNT(*) 
   FROM orders 
   WHERE broker_order_id IS NOT NULL OR order_id IS NOT NULL;
   ```

### Functional Verification

1. **Test order placement**:
   - Place a test order
   - Verify it appears in database
   - Check status updates work

2. **Test order monitoring**:
   - Verify orders are loaded at market open
   - Check status updates during market hours
   - Verify notifications are sent

3. **Test retry queue**:
   - Create a failed order
   - Verify it appears in retry queue
   - Test retry/drop actions

4. **Test statistics API**:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
        http://localhost:8000/api/v1/user/orders/statistics
   ```

## Step 5: Performance Testing (Optional)

Run the performance test script to verify query performance:

```bash
python scripts/performance_test_order_queries.py
```

This will test:
- Order lookup by broker_order_id
- Order lookup by order_id
- Status distribution queries
- Order statistics queries

Expected results:
- Query time < 100ms for single order lookup
- Query time < 500ms for statistics queries
- Index usage confirmed in query plans

## Troubleshooting

### Migration Issues

**Issue**: Alembic migration fails
- **Solution**: Use manual SQL commands from Step 1

**Issue**: Indexes already exist
- **Solution**: Migration is idempotent, safe to run again

### DB-Only Mode Issues

**Issue**: Orders not appearing after enabling DB-only mode
- **Check**: Verify orders are in database
- **Check**: Verify `db_only_mode=True` is set correctly
- **Check**: Verify DB session is properly initialized

**Issue**: Errors about JSON file not found
- **Solution**: This is expected in DB-only mode. JSON file is not needed.

### Cleanup Issues

**Issue**: Backup file not created
- **Solution**: Check file permissions
- **Solution**: Ensure data directory exists

**Issue**: Orders missing after cleanup
- **Solution**: Restore from backup
- **Solution**: Verify orders are in database before cleanup

## Rollback Plan

If you need to rollback:

1. **Disable DB-only mode**:
   ```python
   db_only_mode=False
   ```

2. **Restore JSON file**:
   ```bash
   cp data/pending_orders.json.backup.<timestamp> data/pending_orders.json
   ```

3. **Verify system works**:
   - Test order operations
   - Verify JSON reads/writes occur

## Post-Migration Checklist

- [ ] Database indexes created
- [ ] DB-only mode enabled (optional)
- [ ] JSON file backed up
- [ ] JSON file removed (if DB-only mode enabled)
- [ ] All orders accessible via API
- [ ] Order statistics endpoint working
- [ ] Notifications working
- [ ] Retry queue functional
- [ ] Performance tests passing
- [ ] Documentation updated

## Support

For issues or questions:
1. Check logs: `logs/*.log`
2. Review implementation plan: `documents/features/UNIFIED_ORDER_MONITORING_IMPLEMENTATION_PLAN.md`
3. Review completion summary: `documents/features/UNIFIED_ORDER_MONITORING_IMPLEMENTATION_SUMMARY.md`

---

**Migration Guide Version**: 1.0
**Last Updated**: January 2025

