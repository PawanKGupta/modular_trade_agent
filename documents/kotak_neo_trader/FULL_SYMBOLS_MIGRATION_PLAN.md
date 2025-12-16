# Full Symbols Migration Plan

**Last Updated**: 2025-01-17
**Status**: Planning
**Goal**: Migrate from base symbols to full symbols everywhere (without smart matching)

## Executive Summary

This document outlines the migration plan to use full trading symbols (e.g., `RELIANCE-EQ`, `SALSTEEL-BE`) everywhere in the system instead of base symbols (e.g., `RELIANCE`, `SALSTEEL`). Since scrip master is broker-provided and segments are tracked as separate instruments, exact symbol matching is sufficient and more accurate.

### Key Benefits
- ✅ More accurate: Segments tracked separately (correct behavior)
- ✅ Simpler: No base symbol extraction needed for matching
- ✅ Consistent: Matches broker's model (segments are different instruments)
- ✅ No aggregation issues: Each segment is independent

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

## Phase 1: Database Schema & Migration

### 1.1 Current State Analysis

**Positions Table:**
- `symbol` column: `String(32)` - Currently stores base symbols (e.g., `RELIANCE`)
- No schema change needed (can store full symbols)

**Orders Table:**
- `symbol` column: `String(32)` - Already stores full symbols (e.g., `RELIANCE-EQ`)
- No schema change needed

**Migration Strategy:**
- Convert existing base symbols in positions table to full symbols
- Use matching orders to determine correct segment
- Default to `-EQ` if no matching order found

### 1.2 Migration Script

**File**: `alembic/versions/XXXXX_migrate_to_full_symbols.py`

**Steps:**
1. Update positions from matching orders (preferred)
2. Default remaining base symbols to `-EQ` suffix
3. Verify all positions have full symbols

**Checklist:**
- [ ] Create Alembic migration script
- [ ] Test migration on development database
- [ ] Backup production database before migration
- [ ] Run migration script
- [ ] Verify all positions have full symbols
- [ ] Document any positions that couldn't be migrated

### 1.3 Migration Script Template

```python
"""migrate_to_full_symbols

Revision ID: XXXXX_migrate_to_full_symbols
Revises: <previous_revision>
Create Date: 2025-01-17
"""

from alembic import op
from sqlalchemy import text

def upgrade() -> None:
    """
    Migrate positions table from base symbols to full symbols.

    Strategy:
    1. For each position with base symbol (e.g., "RELIANCE")
    2. Find matching order(s) to get full symbol (e.g., "RELIANCE-EQ")
    3. Update position.symbol to full symbol
    4. If no matching order found, default to "{base_symbol}-EQ"
    """

    # Step 1: Update positions from matching orders
    op.execute(text("""
        UPDATE positions p
        SET symbol = (
            SELECT o.symbol
            FROM orders o
            WHERE o.user_id = p.user_id
              AND o.side = 'buy'
              AND o.status = 'ONGOING'
              AND UPPER(SPLIT_PART(o.symbol, '-', 1)) = UPPER(p.symbol)
            ORDER BY o.placed_at DESC
            LIMIT 1
        )
        WHERE p.symbol NOT LIKE '%-EQ'
          AND p.symbol NOT LIKE '%-BE'
          AND p.symbol NOT LIKE '%-BL'
          AND p.symbol NOT LIKE '%-BZ'
          AND EXISTS (
              SELECT 1 FROM orders o
              WHERE o.user_id = p.user_id
                AND o.side = 'buy'
                AND o.status = 'ONGOING'
                AND UPPER(SPLIT_PART(o.symbol, '-', 1)) = UPPER(p.symbol)
          )
    """))

    # Step 2: Default remaining base symbols to -EQ
    op.execute(text("""
        UPDATE positions
        SET symbol = symbol || '-EQ'
        WHERE symbol NOT LIKE '%-EQ'
          AND symbol NOT LIKE '%-BE'
          AND symbol NOT LIKE '%-BL'
          AND symbol NOT LIKE '%-BZ'
    """))

    # Step 3: Verify migration (log positions that still don't have suffix)
    # This should return 0 rows
    result = op.get_bind().execute(text("""
        SELECT user_id, symbol, quantity
        FROM positions
        WHERE symbol NOT LIKE '%-EQ'
          AND symbol NOT LIKE '%-BE'
          AND symbol NOT LIKE '%-BL'
          AND symbol NOT LIKE '%-BZ'
    """))

    if result.rowcount > 0:
        raise ValueError(
            f"Migration incomplete: {result.rowcount} positions still have base symbols"
        )


def downgrade() -> None:
    """
    Revert to base symbols (extract base from full symbols).
    Note: This is a one-way migration in practice.
    """
    op.execute(text("""
        UPDATE positions
        SET symbol = UPPER(SPLIT_PART(symbol, '-', 1))
    """))
```

---

## Phase 2: Core Code Changes

### 2.1 Files to Update

**Primary Files:**
1. `modules/kotak_neo_auto_trader/sell_engine.py` - ~15 locations
2. `modules/kotak_neo_auto_trader/unified_order_monitor.py` - ~10 locations
3. `modules/kotak_neo_auto_trader/auto_trade_engine.py` - ~5 locations
4. `src/infrastructure/persistence/orders_repository.py` - ~3 locations
5. `modules/kotak_neo_auto_trader/manual_order_matcher.py` - ~5 locations
6. `modules/kotak_neo_auto_trader/portfolio.py` - ~3 locations
7. `modules/kotak_neo_auto_trader/run_trading_service.py` - ~2 locations

### 2.2 sell_engine.py Changes

#### Change 1: `_register_order()` - Use Full Symbols as Keys

**Location**: Line ~232-233

**Current:**
```python
base_symbol = extract_base_symbol(symbol).upper()
self.active_sell_orders[base_symbol] = {
    "order_id": order_id,
    "target_price": target_price,
    "qty": qty,
    "ticker": ticker,
    **kwargs,
}
```

**New:**
```python
full_symbol = symbol.upper()  # Already has suffix from scrip master
self.active_sell_orders[full_symbol] = {
    "order_id": order_id,
    "target_price": target_price,
    "qty": qty,
    "ticker": ticker,
    **kwargs,
}
```

**Checklist:**
- [ ] Update `_register_order()` method
- [ ] Update all callers to pass full symbols
- [ ] Update all `active_sell_orders` lookups to use full symbols

#### Change 2: `get_open_positions()` - Store Full Symbols

**Location**: Line ~471

**Current:**
```python
base_symbol = extract_base_symbol(symbol).upper()
broker_holdings_map[base_symbol] = qty
```

**New:**
```python
full_symbol = symbol.upper()  # Keep full symbol from broker
broker_holdings_map[full_symbol] = qty
```

**Checklist:**
- [ ] Update `get_open_positions()` method
- [ ] Remove base symbol extraction
- [ ] Verify broker holdings map uses full symbols

#### Change 3: `_reconcile_positions_with_broker_holdings()` - Exact Matching

**Location**: Line ~1637-1663

**Current:**
```python
base_symbol = extract_base_symbol(symbol).upper()
if base_symbol and qty > 0:
    broker_holdings_map[base_symbol] = qty

# Later:
symbol = pos.symbol.upper()
broker_qty = broker_holdings_map.get(symbol, 0)
```

**New:**
```python
full_symbol = symbol.upper()  # Keep full symbol from broker
if full_symbol and qty > 0:
    broker_holdings_map[full_symbol] = qty

# Later:
symbol = pos.symbol.upper()  # Already full symbol after migration
broker_qty = broker_holdings_map.get(symbol, 0)  # ✅ Exact match
```

**Checklist:**
- [ ] Update broker holdings map creation
- [ ] Remove base symbol extraction
- [ ] Verify exact matching works
- [ ] Update logging to show full symbols

#### Change 4: `_reconcile_single_symbol()` - Exact Matching

**Location**: Line ~1899-1900

**Current:**
```python
base_symbol = extract_base_symbol(holding_symbol).upper()
if base_symbol == symbol.upper():
    broker_qty = int(holding.get("quantity", 0))
    break
```

**New:**
```python
full_symbol = holding_symbol.upper()
if full_symbol == symbol.upper():  # ✅ Exact match
    broker_qty = int(holding.get("quantity", 0))
    break
```

**Checklist:**
- [ ] Update `_reconcile_single_symbol()` method
- [ ] Remove base symbol extraction
- [ ] Verify exact matching logic

#### Change 5: `_detect_manual_sells_from_orders()` - Exact Matching

**Location**: Line ~970-1001

**Current:**
```python
# Build symbol_to_position map
symbol_to_position = {}
for pos in open_positions:
    base_symbol = extract_base_symbol(pos.symbol).upper()
    symbol_to_position[base_symbol] = {...}

# Later:
base_symbol = extract_base_symbol(trading_symbol).upper()
if base_symbol not in symbol_to_position:
    continue
```

**New:**
```python
# Build symbol_to_position map
symbol_to_position = {}
for pos in open_positions:
    full_symbol = pos.symbol.upper()  # Already full symbol
    symbol_to_position[full_symbol] = {...}

# Later:
full_symbol = trading_symbol.upper()
if full_symbol not in symbol_to_position:
    logger.debug(
        f"Skipping manual sell order {order_id} for {full_symbol}: "
        f"Not in tracked positions (likely manual buy or different segment)"
    )
    continue
```

**Checklist:**
- [ ] Update `symbol_to_position` map building
- [ ] Update manual sell detection logic
- [ ] Update all references to use full symbols
- [ ] Update logging messages

#### Change 6: `_detect_and_track_pending_manual_sell_orders()` - Exact Matching

**Location**: Line ~1363-1517

**Changes:**
- Similar to Change 5
- Use full symbols for matching
- Remove base symbol extraction

**Checklist:**
- [ ] Update pending manual sell detection
- [ ] Use full symbols for matching
- [ ] Update logging

#### Change 7: All `active_sell_orders` Lookups

**Locations**: Multiple throughout file

**Find all:**
```python
self.active_sell_orders[base_symbol]
```

**Replace with:**
```python
self.active_sell_orders[full_symbol]
```

**Where `full_symbol` is obtained from:**
- `position.symbol` (already full after migration)
- `trade.get("placed_symbol")` or `trade.get("symbol")` (should be full)
- Scrip master resolution

**Checklist:**
- [ ] Find all `active_sell_orders` lookups
- [ ] Replace with full symbol lookups
- [ ] Verify symbol source is full symbol

### 2.3 unified_order_monitor.py Changes

#### Change 1: `_create_position_from_executed_order()` - Store Full Symbol

**Location**: Line ~993-1020

**Current:**
```python
base_symbol = extract_base_symbol(symbol).upper()

# Later:
self.positions_repo.upsert(
    user_id=self.user_id,
    symbol=base_symbol,  # ❌ Base symbol
    ...
)
```

**New:**
```python
full_symbol = symbol.upper()  # Already full from broker/order

# Later:
self.positions_repo.upsert(
    user_id=self.user_id,
    symbol=full_symbol,  # ✅ Full symbol
    ...
)
```

**Checklist:**
- [ ] Update position creation to use full symbols
- [ ] Remove base symbol extraction for position storage
- [ ] Verify symbol comes from order (already full)
- [ ] **IMPORTANT**: If ticker is created here, use `get_ticker_from_full_symbol()`

#### Change 2: `check_and_place_sell_orders_for_new_holdings()` - Use Full Symbols

**Location**: Line ~1792-1847

**Current:**
```python
base_symbol = extract_base_symbol(db_order.symbol).upper()
base_sym = extract_base_symbol(db_order.symbol).upper()
ticker = f"{base_sym}.NS"

trade = {
    "symbol": base_symbol,
    ...
}
```

**New:**
```python
full_symbol = db_order.symbol.upper()  # Already full from orders table
# Use helper function for ticker creation
from modules.kotak_neo_auto_trader.utils.symbol_utils import get_ticker_from_full_symbol
ticker = get_ticker_from_full_symbol(full_symbol)  # ✅ "RELIANCE-EQ" -> "RELIANCE.NS"

trade = {
    "symbol": full_symbol,  # ✅ Full symbol for matching
    "ticker": ticker,
    "placed_symbol": full_symbol,  # ✅ Full symbol
    ...
}
```

**Checklist:**
- [ ] Update to use full symbols from orders
- [ ] Use `get_ticker_from_full_symbol()` helper for ticker creation
- [ ] Update trade dict to use full symbols

#### Change 3: Buy Order Reconciliation - Exact Matching

**Location**: Line ~466

**Current:**
```python
holding_base = extract_base_symbol(holding_symbol).upper()
if holding_base == base_symbol:
    found_in_holdings = True
```

**New:**
```python
holding_full_symbol = holding_symbol.upper()
if holding_full_symbol == order_symbol.upper():  # ✅ Exact match
    found_in_holdings = True
```

**Checklist:**
- [ ] Update reconciliation logic
- [ ] Use exact symbol matching
- [ ] Update variable names for clarity

### 2.4 auto_trade_engine.py Changes

#### Change 1: Verify `_resolve_broker_symbol()` Usage

**Location**: Line ~2361

**Action**: Verify all callers use the resolved full symbol

**Checklist:**
- [ ] Review all callers of `_resolve_broker_symbol()`
- [ ] Ensure resolved symbol is used (not base symbol)
- [ ] Update any code that extracts base symbol after resolution

#### Change 2: Position Updates - Use Full Symbols

**Locations**: Multiple

**Action**: Ensure all position creation/updates use full symbols

**Checklist:**
- [ ] Find all position creation/update calls
- [ ] Verify they use full symbols
- [ ] Update any that use base symbols

### 2.5 orders_repository.py Changes

#### Change 1: Update Duplicate Check Logic

**Location**: Line ~224-252

**Current:**
```python
symbol_upper = symbol.upper().strip()
base_symbol = symbol_upper.split("-")[0].strip()

# Check exact match first, then base match
if existing_symbol_upper == symbol_upper:
    # Exact match
    return existing_order
if existing_base == base_symbol:
    # Base match (fallback)
    return existing_order
```

**New:**
```python
symbol_upper = symbol.upper().strip()

# Only exact match (full symbols are different instruments)
if existing_symbol_upper == symbol_upper:
    logger.warning(
        f"Duplicate order prevented: Active buy order already exists "
        f"with symbol '{symbol}'. "
        f"Existing order: {existing_order.symbol} (id: {existing_order.id}, "
        f"status: {existing_order.status}). "
        f"Returning existing order."
    )
    return existing_order
```

**Checklist:**
- [ ] Remove base symbol fallback check
- [ ] Keep only exact match
- [ ] Update logging messages
- [ ] Verify logic handles different segments correctly

#### Change 2: `has_ongoing_buy_order()` - Verify Callers

**Location**: Line ~351-372

**Status**: ✅ **No code change needed** - Already uses exact matching

**Action Required**: Verify all callers pass full symbols

**Checklist:**
- [ ] Review all callers of `has_ongoing_buy_order()`
- [ ] Update callers that pass base symbols to pass full symbols
- [ ] Test with full symbols

#### Change 3: Signal Matching - No Change Needed

**Location**: Line ~545

**Status**: ✅ **No change needed** - Correctly extracts base symbol for signal matching

**Note**: Signals table stores base symbols, so base symbol extraction is correct here

### 2.6 positions_repository.py Changes

#### Change: Verify `get_by_symbol()` Usage

**Location**: Line ~24

**Action**: Ensure all callers pass full symbols

**Checklist:**
- [ ] Review all callers of `get_by_symbol()`
- [ ] Update callers to pass full symbols
- [ ] Add validation/warning if base symbol is passed

### 2.7 Other Files

**Files to Review:**
- `modules/kotak_neo_auto_trader/manual_order_matcher.py`
- `modules/kotak_neo_auto_trader/portfolio.py`
- `modules/kotak_neo_auto_trader/run_trading_service.py`
- `modules/kotak_neo_auto_trader/run_sell_orders.py`
- `modules/kotak_neo_auto_trader/storage.py`
- `modules/kotak_neo_auto_trader/services/indicator_service.py`
- `modules/kotak_neo_auto_trader/services/portfolio_service.py`
- `modules/kotak_neo_auto_trader/order_state_manager.py`

**Checklist:**
- [ ] Review each file for base symbol usage
- [ ] Update to use full symbols where appropriate
- [ ] Keep base symbol extraction only for ticker format

---

## Phase 3: Helper Functions & Utilities

### 3.1 Update symbol_utils.py

**File**: `modules/kotak_neo_auto_trader/utils/symbol_utils.py`

#### New Function: `ensure_full_symbol()`

```python
def ensure_full_symbol(
    symbol: str,
    scrip_master=None,
    exchange: str = "NSE"
) -> str:
    """
    Ensure symbol has segment suffix. Use scrip master if available.

    Args:
        symbol: Symbol (may be base or full)
        scrip_master: Scrip master instance (optional)
        exchange: Exchange (default: NSE)

    Returns:
        Full symbol with suffix (e.g., "RELIANCE-EQ")
    """
    symbol = normalize_symbol(symbol)

    # Already has suffix
    if any(symbol.endswith(suf) for suf in ["-EQ", "-BE", "-BL", "-BZ"]):
        return symbol

    # Try scrip master resolution
    if scrip_master:
        instrument = scrip_master.get_instrument(symbol, exchange=exchange)
        if instrument and instrument.get("symbol"):
            return instrument["symbol"].upper()

    # Fallback to -EQ
    return f"{symbol}-EQ"
```

#### New Function: `get_ticker_from_full_symbol()`

```python
def get_ticker_from_full_symbol(
    full_symbol: str,
    exchange: str = "NS"
) -> str:
    """
    Convert full trading symbol to yfinance ticker format.

    This extracts the base symbol and adds exchange suffix.
    yfinance requires base symbols (e.g., "RELIANCE.NS"), not full symbols
    (e.g., "RELIANCE-EQ.NS").

    Args:
        full_symbol: Full trading symbol (e.g., "RELIANCE-EQ", "SALSTEEL-BE")
        exchange: Exchange suffix (default: "NS" for NSE, "BO" for BSE)

    Returns:
        Ticker format (e.g., "RELIANCE.NS", "SALSTEEL.NS")

    Examples:
        >>> get_ticker_from_full_symbol("RELIANCE-EQ")
        "RELIANCE.NS"
        >>> get_ticker_from_full_symbol("SALSTEEL-BE")
        "SALSTEEL.NS"
        >>> get_ticker_from_full_symbol("TCS")  # Already base
        "TCS.NS"
    """
    base_symbol = extract_base_symbol(full_symbol)
    return f"{base_symbol}.{exchange}"
```

#### New Function: `get_base_symbol_for_ticker()`

```python
def get_base_symbol_for_ticker(full_symbol: str) -> str:
    """
    Extract base symbol for ticker format (e.g., "RELIANCE.NS").

    This is ONLY for ticker format, not for matching.
    Prefer using get_ticker_from_full_symbol() for ticker creation.

    Args:
        full_symbol: Full trading symbol (e.g., "RELIANCE-EQ")

    Returns:
        Base symbol (e.g., "RELIANCE")
    """
    return extract_base_symbol(full_symbol)
```

**Checklist:**
- [ ] Add `ensure_full_symbol()` function
- [ ] Add `get_ticker_from_full_symbol()` function (PRIMARY)
- [ ] Add `get_base_symbol_for_ticker()` function (helper)
- [ ] Update documentation
- [ ] Add unit tests

### 3.2 Ticker Creation Fixes Required

**CRITICAL**: After migration, all ticker creation must extract base symbol first.

#### Files Requiring Ticker Creation Fixes

| File | Line | Current Code | Fix Required |
|------|------|--------------|--------------|
| `sell_engine.py` | 493 | `ticker = f"{pos.symbol}.NS"` | Extract base first |
| `sell_engine.py` | 623 | `ticker = position.get("ticker", f"{symbol}.NS")` | Extract base first |
| `sell_engine.py` | 742 | `ticker = position.get("ticker", f"{symbol}.NS")` | Extract base first |
| `sell_engine.py` | 832 | `ticker = f"{symbol}.NS"` | Extract base first |
| `auto_trade_engine.py` | 347 | `f"{pos.symbol}.NS"` | Extract base first |
| `auto_trade_engine.py` | 387 | `f"{pos.symbol}.NS"` | Extract base first |
| `auto_trade_engine.py` | 3193 | `f"{symbol}.NS"` | Extract base first |
| `auto_trade_engine.py` | 4902 | `f"{symbol}.NS"` | Extract base first |
| `auto_trade_engine.py` | 5386 | `f"{symbol}.NS"` | Extract base first |
| `storage.py` | 292 | `f"{symbol}.NS"` | Extract base first |
| `indicator_service.py` | 553 | `f"{symbol}.NS"` | Extract base first |
| `price_service.py` | 576 | `f"{symbol}.NS"` | Extract base first |
| `live_price_manager.py` | 212 | `f"{symbol}.NS"` | Extract base first |
| `position_monitor.py` | 228 | `f"{symbol}.NS"` | Extract base first |

**Note**: Some files already do this correctly (e.g., `unified_order_monitor.py:1816-1817`).

#### Standard Pattern for Ticker Creation

**Before (incorrect after migration):**
```python
# ❌ WRONG: Assumes symbol is base, but after migration it's full
ticker = f"{pos.symbol}.NS"  # If pos.symbol = "RELIANCE-EQ", creates "RELIANCE-EQ.NS" (invalid!)
```

**After (correct):**
```python
# ✅ CORRECT: Extract base symbol first
from modules.kotak_neo_auto_trader.utils.symbol_utils import get_ticker_from_full_symbol

ticker = get_ticker_from_full_symbol(pos.symbol)  # "RELIANCE-EQ" -> "RELIANCE.NS"
```

**Or manually:**
```python
# ✅ CORRECT: Manual extraction
from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_base_symbol

base_symbol = extract_base_symbol(pos.symbol)  # "RELIANCE-EQ" -> "RELIANCE"
ticker = f"{base_symbol}.NS"  # "RELIANCE.NS"
```

**Checklist:**
- [ ] Review all ticker creation locations
- [ ] Replace with `get_ticker_from_full_symbol()` helper
- [ ] Verify yfinance compatibility
- [ ] Test ticker creation for all segments (EQ, BE, BL, BZ)

---

## Phase 4: Testing & Validation

### 4.1 Unit Tests

#### Test 1: Full Symbol Storage

**File**: `tests/unit/kotak/test_full_symbol_storage.py`

```python
def test_position_stores_full_symbol():
    """Verify positions table stores full symbols"""
    position = positions_repo.upsert(
        user_id=1,
        symbol="RELIANCE-EQ",  # Full symbol
        quantity=100,
        avg_price=2500.0,
        ...
    )
    assert position.symbol == "RELIANCE-EQ"
```

**Checklist:**
- [ ] Create test file
- [ ] Test position creation with full symbols
- [ ] Test position retrieval with full symbols
- [ ] Verify no base symbols are stored

#### Test 2: Exact Matching in Reconciliation

**File**: `tests/unit/kotak/test_reconciliation_exact_match.py`

```python
def test_reconciliation_exact_match():
    """Verify reconciliation matches exact symbols"""
    # Position: RELIANCE-EQ
    # Broker holdings: RELIANCE-EQ
    # Should match exactly
    position = create_position("RELIANCE-EQ", 100)
    broker_holdings = [{"tradingSymbol": "RELIANCE-EQ", "quantity": 100}]

    # ... reconciliation logic
    assert broker_qty == 100  # ✅ Matches
```

**Checklist:**
- [ ] Create test file
- [ ] Test exact symbol matching
- [ ] Test different segments don't match
- [ ] Test reconciliation logic

#### Test 3: Different Segments Tracked Separately

**File**: `tests/unit/kotak/test_segment_separation.py`

```python
def test_different_segments_tracked_separately():
    """Verify RELIANCE-EQ and RELIANCE-BE are tracked separately"""
    # Create position: RELIANCE-EQ
    # Broker holdings: RELIANCE-BE
    # Should NOT match (different instruments)
    position = create_position("RELIANCE-EQ", 100)
    broker_holdings = [{"tradingSymbol": "RELIANCE-BE", "quantity": 50}]

    # ... reconciliation
    assert broker_qty == 0  # ✅ No match (different segments)
```

**Checklist:**
- [ ] Create test file
- [ ] Test segment separation
- [ ] Verify different segments don't interfere
- [ ] Test multiple segments for same base symbol

#### Test 4: Manual Sell Detection - Exact Match

**File**: `tests/unit/kotak/test_manual_sell_exact_match.py`

```python
def test_manual_sell_detection_exact_match():
    """Verify manual sell detection matches exact symbols"""
    # Position: RELIANCE-EQ
    # Manual sell: RELIANCE-EQ
    # Should detect
    position = create_position("RELIANCE-EQ", 100)
    manual_sell = {"tradingSymbol": "RELIANCE-EQ", "quantity": 100}

    # ... detection logic
    assert detected == True  # ✅ Detected
```

**Checklist:**
- [ ] Create test file
- [ ] Test exact match detection
- [ ] Test different segments don't match
- [ ] Test partial sells

#### Test 5: Scrip Master Resolution Consistency

**File**: `tests/unit/kotak/test_scrip_master_consistency.py`

```python
def test_scrip_master_resolution_consistent():
    """Verify scrip master always resolves to same segment"""
    symbol1 = scrip_master.get_trading_symbol("RELIANCE", "NSE")
    symbol2 = scrip_master.get_trading_symbol("RELIANCE", "NSE")
    assert symbol1 == symbol2  # ✅ Consistent
```

**Checklist:**
- [ ] Create test file
- [ ] Test scrip master consistency
- [ ] Test resolution for various symbols
- [ ] Verify deterministic behavior

### 4.2 Integration Tests

**Checklist:**
- [ ] Test end-to-end order placement with full symbols
- [ ] Test position creation from executed orders
- [ ] Test reconciliation with broker holdings
- [ ] Test manual sell detection
- [ ] Test sell order placement

### 4.3 Regression Tests

**Checklist:**
- [ ] Run full test suite
- [ ] Verify no existing tests break
- [ ] Update tests that expect base symbols
- [ ] Add new tests for full symbol behavior

---

## Phase 5: Migration Execution

### 5.1 Pre-Migration Checklist

- [ ] Backup production database
- [ ] Verify scrip master is loaded and working
- [ ] Test scrip master resolution for all active positions
- [ ] Document current symbol formats in database
- [ ] Review all active positions and their symbols
- [ ] Identify any positions without matching orders
- [ ] Prepare rollback plan
- [ ] Schedule migration window (low-traffic period)

### 5.2 Migration Steps

**Step 1: Database Migration**
- [ ] Run Alembic migration script
- [ ] Verify migration completed successfully
- [ ] Check for any errors or warnings
- [ ] Verify all positions have full symbols

**Step 2: Code Deployment**
- [ ] Deploy updated code
- [ ] Verify services start correctly
- [ ] Check logs for any symbol-related errors
- [ ] Monitor error rates

**Step 3: Validation**
- [ ] Verify reconciliation works correctly
- [ ] Verify manual sell detection works
- [ ] Verify order placement works
- [ ] Verify position creation works
- [ ] Monitor logs for 24 hours

### 5.3 Post-Migration Checklist

- [ ] All positions have full symbols
- [ ] All new positions created with full symbols
- [ ] Reconciliation matches exact symbols
- [ ] Manual sell detection works
- [ ] No symbol mismatch errors in logs
- [ ] Performance is acceptable
- [ ] No increase in error rates
- [ ] User feedback is positive

---

## Phase 6: Code Locations Summary

### 6.1 Primary Files

| File | Locations | Priority |
|------|-----------|----------|
| `sell_engine.py` | ~15 | High |
| `unified_order_monitor.py` | ~10 | High |
| `auto_trade_engine.py` | ~5 | Medium |
| `orders_repository.py` | ~3 | Medium |
| `manual_order_matcher.py` | ~5 | Medium |
| `portfolio.py` | ~3 | Low |
| `run_trading_service.py` | ~2 | Low |

### 6.2 Additional Locations

**IMPORTANT**: See `FULL_SYMBOLS_MIGRATION_ADDITIONAL_LOCATIONS.md` for additional files that need updates:

- Application Services (`analysis_deduplication_service.py`, `paper_trading_service_adapter.py`)
- API Routes (`server/app/routers/orders.py`, `server/app/routers/broker.py`)
- Test Files (155+ files may need updates)
- Documentation files
- Signals table (symbol format decision needed)

### 6.3 Key Changes Summary

1. **Remove base symbol extraction** from matching logic
2. **Update all `symbol_to_position` dictionaries** to use full symbols
3. **Update all `active_sell_orders`** to use full symbols as keys
4. **Remove base symbol aggregation** logic
5. **Update all matching/comparison logic** to use exact matching
6. **Keep base symbol extraction** only for ticker format (`.NS`)
7. **Fix all ticker creation** to use `get_ticker_from_full_symbol()` helper
8. **Distinguish between matching (full) and ticker creation (base)**

---

## Phase 7: Rollback Plan

### 7.1 Rollback Triggers

Rollback if:
- Migration script fails
- High error rate after deployment
- Reconciliation fails
- Manual sell detection fails
- User reports issues

### 7.2 Rollback Steps

**Step 1: Revert Code**
- [ ] Revert code changes to previous version
- [ ] Deploy reverted code
- [ ] Verify services restart correctly

**Step 2: Database Rollback (Optional)**
- [ ] Run migration downgrade (if needed)
- [ ] Or keep full symbols (backward compatible with base symbol matching)

**Step 3: Hybrid Approach (If Needed)**
- [ ] Add temporary base symbol extraction for matching
- [ ] Keep full symbols in database
- [ ] Use base symbol matching as fallback
- [ ] Investigate and fix issues
- [ ] Re-apply migration when ready

### 7.3 Rollback Checklist

- [ ] Code reverted
- [ ] Services restarted
- [ ] System functioning normally
- [ ] Issues documented
- [ ] Root cause analysis completed
- [ ] Fix plan created

---

## Phase 8: Documentation Updates

### 8.1 Code Documentation

**Checklist:**
- [ ] Update docstrings to reflect full symbol usage
- [ ] Update comments explaining symbol matching
- [ ] Document scrip master as source of truth
- [ ] Update inline comments

### 8.2 User Documentation

**Checklist:**
- [ ] Update user guides (if any)
- [ ] Update API documentation
- [ ] Update troubleshooting guides

### 8.3 Technical Documentation

**Checklist:**
- [ ] Update architecture documents
- [ ] Update design decisions document
- [ ] Update migration notes
- [ ] Document lessons learned

---

## Implementation Order

### Recommended Sequence

1. **Phase 1**: Database migration (non-breaking, can run first)
2. **Phase 3**: Helper functions (add new, don't break existing)
3. **Phase 2**: Core code changes (update logic)
4. **Phase 4**: Testing (validate changes)
5. **Phase 5**: Deployment (monitor closely)
6. **Phase 6**: Documentation (ongoing)
7. **Phase 7**: Rollback (if needed)

### Timeline Estimate

- **Phase 1**: 1-2 days (migration script + testing)
- **Phase 2**: 3-5 days (code changes + review)
- **Phase 3**: 1 day (helper functions)
- **Phase 4**: 2-3 days (testing)
- **Phase 5**: 1 day (deployment)
- **Total**: ~8-12 days

---

## Risk Assessment

### High Risk Areas

1. **Reconciliation Logic**
   - Risk: May fail if broker returns different segment
   - Mitigation: Verify scrip master consistency, test thoroughly

2. **Manual Sell Detection**
   - Risk: May miss manual sells if segment differs
   - Mitigation: Test with various scenarios, monitor logs

3. **Position Creation**
   - Risk: May create positions with wrong symbols
   - Mitigation: Always use scrip master resolution

### Medium Risk Areas

1. **Active Sell Orders Tracking**
   - Risk: May lose track of orders if symbol format changes
   - Mitigation: Update all lookups, test thoroughly

2. **Order Matching**
   - Risk: May not match orders correctly
   - Mitigation: Use exact matching, test edge cases

### Low Risk Areas

1. **Ticker Format**
   - Risk: Medium (many places need fixes)
   - Mitigation: Use `get_ticker_from_full_symbol()` helper consistently
   - Action: Review all ticker creation locations (see Phase 3.2)

---

## Success Criteria

### Must Have

- ✅ All positions have full symbols
- ✅ Reconciliation works with exact matching
- ✅ Manual sell detection works
- ✅ Order placement works
- ✅ No increase in error rates
- ✅ All tests pass

### Nice to Have

- ✅ Improved performance (simpler matching)
- ✅ Better accuracy (segment separation)
- ✅ Cleaner code (less base symbol extraction)

---

## Notes

### Important Considerations

1. **Scrip Master Consistency**: Ensure scrip master always resolves to same segment
2. **Broker API Consistency**: Verify broker APIs return same segment we used
3. **Manual Trades**: Different segments from manual trades are not tracked (by design)
4. **Migration Safety**: Database migration is reversible (downgrade available)

### Open Questions

- [ ] Should we validate scrip master resolution before migration?
- [ ] How to handle positions without matching orders?
- [ ] Should we add monitoring for symbol mismatches?

---

## Appendix

### A. Symbol Format Examples

**Base Symbol**: `RELIANCE` (for yfinance ticker: `RELIANCE.NS`)
**Full Symbols** (for matching/comparison):
- `RELIANCE-EQ` (Equity segment)
- `RELIANCE-BE` (T2T segment)
- `RELIANCE-BL` (T2T segment)
- `RELIANCE-BZ` (T2T segment)

**Usage:**
- **Matching**: Use full symbols (`RELIANCE-EQ` == `RELIANCE-EQ`)
- **Ticker Creation**: Extract base first (`RELIANCE-EQ` → `RELIANCE` → `RELIANCE.NS`)

### B. Migration Script SQL (PostgreSQL)

```sql
-- Step 1: Update from matching orders
UPDATE positions p
SET symbol = (
    SELECT o.symbol
    FROM orders o
    WHERE o.user_id = p.user_id
      AND o.side = 'buy'
      AND o.status = 'ONGOING'
      AND UPPER(SPLIT_PART(o.symbol, '-', 1)) = UPPER(p.symbol)
    ORDER BY o.placed_at DESC
    LIMIT 1
)
WHERE p.symbol NOT LIKE '%-EQ'
  AND p.symbol NOT LIKE '%-BE'
  AND p.symbol NOT LIKE '%-BL'
  AND p.symbol NOT LIKE '%-BZ'
  AND EXISTS (
      SELECT 1 FROM orders o
      WHERE o.user_id = p.user_id
        AND o.side = 'buy'
        AND o.status = 'ONGOING'
        AND UPPER(SPLIT_PART(o.symbol, '-', 1)) = UPPER(p.symbol)
  );

-- Step 2: Default remaining to -EQ
UPDATE positions
SET symbol = symbol || '-EQ'
WHERE symbol NOT LIKE '%-EQ'
  AND symbol NOT LIKE '%-BE'
  AND symbol NOT LIKE '%-BL'
  AND symbol NOT LIKE '%-BZ';
```

### C. Migration Script SQL (SQLite)

```sql
-- Step 1: Update from matching orders
UPDATE positions
SET symbol = (
    SELECT o.symbol
    FROM orders o
    WHERE o.user_id = positions.user_id
      AND o.side = 'buy'
      AND o.status = 'ONGOING'
      AND UPPER(SUBSTR(o.symbol, 1, INSTR(o.symbol || '-', '-') - 1)) =
          UPPER(SUBSTR(positions.symbol, 1, INSTR(positions.symbol || '-', '-') - 1))
    ORDER BY o.placed_at DESC
    LIMIT 1
)
WHERE positions.symbol NOT LIKE '%-EQ'
  AND positions.symbol NOT LIKE '%-BE'
  AND positions.symbol NOT LIKE '%-BL'
  AND positions.symbol NOT LIKE '%-BZ'
  AND EXISTS (
      SELECT 1 FROM orders o
      WHERE o.user_id = positions.user_id
        AND o.side = 'buy'
        AND o.status = 'ONGOING'
        AND UPPER(SUBSTR(o.symbol, 1, INSTR(o.symbol || '-', '-') - 1)) =
            UPPER(SUBSTR(positions.symbol, 1, INSTR(positions.symbol || '-', '-') - 1))
  );

-- Step 2: Default remaining to -EQ
UPDATE positions
SET symbol = symbol || '-EQ'
WHERE symbol NOT LIKE '%-EQ'
  AND symbol NOT LIKE '%-BE'
  AND symbol NOT LIKE '%-BL'
  AND symbol NOT LIKE '%-BZ';
```

---

**Document Version**: 1.0
**Last Updated**: 2025-01-17
**Status**: Planning
**Next Steps**: Review and approve plan, then begin Phase 1
