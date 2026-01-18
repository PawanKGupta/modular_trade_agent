# Table-Based Locking for Scheduler

## Problem with PostgreSQL Advisory Locks

PostgreSQL advisory locks are **connection-specific** - they can only be released by the same connection that acquired them. This creates a fundamental problem with connection pooling:

1. Thread acquires lock on connection A
2. Thread exits, connection A is returned to pool
3. Lock remains held by connection A in the pool
4. New thread tries to acquire lock but can't (connection A still holds it)
5. Must wait for connection pool to recycle (1 hour) or restart database

## Solution: Table-Based Locking

Instead of PostgreSQL advisory locks, we use a simple database table (`scheduler_lock`) that:

1. **Works with any connection** - any connection can acquire/release
2. **Auto-expires stale locks** - locks expire after 5 minutes
3. **Simple cleanup** - just delete expired rows
4. **Works with connection pooling** - no connection-specific issues
5. **Easier to debug** - can query the table to see locks

## Implementation

### Database Model

```python
class SchedulerLock(Base):
    user_id: int (primary key)
    locked_at: datetime
    lock_id: str (UUID, unique per instance)
    expires_at: datetime (auto-expires after 5 minutes)
```

### Lock Acquisition

```python
# Try to INSERT - if user_id already exists, lock is held
INSERT INTO scheduler_lock (user_id, lock_id, expires_at, ...)
VALUES (...)
ON CONFLICT (user_id) DO NOTHING
RETURNING lock_id
```

### Lock Release

```python
# Delete by lock_id (only release our own lock)
DELETE FROM scheduler_lock WHERE lock_id = ?
```

### Stale Lock Cleanup

```python
# Delete expired locks
DELETE FROM scheduler_lock WHERE expires_at < NOW()
```

## Benefits

1. ✅ **No connection pool issues** - works with any connection
2. ✅ **Auto-cleanup** - expired locks are automatically removed
3. ✅ **Simple** - just INSERT/DELETE operations
4. ✅ **Debuggable** - can query table to see active locks
5. ✅ **Works across processes** - database-level locking

## Migration

The old advisory lock code has been replaced with table-based locking. No migration needed - the table is created automatically via SQLAlchemy models.

