# Migration Plan: Unified Trading Service → Multi-User DB/UI System

**Last Updated**: January 2025
**Status**: Phase 1 Complete ✅ | Phase 2 Complete ✅ | Phase 3 Ready
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
| **User Configuration Management** | Medium | Medium | 1.5 weeks |
| **Authentication Integration** | Medium | Low | 1 week |
| **Scheduled Tasks** | Medium | Medium | 1 week |
| **UI Integration** | Medium | Low | 1.5 weeks |
| **ML Training Management** | Medium | Low | 1 week |
| **Logging System** | Medium | Medium | 1.5 weeks |
| **Notifications & Alerts** | Medium | Low | 1 week |
| **Backup & Recovery** | Medium | Medium | 1 week |
| **Audit Trail** | Low | Low | 0.5 weeks |
| **Data Export** | Low | Low | 0.5 weeks |
| **Testing & Validation** | High | High | 2 weeks |

**Total Estimated Effort**: 10-12 weeks (with parallel work)

---

## Phase 1: Foundation & Data Migration (Weeks 1-2) ✅ **COMPLETE**

### 1.1 Database Schema Extensions
**Complexity**: Low | **Effort**: 3 days

**Tasks**:
- [x] Add `service_status` table for tracking service state per user ✅
- [x] Add `service_tasks` table for task execution history ✅
- [x] **Add `service_logs` table for structured logging (user-scoped)** ✅
- [x] **Add `error_logs` table for error/exception tracking (user-scoped)** ✅
- [x] Extend `orders` table with broker-specific fields (order_id, broker_order_id, metadata) ✅
- [x] Add `holdings` table (if not exists) for portfolio tracking ✅
- [x] **Add `user_trading_config` table for user-specific trading configurations** ✅
- [x] **Add `ml_training_jobs` table for ML training job tracking (admin-only)** ✅
- [x] **Add `ml_models` table for ML model versioning (admin-only)** ✅
- [x] **Add `user_notification_preferences` table for notification settings** ✅
- [x] **Add `notifications` table for notification history** ✅
- [x] **Add `audit_logs` table for audit trail** ✅
- [x] Create migration scripts (Alembic) ✅

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

class ServiceLog(Base):
    """Structured service logs (user-scoped)"""
    id: int
    user_id: int  # Foreign key to Users
    level: str  # 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    module: str  # Module/component name
    message: str  # Log message
    context: JSON | None  # Additional context (symbol, order_id, etc.)
    timestamp: datetime
    # Index on (user_id, timestamp, level) for efficient queries

class ErrorLog(Base):
    """Error/exception logs for debugging (user-scoped)"""
    id: int
    user_id: int  # Foreign key to Users
    error_type: str  # Exception class name
    error_message: str  # Exception message
    traceback: str  # Full traceback
    context: JSON | None  # Request context, user config, etc.
    resolved: bool  # Whether error was resolved
    resolved_at: datetime | None
    resolved_by: int | None  # Admin user ID who resolved
    resolution_notes: str | None
    occurred_at: datetime
    # Index on (user_id, occurred_at, resolved) for efficient queries

class MLTrainingJob(Base):
    """ML training job tracking (admin-only)"""
    id: int
    started_by: int  # Admin user ID (Foreign key to Users)
    status: str  # 'pending', 'running', 'completed', 'failed'
    model_type: str  # 'verdict_classifier', 'price_regressor'
    algorithm: str  # 'random_forest', 'xgboost'
    training_data_path: str
    started_at: datetime
    completed_at: datetime | None
    model_path: str | None  # Path to trained model
    accuracy: float | None
    error_message: str | None
    logs: str | None  # Training logs

class MLModel(Base):
    """ML model versioning (admin-only)"""
    id: int
    model_type: str  # 'verdict_classifier', 'price_regressor'
    version: str  # 'v1.0', 'v1.1', etc.
    model_path: str
    accuracy: float | None
    training_job_id: int  # Foreign key to MLTrainingJob
    is_active: bool  # Only one active model per type
    created_at: datetime
    created_by: int  # Admin user ID (Foreign key to Users)

class UserNotificationPreferences(Base):
    """User notification preferences"""
    id: int
    user_id: int  # Foreign key to Users (unique)
    telegram_enabled: bool = False
    telegram_chat_id: str | None = None
    email_enabled: bool = False
    email_address: str | None = None
    in_app_enabled: bool = True
    notify_service_events: bool = True
    notify_trading_events: bool = True
    notify_system_events: bool = True
    notify_errors: bool = True
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None

class Notification(Base):
    """Notification history"""
    id: int
    user_id: int  # Foreign key to Users
    type: str  # 'service', 'trading', 'system', 'error'
    level: str  # 'info', 'warning', 'error', 'critical'
    title: str
    message: str
    read: bool = False
    read_at: datetime | None = None
    created_at: datetime
    telegram_sent: bool = False
    email_sent: bool = False
    in_app_delivered: bool = True

class AuditLog(Base):
    """Audit trail for all actions"""
    id: int
    user_id: int  # Who performed the action
    action: str  # 'create', 'update', 'delete', 'login', 'logout', etc.
    resource_type: str  # 'order', 'config', 'user', 'service', etc.
    resource_id: int | None  # ID of affected resource
    changes: JSON | None  # What changed (before/after)
    ip_address: str | None
    user_agent: str | None
    timestamp: datetime

class UserTradingConfig(Base):
    """User-specific trading strategy and service configurations"""
    id: int
    user_id: int  # Foreign key to Users
    # Strategy Parameters
    rsi_period: int = 10
    rsi_oversold: float = 30.0
    rsi_extreme_oversold: float = 20.0
    rsi_near_oversold: float = 40.0
    # Capital & Position Management
    user_capital: float = 200000.0  # Capital per trade
    max_portfolio_size: int = 6  # Max positions
    max_position_volume_ratio: float = 0.10  # 10% of daily volume
    min_absolute_avg_volume: int = 10000
    # Chart Quality Filters
    chart_quality_enabled: bool = True
    chart_quality_min_score: float = 50.0
    chart_quality_max_gap_frequency: float = 25.0
    chart_quality_min_daily_range_pct: float = 1.0
    chart_quality_max_extreme_candle_frequency: float = 20.0
    # Risk Management
    # Note: Stop loss is optional (not in current system, future feature)
    default_stop_loss_pct: float | None = None  # Optional, 8% if enabled
    tight_stop_loss_pct: float | None = None    # Optional, 6% if enabled
    min_stop_loss_pct: float | None = None      # Optional, 3% if enabled
    default_target_pct: float = 0.10     # 10%
    strong_buy_target_pct: float = 0.12  # 12%
    excellent_target_pct: float = 0.15   # 15%
    # Risk-Reward Ratios
    strong_buy_risk_reward: float = 3.0
    buy_risk_reward: float = 2.5
    excellent_risk_reward: float = 3.5
    # Order Defaults
    default_exchange: str = "NSE"
    default_product: str = "CNC"
    default_order_type: str = "MARKET"
    default_variety: str = "AMO"
    default_validity: str = "DAY"
    # Behavior Toggles
    allow_duplicate_recommendations_same_day: bool = False
    exit_on_ema9_or_rsi50: bool = True
    min_combined_score: int = 25  # Minimum score for order placement
    # News Sentiment
    news_sentiment_enabled: bool = True
    news_sentiment_lookback_days: int = 30
    news_sentiment_min_articles: int = 2
    news_sentiment_pos_threshold: float = 0.25
    news_sentiment_neg_threshold: float = -0.25
    # ML Configuration
    ml_enabled: bool = False
    ml_model_version: str | None = None  # 'v1.0', 'v1.1', or None for active
    ml_confidence_threshold: float = 0.5
    ml_combine_with_rules: bool = True
    # Scheduling Preferences (JSON field for flexibility)
    task_schedule: JSON | None = None  # Custom task timing per user
    # Timestamps
    created_at: datetime
    updated_at: datetime
```

**Deliverables**:
- Database migration files
- Updated models in `src/infrastructure/db/models.py`
- Repository classes for new tables

**Testing** (Incremental):
- [x] Unit tests for new models ✅
- [x] Unit tests for repositories ✅
- [x] Test database migrations (up/down) ✅
- [x] Test schema constraints and indexes ✅
- [x] Schema validation tests ✅

**Documentation** (Incremental):
- [x] Document new database schema ✅
- [x] Document migration process ✅
- [x] Update data model diagrams ✅
- [x] Phase 1 completion report ✅

---

### 1.2 Data Migration Scripts
**Complexity**: Medium-High | **Effort**: 5 days

**Tasks**:
- [x] Create migration script for `trades_history.json` → `orders` + `fills` tables ✅
- [x] Create migration script for `pending_orders.json` → `orders` table (AMO status) ✅
- [x] Create migration script for paper trading data → user-scoped orders ✅
- [x] Create migration script for portfolio/holdings → `positions` table ✅
- [x] Handle data deduplication and validation ✅
- [x] Create rollback scripts ✅

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

**Testing** (Incremental):
- [x] Unit tests for migration scripts ✅
- [x] Integration tests with sample data ✅
- [x] Test data validation logic ✅
- [x] Test rollback procedures ✅
- [x] Test edge cases (empty files, malformed data) ✅

**Documentation** (Incremental):
- [x] Document migration scripts usage ✅
- [x] Document data mapping (file → DB) ✅
- [x] Document validation rules ✅
- [x] Document rollback procedures ✅

---

### 1.3 Repository Layer Updates
**Complexity**: Medium | **Effort**: 3 days

**Tasks**:
- [x] Update `OrdersRepository` to support broker-specific fields ✅
- [x] Create `ServiceStatusRepository` for service state management ✅
- [x] Create `ServiceTaskRepository` for task execution tracking ✅
- [x] **Create `ServiceLogRepository` for structured logging** ✅
- [x] **Create `ErrorLogRepository` for error/exception tracking** ✅
- [x] **Create `UserTradingConfigRepository` for user-specific configurations** ✅
- [x] **Create `MLTrainingJobRepository` for ML training job tracking** ✅
- [x] **Create `MLModelRepository` for ML model versioning** ✅
- [x] **Create `NotificationRepository` for notification management** ✅
- [x] **Create `AuditLogRepository` for audit trail** ✅
- [x] Update `PositionsRepository` to match unified service holdings format ✅
- [x] Add bulk import methods for migration ✅

**Deliverables**:
- Updated repository classes
- Unit tests for repositories (>80% coverage)

**Testing** (Incremental):
- [x] Unit tests for all repository methods ✅
- [x] Test CRUD operations ✅
- [x] Test user isolation (data scoping) ✅
- [x] Test error handling ✅
- [x] Test edge cases (empty results, None values) ✅

**Documentation** (Incremental):
- [x] Document repository interfaces ✅
- [x] Document data access patterns ✅
- [x] Update API documentation ✅

---

### 1.4 User Configuration Management
**Complexity**: Medium | **Effort**: 4 days

**Tasks**:
- [x] Create `UserTradingConfigRepository` with CRUD operations ✅
- [x] Create default configuration factory (from `StrategyConfig.default()`) ✅
- [x] Create configuration migration script (migrate global config to user configs) ✅
- [x] Create API endpoints for configuration management ✅
- [x] Create UI for configuration editing ✅
- [x] Add configuration validation logic ✅

**Configuration Migration Strategy**:
1. **Default User**: Create default user config from current `StrategyConfig.default()`
2. **Existing Users**: Initialize with defaults, allow customization
3. **New Users**: Start with system defaults, can customize via UI

**API Endpoints**:
```python
@router.get("/user/trading-config")
def get_trading_config(current: Users = Depends(get_current_user)):
    """Get user's trading configuration"""

@router.put("/user/trading-config")
def update_trading_config(
    config: TradingConfigUpdate,
    current: Users = Depends(get_current_user)
):
    """Update user's trading configuration"""

@router.post("/user/trading-config/reset")
def reset_trading_config(current: Users = Depends(get_current_user)):
    """Reset to default configuration"""
```

**Configuration Loading in Service**:
```python
class TradingService:
    def __init__(self, user_id: int, db: Session, broker_creds: dict):
        self.user_id = user_id
        self.db = db

        # Load user-specific configuration
        config_repo = UserTradingConfigRepository(db)
        self.config = config_repo.get_or_create_default(user_id)

        # Convert DB config to StrategyConfig object
        self.strategy_config = self._db_config_to_strategy_config(self.config)

        # Use strategy_config throughout service
```

**Deliverables**:
- `UserTradingConfigRepository`
- Configuration migration scripts
- API endpoints for config management
- UI components for config editing
- Configuration validation and defaults

**Testing** (Incremental):
- [x] Unit tests for config repository ✅
- [x] Unit tests for config validation ✅
- [x] API tests for config endpoints ✅
- [x] UI tests for config page ✅
- [x] Test config presets ✅
- [x] Test config migration ✅

**Documentation** (Incremental):
- [x] Document configuration options ✅
- [x] Document config presets ✅
- [x] Document validation rules ✅
- [x] Update user guide with config section ✅

---

## Phase 2: Service Architecture Refactoring (Weeks 3-5) ✅ **COMPLETE**

### 2.1 Multi-User Service Wrapper
**Complexity**: High | **Effort**: 5 days

**Tasks**:
- [x] Create `MultiUserTradingService` class that wraps existing `TradingService` ✅
- [x] Add user context to all service operations ✅
- [x] Implement user-scoped broker authentication ✅
- [x] Add service instance management (one per user) ✅
- [x] Implement service lifecycle management (start/stop per user) ✅

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

**Testing** (Incremental):
- [x] Unit tests for multi-user service wrapper ✅
- [x] Integration tests for service lifecycle ✅
- [x] Test user isolation in services ✅
- [x] Test service start/stop ✅
- [x] Test concurrent services ✅

**Documentation** (Incremental):
- [x] Document service architecture ✅
- [x] Document service lifecycle ✅
- [x] Update architecture diagrams ✅

---

### 2.2 User-Scoped Logging System
**Complexity**: Medium | **Effort**: 4 days

**Tasks**:
- [x] Create user-scoped logger wrapper ✅
- [x] Integrate with existing logging infrastructure ✅
- [x] Add database logging handler (for structured logs) ✅
- [x] Add file logging handler (per-user log files) ✅
- [x] Add error/exception capture and storage ✅
- [x] Add log context injection (user_id, service, task) ✅
- [x] Implement log retention policies ✅
- [x] Add log search and filtering ✅

**Logging Architecture**:
```python
class UserScopedLogger:
    """Logger wrapper that adds user context to all logs"""

    def __init__(self, user_id: int, base_logger: logging.Logger):
        self.user_id = user_id
        self.logger = base_logger
        self.db_handler = DatabaseLogHandler(user_id)
        self.file_handler = UserFileLogHandler(user_id)

    def info(self, message: str, **context):
        """Log info with user context"""
        self._log(logging.INFO, message, context)

    def error(self, message: str, exc_info=None, **context):
        """Log error with user context and exception capture"""
        self._log(logging.ERROR, message, context, exc_info)
        if exc_info:
            self._capture_exception(exc_info, context)

    def _log(self, level: int, message: str, context: dict, exc_info=None):
        """Internal logging with user context"""
        # Add user_id to context
        context['user_id'] = self.user_id
        context['timestamp'] = datetime.utcnow()

        # Log to database (structured)
        self.db_handler.emit(level, message, context)

        # Log to file (detailed)
        self.file_handler.emit(level, message, context, exc_info)

        # Log to console (if needed)
        self.logger.log(level, f"[User {self.user_id}] {message}", extra=context)
```

**File Logging Structure**:
```
logs/
├── users/
│   ├── user_1/
│   │   ├── service_20250115.log
│   │   ├── service_20250116.log
│   │   └── errors_20250115.log
│   ├── user_2/
│   │   └── ...
│   └── admin/
│       └── system.log
```

**Database Logging**:
- Structured logs in `ServiceLog` table
- Error logs in `ErrorLog` table
- Indexed for fast queries
- Retention policy: Keep last 30 days in DB, archive older logs

**Error Capture**:
```python
def capture_exception(user_id: int, exception: Exception, context: dict):
    """Capture exception with full context"""
    error_log = ErrorLog(
        user_id=user_id,
        error_type=type(exception).__name__,
        error_message=str(exception),
        traceback=traceback.format_exc(),
        context={
            'user_config': get_user_config(user_id),
            'service_status': get_service_status(user_id),
            'recent_actions': get_recent_actions(user_id),
            **context
        },
        occurred_at=datetime.utcnow()
    )
    ErrorLogRepository(db).create(error_log)
```

**Log Access**:
- **Users**: Can view their own logs (last 7 days)
- **Admin**: Can view all logs, search across users, filter by level/date
- **API**: REST endpoints for log retrieval with pagination

**Deliverables**:
- User-scoped logger wrapper
- Database logging handler
- File logging handler (per-user)
- Error capture and storage
- Log repository classes
- Log search/filter API

**Testing** (Incremental):
- [x] Unit tests for logger wrapper ✅
- [x] Unit tests for log handlers ✅
- [x] Integration tests for log storage ✅
- [x] Test error capture ✅
- [x] Test log search/filter ✅
- [x] Test log retention ✅

**Documentation** (Incremental):
- [x] Document logging architecture ✅
- [x] Document log access patterns ✅
- [x] Document error resolution workflow ✅

---

### 2.3 User Context Integration
**Complexity**: High | **Effort**: 5 days

**Tasks**:
- [x] Modify `TradingService` to accept `user_id` and `db_session` ✅
- [x] **Load user-specific configuration at service initialization** ✅
- [x] Replace file-based storage with repository calls ✅
- [x] Update all order operations to use `OrdersRepository` ✅
- [x] Update portfolio operations to use `PositionsRepository` ✅
- [x] **Replace global `StrategyConfig` with user-specific config** ✅
- [x] **Update all strategy logic to use user config (RSI thresholds, capital, etc.)** ✅
- [x] Add user_id to all database operations ✅
- [x] Maintain backward compatibility during transition ✅

**Key Changes**:
```python
# Before
class TradingService:
    def __init__(self, env_file: str):
        self.env_file = env_file
        # Uses file-based storage
        # Uses global StrategyConfig.default()

# After
class TradingService:
    def __init__(self, user_id: int, db: Session, broker_creds: dict):
        self.user_id = user_id
        self.db = db
        self.orders_repo = OrdersRepository(db)
        self.positions_repo = PositionsRepository(db)

        # Load user-specific configuration
        config_repo = UserTradingConfigRepository(db)
        user_config = config_repo.get_or_create_default(user_id)
        self.strategy_config = self._db_config_to_strategy_config(user_config)

        # Use user config throughout service
        # - self.strategy_config.rsi_oversold (user-specific)
        # - self.strategy_config.user_capital (user-specific)
        # - self.strategy_config.max_portfolio_size (user-specific)
```

**Configuration Usage Examples**:
```python
# In order placement logic
def place_buy_order(self, symbol: str):
    # Use user's capital per trade
    capital = self.strategy_config.user_capital

    # Use user's RSI thresholds for filtering
    if rsi < self.strategy_config.rsi_oversold:
        # Place order

    # Use user's risk management settings
    # Stop loss is optional (check if configured)
    if self.strategy_config.default_stop_loss_pct:
        stop_loss = price * (1 - self.strategy_config.default_stop_loss_pct)
    target = price * (1 + self.strategy_config.default_target_pct)

# In portfolio management
def check_portfolio_capacity(self):
    current_positions = self.positions_repo.count_open(self.user_id)
    max_positions = self.strategy_config.max_portfolio_size
    return current_positions < max_positions
```

**Deliverables**:
- Refactored `TradingService` class
- Updated all internal methods to use user config
- Configuration loading and validation
- Backward compatibility layer

**Testing** (Incremental):
- [x] Unit tests for user context integration ✅
- [x] Integration tests for service with user config ✅
- [x] Test configuration loading ✅
- [x] Test all scheduled tasks with user context ✅
- [x] Test backward compatibility ✅

**Documentation** (Incremental):
- [x] Document user context integration ✅
- [x] Document configuration usage ✅
- [x] Update service documentation ✅

---

### 2.4 Broker Authentication Integration
**Complexity**: Medium | **Effort**: 3 days

**Tasks**:
- [x] Replace `env_file` auth with DB-stored encrypted credentials ✅
- [x] Load broker credentials from `UserSettings.broker_creds_encrypted` ✅
- [x] Decrypt credentials per user ✅
- [x] Handle credential refresh/update ✅
- [x] Support both paper and broker modes per user ✅

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

**Testing** (Incremental):
- [x] Unit tests for credential loading ✅
- [x] Integration tests for broker auth ✅
- [x] Test credential encryption/decryption ✅
- [x] Test error handling ✅

**Documentation** (Incremental):
- [x] Document authentication flow ✅
- [x] Document credential management ✅
- [x] Update security documentation ✅

---

### 2.5 Scheduled Tasks Refactoring
**Complexity**: Medium | **Effort**: 4 days

**Tasks**:
- [x] Convert scheduled tasks to user-scoped operations ✅
- [x] Update task execution to write to `ServiceTaskExecution` table ✅
- [x] Add task status tracking in UI ✅
- [x] Implement per-user task scheduling ✅
- [x] Handle task failures with user context ✅

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

**Testing** (Incremental):
- [x] Unit tests for task execution ✅
- [x] Integration tests for scheduled tasks ✅
- [x] Test task logging ✅
- [x] Test error recovery ✅
- [x] Test task isolation per user ✅

**Documentation** (Incremental):
- [x] Document task scheduling ✅
- [x] Document task execution flow ✅
- [x] Update task documentation ✅

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
- API tests (>80% coverage)

**Testing** (Incremental):
- [ ] Unit tests for API endpoints
- [ ] Integration tests for service management
- [ ] Test authentication/authorization
- [ ] Test error responses
- [ ] API contract tests

**Documentation** (Incremental):
- [ ] Update API documentation (OpenAPI)
- [ ] Document service management endpoints
- [ ] Update API reference

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
- UI tests (>80% coverage)
- Integration with API

**Testing** (Incremental):
- [ ] Unit tests for React components
- [ ] Integration tests for UI workflows
- [ ] E2E tests for service management
- [ ] Test error states
- [ ] Test loading states

**Documentation** (Incremental):
- [ ] Document UI features
- [ ] Update user guide
- [ ] Create UI screenshots/demos

---

### 3.3 Trading Configuration UI
**Complexity**: Medium | **Effort**: 5 days

**Tasks**:
- [ ] Create Trading Configuration page in UI
- [ ] Display all user-specific configuration settings
- [ ] Group settings by category (Strategy, Risk, Capital, etc.)
- [ ] Add form validation for configuration values
- [ ] Show current vs default values
- [ ] Add "Reset to Defaults" button
- [ ] Add configuration presets (Conservative, Moderate, Aggressive)
- [ ] Show impact of configuration changes (e.g., "This will allow X more positions")

**UI Components**:
- `TradingConfigPage.tsx` - Main configuration page
- `StrategyConfigSection.tsx` - RSI, volume, chart quality settings
- `RiskConfigSection.tsx` - Stop loss, targets, risk-reward ratios
- `CapitalConfigSection.tsx` - Capital per trade, portfolio size
- `OrderConfigSection.tsx` - Order defaults (exchange, product, variety)
- `BehaviorConfigSection.tsx` - Toggles and behavior settings
- `ConfigPresets.tsx` - Predefined configuration templates

**Configuration Categories**:
1. **Strategy Parameters**
   - RSI thresholds (oversold, extreme oversold)
   - Volume settings
   - Chart quality filters

2. **Capital & Position Management**
   - Capital per trade
   - Maximum portfolio size
   - Maximum position volume ratio
   - Minimum average volume

3. **Risk Management**
   - Stop loss percentages (optional - future feature)
   - Target percentages
   - Risk-reward ratios

4. **Order Defaults**
   - Exchange, product, order type
   - Order variety (AMO, REGULAR)
   - Order validity

5. **Behavior Settings**
   - Allow duplicate recommendations
   - Exit conditions
   - Minimum combined score

6. **Advanced Features**
   - News sentiment settings
   - ML configuration (enable/disable, model version selection)
   - Custom task scheduling

**API Integration**:
```typescript
// web/src/api/trading-config.ts
export async function getTradingConfig(): Promise<TradingConfig>
export async function updateTradingConfig(config: Partial<TradingConfig>): Promise<TradingConfig>
export async function resetTradingConfig(): Promise<TradingConfig>
export async function getConfigPresets(): Promise<ConfigPreset[]>
```

**Deliverables**:
- React components for configuration management
- Form validation and error handling
- Configuration presets
- UI tests (>80% coverage)
- Integration with API

**Testing** (Incremental):
- [ ] Unit tests for config components
- [ ] Integration tests for config workflows
- [ ] Test form validation
- [ ] Test config presets
- [ ] E2E tests for config management

**Documentation** (Incremental):
- [ ] Document configuration options
- [ ] Document config presets
- [ ] Update user guide
- [ ] Create config examples

---

### 3.4 ML Training Management (Admin-Only)
**Complexity**: Medium | **Effort**: 4 days

**Tasks**:
- [ ] Create ML training API endpoints (admin-only)
- [ ] Create ML model management endpoints (list, version, activate)
- [ ] Create ML training UI (admin-only)
- [ ] Add training job status tracking
- [ ] Add model versioning system
- [ ] Integrate with user configs (users can enable/disable ML, admin trains)

**Architecture**:
- **Admin Role**: Can trigger ML training, manage models, view training history
- **User Role**: Can enable/disable ML in their config, select model version
- **Training**: Runs as background job, updates model versions when complete
- **Models**: Stored in `models/` directory, versioned by timestamp/version

**API Endpoints** (Admin-Only):
```python
@router.post("/admin/ml/train")
def start_ml_training(
    config: MLTrainingRequest,
    current: Users = Depends(get_current_admin)
):
    """Start ML model training (admin only)"""
    # Trigger background training job
    # Return job ID for status tracking

@router.get("/admin/ml/jobs")
def list_training_jobs(current: Users = Depends(get_current_admin)):
    """List all ML training jobs (admin only)"""

@router.get("/admin/ml/jobs/{job_id}")
def get_training_job_status(
    job_id: int,
    current: Users = Depends(get_current_admin)
):
    """Get training job status (admin only)"""

@router.get("/admin/ml/models")
def list_ml_models(current: Users = Depends(get_current_admin)):
    """List all trained models (admin only)"""

@router.post("/admin/ml/models/{model_id}/activate")
def activate_model(
    model_id: int,
    current: Users = Depends(get_current_admin)
):
    """Activate a model version for use (admin only)"""
```

**Database Schema**:
```python
class MLTrainingJob(Base):
    """ML training job tracking"""
    id: int
    started_by: int  # Admin user ID
    status: str  # 'pending', 'running', 'completed', 'failed'
    model_type: str  # 'random_forest', 'xgboost'
    training_data_path: str
    started_at: datetime
    completed_at: datetime | None
    model_path: str | None  # Path to trained model
    accuracy: float | None
    error_message: str | None

class MLModel(Base):
    """ML model versioning"""
    id: int
    model_type: str  # 'verdict_classifier', 'price_regressor'
    version: str  # 'v1.0', 'v1.1', etc.
    model_path: str
    accuracy: float | None
    training_job_id: int  # Foreign key to MLTrainingJob
    is_active: bool  # Only one active model per type
    created_at: datetime
    created_by: int  # Admin user ID
```

**UI Components** (Admin-Only):
- `MLTrainingPage.tsx` - Main ML training dashboard
- `MLTrainingForm.tsx` - Form to start training (select data, model type)
- `MLTrainingJobsTable.tsx` - List of training jobs with status
- `MLModelsTable.tsx` - List of trained models, activate/deactivate
- `MLTrainingLogs.tsx` - View training logs in real-time

**Training Workflow**:
1. Admin selects training data source (CSV file or database query)
2. Admin selects model type (Random Forest, XGBoost)
3. Admin triggers training (background job)
4. Training runs asynchronously, updates job status
5. On completion, model is saved and versioned
6. Admin can activate new model version
7. Users with ML enabled automatically use active model

**User Integration**:
- Users can enable/disable ML in their `UserTradingConfig`
- Users can select which model version to use (optional, defaults to active)
- ML predictions use the selected/active model

**Deliverables**:
- ML training API endpoints (admin-only)
- ML model management API
- ML training UI (admin-only)
- Background job processing
- Model versioning system
- Integration with user configs

**Testing** (Incremental):
- [ ] Unit tests for ML training API
- [ ] Integration tests for training jobs
- [ ] Test model versioning
- [ ] Test admin authorization
- [ ] UI tests for ML training page

**Documentation** (Incremental):
- [ ] Document ML training workflow
- [ ] Document model versioning
- [ ] Update admin guide
- [ ] Document training data requirements

---

### 3.5 Log Management UI
**Complexity**: Medium | **Effort**: 4 days

**Tasks**:
- [ ] Create Log Viewer page (user and admin views)
- [ ] Display structured logs with filtering
- [ ] Display error logs with traceback viewer
- [ ] Add log search functionality
- [ ] Add log export (CSV, JSON)
- [ ] Add real-time log streaming
- [ ] Add error resolution workflow (admin)

**UI Components**:
- `LogViewerPage.tsx` - Main log viewer
- `LogTable.tsx` - Structured log table with filters
- `ErrorLogTable.tsx` - Error log table with resolution status
- `LogSearch.tsx` - Search and filter controls
- `TracebackViewer.tsx` - Formatted traceback display
- `ErrorResolutionDialog.tsx` - Admin error resolution form
- `LogExport.tsx` - Export logs to file

**User View**:
- View own logs (last 7 days)
- Filter by level (INFO, WARNING, ERROR)
- Search by message/keyword
- View error details and traceback
- Export own logs

**Admin View**:
- View all users' logs
- Filter by user, level, date range
- Search across all logs
- View error logs with resolution status
- Resolve errors (mark as resolved, add notes)
- Export logs for analysis
- Real-time log streaming

**API Endpoints**:
```python
@router.get("/user/logs")
def get_user_logs(
    level: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    search: str | None = None,
    limit: int = 100,
    current: Users = Depends(get_current_user)
):
    """Get user's own logs"""

@router.get("/user/logs/errors")
def get_user_errors(
    resolved: bool | None = None,
    current: Users = Depends(get_current_user)
):
    """Get user's error logs"""

@router.get("/admin/logs")
def get_all_logs(
    user_id: int | None = None,
    level: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    search: str | None = None,
    current: Users = Depends(get_current_admin)
):
    """Get all logs (admin only)"""

@router.get("/admin/logs/errors")
def get_all_errors(
    user_id: int | None = None,
    resolved: bool | None = None,
    current: Users = Depends(get_current_admin)
):
    """Get all error logs (admin only)"""

@router.post("/admin/logs/errors/{error_id}/resolve")
def resolve_error(
    error_id: int,
    notes: str,
    current: Users = Depends(get_current_admin)
):
    """Mark error as resolved (admin only)"""

@router.get("/user/logs/stream")
def stream_logs(
    current: Users = Depends(get_current_user)
):
    """Stream real-time logs (WebSocket)"""
```

**Log Retention Policy**:
- **Database**: Keep last 30 days of structured logs
- **File Logs**: Keep last 90 days, archive older
- **Error Logs**: Keep all unresolved errors, resolved errors for 90 days
- **Archival**: Move old logs to compressed archives

**Deliverables**:
- Log viewer UI components
- Error log viewer with traceback
- Log search and filtering
- Log export functionality
- Error resolution workflow
- Real-time log streaming
- API endpoints for log access

**Testing** (Incremental):
- [ ] Unit tests for log viewer components
- [ ] Integration tests for log access
- [ ] Test log search/filter
- [ ] Test error resolution workflow
- [ ] Test log export
- [ ] E2E tests for log viewing

**Documentation** (Incremental):
- [ ] Document log access
- [ ] Document error resolution
- [ ] Update user/admin guides
- [ ] Document debugging workflows

---

### 3.6 Notifications & Alerts System
**Complexity**: Medium | **Effort**: 5 days

**Tasks**:
- [ ] Create user notification preferences table
- [ ] Integrate with existing Telegram notification system
- [ ] Add in-app notifications (UI notifications)
- [ ] Add email notifications (optional)
- [ ] Create notification API endpoints
- [ ] Create notification UI components
- [ ] Add notification preferences UI

**Notification Types**:
1. **Service Events**
   - Service started/stopped
   - Service errors/failures
   - Task execution failures

2. **Trading Events**
   - Order placed/filled/cancelled
   - Position opened/closed
   - Target price reached
   - Stop loss triggered (if implemented)

3. **System Events**
   - Broker connection issues
   - API rate limit warnings
   - Data feed delays

4. **Admin Events** (Admin only)
   - ML training completed
   - System-wide errors
   - User account issues

**Database Schema**:
```python
class UserNotificationPreferences(Base):
    """User notification preferences"""
    id: int
    user_id: int  # Foreign key to Users
    # Notification channels
    telegram_enabled: bool = False
    telegram_chat_id: str | None = None
    email_enabled: bool = False
    email_address: str | None = None
    in_app_enabled: bool = True  # Always enabled
    # Notification types
    notify_service_events: bool = True
    notify_trading_events: bool = True
    notify_system_events: bool = True
    notify_errors: bool = True
    # Quiet hours (optional)
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None

class Notification(Base):
    """Notification history"""
    id: int
    user_id: int  # Foreign key to Users
    type: str  # 'service', 'trading', 'system', 'error'
    level: str  # 'info', 'warning', 'error', 'critical'
    title: str
    message: str
    read: bool = False
    read_at: datetime | None = None
    created_at: datetime
    # Delivery status
    telegram_sent: bool = False
    email_sent: bool = False
    in_app_delivered: bool = True
```

**API Endpoints**:
```python
@router.get("/user/notifications")
def get_notifications(
    unread_only: bool = False,
    current: Users = Depends(get_current_user)
):
    """Get user's notifications"""

@router.post("/user/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    current: Users = Depends(get_current_user)
):
    """Mark notification as read"""

@router.get("/user/notification-preferences")
def get_preferences(current: Users = Depends(get_current_user)):
    """Get notification preferences"""

@router.put("/user/notification-preferences")
def update_preferences(
    prefs: NotificationPreferencesUpdate,
    current: Users = Depends(get_current_user)
):
    """Update notification preferences"""
```

**Deliverables**:
- Notification preferences management
- Multi-channel notification system (Telegram, Email, In-app)
- Notification history and read status
- Notification preferences UI
- Integration with existing Telegram service

**Testing** (Incremental):
- [ ] Unit tests for notification service
- [ ] Integration tests for notification delivery
- [ ] Test all notification channels
- [ ] Test notification preferences
- [ ] UI tests for notification center

**Documentation** (Incremental):
- [ ] Document notification setup
- [ ] Document notification types
- [ ] Update user guide
- [ ] Document Telegram integration

---

### 3.7 Real-Time Updates
**Complexity**: Medium | **Effort**: 3 days

**Tasks**:
- [ ] Add WebSocket support for real-time service status
- [ ] Push order updates to UI
- [ ] Push position updates to UI
- [ ] Push task execution events to UI
- [ ] Push ML training job updates to admin UI
- [ ] Push notifications to UI
- [ ] Implement connection management

**Deliverables**:
- WebSocket server (FastAPI)
- WebSocket client (React)
- Real-time UI updates

**Testing** (Incremental):
- [ ] Unit tests for WebSocket server
- [ ] Integration tests for WebSocket connections
- [ ] Test real-time updates
- [ ] Test connection management
- [ ] Test reconnection logic

**Documentation** (Incremental):
- [ ] Document WebSocket API
- [ ] Document real-time features
- [ ] Update API documentation

---

## Phase 4: Additional Features & Operations (Weeks 7-9)

### 4.1 Backup & Recovery System
**Complexity**: Medium | **Effort**: 4 days

**Tasks**:
- [ ] Create automated backup system
- [ ] Database backup (daily, weekly, monthly)
- [ ] File backup (log files, models)
- [ ] Backup verification and testing
- [ ] Restore procedures and scripts
- [ ] Backup retention policy
- [ ] Backup UI (admin-only)

**Backup Strategy**:
- **Database**: Daily full backup, weekly incremental
- **Files**: Daily backup of logs, models, configs
- **Retention**: 30 days daily, 12 weeks weekly, 12 months monthly
- **Storage**: Local + cloud (optional)

**Backup Automation**:
```python
class BackupService:
    """Automated backup service"""

    def backup_database(self) -> str:
        """Backup database to file"""

    def backup_files(self, paths: List[str]) -> str:
        """Backup files to archive"""

    def verify_backup(self, backup_path: str) -> bool:
        """Verify backup integrity"""

    def restore_database(self, backup_path: str) -> bool:
        """Restore database from backup"""
```

**Deliverables**:
- Automated backup scripts
- Backup verification tools
- Restore procedures
- Backup management UI (admin)

**Testing** (Incremental):
- [ ] Unit tests for backup service
- [ ] Integration tests for backup/restore
- [ ] Test backup verification
- [ ] Test restore procedures
- [ ] Test backup retention

**Documentation** (Incremental):
- [ ] Document backup procedures
- [ ] Document restore procedures
- [ ] Update admin guide
- [ ] Document backup retention policy

---

### 4.2 Audit Trail System
**Complexity**: Low | **Effort**: 2 days

**Tasks**:
- [ ] Create audit log table
- [ ] Log all user actions (create, update, delete)
- [ ] Log admin actions
- [ ] Log configuration changes
- [ ] Log service start/stop events
- [ ] Create audit log viewer (admin-only)

**Database Schema**:
Already defined in Phase 1.1 (see `AuditLog` table above)

**Deliverables**:
- Audit log table and repository
- Audit logging middleware
- Audit log viewer UI (admin)

**Testing** (Incremental):
- [ ] Unit tests for audit logging
- [ ] Integration tests for audit trail
- [ ] Test audit log capture
- [ ] Test audit log search
- [ ] UI tests for audit viewer

**Documentation** (Incremental):
- [ ] Document audit trail
- [ ] Document audit log access
- [ ] Update admin guide
- [ ] Document compliance features

---

### 4.3 Data Export & Privacy
**Complexity**: Low | **Effort**: 2 days

**Tasks**:
- [ ] Create data export API endpoint
- [ ] Export user data (orders, positions, PnL, configs)
- [ ] Export in JSON/CSV format
- [ ] Add data deletion (GDPR compliance)
- [ ] Create export UI

**API Endpoints**:
```python
@router.get("/user/export")
def export_user_data(
    format: str = "json",  # 'json' or 'csv'
    current: Users = Depends(get_current_user)
):
    """Export all user data"""

@router.delete("/user/data")
def delete_user_data(
    current: Users = Depends(get_current_user)
):
    """Delete all user data (GDPR)"""
```

**Deliverables**:
- Data export functionality
- Data deletion functionality
- Export UI

**Testing** (Incremental):
- [ ] Unit tests for data export
- [ ] Integration tests for export/deletion
- [ ] Test export formats (JSON/CSV)
- [ ] Test data deletion (GDPR)
- [ ] Test export completeness

**Documentation** (Incremental):
- [ ] Document data export
- [ ] Document data deletion
- [ ] Update privacy policy
- [ ] Document GDPR compliance

---

### 4.4 Performance Monitoring
**Complexity**: Medium | **Effort**: 3 days

**Tasks**:
- [ ] Add performance metrics collection
- [ ] Track service performance per user
- [ ] Track API response times
- [ ] Track database query performance
- [ ] Create performance dashboard (admin)
- [ ] Add performance alerts

**Metrics to Track**:
- Service uptime per user
- Task execution times
- API response times
- Database query performance
- Memory/CPU usage per service
- Order execution latency

**Deliverables**:
- Performance metrics collection
- Performance dashboard
- Performance alerts

**Testing** (Incremental):
- [ ] Unit tests for metrics collection
- [ ] Integration tests for performance monitoring
- [ ] Test performance dashboard
- [ ] Test performance alerts

**Documentation** (Incremental):
- [ ] Document performance metrics
- [ ] Document monitoring dashboard
- [ ] Update admin guide
- [ ] Document performance tuning

---

### 4.5 Rate Limiting & Security
**Complexity**: Medium | **Effort**: 3 days

**Tasks**:
- [ ] Add API rate limiting per user
- [ ] Add request throttling
- [ ] Add IP-based rate limiting
- [ ] Add security headers
- [ ] Add input validation and sanitization
- [ ] Add SQL injection prevention
- [ ] Add XSS prevention

**Rate Limiting**:
- Per-user limits: 100 requests/minute
- Per-IP limits: 200 requests/minute
- Admin: Higher limits
- Service endpoints: Separate limits

**Deliverables**:
- Rate limiting middleware
- Security headers
- Input validation
- Security audit

**Testing** (Incremental):
- [ ] Unit tests for rate limiting
- [ ] Integration tests for security
- [ ] Test rate limit enforcement
- [ ] Security tests (SQL injection, XSS)
- [ ] Penetration testing

**Documentation** (Incremental):
- [ ] Document security measures
- [ ] Document rate limiting
- [ ] Update security documentation
- [ ] Document security best practices

---

## Testing & Documentation Strategy

### Approach: **Incremental (Per Phase)** ✅

**Philosophy**: Write tests and documentation **alongside code**, not at the end.

**Benefits**:
- ✅ Catch bugs early (fail fast)
- ✅ Prevent technical debt accumulation
- ✅ Ensure >80% coverage throughout
- ✅ Documentation stays current
- ✅ Easier code reviews
- ✅ Confidence in each phase before moving forward

**Strategy**:
- **Unit Tests**: Write immediately after implementing each component
- **Integration Tests**: Write after completing each phase
- **Documentation**: Update as features are built
- **E2E Tests**: Write after UI components are complete
- **Final Validation**: Comprehensive testing at end (Phase 5)

---

## Testing & Documentation Standards

### Testing Requirements (Per Phase)

**Coverage Targets**:
- **Minimum**: 80% coverage for all new code
- **Critical Paths**: 95%+ (authentication, order execution, data isolation)
- **UI Components**: 80%+ (React components, user interactions)

**Test Types Per Phase**:
1. **Unit Tests**: Write immediately after each component
2. **Integration Tests**: Write after completing each feature
3. **API Tests**: Write after each API endpoint
4. **UI Tests**: Write after each UI component
5. **E2E Tests**: Write after completing each user workflow

**Test Organization**:
```
tests/
├── server/
│   ├── test_broker_api.py ✅ (already exists)
│   ├── test_service_api.py (new)
│   ├── test_config_api.py (new)
│   └── test_notification_api.py (new)
├── unit/
│   ├── services/
│   │   └── test_multi_user_trading_service.py (new)
│   └── infrastructure/
│       └── test_user_scoped_logger.py (new)
├── integration/
│   ├── test_multi_user_isolation.py (new)
│   ├── test_service_lifecycle.py (new)
│   └── test_data_migration.py (new)
└── e2e/
    └── test_user_workflows.py (new)
```

**Test Execution**:
- Run tests after each component: `pytest tests/unit/ tests/server/ -v`
- Run full suite before phase completion: `pytest tests/ -v --cov`
- CI runs all tests on every commit

### Documentation Requirements (Per Phase)

**Documentation Types**:
1. **Code Documentation**: Docstrings, type hints (as code is written)
2. **API Documentation**: OpenAPI/Swagger (auto-generated from code)
3. **User Documentation**: Updated as features are built
4. **Admin Documentation**: Updated as admin features are built
5. **Architecture Documentation**: Updated as architecture evolves

**Documentation Updates Per Phase**:
- **Phase 1**: Database schema docs, migration guides
- **Phase 2**: Service architecture docs, logging docs
- **Phase 3**: API docs, UI user guides
- **Phase 4**: Admin guides, operational docs
- **Phase 5**: Final review, comprehensive guides

**Documentation Location**:
- Code docs: Inline docstrings
- API docs: `docs/api/` (auto-generated)
- User guides: `docs/user-guide/`
- Admin guides: `docs/admin-guide/`
- Architecture: `docs/architecture/`

---

## Phase 5: Final Testing & Validation (Weeks 11-12)

### 5.1 Comprehensive Integration Testing
**Complexity**: High | **Effort**: 3 days

**Tasks**:
- [ ] Run full test suite (all phases)
- [ ] Test end-to-end workflows (user signup → service start → trading → monitoring)
- [ ] Test multi-user scenarios (10+ concurrent users)
- [ ] Test user isolation comprehensively
- [ ] Test service failure recovery
- [ ] Test data migration with production data
- [ ] Load testing (50+ concurrent users)
- [ ] Stress testing (resource limits)

**Test Scenarios**:
1. **Complete User Journey**: Signup → Config → Service Start → Trading → Monitoring
2. **Multi-User Isolation**: 10 users, verify complete data isolation
3. **Service Failures**: One user's service fails, others unaffected
4. **Credential Management**: Each user's credentials isolated and encrypted
5. **Configuration Changes**: User changes config, service picks up changes
6. **Notification Delivery**: All channels work correctly
7. **Backup/Restore**: Full backup and restore cycle
8. **Audit Trail**: All actions logged correctly

**Deliverables**:
- Comprehensive integration test suite
- Load test results
- Stress test results
- Performance benchmarks

---

### 5.2 Migration Validation
**Complexity**: Medium | **Effort**: 2 days

**Tasks**:
- [ ] Validate migrated data accuracy (100% match)
- [ ] Compare file-based vs DB data (automated)
- [ ] Test rollback procedures (end-to-end)
- [ ] Validate historical data integrity
- [ ] Performance comparison (file vs DB)
- [ ] Data consistency checks

**Deliverables**:
- Validation reports
- Data comparison scripts
- Rollback test results
- Performance comparison report

---

### 5.3 Documentation Finalization
**Complexity**: Medium | **Effort**: 2 days

**Tasks**:
- [ ] Review and finalize all phase documentation
- [ ] Create user guide (how to use the system)
- [ ] Create admin guide (how to manage users, ML training, etc.)
- [ ] Create API documentation (OpenAPI/Swagger)
- [ ] Create deployment guide
- [ ] Create troubleshooting guide
- [ ] Create migration guide (for future migrations)
- [ ] Update README with new architecture

**Documentation Structure**:
```
docs/
├── migration/
│   └── UNIFIED_SERVICE_TO_MULTIUSER_MIGRATION_PLAN.md (this file)
├── user-guide/
│   ├── getting-started.md
│   ├── trading-configuration.md
│   ├── service-management.md
│   └── notifications.md
├── admin-guide/
│   ├── user-management.md
│   ├── ml-training.md
│   ├── monitoring.md
│   └── backup-recovery.md
├── api/
│   └── api-reference.md (auto-generated from OpenAPI)
└── deployment/
    ├── deployment-guide.md
    ├── troubleshooting.md
    └── migration-procedure.md
```

**Deliverables**:
- Complete user documentation
- Complete admin documentation
- API documentation (OpenAPI)
- Deployment guide
- Troubleshooting guide

---

### 5.4 Production Readiness Checklist
**Complexity**: Medium | **Effort**: 1 day

**Tasks**:
- [ ] All tests passing (>80% coverage)
- [ ] All documentation complete
- [ ] Security audit completed
- [ ] Performance benchmarks met
- [ ] Backup/restore tested
- [ ] Monitoring and alerts configured
- [ ] Rollback plan tested
- [ ] Deployment procedure documented
- [ ] Team training completed

**Deliverables**:
- Production readiness report
- Go/No-Go decision document

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
- ✅ **Unit tests >80% coverage**
- ✅ **Documentation complete**

### Phase 2 Success
- ✅ Multi-user service runs successfully
- ✅ User isolation verified
- ✅ All scheduled tasks execute correctly
- ✅ Performance meets requirements
- ✅ **Integration tests >80% coverage**
- ✅ **Documentation updated**

### Phase 3 Success
- ✅ Service management API works
- ✅ UI displays service status correctly
- ✅ Real-time updates work
- ✅ User can start/stop service
- ✅ **API tests >80% coverage**
- ✅ **UI tests >80% coverage**
- ✅ **User documentation complete**

### Phase 4 Success
- ✅ All operational features working
- ✅ Backup/restore tested
- ✅ Security audit passed
- ✅ Performance monitoring working
- ✅ **All tests >80% coverage**
- ✅ **Admin documentation complete**

### Phase 5 Success
- ✅ All tests pass (>80% coverage)
- ✅ Comprehensive integration tests pass
- ✅ Load testing passed
- ✅ Production deployment successful
- ✅ No service disruptions
- ✅ Monitoring and alerts working
- ✅ **All documentation finalized**
- ✅ **Team trained on new system**

---

## Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| **Phase 1: Foundation** | 2 weeks | DB schema, migration scripts, repositories + **tests & docs** |
| **Phase 2: Architecture** | 3 weeks | Multi-user service, user context, scheduled tasks, logging + **tests & docs** |
| **Phase 3: API/UI** | 2.5 weeks | Service management API, UI components, notifications + **tests & docs** |
| **Phase 4: Operations** | 2 weeks | Backup, audit, export, monitoring, security + **tests & docs** |
| **Phase 5: Final Testing** | 1.5 weeks | Comprehensive integration tests, validation, documentation finalization |

**Total**: 10-12 weeks (with some parallel work possible)

**Note**: Testing and documentation are **incremental** - written alongside each phase, not at the end. Phase 5 is for final validation and documentation review.

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

## Decisions Made ✅

1. **User Assignment**: ✅ **DECIDED - Option A**
   - Create "default" user and migrate all data
   - Allow reassignment later if needed
   - **Status**: Approved

2. **Service Execution**: ✅ **DECIDED - Option A**
   - One service instance per user (better isolation and scalability)
   - Each user gets their own service process
   - **Status**: Approved

3. **Paper Trading**: ✅ **DECIDED - Yes**
   - Migrate paper trading data
   - Create separate users for paper trading
   - **Status**: Approved

4. **Historical Data**: ✅ **DECIDED - All Data**
   - Migrate all available historical data (no cutoff)
   - Preserve complete trading history
   - **Status**: Approved

5. **Configuration Defaults**: ✅ **DECIDED - Option A**
   - Migrate current global config as default for all users
   - Preserve current behavior, allow customization later
   - **Status**: Approved

6. **Configuration Validation**: ✅ **DECIDED - Updated Rules**
   - RSI thresholds: 0-100, oversold < near_oversold
   - Capital: > 0, reasonable max (e.g., 10M)
   - Portfolio size: 1-20 positions
   - **Stop loss: Optional (not in current system, may be future feature)**
   - Risk-reward: >= 1.0 (if applicable)
   - **Status**: Approved with stop loss clarification

7. **Configuration Presets**: ✅ **DECIDED - Yes**
   - Provide 3 presets:
     - **Conservative**: Lower RSI thresholds, smaller positions, more selective
     - **Moderate**: Current defaults (balanced)
     - **Aggressive**: Higher RSI thresholds, larger positions, more aggressive entry
   - **Status**: Approved

8. **ML Training Management**: ✅ **DECIDED - Admin-Only**
   - Admin can trigger ML training jobs
   - Admin can manage model versions (activate/deactivate)
   - Users can enable/disable ML in their config
   - Users can select model version (optional, defaults to active)
   - Training runs as background job with status tracking
   - **Status**: Approved

9. **Logging Management**: ✅ **DECIDED - User-Scoped Logging**
   - Each user has separate log files and database logs
   - Users can view their own logs (last 7 days)
   - Admin can view all logs, search across users
   - Error/exception logs with full context and traceback
   - Error resolution workflow (admin can mark errors as resolved)
   - Log retention: 30 days in DB, 90 days in files
   - Real-time log streaming for debugging
   - **Status**: Approved

10. **Notifications & Alerts**: ✅ **DECIDED - Multi-Channel**
    - Users can configure notification preferences (Telegram, Email, In-app)
    - Notifications for service events, trading events, errors
    - In-app notification center with read/unread status
    - Integration with existing Telegram service
    - Quiet hours support (optional)
    - **Status**: Approved

11. **Backup & Recovery**: ✅ **DECIDED - Automated Backups**
    - Automated daily database backups
    - Automated file backups (logs, models)
    - Backup verification and testing
    - Restore procedures documented
    - Backup retention: 30 days daily, 12 weeks weekly, 12 months monthly
    - **Status**: Approved

12. **Audit Trail**: ✅ **DECIDED - Comprehensive Logging**
    - Log all user actions (create, update, delete)
    - Log admin actions
    - Log configuration changes
    - Log service events
    - Admin-only audit log viewer
    - **Status**: Approved

13. **Data Export & Privacy**: ✅ **DECIDED - GDPR Compliant**
    - Users can export all their data (JSON/CSV)
    - Users can delete all their data (GDPR)
    - Data export UI
    - **Status**: Approved

14. **Performance Monitoring**: ✅ **DECIDED - Per-User Metrics**
    - Track service performance per user
    - Track API response times
    - Track database query performance
    - Performance dashboard (admin)
    - Performance alerts
    - **Status**: Approved

15. **Rate Limiting & Security**: ✅ **DECIDED - Per-User Limits**
    - API rate limiting per user (100 req/min)
    - IP-based rate limiting (200 req/min)
    - Security headers
    - Input validation and sanitization
    - SQL injection and XSS prevention
    - **Status**: Approved

---

## Implementation Notes

### Stop Loss Handling
- **Current System**: No stop loss implementation
- **Migration**: Stop loss fields in config will be optional/nullable
- **Future**: Can be added as optional feature without breaking existing functionality
- **Validation**: Skip stop loss validation if not enabled/configured

### Configuration Schema Update
The `UserTradingConfig` table will have stop loss fields as **optional**:
```python
# Risk Management (Optional - not in current system)
default_stop_loss_pct: float | None = None  # Optional, future feature
tight_stop_loss_pct: float | None = None    # Optional, future feature
min_stop_loss_pct: float | None = None      # Optional, future feature
```

This allows:
- Current system: All stop loss fields = None (not used)
- Future enhancement: Users can optionally configure stop loss
- No breaking changes: Service logic checks if stop loss is configured before using

### ML Training Management
- **Admin Role**: Full control over ML training
  - Trigger training jobs
  - Manage model versions
  - View training history and logs
  - Activate/deactivate models

- **User Role**: Configuration only
  - Enable/disable ML in their config
  - Select model version (optional, defaults to active)
  - Cannot trigger training

- **Training Workflow**:
  1. Admin triggers training via UI/API
  2. Training runs as background job
  3. Job status tracked in database
  4. On completion, model versioned and saved
  5. Admin activates new version
  6. Users with ML enabled use active model

- **Model Storage**:
  - Models stored in `models/` directory
  - Versioned by timestamp/version number
  - Database tracks model metadata
  - Only one active model per type (verdict_classifier, price_regressor)

### Logging Management
- **User-Scoped Logging**:
  - Each user's service logs to separate files: `logs/users/user_{id}/service_{date}.log`
  - Structured logs stored in database (`ServiceLog` table)
  - Error logs stored separately (`ErrorLog` table) with full context

- **Log Access**:
  - **Users**: View own logs (last 7 days), search, filter by level
  - **Admin**: View all logs, search across users, filter by user/level/date
  - **Error Logs**: Full traceback, context (user config, service status), resolution tracking

- **Error Resolution Workflow**:
  1. Error occurs → Captured with full context
  2. Error appears in admin error log dashboard
  3. Admin investigates (view traceback, context, user config)
  4. Admin resolves error (add notes, mark as resolved)
  5. User notified if error affected their service

- **Log Retention**:
  - Database: Last 30 days (structured logs)
  - Files: Last 90 days (detailed logs)
  - Error logs: All unresolved, resolved for 90 days
  - Older logs archived to compressed files

- **Real-Time Debugging**:
  - WebSocket streaming for real-time log viewing
  - Filter by level, search keywords
  - Useful for debugging active issues

- **Context Capture**:
  - User configuration at time of error
  - Service status and recent actions
  - Request context (symbol, order_id, etc.)
  - Full Python traceback
  - System state (memory, CPU if available)

### Notifications & Alerts
- **Multi-Channel Support**:
  - Telegram (existing integration)
  - Email (optional, future)
  - In-app notifications (always enabled)

- **Notification Types**:
  - Service events (start/stop, errors)
  - Trading events (orders, positions)
  - System events (broker issues, API limits)
  - Error notifications (critical errors)

- **User Preferences**:
  - Enable/disable per channel
  - Enable/disable per notification type
  - Quiet hours (optional)
  - Notification history with read/unread status

### Backup & Recovery
- **Automated Backups**:
  - Database: Daily full, weekly incremental
  - Files: Daily (logs, models, configs)
  - Retention: 30 days daily, 12 weeks weekly, 12 months monthly

- **Recovery Procedures**:
  - Database restore from backup
  - File restore from backup
  - Point-in-time recovery (if supported)
  - Disaster recovery plan

### Audit Trail
- **Comprehensive Logging**:
  - All user actions (CRUD operations)
  - Admin actions
  - Configuration changes
  - Service events
  - Login/logout events

- **Audit Log Features**:
  - Who did what, when
  - What changed (before/after)
  - IP address and user agent
  - Searchable and filterable
  - Admin-only access

### Data Export & Privacy
- **Data Export**:
  - Export all user data (orders, positions, PnL, configs)
  - Formats: JSON, CSV
  - One-click export via UI

- **Data Deletion**:
  - GDPR-compliant data deletion
  - Soft delete (mark as deleted, retain for audit)
  - Hard delete (after retention period)

### Performance Monitoring
- **Metrics Collection**:
  - Service uptime per user
  - Task execution times
  - API response times
  - Database query performance
  - Resource usage (memory, CPU)

- **Monitoring Dashboard**:
  - Real-time metrics
  - Historical trends
  - Performance alerts
  - Admin-only access

### Security & Rate Limiting
- **Rate Limiting**:
  - Per-user: 100 requests/minute
  - Per-IP: 200 requests/minute
  - Admin: Higher limits
  - Service endpoints: Separate limits

- **Security Measures**:
  - Security headers (CORS, CSP, etc.)
  - Input validation and sanitization
  - SQL injection prevention
  - XSS prevention
  - CSRF protection
  - Encrypted credentials storage

---

**Document Status**: ✅ Ready for Review
**Next Review Date**: After Phase 1 completion
