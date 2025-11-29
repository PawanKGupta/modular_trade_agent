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

### Notification Preferences

**Purpose:** Control which notifications you receive and how

**Location:** Dashboard → Notifications (or `/dashboard/notification-preferences`)

**Features:**

#### Notification Channels
Choose how you want to receive notifications:

- **In-App Notifications**: Show notifications in the web interface (enabled by default)
- **Telegram**: Receive notifications via Telegram bot
  - Enable the toggle
  - Enter your Telegram Chat ID (required when enabled)
- **Email**: Receive notifications via email
  - Enable the toggle
  - Enter your email address (required when enabled)

#### Order Events
Control notifications for order-related events:

- **Order Placed**: Notify when an order is placed (enabled by default)
- **Order Executed**: Notify when an order is executed (enabled by default)
- **Order Rejected**: Notify when an order is rejected (enabled by default)
- **Order Cancelled**: Notify when an order is cancelled (enabled by default)
- **Order Modified (Manual)**: Notify when an order is manually modified (opt-in, disabled by default)
- **Partial Fill**: Notify when an order is partially filled (enabled by default)

**Quick Actions:**
- Click **Enable All** to enable all order event notifications
- Click **Disable All** to disable all order event notifications

#### Retry Queue Events
Control notifications for retry queue operations:

- **Order Added to Retry Queue**: Notify when an order is added to retry queue (enabled by default)
- **Retry Queue Updated**: Notify when retry queue is updated (enabled by default)
- **Order Removed from Retry Queue**: Notify when an order is removed from retry queue (enabled by default)
- **Order Retried Successfully**: Notify when an order is retried successfully (enabled by default)

**Quick Actions:**
- Click **Enable All** to enable all retry queue notifications
- Click **Disable All** to disable all retry queue notifications

#### System Events
Control notifications for system-level events:

- **System Errors**: Notify on system errors (enabled by default)
- **System Warnings**: Notify on system warnings (opt-in, disabled by default)
- **System Info**: Notify on system information messages (opt-in, disabled by default)

**Quick Actions:**
- Click **Enable All** to enable all system event notifications
- Click **Disable All** to disable all system event notifications

#### Quiet Hours
Set a time range when notifications will be suppressed:

1. **Set Start Time**: Choose when quiet hours begin (e.g., 22:00 for 10 PM)
2. **Set End Time**: Choose when quiet hours end (e.g., 08:00 for 8 AM)
3. **Clear**: Click "Clear" to disable quiet hours

**Example:** Set quiet hours from 22:00 to 08:00 to suppress notifications during nighttime.

**Note:** Quiet hours can span midnight (e.g., 22:00 - 08:00 means 10 PM to 8 AM).

**Usage:**
1. Navigate to **Notifications** page
2. Configure your preferences
3. Click **Save Preferences** to apply changes
4. Changes take effect immediately

**Tips:**
- Start with default settings and adjust based on your needs
- Use quiet hours to avoid notifications during sleep or meetings
- Disable notifications you don't need to reduce noise
- Enable "Order Modified" only if you manually modify orders and want to track changes

### Viewing Notifications

**Purpose:** View and manage in-app notifications

**Location:** Dashboard → Notifications (or `/dashboard/notifications`)

**Features:**

#### Notification List
View all your in-app notifications with:
- **Type Filter**: Filter by `service`, `trading`, `system`, or `error`
- **Level Filter**: Filter by `info`, `warning`, `error`, or `critical`
- **Read Status**: Filter by read/unread notifications
- **Pagination**: View up to 500 notifications at a time

#### Notification Details
Each notification shows:
- **Title**: Brief summary of the event
- **Message**: Detailed information about the event
- **Type**: Category of the notification
- **Level**: Severity level (info, warning, error, critical)
- **Read Status**: Whether you've read the notification
- **Delivery Status**: Whether notification was sent via Telegram/Email
- **Timestamp**: When the notification was created

#### Actions
- **Mark as Read**: Click on a notification to mark it as read
- **Mark All as Read**: Use the "Mark All as Read" button to clear all unread notifications
- **Filter**: Use the dropdown filters to find specific notifications
- **Unread Count**: See the number of unread notifications in the header

#### Service Event Notifications
Service events include:
- **Service Started**: When a trading service (analysis, order placement, etc.) starts
- **Service Stopped**: When a trading service stops
- **Service Execution Completed**: When a service task completes (success or failure)

**Usage:**
1. Navigate to **Notifications** page
2. Use filters to find specific notifications
3. Click on a notification to mark it as read
4. Use "Mark All as Read" to clear all unread notifications

**Tips:**
- Check notifications regularly to stay informed about system events
- Use filters to focus on specific types of notifications
- Service execution notifications help track task completion and failures

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
