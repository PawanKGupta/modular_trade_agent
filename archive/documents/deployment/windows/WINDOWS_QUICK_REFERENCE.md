# Windows Quick Reference

Fast commands and steps to install, run, manage as a service, and troubleshoot on Windows.

---

## 1) Install

- Executable (no Python needed)
  1. Extract folder (e.g., `C:\TradingAgent`)
  2. Create `C:\TradingAgent\kotak_neo.env`:
     ```env
     KOTAK_CONSUMER_KEY=your_key
     KOTAK_CONSUMER_SECRET=your_secret
     KOTAK_MOBILE_NUMBER=9876543210
     KOTAK_PASSWORD=your_password
     KOTAK_MPIN=123456
     KOTAK_ENVIRONMENT=prod
     # Optional Telegram
     TELEGRAM_BOT_TOKEN=...
     TELEGRAM_CHAT_ID=...
     ```
  3. Run: `C:\TradingAgent\ModularTradeAgent.exe`

- From source (Python)
  ```powershell
  # In project root
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  python trade_agent.py --backtest
  ```

---

## 2) Service Control (NSSM / sc)

- Install with NSSM (example):
  ```cmd
  nssm install ModularTradeAgent_Main "C:\TradingAgent\ModularTradeAgent.exe"
  nssm set ModularTradeAgent_Main AppDirectory "C:\TradingAgent"
  nssm set ModularTradeAgent_Main Start SERVICE_AUTO_START
  nssm start ModularTradeAgent_Main
  ```

- Start/Stop (sc):
  ```cmd
  sc start ModularTradeAgent_Main
  sc stop  ModularTradeAgent_Main
  sc start ModularTradeAgent_Monitor
  sc stop  ModularTradeAgent_Monitor
  sc start ModularTradeAgent_EOD
  sc stop  ModularTradeAgent_EOD
  sc start ModularTradeAgent_Sell
  sc stop  ModularTradeAgent_Sell
  ```

- Remove services:
  ```cmd
  sc stop ModularTradeAgent_Sell
  sc stop ModularTradeAgent_EOD
  sc stop ModularTradeAgent_Monitor
  sc stop ModularTradeAgent_Main
  sc delete ModularTradeAgent_Sell
  sc delete ModularTradeAgent_EOD
  sc delete ModularTradeAgent_Monitor
  sc delete ModularTradeAgent_Main
  ```

---

## 3) Logs & Data
- Executable console output (run from `cmd` to see errors)
- Installer/Service logs: `C:\ProgramData\ModularTradeAgent\logs\`
- Trade history: `data\trades_history.json` (back up regularly)

---

## 4) Telegram Test
```powershell
.\.venv\Scripts\Activate.ps1   # if running from source
python -c "from core.telegram import send_telegram; send_telegram('Windows test OK')"
```

---

## 5) Common Issues (Quick Fixes)
- App closes immediately: run from `cmd` to see full error
  ```cmd
  cd C:\TradingAgent
  ModularTradeAgent.exe
  ```
- Auth fails: check `kotak_neo.env` values and formats; MPIN must be 6 digits
- Orders not placing: ensure sufficient funds; system retries AMO automatically
- Antivirus flags exe: add to AV exclusions (PyInstaller false positive is common)
- Service won’t start: verify working dir and paths; test exe manually first

---

## 6) Uninstall (Executable Install)
```cmd
:: Stop and delete services (see Service Control)
rmdir /s C:\ProgramData\ModularTradeAgent
```

---

## 7) Handy Commands
```cmd
:: List services matching the agent
sc query | findstr ModularTradeAgent

:: Check last N error lines in logs (PowerShell)
Get-Content C:\ProgramData\ModularTradeAgent\logs\*.log -Tail 50
```
