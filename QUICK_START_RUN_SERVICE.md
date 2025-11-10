# How to Run the Unified Trading Service

The `run_trading_service.py` is a **unified service** that runs ALL trading tasks automatically with a single persistent session. You don't need to run individual services separately anymore.

## 📋 What It Does

The unified service automatically runs these tasks on trading days (Mon-Fri):

- **9:00 AM** - Pre-market retry (retry failed orders from previous day)
- **9:15 AM - 3:30 PM** - Sell monitoring (continuous, monitors sell orders every minute)
- **9:30 AM, 10:30 AM, 11:30 AM...** - Position monitoring (hourly)
- **4:00 PM** - Market analysis (runs trade_agent.py --backtest)
- **4:05 PM** - Place buy orders (AMO orders for next day)
- **6:00 PM** - End-of-day cleanup (resets for next day)

## 🚀 Quick Start (Windows)

### Option 1: Run Directly (Testing/Development)

```powershell
# From project root directory
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service.py
```

Or with custom env file:
```powershell
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service.py --env path\to\your\kotak_neo.env
```

### Option 2: Run as Windows Service (Production)

Using NSSM (Non-Sucking Service Manager):

```powershell
# From project root directory
$svc = "TradeAgentUnified"

# Install service
nssm install $svc ".\.venv\Scripts\python.exe"
nssm set $svc AppDirectory "$PWD"
nssm set $svc AppParameters "modules\kotak_neo_auto_trader\run_trading_service.py --env modules\kotak_neo_auto_trader\kotak_neo.env"
nssm set $svc Start SERVICE_AUTO_START

# Start service
nssm start $svc

# Check status
sc query TradeAgentUnified

# Stop service
sc stop TradeAgentUnified
```

### Option 3: Run in Background (Using PowerShell)

```powershell
# Start in background
Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "modules\kotak_neo_auto_trader\run_trading_service.py" `
    -WorkingDirectory "$PWD" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "logs\service_output.log" `
    -RedirectStandardError "logs\service_error.log"
```

## 🔍 Verify It's Running

Check the logs:
```powershell
# View recent logs
Get-Content logs\trade_agent_*.log -Tail 50
```

You should see:
```
TRADING SERVICE INITIALIZATION
Authentication successful - session active for the day
TRADING SERVICE STARTED (CONTINUOUS MODE)
Service will run continuously 24/7
Tasks execute automatically on trading days (Mon-Fri)
```

## ⏹️ Stop the Service

### If running directly:
Press `Ctrl+C` in the terminal

### If running as Windows service:
```powershell
sc stop TradeAgentUnified
```

### If running in background:
```powershell
# Find the process
Get-Process python | Where-Object {$_.Path -like "*\.venv*"}

# Stop it
Stop-Process -Name python -Force
```

## 📝 Prerequisites

1. **Credentials file** must exist:
   ```
   modules/kotak_neo_auto_trader/kotak_neo.env
   ```

2. **Virtual environment** activated (if running directly):
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. **Dependencies installed**:
   ```powershell
   pip install -r requirements.txt
   ```

## 🎯 Key Features

✅ **Single Login**: Logs in once at startup, maintains session all day  
✅ **Automatic Re-auth**: Handles JWT expiry automatically (with your fixes!)  
✅ **All Tasks**: Runs all scheduled tasks automatically  
✅ **Thread-Safe**: Handles concurrent operations safely  
✅ **Graceful Shutdown**: Cleans up properly on exit  

## 🔧 Troubleshooting

### Service won't start?
- Check logs: `logs\trade_agent_*.log`
- Verify credentials file exists and is valid
- Check virtual environment is set up correctly

### Tasks not running?
- Verify current time is during trading hours (Mon-Fri, 9:00 AM - 6:00 PM IST)
- Check logs for error messages
- Verify internet connection

### Authentication issues?
- Check credentials in `kotak_neo.env`
- Verify MPIN is correct
- Check logs for authentication errors

## 📚 Additional Resources

- Full documentation: `documents/architecture/UNIFIED_TRADING_SERVICE.md`
- Windows deployment: `documents/deployment/windows/WINDOWS_UNIFIED_SERVICE.md`
- Ubuntu deployment: `documents/deployment/ubuntu/INSTALL_UBUNTU.md`





