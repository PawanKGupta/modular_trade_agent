# Architecture Overview

Complete architecture documentation for the Modular Trade Agent system.

## System Overview

The Modular Trade Agent is a **multi-user, web-based trading system** with the following architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    React Web Frontend                         │
│  (TypeScript, React Router, TanStack Query)                  │
└────────────────────────┬──────────────────────────────────────┘
                         │ HTTP/REST
┌────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend                             │
│  (Python, SQLAlchemy, Pydantic, JWT Auth)                      │
└────────┬──────────────┬──────────────┬────────────────────────┘
         │              │              │
    ┌────▼────┐    ┌────▼────┐   ┌────▼────┐
    │ SQLite  │    │ Kotak   │   │Telegram │
    │   DB    │    │ Neo API │   │   API   │
    └─────────┘    └─────────┘   └─────────┘
```

## Core Components

### 1. Frontend (React/TypeScript)

**Location:** `web/src/`

**Key Features:**
- **Pages:**
  - Authentication (Login/Signup)
  - Dashboard (Buying Zone, Orders, Targets, P&L)
  - Paper Trading
  - Service Status & Management
  - Trading Configuration
  - Settings (Broker, Telegram)
  - Admin (Users, ML Training, Logs)

- **State Management:**
  - TanStack Query for server state
  - Zustand for client state (optional)
  - React Context for auth

- **API Client:**
  - Centralized API client in `web/src/api/`
  - Automatic token refresh
  - Error handling

### 2. Backend (FastAPI)

**Location:** `server/app/`

**Key Components:**

#### API Routers (`server/app/routers/`)
- `auth.py` - Authentication (signup, login, refresh)
- `signals.py` - Trading signals and buying zone
- `orders.py` - Order management
- `targets.py` - Target management
- `pnl.py` - Profit & Loss tracking
- `paper_trading.py` - Paper trading operations
- `trading_config.py` - Trading configuration
- `broker.py` - Broker credential management
- `service.py` - Service status and management
- `ml.py` - ML training and models
- `logs.py` - Log viewing
- `admin.py` - Admin operations
- `user.py` - User management
- `activity.py` - Activity tracking
- `notification_preferences.py` - Notification preferences management

#### Core (`server/app/core/`)
- `config.py` - Application configuration
- `security.py` - Password hashing, JWT tokens
- `deps.py` - Dependency injection (DB, auth)

#### Schemas (`server/app/schemas/`)
- Pydantic models for request/response validation

### 3. Business Logic Layer

**Location:** `src/`

**Clean Architecture Pattern:**

```
src/
├── domain/              # Domain entities and business rules
│   ├── entities/        # Core business objects
│   └── value_objects/   # Value objects
├── application/         # Application services (use cases)
│   └── services/        # Business logic orchestration
└── infrastructure/      # Infrastructure adapters
    ├── db/              # Database models and repositories
    ├── persistence/     # Repository implementations
    └── external/        # External API adapters
```

### 4. Service Layer (Phase 4)

**Location:** `services/`

**Status:** ✅ **Primary Implementation** (Phase 4 Complete)

The service layer is the **recommended way** to interact with analysis functionality. Legacy `core.*` functions are deprecated and will be removed in a future version.

**Key Services:**

#### Core Analysis Services
- **`AnalysisService`** - Main stock analysis orchestration
  - Replaces `core.analysis.analyze_ticker()`
  - Coordinates data fetching, indicators, signals, and verdicts
  - Supports dependency injection for testing

- **`AsyncAnalysisService`** - Async batch analysis
  - Replaces `core.analysis.analyze_multiple_tickers()`
  - **80% faster** batch processing (25min → 5min for 50 stocks)
  - Parallel processing with configurable concurrency

#### Supporting Services
- **`DataService`** - Data fetching from yfinance
  - Replaces `core.data_fetcher` functions
  - Supports caching (70-90% reduction in API calls)

- **`IndicatorService`** - Technical indicator calculation
  - Replaces `core.indicators` functions
  - Configurable via `StrategyConfig`

- **`SignalService`** - Signal detection (patterns, RSI, etc.)
  - Replaces `core.patterns` and signal detection logic
  - Detects hammer, bullish engulfing, divergence, etc.

- **`VerdictService`** - Verdict determination and trading parameters
  - Replaces `core.analysis.calculate_smart_*()` functions
  - Returns typed `TradingParameters` object

- **`ScoringService`** - Scoring and ranking
  - Replaces `core.scoring.compute_strength_score()`
  - Provides strength scores, priority scores, combined scores

- **`BacktestService`** - Backtesting integration
  - Replaces `core.backtest_scoring` functions
  - Adds historical performance scoring

#### ML Services (Optional)
- **`MLVerdictService`** - ML-based verdict prediction
  - Two-stage approach: chart quality filter + ML prediction
  - Requires trained model file

- **`MLPriceService`** - ML-based price prediction
- **`MLTrainingService`** - Automated model training

#### Advanced Features (Phase 2-3)
- **`AsyncDataService`** - Async data fetching
- **`CacheService`** - Caching layer (70-90% API call reduction)
- **`EventBus`** - Event-driven architecture
- **`AnalysisPipeline`** - Composable pipeline pattern

**Migration:** See [docs/MIGRATION_GUIDE_PHASE4.md](MIGRATION_GUIDE_PHASE4.md) for migrating from `core.*` to services.

**Example Usage:**
```python
from services import AnalysisService, AsyncAnalysisService
import asyncio

# Single ticker analysis
service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS")

# Batch analysis (80% faster)
async def analyze():
    async_service = AsyncAnalysisService(max_concurrent=10)
    results = await async_service.analyze_batch_async(
        tickers=["RELIANCE.NS", "TCS.NS", "INFY.NS"]
    )
    return results

results = asyncio.run(analyze())
```

### 5. Trading Module

**Location:** `modules/kotak_neo_auto_trader/`

**Components:**
- Broker integration (Kotak Neo API)
- Order placement and management
- Position tracking
- Paper trading adapter
- Scheduled service execution

### 6. Notification System

**Location:** `modules/kotak_neo_auto_trader/telegram_notifier.py` and `services/notification_preference_service.py`

**Architecture:**

```
┌─────────────────────────────────────────────────────────┐
│              Notification Sources                        │
│  (AutoTradeEngine, UnifiedOrderMonitor, etc.)           │
└────────────────────┬──────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│            TelegramNotifier                             │
│  - Rate limiting (10/min, 100/hour)                    │
│  - Message formatting                                    │
│  - Preference checking                                   │
└────────────────────┬──────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│      NotificationPreferenceService                      │
│  - Get user preferences                                 │
│  - Check if notification should be sent                 │
│  - Check quiet hours                                    │
│  - Get enabled channels                                 │
│  - Cache management (5 min TTL)                         │
└────────────────────┬──────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│         UserNotificationPreferences                      │
│  (Database Table)                                       │
│  - Channel preferences (Telegram, Email, In-App)        │
│  - Event type preferences (26 granular events)        │
│  - Quiet hours                                          │
└─────────────────────────────────────────────────────────┘
```

**Key Components:**

#### NotificationPreferenceService
**Location:** `services/notification_preference_service.py`

**Purpose:** Centralized service for managing and checking user notification preferences.

**Key Methods:**
- `get_preferences(user_id)` - Get user preferences (with caching)
- `get_or_create_default_preferences(user_id)` - Get or create default preferences
- `update_preferences(user_id, preferences_dict)` - Update user preferences
- `should_notify(user_id, event_type, channel)` - Check if notification should be sent
- `is_quiet_hours(user_id)` - Check if current time is within quiet hours
- `get_enabled_channels(user_id)` - Get list of enabled notification channels
- `clear_cache(user_id)` - Clear preference cache

**Features:**
- In-memory caching (5-minute TTL) to reduce database queries
- Automatic default preference creation for new users
- Support for quiet hours (including spanning midnight)
- Granular event type filtering
- Channel enablement checking

#### EmailNotifier
**Location:** `services/email_notifier.py`

**Purpose:** Send email notifications via SMTP.

**Configuration:**
- Reads SMTP settings from environment variables:
  - `SMTP_HOST`: SMTP server hostname (e.g., smtp.gmail.com)
  - `SMTP_PORT`: SMTP server port (default: 587)
  - `SMTP_USER`: SMTP username/email
  - `SMTP_PASSWORD`: SMTP password or app password
  - `SMTP_FROM_EMAIL`: From email address (defaults to SMTP_USER)
  - `SMTP_USE_TLS`: Use TLS encryption (default: True)

**Methods:**
- `is_available()` - Check if SMTP is configured
- `send_service_notification(to_email, title, message, level)` - Send service event notification
- `send_email(to_email, subject, body, html_body=None)` - Send generic email

**Integration:**
- Used by `IndividualServiceManager` and `MultiUserTradingService` for service event notifications
- Respects user email preferences and notification preferences
- Only sends if email is enabled in user preferences and SMTP is configured

#### TelegramNotifier
**Location:** `modules/kotak_neo_auto_trader/telegram_notifier.py`

**Purpose:** Send notifications via Telegram with preference checking.

**Integration:**
- Automatically checks user preferences before sending
- Respects quiet hours
- Checks channel enablement
- Maps notification methods to event types

**Notification Methods:**
- `notify_order_placed()` → `ORDER_PLACED`
- `notify_order_rejection()` → `ORDER_REJECTED`
- `notify_order_execution()` → `ORDER_EXECUTED`
- `notify_order_cancelled()` → `ORDER_CANCELLED`
- `notify_order_modified()` → `ORDER_MODIFIED` (new in Phase 4)
- `notify_partial_fill()` → `PARTIAL_FILL`
- `notify_retry_queue_updated()` → `RETRY_QUEUE_*` events
- `notify_system_alert()` → `SYSTEM_ERROR/WARNING/INFO`
- `notify_daily_summary()` → `TRADING_EVENT` (legacy)
- `notify_tracking_stopped()` → `TRADING_EVENT` (legacy)

**Service Event Notifications:**
Service lifecycle events are handled by `IndividualServiceManager` and `MultiUserTradingService`:
- `_notify_service_started()` → `SERVICE_STARTED` (Telegram, Email, In-App)
- `_notify_service_stopped()` → `SERVICE_STOPPED` (Telegram, Email, In-App)
- `_notify_service_execution_completed()` → `SERVICE_EXECUTION_COMPLETED` (Telegram, Email, In-App)

**Event Types:**
See [Notification Event Types](#notification-event-types) section below.

#### Database Schema
**Table:** `user_notification_preferences`

**Columns:**
- **Channels:** `telegram_enabled`, `telegram_chat_id`, `email_enabled`, `email_address`, `in_app_enabled`
- **Order Events:** `notify_order_placed`, `notify_order_rejected`, `notify_order_executed`, `notify_order_cancelled`, `notify_order_modified`, `notify_partial_fill`
- **Retry Queue Events:** `notify_retry_queue_added`, `notify_retry_queue_updated`, `notify_retry_queue_removed`, `notify_retry_queue_retried`
- **System Events:** `notify_system_errors`, `notify_system_warnings`, `notify_system_info`
- **Service Events:** `notify_service_started`, `notify_service_stopped`, `notify_service_execution_completed`
- **Quiet Hours:** `quiet_hours_start`, `quiet_hours_end`
- **Legacy:** `notify_service_events`, `notify_trading_events`, `notify_system_events`, `notify_errors`

**Migration:** See [Migration Guide](#notification-preferences-migration) section below.

## Data Flow

### Signal Generation Flow

```
1. Scheduled Service Trigger
   ↓
2. Analysis Service
   ├─→ Data Service (fetch stock data)
   ├─→ Indicator Service (calculate indicators)
   ├─→ Signal Service (generate signals)
   └─→ Verdict Service (determine verdict)
   ↓
3. ML Service (optional - enhance verdict)
   ↓
4. Save to Database (BuyingZone table)
   ↓
5. Web UI displays signals
```

### Order Execution Flow

```
1. User approves signal (or auto-approve)
   ↓
2. Trading Service creates order
   ↓
3. Broker Adapter places order via Kotak Neo API
   ↓
4. Order status tracked in database
   ↓
5. Monitoring service checks order status
   ↓
6. Target/Stop management
   ↓
7. P&L calculation and reporting
```

## Database Schema

### Core Tables

- **users** - User accounts and authentication
- **user_settings** - User-specific settings (encrypted broker credentials)
- **buying_zone** - Trading signals
- **orders** - Order history
- **targets** - Target prices and stops
- **positions** - Current positions
- **paper_trading** - Paper trading records
- **pnl** - Profit & Loss records
- **service_tasks** - Scheduled task execution history
- **ml_models** - ML model metadata
- **ml_training_jobs** - ML training job history

## Security Architecture

### Authentication Flow

```
1. User submits credentials
   ↓
2. Backend verifies password (pbkdf2_sha256)
   ↓
3. Generate JWT access token + refresh token
   ↓
4. Frontend stores tokens
   ↓
5. Subsequent requests include token in Authorization header
   ↓
6. Backend validates token and extracts user ID
   ↓
7. User-scoped data access
```

### Credential Encryption

- Broker credentials encrypted using Fernet (AES-128)
- Encryption key stored in environment variable
- Credentials decrypted only when needed for API calls
- Never logged or exposed in responses

## Deployment Architecture

### Development

```
┌─────────────┐
│   React     │  :5173
│   (Vite)    │
└──────┬──────┘
       │
┌──────▼──────┐
│   FastAPI   │  :8000
│  (Uvicorn)  │
└──────┬──────┘
       │
┌──────▼──────┐
│   SQLite    │
│   (Local)   │
└─────────────┘
```

### Production (Docker)

```
┌─────────────────────────────────────┐
│         Docker Compose              │
│  ┌──────────────┐  ┌──────────────┐ │
│  │   Nginx      │  │   FastAPI    │ │
│  │  (Web UI)    │  │   (API)      │ │
│  │   :5173      │  │   :8000      │ │
│  └──────┬───────┘  └──────┬───────┘ │
│         │                  │         │
│  ┌──────▼──────────────────▼───────┐ │
│  │      PostgreSQL/SQLite          │ │
│  │         (Database)               │ │
│  └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

## Key Design Patterns

### 1. Repository Pattern
- Data access abstraction
- Location: `src/infrastructure/persistence/`

### 2. Service Layer Pattern
- Business logic orchestration
- Location: `services/` and `src/application/services/`

### 3. Dependency Injection
- FastAPI's Depends() for DI
- Database sessions, authentication

### 4. Clean Architecture
- Separation of concerns
- Domain → Application → Infrastructure

### 5. Event-Driven (Partial)
- Event bus for decoupled components
- Location: `services/event_bus.py`

## Technology Choices

### Why FastAPI?
- Modern Python async support
- Automatic API documentation
- Type validation with Pydantic
- High performance

### Why React?
- Component-based architecture
- Rich ecosystem
- TypeScript for type safety
- TanStack Query for server state

### Why SQLite (Dev) / PostgreSQL (Prod)?
- SQLite: Zero configuration, perfect for development
- PostgreSQL: Production-grade, supports concurrent connections
- SQLAlchemy abstracts database differences

## Scalability Considerations

### Current Limitations
- Single instance deployment
- SQLite for development (not suitable for high concurrency)

### Future Scalability Options
- PostgreSQL for production
- Redis for caching
- Message queue for async processing
- Horizontal scaling with load balancer
- CDN for static assets

## Monitoring and Logging

### Logging
- Structured logging to files (`logs/`)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Rotating file handlers

### Monitoring
- Health check endpoint: `/health`
- Service status tracking in database
- Task execution history
- Error tracking in logs

## Security Best Practices

1. **Password Security**
   - pbkdf2_sha256 hashing
   - No plain text storage

2. **Token Security**
   - JWT with expiration
   - Refresh token rotation
   - Secure token storage (httpOnly cookies in production)

3. **Credential Encryption**
   - Fernet encryption for sensitive data
   - Key management via environment variables

4. **SQL Injection Prevention**
   - SQLAlchemy ORM (parameterized queries)
   - No raw SQL queries

5. **CORS Protection**
   - Configurable allowed origins
   - Credentials handling

## Development Workflow

1. **Local Development**
   - Backend: `uvicorn server.app.main:app --reload`
   - Frontend: `npm run dev`
   - Database: SQLite (auto-created)

2. **Testing**
   - Unit tests: `pytest tests/`
   - Integration tests: API endpoint testing
   - E2E tests: Playwright (optional)

3. **Docker Development**
   - `docker-compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up`

4. **Production Deployment**
   - `docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d`

## Notification Event Types

**Location:** `services/notification_preference_service.py` - `NotificationEventType` class

### Order Events

- **`ORDER_PLACED`**: Order placed successfully
- **`ORDER_REJECTED`**: Order rejected by broker
- **`ORDER_EXECUTED`**: Order executed/filled
- **`ORDER_CANCELLED`**: Order cancelled
- **`ORDER_MODIFIED`**: Order manually modified (opt-in)
- **`PARTIAL_FILL`**: Order partially filled

### Retry Queue Events

- **`RETRY_QUEUE_ADDED`**: Order added to retry queue
- **`RETRY_QUEUE_UPDATED`**: Retry queue updated
- **`RETRY_QUEUE_REMOVED`**: Order removed from retry queue
- **`RETRY_QUEUE_RETRIED`**: Order retried successfully

### System Events

- **`SYSTEM_ERROR`**: System errors (enabled by default)
- **`SYSTEM_WARNING`**: System warnings (opt-in, disabled by default)
- **`SYSTEM_INFO`**: System information messages (opt-in, disabled by default)

### Legacy Event Types (Backward Compatibility)

- **`SERVICE_EVENT`**: Maps to service-related events
- **`TRADING_EVENT`**: Maps to trading-related events
- **`SYSTEM_EVENT`**: Maps to system events
- **`ERROR`**: Maps to error events

**Usage:**
```python
from services.notification_preference_service import NotificationEventType

# Check if notification should be sent
service = NotificationPreferenceService(db_session)
should_send = service.should_notify(
    user_id=1,
    event_type=NotificationEventType.ORDER_PLACED,
    channel="telegram"
)
```

## Notification Preferences Migration

### Database Migration

**Migration File:** `alembic/versions/53c66ed1105b_add_granular_notification_preferences.py`

**Steps:**
1. Run Alembic migration:
   ```bash
   alembic upgrade head
   ```

2. Verify migration:
   ```bash
   alembic current
   ```

**What Changed:**
- Added 13 new boolean columns to `user_notification_preferences` table
- All new columns default to `TRUE` (except opt-in events: `ORDER_MODIFIED`, `SYSTEM_WARNING`, `SYSTEM_INFO`)
- Existing users automatically get default preferences (backward compatible)

**Rollback:**
```bash
alembic downgrade -1
```

### API Changes

**New Endpoints:**
- `GET /api/v1/user/notification-preferences` - Get user preferences
- `PUT /api/v1/user/notification-preferences` - Update user preferences
- `GET /api/v1/user/notifications` - Get in-app notifications (with filters)
- `PUT /api/v1/user/notifications/{id}/read` - Mark notification as read
- `PUT /api/v1/user/notifications/read-all` - Mark all notifications as read
- `GET /api/v1/user/notifications/unread-count` - Get unread notification count

**Request/Response Schemas:**
- `NotificationPreferencesResponse` - Response model with all preference fields
- `NotificationPreferencesUpdate` - Request model (all fields optional for partial updates)

**Breaking Changes:** None - all changes are additive.

### Code Changes

**New Service:**
- `NotificationPreferenceService` - Centralized preference management

**Updated Components:**
- `TelegramNotifier` - Now checks preferences before sending
- `AutoTradeEngine` - Passes `user_id` to notification methods
- `UnifiedOrderMonitor` - Passes `user_id` to notification methods
- `OrderStateManager` - Passes `user_id` and detects order modifications
- `IndividualServiceManager` - Sends service event notifications (started, stopped, execution completed)
- `MultiUserTradingService` - Sends unified service notifications (started, stopped)
- `EmailNotifier` - New service for sending email notifications
- `NotificationRepository` - Repository for managing in-app notifications

**Backward Compatibility:**
- All notification methods accept optional `user_id` parameter
- If `user_id` is `None`, notifications are sent (legacy behavior)
- Default preferences maintain current behavior (all events enabled)

### Frontend Changes

**New Pages:**
- `/dashboard/notification-preferences` - Notification preferences settings page
- `/dashboard/notifications` - In-app notifications viewer page

**New API Clients:**
- `web/src/api/notification-preferences.ts` - API client for preferences
- `web/src/api/notifications.ts` - API client for in-app notifications

**Navigation:**
- Added "Notifications" link to sidebar navigation (with sub-link "Preferences")
