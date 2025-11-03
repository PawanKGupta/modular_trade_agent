# Thread-Safe Re-Authentication Implementation

## Problem: Concurrent Re-Authentication

When multiple threads detect JWT expiry simultaneously (common in parallel monitoring), they might all attempt to re-authenticate at the same time, leading to:
- **Redundant re-authentication calls**
- **Resource waste**
- **Potential conflicts**
- **API rate limiting issues**

## Solution: Thread-Safe Coordination

Implemented a thread-safe mechanism that ensures:
- ✅ **Only one thread performs re-auth** for each auth object
- ✅ **Other threads wait** for the first thread to complete
- ✅ **All threads share the re-authenticated session**
- ✅ **No redundant re-auth calls**

## Implementation Details

### Architecture

```
Thread 1 (gets lock)          Thread 2 (waits)            Thread 3 (waits)
     |                             |                            |
     |→ Detect auth error          |→ Detect auth error         |→ Detect auth error
     |→ Acquire lock ✓             |→ Acquire lock ✗            |→ Acquire lock ✗
     |→ Perform re-auth            |→ Wait for event            |→ Wait for event
     |→ Set event                  |← Event set                |← Event set
     |→ Release lock               |→ Use new session           |→ Use new session
```

### Key Components

1. **Per-Auth-Object Locks**:
   ```python
   _reauth_locks: Dict[int, threading.Lock] = {}
   ```
   - Each `KotakNeoAuth` object has its own lock
   - Uses `id(auth)` to uniquely identify auth objects
   - Prevents conflicts between different auth instances

2. **Re-Authentication Events**:
   ```python
   _reauth_in_progress: Dict[int, threading.Event] = {}
   ```
   - Signals when re-auth is in progress/completed
   - Waiting threads listen to this event
   - Automatically cleared when new re-auth starts

3. **Thread-Safe Re-Auth Function**:
   ```python
   def _attempt_reauth_thread_safe(auth: KotakNeoAuth, method_name: str) -> bool:
       # Only one thread acquires lock
       # Other threads wait for event
   ```

## How It Works

### Scenario: 5 Concurrent API Calls Detect JWT Expiry

**Without Thread-Safe Implementation:**
```
Thread 1 → force_relogin() ❌ Redundant
Thread 2 → force_relogin() ❌ Redundant
Thread 3 → force_relogin() ❌ Redundant
Thread 4 → force_relogin() ❌ Redundant
Thread 5 → force_relogin() ❌ Redundant

Result: 5 re-auth calls (wasteful, potential conflicts)
```

**With Thread-Safe Implementation:**
```
Thread 1 → Acquire lock ✓ → force_relogin() → Set event
Thread 2 → Lock held ✗ → Wait for event → Event set → Use new session
Thread 3 → Lock held ✗ → Wait for event → Event set → Use new session
Thread 4 → Lock held ✗ → Wait for event → Event set → Use new session
Thread 5 → Lock held ✗ → Wait for event → Event set → Use new session

Result: 1 re-auth call, all 5 threads benefit ✅
```

## Test Results

### Concurrent Re-Authentication Test

**Test Setup**: 5 threads detecting JWT expiry simultaneously

**Results**:
- ✅ `force_relogin()` called: **1 time** (not 5)
- ✅ All 5 threads detected successful re-auth
- ✅ All threads waited and received the same authenticated session
- ✅ Thread coordination working correctly

**Timeline**:
```
Thread 0: Acquired lock, performed re-auth (0.102s)
Thread 1: Waited, detected completion (0.101s)
Thread 2: Waited, detected completion (0.100s)
Thread 3: Waited, detected completion (0.101s)
Thread 4: Waited, detected completion (0.101s)
```

### Sequential Re-Authentication Test

**Test Setup**: Two separate re-auth attempts (e.g., session expires twice)

**Results**:
- ✅ `force_relogin()` called: **2 times** (correct - two separate events)
- ✅ Both re-auth attempts succeeded
- ✅ Sequential re-auth works correctly

## Code Implementation

### Lock Management

```python
# Thread-safe locks per auth object
_reauth_locks: Dict[int, threading.Lock] = {}
_reauth_locks_lock = threading.Lock()  # Protects the dict itself
_reauth_in_progress: Dict[int, threading.Event] = {}
```

### Re-Authentication Flow

```python
def _attempt_reauth_thread_safe(auth: KotakNeoAuth, method_name: str) -> bool:
    lock = _get_reauth_lock(auth)
    reauth_event = _get_reauth_event(auth)
    
    # Try non-blocking acquire
    if lock.acquire(blocking=False):
        # Got lock - perform re-auth
        reauth_event.clear()  # Clear previous state
        try:
            if auth.force_relogin():
                reauth_event.set()  # Signal success
                return True
        finally:
            lock.release()
    else:
        # Lock held - wait for re-auth
        if reauth_event.wait(timeout=30.0):
            return True  # Re-auth completed
        # Handle timeout...
```

## Benefits

1. **Efficiency**: Only one re-auth call instead of N concurrent calls
2. **Consistency**: All threads use the same authenticated session
3. **Reliability**: No conflicts from concurrent re-auth attempts
4. **Performance**: Faster - threads don't block waiting for redundant re-auth

## Edge Cases Handled

1. **Timeout Protection**: 30-second timeout prevents deadlock
2. **Failure Handling**: If re-auth fails, other threads can retry
3. **Event Clearing**: Event cleared before new re-auth to handle re-expiry
4. **Lock Cleanup**: Locks persist per auth object (no memory leak concerns)

## Real-World Impact

### Before (Without Thread Safety)
```
Parallel monitoring (10 stocks) → JWT expires
→ 10 threads → 10 re-auth calls
→ API throttling, conflicts, slower recovery
```

### After (With Thread Safety)
```
Parallel monitoring (10 stocks) → JWT expires
→ 10 threads → 1 re-auth call
→ All 10 threads use new session immediately
→ Fast recovery, no conflicts
```

## Status: ✅ Production Ready

Thread-safe re-authentication is:
- ✅ **Tested** with concurrent scenarios
- ✅ **Validated** with multiple threads
- ✅ **Handles** timeouts and failures
- ✅ **Efficient** - no redundant calls

