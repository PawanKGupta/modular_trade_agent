# Individual Service Management Implementation Plan

**Last Updated**: November 18, 2025
**Status**: ✅ Completed
**Phase**: 3.6 - Service Status Enhancement

---

## Overview

This document outlines the implementation plan for enhancing the Service Status page with individual service management capabilities. This feature allows users to run individual trading tasks independently, provides admin controls for schedule management, and implements conflict detection to prevent duplicate executions.

---

## Requirements Summary

### Core Features

1. **Unified Service Control**
   - When unified service is running → "Start Service" button disabled
   - When unified service is NOT running → all individual task options enabled

2. **Individual Service Management**
   - Users can start any individual service (only when unified is not running)
   - Users can "run once" any service at any time (even when unified is running)
   - Individual services run continuously on their own schedule until stopped
   - Individual services run in separate processes for isolation

3. **Admin Privileges**
   - Admin can change schedule time for each service
   - Changes apply to all users
   - Schedule changes require unified service restart to take effect
   - Analysis service is admin-only (only admin can see and run)

4. **Analysis Service (Shared)**
   - Common service shared by all users
   - Updates Signals table (shared, no user_id)
   - Deduplication: if analysis runs multiple times during same trading day (9AM - next day 9AM), UPDATE existing signals rather than creating new entries
   - Weekend/holiday handling: allow admin to run analysis on weekends but skip the update

5. **Conflict Detection**
   - Cannot start individual service if unified service is running
   - "Run once" is allowed even when unified is running
   - If unified is running and "run once" is triggered at the same time:
     - Show warning
     - Prevent duplicate execution (check if task is currently executing or started within last 2 minutes)

6. **Service Status Tracking**
   - Unified service: track running/stopped per user
   - Individual services: track which ones are running per user
   - Last execution time per individual service
   - Next scheduled execution time
   - Execution history per individual service

---

## Database Schema

### New Tables

#### 1. `service_schedules`
Service schedule configuration (admin-editable, applies to all users)

**Columns:**
- `id` (INTEGER, PRIMARY KEY)
- `task_name` (VARCHAR(64), UNIQUE, INDEXED) - premarket_retry, sell_monitor, position_monitor, analysis, buy_orders, eod_cleanup
- `schedule_time` (TIME, NOT NULL) - HH:MM in IST
- `enabled` (BOOLEAN, DEFAULT: true)
- `is_hourly` (BOOLEAN, DEFAULT: false) - For position_monitor (runs hourly at :30)
- `is_continuous` (BOOLEAN, DEFAULT: false) - For sell_monitor (runs continuously)
- `end_time` (TIME, NULLABLE) - For continuous tasks
- `description` (VARCHAR(512), NULLABLE)
- `updated_by` (INTEGER, FOREIGN KEY → users.id, NULLABLE) - Admin who last updated
- `created_at` (DATETIME)
- `updated_at` (DATETIME)

**Constraints:**
- UNIQUE constraint on `task_name` (one schedule per task)

**Default Schedules:**
- `premarket_retry`: 09:00, enabled=true, is_hourly=false, is_continuous=false
- `sell_monitor`: 09:15, enabled=true, is_hourly=false, is_continuous=true, end_time=15:30
- `position_monitor`: 09:30, enabled=true, is_hourly=true, is_continuous=false
- `analysis`: 16:00, enabled=true, is_hourly=false, is_continuous=false (admin-only)
- `buy_orders`: 16:05, enabled=true, is_hourly=false, is_continuous=false
- `eod_cleanup`: 18:00, enabled=true, is_hourly=false, is_continuous=false

#### 2. `individual_service_status`
Individual service status tracking per user

**Columns:**
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY → users.id, INDEXED)
- `task_name` (VARCHAR(64), INDEXED) - premarket_retry, sell_monitor, position_monitor, buy_orders, eod_cleanup
- `is_running` (BOOLEAN, DEFAULT: false)
- `started_at` (DATETIME, NULLABLE)
- `last_execution_at` (DATETIME, NULLABLE)
- `next_execution_at` (DATETIME, NULLABLE)
- `process_id` (INTEGER, NULLABLE) - OS process ID
- `created_at` (DATETIME)
- `updated_at` (DATETIME)

**Constraints:**
- UNIQUE constraint on (`user_id`, `task_name`)
- INDEX on (`user_id`, `task_name`)

#### 3. `individual_service_task_execution`
Individual service task execution history per user

**Columns:**
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (INTEGER, FOREIGN KEY → users.id, INDEXED)
- `task_name` (VARCHAR(64), INDEXED)
- `executed_at` (DATETIME, INDEXED)
- `status` (VARCHAR(16), INDEXED) - 'success', 'failed', 'skipped', 'running'
- `duration_seconds` (FLOAT)
- `details` (JSON, NULLABLE)
- `execution_type` (VARCHAR(16), DEFAULT: 'scheduled') - 'scheduled', 'run_once', 'manual'

**Indexes:**
- Composite index on (`user_id`, `task_name`, `executed_at`)

---

## Implementation Phases

### Phase 1: Database Schema ✅

**Status**: In Progress

**Tasks:**
- [x] Create `ServiceSchedule` model
- [x] Create `IndividualServiceStatus` model
- [x] Create `IndividualServiceTaskExecution` model
- [ ] Create Alembic migration
- [ ] Add default schedule data in migration
- [ ] Test migration up/down

**Files:**
- `src/infrastructure/db/models.py` ✅
- `alembic/versions/XXXX_add_individual_service_management.py` (to be created)

---

### Phase 2: Backend - Repositories

**Status**: Pending

**Tasks:**
- [ ] Create `ServiceScheduleRepository`
  - Methods: `get_all()`, `get_by_task_name()`, `update()`, `create_defaults()`
- [ ] Create `IndividualServiceStatusRepository`
  - Methods: `get_by_user_and_task()`, `create_or_update()`, `list_by_user()`, `mark_running()`, `mark_stopped()`
- [ ] Create `IndividualServiceTaskExecutionRepository`
  - Methods: `create()`, `get_latest()`, `list_by_user_and_task()`, `get_running_tasks()`

**Files:**
- `src/infrastructure/persistence/service_schedule_repository.py` (new)
- `src/infrastructure/persistence/individual_service_status_repository.py` (new)
- `src/infrastructure/persistence/individual_service_task_execution_repository.py` (new)

---

### Phase 3: Backend - Services

**Status**: Pending

**Tasks:**
- [ ] Create `IndividualServiceManager`
  - Methods: `start_service()`, `stop_service()`, `run_once()`, `get_status()`
  - Process management (spawn/kill processes)
  - Conflict detection logic
- [ ] Create `ScheduleManager`
  - Methods: `get_schedules()`, `update_schedule()`, `validate_schedule()`
  - Schedule calculation (next execution time)
- [ ] Enhance `AnalysisService` (or create new)
  - Deduplication logic for trading day window
  - Weekend/holiday handling
- [ ] Create `ConflictDetectionService`
  - Methods: `check_conflict()`, `is_task_running()`, `is_task_recently_started()`

**Files:**
- `src/application/services/individual_service_manager.py` (new)
- `src/application/services/schedule_manager.py` (new)
- `src/application/services/analysis_deduplication_service.py` (new)
- `src/application/services/conflict_detection_service.py` (new)

---

### Phase 4: Backend - API Endpoints

**Status**: Pending

**Tasks:**
- [ ] Create `/api/v1/service/schedules` (GET, PUT) - Admin only
  - GET: List all schedules
  - PUT: Update schedule (requires unified service restart)
- [ ] Create `/api/v1/service/individual/start` (POST)
  - Start individual service (check unified service not running)
- [ ] Create `/api/v1/service/individual/stop` (POST)
  - Stop individual service
- [ ] Create `/api/v1/service/individual/run-once` (POST)
  - Run task once (with conflict detection)
- [ ] Create `/api/v1/service/individual/status` (GET)
  - Get individual service statuses for user
- [ ] Enhance `/api/v1/service/status` (GET)
  - Include individual service statuses
- [ ] Create `/api/v1/service/analysis/run` (POST) - Admin only
  - Run analysis service with deduplication

**Files:**
- `server/app/routers/service.py` (enhance)
- `server/app/schemas/service.py` (enhance)
- `server/app/routers/admin.py` (add schedule management)

---

### Phase 5: Backend - Individual Service Execution

**Status**: Pending

**Tasks:**
- [ ] Create individual service runner scripts
  - `scripts/run_individual_service.py` - Main entry point
  - Support for each task type (premarket_retry, sell_monitor, etc.)
- [ ] Implement process spawning
  - Use `subprocess.Popen` or `multiprocessing.Process`
  - Track process IDs
  - Handle process cleanup on stop
- [ ] Implement schedule-based execution
  - Read schedule from database
  - Calculate next execution time
  - Execute at scheduled time
  - Handle hourly/continuous tasks
- [ ] Implement "run once" execution
  - Execute immediately in separate thread/process
  - 5-minute timeout
  - Use same user context (credentials, config)

**Files:**
- `scripts/run_individual_service.py` (new)
- `src/application/services/individual_service_executor.py` (new)

---

### Phase 6: Analysis Service Deduplication

**Status**: Pending

**Tasks:**
- [ ] Create trading day window calculation
  - Function: `get_current_trading_day_window()`
  - Logic:
    - If current time >= 9AM today → trading day = today
    - If current time < 9AM today → trading day = previous trading day (skip weekends)
    - If today is weekend → trading day = last Friday
- [ ] Implement signal deduplication
  - Find all signals in trading day window
  - Match by symbol
  - Update existing signals
  - Insert new signals
- [ ] Integrate with `trade_agent.py --backtest`
  - Modify analysis execution to use deduplication
  - Handle weekend runs (skip update)

**Files:**
- `src/application/services/analysis_deduplication_service.py` (new)
- `modules/kotak_neo_auto_trader/run_trading_service.py` (modify `run_analysis()`)

---

### Phase 7: Frontend - API Client

**Status**: Pending

**Tasks:**
- [ ] Add API client methods for schedules
  - `getSchedules()`, `updateSchedule()`
- [ ] Add API client methods for individual services
  - `startIndividualService()`, `stopIndividualService()`, `runOnce()`, `getIndividualServiceStatus()`
- [ ] Add API client method for analysis
  - `runAnalysis()` (admin only)

**Files:**
- `web/src/api/service.ts` (enhance)

---

### Phase 8: Frontend - UI Components

**Status**: Pending

**Tasks:**
- [ ] Enhance `ServiceStatusPage`
  - Add individual services section
  - Show unified service status (disable start if running)
  - Show individual service statuses with controls
  - Show next execution times
  - Show execution history
- [ ] Create `IndividualServiceCard` component
  - Task name, status, last execution, next execution
  - Start/Stop/Run Once buttons
  - Disable logic based on unified service status
- [ ] Create `AdminScheduleManagement` component
  - List of schedules with edit capability
  - Time picker for schedule time
  - Enable/disable toggles
  - Validation rules
  - Test schedule button
  - Preview next execution times
  - Bulk enable/disable
  - Show last updated by admin
- [ ] Add conflict warnings
  - Show warning when unified is running and user tries to start individual
  - Show warning when "run once" conflicts with running task
  - Show banner when schedule changes

**Files:**
- `web/src/routes/dashboard/ServiceStatusPage.tsx` (enhance)
- `web/src/routes/dashboard/IndividualServiceCard.tsx` (new)
- `web/src/routes/dashboard/AdminScheduleManagement.tsx` (new)
- `web/src/components/ConflictWarning.tsx` (new)

---

### Phase 9: Testing

**Status**: Pending

**Tasks:**
- [ ] Unit tests for repositories
- [ ] Unit tests for services
- [ ] Unit tests for API endpoints
- [ ] Integration tests for individual service execution
- [ ] Integration tests for conflict detection
- [ ] Integration tests for analysis deduplication
- [ ] E2E tests for UI workflows

**Files:**
- `tests/unit/infrastructure/test_service_schedule_repository.py` (new)
- `tests/unit/infrastructure/test_individual_service_status_repository.py` (new)
- `tests/unit/application/test_individual_service_manager.py` (new)
- `tests/unit/application/test_conflict_detection_service.py` (new)
- `tests/unit/application/test_analysis_deduplication_service.py` (new)
- `tests/unit/server/test_individual_service_api.py` (new)
- `web/src/routes/__tests__/IndividualServiceCard.test.tsx` (new)
- `web/src/routes/__tests__/AdminScheduleManagement.test.tsx` (new)

---

### Phase 10: Documentation

**Status**: Pending

**Tasks:**
- [ ] Update API documentation
- [ ] Create user guide for individual services
- [ ] Create admin guide for schedule management
- [ ] Update architecture documentation
- [ ] Add inline code documentation

**Files:**
- `documents/features/INDIVIDUAL_SERVICE_MANAGEMENT.md` (new)
- `documents/admin/SCHEDULE_MANAGEMENT.md` (new)
- `documents/api/SERVICE_API.md` (update)

---

## Technical Details

### Conflict Detection Logic

```python
def check_conflict(user_id: int, task_name: str) -> tuple[bool, str]:
    """
    Check if running the task would conflict with unified service.

    Returns:
        (has_conflict: bool, message: str)
    """
    # Check if unified service is running
    unified_running = is_unified_service_running(user_id)

    # Check if task is currently executing in unified service
    if unified_running:
        # Check ServiceTaskExecution for running task
        running_task = get_running_task(user_id, task_name)
        if running_task:
            return True, f"Task '{task_name}' is currently running in unified service"

        # Check if task started within last 2 minutes
        recent_task = get_recent_task(user_id, task_name, minutes=2)
        if recent_task:
            return True, f"Task '{task_name}' was started recently in unified service"

    return False, ""
```

### Analysis Deduplication Logic

```python
def get_current_trading_day_window() -> tuple[datetime, datetime]:
    """
    Get the current trading day window (9AM to next day 9AM, excluding weekends).

    Returns:
        (window_start: datetime, window_end: datetime)
    """
    now = ist_now()
    current_time = now.time()

    # If before 9AM, use previous trading day
    if current_time < time(9, 0):
        # Go back to previous trading day (skip weekends)
        trading_day = now.date() - timedelta(days=1)
        while trading_day.weekday() >= 5:  # Saturday = 5, Sunday = 6
            trading_day -= timedelta(days=1)
        window_start = datetime.combine(trading_day, time(9, 0))
        window_end = datetime.combine(now.date(), time(9, 0))
    else:
        # Current trading day
        window_start = datetime.combine(now.date(), time(9, 0))
        window_end = datetime.combine(now.date() + timedelta(days=1), time(9, 0))

    return window_start, window_end

def deduplicate_signals(new_signals: list[dict]) -> None:
    """
    Update existing signals or insert new ones based on trading day window.
    """
    window_start, window_end = get_current_trading_day_window()

    # Get existing signals in window
    existing_signals = db.query(Signals).filter(
        Signals.ts >= window_start,
        Signals.ts < window_end
    ).all()

    existing_symbols = {s.symbol for s in existing_signals}

    for signal_data in new_signals:
        symbol = signal_data['symbol']
        if symbol in existing_symbols:
            # Update existing signal
            existing = next(s for s in existing_signals if s.symbol == symbol)
            update_signal_from_data(existing, signal_data)
        else:
            # Insert new signal
            create_signal_from_data(signal_data)
```

### Schedule Validation Rules

```python
def validate_schedule(task_name: str, schedule_time: time, is_hourly: bool, is_continuous: bool, end_time: time | None) -> tuple[bool, str]:
    """
    Validate schedule configuration.

    Returns:
        (is_valid: bool, error_message: str)
    """
    # Time format validation
    if not (0 <= schedule_time.hour < 24 and 0 <= schedule_time.minute < 60):
        return False, "Invalid time format"

    # Position monitor: must be at :30 minutes if hourly
    if task_name == "position_monitor" and is_hourly:
        if schedule_time.minute != 30:
            return False, "Position monitor must be scheduled at :30 minutes when hourly"

    # Sell monitor: start time must be before end time if continuous
    if task_name == "sell_monitor" and is_continuous:
        if end_time and schedule_time >= end_time:
            return False, "Start time must be before end time for continuous tasks"

    # Business hours validation (9:00 - 18:00) for non-continuous tasks
    if not is_continuous and not is_hourly:
        if schedule_time < time(9, 0) or schedule_time > time(18, 0):
            return False, "Schedule time must be between 9:00 AM and 6:00 PM"

    return True, ""
```

### Process Management

```python
def start_individual_service(user_id: int, task_name: str) -> int:
    """
    Start individual service in separate process.

    Returns:
        process_id: int
    """
    # Check unified service not running
    if is_unified_service_running(user_id):
        raise ValueError("Cannot start individual service when unified service is running")

    # Spawn process
    process = subprocess.Popen(
        [sys.executable, "scripts/run_individual_service.py",
         "--user-id", str(user_id),
         "--task", task_name],
        cwd=project_root
    )

    # Update status
    update_service_status(user_id, task_name, is_running=True, process_id=process.pid)

    return process.pid

def stop_individual_service(user_id: int, task_name: str) -> None:
    """
    Stop individual service process.
    """
    status = get_service_status(user_id, task_name)
    if not status or not status.is_running:
        return

    if status.process_id:
        try:
            # Send termination signal
            os.kill(status.process_id, signal.SIGTERM)
            # Wait up to 30 seconds
            time.sleep(30)
            # Force kill if still running
            try:
                os.kill(status.process_id, signal.SIGKILL)
            except ProcessLookupError:
                pass  # Already terminated
        except ProcessLookupError:
            pass  # Process already dead

    # Update status
    update_service_status(user_id, task_name, is_running=False, process_id=None)
```

---

## Edge Cases and Error Handling

### 1. Process Crash
- **Scenario**: Individual service process crashes
- **Handling**: Mark as stopped, log error, no auto-restart

### 2. Server Restart
- **Scenario**: Server restarts while individual services are running
- **Handling**: Mark all individual services as stopped on startup

### 3. Schedule Change During Execution
- **Scenario**: Admin changes schedule while unified service is running
- **Handling**: Show banner notification, require unified service restart

### 4. Multiple "Run Once" Clicks
- **Scenario**: User clicks "run once" multiple times quickly
- **Handling**: Prevent duplicate execution (check if same task is already running)

### 5. Analysis Service Weekend Run
- **Scenario**: Admin runs analysis on weekend
- **Handling**: Allow execution but skip signal update (log warning)

### 6. Timeout on "Run Once"
- **Scenario**: "Run once" execution takes longer than 5 minutes
- **Handling**: Timeout after 5 minutes, log timeout error, mark as failed

---

## Testing Strategy

### Unit Tests
- Repository methods
- Service methods
- Validation logic
- Conflict detection
- Deduplication logic

### Integration Tests
- Individual service execution
- Process management
- Schedule-based execution
- Conflict detection scenarios
- Analysis deduplication

### E2E Tests
- Start/stop individual service
- Run once execution
- Schedule management (admin)
- Conflict warnings
- Analysis execution (admin)

---

## Success Criteria

1. ✅ Users can start/stop individual services when unified service is not running
2. ✅ Users can "run once" any service at any time (with conflict detection)
3. ✅ Admin can manage schedules via UI
4. ✅ Schedule changes require unified service restart
5. ✅ Analysis service deduplicates signals correctly
6. ✅ Conflict detection prevents duplicate executions
7. ✅ All services track status and execution history
8. ✅ Process management handles crashes and restarts gracefully

---

## Timeline Estimate

- **Phase 1**: Database Schema - 1 day
- **Phase 2**: Repositories - 1 day
- **Phase 3**: Services - 2 days
- **Phase 4**: API Endpoints - 2 days
- **Phase 5**: Individual Service Execution - 3 days
- **Phase 6**: Analysis Deduplication - 2 days
- **Phase 7**: Frontend API Client - 1 day
- **Phase 8**: Frontend UI - 3 days
- **Phase 9**: Testing - 3 days
- **Phase 10**: Documentation - 1 day

**Total Estimate**: ~19 days

---

## Dependencies

- Existing service management infrastructure
- Database migration system (Alembic)
- Process management capabilities
- User authentication and authorization
- Admin role management

---

## Risks and Mitigations

### Risk 1: Process Management Complexity
- **Risk**: Managing multiple processes can be complex
- **Mitigation**: Use proven process management libraries, thorough testing

### Risk 2: Conflict Detection Edge Cases
- **Risk**: Race conditions in conflict detection
- **Mitigation**: Use database locks, thorough testing of edge cases

### Risk 3: Schedule Change Impact
- **Risk**: Users may not notice schedule changes
- **Mitigation**: Banner notifications, clear UI indicators

### Risk 4: Analysis Deduplication Accuracy
- **Risk**: Incorrect trading day window calculation
- **Mitigation**: Comprehensive testing, clear documentation of logic

---

## Future Enhancements

1. **Service Health Monitoring**
   - CPU/Memory usage per service
   - Automatic restart on failure
   - Alerting for service issues

2. **Advanced Scheduling**
   - Cron-like expressions
   - Multiple schedules per task
   - Timezone support

3. **Service Dependencies**
   - Define task dependencies
   - Automatic execution order

4. **Service Analytics**
   - Execution success rates
   - Performance metrics
   - Cost analysis

---

*This document will be updated as implementation progresses.*
