# Windows vs Ubuntu Services Comparison

Complete alignment between Windows and Ubuntu systemd services.

---

## 🎯 Service Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  MODULAR TRADE AGENT                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  STAGE 1: SIGNAL GENERATION                            │ │
│  │  trade_agent.py - Analyzes stocks, sends signals       │ │
│  │  Time: 4:00 PM IST daily                               │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  STAGE 2: AUTOMATED TRADING (Kotak Neo)                │ │
│  │                                                          │ │
│  │  ① Auto Trade - Places buy orders (4:05 PM)            │ │
│  │  ② Sell Orders - Places sell orders (9:15 AM)          │ │
│  │  ③ Position Monitor - Real-time monitoring (every 1min)│ │
│  │  ④ EOD Cleanup - Daily reconciliation (3:35 PM)        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Service Mapping

### Windows (NSSM Services)

| Service Name | Script | Purpose | Schedule |
|--------------|--------|---------|----------|
| `ModularTradeAgent_Main` | `run_auto_trade.py` | Place buy orders | Manual/4:05 PM |
| `ModularTradeAgent_Monitor` | `run_position_monitor.py` | Monitor positions | Every 1 min |
| `ModularTradeAgent_Sell` | `run_sell_orders.py` | Manage sell orders | 9:15 AM |
| `ModularTradeAgent_EOD` | `run_eod_cleanup.py` | Daily cleanup | 3:35 PM |

**Plus**: Signal generation (trade_agent.py) at 4:00 PM

### Ubuntu (Systemd Services)

| Service Name | Script | Purpose | Schedule |
|--------------|--------|---------|----------|
| `tradeagent-analysis.service` | `trade_agent.py` | Analyze & generate signals | 4:00 PM |
| `tradeagent-autotrade.service` | `run_auto_trade.py` | Place buy orders | 9:00 AM & 4:05 PM |
| `tradeagent-monitor.service` | `run_position_monitor.py` | Monitor positions | Every 1 min |
| `tradeagent-sell.service` | `run_sell_orders.py` | Manage sell orders | 9:15 AM |
| `tradeagent-eod.service` | `run_eod_cleanup.py` | Daily cleanup | 3:35 PM |

---

## 📅 Daily Timeline

### Complete Execution Flow

```
9:00 AM  - 🔵 Auto Trade Service (Retry)
           └─ Retries failed orders from previous day
           └─ Handles insufficient balance cases

9:15 AM  - 🟢 Sell Orders Service
           └─ Places limit sell orders for open positions
           └─ Targets: EMA9 levels
           
9:15 AM  - 🔵 Position Monitor Starts (Every 1 min)
to       - └─ Monitors all open positions
3:30 PM  - └─ Sends alerts for exit signals
           └─ Checks for averaging opportunities
           
3:30 PM  - Market closes

3:35 PM  - 🟡 EOD Cleanup Service
           └─ Reconciles positions
           └─ Updates trade history
           └─ Sends daily summary

4:00 PM  - 🟢 Trade Analysis Service
           └─ Scrapes stock list
           └─ Analyzes stocks
           └─ Generates BUY signals
           └─ Sends Telegram alerts

4:05 PM  - 🔵 Auto Trade Service
           └─ Reads analysis results
           └─ Places AMO buy orders
           └─ Updates trade history
```

---

## 🔧 Installation Commands

### Ubuntu

```bash
# Option 1: Multiple Services (5 separate systemd services)
chmod +x setup_ubuntu.sh
sudo ./setup_ubuntu.sh

# Option 2: Unified Service (1 persistent service - Recommended)
# Create manual unit as per INSTALL_UBUNTU.md (tradeagent-unified.service)
```

### Windows

```bash
# Run installer executable
ModularTradeAgent_Installer.exe
# Or
python installer/setup.py
```

---

## 📋 Service Details

### 1. Trade Analysis Service
**Purpose**: Generate trading signals  
**Windows**: Not a separate service (run manually or via Task Scheduler)  
**Ubuntu**: `tradeagent-analysis.service`  
**Schedule**: Daily at 4:00 PM IST (Mon-Fri)  
**Output**: Telegram message with BUY candidates

### 2. Auto Trade Service
**Purpose**: Place buy orders based on signals + retry failed orders  
**Windows**: `ModularTradeAgent_Main`  
**Ubuntu**: `tradeagent-autotrade.service`  
**Schedule**: 
- Daily at 9:00 AM IST (retry orders that failed due to insufficient balance)
- Daily at 4:05 PM IST (place new AMO orders after analysis)  
**Requires**: Kotak Neo credentials in `kotak_neo.env`

### 3. Position Monitor Service
**Purpose**: Real-time position monitoring during market hours  
**Windows**: `ModularTradeAgent_Monitor`  
**Ubuntu**: `tradeagent-monitor.service`  
**Schedule**: Every 1 minutes (9:15 AM - 3:30 PM)  
**Actions**:
- Checks exit conditions (RSI, EMA)
- Sends Telegram alerts
- Identifies averaging opportunities

### 4. Sell Orders Service
**Purpose**: Place and manage profit-taking sell orders  
**Windows**: `ModularTradeAgent_Sell`  
**Ubuntu**: `tradeagent-sell.service`  
**Schedule**: Daily at 9:15 AM IST (market open)  
**Strategy**: EMA9 target tracking with dynamic updates

### 5. EOD Cleanup Service
**Purpose**: Daily reconciliation and summaries  
**Windows**: `ModularTradeAgent_EOD`  
**Ubuntu**: `tradeagent-eod.service`  
**Schedule**: Daily at 3:35 PM IST (after market close)  
**Actions**:
- Reconcile positions with broker
- Update trade history
- Send daily summary to Telegram

---

## 🛠️ Management Commands

### Ubuntu Commands

#### View Services
```bash
# View all services
systemctl list-timers tradeagent-*

# View specific service status
systemctl status tradeagent-analysis.timer
systemctl status tradeagent-autotrade.timer
systemctl status tradeagent-monitor.timer
systemctl status tradeagent-sell.timer
systemctl status tradeagent-eod.timer

# View unified service
systemctl status tradeagent-unified.service
```

#### View Logs
```bash
journalctl -u tradeagent-analysis.service -f
journalctl -u tradeagent-autotrade.service -f
journalctl -u tradeagent-monitor.service -f
journalctl -u tradeagent-sell.service -f
journalctl -u tradeagent-eod.service -f

# Unified service logs
journalctl -u tradeagent-unified.service -f
```

#### Manual Execution
```bash
sudo systemctl start tradeagent-analysis.service
sudo systemctl start tradeagent-autotrade.service
sudo systemctl start tradeagent-monitor.service
sudo systemctl start tradeagent-sell.service
sudo systemctl start tradeagent-eod.service

# Restart unified service
sudo systemctl restart tradeagent-unified.service
```

#### Stop/Disable Services
```bash
# Stop all timers (multiple services)
sudo systemctl stop tradeagent-*.timer

# Stop unified service
sudo systemctl stop tradeagent-unified.service

# Disable services (prevent auto-start)
sudo systemctl disable tradeagent-analysis.timer
sudo systemctl disable tradeagent-unified.service
```

#### Complete Uninstall
```bash
# For unified service
sudo systemctl stop tradeagent-unified.service
sudo systemctl disable tradeagent-unified.service
sudo rm /etc/systemd/system/tradeagent-unified.service
sudo systemctl daemon-reload

# For multiple services (if installed by setup_ubuntu.sh)
sudo systemctl stop 'tradeagent-*.timer'
sudo systemctl disable 'tradeagent-*.timer'
sudo rm /etc/systemd/system/tradeagent-*.service /etc/systemd/system/tradeagent-*.timer
sudo systemctl daemon-reload
```

### Windows Commands

```cmd
REM View all services
sc query | findstr "ModularTradeAgent"

REM Start/Stop individual services
net start ModularTradeAgent_Main
net start ModularTradeAgent_Monitor
net start ModularTradeAgent_Sell
net start ModularTradeAgent_EOD

net stop ModularTradeAgent_Main
net stop ModularTradeAgent_Monitor
net stop ModularTradeAgent_Sell
net stop ModularTradeAgent_EOD

REM Or use batch files
START_ALL_SERVICES.bat
STOP_ALL_SERVICES.bat
```

---

## ⚙️ Configuration Requirements

### Both Platforms Need:

1. **Telegram Credentials** (`cred.env` or `kotak_neo.env`):
   ```env
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

2. **Kotak Neo Credentials** (for automated trading - `kotak_neo.env`):
   ```env
   KOTAK_NEO_CONSUMER_KEY=your_key
   KOTAK_NEO_CONSUMER_SECRET=your_secret
   KOTAK_NEO_MOBILE_NUMBER=9876543210
   KOTAK_NEO_PASSWORD=your_password
   KOTAK_NEO_MPIN=123456
   ```

---

## 🎯 Use Cases

### Multiple Services Approach
- **Purpose**: Separate control over each trading task
- **Services**: 5 independent systemd services
- **Setup**: `sudo ./setup_ubuntu.sh`
- **Best for**: 
  - Granular control over each task
  - Debugging individual components
  - Custom scheduling needs

### Unified Service Approach (Recommended)
- **Purpose**: Single persistent trading session
- **Services**: 1 unified service handling all tasks
- **Setup**: Create systemd unit as per INSTALL_UBUNTU.md (tradeagent-unified.service)
- **Best for**:
  - Production deployment
  - Better resource management
  - No JWT expiry issues
  - Matches Windows implementation

---

## 📊 Verification

### Check Services Status

**Ubuntu:**
```bash
# Check timers/services (if using multi-service setup)
systemctl list-timers tradeagent-*
systemctl list-units tradeagent-* --all

# Or unified service
systemctl status tradeagent-unified.service
```

**Windows:**
```cmd
sc query | findstr "ModularTradeAgent"

REM Or use Services GUI
services.msc
```

---

## ⚠️ Important Notes

1. **Analysis service** is independent and always runs (generates signals)
2. **Trading services** (Auto Trade, Monitor, Sell, EOD) require:
   - Kotak Neo modules in `modules/kotak_neo_auto_trader/`
   - Valid Kotak Neo credentials
   - Active broker connection

3. **Service dependencies**:
   - Auto Trade depends on Analysis (runs 5 min after)
   - All services are independent otherwise

4. **Test before live**: Always test services manually before automation

---

## 🔄 Migration Path

### From Windows to Ubuntu

1. **Backup** Windows data:
   ```cmd
   backup_data.bat
   ```

2. **Transfer** to Ubuntu:
   ```bash
   scp -r C:\Personal\Projects\TradingView\modular_trade_agent user@ubuntu-server:/home/user/
   ```

3. **Install** on Ubuntu:
   ```bash
   cd ~/modular_trade_agent
   ./setup_ubuntu.sh
   sudo ./setup_complete_services_ubuntu.sh
   ```

4. **Copy** configuration files:
   ```bash
   # Copy credentials
   cp /path/to/backup/kotak_neo.env ~/modular_trade_agent/
   cp /path/to/backup/cred.env ~/modular_trade_agent/
   
   # Copy trade history
   cp /path/to/backup/data/trades_history.json ~/modular_trade_agent/data/
   ```

5. **Verify**:
   ```bash
   ./verify_installation.sh
   systemctl list-timers tradeagent-*
   ```

---

**Summary**: Both Windows and Ubuntu now have identical functionality with properly aligned services! 🎉
