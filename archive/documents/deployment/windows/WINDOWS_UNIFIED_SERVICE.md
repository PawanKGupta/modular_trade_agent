# Windows Unified Service Guide

Run the unified trading service (single persistent session) as a Windows service using NSSM.

---

## Overview
- Service runs modules/kotak_neo_auto_trader/run_trading_service.py continuously
- Single login at startup; handles all scheduled tasks all day
- Logs go to project logs/ and optional NSSM stdout/stderr files

---

## Prerequisites
1) From project root, ensure credentials exist:
```env
modules/kotak_neo_auto_trader/kotak_neo.env
```
2) Create/verify venv (source install):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## Install Service (NSSM)
1) Download NSSM: https://nssm.cc/download (place nssm.exe in PATH)
2) Run these in PowerShell from the project root:
```powershell
# Service name
$svc = "TradeAgentUnified"

# Create service to run unified scheduler
nssm install $svc ".\ .venv\Scripts\python.exe"  # (no space after .\)
# AppDirectory = project root
nssm set $svc AppDirectory "$PWD"
# Arguments (script + env file)
nssm set $svc AppParameters "modules\kotak_neo_auto_trader\run_trading_service.py --env modules\kotak_neo_auto_trader\kotak_neo.env"
# Auto-start on boot
nssm set $svc Start SERVICE_AUTO_START
# Optional: redirect stdout/stderr to rotating files
$logDir = "C:\ProgramData\ModularTradeAgent\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
nssm set $svc AppStdout "$logDir\unified_service.log"
nssm set $svc AppStderr "$logDir\unified_service_error.log"
nssm set $svc AppRotateFiles 1
nssm set $svc AppRotateOnline 1
nssm set $svc AppRotateBytes 10485760  # 10 MB

# Start service
nssm start $svc
```

Note: Always use .\.venv\Scripts\python.exe for this project.

---

## Manage Service
```powershell
# Start/Stop/Restart
sc start  TradeAgentUnified
sc stop   TradeAgentUnified
sc query  TradeAgentUnified

# Auto-start already set; to set manually:
# nssm set TradeAgentUnified Start SERVICE_AUTO_START

# Delete service (cleanup)
sc stop TradeAgentUnified
sc delete TradeAgentUnified
```

---

## Validation
- Status: `sc query TradeAgentUnified | findstr STATE`
- App logs: `logs\trade_agent_YYYYMMDD.log`
- NSSM logs (if enabled): `C:\ProgramData\ModularTradeAgent\logs\unified_service*.log`
- Confirm Telegram alerts at task times

---

## Troubleshooting
- Service won’t start:
  - Run the command manually to see errors:
    ```powershell
    .\.venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service.py --env modules\kotak_neo_auto_trader\kotak_neo.env
    ```
  - Verify `modules/kotak_neo_auto_trader/kotak_neo.env` exists and is correct
  - Ensure working directory (AppDirectory) is the project root
- No logs:
  - Check `logs\` folder and NSSM stdout/stderr files
- Credentials/2FA errors:
  - Recheck env file values; MPIN must be 6 digits

---

## Notes
- Unified service replaces multiple scheduled tasks with one long-running process
- To update code: stop service, pull changes, ensure venv packages, start service
