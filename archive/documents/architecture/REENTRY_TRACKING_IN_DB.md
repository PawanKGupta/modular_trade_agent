# Reentry Tracking in Database - Current State

## Summary

**Reentries are NOT properly tracked in the database.** The current implementation has significant gaps:

1. ❌ **Positions Table**: No reentry tracking at all
2. ⚠️ **Orders Table**: Reentry orders are stored as regular buy orders (no `entry_type` flag)
3. ✅ **Trade History JSON**: Reentries are tracked in the `reentries` array

## Current Implementation

### How Reentries Work

When a reentry order is placed (averaging down):

1. **Order Placement** (`evaluate_reentries_and_exits()` - Line 3343):
   ```python
   resp = self.orders.place_market_buy(
       symbol=place_symbol,
       quantity=qty,
       variety=self.strategy_config.default_variety,
       exchange=self.strategy_config.default_exchange,
       product=self.strategy_config.default_product,
   )
   ```

2. **Order Storage in DB**:
   - Order is created via `OrderTracker.add_pending_order()` → `orders_repo.create_amo()`
   - **Problem**: `create_amo()` does NOT accept `order_metadata` parameter
   - **Result**: Reentry orders are stored as regular buy orders with NO indication they're reentries

3. **Trade History Update** (Line 3446-3471):
   ```python
   # Update trade history with new total quantity
   for e in entries:
       old_qty = e.get("qty", 0)
       new_total_qty = old_qty + qty
       e["qty"] = new_total_qty
       
       # Also add reentry metadata for tracking
       if "reentries" not in e:
           e["reentries"] = []
       e["reentries"].append({
           "qty": qty,
           "level": next_level,
           "rsi": rsi,
           "price": price,
           "time": datetime.now().isoformat(),
       })
   ```
   - **Location**: Only in `trades_history.json` file
   - **NOT synced to positions table**
   - **NOT stored in Orders table metadata**

4. **Position Update**:
   - When reentry order executes, `_update_position_from_trade()` is called
   - **Problem**: It only updates `quantity` and `avg_price` in positions table
   - **Missing**: No reentry history, no reentry count, no reentry details

## What's Missing

### 1. Positions Table
- ❌ No `reentry_count` field
- ❌ No `reentries` JSON array
- ❌ No way to query "positions with reentries"
- ❌ No way to see reentry history for a position

### 2. Orders Table
- ❌ No `entry_type` field to distinguish reentry orders from initial entries
- ❌ `order_metadata` is not set for reentry orders
- ❌ Cannot query "all reentry orders for a symbol"
- ❌ Cannot link reentry orders to their parent position

### 3. Relationship Tracking
- ❌ No foreign key relationship between reentry orders and initial entry order
- ❌ No way to group orders by position (initial + reentries)
- ❌ No way to see the full order history for a position

## Current Workarounds

### To Get Reentry Information:

1. **From Trade History JSON**:
   ```python
   history = load_history(history_path)
   for trade in history.get("trades", []):
       if trade.get("status") == "open":
           reentries = trade.get("reentries", [])
           # Access reentry details here
   ```

2. **From Orders Table** (Partial):
   - Query all buy orders for a symbol
   - **Problem**: Cannot distinguish which are reentries vs initial entries
   - **Problem**: Cannot link reentry orders to their parent position

3. **From Positions Table**:
   - Only shows aggregated `quantity` and `avg_price`
   - **Problem**: Cannot see individual reentry details
   - **Problem**: Cannot see reentry count

## Impact

### Functional Issues:

1. **Daily Reentry Cap Check** (`reentries_today()` - Line 1570):
   - Currently checks `trades_history.json` for `entry_type == "reentry"`
   - **Problem**: Reentries are NOT stored as separate entries with `entry_type="reentry"`
   - **Problem**: Reentries are added to the `reentries` array of existing trade
   - **Result**: Daily cap check may not work correctly

2. **Reentry History**:
   - Cannot query reentry history from database
   - Must read `trades_history.json` file
   - Not available via API queries

3. **Position Analysis**:
   - Cannot analyze "positions with reentries" vs "positions without reentries"
   - Cannot see reentry patterns (how many times user averaged down)
   - Cannot calculate average reentry price vs initial entry price

## Recommended Solutions

### Option 1: Add Reentry Tracking to Orders Table (Recommended)

**Add `entry_type` field to Orders table**:
```python
class Orders(Base):
    # ... existing fields ...
    entry_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # 'initial', 'reentry', 'manual'
```

**Update `create_amo()` to accept metadata**:
```python
def create_amo(
    self,
    *,
    user_id: int,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None,
    order_id: str | None = None,
    broker_order_id: str | None = None,
    entry_type: str | None = None,  # NEW
    order_metadata: dict | None = None,  # NEW
) -> Orders:
```

**When placing reentry order**:
```python
# In evaluate_reentries_and_exits()
self.orders_repo.create_amo(
    user_id=self.user_id,
    symbol=symbol,
    side="buy",
    order_type="market",
    quantity=qty,
    price=price,
    entry_type="reentry",  # Mark as reentry
    order_metadata={
        "rsi_level": next_level,
        "rsi": rsi,
        "reentry_index": len(existing_reentries) + 1,
    }
)
```

### Option 2: Add Reentry Tracking to Positions Table

**Add reentry fields to Positions table**:
```python
class Positions(Base):
    # ... existing fields ...
    reentry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reentries: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Array of reentry details
    initial_entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_reentry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
```

**Update `_update_position_from_trade()` to sync reentries**:
```python
def _update_position_from_trade(self, trade: dict[str, Any]) -> None:
    # ... existing code ...
    
    if status == "open":
        reentries = trade.get("reentries", [])
        self.positions_repo.upsert(
            user_id=self.user_id,
            symbol=symbol,
            quantity=qty,
            avg_price=entry_price,
            opened_at=entry_time,
            reentry_count=len(reentries),  # NEW
            reentries=reentries,  # NEW
        )
```

### Option 3: Hybrid Approach (Best)

**Combine both approaches**:
1. **Orders Table**: Add `entry_type` to distinguish reentry orders
2. **Positions Table**: Add `reentry_count` and `reentries` JSON for quick lookup
3. **Link Orders**: Add `parent_order_id` or `position_id` to link reentry orders to position

**Benefits**:
- Can query reentry orders from Orders table
- Can see reentry summary in Positions table
- Can link reentry orders to their parent position
- Maintains backward compatibility

## Current Code Locations

### Reentry Logic:
- **Placement**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` - Line 3056-3473
- **Trade History Update**: Line 3446-3471
- **Daily Cap Check**: Line 1570-1595

### Order Creation:
- **`create_amo()`**: `src/infrastructure/persistence/orders_repository.py` - Line 188-215
- **`add_pending_order()`**: `modules/kotak_neo_auto_trader/order_tracker.py` - Line 146-221

### Position Updates:
- **`_update_position_from_trade()`**: `modules/kotak_neo_auto_trader/auto_trade_engine.py` - Line 320-383

## Conclusion

**Current State**: Reentries are only tracked in `trades_history.json`, not in the database.

**Impact**: Cannot query reentry data from database, must read JSON file.

**Recommendation**: Implement Option 3 (Hybrid Approach) to properly track reentries in both Orders and Positions tables.

