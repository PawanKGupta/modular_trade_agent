# Bug Fix: Transaction Commit for Status Updates

## Problem

Status updates using `update_running()`, `update_heartbeat()`, `update_task_execution()`, and `increment_error()` only call `flush()` but not `commit()`. When these are followed by operations that might rollback (like `notification_repo.create()`), the status updates can be lost if a rollback occurs.

## Root Cause

The `ServiceStatusRepository` methods use `flush()` instead of `commit()` to allow callers to manage transactions. However, if a subsequent operation (like notification creation) fails and rolls back, it rolls back ALL uncommitted changes, including the status updates.

### Example Bug Pattern:
```python
# Status update (only flushes, doesn't commit)
self._service_status_repo.update_running(user_id, running=True)

# Notification creation (can rollback on failure)
self._notification_repo.create(...)  # If this fails and rolls back, status update is lost!
```

## Fixes Applied

### 1. `start_service()` - Commit before notification
**File**: `src/application/services/multi_user_trading_service.py` (line 514-516)

**Before**:
```python
self._service_status_repo.update_running(user_id, running=True)
self._service_status_repo.update_heartbeat(user_id)
self._notify_service_started(user_id)  # Can rollback!
```

**After**:
```python
self._service_status_repo.update_running(user_id, running=True)
self._service_status_repo.update_heartbeat(user_id)
self.db.commit()  # Commit status BEFORE notification
self._notify_service_started(user_id)
```

### 2. `stop_service()` - Commit before notification
**File**: `src/application/services/multi_user_trading_service.py` (line 601-603)

**Before**:
```python
self._service_status_repo.update_running(user_id, running=False)
self._service_status_repo.update_heartbeat(user_id)
self._notify_service_stopped(user_id)  # Can rollback!
```

**After**:
```python
self._service_status_repo.update_running(user_id, running=False)
self._service_status_repo.update_heartbeat(user_id)
self.db.commit()  # Commit status BEFORE notification
self._notify_service_stopped(user_id)
```

### 3. Exception handler in `start_service()` - Commit error status
**File**: `src/application/services/multi_user_trading_service.py` (line 534-536)

**Before**:
```python
self._service_status_repo.update_running(user_id, running=False)
self._service_status_repo.increment_error(user_id, error_message=str(e))
raise  # Status might be lost if transaction is rolled back
```

**After**:
```python
self._service_status_repo.update_running(user_id, running=False)
self._service_status_repo.increment_error(user_id, error_message=str(e))
self.db.commit()  # Commit error status before raising
raise
```

### 4. Exception handler in `stop_service()` - Commit error status
**File**: `src/application/services/multi_user_trading_service.py` (line 626-627)

**Before**:
```python
self._service_status_repo.increment_error(user_id, error_message=str(e))
return False  # Status might be lost
```

**After**:
```python
self._service_status_repo.increment_error(user_id, error_message=str(e))
self.db.commit()  # Commit error status
return False
```

### 5. `task_execution_wrapper.py` - Commit status updates
**File**: `src/application/services/task_execution_wrapper.py`

**Success case** (line 71-72):
```python
status_repo.update_task_execution(user_id)
db_session.commit()  # Commit status update
```

**Error case** (line 95-97):
```python
status_repo.update_task_execution(user_id)
status_repo.increment_error(user_id, error_message=str(e))
db_session.commit()  # Commit status updates before raising
```

## Why This Matters

1. **Data Integrity**: Status updates must be persisted even if subsequent operations fail
2. **Test Reliability**: In test suites, transaction rollbacks from other tests can affect status
3. **Production Reliability**: Notification failures shouldn't cause status to be incorrect

## Testing

- ✅ `test_start_service_success` now passes consistently
- ✅ Status updates are persisted even when notifications fail
- ✅ Error status is persisted even when exceptions are raised

## Related Files

- `src/infrastructure/persistence/service_status_repository.py` - Repository methods use `flush()`
- `src/infrastructure/persistence/notification_repository.py` - Can rollback on failure
- `src/application/services/multi_user_trading_service.py` - Fixed status update commits
- `src/application/services/task_execution_wrapper.py` - Fixed status update commits

## Pattern to Watch For

Any code that:
1. Calls `update_running()`, `update_heartbeat()`, `update_task_execution()`, or `increment_error()`
2. Followed by operations that might rollback (notification creation, external API calls, etc.)
3. Should commit the status update BEFORE the risky operation
