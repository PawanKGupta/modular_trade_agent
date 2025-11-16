# Migration Plan: Unified Trading Service → Multi-User DB/UI System

**Last Updated**: January 2025
**Status**: Planning Phase
**Estimated Duration**: 6-8 weeks (phased approach)

---

## Executive Summary

This document outlines the migration plan from the current **single-user, file-based unified trading service** to the new **multi-user, database-backed, UI-enabled system**.

### Current State
- ✅ Single unified service running 24/7
- ✅ File-based storage (JSON/CSV)
- ✅ Single user (no authentication)
- ✅ Direct Kotak Neo integration
- ✅ 7 scheduled tasks (pre-market, sell orders, monitoring, analysis, buy orders, EOD)

### Target State
- ✅ Multi-user support with authentication
- ✅ Database-backed (PostgreSQL/SQLite)
- ✅ React UI for monitoring/control
- ✅ REST API for all operations
- ✅ User-scoped data isolation
- ✅ Encrypted broker credentials per user

---

## Migration Complexity Assessment

### Overall Complexity: **HIGH** (7/10)

| Component | Complexity | Risk | Effort |
|-----------|-----------|------|--------|
| **Data Migration** | Medium-High | Medium | 2 weeks |
| **Service Architecture** | High | High | 3 weeks |
| **Authentication Integration** | Medium | Low | 1 week |
| **Scheduled Tasks** | Medium | Medium | 1 week |
| **UI Integration** | Medium | Low | 1 week |
| **Testing & Validation** | High | High | 2 weeks |

**Total Estimated Effort**: 6-8 weeks (with parallel work)

---

## Phase 1: Foundation & Data Migration (Weeks 1-2)

### 1.1 Database Schema Extensions
**Complexity**: Low | **Effort**: 3 days

**Tasks**:
- [ ] Add `service_status` table for tracking service state per user
- [ ] Add `service_tasks` table for task execution history
- [ ] Add `service_logs` table for structured logging
- [ ] Extend `orders` table with broker-specific fields (order_id, broker_order_id)
- [ ] Add `holdings` table (if not exists) for portfolio tracking
- [ ] Create migration scripts (Alembic)

**Schema Additions**:
```python
class ServiceStatus(Base):
    user_id: int
    service_running: bool
    last_heartbeat: datetime
    last_task_execution: datetime
    error_count: int
    last_error: str | None

class ServiceTaskExecution(Base):
    user_id: int
    task_name: str  # 'premarket_retry', 'sell_monitor', etc.
    executed_at: datetime
    status: str  # 'success', 'failed', 'skipped'
    duration_seconds: float
    details: JSON  # task-specific data
```

**Deliverables**:
- Database migration files
- Updated models in `src/infrastructure/db/models.py`
- Repository classes for new tables

---

### 1.2 Data Migration Scripts
**Complexity**: Medium-High | **Effort**: 5 days

**Tasks**:
- [ ] Create migration script for `trades_history.json` → `orders` + `fills` tables
- [ ] Create migration script for `pending_orders.json` → `orders` table (AMO status)
- [ ] Create migration script for paper trading data → user-scoped orders
- [ ] Create migration script for portfolio/holdings → `positions` table
- [ ] Handle data deduplication and validation
- [ ] Create rollback scripts

**File Sources**:
```
data/
├── trades_history.json          → orders + fills
├── pending_orders.json          → orders (AMO status)
└── system_recommended_symbols.json → signals

paper_trading/
├── unified_service/
│   ├── orders.json              → orders (user-scoped)
│   ├── holdings.json            → positions
│   └── transactions.json        → fills
```

**Migration Strategy**:
1. **Dual-write period** (2 weeks): Write to both files and DB
2. **Validation period** (1 week): Compare file vs DB data
3. **Cutover**: Switch to DB-only writes
4. **Archive**: Move old files to `data/archive/`

**Deliverables**:
- `scripts/migrate_trades_history.py`
- `scripts/migrate_pending_orders.py`
- `scripts/migrate_paper_trading.py`
- Validation scripts
- Rollback scripts

---

### 1.3 Repository Layer Updates
**Complexity**: Medium | **Effort**: 3 days

**Tasks**:
- [ ] Update `OrdersRepository` to support broker-specific fields
- [ ] Create `ServiceStatusRepository` for service state management
- [ ] Create `ServiceTaskRepository` for task execution tracking
- [ ] Update `PositionsRepository` to match unified service holdings format
- [ ] Add bulk import methods for migration

**Deliverables**:
- Updated repository classes
- Unit tests for repositories

---

## Phase 2: Service Architecture Refactoring (Weeks 3-5)

### 2.1 Multi-User Service Wrapper
**Complexity**: High | **Effort**: 5 days

**Tasks**:
- [ ] Create `MultiUserTradingService` class that wraps existing `TradingService`
- [ ] Add user context to all service operations
- [ ] Implement user-scoped broker authentication
- [ ] Add service instance management (one per user)
- [ ] Implement service lifecycle management (start/stop per user)

**Architecture**:
```python
class MultiUserTradingService:
    """Manages trading services for multiple users"""

    def __init__(self, db: Session):
        self.db = db
        self._services: Dict[int, TradingService] = {}  # user_id -> service

    def start_service(self, user_id: int) -> bool:
        """Start trading service for a user"""
        # Load user settings (broker creds, trade mode)
        # Initialize TradingService with user context
        # Store service instance

    def stop_service(self, user_id: int) -> bool:
        """Stop trading service for a user"""

    def get_service_status(self, user_id: int) -> ServiceStatus:
        """Get current service status"""
```

**Deliverables**:
- `src/application/services/multi_user_trading_service.py`
- Integration with existing `TradingService`
- Service management API endpoints

---

### 2.2 User Context Integration
**Complexity**: High | **Effort**: 5 days

**Tasks**:
- [ ] Modify `TradingService` to accept `user_id` and `db_session`
- [ ] Replace file-based storage with repository calls
- [ ] Update all order operations to use `OrdersRepository`
- [ ] Update portfolio operations to use `PositionsRepository`
- [ ] Add user_id to all database operations
- [ ] Maintain backward compatibility during transition

**Key Changes**:
```python
# Before
class TradingService:
    def __init__(self, env_file: str):
        self.env_file = env_file
        # Uses file-based storage

# After
class TradingService:
    def __init__(self, user_id: int, db: Session, broker_creds: dict):
        self.user_id = user_id
        self.db = db
        self.orders_repo = OrdersRepository(db)
        self.positions_repo = PositionsRepository(db)
        # Uses database repositories
```

**Deliverables**:
- Refactored `TradingService` class
- Updated all internal methods
- Backward compatibility layer

---

### 2.3 Broker Authentication Integration
**Complexity**: Medium | **Effort**: 3 days

**Tasks**:
- [ ] Replace `env_file` auth with DB-stored encrypted credentials
- [ ] Load broker credentials from `UserSettings.broker_creds_encrypted`
- [ ] Decrypt credentials per user
- [ ] Handle credential refresh/update
- [ ] Support both paper and broker modes per user

**Implementation**:
```python
def _load_broker_creds(self, user_id: int) -> dict:
    """Load and decrypt broker credentials from DB"""
    settings = SettingsRepository(self.db).get_by_user_id(user_id)
    if not settings.broker_creds_encrypted:
        raise ValueError("No broker credentials stored")

    decrypted = decrypt_blob(settings.broker_creds_encrypted)
    return json.loads(decrypted.decode('utf-8'))
```

**Deliverables**:
- Updated authentication flow
- Credential management integration
- Error handling for missing/invalid credentials

---

### 2.4 Scheduled Tasks Refactoring
**Complexity**: Medium | **Effort**: 4 days

**Tasks**:
- [ ] Convert scheduled tasks to user-scoped operations
- [ ] Update task execution to write to `ServiceTaskExecution` table
- [ ] Add task status tracking in UI
- [ ] Implement per-user task scheduling
- [ ] Handle task failures with user context

**Task Execution Flow**:
```python
def execute_task(self, user_id: int, task_name: str):
    """Execute a scheduled task for a user"""
    task_start = datetime.utcnow()
    try:
        # Execute task with user context
        result = self._run_task(user_id, task_name)

        # Log execution
        ServiceTaskRepository(self.db).create(
            user_id=user_id,
            task_name=task_name,
            executed_at=task_start,
            status='success',
            duration_seconds=(datetime.utcnow() - task_start).total_seconds(),
            details=result
        )
    except Exception as e:
        # Log failure
        ServiceTaskRepository(self.db).create(
            user_id=user_id,
            task_name=task_name,
            executed_at=task_start,
            status='failed',
            details={'error': str(e)}
        )
```

**Deliverables**:
- Refactored task execution methods
- Task logging to database
- Error handling and recovery

---

## Phase 3: API & UI Integration (Weeks 5-6)

### 3.1 Service Management API
**Complexity**: Medium | **Effort**: 3 days

**Tasks**:
- [ ] Create `/api/v1/user/service/start` endpoint
- [ ] Create `/api/v1/user/service/stop` endpoint
- [ ] Create `/api/v1/user/service/status` endpoint
- [ ] Create `/api/v1/user/service/tasks` endpoint (task history)
- [ ] Create `/api/v1/user/service/logs` endpoint (recent logs)

**Endpoints**:
```python
@router.post("/service/start")
def start_service(current: Users = Depends(get_current_user)):
    """Start trading service for current user"""

@router.post("/service/stop")
def stop_service(current: Users = Depends(get_current_user)):
    """Stop trading service for current user"""

@router.get("/service/status")
def get_service_status(current: Users = Depends(get_current_user)):
    """Get service status and health"""

@router.get("/service/tasks")
def get_task_history(current: Users = Depends(get_current_user)):
    """Get task execution history"""
```

**Deliverables**:
- FastAPI router for service management
- API client methods in `web/src/api/`
- API tests

---

### 3.2 Service Status UI
**Complexity**: Medium | **Effort**: 4 days

**Tasks**:
- [ ] Create Service Status page in UI
- [ ] Display service running/stopped status
- [ ] Show last task execution times
- [ ] Display task execution history table
- [ ] Add start/stop service buttons
- [ ] Show real-time service health

**UI Components**:
- `ServiceStatusPage.tsx` - Main service dashboard
- `ServiceTasksTable.tsx` - Task execution history
- `ServiceLogsViewer.tsx` - Recent service logs
- `ServiceControls.tsx` - Start/stop buttons

**Deliverables**:
- React components for service management
- UI tests
- Integration with API

---

### 3.3 Real-Time Updates
**Complexity**: Medium | **Effort**: 3 days

**Tasks**:
- [ ] Add WebSocket support for real-time service status
- [ ] Push order updates to UI
- [ ] Push position updates to UI
- [ ] Push task execution events to UI
- [ ] Implement connection management

**Deliverables**:
- WebSocket server (FastAPI)
- WebSocket client (React)
- Real-time UI updates

---

## Phase 4: Testing & Validation (Weeks 6-8)

### 4.1 Integration Testing
**Complexity**: High | **Effort**: 5 days

**Tasks**:
- [ ] Test data migration scripts with production data
- [ ] Test multi-user service execution
- [ ] Test user isolation (data leakage prevention)
- [ ] Test service start/stop per user
- [ ] Test scheduled tasks execution
- [ ] Test broker authentication per user
- [ ] Load testing (multiple users)

**Test Scenarios**:
1. **Single User**: Service runs normally
2. **Multiple Users**: Services run independently
3. **User Isolation**: User A cannot see User B's data
4. **Service Failures**: One user's service failure doesn't affect others
5. **Credential Management**: Each user's credentials are isolated

**Deliverables**:
- Integration test suite
- Load test results
- Performance benchmarks

---

### 4.2 Migration Validation
**Complexity**: Medium | **Effort**: 3 days

**Tasks**:
- [ ] Validate migrated data accuracy
- [ ] Compare file-based vs DB data
- [ ] Test rollback procedures
- [ ] Validate historical data integrity
- [ ] Performance comparison (file vs DB)

**Deliverables**:
- Validation reports
- Data comparison scripts
- Rollback test results

---

### 4.3 Production Readiness
**Complexity**: Medium | **Effort**: 3 days

**Tasks**:
- [ ] Create deployment guide
- [ ] Create rollback plan
- [ ] Document migration procedure
- [ ] Create monitoring dashboards
- [ ] Set up alerts for service failures
- [ ] Performance tuning

**Deliverables**:
- Deployment documentation
- Rollback procedures
- Monitoring setup
- Alert configuration

---

## Migration Strategy: Dual-Write Approach

### Phase A: Dual-Write (Weeks 1-4)
- ✅ Write to both files AND database
- ✅ Read from files (existing service continues)
- ✅ Validate DB writes match file writes
- ✅ No disruption to existing service

### Phase B: Validation (Week 5)
- ✅ Compare file vs DB data
- ✅ Fix any discrepancies
- ✅ Validate data integrity
- ✅ Performance testing

### Phase C: Cutover (Week 6)
- ✅ Switch reads to database
- ✅ Keep file writes for backup (1 week)
- ✅ Monitor for issues
- ✅ Rollback plan ready

### Phase D: Cleanup (Week 7-8)
- ✅ Stop file writes
- ✅ Archive old files
- ✅ Remove file-based code paths
- ✅ Final validation

---

## Risk Assessment & Mitigation

### High Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Data Loss During Migration** | Critical | Low | Dual-write, validation, backups |
| **Service Downtime** | High | Medium | Phased migration, backward compatibility |
| **Performance Degradation** | Medium | Medium | Load testing, optimization, caching |
| **User Isolation Breach** | Critical | Low | Comprehensive testing, code review |
| **Broker Auth Failures** | High | Medium | Credential validation, error handling |

### Medium Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Migration Script Errors** | Medium | Medium | Test scripts, validation, rollback |
| **Scheduled Task Failures** | Medium | Low | Error handling, retry logic, monitoring |
| **UI Performance Issues** | Low | Medium | Optimization, pagination, caching |

---

## Success Criteria

### Phase 1 Success
- ✅ All data migrated to database
- ✅ Data validation passes
- ✅ No data loss
- ✅ Rollback tested

### Phase 2 Success
- ✅ Multi-user service runs successfully
- ✅ User isolation verified
- ✅ All scheduled tasks execute correctly
- ✅ Performance meets requirements

### Phase 3 Success
- ✅ Service management API works
- ✅ UI displays service status correctly
- ✅ Real-time updates work
- ✅ User can start/stop service

### Phase 4 Success
- ✅ All tests pass
- ✅ Production deployment successful
- ✅ No service disruptions
- ✅ Monitoring and alerts working

---

## Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| **Phase 1: Foundation** | 2 weeks | DB schema, migration scripts, repositories |
| **Phase 2: Architecture** | 3 weeks | Multi-user service, user context, scheduled tasks |
| **Phase 3: API/UI** | 2 weeks | Service management API, UI components |
| **Phase 4: Testing** | 2 weeks | Integration tests, validation, deployment |

**Total**: 6-8 weeks (with some parallel work possible)

---

## Dependencies

### External Dependencies
- ✅ Database (PostgreSQL recommended for production)
- ✅ FastAPI server running
- ✅ React UI deployed
- ✅ Broker API access (Kotak Neo)

### Internal Dependencies
- ✅ User authentication system
- ✅ Database repositories
- ✅ Encryption utilities
- ✅ Existing unified service code

---

## Rollback Plan

### If Migration Fails

1. **Immediate Rollback** (< 1 hour):
   - Stop new service
   - Restart file-based service
   - Verify file-based service works

2. **Data Rollback** (< 4 hours):
   - Restore files from backup
   - Validate file data integrity
   - Resume file-based operations

3. **Code Rollback** (< 1 day):
   - Revert to previous git commit
   - Redeploy previous version
   - Document issues for next attempt

---

## Next Steps

1. **Review & Approve Plan** (1 day)
2. **Set Up Development Environment** (1 day)
3. **Start Phase 1: Foundation** (Week 1)
4. **Weekly Progress Reviews**
5. **Adjust plan based on learnings**

---

## Questions & Decisions Needed

1. **User Assignment**: How to assign existing file-based data to users?
   - Option A: Create "default" user and migrate all data
   - Option B: Manual assignment during migration
   - **Recommendation**: Option A for initial migration, allow reassignment later

2. **Service Execution**: Run one service per user or shared service?
   - Option A: One service instance per user (more isolation)
   - Option B: Shared service with user context (more efficient)
   - **Recommendation**: Option A for better isolation and scalability

3. **Paper Trading**: Migrate paper trading data?
   - **Recommendation**: Yes, create separate users for paper trading

4. **Historical Data**: How far back to migrate?
   - **Recommendation**: All available data (no cutoff)

---

**Document Status**: ✅ Ready for Review
**Next Review Date**: After Phase 1 completion
