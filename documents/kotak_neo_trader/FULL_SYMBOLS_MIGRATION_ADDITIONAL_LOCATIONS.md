# Full Symbols Migration - Additional Locations

**Last Updated**: 2025-01-17
**Status**: Additional locations found
**Purpose**: List all additional places that need updates beyond the main migration plan

## Summary

This document lists additional files and locations that need updates for the full symbols migration, beyond those already covered in `FULL_SYMBOLS_MIGRATION_PLAN.md`.

---

## 1. Application Services

### 1.1 `src/application/services/analysis_deduplication_service.py`

**Issue**: Extracts base symbol from ticker, then uses it to query positions.

**Location**: Line ~178

**Current Code:**
```python
symbol = signal_data.get("symbol") or signal_data.get("ticker", "").replace(".NS", "")
# Later uses symbol to query positions:
position = self._positions_repo.get_by_symbol_any(
    self.user_id, symbol, include_closed=True
)
```

**Problem**:
- If `signal.symbol` is base symbol (e.g., `"RELIANCE"`), it will query positions with base symbol
- After migration, positions will have full symbols (e.g., `"RELIANCE-EQ"`)
- Query will fail to find position

**Fix Required:**
```python
# Option 1: If signal.symbol is base, need to find matching position
# Option 2: Store full symbol in signals table
# Option 3: Query all positions and match by base symbol (temporary workaround)

# For now, signals table likely stores base symbols
# Need to either:
# 1. Update signals table to store full symbols
# 2. Or query positions and match by base symbol extraction
```

**Checklist:**
- [ ] Determine if signals table stores base or full symbols
- [ ] Update position query logic to handle symbol format
- [ ] Consider updating signals table to store full symbols
- [ ] Update `has_ongoing_buy_order()` call (line 208) to use correct symbol format

**Related Locations:**
- Line 220: `get_by_symbol_any()` call
- Line 297: `get_by_symbol_any()` call
- Line 208: `has_ongoing_buy_order()` call

---

### 1.2 `src/application/services/paper_trading_service_adapter.py`

**Issue**: Multiple places use symbols, some create tickers incorrectly.

**Location 1**: Line ~919

**Current Code:**
```python
symbol = holding.symbol
ticker = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
```

**Problem**:
- If `holding.symbol` is full symbol (e.g., `"RELIANCE-EQ"`), creates `"RELIANCE-EQ.NS"` (invalid)

**Fix Required:**
```python
from modules.kotak_neo_auto_trader.utils.symbol_utils import get_ticker_from_full_symbol

symbol = holding.symbol
ticker = get_ticker_from_full_symbol(symbol)  # ✅ Handles both base and full
```

**Location 2**: Line ~913-936

**Current Code:**
```python
pending_sell_symbols = {
    o.symbol for o in pending_orders if o.is_sell_order() and o.is_active()
}

# Later:
if symbol in self.active_sell_orders or symbol in pending_sell_symbols:
    # Uses symbol for matching
```

**Problem**:
- If `active_sell_orders` uses full symbols as keys, but `symbol` is base, matching fails

**Fix Required:**
- Ensure `symbol` is full symbol when used for matching
- Or ensure `active_sell_orders` uses same format as `symbol`

**Location 3**: Line ~1071-1120

**Current Code:**
```python
for symbol, order_info in list(self.active_sell_orders.items()):
    ticker = order_info["ticker"]
    # Uses symbol for various operations
```

**Problem**:
- If `active_sell_orders` keys are base symbols, but positions have full symbols, matching fails

**Fix Required:**
- Update `active_sell_orders` to use full symbols as keys
- Update all lookups to use full symbols

**Checklist:**
- [ ] Fix ticker creation (line 919)
- [ ] Review `active_sell_orders` key format
- [ ] Update all symbol matching to use full symbols
- [ ] Test paper trading with full symbols

---

## 2. API Routes

### 2.1 `server/app/routers/orders.py`

**Location**: Line ~40

**Current Code:**
```python
ticker = getattr(order, "ticker", None) or f"{order.symbol}.NS"
stock = yf.Ticker(ticker)
```

**Problem**:
- If `order.symbol` is full symbol (e.g., `"RELIANCE-EQ"`), creates `"RELIANCE-EQ.NS"` (invalid)

**Fix Required:**
```python
from modules.kotak_neo_auto_trader.utils.symbol_utils import get_ticker_from_full_symbol

ticker = getattr(order, "ticker", None) or get_ticker_from_full_symbol(order.symbol)
stock = yf.Ticker(ticker)
```

**Checklist:**
- [ ] Fix ticker creation
- [ ] Test order recalculation endpoint

---

### 2.2 `server/app/routers/broker.py`

**Location**: Line ~640-680

**Current Code:**
```python
# Normalize symbol: remove .NS/.BO suffix and -EQ/-BE suffix
normalized_symbol = symbol.upper().replace(".NS", "").replace(".BO", "")
# Remove broker-specific suffixes like -EQ, -BE
if "-" in normalized_symbol:
    normalized_symbol = normalized_symbol.split("-")[0]

position = positions_repo.get_by_symbol(current.id, normalized_symbol)
```

**Problem**:
- After migration, positions have full symbols
- This code extracts base symbol and queries with base symbol
- Query will fail to find position

**Fix Required:**
```python
# Option 1: Query with full symbol if available
# Option 2: Query all positions and match by base symbol
# Option 3: Update to use full symbol from broker response

# If broker returns full symbol:
full_symbol = symbol.upper()  # e.g., "RELIANCE-EQ"
position = positions_repo.get_by_symbol(current.id, full_symbol)

# If broker returns base symbol, need to find matching position:
# (This is a fallback - ideally broker should return full symbol)
base_symbol = extract_base_symbol(symbol).upper()
# Query all positions and find one matching base symbol
```

**Checklist:**
- [ ] Determine format of `symbol` from broker response
- [ ] Update position query logic
- [ ] Test portfolio endpoint

---

## 3. Test Files

### 3.1 Test Files Using Symbols

**Files Found**: 155+ test files use symbols

**Common Patterns:**
1. Mock positions with base symbols
2. Mock orders with base symbols
3. Symbol comparisons using base symbols
4. Ticker creation from symbols

**Examples:**

**Pattern 1: Mock Position Creation**
```python
# Current (many test files):
position = Mock(spec=Positions)
position.symbol = "RELIANCE"  # ❌ Base symbol

# After migration:
position = Mock(spec=Positions)
position.symbol = "RELIANCE-EQ"  # ✅ Full symbol
```

**Pattern 2: Symbol Comparison**
```python
# Current:
assert position.symbol == "RELIANCE"  # ❌ Base symbol

# After migration:
assert position.symbol == "RELIANCE-EQ"  # ✅ Full symbol
```

**Pattern 3: Ticker Creation**
```python
# Current:
ticker = f"{symbol}.NS"  # ❌ If symbol is full, creates invalid ticker

# After migration:
from modules.kotak_neo_auto_trader.utils.symbol_utils import get_ticker_from_full_symbol
ticker = get_ticker_from_full_symbol(symbol)  # ✅ Handles both
```

**Checklist:**
- [ ] Review all test files for symbol usage
- [ ] Update mock positions to use full symbols
- [ ] Update mock orders to use full symbols
- [ ] Update symbol comparisons
- [ ] Fix ticker creation in tests
- [ ] Run full test suite after migration

**Priority Test Files:**
- `tests/unit/kotak/test_manual_sell_detection_from_orders.py`
- `tests/unit/kotak/test_pending_manual_sell_tracking.py`
- `tests/unit/kotak/test_exit_price_time_recording.py`
- `tests/unit/kotak/test_unified_order_monitor.py`
- `tests/unit/kotak/test_sell_engine.py`
- `tests/unit/infrastructure/test_positions_repository_multiple_positions.py`

---

## 4. Documentation Files

### 4.1 Documentation Updates Needed

**Files:**
- `docs/API_COMPATIBILITY_VERIFICATION.md` - Line 100: Mentions base symbol storage
- `docs/API_COMPATIBILITY_POSITIONS.md` - May mention symbol format
- `documents/kotak_neo_trader/SELL_ORDER_IMPLEMENTATION_COMPLETE.md` - May reference symbol format
- `documents/EDGE_CASES.md` - May reference symbol format

**Checklist:**
- [ ] Update documentation to reflect full symbol usage
- [ ] Update examples to show full symbols
- [ ] Update API documentation
- [ ] Update troubleshooting guides

---

## 5. Signals Table

### 5.1 Signals Repository

**Issue**: Signals table stores base symbols, but positions will have full symbols after migration.

**Location**: `src/infrastructure/persistence/signals_repository.py`

**Current State**: ✅ **CONFIRMED** - Signals table stores **base symbols**

**Evidence:**
1. **Signal Creation** (`analysis_deduplication_service.py:507`):
   ```python
   symbol = data.get("symbol") or data.get("ticker", "").replace(".NS", "")
   signal = Signals(symbol=symbol, ...)  # Base symbol stored
   ```

2. **Order-to-Signal Matching** (`orders_repository.py:545`):
   ```python
   # Extract base symbol (remove -EQ, -BE suffixes)
   base_symbol = order.symbol.split("-")[0] if "-" in order.symbol else order.symbol
   # Find the latest signal for this symbol
   signal = self.db.execute(
       select(Signals).where(Signals.symbol == base_symbol)
   )
   ```

**Problem**:
- Signals store base symbols (e.g., `"RELIANCE"`)
- After migration, positions will have full symbols (e.g., `"RELIANCE-EQ"`)
- Signal-to-position matching will fail

**Options:**

**Option 1: Keep Signals as Base Symbols (Recommended)**
- Signals represent stock recommendations, not specific segments
- Update position query logic to extract base symbol when matching
- Pros: Signals remain segment-agnostic
- Cons: Need base symbol extraction for matching

**Option 2: Migrate Signals to Full Symbols**
- Update signals table to store full symbols
- Requires migration script
- Pros: Consistent with positions
- Cons: Signals become segment-specific (may not be desired)

**Recommended Fix (Option 1):**
```python
# In analysis_deduplication_service.py:
symbol = signal_data.get("symbol") or signal_data.get("ticker", "").replace(".NS", "")
# symbol is base (e.g., "RELIANCE")

# Query all positions and match by base symbol
all_positions = self._positions_repo.list(self.user_id)
matching_position = None
for pos in all_positions:
    pos_base = extract_base_symbol(pos.symbol).upper()
    if pos_base == symbol.upper():
        matching_position = pos
        break
```

**Checklist:**
- [x] ✅ Confirmed signals table stores base symbols
- [ ] Decide: Keep base symbols or migrate to full symbols (recommend: keep base)
- [ ] Update position query logic to handle base symbol matching
- [ ] Update `has_ongoing_buy_order()` callers to use base symbol
- [ ] Update signal-to-order matching logic if needed

---

## 6. Manual Order Matcher

### 6.1 `modules/kotak_neo_auto_trader/manual_order_matcher.py`

**Location**: Line ~273

**Current Code:**
```python
broker_holding = holdings_dict.get(symbol.upper())
```

**Problem**:
- `holdings_dict` likely uses base symbols as keys
- After migration, positions use full symbols
- Matching may fail

**Fix Required:**
- Review how `holdings_dict` is built
- Ensure consistent symbol format
- Update matching logic if needed

**Checklist:**
- [ ] Review `holdings_dict` key format
- [ ] Update matching logic
- [ ] Test manual order matching

---

## 7. Scripts Directory

### 7.1 Utility Scripts

**Issue**: Many scripts extract base symbols from orders/positions for display or matching.

**Files Found:**
- `scripts/find_order_ids.py` - Lines 61, 71: Extracts base symbol, tries with -EQ suffix
- `scripts/check_user_orders_and_signals.py` - Line 61: Extracts base symbol from order.symbol
- `scripts/fix_tracking_data_corruption.py` - Lines 101-109, 171: Removes suffixes to get base symbol
- `scripts/verify_tracking_data.py` - Lines 96-104: Removes suffixes to get base symbol
- `scripts/migration/migrate_trades_history.py` - Lines 50-57: Extracts base symbol
- `scripts/migration/migrate_pending_orders.py` - Lines 59-66: Extracts base symbol

**Problem**:
- Scripts assume positions/orders have base symbols
- After migration, positions will have full symbols
- Scripts may fail to match or display incorrectly

**Fix Required:**
- Update scripts to handle full symbols
- Use `extract_base_symbol()` when base symbol is needed for display
- Use full symbols for matching

**Checklist:**
- [ ] Review all scripts for symbol extraction
- [ ] Update scripts to handle full symbols
- [ ] Test scripts after migration
- [ ] Update script documentation

**Priority Scripts:**
- `scripts/find_order_ids.py` - Used for debugging
- `scripts/check_user_orders_and_signals.py` - Used for verification
- `scripts/fix_tracking_data_corruption.py` - Used for data fixes
- `scripts/verify_tracking_data.py` - Used for verification

---

## 8. Repository Documentation

### 8.1 Positions Repository Docstrings

**Issue**: Docstrings incorrectly state "Base symbol (without suffix)".

**Location**: `src/infrastructure/persistence/positions_repository.py`

**Current Docstrings:**
- Line 53: `symbol: Base symbol (without suffix)`
- Line 81: `symbol: Base symbol (without suffix)`
- Line 202: `symbol: Base symbol (without suffix)`
- Line 238: `symbol: Base symbol (without suffix)`

**Problem**:
- After migration, positions will have full symbols
- Docstrings are misleading
- Developers may pass base symbols expecting them to work

**Fix Required:**
```python
# Before:
symbol: Base symbol (without suffix)

# After:
symbol: Full trading symbol (e.g., "RELIANCE-EQ", "SALSTEEL-BE")
```

**Checklist:**
- [ ] Update all docstrings in `positions_repository.py`
- [ ] Update method parameter descriptions
- [ ] Update return value descriptions if needed
- [ ] Verify all callers pass full symbols

---

## 9. Web Frontend

### 9.1 Frontend Symbol Display

**Issue**: Frontend may need to handle full symbols for display.

**Files:**
- `web/src/routes/dashboard/DashboardHome.tsx` - May display symbols
- `web/src/routes/dashboard/PaperTradingHistoryPage.tsx` - May display symbols
- Other frontend components

**Problem**:
- Frontend may need to extract base symbol for display
- Or display full symbols as-is
- Need to ensure consistent formatting

**Fix Required:**
- Review frontend symbol display
- Decide if full symbols should be displayed or base symbols
- Update frontend to handle full symbols correctly

**Checklist:**
- [ ] Review frontend symbol usage
- [ ] Update symbol display logic if needed
- [ ] Test frontend with full symbols
- [ ] Update frontend documentation

---

## 10. Summary Checklist

### High Priority
- [ ] `analysis_deduplication_service.py` - Position queries
- [ ] `paper_trading_service_adapter.py` - Ticker creation and matching
- [ ] `server/app/routers/broker.py` - Position queries
- [ ] `server/app/routers/orders.py` - Ticker creation
- [ ] `positions_repository.py` - Docstring updates
- [ ] Test files - Mock data and comparisons

### Medium Priority
- [ ] Signals table - Symbol format decision
- [ ] Manual order matcher - Matching logic
- [ ] Scripts directory - Symbol extraction updates
- [ ] Documentation updates

### Low Priority
- [ ] Web frontend - Symbol display
- [ ] Other API routes (if any)
- [ ] Other service files (if any)

---

## 8. Migration Strategy for Additional Locations

### Phase 1: Identify All Locations
- [x] Search codebase for symbol usage
- [x] List all files needing updates
- [ ] Review each file for specific changes needed

### Phase 2: Update Application Services
- [ ] Update `analysis_deduplication_service.py`
- [ ] Update `paper_trading_service_adapter.py`
- [ ] Test service functionality

### Phase 3: Update API Routes
- [ ] Update `orders.py`
- [ ] Update `broker.py`
- [ ] Test API endpoints

### Phase 4: Update Tests
- [ ] Update mock data
- [ ] Update assertions
- [ ] Run test suite
- [ ] Fix failing tests

### Phase 5: Update Documentation
- [ ] Update repository docstrings
- [ ] Update all documentation files
- [ ] Update examples
- [ ] Update API docs

### Phase 6: Update Scripts
- [ ] Review all utility scripts
- [ ] Update scripts to handle full symbols
- [ ] Test scripts after migration

### Phase 7: Update Frontend (if needed)
- [ ] Review frontend symbol display
- [ ] Update frontend if needed
- [ ] Test frontend with full symbols

---

## 9. Notes

### Important Considerations

1. **Signals Table**: ✅ **CONFIRMED** - Stores base symbols. Recommended to keep base symbols (signals are segment-agnostic). Need matching logic to extract base symbol when querying positions.

2. **Paper Trading**: Uses different symbol format - need to ensure consistency.

3. **Test Files**: Many tests will need updates. Consider creating a test helper function for symbol creation.

4. **Backward Compatibility**: Some code may need to handle both base and full symbols during transition.

### Test Helper Function

Consider creating a test helper:

```python
# tests/conftest.py or tests/helpers.py
def create_position_with_symbol(symbol: str, **kwargs) -> Mock:
    """
    Create a mock position with full symbol.

    Args:
        symbol: Full symbol (e.g., "RELIANCE-EQ") or base (will be converted)
        **kwargs: Other position attributes

    Returns:
        Mock position object
    """
    from modules.kotak_neo_auto_trader.utils.symbol_utils import ensure_full_symbol

    full_symbol = ensure_full_symbol(symbol)
    position = Mock(spec=Positions)
    position.symbol = full_symbol
    # Set other attributes from kwargs
    for key, value in kwargs.items():
        setattr(position, key, value)
    return position
```

---

## 11. Alembic Migration Files

### 11.1 Existing Migration Files

**File**: `alembic/versions/d1e2f3a4b5c6_add_entry_rsi_to_positions_and_backfill.py`

**Issue**: SQL queries join positions and orders by symbol.

**Location**: Lines 58, 70, 85, 96, 111

**Current SQL:**
```sql
WHERE o.user_id = positions.user_id
  AND o.symbol = positions.symbol
```

**Status**: ✅ **No action needed**
- This migration has already run
- After our migration, both positions and orders will have full symbols
- The join will work correctly (both full symbols match)
- No changes needed to existing migration files

**Note**: Future migrations should use full symbols for joins.

**Checklist:**
- [x] ✅ Reviewed existing migration files
- [ ] No changes needed to existing migrations
- [ ] Future migrations should use full symbols

---

## 12. Complete File List

### Files Requiring Updates

**Application Services (2):**
- `src/application/services/analysis_deduplication_service.py`
- `src/application/services/paper_trading_service_adapter.py`

**API Routes (2):**
- `server/app/routers/orders.py`
- `server/app/routers/broker.py`

**Repositories (2):**
- `src/infrastructure/persistence/positions_repository.py` (docstrings)
- `src/infrastructure/persistence/orders_repository.py` (has_ongoing_buy_order callers)

**Scripts (6+):**
- `scripts/find_order_ids.py`
- `scripts/check_user_orders_and_signals.py`
- `scripts/fix_tracking_data_corruption.py`
- `scripts/verify_tracking_data.py`
- `scripts/migration/migrate_trades_history.py`
- `scripts/migration/migrate_pending_orders.py`
- (Other scripts may need review)

**Test Files (155+):**
- All test files using symbols (see grep results)

**Frontend (2+):**
- `web/src/routes/dashboard/DashboardHome.tsx`
- `web/src/routes/dashboard/PaperTradingHistoryPage.tsx`
- (Other frontend files may need review)

**Documentation (4+):**
- `docs/API_COMPATIBILITY_VERIFICATION.md`
- `docs/API_COMPATIBILITY_POSITIONS.md`
- `documents/kotak_neo_trader/SELL_ORDER_IMPLEMENTATION_COMPLETE.md`
- `documents/EDGE_CASES.md`
- (Other docs may need review)

**Total**: ~170+ files may need updates

---

**Document Version**: 1.1
**Last Updated**: 2025-01-17
**Status**: Additional locations identified and documented
