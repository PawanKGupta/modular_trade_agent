# Complete Features Documentation

Complete documentation of all features in Rebound — Modular Trade Agent system.

## 📊 Core Features

### 1. Trading Signals (Buying Zone)

**Purpose:** Automated stock screening and signal generation based on mean reversion to EMA9 strategy.

**Key Features:**
- **Signal Generation:** Automatically identifies oversold dips (RSI10 < 30) in stocks above EMA200
- **Multi-Factor Analysis:**
  - Technical indicators (RSI, EMA9, EMA200)
  - Chart quality assessment
  - Backtest scoring (2-year historical validation)
  - ML-enhanced verdicts
  - Volume analysis
  - Fundamental screening (PE, PB ratios)
- **Signal Management:**
  - View active, rejected, and historical signals
  - Approve/reject signals
  - Customizable column display
  - Date filtering
  - Status filtering
- **T2T Segment Filtering:**
  - Automatically filters out Trade-to-Trade segment stocks (-BE, -BL, -BZ)
  - These stocks have same-day selling restrictions and are excluded from trading
  - Filtering happens at signal generation stage (hard filter)
  - Uses scrip master for robust symbol resolution
- **Analysis Deduplication:**
  - Prevents duplicate signals within the same trading day window
  - Trading day window: 9AM to next day 9AM (excluding weekends)
  - Automatic duplicate detection and prevention

**UI Location:** `/dashboard/buying-zone`

**Data Fields:**
- Symbol, Status
- RSI10, EMA9, EMA200
- Distance to EMA9
- Clean chart indicator
- Monthly support distance
- Confidence scores
- Backtest scores
- Combined scores
- ML verdict and confidence
- Buy range, Target, Stop loss
- Volume ratios
- Fundamental data (PE, PB)

### 2. Order Management

**Purpose:** Monitor and manage trading orders (buy/sell).

**Key Features:**
- **Order Tracking:**
  - View all orders (buy/sell)
  - Filter by status (open, filled, cancelled, rejected)
  - Real-time status updates
  - Order history
- **Order Details:**
  - Symbol, quantity, price
  - Order type (MARKET, LIMIT)
  - Transaction type (BUY, SELL)
  - Exchange, product, variety
  - Status and timestamps
  - Execution details
  - Order ID and broker order ID
- **T2T Segment Handling:**
  - T2T stocks automatically use LIMIT orders (not MARKET)
  - Limit price set at current price + 1% buffer
  - Prevents order rejections due to same-day selling restrictions

**UI Location:** `/dashboard/orders`

**API Endpoints:**
- `GET /api/v1/user/orders/` - List orders (paginated)
- `POST /api/v1/user/orders/{id}/retry` - Retry a failed order
- `DELETE /api/v1/user/orders/{id}` - Drop a failed order from retry queue
- `POST /api/v1/user/orders/sync` - Manually sync order status from broker

### 3. Target Management

**Purpose:** Manage target prices and stop losses for positions.

**Key Features:**
- **Target Tracking:**
  - View all active targets
  - Set custom targets
  - Automatic target calculation (EMA9)
  - Stop loss management

**UI Location:** `/dashboard/targets`

### 4. P&L Tracking

**Purpose:** Comprehensive profit and loss tracking.

**Key Features:**
- Real-time P&L calculation
- Position-wise P&L
- Overall portfolio P&L
- Historical P&L trends

**UI Location:** `/dashboard/pnl`

### 5. Paper Trading

**Purpose:** Risk-free strategy testing with realistic simulation.

**Key Features:**
- Virtual portfolio management
- Realistic order execution
- Fee calculation (brokerage, STT, GST)
- Slippage simulation
- Complete P&L tracking
- Per-user paper trading portfolios
- Integration with unified trading service
- Paper trading service adapter for individual services
- Web UI access for portfolio and history

See [Paper Trading Complete Guide](PAPER_TRADING_COMPLETE.md) for complete documentation.

### 6. Service Management

**Purpose:** Manage automated trading services.

**Key Features:**
- **Unified Service:** Single service per user running all trading tasks automatically
- **Individual Services:** Run specific tasks independently:
  - `analysis` - Stock analysis and signal generation
  - `buy_orders` - Place buy orders for approved signals
  - `premarket_retry` - Retry failed orders from previous day
  - `sell_monitor` - Monitor positions and execute sell orders at targets
  - `eod_cleanup` - End-of-day cleanup tasks
- **Service Control:** Start/stop services via web UI
- **Conflict Detection:** Prevents conflicts between unified and individual services
- **Status Tracking:** Real-time service status monitoring
- **Task History:** View execution history and logs

**UI Location:** `/dashboard/service`

### 7. Trading Configuration

**Purpose:** Configure trading strategy parameters.

**Key Features:**
- RSI thresholds
- EMA parameters
- Volume requirements
- Chart quality settings
- ML model configuration

**UI Location:** `/dashboard/settings`

See [Trading Configuration Guide](TRADING_CONFIG.md) for details.

### 8. Logging System

**Purpose:** Comprehensive logging with database and file handlers.

**Key Features:**
- **Database Logging:**
  - Async queue-based logging to prevent transaction conflicts
  - Batch processing for efficient writes
  - User-scoped log isolation
  - Automatic log retention
- **File Logging:**
  - Per-user log files organized by date
  - Separate service and error logs
  - Docker-compatible log rotation
  - Automatic rotation handling in Docker environments
- **Error Capture:**
  - Automatic exception logging
  - Context preservation
  - User state tracking
- **Log Retention:**
  - Automatic cleanup of old logs
  - Configurable retention period
  - Separate retention for service logs and error logs

**Technical Details:**
- Activity logs use JSONL file format (one file per user per day)
- Error logs stored in database (ErrorLog table)
- File-based logging eliminates SQLite lock contention
- `FileLogReader` provides efficient log reading and filtering
- `LogRetentionService` manages automatic cleanup of old files and error logs

### 9. Notification System

**Purpose:** Multi-channel notification system with granular preferences.

**Key Features:**
- **Notification Channels:**
  - Telegram notifications (with bot integration)
  - Email notifications (SMTP-based)
  - In-app notifications (web UI)
- **Granular Event Preferences:**
  - Order events (placed, executed, rejected, cancelled, modified, partial fill)
  - Retry queue events (added, updated, removed, retried)
  - System events (errors, warnings, info)
  - Service events (started, stopped, execution completed)
- **Notification Preferences:**
  - Per-event enable/disable
  - Quiet hours support
  - Channel-specific preferences
  - Default preferences for new users
- **Rate Limiting:**
  - Telegram: 10 notifications/minute, 100/hour
  - Automatic throttling to prevent spam

**UI Location:** `/dashboard/notification-preferences` and `/dashboard/notifications`

**Technical Details:**
- `NotificationPreferenceService` manages preferences with caching
- `TelegramNotifier` checks preferences before sending
- `EmailNotifier` supports SMTP configuration
- In-app notifications stored in database with read/unread status

## 🔐 Security Features

### Authentication
- JWT-based authentication
- Refresh token support
- Secure password hashing (pbkdf2_sha256)

### Credential Management
- Encrypted broker credentials in database
- Encrypted Telegram credentials
- Per-user credential isolation

### Access Control
- Role-based access (Admin/User)
- User-scoped data isolation
- API endpoint protection

## 📈 ML Features

### Model Training
- Automated model training
- Retraining capabilities
- Model versioning
- Automatic retraining triggered by events (`MLRetrainingService`)

### Prediction
- ML-enhanced verdicts
- Confidence scoring
- Feature engineering
- Two-stage approach (chart quality filter + ML prediction)

### Monitoring & Feedback
- ML prediction logging (`MLLoggingService`)
- Performance metrics tracking
- Model drift detection
- Feedback collection (`MLFeedbackService`)
- Agreement/disagreement tracking with rule-based system

See [ML Integration Guide](../architecture/ML_COMPLETE_GUIDE.md) for details.

## 🔄 Recent Updates

### T2T Segment Filtering (2025-12-14)
- Added hard filter at signal generation stage
- Automatically excludes -BE, -BL, -BZ stocks
- Uses scrip master for robust symbol resolution
- Prevents same-day selling issues

### Async Database Logging (2025-12-14)
- Implemented async queue-based logging
- Prevents SQLAlchemy transaction conflicts
- Batch processing for performance
- Graceful shutdown handling

### Docker Log Rotation Fix (2025-12-14)
- Automatic Docker environment detection
- Disables rotation if not possible
- Prevents permission errors
- Continuous logging to current file
