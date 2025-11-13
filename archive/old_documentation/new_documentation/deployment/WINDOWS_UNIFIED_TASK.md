# Windows Unified Task (Task Scheduler) — Quick Steps

Note: NSSM service is preferred for 24/7. Use Task Scheduler if services are restricted.

Create scheduled task (runs at logon and daily at 9:00)
```powershell
$task = "TradeAgentUnifiedTask"
$cmd  = 'cmd.exe'
$args = '/c cd /d "%CD%" && .\\.venv\\Scripts\\python.exe modules\\kotak_neo_auto_trader\\run_trading_service.py --env modules\\kotak_neo_auto_trader\\kotak_neo.env'
schtasks /Create /TN $task /TR "$cmd $args" /SC ONLOGON /RL HIGHEST /F
schtasks /Create /TN $task-9am /TR "$cmd $args" /SC DAILY /ST 09:00 /RL HIGHEST /F
```

Manage
```powershell
schtasks /Run   /TN TradeAgentUnifiedTask
schtasks /Query /TN TradeAgentUnifiedTask /V /FO LIST
schtasks /Delete /TN TradeAgentUnifiedTask /F
```

Tips
- Ensure the venv and repo paths are correct; commands run in project root via `cd /d`.
- For GUI: set "Start in" to the repo folder and point to `.\\.venv\\Scripts\\python.exe` with parameters.
- Logs remain under `logs/` as configured by the app.
- Prefer NSSM-based service: see new_documentation/deployment/WINDOWS_UNIFIED.md.
