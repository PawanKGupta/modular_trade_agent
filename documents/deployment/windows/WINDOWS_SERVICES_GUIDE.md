# Windows Services Guide

## Overview

The installer creates **4 separate Windows services**, each handling a specific aspect of automated trading. This modular approach allows you to:
- Run only the services you need
- Start/stop services independently
- Monitor each component separately
- Scale resources per service

## Services Created

### 1. ModularTradeAgent_Main
**Script**: `run_auto_trade.py`  
**Description**: Main Auto Trading Engine - Places orders and manages positions

**What it does**:
- Loads buy/sell recommendations from analysis CSV
- Places AMO (After Market Orders) for new entries
- Retries failed orders due to insufficient balance
- Evaluates exit conditions (RSI > 50 or Price >= EMA9)
- Manages position re-entries at RSI 20 and RSI 10 levels
- Reconciles holdings with trade history

**When to run**:
- Daily at 8:00 AM (before market open for AMO orders)
- During market hours for regular orders
- Can run continuously for real-time order management

**Log file**: `logs/ModularTradeAgent_Main.log`

---

### 2. ModularTradeAgent_Monitor
**Script**: `run_position_monitor.py`  
**Description**: Position Monitor - Real-time monitoring and alerts

**What it does**:
- Monitors all open positions every hour (configurable)
- Checks position health (P&L, RSI, EMA distance)
- Detects exit condition proximity (near EMA9 or RSI 50)
- Identifies averaging opportunities (RSI < 20 or < 10)
- Sends Telegram alerts for critical situations
- Tracks unrealized profit/loss

**When to run**:
- During market hours (9:15 AM - 3:30 PM)
- Can run continuously for real-time monitoring

**Log file**: `logs/ModularTradeAgent_Monitor.log`

---

### 3. ModularTradeAgent_EOD
**Script**: `run_eod_cleanup.py`  
**Description**: End-of-Day Cleanup - Reconciliation and daily summary

**What it does**:
- Final order status verification (pending → executed/rejected)
- Manual trade reconciliation (detects manual buys/sells)
- Cleanup stale pending orders
- Generate daily statistics and summaries
- Send Telegram daily summary
- Archive completed tracking entries

**When to run**:
- Daily at 6:00 PM (after market close)
- Or manually after trading day

**Log file**: `logs/ModularTradeAgent_EOD.log`

---

### 4. ModularTradeAgent_Sell
**Script**: `run_sell_orders.py`  
**Description**: Sell Order Manager - EMA9 target tracking and execution

**What it does**:
- Places limit sell orders at daily EMA9 price
- Monitors and updates orders every minute with lowest EMA9
- Tracks order execution
- Updates trade history when orders execute
- Handles partial fills and quantity mismatches

**When to run**:
- During market hours (9:15 AM - 3:30 PM)
- Continuous monitoring for EMA9 updates

**Log file**: `logs/ModularTradeAgent_Sell.log`

---

## Service Control (NSSM / sc)

### Start All Services
```cmd
sc start ModularTradeAgent_Main
sc start ModularTradeAgent_Monitor
sc start ModularTradeAgent_EOD
sc start ModularTradeAgent_Sell
```

### Stop All Services
```cmd
sc stop ModularTradeAgent_Sell
sc stop ModularTradeAgent_EOD
sc stop ModularTradeAgent_Monitor
sc stop ModularTradeAgent_Main
```

### Individual Service Control
```cmd
:: Main Trading Engine
sc start ModularTradeAgent_Main
sc stop ModularTradeAgent_Main

:: Position Monitor
sc start ModularTradeAgent_Monitor
sc stop ModularTradeAgent_Monitor

:: EOD Cleanup
sc start ModularTradeAgent_EOD
sc stop ModularTradeAgent_EOD

:: Sell Order Manager
sc start ModularTradeAgent_Sell
sc stop ModularTradeAgent_Sell
```

Note: If you installed services with NSSM, you can also use:
```cmd
nssm start ModularTradeAgent_Main
nssm stop ModularTradeAgent_Main
```

## Recommended Usage Patterns

### Pattern 1: Full Automation
Run all services continuously:
```cmd
:: Start everything
sc start ModularTradeAgent_Main
sc start ModularTradeAgent_Monitor
sc start ModularTradeAgent_EOD
sc start ModularTradeAgent_Sell

:: Services run 24/7
:: Main: Places orders when needed
:: Monitor: Alerts you during market hours
:: EOD: Runs cleanup at 6 PM daily
:: Sell: Manages sell orders during market hours
```

### Pattern 2: Manual Control
Run only specific services as needed:
```cmd
:: Morning: Place AMO orders
sc start ModularTradeAgent_Main
:: ... wait for completion ...
sc stop ModularTradeAgent_Main

:: During market: Monitor positions
sc start ModularTradeAgent_Monitor

:: Evening: Daily cleanup
sc start ModularTradeAgent_EOD
```

### Pattern 3: Hybrid
Some services automated, some manual:
```cmd
:: Automated: Monitor and sell management
sc start ModularTradeAgent_Monitor
sc start ModularTradeAgent_Sell

:: Manual: You control when to trade
:: Manually start/stop ModularTradeAgent_Main when desired

:: Automated: Daily cleanup
:: Schedule or manually start at 6 PM
sc start ModularTradeAgent_EOD
```

## Service Configuration

### Startup Type
All services installed with: **Manual Start** (SERVICE_DEMAND_START)

To change to automatic startup:
```cmd
# Using NSSM
nssm set ModularTradeAgent_Main Start SERVICE_AUTO_START

# Or via Windows Services (services.msc)
# Right-click service → Properties → Startup type: Automatic
```

### Service Account
Default: **SYSTEM** account

To run as specific user:
```cmd
# Using NSSM
nssm set ModularTradeAgent_Main ObjectName DOMAIN\Username Password
```

## Windows Task Scheduler Alternative

If you prefer Task Scheduler over services:

### Main Trader (Daily 8 AM)
```
Trigger: Daily at 8:00 AM
Action: Run RUN_AGENT.bat
Conditions: Run only on weekdays
```

### Position Monitor (Market Hours)
```
Trigger: Daily at 9:15 AM
Action: Start service ModularTradeAgent_Monitor
Conditions: Stop at 3:30 PM
```

### EOD Cleanup (Daily 6 PM)
```
Trigger: Daily at 6:00 PM
Action: Start service ModularTradeAgent_EOD
Conditions: Run only on weekdays
```

## Monitoring Services

### Check Status
```cmd
# Using net command
net start | findstr ModularTradeAgent

# Using sc command
sc query ModularTradeAgent_Main
sc query ModularTradeAgent_Monitor
sc query ModularTradeAgent_EOD
sc query ModularTradeAgent_Sell
```

### View Logs
Logs are in: `C:\ProgramData\ModularTradeAgent\logs\`

```
ModularTradeAgent_Main.log         # Main trader output
ModularTradeAgent_Main_error.log   # Main trader errors
ModularTradeAgent_Monitor.log      # Monitor output
ModularTradeAgent_Monitor_error.log # Monitor errors
... (similar for EOD and Sell)
```

### Windows Event Viewer
Service start/stop events logged in:
- **Application and Services Logs** → **Windows Logs** → **System**
- Filter by source: "Service Control Manager"

## Service Dependencies

```
ModularTradeAgent_Main
  ├── No dependencies
  └── Core trading engine

ModularTradeAgent_Monitor
  ├── Reads from: trades_history.json
  └── Depends on: Main having created positions

ModularTradeAgent_EOD
  ├── Reads from: trades_history.json
  ├── Reads from: pending_orders.json
  └── Should run AFTER market hours

ModularTradeAgent_Sell
  ├── Reads from: trades_history.json
  └── Requires: Open positions to sell
```

## Troubleshooting

### Service Won't Start

**Error**: Service fails to start
- **Check**: Credentials in `kotak_neo.env` are correct
- **Check**: Python executable path is valid
- **Check**: Script exists at specified path
- **View**: Error log in `logs/` folder

### Service Crashes

**Error**: Service stops unexpectedly
- **Check**: Error logs in `logs/ModularTradeAgent_*.error.log`
- **Check**: Windows Event Viewer for crash details
- **Test**: Run script manually to see error:
  ```cmd
  cd C:\ProgramData\ModularTradeAgent\TradingAgent
  python modules\kotak_neo_auto_trader\run_auto_trade.py
  ```

### Multiple Services Conflict

**Issue**: Services interfere with each other
- **Solution**: Services are designed to work together
- **Check**: All use same `kotak_neo.env` file
- **Ensure**: Only one instance of each service runs

### High CPU/Memory Usage

**Issue**: Service consuming too many resources
- **Check**: Service running continuously when not needed
- **Solution**: Stop service when market is closed
- **Configure**: Reduce monitoring frequency in scripts

## Uninstalling Services

### Remove All Services
```cmd
# Using NSSM
nssm remove ModularTradeAgent_Main confirm
nssm remove ModularTradeAgent_Monitor confirm
nssm remove ModularTradeAgent_EOD confirm
nssm remove ModularTradeAgent_Sell confirm

# Or using sc
sc delete ModularTradeAgent_Main
sc delete ModularTradeAgent_Monitor
sc delete ModularTradeAgent_EOD
sc delete ModularTradeAgent_Sell
```

### Remove Installation
```cmd
:: Stop all services first
sc stop ModularTradeAgent_Sell
sc stop ModularTradeAgent_EOD
sc stop ModularTradeAgent_Monitor
sc stop ModularTradeAgent_Main

:: Uninstall services (use either NSSM or sc)
:: With NSSM:
nssm remove ModularTradeAgent_Main confirm
nssm remove ModularTradeAgent_Monitor confirm
nssm remove ModularTradeAgent_EOD confirm
nssm remove ModularTradeAgent_Sell confirm

:: Or with sc:
sc delete ModularTradeAgent_Main
sc delete ModularTradeAgent_Monitor
sc delete ModularTradeAgent_EOD
sc delete ModularTradeAgent_Sell

:: Delete installation directory (if created by installer)
rmdir /s C:\ProgramData\ModularTradeAgent
```

## Best Practices

### 1. Start with One Service
- Begin with **ModularTradeAgent_Main** only
- Verify it works correctly
- Add other services gradually

### 2. Monitor Logs
- Check logs daily during initial setup
- Verify services are behaving as expected
- Set up log rotation for long-term usage

### 3. Test Before Production
- Run services manually first (RUN_AGENT.bat)
- Verify with small positions
- Monitor for several days before full automation

### 4. Backup Configuration
- Keep backup of `kotak_neo.env`
- Export service configurations (NSSM)
- Document any customizations

### 5. Resource Management
- Don't run unnecessary services
- Stop services when market is closed
- Monitor system resources

## Service Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  Windows Services                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ModularTradeAgent_Main     (Core trading logic)        │
│      ↓                                                   │
│  trades_history.json ←────────────────┐                 │
│      ↓                                 │                 │
│  ┌──────────────┐  ┌────────────────┐ │                │
│  │   Monitor    │  │  Sell Orders   │ │                │
│  │   Service    │  │    Service     │ │                │
│  └──────────────┘  └────────────────┘ │                │
│      ↓                                 │                 │
│  Telegram Alerts                       │                │
│                                        │                 │
│  ModularTradeAgent_EOD                 │                │
│      └────────────────────────────────┘                 │
│         (Reconciliation & Cleanup)                       │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Summary

**4 Services Installed**:
1. ✅ **Main** - Auto trading engine
2. ✅ **Monitor** - Position monitoring & alerts
3. ✅ **EOD** - End-of-day cleanup
4. ✅ **Sell** - Sell order management

**Control**:
- Start/Stop all: `sc start/stop ModularTradeAgent_*`
- Individual control: `sc start ModularTradeAgent_Main`, `sc stop ModularTradeAgent_Main`, etc.

**Logs**: `C:\ProgramData\ModularTradeAgent\logs\`

**Perfect for modular, scalable trading automation!** 🚀
