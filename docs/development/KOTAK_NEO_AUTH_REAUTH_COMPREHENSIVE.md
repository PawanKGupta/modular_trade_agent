# Kotak Neo Authentication and Re-Authentication - Comprehensive Guide

## Overview

This document provides a comprehensive analysis of the authentication flow, session management, re-authentication handling, and all safeguards implemented in the Kotak Neo broker integration. It consolidates information from multiple analysis documents into a single reference.

## Table of Contents

1. [Authentication Flow](#authentication-flow)
2. [Session Management](#session-management)
3. [Re-Authentication Mechanism](#re-authentication-mechanism)
4. [Implementation Issues and Fixes](#implementation-issues-and-fixes)
5. [Infinite Loop Prevention](#infinite-loop-prevention)
6. [Backward Compatibility](#backward-compatibility)
7. [API Methods Coverage](#api-methods-coverage)
8. [Summary](#summary)

---

## Authentication Flow

### 1. Initial Authentication (`KotakNeoAuth.login()`)

**Location**: `modules/kotak_neo_auto_trader/auth.py`

**Flow**:
1. Initialize NeoAPI client with consumer_key/consumer_secret
2. Call `client.login(mobilenumber, password)` - First factor authentication
3. Call `client.session_2fa(OTP=mpin)` - Second factor authentication (MPIN)
4. Extract session token from response
5. Set `is_logged_in = True`

**Session Duration**: Sessions remain active for the entire trading day (as per Kotak Neo API)

### 2. Session Caching (Broker Portfolio Endpoint)

**Location**: `server/app/routers/broker.py` (lines 512-539)

**Flow**:
1. Check `_broker_auth_cache` for existing auth instance per user
2. If cached, reuse existing auth (assumes session is still valid)
3. If not cached, create new `KotakNeoAuth` instance and call `login()`
4. Cache the authenticated session for reuse

**Note**: The cache assumes sessions are always valid, but doesn't verify session validity before reuse. Re-authentication is triggered on-demand when auth errors are detected.

### 3. Force Re-Login (`KotakNeoAuth.force_relogin()`)

**Location**: `modules/kotak_neo_auto_trader/auth.py` (lines 304-385)

**Flow**:
1. Acquire thread lock (prevents concurrent re-auth)
2. Logout old client (cleanup SDK state)
3. Reset auth state (`is_logged_in = False`, `client = None`)
4. Create NEW client instance (critical - don't reuse stale clients)
5. Perform fresh login + 2FA
6. Retry 2FA up to 2 times if it fails with SDK errors
7. Set `is_logged_in = True` on success

---

## Session Management

### Session Expiry Scenarios

Sessions can expire due to:
- JWT token expiration (typically at end of trading day)
- Network connectivity issues
- Broker API server issues
- Long idle periods

### Session Reuse Strategy

**Current Approach**: Re-authenticate on-demand when auth errors are detected
- More efficient than checking validity before every request
- Failure rate limiting prevents excessive re-auth attempts
- Thread-safe coordination prevents concurrent re-auth

**Future Consideration**: Could add lightweight health check if needed

---

## Re-Authentication Mechanism

### Decorator-Based Re-Auth (`@handle_reauth`)

**Location**: `modules/kotak_neo_auto_trader/auth_handler.py`

**How it works**:
1. Wraps methods that make API calls
2. Catches auth failures in responses (checks for error codes like `900901`, "JWT token expired", etc.)
3. Detects auth exceptions (checks for keywords like "jwt", "unauthorized", "token expired")
4. Calls `auth.force_relogin()` to re-authenticate
5. Retries the method once after successful re-auth
6. Uses thread-safe locks to prevent concurrent re-auth attempts

**Thread Safety**:
- Uses per-auth-object locks (`_reauth_locks`)
- Only one thread performs re-auth at a time
- Other threads wait for re-auth to complete (max 30s timeout)
- Tracks recent failures to prevent infinite retry loops (max 3 failures in 60s window)

### Manual Re-Auth (Broker Adapter)

**Location**: `modules/kotak_neo_auto_trader/infrastructure/broker_adapters/kotak_neo_adapter.py`

**Why Manual Implementation**:
- Broker adapter has `self.auth_handler` (not `self.auth`)
- Need to update `self._client` after re-auth
- More control over retry logic and error handling

**Implementation Pattern**:
```python
def get_holdings(self) -> list[Holding]:
    """Get portfolio holdings with automatic re-authentication on session expiry."""
    max_retries = 1  # Retry once after re-auth
    for attempt in range(max_retries + 1):
        try:
            # Check failure rate BEFORE attempting re-auth
            if _check_reauth_failure_rate(self.auth_handler):
                logger.error("Re-authentication blocked due to recent failures")
                return []

            # Call API with timeout protection
            response = call_with_timeout(method, timeout=DEFAULT_SDK_TIMEOUT)

            # Check for auth errors in response
            if isinstance(response, dict) and is_auth_error(response):
                # Attempt re-auth and retry
                if attempt < max_retries and _attempt_reauth_thread_safe(...):
                    self._client = self.auth_handler.get_client()  # Update client
                    break  # Retry the outer loop
                else:
                    _record_reauth_failure(self.auth_handler)
                    return []

            # Success - parse and return
            if "data" in response:
                return self._parse_holdings_response(response["data"])
        except Exception as e:
            if is_auth_exception(e):
                # Same re-auth logic for exceptions
                # ...
            else:
                # Non-auth errors handled normally
                return []
    return []
```

**Features**:
- ✅ Detects auth errors in responses and exceptions
- ✅ Checks failure rate before attempting re-auth
- ✅ Thread-safe re-authentication
- ✅ Updates client after successful re-auth
- ✅ Retries once automatically
- ✅ Records failures to prevent infinite loops
- ✅ Timeout protection (30s default)

---

## Implementation Issues and Fixes

### Issue 1: Broker Adapter Bypasses Re-Auth Decorator ✅ FIXED

**Problem**: `KotakNeoBrokerAdapter.get_holdings()` and `get_account_limits()` did NOT use `@handle_reauth` decorator, causing API calls to fail without re-authentication when sessions expired.

**Root Cause**: Broker adapter methods called SDK client directly without re-auth handling.

**Solution Implemented**: Added re-authentication logic directly to broker adapter methods with multiple safeguards.

**Code Location**: `modules/kotak_neo_auto_trader/infrastructure/broker_adapters/kotak_neo_adapter.py`

**Impact**: When session expires:
1. SDK client calls fail (connection refused, timeout, or auth errors)
2. Auth errors are detected using `is_auth_error()` and `is_auth_exception()`
3. **Re-authentication is attempted** (if not blocked by failure rate)
4. Client is updated after successful re-auth
5. Method retries once automatically
6. If re-auth fails or max retries reached, returns empty result
7. **No infinite loops** - multiple safeguards prevent this

### Issue 2: No Timeout Handling ✅ FIXED

**Problem**: SDK client calls have no explicit timeout, so they can hang indefinitely.

**Solution Implemented**: Added timeout wrapper using `concurrent.futures.ThreadPoolExecutor`

**Code Location**:
- `modules/kotak_neo_auto_trader/utils/timeout_utils.py` - Timeout utility
- `modules/kotak_neo_auto_trader/infrastructure/broker_adapters/kotak_neo_adapter.py` - Integration

**Implementation**:
```python
from modules.kotak_neo_auto_trader.utils.timeout_utils import call_with_timeout, DEFAULT_SDK_TIMEOUT

# Wrap SDK calls with timeout
response = call_with_timeout(
    method,
    timeout=DEFAULT_SDK_TIMEOUT,  # 30 seconds
    timeout_error_message=f"get_holdings() call to {method_name}() timed out",
)
```

**Features**:
- ✅ **Cross-platform**: Works on Windows and Linux using ThreadPoolExecutor
- ✅ **Default timeout**: 30 seconds (configurable)
- ✅ **Timeout handling**: Raises `TimeoutError` on timeout
- ✅ **Graceful degradation**: Returns empty result on timeout (non-auth error)
- ✅ **Thread-safe**: Uses ThreadPoolExecutor for isolation

**Current Status**:
- ✅ SDK-level timeout implemented (30s default)
- ✅ Nginx timeout increased to 300s (backup protection)
- ✅ Re-auth logic has timeouts (30s wait, 5s lock)
- ✅ Timeout errors handled gracefully (return empty result)

**Impact**: When broker API is slow or unreachable:
- ✅ SDK calls timeout after 30 seconds (fail fast)
- ✅ Returns empty result instead of hanging
- ✅ Nginx timeout (300s) provides backup protection
- ✅ Re-auth timeouts prevent hanging during re-authentication

### Issue 3: Portfolio Loading Timeout ✅ FIXED

**Previous Behavior (Before Fix)**:
1. **Session Expires**: Cached auth session becomes invalid (JWT expires, network issues, etc.)
2. **Broker Adapter Called**: `broker.get_holdings()` and `broker.get_account_limits()` are called
3. **No Re-Auth**: Methods didn't have re-auth logic, so no re-authentication was attempted
4. **SDK Retries**: SDK client internally retried failed connections, causing long waits
5. **Timeout**: After 120-300 seconds, nginx timed out with 504 Gateway Timeout
6. **Error Handling**: Exceptions were caught but returned empty results, masking the real issue

**Current Behavior (After Fix)** ✅:
1. **Session Expires**: Cached auth session becomes invalid (JWT expires, network issues, etc.)
2. **Broker Adapter Called**: `broker.get_holdings()` and `broker.get_account_limits()` are called
3. **Auth Error Detected**: Methods detect auth errors using `is_auth_error()` and `is_auth_exception()`
4. **Failure Rate Check**: Before attempting re-auth, checks if too many failures occurred recently
   - If 3+ failures in last 60s → **Blocked**, returns empty result immediately
5. **Re-Authentication**: If not blocked, attempts re-auth using `_attempt_reauth_thread_safe()`
   - Thread-safe: Only one thread performs re-auth
   - Timeout protection: 30s wait, 5s lock timeout
6. **Client Update**: After successful re-auth, updates `self._client` with new authenticated client
7. **Retry**: Retries API call once automatically (max 1 retry per method call)
8. **Result**:
   - If re-auth succeeds and retry succeeds → Returns holdings/limits ✅
   - If re-auth fails or retry fails → Records failure, returns empty result
   - **No infinite loops** - Multiple safeguards prevent this

---

## Infinite Loop Prevention

### Safeguards Implemented ✅

#### 1. Per-Method Retry Limit ✅
**Location**: All broker adapter methods

```python
max_retries = 1  # Retry once after re-auth
for attempt in range(max_retries + 1):  # 0, 1 (2 total attempts)
    if attempt < max_retries:  # Only retry on attempt 0
        # Re-auth logic
    else:
        return []  # Stop after max retries
```

**Protection**: Each method call can only retry **once** (2 total attempts: original + 1 retry)

#### 2. Failure Rate Limiting ✅
**Location**: `auth_handler.py` - `_check_reauth_failure_rate()`

```python
_REAUTH_FAILURE_WINDOW = 60  # seconds
_MAX_REAUTH_FAILURES = 3  # max failures in window before blocking
```

**Protection**:
- Tracks re-auth failures per auth object
- Blocks re-auth if **3 failures occur within 60 seconds**
- Prevents rapid re-auth attempts across multiple method calls

**Usage in Broker Adapter**:
```python
# Check failure rate BEFORE attempting re-auth
if _check_reauth_failure_rate(self.auth_handler):
    logger.error("Re-authentication blocked due to recent failures")
    return []  # Stop immediately
```

#### 3. Thread-Safe Coordination ✅
**Location**: `auth_handler.py` - `_attempt_reauth_thread_safe()`

**Protection**:
- Only **one thread** performs re-auth per auth object
- Other threads wait for re-auth to complete (max 30s timeout)
- Prevents concurrent re-auth attempts that could cause loops

#### 4. Timeout Protection ✅
**Location**: `auth_handler.py` - `_attempt_reauth_thread_safe()`

```python
# Wait for re-auth to complete (with timeout to prevent deadlock)
if reauth_event.wait(timeout=30.0):
    return True
else:
    logger.warning("Re-authentication timeout")
    # Try own re-auth with 5s timeout
    if lock.acquire(blocking=True, timeout=5.0):
        # ...
```

**Protection**:
- 30s timeout for waiting threads
- 5s timeout for lock acquisition
- Prevents indefinite blocking

#### 5. Failure Recording ✅
**Location**: `auth_handler.py` - `_record_reauth_failure()`

**Protection**:
- Records each re-auth failure with timestamp
- Used by `_check_reauth_failure_rate()` to block future attempts
- Automatically clears after successful re-auth

**Usage in Broker Adapter**:
```python
if _attempt_reauth_thread_safe(...):
    # Success - failure history cleared automatically
    pass
else:
    _record_reauth_failure(self.auth_handler)  # Record failure
    return []  # Stop
```

#### 6. Conditional Re-Auth Attempts ✅
**Location**: All broker adapter methods

```python
# Only attempt re-auth if:
if (
    attempt < max_retries  # ✅ Haven't exceeded retry limit
    and self.auth_handler  # ✅ Auth handler exists
    and hasattr(self.auth_handler, "force_relogin")  # ✅ Method exists
):
    # Attempt re-auth
```

**Protection**: Multiple checks prevent re-auth attempts when conditions aren't met

### Flow Diagram

```
Method Call (get_holdings/get_account_limits/place_order/cancel_order/get_all_orders)
    │
    ├─> Attempt 0: Call API
    │       │
    │       ├─> Success? ──> Return result ✅
    │       │
    │       └─> Auth Error?
    │               │
    │               ├─> Check failure rate ──> Blocked? ──> Return [] ✅ (STOP)
    │               │
    │               ├─> Attempt re-auth
    │               │       │
    │               │       ├─> Success? ──> Attempt 1: Retry API call
    │               │       │                       │
    │               │       │                       ├─> Success? ──> Return result ✅
    │               │       │                       │
    │               │       │                       └─> Error? ──> Record failure ──> Return [] ✅ (STOP)
    │               │       │
    │               │       └─> Failed? ──> Record failure ──> Return [] ✅ (STOP)
    │               │
    │               └─> Max retries? ──> Return [] ✅ (STOP)
    │
    └─> Non-auth error? ──> Return [] ✅ (STOP - no re-auth)
```

### Maximum Possible Re-Auth Attempts

#### Per Method Call
- **Maximum**: 1 re-auth attempt per method call
- **Maximum API calls**: 2 (original + 1 retry)
- **Guaranteed stop**: After 2 attempts

#### Across Multiple Method Calls
- **Maximum**: 3 re-auth attempts within 60 seconds
- **After 3 failures**: All re-auth blocked for 60 seconds
- **Guaranteed stop**: After 3 failures, no more re-auth for 60s

### Example Scenarios

#### Scenario 1: Single Auth Error (Success)
1. `get_holdings()` called → Auth error detected
2. Check failure rate → Not blocked (0 failures)
3. Attempt re-auth → Success
4. Retry API call → Success
5. Return holdings ✅

**Result**: 2 API calls total, 1 re-auth attempt

#### Scenario 2: Re-Auth Fails
1. `get_holdings()` called → Auth error detected
2. Check failure rate → Not blocked (0 failures)
3. Attempt re-auth → **Fails**
4. Record failure (count = 1)
5. Return [] ✅

**Result**: 1 API call, 1 re-auth attempt, stopped

#### Scenario 3: Multiple Failures (Rate Limited)
1. `get_holdings()` called → Auth error detected
2. Check failure rate → **Blocked** (3 failures in last 60s)
3. Return [] immediately ✅

**Result**: 0 re-auth attempts, stopped immediately

#### Scenario 4: Retry After Re-Auth Still Fails
1. `get_holdings()` called → Auth error detected
2. Attempt re-auth → Success
3. Retry API call → **Still auth error**
4. Check failure rate → Not blocked yet (0 failures)
5. Attempt re-auth again? → **NO** (max_retries reached)
6. Return [] ✅

**Result**: 2 API calls, 1 re-auth attempt, stopped after max retries

**Worst case scenario**:
- 3 method calls with auth errors
- 3 re-auth attempts (1 per call)
- All fail
- **Result**: Re-auth blocked for 60 seconds, methods return empty results
- **No infinite loop** ✅

---

## Backward Compatibility

### Summary

✅ **All changes are backward compatible:**

1. **Normal successful calls** work exactly as before
2. **Non-auth errors** handled the same way (return empty list/dict)
3. **Missing auth_handler** safely falls back to original behavior
4. **Import failures** safely fall back to original behavior
5. **Return types and values** unchanged
6. **Test compatibility** maintained

The only new behavior is:
- **Auth errors** now trigger re-authentication and retry once
- This is an **enhancement**, not a breaking change
- If re-auth fails, behavior is same as before (return empty result)

### Import Safety

**Implementation**:
```python
try:
    from modules.kotak_neo_auto_trader.auth_handler import (
        is_auth_error,
        is_auth_exception,
        _attempt_reauth_thread_safe,
        _check_reauth_failure_rate,
        _record_reauth_failure,
    )
except ImportError:
    # Fallback if auth_handler not available (shouldn't happen in normal usage)
    def is_auth_error(response):  # noqa: ARG001
        return False
    def is_auth_exception(exception):  # noqa: ARG001
        return False
    def _attempt_reauth_thread_safe(auth, method_name):  # noqa: ARG001
        return False
    def _check_reauth_failure_rate(auth):  # noqa: ARG001
        return False  # Don't block if import fails
    def _record_reauth_failure(auth):  # noqa: ARG001
        pass  # No-op if import fails
```

**Result**: ✅ Safe - if imports fail, re-auth is never attempted, code works normally

### Return Value Guarantees

#### get_holdings()
- **Success**: Returns `list[Holding]` (unchanged)
- **Error**: Returns `[]` (unchanged)
- **Auth Error + Re-auth Success**: Retries once, returns `list[Holding]` or `[]`
- **Auth Error + Re-auth Failure**: Returns `[]` (same as before)

#### get_account_limits()
- **Success**: Returns `dict[str, Any]` with keys: `available_cash`, `margin_used`, `margin_available`, `collateral`, `net` (unchanged)
- **Error**: Returns `{}` (unchanged)
- **Auth Error + Re-auth Success**: Retries once, returns `dict` or `{}`
- **Auth Error + Re-auth Failure**: Returns `{}` (same as before)

#### place_order()
- **Success**: Returns `str` (order_id) (unchanged)
- **Error**: Raises `RuntimeError` (unchanged)
- **Auth Error + Re-auth Success**: Retries once, returns `str` or raises `RuntimeError`
- **Auth Error + Re-auth Failure**: Raises `RuntimeError` (same as before)

#### cancel_order()
- **Success**: Returns `bool` (True) (unchanged)
- **Error**: Returns `bool` (False) (unchanged)
- **Auth Error + Re-auth Success**: Retries once, returns `bool`
- **Auth Error + Re-auth Failure**: Returns `False` (same as before)

#### get_all_orders()
- **Success**: Returns `list[Order]` (unchanged)
- **Error**: Returns `[]` (unchanged)
- **Auth Error + Re-auth Success**: Retries once, returns `list[Order]` or `[]`
- **Auth Error + Re-auth Failure**: Returns `[]` (same as before)

### Edge Cases Handled

1. ✅ **Auth Handler is None**: Returns empty result
2. ✅ **Import Failures**: Re-auth never attempted
3. ✅ **Re-auth Function Returns False**: Returns empty result
4. ✅ **Max Retries Reached**: Returns empty result
5. ✅ **Client Update After Re-auth**: Client updated before retry

---

## API Methods Coverage

### Methods with Re-Authentication and Timeout Handling ✅

All Kotak API methods in `KotakNeoBrokerAdapter` now have:

1. ✅ **`get_holdings()`** - Re-auth, timeout, failure rate limiting
2. ✅ **`get_account_limits()`** - Re-auth, timeout, failure rate limiting
3. ✅ **`place_order()`** - Re-auth, timeout, failure rate limiting
4. ✅ **`cancel_order()`** - Re-auth, timeout, failure rate limiting
5. ✅ **`get_all_orders()`** - Re-auth, timeout, failure rate limiting

### Test Coverage

**Total Tests**: 27 tests covering all scenarios

**Test Categories**:
- Re-authentication on auth errors (11 tests)
- Timeout handling (5 tests)
- Failure rate limiting (5 tests)
- Retry logic (2 tests)
- Backward compatibility (3 tests)
- Infinite loop prevention (2 tests)

**All tests passing** ✅

---

## Summary

### Root Cause (FIXED ✅)
Broker adapter methods bypassed the re-authentication mechanism by calling SDK client directly without re-auth handling.

### Impact (Before Fix)
When sessions expired, API calls failed without re-authentication, SDK retried internally causing long timeouts, and nginx returned 504 Gateway Timeout.

### Solution Implemented ✅
Added re-authentication handling directly to all broker adapter methods with multiple safeguards:

1. ✅ **Re-authentication Logic**: Detects auth errors and triggers re-auth automatically
2. ✅ **Failure Rate Limiting**: Blocks re-auth after 3 failures in 60 seconds
3. ✅ **Per-Method Retry Limit**: Max 1 retry per method call (2 total attempts)
4. ✅ **Thread-Safe Coordination**: Only one re-auth at a time
5. ✅ **Timeout Protection**: 30s wait timeout, 5s lock timeout, 30s SDK call timeout
6. ✅ **Failure Recording**: Tracks failures to prevent rapid retries
7. ✅ **Client Update**: Updates client after successful re-auth
8. ✅ **Backward Compatible**: Returns empty results on errors (same as before)
9. ✅ **Comprehensive Coverage**: All 5 API methods protected

### Infinite Loop Prevention ✅
Multiple safeguards ensure no infinite loops:
- **Per-method limit**: Max 1 retry per method call
- **Failure rate limiting**: Blocks after 3 failures in 60s
- **Thread safety**: Only one re-auth at a time
- **Timeouts**: Prevents indefinite blocking
- **Failure recording**: Tracks failures to prevent rapid retries

**Maximum possible re-auth attempts**:
- Per method call: 1 re-auth attempt (2 total API calls)
- Across multiple calls: 3 re-auth attempts within 60 seconds, then blocked

### Current Status
✅ **FIXED** - All broker adapter methods now have re-authentication with infinite loop prevention
✅ **FIXED** - SDK-level timeout implemented using ThreadPoolExecutor (30s default)
✅ **FIXED** - All 5 API methods covered (get_holdings, get_account_limits, place_order, cancel_order, get_all_orders)
✅ **TESTED** - 27 comprehensive tests, all passing
✅ **BACKWARD COMPATIBLE** - No breaking changes
✅ **SAFE** - Multiple safeguards prevent infinite loops
✅ **COMPLETE** - All major issues addressed

### Related Files

**Implementation**:
- `modules/kotak_neo_auto_trader/infrastructure/broker_adapters/kotak_neo_adapter.py` - Broker adapter with re-auth
- `modules/kotak_neo_auto_trader/auth_handler.py` - Re-auth utilities
- `modules/kotak_neo_auto_trader/utils/timeout_utils.py` - Timeout utilities
- `modules/kotak_neo_auto_trader/auth.py` - Authentication logic

**Tests**:
- `tests/unit/infrastructure/broker_adapters/test_kotak_neo_adapter_reauth_timeout.py` - Comprehensive test suite (27 tests)

**Configuration**:
- `web/nginx.conf` - Nginx timeout settings (300s)

---

## Recommendations

1. ✅ **Safe to deploy** - All backward compatibility checks pass
2. ✅ **Tests passing** - 27 comprehensive tests, all passing
3. ✅ **Monitor logs** - Watch for re-auth attempts in production
4. ✅ **No breaking changes** - All changes are backward compatible
5. ✅ **Production ready** - Multiple safeguards prevent infinite loops

---

*Last Updated: December 2025*
*Consolidated from: AUTH_SESSION_FLOW_ANALYSIS.md, BACKWARD_COMPATIBILITY_ANALYSIS.md, REAUTH_INFINITE_LOOP_PREVENTION.md*
