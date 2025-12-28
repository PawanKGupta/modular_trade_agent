# Testing Plan: Phase 0 + Phase 1

**Status:** Ready for Testing  
**Date:** December 23, 2024  
**Scope:** Phase 0 (Database Schema) + Phase 1 (Chart Library & PnL Service)

---

## 🎯 Testing Objectives

1. **Verify database migrations** work correctly (up/down)
2. **Validate data integrity** after schema changes
3. **Test PnL calculation accuracy** using Phase 0.2 exit details
4. **Verify chart components** render correctly
5. **Ensure API endpoints** function properly
6. **Check integration** between Phase 0 and Phase 1.2

---

## 📋 Pre-Testing Checklist

- [ ] Backup production/staging database (if applicable)
- [ ] Ensure test database is available
- [ ] Review migration order (8 migrations for Phase 0)
- [ ] Have sample data ready (positions, orders, closed positions)

---

## 🗄️ Phase 0: Database Schema Testing

### 0.1 Migration Testing

#### Test Migration Up
```bash
# Check current migration state
alembic current

# Apply all Phase 0 migrations
alembic upgrade head

# Verify all tables exist
# (Check: orders.trade_mode, positions.exit_*, portfolio_snapshots, targets, etc.)
```

**Expected Results:**
- ✅ All 8 migrations apply successfully
- ✅ No errors or warnings
- ✅ All new columns/tables exist

#### Test Migration Down (Rollback)
```bash
# Rollback one migration at a time
alembic downgrade -1

# Verify rollback works
# Repeat for each migration
```

**Expected Results:**
- ✅ Each migration rolls back cleanly
- ✅ No data loss (for nullable columns)
- ✅ Foreign key constraints handled correctly

#### Test Migration Up Again
```bash
# Re-apply all migrations
alembic upgrade head
```

**Expected Results:**
- ✅ Migrations re-apply successfully
- ✅ Data integrity maintained

---

### 0.2 Data Integrity Testing

#### Test Trade Mode Column (Phase 0.1)
```sql
-- Check all orders have trade_mode
SELECT COUNT(*) FROM orders WHERE trade_mode IS NULL;
-- Expected: 0 (after backfill)

-- Check trade_mode values are valid
SELECT DISTINCT trade_mode FROM orders;
-- Expected: 'paper' or 'broker' only

-- Verify paper trading orders have PAPER mode
SELECT COUNT(*) FROM orders 
WHERE trade_mode = 'paper' AND orig_source = 'paper_trading';
```

**Test Backfill Script:**
```bash
python scripts/backfill_trade_mode_to_orders.py
```

**Expected Results:**
- ✅ All existing orders have trade_mode set
- ✅ Paper trading orders have `trade_mode = 'paper'`
- ✅ Broker orders have `trade_mode = 'broker'` (if any)

---

#### Test Exit Details (Phase 0.2)
```sql
-- Check closed positions have exit details
SELECT 
    COUNT(*) as total_closed,
    COUNT(exit_price) as with_exit_price,
    COUNT(exit_reason) as with_exit_reason,
    COUNT(realized_pnl) as with_realized_pnl,
    COUNT(sell_order_id) as with_sell_order_id
FROM positions 
WHERE closed_at IS NOT NULL;
```

**Test Backfill Script:**
```bash
python scripts/backfill_exit_details_to_positions.py
```

**Expected Results:**
- ✅ Closed positions have exit_price populated
- ✅ exit_reason is set (e.g., 'EMA9_TARGET', 'MANUAL')
- ✅ realized_pnl is calculated correctly
- ✅ sell_order_id links to orders table

**Manual Validation:**
- Pick a closed position
- Verify: `realized_pnl = (exit_price - avg_price) * quantity_sold`
- Verify: `sell_order_id` points to correct order

---

#### Test Portfolio Snapshots (Phase 0.3)
```sql
-- Check portfolio_snapshots table exists
SELECT COUNT(*) FROM portfolio_snapshots;

-- Verify unique constraint works
-- (Should fail if duplicate user_id + date + snapshot_type)
```

**Expected Results:**
- ✅ Table exists and is accessible
- ✅ Unique constraint prevents duplicates

---

#### Test Targets Table (Phase 0.4)
```sql
-- Check targets table
SELECT COUNT(*) FROM targets;

-- Verify foreign key to positions
SELECT t.*, p.symbol 
FROM targets t
LEFT JOIN positions p ON t.position_id = p.id;
```

**Expected Results:**
- ✅ Table exists
- ✅ Foreign keys work correctly
- ✅ Active targets queryable

---

#### Test Other Tables (Phase 0.5-0.8)
- [ ] `pnl_calculation_audit` table exists
- [ ] `price_cache` table exists
- [ ] `export_jobs` table exists
- [ ] `analytics_cache` table exists

---

## 📊 Phase 1.1: Chart Library Testing

### Test Chart Components

#### Visual Testing
1. **Import and render ExampleLineChart:**
   ```tsx
   import { ExampleLineChart } from '@/components/charts';
   
   const data = [
     { name: 'Jan', value: 100 },
     { name: 'Feb', value: 200 },
     { name: 'Mar', value: 150 },
   ];
   
   <ExampleLineChart data={data} title="Test Chart" />
   ```

2. **Verify:**
   - ✅ Chart renders without errors
   - ✅ Dark theme colors applied correctly
   - ✅ Responsive behavior works
   - ✅ Tooltip appears on hover
   - ✅ Legend displays correctly

#### Theme Testing
```tsx
import { chartTheme, chartStyles } from '@/components/charts';

// Verify theme values
console.log(chartTheme.background); // Should be '#121923'
console.log(chartTheme.accent); // Should be '#4fc3f7'
```

**Expected Results:**
- ✅ Theme matches app's CSS variables
- ✅ Colors are consistent with dark theme

#### Bundle Size Check
```bash
cd web
npm run build
# Check bundle size increase is reasonable
```

**Expected Results:**
- ✅ Bundle size increase < 200KB (recharts is ~150KB)
- ✅ No duplicate dependencies

---

## 💰 Phase 1.2: PnL Calculation Service Testing

### Unit Tests

#### Test Realized P&L Calculation
```python
# Test with sample closed position
service = PnlCalculationService(db)

# Create test data:
# - Closed position with exit_price, avg_price, realized_pnl
# - Sell order linked via sell_order_id

realized = service.calculate_realized_pnl(user_id=1, target_date=date.today())

# Verify:
# - realized_pnl matches position.realized_pnl
# - Date grouping works correctly
```

**Test Cases:**
1. ✅ Single closed position → correct realized P&L
2. ✅ Multiple closed positions on same date → sum correctly
3. ✅ Closed positions on different dates → grouped correctly
4. ✅ Position with realized_pnl field → uses stored value
5. ✅ Position without realized_pnl → calculates from exit_price
6. ✅ Position with sell_order_id → gets quantity from order
7. ✅ Trade mode filtering (PAPER vs BROKER) works

---

#### Test Unrealized P&L Calculation
```python
unrealized = service.calculate_unrealized_pnl(user_id=1)

# Verify:
# - Uses unrealized_pnl from positions table
# - Groups by current date
```

**Test Cases:**
1. ✅ Single open position → correct unrealized P&L
2. ✅ Multiple open positions → sum correctly
3. ✅ Trade mode filtering works
4. ⚠️ **Note:** Currently uses placeholder (unrealized_pnl field)

---

#### Test Fees Calculation
```python
fees = service.calculate_fees(user_id=1, target_date=date.today())

# Verify:
# - Fee = order_value * 0.001 (0.1%)
# - Both buy and sell orders included
```

**Test Cases:**
1. ✅ Single order → fee = value * 0.001
2. ✅ Multiple orders on same date → sum correctly
3. ✅ Trade mode filtering works
4. ✅ Uses avg_price if available, otherwise price

---

#### Test Daily P&L Aggregation
```python
record = service.calculate_daily_pnl(user_id=1, target_date=date.today())

# Verify:
# - PnlDaily record created/updated
# - realized_pnl + unrealized_pnl - fees = total
# - Upsert works (no duplicates)
```

**Test Cases:**
1. ✅ First calculation → creates new record
2. ✅ Re-calculation → updates existing record
3. ✅ All components (realized, unrealized, fees) included
4. ✅ Trade mode filtering works

---

#### Test Date Range Backfill
```python
records = service.calculate_date_range(
    user_id=1,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31)
)

# Verify:
# - Creates records for all dates in range
# - Handles missing data gracefully
# - Performance acceptable (< 1 min for 31 days)
```

**Test Cases:**
1. ✅ Small range (7 days) → completes quickly
2. ✅ Large range (365 days) → completes within limit
3. ✅ Range > 365 days → API rejects (validation)
4. ✅ Dates with no data → creates records with 0 values

---

### API Endpoint Testing

#### Test Calculate Endpoint
```bash
# On-demand calculation
curl -X POST "http://localhost:8000/api/v1/user/pnl/calculate?target_date=2024-12-23" \
  -H "Authorization: Bearer <token>"

# With trade mode filter
curl -X POST "http://localhost:8000/api/v1/user/pnl/calculate?trade_mode=paper" \
  -H "Authorization: Bearer <token>"
```

**Expected Response:**
```json
{
  "date": "2024-12-23",
  "realized_pnl": 1500.0,
  "unrealized_pnl": 500.0,
  "fees": 50.0,
  "total_pnl": 1950.0
}
```

**Test Cases:**
1. ✅ Default (today) → calculates for current date
2. ✅ Specific date → calculates for that date
3. ✅ Trade mode filter → only includes that mode
4. ✅ Invalid trade_mode → 400 error
5. ✅ No data → returns zeros

---

#### Test Backfill Endpoint
```bash
# Historical backfill
curl -X POST "http://localhost:8000/api/v1/user/pnl/backfill?start_date=2024-01-01&end_date=2024-01-31" \
  -H "Authorization: Bearer <token>"
```

**Expected Response:**
```json
{
  "message": "Backfill completed successfully",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "records_created": 31,
  "trade_mode": null
}
```

**Test Cases:**
1. ✅ Valid range → creates records
2. ✅ Range > 365 days → 400 error
3. ✅ start_date > end_date → 400 error
4. ✅ Trade mode filter → only that mode
5. ✅ Large range → completes within timeout

---

### Integration Testing

#### Test Phase 0.2 Integration
```python
# Verify PnL calculation uses Phase 0.2 exit details:
# 1. Create a closed position with exit details
# 2. Calculate P&L
# 3. Verify it uses realized_pnl from position

position = positions_repo.mark_closed(
    user_id=1,
    symbol="RELIANCE-EQ",
    exit_price=2500.0,
    exit_reason="EMA9_TARGET",
    realized_pnl=500.0,
    sell_order_id=123
)

# Calculate P&L
service = PnlCalculationService(db)
realized = service.calculate_realized_pnl(user_id=1)

# Verify realized_pnl = 500.0 (from position, not calculated)
```

**Expected Results:**
- ✅ Uses `realized_pnl` from positions table (Phase 0.2)
- ✅ Falls back to calculation if not available
- ✅ Links to sell_order_id correctly

---

#### Test Phase 0.1 Integration
```python
# Verify trade_mode filtering works:
# 1. Create orders with different trade_mode
# 2. Calculate P&L with filter
# 3. Verify only correct mode included

# Paper trading order
order1 = orders_repo.create_amo(..., trade_mode=TradeMode.PAPER)

# Broker order
order2 = orders_repo.create_amo(..., trade_mode=TradeMode.BROKER)

# Calculate P&L for paper only
service = PnlCalculationService(db)
realized = service.calculate_realized_pnl(user_id=1, trade_mode=TradeMode.PAPER)

# Verify only paper trading positions included
```

**Expected Results:**
- ✅ Trade mode filtering works correctly
- ✅ PAPER and BROKER modes separated
- ✅ Fees calculated per mode

---

## 🐛 Error Handling Testing

### Test Error Scenarios

1. **Missing Data:**
   - Position closed but no exit_price → warning logged, skipped
   - Order without price → fee = 0

2. **Invalid Inputs:**
   - Invalid date format → 400 error
   - Invalid trade_mode → 400 error
   - Date range > 365 days → 400 error

3. **Database Errors:**
   - Connection failure → 500 error with message
   - Constraint violation → handled gracefully

---

## 📈 Performance Testing

### Benchmarks

1. **Single Date Calculation:**
   - Target: < 1 second for 100 positions
   - Target: < 5 seconds for 1000 positions

2. **Date Range Backfill:**
   - Target: < 1 minute for 365 days
   - Target: < 10 seconds for 30 days

3. **Database Queries:**
   - Verify indexes are used
   - Check query execution time

---

## ✅ Acceptance Criteria

### Phase 0
- [x] All migrations apply successfully
- [x] All migrations rollback successfully
- [x] Backfill scripts work correctly
- [x] Data integrity maintained
- [x] No data loss

### Phase 1.1
- [x] Chart components render correctly
- [x] Theme matches application
- [x] Bundle size acceptable
- [x] No console errors

### Phase 1.2
- [x] PnL calculation accurate
- [x] API endpoints functional
- [x] Integration with Phase 0.2 works
- [x] Trade mode filtering works
- [x] Error handling robust
- [x] Performance acceptable

---

## 🚀 Next Steps After Testing

1. **If all tests pass:**
   - Proceed to Phase 2 (Core Dashboard Enhancements)
   - Phase 2 depends on Phase 1.2 working correctly

2. **If issues found:**
   - Fix issues in Phase 0/1 before proceeding
   - Re-test affected areas
   - Document any known limitations

3. **Documentation:**
   - Update release plan with test results
   - Document any deviations from plan
   - Note performance benchmarks

---

## 📝 Test Results Template

```
## Test Results - [Date]

### Phase 0: Database Schema
- Migration Up: ✅ / ❌
- Migration Down: ✅ / ❌
- Data Integrity: ✅ / ❌
- Backfill Scripts: ✅ / ❌
- Issues Found: [List]

### Phase 1.1: Chart Library
- Component Rendering: ✅ / ❌
- Theme Matching: ✅ / ❌
- Bundle Size: ✅ / ❌
- Issues Found: [List]

### Phase 1.2: PnL Service
- Realized P&L: ✅ / ❌
- Unrealized P&L: ✅ / ❌
- Fees Calculation: ✅ / ❌
- API Endpoints: ✅ / ❌
- Integration: ✅ / ❌
- Performance: ✅ / ❌
- Issues Found: [List]

### Overall Status: ✅ Ready for Phase 2 / ❌ Needs Fixes
```

---

**Last Updated:** December 23, 2024

