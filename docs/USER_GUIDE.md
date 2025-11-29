# User Guide

Complete guide to using the Modular Trade Agent web interface.

## Getting Started

### First Login

1. Navigate to http://localhost:5173 (or your deployment URL)
2. Click **Sign Up** to create an account, or use admin credentials if provided
3. After login, you'll see the dashboard

### Initial Setup

1. **Configure Broker Credentials** (Settings → Broker)
   - Enter your Kotak Neo API credentials
   - Credentials are encrypted and stored securely
   - Required for live trading

2. **Configure Trading Parameters** (Trading Config)
   - Adjust RSI period, EMA periods, capital allocation
   - Set risk management parameters
   - Save your configuration

3. **Test with Paper Trading** (Paper Trading)
   - Enable paper trading mode
   - Set initial capital
   - Monitor simulated trades before going live

## Dashboard Pages

### Buying Zone

**Purpose:** View and manage trading signals

**Features:**
- View all active signals
- Filter by date and status
- Customize visible columns
- Approve/reject signals
- View detailed signal information:
  - RSI, EMA9, EMA200 values
  - Distance to EMA9
  - Backtest scores
  - ML verdicts and confidence
  - Buy range, target, stop loss

**Actions:**
- **Reject Signal:** Click reject button to mark signal as rejected
- **Column Customization:** Click column selector to show/hide columns
- **Date Filter:** Select date range to view historical signals

### Orders

**Purpose:** Monitor order execution and status

**Features:**
- View all orders (buy/sell)
- Filter by status (open, filled, cancelled)
- View order details:
  - Symbol, quantity, price
  - Order type, transaction type
  - Status and timestamps
  - Execution details

**Actions:**
- **Refresh:** Auto-refreshes to show latest status
- **Filter:** Use status filter to view specific order types

### Targets

**Purpose:** Manage target prices and stop losses

**Features:**
- View all active targets
- Monitor target progress
- View target details:
  - Entry price
  - Target price (EMA9)
  - Stop loss
  - Current P&L

### P&L (Profit & Loss)

**Purpose:** Track trading performance

**Features:**
- View overall P&L summary
- View P&L by position
- Historical P&L trends
- Performance metrics

### Paper Trading

**Purpose:** Test strategies without real money

**Features:**
- **Portfolio:** View current holdings
- **History:** View all paper trades
- **Execute Trades:** Manually execute paper trades
- **Settings:** Configure initial capital and parameters

**Usage:**
1. Enable paper trading mode
2. Set initial capital
3. Monitor simulated trades
4. Review performance before going live

### Service Status

**Purpose:** Monitor automated trading services

**Features:**
- View service status (running/stopped)
- View recent task executions
- View service logs
- Start/stop services
- View task history

**Services:**
- Pre-market analysis
- Order monitoring
- Target management
- End-of-day tasks

### Trading Config

**Purpose:** Configure trading strategy parameters

**Features:**
- **RSI Settings:**
  - RSI period (default: 10)
  - RSI oversold threshold (default: 30)

- **EMA Settings:**
  - EMA9 period (default: 9)
  - EMA200 period (default: 200)

- **Volume Settings:**
  - Minimum volume multiplier
  - Volume quality thresholds

- **Capital Management:**
  - User capital
  - Maximum position size
  - Risk management parameters

**Usage:**
1. Adjust parameters as needed
2. Click **Save** to apply changes
3. Changes take effect immediately

### Settings

**Purpose:** Configure system settings

**Sections:**

#### Broker Credentials
- Consumer Key
- Consumer Secret
- Access Token
- User ID

**Note:** Credentials are encrypted before storage.

#### Telegram Settings (Optional)
- Bot Token
- Chat ID
- Enable/disable notifications

### Admin Pages (Admin Only)

#### Users
- View all users
- Manage user roles
- Activate/deactivate users

#### ML Training
- View ML training status
- Start/stop training jobs
- View training history
- Monitor model performance

#### Logs
- View system logs
- Filter by log level
- Search logs
- Export logs

#### Service Schedule
- Configure service schedules
- Enable/disable tasks
- Set execution times

## Common Workflows

### Daily Trading Workflow

1. **Morning:**
   - Check **Service Status** - ensure services are running
   - Review **Buying Zone** for new signals
   - Approve/reject signals as needed

2. **During Market Hours:**
   - Monitor **Orders** for execution
   - Check **Targets** for progress
   - Review **P&L** for performance

3. **End of Day:**
   - Review **P&L** summary
   - Check **Service Status** for task completion
   - Review **Logs** for any errors

### Testing Strategy Workflow

1. **Enable Paper Trading:**
   - Go to **Paper Trading**
   - Set initial capital
   - Enable paper trading mode

2. **Configure Strategy:**
   - Go to **Trading Config**
   - Adjust parameters
   - Save configuration

3. **Monitor Performance:**
   - Review paper trading results
   - Analyze P&L
   - Adjust parameters as needed

4. **Go Live:**
   - Configure broker credentials
   - Disable paper trading
   - Start live trading

### Signal Review Workflow

1. **View Signals:**
   - Go to **Buying Zone**
   - Review all active signals

2. **Analyze Signals:**
   - Check RSI, EMA values
   - Review backtest scores
   - Check ML confidence

3. **Make Decision:**
   - Approve promising signals
   - Reject weak signals
   - Monitor approved signals

## Tips and Best Practices

### Signal Analysis
- **High Backtest Score:** Signals with >60 backtest score are more reliable
- **ML Confidence:** ML confidence >0.7 indicates strong signal
- **Distance to EMA9:** Closer distance (<5%) means faster target achievement
- **Volume:** Higher volume ratio indicates stronger participation

### Risk Management
- Start with paper trading
- Use conservative capital allocation initially
- Monitor P&L regularly
- Adjust parameters based on performance

### Service Management
- Keep services running for automated trading
- Monitor service logs for errors
- Review task execution history regularly
- Ensure broker credentials are valid

### Troubleshooting

**Signals Not Appearing:**
- Check service status (should be running)
- Review logs for errors
- Verify trading configuration

**Orders Not Executing:**
- Verify broker credentials
- Check order status
- Review service logs

**P&L Not Updating:**
- Wait for end-of-day processing
- Check service status
- Review logs for errors

## Keyboard Shortcuts

- `Ctrl+K` / `Cmd+K`: Quick search (if implemented)
- `Esc`: Close modals/dialogs
- `Enter`: Submit forms

## Getting Help

- Check **Logs** page for error details
- Review **Service Status** for service issues
- Check documentation for detailed guides
- Review API documentation for programmatic access
