# Re-Authentication Handling Analysis

## Current Status

### ✅ Methods WITH Re-Authentication Handling

1. **`orders.py` - `get_orders()`**
   - **Status**: ✅ Fully implemented
   - **Error Detection**: Checks for:
     - Error code `'900901'`
     - Description containing `'invalid jwt token'`
     - Message containing `'invalid credentials'`
   - **Re-Auth Flow**:
     - Calls `self.auth.force_relogin()` on first failure
     - Retries API call once after successful re-auth
     - Prevents infinite retry loops with `_retry_count` parameter
   - **Code Location**: `modules/kotak_neo_auto_trader/orders.py:306-343`

### ❌ Methods WITHOUT Re-Authentication Handling

1. **`orders.py` - `place_equity_order()`**
   - **Status**: ❌ No re-auth handling
   - **Impact**: HIGH - Order placement will fail silently if JWT expires
   - **Current Behavior**: Returns `None` on failure without attempting re-auth
   - **Risk**: Orders might not be placed during JWT expiry

2. **`orders.py` - `modify_order()`**
   - **Status**: ❌ No re-auth handling
   - **Impact**: HIGH - Order modifications will fail if JWT expires
   - **Current Behavior**: Returns `None` on failure

3. **`orders.py` - `cancel_order()`**
   - **Status**: ❌ No re-auth handling
   - **Impact**: HIGH - Order cancellation will fail if JWT expires
   - **Current Behavior**: Returns `None` on failure

4. **`market_data.py` - `get_quote()`**
   - **Status**: ❌ No re-auth handling
   - **Impact**: MEDIUM - Quote fetching will fail if JWT expires
   - **Current Behavior**: Returns `None` on failure

5. **`market_data.py` - `get_ltp()`**
   - **Status**: ❌ No re-auth handling
   - **Impact**: MEDIUM - LTP fetching will fail if JWT expires
   - **Current Behavior**: Falls back to yfinance (if available) or returns `None`

6. **`portfolio.py` - `get_positions()`**
   - **Status**: ❌ No re-auth handling
   - **Impact**: MEDIUM - Position retrieval will fail if JWT expires
   - **Current Behavior**: Returns `None` on failure

7. **`portfolio.py` - `get_limits()`**
   - **Status**: ❌ No re-auth handling
   - **Impact**: LOW - Limits retrieval will fail if JWT expires
   - **Current Behavior**: Returns `None` on failure

8. **`orders.py` - `get_pending_orders()`**
   - **Status**: ⚠️ Partial (indirect)
   - **Impact**: MEDIUM - Uses `get_orders()` which has re-auth, but filters results
   - **Note**: Will benefit from re-auth if `get_orders()` handles it successfully

9. **`orders.py` - `get_executed_orders()`**
   - **Status**: ⚠️ Partial (indirect)
   - **Impact**: MEDIUM - Uses `get_orders()` which has re-auth, but filters results
   - **Note**: Will benefit from re-auth if `get_orders()` handles it successfully

## Common Authorization Error Patterns

Based on `get_orders()` implementation, the following patterns indicate JWT expiry/auth failure:

1. **Error Code**: `'900901'`
2. **Error Description**: Contains `'invalid jwt token'` (case-insensitive)
3. **Error Message**: Contains `'invalid credentials'` (case-insensitive)
4. **HTTP Status**: Typically `401 Unauthorized` or `403 Forbidden`

## Recommended Fix Strategy

### 1. Create Reusable Re-Auth Helper Method

Add a helper method in `orders.py` or create a mixin/base class:

```python
def _check_and_reauth_on_error(self, response: Dict, retry_count: int = 0) -> bool:
    """
    Check if response indicates auth failure and attempt re-authentication.
    
    Returns:
        True if re-auth was attempted and successful, False otherwise
    """
    if not isinstance(response, dict):
        return False
    
    code = response.get('code', '')
    message = str(response.get('message', '')).lower()
    description = str(response.get('description', '')).lower()
    
    # Detect JWT expiry / auth failure
    if code == '900901' or 'invalid jwt token' in description or 'invalid credentials' in message:
        if retry_count == 0:
            logger.warning("❌ JWT token expired - attempting re-authentication...")
            if hasattr(self.auth, 'force_relogin') and self.auth.force_relogin():
                logger.info("✅ Re-authentication successful")
                return True
            else:
                logger.error("❌ Re-authentication failed")
                return False
    
    return False
```

### 2. Apply Re-Auth Pattern to All Critical Methods

Methods to update (in priority order):

1. **HIGH PRIORITY**:
   - `place_equity_order()` - Order placement is critical
   - `modify_order()` - Order modification is critical
   - `cancel_order()` - Order cancellation is critical

2. **MEDIUM PRIORITY**:
   - `get_quote()` - Used for LTP fetching
   - `get_positions()` - Used for portfolio tracking
   - `get_pending_orders()` - Should add explicit handling even though it uses `get_orders()`
   - `get_executed_orders()` - Should add explicit handling even though it uses `get_orders()`

3. **LOW PRIORITY**:
   - `get_limits()` - Less frequently used
   - Other market data methods

### 3. Implementation Pattern

For each method, wrap the API call with:

```python
def place_equity_order(self, ..., _retry_count: int = 0) -> Optional[Dict]:
    # ... existing code ...
    
    try:
        response = method(**payload)
        
        # Check for auth failure
        if isinstance(response, dict) and self._check_and_reauth_on_error(response, _retry_count):
            # Retry once after re-auth
            return self.place_equity_order(..., _retry_count=1)
        
        # ... handle response ...
        
    except Exception as e:
        # Check if exception indicates auth failure
        error_str = str(e).lower()
        if 'jwt' in error_str or 'unauthorized' in error_str or 'invalid credentials' in error_str:
            if _retry_count == 0 and hasattr(self.auth, 'force_relogin') and self.auth.force_relogin():
                return self.place_equity_order(..., _retry_count=1)
        
        logger.error(f"Error placing order: {e}")
        return None
```

## Current Risk Assessment

### High Risk Scenarios

1. **Long-Running Service**: If service runs for hours/days, JWT will eventually expire
2. **Order Placement at Market Open**: If JWT expires between initialization and 9:15 AM, orders won't be placed
3. **Order Modifications During Day**: If JWT expires during monitoring, EMA9 updates will fail
4. **Critical Operations**: Any operation that doesn't retry after re-auth will fail permanently until service restart

### Current Mitigation

- ✅ `get_orders()` has re-auth - helps with order status checks
- ❌ Order placement has no re-auth - orders will fail to place
- ❌ Order modifications have no re-auth - price updates will fail
- ❌ Market data has no re-auth - will fallback to yfinance (delayed data)

## Recommendations

1. **Immediate**: Add re-auth handling to `place_equity_order()`, `modify_order()`, and `cancel_order()`
2. **Short-term**: Add re-auth handling to `get_quote()` and `get_positions()`
3. **Long-term**: Consider implementing a middleware/decorator pattern for automatic re-auth on all API calls

## Testing Checklist

For each method with re-auth added:
- [ ] Test with expired JWT (mock or wait for expiry)
- [ ] Verify re-auth is triggered correctly
- [ ] Verify retry after re-auth succeeds
- [ ] Verify no infinite retry loops
- [ ] Test error handling when re-auth itself fails
- [ ] Test concurrent requests during re-auth

