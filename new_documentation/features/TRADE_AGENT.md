# Trade Agent — Details and Commands

What it does
- Analyzes NSE stocks using core RSI/EMA logic and filters
- Optional 2-year backtest scoring for higher‑quality signals
- Sends prioritized Telegram alerts

Prerequisites
- Python 3.12+
- Configure `cred.env` (Telegram) and `modules/kotak_neo_auto_trader/kotak_neo.env` (for trading modules)

Run commands
- Windows
```powershell
.\.venv\Scripts\python.exe trade_agent.py --backtest
```
- Ubuntu/macOS
```bash
.venv/bin/python trade_agent.py --backtest
```

Common options
```powershell
# Standard analysis
.\.venv\Scripts\python.exe trade_agent.py
# Faster (no CSV, single timeframe)
.\.venv\Scripts\python.exe trade_agent.py --no-csv --no-mtf
# Dip-buying mode
.\.venv\Scripts\python.exe trade_agent.py --dip-mode
```

Tips
- Logs: `logs/trade_agent_YYYYMMDD.log`
- Telegram test (Windows):
```powershell
.\.venv\Scripts\python.exe -c "from core.telegram import send_telegram; send_telegram('Trade Agent test OK')"
```
