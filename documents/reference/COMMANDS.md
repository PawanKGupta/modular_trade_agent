# Trading Bot - Command Reference

Complete guide to all available commands and scripts for managing the automated trading system.

---

## Table of Contents
- [Initial Setup](#initial-setup)
- [Task Management](#task-management)
- [Manual Trading Operations](#manual-trading-operations)
- [Analysis & Backtesting](#analysis--backtesting)
- [Monitoring & Logs](#monitoring--logs)
- [Windows Task Scheduler](#windows-task-scheduler)

---

## Initial Setup

### 1. Create Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Configure Environment
Create and configure the environment file:
```powershell
notepad modules\kotak_neo_auto_trader\kotak_neo.env
```

Required variables:
- `CONSUMER_KEY`
- `CONSUMER_SECRET`
- `MOBILE_NUMBER`
- `PASSWORD`
- `MPIN`

### 4. Setup Scheduled Tasks (Run as Administrator)
```powershell
# Option 1: Open PowerShell as Administrator, then run:
.\setup_scheduled_tasks.ps1

# Option 2: From current PowerShell (will prompt for admin):
Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PWD\setup_scheduled_tasks.ps1`""
```

Alternative setup script:
```powershell
.\create_tasks.ps1
```

---

## Task Management

### Check Task Status
```powershell
.\manage_tasks.ps1 status
```
Shows current state, next run time, and last execution result for all tasks.

### Enable All Tasks
```powershell
.\manage_tasks.ps1 enable
```
Enables all scheduled tasks and displays their status.

### Disable All Tasks
```powershell
.\manage_tasks.ps1 disable
```
Disables all scheduled tasks (useful when going on vacation or testing).

### Test Analysis Task
```powershell
.\manage_tasks.ps1 test
```
Manually runs the analysis task and monitors its execution.

### View Recent Logs
```powershell
.\manage_tasks.ps1 logs
```
Displays the last 50 log entries.

### Remove All Tasks
```powershell
.\manage_tasks.ps1 remove
```
Permanently removes all scheduled tasks (requires confirmation).

### Help
```powershell
.\manage_tasks.ps1 help
```
Displays usage information.

---

## Manual Trading Operations

### Run Analysis with Backtest
```powershell
python trade_agent.py --backtest
```
Analyzes stocks and generates scored recommendations based on historical performance.

---

## Kotak Neo Auto Trader Commands

**📚 Full documentation:** [`features/KOTAK_NEO_COMMANDS.md`](features/KOTAK_NEO_COMMANDS.md)

### Place Buy Orders (AMO)
```powershell
# Auto-detect latest CSV
python -m modules.kotak_neo_auto_trader.run_place_amo

# Specify CSV file
python -m modules.kotak_neo_auto_trader.run_place_amo --csv analysis_results\bulk_analysis_final_*.csv

# Custom env file
python -m modules.kotak_neo_auto_trader.run_place_amo --env path\to\kotak_neo.env

# Logout after completion
python -m modules.kotak_neo_auto_trader.run_place_amo --logout
```
Places After Market Orders (AMO) for buying stocks at 4 PM based on analysis results.

**Key features:**
- Pre-flight checks (portfolio cap, holdings, balance)
- Automatic duplicate order cancellation
- NSE/BSE tick size rounding
- Telegram notifications

### Sell Order Management
```powershell
# Standard run (wait for market open, then monitor)
python -m modules.kotak_neo_auto_trader.run_sell_orders

# Place once and exit (no monitoring)
python -m modules.kotak_neo_auto_trader.run_sell_orders --run-once

# Custom monitoring interval
python -m modules.kotak_neo_auto_trader.run_sell_orders --monitor-interval 30

# Skip waiting for market open (testing)
python -m modules.kotak_neo_auto_trader.run_sell_orders --skip-wait
```
Automated sell order management with EMA9 profit targets.

**Execution:**
- **9:15 AM:** Places sell orders at EMA9
- **9:15 AM - 3:30 PM:** Monitors and updates orders every minute
- **Auto-updates:** Modifies orders when lower EMA9 detected
- **Auto-closes:** Marks positions as closed when orders execute

### Position Monitoring
```powershell
# Standard monitoring (market hours only)
python -m modules.kotak_neo_auto_trader.run_position_monitor

# Custom history file
python -m modules.kotak_neo_auto_trader.run_position_monitor --history data\trades_history.json

# Disable Telegram alerts
python -m modules.kotak_neo_auto_trader.run_position_monitor --no-alerts

# Force run outside market hours
python -m modules.kotak_neo_auto_trader.run_position_monitor --force
```
Real-time position monitoring with exit signals and averaging opportunities.

**Alerts:**
- ⚠️ Exit imminent (RSI > 50 or price < EMA9)
- 🔄 Averaging opportunity (RSI < 30)
- 📊 Position health status

### End-of-Day Cleanup
```powershell
# Standard EOD cleanup
python -m modules.kotak_neo_auto_trader.run_eod_cleanup

# Custom env file
python -m modules.kotak_neo_auto_trader.run_eod_cleanup --env path\to\kotak_neo.env
```
Daily reconciliation and reporting at market close (3:35 PM).

**Tasks:**
1. Portfolio reconciliation
2. Order status verification
3. Trade history update
4. Daily report generation
5. Telegram summary
6. Data backup

### Complete Daily Workflow
```powershell
# 4:00 PM - Analysis & Buy Orders
python trade_agent.py --backtest
python -m modules.kotak_neo_auto_trader.run_place_amo

# 9:15 AM - Sell Orders (runs until 3:30 PM)
python -m modules.kotak_neo_auto_trader.run_sell_orders

# 10:00 AM - 3:00 PM - Position Monitoring (hourly)
python -m modules.kotak_neo_auto_trader.run_position_monitor

# 3:35 PM - End-of-Day Cleanup
python -m modules.kotak_neo_auto_trader.run_eod_cleanup
```

---

## Analysis & Backtesting

### Basic Analysis (No Backtest)
```powershell
python trade_agent.py
```
Runs analysis without backtesting (faster, but no historical scoring).

### Analysis with Custom Date Range
```powershell
python trade_agent.py --backtest --start-date 2024-01-01 --end-date 2024-12-31
```

### View Analysis Results
```powershell
# View latest CSV results
Get-ChildItem analysis_results\bulk_analysis_final_*.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content

# Open in Excel
$latest = Get-ChildItem analysis_results\bulk_analysis_final_*.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Start-Process $latest.FullName
```

---

## Monitoring & Logs

### View Live Logs
```powershell
Get-Content logs\trade_agent.log -Wait -Tail 50
```
Monitors log file in real-time (press Ctrl+C to stop).

### View Last N Log Lines
```powershell
Get-Content logs\trade_agent.log -Tail 100
```

### Search Logs
```powershell
# Search for errors
Select-String -Path logs\trade_agent.log -Pattern "ERROR" -Context 2,2

# Search for specific stock
Select-String -Path logs\trade_agent.log -Pattern "RELIANCE"

# Search in date range
Get-Content logs\trade_agent.log | Select-String -Pattern "2024-10-27"
```

### Monitor System Resources
```powershell
# Check if service is running
Get-Process python*

# View unified service status
Get-ScheduledTask -TaskName "TradingService-Unified" | Get-ScheduledTaskInfo
```

---

## Unified Trading Service Control

### Service Management
```powershell
# Start the unified service
Start-ScheduledTask -TaskName "TradingService-Unified"

# Stop the running service
Stop-ScheduledTask -TaskName "TradingService-Unified"

# Check service status
Get-ScheduledTask -TaskName "TradingService-Unified" | Select-Object State

# View detailed service info
Get-ScheduledTask -TaskName "TradingService-Unified" | Get-ScheduledTaskInfo | Format-List
```

### Service Configuration
```powershell
# Set infinite timeout (continuous operation)
$task = Get-ScheduledTask -TaskName "TradingService-Unified"
$task.Settings.ExecutionTimeLimit = "PT0S"
Set-ScheduledTask -InputObject $task

# Enable auto-restart on failure
$task.Settings.RestartCount = 3
$task.Settings.RestartInterval = "PT5M"
Set-ScheduledTask -InputObject $task
```

### Manual Service Control
```powershell
# Run service manually (for testing)
.\.\.venv\Scripts\python.exe -m modules.kotak_neo_auto_trader.run_trading_service --env modules/kotak_neo_auto_trader/kotak_neo.env

# Kill stuck service process
Get-Process python | Where-Object {$_.Modules.FileName -like "*run_trading_service*"} | Stop-Process
```

---

## Service Schedule (Continuous 24/7)

### Automatic Tasks

| Time | Task | Description |
|------|------|-------------|
| **At Startup** | Service Start | Login once, runs continuously |
| **Mon-Fri 9:00 AM** | Pre-Market Retry | Retry failed orders from previous day |
| **Mon-Fri 9:15 AM** | Sell Orders | Place limit sell orders at EMA9 targets |
| **Mon-Fri 9:15-3:30 PM** | Sell Monitoring | Update orders every minute |
| **Mon-Fri 9:30+ AM (hourly)** | Position Monitor | Check for reentry/exit signals |
| **Mon-Fri 4:00 PM** | Market Analysis | Run trade_agent.py --backtest |
| **Mon-Fri 4:05 PM** | Buy Orders | Place AMO buy orders for next day |
| **Mon-Fri 6:00 PM** | EOD Cleanup | Cleanup + reset for next day |
| **Sat-Sun** | Idle | Service runs but no tasks execute |

### Task Settings
- **Run whether user is logged on or not**: No (Interactive)
- **Run with highest privileges**: Yes
- **Allow task to be run on demand**: Yes
- **Start when available**: Yes
- **Restart on failure**: 3 times (5-minute intervals)
- **Battery**: Run even on battery power

---

## Troubleshooting Commands

### Check Python Environment
```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\pip list | Select-String "yfinance|pandas|python-dotenv"
```

### Verify Environment File
```powershell
Test-Path modules\kotak_neo_auto_trader\kotak_neo.env
```

### Check Task Execution History
```powershell
Get-WinEvent -FilterHashtable @{
    LogName='Microsoft-Windows-TaskScheduler/Operational'
    ID=201  # Task completed successfully
} -MaxEvents 10 | Format-Table TimeCreated, Message -AutoSize
```

### View Failed Task Executions
```powershell
Get-WinEvent -FilterHashtable @{
    LogName='Microsoft-Windows-TaskScheduler/Operational'
    ID=203  # Task failed
} -MaxEvents 10 | Format-Table TimeCreated, Message -AutoSize
```

### Clear Old Log Files
```powershell
# Archive logs older than 30 days
Get-ChildItem logs\*.log | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} | Compress-Archive -DestinationPath logs\archive.zip -Update
Get-ChildItem logs\*.log | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} | Remove-Item
```

---

## Quick Reference

### Daily Operations
```powershell
# Morning routine (before market opens)
.\manage_tasks.ps1 status                    # Check task status
Get-Content logs\trade_agent.log -Tail 20    # Review recent logs

# End of day (after 4:00 PM)
Get-Content logs\trade_agent.log -Tail 50    # Check analysis results
# Review analysis CSV in analysis_results folder
```

### Emergency Commands
```powershell
# Stop trading service immediately
Stop-ScheduledTask -TaskName "TradingService-Unified"
Get-Process python* | Stop-Process

# Disable service (prevent auto-restart)
Disable-ScheduledTask -TaskName "TradingService-Unified"

# Re-enable after issue resolved
Enable-ScheduledTask -TaskName "TradingService-Unified"
```

### Testing & Development
```powershell
# Test analysis without affecting live system
python trade_agent.py --backtest

# Test with specific parameters
python -m modules.kotak_neo_auto_trader.run_place_amo --help

# Check service definition
Get-ScheduledTask -TaskName "TradingService-Unified" | Select-Object -ExpandProperty Actions
```

---

## Notes

- **Always run PowerShell scripts from the project root directory**
- **Task creation requires Administrator privileges**
- **Keep your computer running during scheduled task times**
- **Monitor logs regularly for errors or issues**
- **Test changes in non-market hours before enabling automation**

---

## Support

For issues or questions:
1. Check logs: `.\manage_tasks.ps1 logs`
2. Review task status: `.\manage_tasks.ps1 status`
3. View this documentation: `Get-Content COMMANDS.md`
