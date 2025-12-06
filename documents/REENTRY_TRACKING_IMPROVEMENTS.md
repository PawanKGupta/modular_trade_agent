# Reentry Tracking Improvements

## Identified Improvements

### 1. **Duplicate Reentry Detection** 🔴 HIGH PRIORITY

**Problem**: If the same order executes multiple times (e.g., due to retry or reconciliation), we might add duplicate reentry entries.

**Current Code**: 
```python
# unified_order_monitor.py:653
reentries_array.append(reentry_data)  # No duplicate check!
```

**Solution**: Check if reentry with same order_id or timestamp already exists:
```python
# Check for duplicate reentry (same order_id or very similar timestamp)
order_id_in_reentry = reentry_data.get("order_id") or order_id
existing_reentry = next(
    (r for r in reentries_array 
     if r.get("order_id") == order_id_in_reentry or 
        (r.get("time") == reentry_data["time"] and r.get("qty") == reentry_data["qty"])),
    None
)
if existing_reentry:
    logger.warning(f"Duplicate reentry detected for {base_symbol}, skipping")
    return
```

**Impact**: Prevents duplicate reentry entries in database

---

### 2. **Data Validation Before Write** 🟡 MEDIUM PRIORITY

**Problem**: No validation that reentry data has required fields before writing to database.

**Current Code**: Directly appends reentry_data without validation.

**Solution**: Add validation function:
```python
def _validate_reentry_data(reentry_data: dict) -> bool:
    """Validate reentry data structure before writing"""
    required_fields = ["qty", "price", "time"]
    for field in required_fields:
        if field not in reentry_data:
            logger.error(f"Missing required field '{field}' in reentry data")
            return False
    
    # Validate types
    if not isinstance(reentry_data["qty"], int) or reentry_data["qty"] <= 0:
        logger.error(f"Invalid qty: {reentry_data['qty']}")
        return False
    
    if not isinstance(reentry_data["price"], (int, float)) or reentry_data["price"] <= 0:
        logger.error(f"Invalid price: {reentry_data['price']}")
        return False
    
    # Validate time format
    try:
        datetime.fromisoformat(reentry_data["time"])
    except (ValueError, TypeError):
        logger.error(f"Invalid time format: {reentry_data['time']}")
        return False
    
    return True
```

**Impact**: Prevents invalid data from being written to database

---

### 3. **Data Integrity Check** 🟡 MEDIUM PRIORITY

**Problem**: `reentry_count` might not match length of `reentries` array if updates fail partially.

**Current Code**: 
```python
reentry_count = len(reentries_array)  # Calculated but not validated
```

**Solution**: Add integrity check after update:
```python
# After upsert, verify integrity
updated_position = self.positions_repo.get_by_symbol(self.user_id, base_symbol)
if updated_position:
    actual_count = len(updated_position.reentries or [])
    if updated_position.reentry_count != actual_count:
        logger.warning(
            f"Reentry count mismatch for {base_symbol}: "
            f"count={updated_position.reentry_count}, array_length={actual_count}. "
            f"Fixing..."
        )
        # Fix the mismatch
        self.positions_repo.upsert(
            user_id=self.user_id,
            symbol=base_symbol,
            reentry_count=actual_count,
            # ... other fields
        )
```

**Impact**: Ensures data consistency in database

---

### 4. **Position Closed Check** 🔴 HIGH PRIORITY

**Problem**: If position is closed but reentry order executes, we might reopen it incorrectly.

**Current Code**: 
```python
if existing_pos:  # Doesn't check if position is closed!
    is_reentry = True
```

**Solution**: Check if position is closed:
```python
if existing_pos:
    if existing_pos.closed_at is not None:
        logger.warning(
            f"Reentry order executed for closed position {base_symbol}. "
            f"Position was closed at {existing_pos.closed_at}. "
            f"Skipping reentry update."
        )
        return  # Don't add reentry to closed position
    
    is_reentry = True
```

**Impact**: Prevents reopening closed positions incorrectly

---

### 5. **Add Order ID to Reentry Data** 🟡 MEDIUM PRIORITY

**Problem**: Can't track which order_id created which reentry entry.

**Current Code**: Reentry data doesn't include order_id.

**Solution**: Add order_id to reentry data:
```python
reentry_data = {
    "qty": int(execution_qty),
    "level": int(reentry_level) if reentry_level is not None else None,
    "rsi": float(reentry_rsi) if reentry_rsi is not None else None,
    "price": float(reentry_price),
    "time": execution_time.isoformat(),
    "order_id": order_id,  # NEW: Track which order created this reentry
}
```

**Impact**: Better traceability and duplicate detection

---

### 6. **Performance: Cache reentries_today() Results** 🟢 LOW PRIORITY

**Problem**: `reentries_today()` is called multiple times for same symbol, but always queries database.

**Current Code**: Always queries database.

**Solution**: Add short-lived cache (e.g., 1 minute):
```python
from functools import lru_cache
from datetime import datetime, timedelta

# Cache with TTL
_reentry_cache: dict[tuple[int, str], tuple[int, datetime]] = {}

def reentries_today(self, base_symbol: str) -> int:
    cache_key = (self.user_id, base_symbol.upper())
    now = datetime.now()
    
    # Check cache
    if cache_key in _reentry_cache:
        count, cached_time = _reentry_cache[cache_key]
        if now - cached_time < timedelta(minutes=1):
            return count
    
    # Query database
    count = self._query_reentries_today(base_symbol)
    
    # Update cache
    _reentry_cache[cache_key] = (count, now)
    return count
```

**Impact**: Reduces database queries for repeated calls

---

### 7. **Better Error Messages** 🟢 LOW PRIORITY

**Problem**: Generic error messages don't help debugging.

**Current Code**: 
```python
except Exception as e:
    logger.error(f"Error creating/updating position from executed order {order_id}: {e}")
```

**Solution**: More specific error messages:
```python
except ValueError as e:
    logger.error(
        f"Invalid data for position update: {base_symbol}, order_id={order_id}: {e}"
    )
except Exception as e:
    logger.error(
        f"Unexpected error updating position for {base_symbol}, order_id={order_id}: {e}",
        exc_info=True
    )
```

**Impact**: Easier debugging

---

## Recommended Implementation Order

1. **Position Closed Check** (High Priority) - Prevents data corruption
2. **Duplicate Reentry Detection** (High Priority) - Prevents duplicate entries
3. **Data Validation** (Medium Priority) - Prevents invalid data
4. **Add Order ID** (Medium Priority) - Better traceability
5. **Data Integrity Check** (Medium Priority) - Ensures consistency
6. **Performance Cache** (Low Priority) - Optimization
7. **Better Error Messages** (Low Priority) - Developer experience

