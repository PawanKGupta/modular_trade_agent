# Test Implementation Issues and Fixes

## ✅ FIXES APPLIED

### 1. Fixed OrderStatus.RETRY_PENDING → OrderStatus.FAILED
- Changed all `OrderStatus.RETRY_PENDING` references to `OrderStatus.FAILED`
- Affected tests: `test_2_2`, `test_4_2`

### 2. Fixed Missing order_type Field
- Added `order_type="limit"` to all `Orders()` creations in tests
- Affected tests: `test_6_1`, `test_6_2`, `test_6_3`, `test_7_1`

### 3. Fixed Field Names: executed_price → execution_price
- Changed `executed_price` to `execution_price`
- Changed `executed_quantity` to `execution_qty`
- Affected test: `test_7_1`

### 4. Fixed Missing orders_repo Initialization
- Added `engine.orders_repo = OrdersRepository(session)` in `mock_engine` fixture
- This should fix orders not being placed in several tests

## ⚠️ REMAINING ISSUES

## Summary of Failed Tests

### 1. Orders Not Being Placed (assert 0 == 1 or assert 0 == 3)
**Affected Tests:**
- `test_1_1_complete_workflow_real_trading`
- `test_1_3_multiple_signals_multiple_positions`
- `test_2_5_multiple_buy_orders_same_symbol_duplicate_prevention`
- `test_3_1_eod_cleanup_with_pending_buy_orders`
- `test_2_3_buy_order_partial_fill`

**Root Cause:**
The `place_new_entries` method requires:
- `engine.orders_repo` to be initialized (for database persistence)
- Proper signal-to-recommendation conversion
- Valid holdings check (may fail if portfolio.get_holdings() returns error)

**Fix Required:**
- ✅ Initialize `engine.orders_repo` in `mock_engine` fixture - **DONE**
- ⚠️ Ensure `engine.portfolio.get_holdings()` returns valid response - **MAY NEED ADDITIONAL MOCKING**
- ⚠️ Mock the signal loading/conversion process if needed - **MAY NEED ADDITIONAL MOCKING**

**Additional Investigation Needed:**
- Check if `place_new_entries` requires signals to be loaded from database
- Verify that the recommendation-to-order conversion works correctly
- Ensure portfolio holdings check doesn't block order placement

### 2. OrderStatus.RETRY_PENDING Doesn't Exist
**Affected Tests:**
- `test_2_2_buy_order_insufficient_balance_premarket_retry_success`
- `test_4_2_premarket_retry_still_insufficient_balance`

**Root Cause:**
`OrderStatus` enum only has: `PENDING`, `ONGOING`, `CLOSED`, `FAILED`, `CANCELLED`
There is no `RETRY_PENDING` status. Failed orders that need retry should use `OrderStatus.FAILED`.

**Fix Required:**
✅ Replace `OrderStatus.RETRY_PENDING` with `OrderStatus.FAILED` in tests. - **DONE**

### 3. Missing order_type Field
**Affected Tests:**
- `test_6_1_sell_order_execution_target_reached`
- `test_6_2_sell_order_ema9_update_lower_only`
- `test_6_3_sell_order_rsi_exit`

**Root Cause:**
When creating `Orders` objects directly in tests, the `order_type` field is required (NOT NULL constraint).
The field should be `"market"` or `"limit"`.

**Fix Required:**
✅ Add `order_type="limit"` or `order_type="market"` when creating Orders in tests. - **DONE**

### 4. Wrong Field Name: executed_price vs execution_price
**Affected Tests:**
- `test_7_1_trade_closure_with_profit`

**Root Cause:**
The `Orders` model uses `execution_price` (not `executed_price`).
Similarly, it uses `execution_qty` (not `executed_quantity`).

**Fix Required:**
✅ Change `executed_price=2600.0` to `execution_price=2600.0` - **DONE**
✅ Change `executed_quantity=40` to `execution_qty=40.0` - **DONE**

## Implementation Details

### Orders Model Required Fields:
```python
Orders(
    user_id=int,           # Required
    symbol=str,            # Required
    side=str,              # Required: "buy" | "sell"
    order_type=str,        # Required: "market" | "limit" (NOT NULL)
    quantity=float,        # Required
    price=float | None,    # Optional (required for limit orders)
    status=OrderStatus,    # Required (defaults to PENDING)
    # ... other optional fields
)
```

### OrderStatus Enum Values:
- `PENDING` - Order placed, waiting execution
- `ONGOING` - Order executed (replaces old EXECUTED)
- `CLOSED` - Order closed/fully filled
- `FAILED` - Order failed/rejected (includes retry-pending cases)
- `CANCELLED` - Order cancelled

### place_new_entries Requirements:
1. `engine.auth.is_authenticated()` must return True
2. `engine.orders` must be initialized
3. `engine.portfolio` must be initialized
4. `engine.orders_repo` should be initialized for DB persistence
5. `engine.strategy_config` must have `user_capital` set
6. Portfolio holdings check must succeed
