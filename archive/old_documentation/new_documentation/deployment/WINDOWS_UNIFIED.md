# Windows Unified Service — Quick Steps

Recommended production deployment for continuous operation.

Prerequisites
- Python 3.12+, project venv, credentials (`modules/kotak_neo_auto_trader/kotak_neo.env`)

Install (NSSM)
```powershell
$svc = "TradeAgentUnified"
nssm install $svc ".\.venv\Scripts\python.exe"
nssm set $svc AppDirectory "$PWD"
nssm set $svc AppParameters "modules\kotak_neo_auto_trader\run_trading_service.py --env modules\kotak_neo_auto_trader\kotak_neo.env"
nssm set $svc Start SERVICE_AUTO_START
nssm start $svc
```

Manage
```powershell
sc query TradeAgentUnified
sc start TradeAgentUnified
sc stop  TradeAgentUnified
```

More details
- Full guide: documents/deployment/windows/WINDOWS_UNIFIED_SERVICE.md
- Multi‑service (advanced): documents/deployment/windows/WINDOWS_SERVICES_GUIDE.md
