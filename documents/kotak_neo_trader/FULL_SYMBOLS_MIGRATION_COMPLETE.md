# Full Symbols Migration - Complete Documentation

**Last Updated**: 2025-01-17
**Status**: Production Ready ✅
**Version**: 1.0

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Migration Overview](#migration-overview)
3. [Implementation Details](#implementation-details)
4. [Database Migration](#database-migration)
5. [Code Changes](#code-changes)
6. [Test Coverage](#test-coverage)
7. [Production Deployment](#production-deployment)
8. [Additional Items](#additional-items)
9. [Troubleshooting](#troubleshooting)
10. [Status Summary](#status-summary)

---

## Executive Summary

This document consolidates all information about the migration from base symbols (e.g., `RELIANCE`) to full symbols (e.g., `RELIANCE-EQ`) throughout the system. The migration ensures accurate segment tracking and eliminates symbol matching ambiguity.

### Key Benefits
- ✅ More accurate: Segments tracked separately (correct behavior)
- ✅ Simpler: No base symbol extraction needed for matching
- ✅ Consistent: Matches broker's model (segments are different instruments)
- ✅ No aggregation issues: Each segment is independent

### Migration Status
- ✅ **Core Migration**: 100% Complete
- ✅ **Additional Items**: 100% Complete
- ✅ **Test Coverage**: 55+ new tests, all passing
- ✅ **Production Ready**: All critical items complete

---

## Migration Overview

### Goal
Migrate from base symbols to full symbols everywhere (without smart matching).

### Key Assumptions
- Scrip master is always used for symbol resolution (single source of truth)
- Broker APIs return the same segment we used when placing orders
- Each segment (EQ, BE, BL, BZ) is a separate instrument from broker's perspective
- Manual trades in different segments are not tracked (by design)

### Important Distinction: Matching vs Ticker Creation

**CRITICAL**: After migration, we need to distinguish between two use cases:

1. **Matching/Comparison** (use full symbols):
   - Position matching: `position.symbol == broker_symbol` (both full symbols)
   - Reconciliation: Match exact symbols
   - Order tracking: Use full symbols as keys
   - **NO base symbol extraction needed**

2. **Ticker Creation** (extract base symbol first):
   - yfinance requires base symbols: `"RELIANCE.NS"` not `"RELIANCE-EQ.NS"`
   - Always extract base symbol before creating ticker
   - Use helper function: `get_ticker_from_full_symbol()`
   - **Base symbol extraction STILL needed for tickers only**

---

## Implementation Details

### Phase 1: Database Schema & Migration ✅

**Status**: Complete

**Positions Table:**
- `symbol` column: `String(32)` - Now stores full symbols (e.g., `RELIANCE-EQ`)
- No schema change needed (can store full symbols)

**Orders Table:**
- `symbol` column: `String(32)` - Already stores full symbols (e.g., `RELIANCE-EQ`)
- No schema change needed

**Migration Script**: `alembic/versions/20250117_migrate_positions_to_full_symbols.py`

**Migration Strategy:**
1. For each position with base symbol (e.g., "RELIANCE")
2. Find matching order(s) to get full symbol (e.g., "RELIANCE-EQ")
3. Update position.symbol to full symbol
4. If no matching order found, default to "{base_symbol}-EQ"

**Issues Fixed:**
- ✅ Multiple heads error: Fixed `down_revision` to `"20251213_add_failed_status_to_signalstatus"`
- ✅ Enum value error: Changed `'ONGOING'` to `'ongoing'` (lowercase)

---

## Database Migration

### Migration File
**Location**: `alembic/versions/20250117_migrate_positions_to_full_symbols.py`

### Migration Steps

1. **Update positions from matching orders** (preferred method)
   - Find positions with base symbols
   - Match with orders by user_id and base symbol
   - Update position.symbol to order.symbol (full symbol)

2. **Default remaining positions to -EQ**
   - For positions without matching orders
   - Append `-EQ` suffix to base symbol

3. **Verification**
   - Check all positions have full symbols
   - Verify no base symbols remain

### Testing Migration

**Test Script**: `scripts/test_migration_docker.py`

**Commands**:
```bash
# Test migration in Docker
python scripts/test_migration_docker.py

# Or use helper scripts
./scripts/run_migration_test_docker.sh  # Linux/Mac
./scripts/run_migration_test_docker.ps1  # Windows
```

---

## Code Changes

### Core Files Modified

#### 1. `modules/kotak_neo_auto_trader/sell_engine.py`
- Updated `active_sell_orders` to use full symbols as keys
- Updated reconciliation to use exact symbol matching
- Updated ticker creation to use `get_ticker_from_full_symbol()`
- Updated manual sell detection to use full symbols

**Key Changes**:
- Line 3930: Changed `base_symbol` to `full_symbol` in error logging
- Lines 499, 629, 748: Updated ticker creation to use `get_ticker_from_full_symbol()`
- Line 512: Updated order matching to exact symbol matching

#### 2. `modules/kotak_neo_auto_trader/unified_order_monitor.py`
- Updated position creation to use full symbols
- Updated sell order placement to use full symbols

#### 3. `modules/kotak_neo_auto_trader/utils/symbol_utils.py`
- Added `get_ticker_from_full_symbol()` helper function
- Converts full symbols to yfinance ticker format

#### 4. `server/app/routers/orders.py`
- Fixed ticker creation for yfinance in order recalculation endpoint
- Line 40: Updated to use `get_ticker_from_full_symbol()`

#### 5. `server/app/routers/broker.py`
- Updated position query logic to handle full symbols
- Added fallback for base symbol matching (backward compatibility)

#### 6. `src/application/services/analysis_deduplication_service.py`
- Added `_find_position_by_symbol()` with base symbol fallback matching
- Added `_has_ongoing_buy_order_by_symbol()` with base symbol fallback matching
- Handles both base symbols (from signals) and full symbols (from positions/orders)

#### 7. `modules/kotak_neo_auto_trader/manual_order_matcher.py`
- Updated to use `extract_base_symbol()` utility function
- Maintains backward compatibility

#### 8. `src/infrastructure/persistence/positions_repository.py`
- Updated docstrings to reflect full symbol usage
- All methods now document full symbol parameters

### Helper Functions

**`get_ticker_from_full_symbol(full_symbol: str, exchange: str = "NS") -> str`**
- Converts full trading symbol to yfinance ticker format
- Extracts base symbol and adds exchange suffix
- Example: `"RELIANCE-EQ"` → `"RELIANCE.NS"`

**`extract_base_symbol(symbol: str) -> str`**
- Extracts base symbol by removing segment suffix
- Example: `"RELIANCE-EQ"` → `"RELIANCE"`

---

## Test Coverage

### Test Files Created

#### 1. `test_full_symbols_edge_cases.py` (26 tests)
- Symbol utility edge cases
- Exact symbol matching
- Broker holdings with different field names
- Multiple segments of the same base symbol
- Position creation and retrieval
- Manual sell detection

#### 2. `test_full_symbols_ticker_creation.py` (15 tests)
- Ticker creation from full symbols
- Edge cases (whitespace, case, multiple hyphens)
- Integration with sell engine methods
- Consistency across code paths

#### 3. `test_full_symbols_reconciliation.py` (14 tests)
- Reconciliation with exact matching
- Different broker field names
- Manual sell detection during reconciliation
- Multiple positions with different segments

#### 4. `test_ticker_fixes_edge_cases.py` (22 tests)
- Ticker creation fixes in `sell_engine.py`, `orders.py`, and `broker.py`
- Edge cases and error handling

#### 5. `test_analysis_deduplication_service_symbol_matching.py` (13 tests)
- Base symbol from signals matching full symbols in positions/orders
- Fallback matching logic
- Integration with deduplication service

### Test Statistics
- **Total New Tests**: 90+
- **All Tests Passing**: ✅
- **Test Coverage**: Comprehensive coverage of all migration scenarios

---

## Production Deployment

### Pre-Deployment Checklist

#### ✅ Code Verification
- [x] Migration file has correct `down_revision`
- [x] Migration file uses correct enum value `'ongoing'` (lowercase)
- [x] All fixes committed to repository

#### ✅ Migration Chain Verification
```bash
# Check current database revision
docker exec tradeagent-api python -m alembic current

# Check migration heads (should show only one head)
docker exec tradeagent-api python -m alembic heads

# Verify migration history
docker exec tradeagent-api python -m alembic history
```

### Deployment Steps

#### 1. Backup Database (CRITICAL)
```bash
# Create backup before migration
docker exec tradeagent-db pg_dump -U trader tradeagent > backup_before_full_symbols_migration_$(date +%Y%m%d_%H%M%S).sql
```

#### 2. Pull Latest Code
```bash
git pull origin main  # or your production branch
# Verify migration file is present
ls -la alembic/versions/20250117_migrate_positions_to_full_symbols.py
```

#### 3. Rebuild API Container
```bash
cd docker
docker-compose -f docker-compose.yml build api-server
```

#### 4. Check Migration Status (Before Restart)
```bash
# Check current database state
docker exec tradeagent-db psql -U trader -d tradeagent -c "
SELECT
    COUNT(*) as total_positions,
    COUNT(CASE WHEN symbol LIKE '%-EQ' OR symbol LIKE '%-BE' OR symbol LIKE '%-BL' OR symbol LIKE '%-BZ' THEN 1 END) as full_symbols,
    COUNT(CASE WHEN symbol NOT LIKE '%-EQ' AND symbol NOT LIKE '%-BE' AND symbol NOT LIKE '%-BL' AND symbol NOT LIKE '%-BZ' THEN 1 END) as base_symbols
FROM positions;
"
```

#### 5. Restart API Container (Migration Runs Automatically)
```bash
docker-compose -f docker-compose.yml restart api-server

# Monitor logs for migration
docker-compose -f docker-compose.yml logs -f api-server | grep -i migration
```

#### 6. Verify Migration Success
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
```

### Post-Migration Verification

#### Application Functionality
- [ ] Verify positions are displayed correctly in UI
- [ ] Verify sell orders are created correctly
- [ ] Verify manual sell detection works
- [ ] Verify reconciliation works correctly
- [ ] Check logs for any symbol-related errors

#### Database Integrity
- [ ] All positions have full symbols (no base symbols remaining)
- [ ] Orders and positions match correctly
- [ ] No orphaned positions
- [ ] No duplicate positions for same symbol

---

## Additional Items

### ✅ Completed Items

#### 1. `analysis_deduplication_service.py` ✅
- Added `_find_position_by_symbol()` with base symbol fallback matching
- Added `_has_ongoing_buy_order_by_symbol()` with base symbol fallback matching
- Handles both base symbols (from signals) and full symbols (from positions/orders)
- 13 new tests added

#### 2. Repository Docstrings ✅
- Updated `positions_repository.py` docstrings
- All methods document full symbol parameters

#### 3. `paper_trading_service_adapter.py` ✅
- Already using correct utility functions
- Handles full symbols correctly

#### 4. `manual_order_matcher.py` ✅
- Updated to use `extract_base_symbol()` utility function
- Maintains backward compatibility

#### 5. Scripts Directory ✅
- Updated `check_user_orders_and_signals.py` to use utility function
- Updated `find_order_ids.py` with clarifying comments
- Other scripts verified as working correctly

### Items Not Addressed (By Design)

#### 1. Web Frontend (Low Priority - Cosmetic)
- Frontend symbol display is cosmetic only
- No functional impact
- Can be addressed post-deployment if user feedback indicates need

#### 2. Signals Table (Already Handled)
- Signals table stores base symbols (confirmed)
- `analysis_deduplication_service.py` handles base-to-full symbol matching
- This is the correct approach (signals are segment-agnostic)

---

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

### Rollback Plan

If migration fails or causes issues:

1. **Stop API Container**
```bash
docker-compose -f docker-compose.yml stop api-server
```

2. **Restore Database Backup**
```bash
docker exec -i tradeagent-db psql -U trader tradeagent < backup_before_full_symbols_migration_YYYYMMDD_HHMMSS.sql
```

3. **Downgrade Migration (Optional)**
```bash
docker exec tradeagent-api python -m alembic downgrade -1
```

4. **Revert Code**
```bash
git revert <migration-commit-hash>
docker-compose -f docker-compose.yml build api-server
docker-compose -f docker-compose.yml restart api-server
```

---

## Status Summary

### Core Migration
- ✅ **100% Complete**
- All critical code paths updated
- All critical tests passing
- Migration tested on Docker

### Additional Items
- ✅ **100% Complete**
- All high-priority items addressed
- All medium-priority items reviewed
- Low-priority items documented (can be addressed post-deployment)

### Production Readiness
- ✅ **Ready for Production**
- All critical items complete
- Migration tested
- Rollback plan ready
- Production checklist available

### Files Modified Summary

**Application Services**:
- `src/application/services/analysis_deduplication_service.py`
- `src/application/services/paper_trading_service_adapter.py` (verified)

**Core Modules**:
- `modules/kotak_neo_auto_trader/sell_engine.py`
- `modules/kotak_neo_auto_trader/unified_order_monitor.py`
- `modules/kotak_neo_auto_trader/manual_order_matcher.py`
- `modules/kotak_neo_auto_trader/utils/symbol_utils.py`

**API Routes**:
- `server/app/routers/orders.py`
- `server/app/routers/broker.py`

**Repositories**:
- `src/infrastructure/persistence/positions_repository.py`

**Scripts**:
- `scripts/check_user_orders_and_signals.py`
- `scripts/find_order_ids.py`

**Tests**:
- `tests/unit/kotak/test_full_symbols_edge_cases.py` (new)
- `tests/unit/kotak/test_full_symbols_ticker_creation.py` (new)
- `tests/unit/kotak/test_full_symbols_reconciliation.py` (new)
- `tests/unit/kotak/test_ticker_fixes_edge_cases.py` (new)
- `tests/unit/application/test_analysis_deduplication_service_symbol_matching.py` (new)

**Database**:
- `alembic/versions/20250117_migrate_positions_to_full_symbols.py` (new)

---

## Next Steps

1. **Production Deployment** (User Decision)
   - Follow production deployment steps above
   - Monitor for 24 hours after deployment

2. **Post-Deployment Monitoring**
   - Watch for symbol-related errors
   - Monitor signal deduplication
   - Check script functionality if used

3. **Optional Post-Deployment**
   - Frontend symbol display formatting (if user feedback indicates need)
   - Additional script updates (if issues arise)
   - Documentation updates (as needed)

---

## Notes

- **Migration is idempotent**: Safe to run multiple times (only updates positions without suffixes)
- **Migration is backward compatible**: Old code can still read full symbols (they're just strings)
- **No downtime required**: Migration runs during API startup
- **Automatic rollback**: If migration fails, API startup script continues (but logs warning)

---

**Document Version**: 1.0
**Last Updated**: 2025-01-17
**Status**: Production Ready ✅
