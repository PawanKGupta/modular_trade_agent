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
