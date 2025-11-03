# Kotak Neo Session Validity

## Current Understanding

### Expected Validity

Based on code and documentation:

1. **Official Statement**: "Session will remain active for the entire trading day"
   - Location: `auth.py:94` and `run_trading_service.py:103`
   - This is what Kotak Neo intends/recommends

2. **Documentation References**:
   - Session cache "Auto-expires end-of-day" (`KOTAK_NEO_COMMANDS.md`)
   - "session token is cached and reused automatically until EOD" (`README.md`)
   - Designed for daily use patterns

### Actual Behavior (Observations)

1. **JWT Token Expiry**:
   - Error code `'900901'` indicates JWT token has expired
   - Error messages: "invalid jwt token" or "invalid credentials"
   - Can occur during the day, not just at EOD

2. **No Explicit Duration Specified**:
   - No specific time duration mentioned in code (hours, minutes)
   - No session timeout configuration available
   - Relies on Kotak Neo's internal JWT expiry logic

3. **Re-Authentication Evidence**:
   - `force_relogin()` method exists to handle expired JWT
   - `get_orders()` has re-auth handling for error code `'900901'`
   - Indicates JWT can expire during trading hours

## Key Findings

### ✅ Expected Duration
- **Design Goal**: Entire trading day (morning market open to 6 PM EOD)
- **Typical Use Case**: Single login at startup, active until end-of-day

### ⚠️ Actual Reality
- **JWT Tokens Can Expire**: During the day, not just at EOD
- **Expiry Indicators**:
  - Error code: `'900901'`
  - Error message contains: `'invalid jwt token'` or `'invalid credentials'`
- **No Guaranteed Duration**: No explicit TTL mentioned in documentation

### 🔍 Potential Expiry Scenarios

1. **Long-Running Services**:
   - Service running 24/7 across multiple days
   - JWT may expire between trading days
   - Re-authentication needed at start of new trading day

2. **Extended Trading Sessions**:
   - If session created early morning (e.g., 8 AM)
   - May expire before end-of-day (6 PM)
   - ~10 hours or more of runtime could trigger expiry

3. **Idle Timeout**:
   - Possible that inactive sessions expire faster
   - No confirmation, but common in API designs

## Recommendations

### For Production Systems

1. **Monitor JWT Expiry**:
   - Watch for error code `'900901'` in all API responses
   - Implement re-authentication on all critical methods
   - Don't rely solely on "entire day" assumption

2. **Implement Proactive Re-Auth**:
   - Consider re-authenticating before critical operations
   - Add health check to validate session validity
   - Re-authenticate if session is older than X hours

3. **Error Handling**:
   - Always handle `'900901'` error code
   - Implement retry logic with re-auth for all API calls
   - Log JWT expiry events to track actual duration

4. **Session Refresh Strategy**:
   - Option 1: Reactive - Re-auth on error (current approach in `get_orders()`)
   - Option 2: Proactive - Re-auth before critical operations
   - Option 3: Scheduled - Re-auth periodically (e.g., every 8 hours)

## Current Implementation Status

### ✅ Has Re-Authentication
- `orders.py` - `get_orders()` - Handles error code `'900901'`

### ❌ Missing Re-Authentication
- `orders.py` - `place_equity_order()` - No re-auth on expiry
- `orders.py` - `modify_order()` - No re-auth on expiry
- `orders.py` - `cancel_order()` - No re-auth on expiry
- `market_data.py` - `get_quote()` - No re-auth on expiry
- `market_data.py` - `get_ltp()` - No re-auth on expiry
- `portfolio.py` - `get_positions()` - No re-auth on expiry
- `portfolio.py` - `get_limits()` - No re-auth on expiry

## Conclusion

**Session Validity**: Kotak Neo expects sessions to last "the entire trading day" but JWT tokens can expire during the day. The actual duration is not explicitly documented, and expiry must be handled reactively through error detection and re-authentication.

**Best Practice**: Implement re-authentication handling for all critical API operations, don't assume session will last the entire day without expiry.

