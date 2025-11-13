# Test Trading Service - Quick Reference

Test script that allows running trading tasks outside market hours and on holidays.

## Usage

### Run All Tasks (Default)
```powershell
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py
```

### Run Specific Task
```powershell
# Pre-market retry
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --task premarket_retry

# Sell monitor
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --task sell_monitor

# Position monitor
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --task position_monitor

# Market analysis
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --task analysis

# Buy orders
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --task buy_orders

# EOD cleanup
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --task eod_cleanup
```

### Options

```powershell
# Use custom env file
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --env path\to\your\kotak_neo.env

# Skip initialization (use existing session)
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --skip-init

# Respect actual time/day (don't force trading day)
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --no-force-trading-day
```

## Features

✅ **Bypasses time checks**: Runs tasks at any time of day  
✅ **Bypasses day checks**: Runs on weekends/holidays  
✅ **Individual task testing**: Test specific tasks  
✅ **All tasks testing**: Run all tasks sequentially  
✅ **Full initialization**: Uses same initialization as production  

## Examples

### Test Pre-market Retry on Weekend
```powershell
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --task premarket_retry
```

### Test Sell Monitor at Night
```powershell
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --task sell_monitor
```

### Test All Tasks on Holiday
```powershell
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\test_trading_service.py --task all
```

## What It Does

1. **Overrides time checks**: `is_trading_day()` and `is_market_hours()` return `True`
2. **Overrides task scheduling**: `should_run_task()` returns `True` for any task
3. **Runs tasks**: Executes the actual task methods from `TradingService`
4. **Provides feedback**: Shows success/failure for each task

## Notes

- Uses same initialization as production service
- Connects to real API (uses your credentials)
- Can place real orders (be careful!)
- Logs all activity to standard logs


