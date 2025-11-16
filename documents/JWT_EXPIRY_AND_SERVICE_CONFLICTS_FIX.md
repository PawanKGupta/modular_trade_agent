# JWT Expiry and Service Conflict Fixes - Complete Documentation

**Date**: November 6, 2025  
**Status**: ✅ Fixed and Tested  
**Version**: 2.2

---

## Table of Contents

1. [Issues Identified](#issues-identified)
2. [Root Causes](#root-causes)
3. [Fixes Implemented](#fixes-implemented)
4. [Testing](#testing)
5. [Deployment Guide](#deployment-guide)

---

## Issues Identified

### Issue 1: 13-Second JWT Expiry
**Symptoms:**
- Login successful at 09:15:06
- JWT expires at 09:15:19 (13 seconds later)
- Re-authentication fails with: `'NoneType' object has no attribute 'get'`
- Orders API calls fail with "Invalid JWT token"

**Production Logs:**
```
2025-11-06 09:15:06 — INFO — auth — Login completed successfully!
2025-11-06 09:15:19 — INFO — orders — No orders found (raw preview: {'code': '900901', 'message': 'Invalid Credentials'})
2025-11-06 09:15:19 — ERROR — auth — 2FA call failed: 'NoneType' object has no attribute 'get'
```

### Issue 2: Multiple Services Running Simultaneously
**Symptoms:**
- `run_sell_orders.py` and `run_trading_service.py` both running
- Each creates separate auth session
- Sessions conflict → JWT expires immediately
- Re-authentication fails

**Root Cause:**
- Old individual services (`run_sell_orders.py`, etc.) still installed
- Unified service (`run_trading_service.py`) also running
- Both create separate auth sessions → conflicts

### Issue 3: Concurrent Threading Issues
**Symptoms:**
- `SellOrderManager` uses `ThreadPoolExecutor` (10 threads)
- Multiple threads make API calls simultaneously
- All threads use same `auth.client`
- Potential race conditions if SDK client isn't thread-safe

---

## Root Causes

### 1. Stale Client Reuse in Re-Authentication
**Problem**: `force_relogin()` was reusing existing `self.client` if it wasn't `None`, even if it was stale/expired.

**Old Code (Buggy):**
```python
def force_relogin(self):
    if not self.client:
        self.client = self._initialize_client()  # Only creates new if None
    # BUG: Reuses stale client if it exists!
    self.client.session_2fa(...)  # Fails with SDK internal error
```

**Impact**: When JWT expired quickly, SDK's internal state became corrupted. Reusing the stale client caused SDK to access `None` values internally.

### 2. Multiple Services Creating Separate Sessions
**Problem**: Both old services and unified service running simultaneously.

**Impact**: Each service creates its own auth session. Sessions conflict → broker invalidates tokens → JWT expires immediately.

### 3. Non-Thread-Safe Client Access
**Problem**: Multiple threads accessing `self.auth.client` simultaneously without locks.

**Impact**: Race conditions when:
- Thread A: Making API call with client
- Thread B: Re-authentication replaces client
- Thread A: Still using old client → Error

---

## Fixes Implemented

### Fix 1: Always Create New Client During Re-Authentication

**File**: `modules/kotak_neo_auto_trader/auth.py`

**Changes:**
1. Always create new client instance (never reuse stale clients)
2. Logout old client first to clean up SDK state
3. Add retry logic for 2FA (handles SDK initialization timing)
4. Improved error handling for SDK internal errors

**Code:**
```python
def force_relogin(self) -> bool:
    """Force a fresh login + 2FA (used when JWT expires) - THREAD-SAFE."""
    with self._client_lock:  # Thread-safe
        # Always create new client (never reuse stale)
        old_client = self.client
        if old_client:
            try:
                old_client.logout()  # Clean up SDK state
            except Exception:
                pass  # Non-critical
        
        # Reset state
        self.client = None
        self.is_logged_in = False
        self.session_token = None
        
        # ALWAYS create new client
        self.client = self._initialize_client()
        
        # Perform login + 2FA with retry
        # ...
```

### Fix 2: Service Conflict Detection and Auto-Stop

**File**: `modules/kotak_neo_auto_trader/utils/service_conflict_detector.py`

**Changes:**
1. Detect if unified service is running (for old services)
2. Detect if old services are running (for unified service)
3. Automatically stop old services when unified service starts
4. Clear error messages with instructions

**Code:**
```python
def prevent_service_conflict(script_name: str, is_unified: bool = False, auto_stop: bool = True) -> bool:
    """Check for service conflicts and prevent execution."""
    if is_unified:
        old_services = check_old_services_running()
        if old_services:
            if auto_stop:
                # Automatically stop old services
                stop_old_services_automatically()
            else:
                # Show error and exit
                return False
    else:
        # Old service: Check if unified service is running
        if check_unified_service_running():
            return False  # Exit with error
    return True
```

**Integration:**
- `run_trading_service.py`: Checks for old services, auto-stops them
- `run_sell_orders.py`: Checks for unified service, exits if found

### Fix 3: Thread-Safe Client Access

**File**: `modules/kotak_neo_auto_trader/auth.py`

**Changes:**
1. Added `threading.Lock()` for client access
2. Made `get_client()` thread-safe
3. Made `force_relogin()` thread-safe

**Code:**
```python
class KotakNeoAuth:
    def __init__(self, ...):
        self._client_lock = threading.Lock()  # Thread lock
    
    def get_client(self):
        """Get client (thread-safe)."""
        with self._client_lock:
            if not self.is_logged_in:
                return None
            return self.client
    
    def force_relogin(self):
        """Re-authenticate (thread-safe)."""
        with self._client_lock:
            # Only one thread can re-auth at a time
            # ... re-authentication logic ...
```

**Protection:**
- Prevents concurrent re-authentication attempts
- Prevents race conditions when accessing client
- Coordinates with `@handle_reauth` decorator

---

## Testing

### Unit Tests

**File**: `tests/unit/kotak/test_jwt_expiry_and_service_conflicts.py`

**Tests:**
1. `test_force_relogin_always_creates_new_client` - Verifies new client creation
2. `test_force_relogin_thread_safe` - Verifies thread-safe re-auth
3. `test_service_conflict_detection` - Verifies conflict detection
4. `test_auto_stop_old_services` - Verifies auto-stop functionality
5. `test_get_client_thread_safe` - Verifies thread-safe client access
6. `test_concurrent_api_calls_safe` - Verifies concurrent calls are safe

### Integration Test

**File**: `modules/kotak_neo_auto_trader/run_trading_service_test.py`

**Purpose**: Test all fixes without waiting for scheduled times.

**Usage:**
```bash
python modules/kotak_neo_auto_trader/run_trading_service_test.py --env modules/kotak_neo_auto_trader/kotak_neo.env
```

**What it tests:**
- Service conflict detection
- Thread-safe client access
- JWT re-authentication
- Concurrent API calls
- All tasks execution

---

## Deployment Guide

### Step 1: Stop Old Services

**Linux:**
```bash
sudo systemctl stop tradeagent-sell.service
sudo systemctl stop tradeagent-autotrade.service
sudo systemctl stop tradeagent-monitor.service
sudo systemctl stop tradeagent-eod.service
```

**Windows:**
```powershell
sc stop ModularTradeAgent_Sell
sc stop ModularTradeAgent_Main
sc stop ModularTradeAgent_Monitor
sc stop ModularTradeAgent_EOD
```

### Step 2: Disable Old Services

**Linux:**
```bash
sudo systemctl disable tradeagent-sell.timer
sudo systemctl disable tradeagent-autotrade.timer
sudo systemctl disable tradeagent-monitor.timer
sudo systemctl disable tradeagent-eod.timer
```

**Windows:**
```powershell
sc config ModularTradeAgent_Sell start= disabled
sc config ModularTradeAgent_Main start= disabled
sc config ModularTradeAgent_Monitor start= disabled
sc config ModularTradeAgent_EOD start= disabled
```

**Or use migration script:**
```bash
python scripts/migrate_to_unified_service.py
```

### Step 3: Start Unified Service

**Linux:**
```bash
sudo systemctl start tradeagent-unified.service
sudo systemctl enable tradeagent-unified.service
```

**Windows:**
```powershell
sc start TradeAgentUnified
```

### Step 4: Verify

**Check service status:**
```bash
# Linux
sudo systemctl status tradeagent-unified.service

# Windows
sc query TradeAgentUnified
```

**Check logs:**
```bash
# Linux
journalctl -u tradeagent-unified.service -f

# Windows
# Check NSSM stdout/stderr files or service logs
```

**Verify no conflicts:**
```bash
python scripts/check_services_status.py
```

---

## Verification Checklist

After deployment, verify:

- [ ] Only unified service is running
- [ ] Old services are stopped and disabled
- [ ] Login successful (single login at startup)
- [ ] No JWT conflicts in logs
- [ ] Tasks execute at scheduled times
- [ ] Re-authentication works if JWT expires
- [ ] No `'NoneType' object has no attribute 'get'` errors
- [ ] Thread-safe operations (no race conditions)

---

## Files Modified

1. `modules/kotak_neo_auto_trader/auth.py`
   - Added thread-safe client access
   - Fixed `force_relogin()` to always create new client
   - Improved error handling

2. `modules/kotak_neo_auto_trader/utils/service_conflict_detector.py` (NEW)
   - Service conflict detection
   - Auto-stop old services
   - Clear error messages

3. `modules/kotak_neo_auto_trader/run_trading_service.py`
   - Added conflict detection at startup
   - Auto-stops old services

4. `modules/kotak_neo_auto_trader/run_sell_orders.py`
   - Added conflict detection
   - Exits if unified service is running

5. `modules/kotak_neo_auto_trader/auth_handler.py`
   - Improved error detection
   - Better exception handling

---

## Files Created

1. `modules/kotak_neo_auto_trader/utils/service_conflict_detector.py` - Conflict detection
2. `modules/kotak_neo_auto_trader/run_trading_service_test.py` - Test blueprint
3. `scripts/migrate_to_unified_service.py` - Migration helper
4. `scripts/check_services_status.py` - Status checker
5. `tests/unit/kotak/test_jwt_expiry_and_service_conflicts.py` - Unit tests

---

## Migration Scripts

### Check Services Status
```bash
python scripts/check_services_status.py
```

### Migrate to Unified Service
```bash
# Windows
python scripts/migrate_to_unified_service.py

# Linux
sudo python scripts/migrate_to_unified_service.py
```

---

## Summary

### Problems Fixed
1. ✅ JWT expires in 13 seconds → Fixed: Always create new client during re-auth
2. ✅ Multiple services conflict → Fixed: Auto-detect and stop conflicts
3. ✅ Thread safety issues → Fixed: Added locks for client access

### Key Improvements
- **Thread-safe**: Client access protected by locks
- **Auto-resolution**: Automatically stops conflicting services
- **Robust re-auth**: Always creates new client, handles SDK errors
- **Clear errors**: Helpful error messages with solutions

### Testing
- Unit tests for all fixes
- Integration test blueprint
- Production-ready

---

## Support

If issues persist:
1. Check service status: `python scripts/check_services_status.py`
2. Verify only unified service is running
3. Check logs for errors
4. Run test blueprint: `python modules/kotak_neo_auto_trader/run_trading_service_test.py`
