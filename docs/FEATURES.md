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

**UI Location:** `/dashboard/orders`

**API Endpoints:**
- `GET /api/v1/user/orders` - List orders
- `GET /api/v1/user/orders/{order_id}` - Get order details

### 3. Target Management

**Purpose:** Manage target prices and stop losses for positions.

**Key Features:**
- **Target Tracking:**
  - View all active targets
  - Monitor target progress
  - Track entry vs current price
- **Target Details:**
  - Entry price
  - Target price (EMA9)
  - Stop loss
  - Current price
  - Current P&L
  - Distance to target
  - Distance to stop

**UI Location:** `/dashboard/targets`

**API Endpoints:**
- `GET /api/v1/user/targets` - List targets
- `GET /api/v1/user/targets/{target_id}` - Get target details

### 4. Profit & Loss (P&L) Tracking

**Purpose:** Track trading performance and profitability.

**Key Features:**
- **P&L Summary:**
  - Overall P&L
  - Realized P&L
  - Unrealized P&L
  - Total trades
  - Win rate
- **P&L by Position:**
  - Individual position P&L
  - Entry vs current price
  - Percentage gains/losses
- **Historical P&L:**
  - Date range filtering
  - Performance trends
  - Monthly/yearly summaries

**UI Location:** `/dashboard/pnl`

**API Endpoints:**
- `GET /api/v1/user/pnl/summary` - Get P&L summary
- `GET /api/v1/user/pnl/history` - Get P&L history

### 5. Paper Trading

**Purpose:** Test trading strategies without real money.

**Key Features:**
- **Virtual Portfolio:**
  - Start with configurable capital (default: ₹1,00,000)
  - Realistic market simulation
  - Brokerage and fees calculation
  - Slippage simulation
- **Paper Trading Operations:**
  - Execute paper trades
  - View portfolio holdings
  - Track paper trading P&L
  - View trade history
- **Features:**
  - Drop-in replacement for real broker
  - Realistic execution simulation
  - Complete P&L tracking
  - Persistent state (JSON files)

**UI Location:** `/dashboard/paper-trading`

**API Endpoints:**
- `POST /api/v1/user/paper-trading/execute` - Execute paper trade
- `GET /api/v1/user/paper-trading/portfolio` - Get portfolio
- `GET /api/v1/user/paper-trading/history` - Get trade history

### 6. Trading Configuration

**Purpose:** Configure all trading strategy parameters.

**Key Features:**

#### Strategy Configuration
- **RSI Settings:**
  - RSI period (default: 10)
  - RSI oversold threshold (default: 30)
  - RSI extreme oversold (default: 10)
  - RSI near oversold (default: 35)

#### Capital & Position Management
- **Capital Settings:**
  - User capital (default: ₹2,00,000)
  - Paper trading initial capital (default: ₹10,00,000)
  - Max portfolio size
  - Max position volume ratio (default: 10%)
  - Min absolute average volume

#### Chart Quality Filters
- Chart quality enabled/disabled
- Chart quality minimum score
- Max gap frequency
- Min daily range percentage
- Max extreme candle frequency

#### Risk Management
- **Stop Loss Settings:**
  - Default stop loss percentage
  - Tight stop loss percentage
  - Minimum stop loss percentage
- **Target Settings:**
  - Default target percentage
  - Strong buy target percentage
  - Excellent target percentage
- **Risk-Reward Ratios:**
  - Strong buy risk-reward
  - Buy risk-reward
  - Excellent risk-reward

#### Order Defaults
- Default exchange (NSE)
- Default product (MIS, CNC, NRML)
- Default order type (MARKET, LIMIT)
- Default variety (REGULAR, AMO)
- Default validity (DAY, IOC)

#### Behavior Toggles
- Allow duplicate recommendations same day
- Exit on EMA9 or RSI50
- Minimum combined score
- Enable premarket AMO adjustment

#### News Sentiment
- News sentiment enabled/disabled
- Lookback days (default: 30)
- Minimum articles
- Positive threshold
- Negative threshold

#### ML Configuration
- ML enabled/disabled
- ML model version
- ML confidence threshold
- ML combine with rules

**UI Location:** `/dashboard/config`

**API Endpoints:**
- `GET /api/v1/user/trading-config` - Get configuration
- `PUT /api/v1/user/trading-config` - Update configuration
- `POST /api/v1/user/trading-config/reset` - Reset to defaults

**Presets:**
- Conservative
- Moderate
- Aggressive
- Custom

### 7. Service Management

**Purpose:** Monitor and control automated trading services.

**Key Features:**
- **Service Status:**
  - View service running status
  - Start/stop service
  - View service uptime
  - View last heartbeat
- **Task Management:**
  - View scheduled tasks
  - View task execution history
  - View task status (success, failed, running)
  - View task execution times
- **Individual Services:**
  - Run individual tasks independently
  - View individual service status
  - Conflict detection
  - Schedule management
- **Service Logs:**
  - View recent service logs
  - Filter by log level
  - Real-time log updates
  - Error tracking

**UI Location:** `/dashboard/service`

**API Endpoints:**
- `GET /api/v1/user/service/status` - Get service status
- `POST /api/v1/user/service/start` - Start service
- `POST /api/v1/user/service/stop` - Stop service
- `GET /api/v1/user/service/tasks` - Get task history
- `GET /api/v1/user/service/logs` - Get service logs
- `POST /api/v1/user/service/run/{task_name}` - Run individual task

**Scheduled Tasks:**
- Pre-market analysis
- Order monitoring
- Target management
- End-of-day tasks
- Signal generation
- ML training (scheduled)

### 8. Service Scheduling (Admin)

**Purpose:** Configure service schedules and execution times (Admin only).

**Key Features:**
- **Schedule Configuration:**
  - Enable/disable tasks
  - Set execution times
  - Configure task schedules
  - View schedule status
- **Task Management:**
  - Manage all scheduled tasks
  - Configure task parameters
  - View task dependencies

**UI Location:** `/dashboard/admin/schedules`

**API Endpoints:**
- `GET /api/v1/admin/schedules` - Get schedules
- `PUT /api/v1/admin/schedules/{task_name}` - Update schedule

### 9. Settings

**Purpose:** Configure system settings (broker credentials, Telegram).

**Key Features:**
- **Broker Credentials:**
  - Consumer Key
  - Consumer Secret
  - Access Token
  - User ID
  - Credentials encrypted and stored securely
- **Telegram Settings:**
  - Bot Token
  - Chat ID
  - Enable/disable notifications

**UI Location:** `/dashboard/settings`

**API Endpoints:**
- `GET /api/v1/user/broker/credentials` - Get broker credentials
- `PUT /api/v1/user/broker/credentials` - Update broker credentials

### 10. Log Viewer

**Purpose:** View and manage system logs.

**Key Features:**
- **Log Viewing:**
  - View system logs
  - Filter by log level (DEBUG, INFO, WARNING, ERROR)
  - Search logs
  - Date range filtering
- **Error Tracking:**
  - View error logs
  - Error resolution workflow
  - Error statistics
- **User/Admin Scopes:**
  - User logs (own logs)
  - Admin logs (all users)

**UI Location:** `/dashboard/logs`

**API Endpoints:**
- `GET /api/v1/logs` - Get logs
- `GET /api/v1/admin/logs` - Get all logs (admin)

### 11. ML Training (Admin)

**Purpose:** Manage ML model training and retraining (Admin only).

**Key Features:**
- **Training Management:**
  - Start/stop training jobs
  - View training status
  - View training history
  - Monitor training progress
- **Model Management:**
  - View available models
  - Select model version
  - View model performance
  - Model comparison
- **Training Configuration:**
  - Model version selection
  - Force retrain option
  - Training parameters

**UI Location:** `/dashboard/admin/ml`

**API Endpoints:**
- `GET /api/v1/admin/ml/training` - Get training status
- `POST /api/v1/admin/ml/train` - Start training
- `GET /api/v1/admin/ml/models` - Get models

### 12. User Management (Admin)

**Purpose:** Manage users and roles (Admin only).

**Key Features:**
- **User Management:**
  - View all users
  - Create users
  - Activate/deactivate users
  - Change user roles
- **Role Management:**
  - Admin role
  - User role
  - Role-based permissions

**UI Location:** `/dashboard/admin/users`

**API Endpoints:**
- `GET /api/v1/admin/users` - List users
- `POST /api/v1/admin/users` - Create user
- `PUT /api/v1/admin/users/{user_id}` - Update user
- `DELETE /api/v1/admin/users/{user_id}` - Delete user

### 13. Activity Tracking

**Purpose:** Track user activity and system events.

**Key Features:**
- **Activity Log:**
  - View user activity
  - Filter by activity type
  - Date range filtering
  - Activity details
- **Event Tracking:**
  - Order placements
  - Configuration changes
  - Service starts/stops
  - Signal approvals/rejections

**UI Location:** `/dashboard/activity`

**API Endpoints:**
- `GET /api/v1/user/activity` - Get activity log

## 🔐 Authentication & Security

### Authentication Features
- **User Registration:**
  - Email-based signup
  - Password requirements
  - Automatic user creation
- **Login:**
  - Email/password authentication
  - JWT token generation
  - Refresh token support
- **Token Management:**
  - Access tokens (short-lived)
  - Refresh tokens (long-lived)
  - Automatic token refresh
  - Secure token storage

**UI Locations:**
- `/login` - Login page
- `/signup` - Signup page

**API Endpoints:**
- `POST /api/v1/auth/signup` - User registration
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh token
- `GET /api/v1/auth/me` - Get current user

### Security Features
- **Password Security:**
  - pbkdf2_sha256 hashing
  - No plain text storage
- **Credential Encryption:**
  - Fernet encryption (AES-128)
  - Encrypted broker credentials
  - Encrypted Telegram credentials
- **Role-Based Access:**
  - Admin and User roles
  - Role-based API access
  - UI route protection

## 📱 UI Features

### Dashboard Home
- Overview of key metrics
- Quick access to main features
- Recent activity summary

### Navigation
- Sidebar navigation
- Route protection
- Role-based menu items
- Responsive design

### Real-Time Updates
- Auto-refresh for service status
- Real-time order updates
- Live log streaming
- Task execution monitoring

### Data Visualization
- Tables with sorting and filtering
- Column customization
- Date range filters
- Status filters
- Pagination

## 🔄 Integration Features

### Broker Integration
- **Kotak Neo API:**
  - Order placement
  - Order status tracking
  - Holdings retrieval
  - Position management
  - Real-time price updates

### Telegram Integration
- **Notifications:**
  - Trade alerts
  - Order confirmations
  - Service status updates
  - Error notifications

## 📈 Analytics & Reporting

### Performance Metrics
- Win rate calculation
- Average returns
- Risk-reward ratios
- Drawdown analysis
- Sharpe ratio (if implemented)

### Reporting
- P&L reports
- Trade history
- Performance summaries
- Export capabilities (future)

## 🛠️ System Features

### Database
- **SQLite (Development):**
  - Zero configuration
  - File-based storage
- **PostgreSQL (Production):**
  - Production-grade
  - Concurrent connections
  - Advanced features

### Logging
- Structured logging
- Log levels (DEBUG, INFO, WARNING, ERROR)
- File rotation
- Log retention policies

### Error Handling
- Comprehensive error handling
- Error logging
- User-friendly error messages
- Error tracking

## 🚀 Deployment Features

### Docker Support
- Complete containerization
- Multi-service orchestration
- Environment configuration
- Easy deployment

### Health Checks
- Health check endpoint
- Service status monitoring
- Database connectivity checks

## 📝 Future Features (Planned)

- WebSocket support for real-time updates
- Advanced analytics dashboard
- Export/import configurations
- Multi-broker support
- Mobile app (future)
- Advanced charting
- Strategy backtesting UI
