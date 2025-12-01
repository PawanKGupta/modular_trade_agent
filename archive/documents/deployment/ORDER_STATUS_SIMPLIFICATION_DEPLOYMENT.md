# Order Status Simplification - Phase 6 Deployment Guide

## Overview

This document provides step-by-step instructions for deploying the order status simplification changes (9 → 5 statuses) and retry filtration logic to production.

**Deployment Date**: TBD
**Deployment Window**: Low-traffic period (recommended: Weekend or after market hours)
**Estimated Duration**: 2-3 hours
**Risk Level**: Medium

---

## Pre-Deployment Checklist

### ✅ Code & Testing
- [x] All tests passing (1820 tests collected) ✅ **VERIFIED**
- [x] Code review completed
- [x] Test coverage >80% for modified code
- [x] No critical bugs identified
- [x] All Phase 0-5 tasks completed

### 📋 Documentation
- [x] Implementation guide updated
- [x] Impact analysis documented
- [x] Phase-wise plan updated
- [x] API documentation updated
- [x] Frontend changes documented

### 🗄️ Database
- [ ] Production database backup created
- [ ] Migration script tested on staging
- [ ] Rollback script prepared
- [ ] Data validation queries ready

### 🚀 Deployment
- [ ] Deployment window scheduled
- [ ] Team on standby
- [ ] Monitoring dashboards ready
- [ ] Support team notified
- [ ] Rollback plan ready

### 📊 Monitoring
- [ ] Error logging configured
- [ ] Metrics dashboards ready
- [ ] Alert thresholds set
- [ ] Monitoring team briefed

---

## Step 1: Pre-Deployment Validation

### 1.1 Run Full Test Suite

```bash
# Run all tests
.venv\Scripts\python.exe -m pytest -v

# Expected: All tests passing (1820 tests)
```

### 1.2 Verify Migration Script

```bash
# Check migration script exists
ls alembic/versions/873e86bc5772_order_status_simplification_and_unified_.py

# Review migration script
cat alembic/versions/873e86bc5772_order_status_simplification_and_unified_.py
```

### 1.3 Check Current Database State

```sql
-- Check current order status distribution
SELECT status, COUNT(*) as count
FROM orders
GROUP BY status
ORDER BY count DESC;

-- Check for orders with old statuses (should be empty after migration)
SELECT COUNT(*) as old_status_count
FROM orders
WHERE status IN ('amo', 'pending_execution', 'retry_pending', 'rejected', 'sell');

-- Check reason field usage
SELECT
    COUNT(*) as total_orders,
    COUNT(reason) as orders_with_reason
FROM orders;
```

---

## Step 2: Database Backup

### 2.1 Create Full Backup

**⚠️ CRITICAL: Do not skip this step**

```bash
# PostgreSQL backup
pg_dump -h <host> -U <user> -d <database> -F c -f backup_pre_status_simplification_$(date +%Y%m%d_%H%M%S).dump

# SQLite backup (if using SQLite)
cp <database_path> <database_path>.backup_$(date +%Y%m%d_%H%M%S)
```

### 2.2 Verify Backup

```bash
# Verify backup file exists and is not empty
ls -lh backup_pre_status_simplification_*.dump

# Test restore (on test database)
pg_restore -h <test_host> -U <user> -d <test_database> backup_pre_status_simplification_*.dump
```

---

## Step 3: Database Migration

### 3.1 Run Migration Script

```bash
# Navigate to project root
cd <project_root>

# Activate virtual environment
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Run migration
alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Running upgrade c38b470b20d1 -> 873e86bc5772, order_status_simplification_and_unified_reason
```

### 3.2 Verify Migration

```sql
-- Verify reason field exists
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'orders' AND column_name = 'reason';

-- Verify status migration
SELECT status, COUNT(*) as count
FROM orders
GROUP BY status
ORDER BY count DESC;

-- Should show only: pending, ongoing, closed, failed, cancelled

-- Verify no old statuses remain
SELECT COUNT(*) as old_status_count
FROM orders
WHERE status IN ('amo', 'pending_execution', 'retry_pending', 'rejected', 'sell');
-- Expected: 0

-- Verify reason field usage
SELECT
    COUNT(*) as total_orders,
    COUNT(reason) as orders_with_reason
FROM orders;
```

### 3.3 Data Integrity Check

```sql
-- Check for data loss
SELECT
    (SELECT COUNT(*) FROM orders) as total_orders,
    (SELECT COUNT(*) FROM orders WHERE status IS NOT NULL) as orders_with_status,
    (SELECT COUNT(*) FROM orders WHERE created_at IS NOT NULL) as orders_with_timestamp;

-- All counts should match (no data loss)

-- Verify order relationships intact
SELECT
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT symbol) as unique_symbols
FROM orders;
```

---

## Step 4: Code Deployment

### 4.1 Deploy Repository Changes (Phase 2)

**Files to deploy:**
- `src/infrastructure/persistence/orders_repository.py`
- `src/infrastructure/db/models.py`
- `modules/kotak_neo_auto_trader/utils/trading_day_utils.py`

**Deployment steps:**
1. Deploy updated repository code
2. Restart application services
3. Monitor for errors (5 minutes)

### 4.2 Deploy Business Logic Changes (Phase 3)

**Files to deploy:**
- `modules/kotak_neo_auto_trader/auto_trade_engine.py`
- `modules/kotak_neo_auto_trader/order_tracker.py`
- `modules/kotak_neo_auto_trader/order_state_manager.py`
- `modules/kotak_neo_auto_trader/sell_engine.py`

**Deployment steps:**
1. Deploy updated business logic code
2. Restart application services
3. Monitor for errors (10 minutes)

### 4.3 Deploy API Changes (Phase 4)

**Files to deploy:**
- `server/app/routers/orders.py`
- `server/app/schemas/orders.py`

**Deployment steps:**
1. Deploy updated API code
2. Restart API server
3. Monitor for errors (5 minutes)

### 4.4 Deploy Frontend Changes (Phase 4)

**Files to deploy:**
- `web/src/api/orders.ts`
- `web/src/routes/dashboard/OrdersPage.tsx`
- `web/src/mocks/test-handlers.ts`

**Deployment steps:**
1. Build frontend
2. Deploy frontend assets
3. Clear browser cache (if needed)
4. Monitor for errors (5 minutes)

---

## Step 5: Post-Deployment Validation

### 5.1 Functional Testing

#### Order Placement
```bash
# Test new buy order placement
# Expected: Order created with status='pending', reason='Order placed - waiting for market open'
```

#### Order Execution
```bash
# Test order execution
# Expected: Order status changes to 'ongoing', reason='Order executed at Rs X.XX'
```

#### Order Failure
```bash
# Test order failure
# Expected: Order status='failed', reason='<reason>', retry_count incremented
```

#### Retry Logic
```bash
# Test retry of failed orders
# Expected: Expired orders marked as 'cancelled', non-expired orders retriable
```

#### Sell Orders
```bash
# Test sell order placement
# Expected: Order created with side='sell', status='pending'
```

### 5.2 API Testing

```bash
# Test list orders endpoint
curl -X GET "http://localhost:8000/api/v1/user/orders?status=pending" \
  -H "Authorization: Bearer <token>"

# Expected: Returns orders with status='pending'

# Test retry order endpoint
curl -X POST "http://localhost:8000/api/v1/user/orders/<order_id>/retry" \
  -H "Authorization: Bearer <token>"

# Expected: Returns order with status='failed', retry_count incremented
```

### 5.3 Frontend Testing

1. Navigate to Orders page
2. Verify status filters work (pending, ongoing, failed, closed, cancelled)
3. Verify reason field displays correctly
4. Verify retry/drop buttons work for failed orders
5. Verify no console errors

### 5.4 Database Validation

```sql
-- Verify no new orders with old statuses
SELECT COUNT(*) as old_status_count
FROM orders
WHERE status IN ('amo', 'pending_execution', 'retry_pending', 'rejected', 'sell')
  AND created_at > NOW() - INTERVAL '1 hour';
-- Expected: 0

-- Verify new orders use unified reason field
SELECT
    COUNT(*) as new_orders,
    COUNT(reason) as orders_with_reason
FROM orders
WHERE created_at > NOW() - INTERVAL '1 hour';
-- Expected: new_orders = orders_with_reason
```

---

## Step 6: Monitoring (First 24 Hours)

### 6.1 Key Metrics to Monitor

#### Order Placement
- Order placement success rate
- Order placement error rate
- Average order placement time

#### Order Execution
- Order execution success rate
- Order execution error rate
- Average execution time

#### Retry Logic
- Failed orders count
- Retriable orders count
- Expired orders count (should be marked as cancelled)
- Retry success rate

#### API Performance
- API response times
- API error rates
- API endpoint availability

#### Database Performance
- Database query times
- Database connection pool usage
- Database error rates

### 6.2 Error Monitoring

```bash
# Monitor application logs
tail -f logs/application.log | grep -i "error\|exception\|failed"

# Monitor API logs
tail -f logs/api.log | grep -i "error\|exception\|failed"

# Monitor database logs
tail -f logs/database.log | grep -i "error\|exception\|failed"
```

### 6.3 Alert Thresholds

Set up alerts for:
- Order placement failure rate > 5%
- Order execution failure rate > 10%
- API error rate > 1%
- Database query time > 1 second
- Application errors > 10 per hour

---

## Step 7: Rollback Plan

### 7.1 When to Rollback

Rollback immediately if:
- Critical errors detected
- Data loss detected
- Order placement completely broken
- Order execution completely broken
- API completely unavailable
- Database corruption detected

### 7.2 Rollback Steps

#### Step 1: Stop New Deployments
```bash
# Stop all application services
systemctl stop <service_name>
```

#### Step 2: Restore Database
```bash
# Restore from backup
pg_restore -h <host> -U <user> -d <database> -c backup_pre_status_simplification_*.dump

# Or run rollback migration
alembic downgrade c38b470b20d1
```

#### Step 3: Revert Code
```bash
# Revert to previous commit
git checkout <previous_commit_hash>

# Redeploy previous version
# (Follow deployment steps for previous version)
```

#### Step 4: Verify Rollback
```bash
# Run validation tests
# Verify system functioning
# Monitor for stability
```

---

## Step 8: Post-Deployment Tasks

### 8.1 Documentation Updates
- [ ] Update deployment log
- [ ] Document any issues encountered
- [ ] Update runbook with lessons learned

### 8.2 Team Communication
- [ ] Notify team of successful deployment
- [ ] Share monitoring dashboard links
- [ ] Provide support contact information

### 8.3 Follow-up
- [ ] Schedule 1-week review meeting
- [ ] Collect user feedback
- [ ] Plan any necessary adjustments

---

## Monitoring Checklist (First Week)

### Day 1 (First 24 Hours)
- [ ] Monitor all key metrics hourly
- [ ] Check error logs every 2 hours
- [ ] Verify no critical issues
- [ ] Document any anomalies

### Day 2-3
- [ ] Monitor key metrics every 4 hours
- [ ] Check error logs daily
- [ ] Review user feedback
- [ ] Address any issues

### Day 4-7
- [ ] Monitor key metrics daily
- [ ] Review weekly metrics summary
- [ ] Collect user feedback
- [ ] Plan improvements if needed

---

## Success Criteria

### Technical Success
- ✅ All migrations completed successfully
- ✅ No data loss
- ✅ All tests passing
- ✅ No critical errors
- ✅ Performance acceptable

### Functional Success
- ✅ Order placement works correctly
- ✅ Order execution works correctly
- ✅ Sell orders work correctly
- ✅ Retry logic works correctly
- ✅ Expiry logic works correctly
- ✅ API endpoints work correctly
- ✅ Frontend displays correctly

### Business Success
- ✅ User experience maintained/improved
- ✅ System stability maintained
- ✅ No user complaints
- ✅ Order processing continues normally

---

## Support Contacts

- **Technical Lead**: [Name/Email]
- **Database Admin**: [Name/Email]
- **DevOps Engineer**: [Name/Email]
- **On-Call Engineer**: [Name/Phone]

---

## Appendix

### A. Migration Script Details

**Migration ID**: `873e86bc5772`
**Migration Name**: `order_status_simplification_and_unified_reason`
**Previous Migration**: `c38b470b20d1`

**Migration 1 (`873e86bc5772`):**
1. Adds `reason` column (String(512), nullable)
2. Migrates `failure_reason` → `reason`
3. Migrates `rejection_reason` → `reason`
4. Migrates `cancelled_reason` → `reason`
5. Migrates `AMO` → `PENDING`
6. Migrates `PENDING_EXECUTION` → `PENDING`
7. Migrates `RETRY_PENDING` → `FAILED`
8. Migrates `REJECTED` → `FAILED`
9. Migrates `SELL` → `PENDING` (for orders with side='sell')

**Migration 2 (`3473a345c7fb`):**
1. Drops legacy reason columns: `failure_reason`, `rejection_reason`, `cancelled_reason`
2. All reason data is now stored in the unified `reason` field

### B. Rollback Script

```python
# Rollback migration
alembic downgrade c38b470b20d1

# Manual rollback SQL (if needed)
# Note: This is approximate - some data may be lost
# Note: Legacy reason columns (failure_reason, rejection_reason, cancelled_reason) have been dropped.
# To rollback, you would need to recreate these columns first, then split the unified 'reason' field.
UPDATE orders SET status = 'amo' WHERE status = 'pending' AND side = 'buy';
UPDATE orders SET status = 'retry_pending' WHERE status = 'failed' AND first_failed_at IS NOT NULL;
```

### C. Validation Queries

See Step 3.2 and Step 5.4 for validation queries.

---

**Last Updated**: November 23, 2025
**Version**: 1.0
**Status**: Ready for Deployment
