# Race Condition Fix - Concurrent Reentry Executions

**Date**: 2025-12-07
**Status**: ✅ **FIXED**
**Issue**: Race Condition #2 - Concurrent Reentry Executions

---

## Problem Summary

Even though the daily cap (max 1 reentry per symbol per day) prevents multiple reentry orders from being placed, concurrent execution processing could still cause race conditions:

1. **Same order processed multiple times**: If `check_buy_order_status()` is called concurrently, the same order could be detected as executed multiple times.

2. **Position quantity read-modify-write race**: The position update uses a read-modify-write pattern without locking, causing lost updates when multiple threads process concurrently.

---

## Solution: Database-Level Locking

### Implementation

**Added `get_by_symbol_for_update()` method** to `PositionsRepository`:
```python
def get_by_symbol_for_update(self, user_id: int, symbol: str) -> Positions | None:
    """
    Get position by symbol with row-level lock (SELECT ... FOR UPDATE).

    This prevents concurrent modifications by locking the row until
    the transaction commits.
    """
    stmt = (
        select(Positions)
        .where(Positions.user_id == user_id, Positions.symbol == symbol)
        .with_for_update()
    )
    return self.db.execute(stmt).scalar_one_or_none()
```

### Updated Operations

All position update operations now use locking:

1. **`_create_position_from_executed_order()`**:
   - Uses `get_by_symbol_for_update()` when reading position
   - Uses locked read during integrity check

2. **`upsert()`**:
   - Uses `get_by_symbol_for_update()` when updating existing position

3. **`mark_closed()`**:
   - Uses `get_by_symbol_for_update()` before closing position

4. **`reduce_quantity()`**:
   - Uses `get_by_symbol_for_update()` before reducing quantity

---

## How It Works

### Before (Race Condition)

```
Time T1: Thread A
  - Reads position: quantity = 100
  - Calculates: new_qty = 100 + 10 = 110
  - Updates position: quantity = 110 ✅

Time T2: Thread B (concurrent)
  - Reads position: quantity = 100 (before A's update committed)
  - Calculates: new_qty = 100 + 15 = 115
  - Updates position: quantity = 115 ❌ (overwrites A's update!)

Result: Position shows 115, but should be 125 (100 + 10 + 15)
```

### After (With Locking)

```
Time T1: Thread A
  - Locks row (SELECT ... FOR UPDATE)
  - Reads position: quantity = 100
  - Calculates: new_qty = 100 + 10 = 110
  - Updates position: quantity = 110
  - Commits transaction → Releases lock ✅

Time T2: Thread B (waits for lock)
  - Waits for Thread A's lock to be released
  - Locks row (SELECT ... FOR UPDATE)
  - Reads position: quantity = 110 (sees A's update!)
  - Calculates: new_qty = 110 + 15 = 125
  - Updates position: quantity = 125 ✅
  - Commits transaction → Releases lock

Result: Position shows 125 (correct!)
```

---

## Benefits

1. **Prevents Lost Updates**: Concurrent operations are serialized, ensuring all updates are applied
2. **Correct Quantity Calculations**: Each operation sees the latest state
3. **Works with Transactions**: Lock is held for the transaction duration
4. **Database-Level Solution**: Works across multiple application instances/processes

---

## Technical Details

### Lock Scope

- Lock is acquired when `get_by_symbol_for_update()` is called
- Lock is held until the transaction commits or rolls back
- Other transactions trying to lock the same row will wait

### Transaction Integration

The locking works seamlessly with the transaction safety implementation:
```python
with transaction(self.positions_repo.db):
    # Lock acquired here
    existing_pos = self.positions_repo.get_by_symbol_for_update(user_id, symbol)

    # Calculate new quantity
    new_qty = existing_pos.quantity + execution_qty

    # Update position (lock still held)
    self.positions_repo.upsert(quantity=new_qty, auto_commit=False)

# Lock released when transaction commits
```

### Database Compatibility

- **PostgreSQL**: Full row-level locking support ✅
- **MySQL**: Full row-level locking support ✅
- **SQLite**: `SELECT ... FOR UPDATE` is a no-op (no actual locking), but pattern is correct
  - For SQLite, application-level locking or optimistic locking would be needed for true concurrency control
  - The code pattern is correct and will work in production databases

---

## Testing

**Test File**: `tests/unit/infrastructure/test_position_locking.py`

**Tests Added**:
1. `test_get_by_symbol_for_update_locks_row()` - Verifies locking method works
2. `test_concurrent_reentry_updates_serialized()` - Tests concurrent update serialization
3. `test_upsert_uses_locking_for_existing_position()` - Verifies upsert uses locking
4. `test_mark_closed_uses_locking()` - Verifies mark_closed uses locking
5. `test_reduce_quantity_uses_locking()` - Verifies reduce_quantity uses locking

**All tests passing**: ✅ 5/5

---

## Files Changed

1. **`src/infrastructure/persistence/positions_repository.py`**:
   - Added `get_by_symbol_for_update()` method
   - Updated `upsert()`, `mark_closed()`, `reduce_quantity()` to use locking

2. **`modules/kotak_neo_auto_trader/unified_order_monitor.py`**:
   - Updated `_create_position_from_executed_order()` to use locked reads
   - Updated integrity check to use locked read

3. **`tests/unit/infrastructure/test_position_locking.py`** (new):
   - Comprehensive tests for locking behavior

4. **`ORDER_MANAGEMENT_COMPLETE.md`** (in same folder):
   - Updated to reflect fix status

---

## Related Issues

- **Transaction Safety** (Flaw #1): Also fixed - ensures atomicity of operations
- **Daily Cap**: Reduces likelihood of concurrent executions from different orders
- **Duplicate Detection**: Prevents duplicate reentry entries (complements locking)

---

## Status

✅ **FIXED** (2025-12-07)

The race condition has been resolved through database-level locking. All position update operations now use `SELECT ... FOR UPDATE` to ensure serialized access and prevent lost updates.
