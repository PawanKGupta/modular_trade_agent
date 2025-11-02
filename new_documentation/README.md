# Modular Trade Agent — Quick Start (New Documentation)

This simplified guide focuses on the most-used features and the recommended unified deployments.

Version: 25.4.1
Python: 3.12+

---

## Features at a glance
- Trade Agent (daily analysis with optional backtest scoring; Telegram alerts)
- Backtesting (strategy validation and analytics)
- Unified deployments (Windows/Ubuntu) for continuous 24/7 operation

Links for details
- [Trade Agent](features/TRADE_AGENT.md)
- [Backtest](features/BACKTEST.md)
- [Configuration](configuration/SETTINGS.md)
- [Windows unified service](deployment/WINDOWS_UNIFIED.md)
- [Ubuntu unified service](deployment/UBUNTU_UNIFIED.md)
- [Known Issues](KNOWN_ISSUES.md)
- [Release notes (25.4.1)](releases/25.4.1.md)

---

## Feature 1 — Trade Agent
What it does
- Analyzes the NSE universe (RSI/EMA core logic + filters)
- Optional 2-year backtest scoring for higher quality
- Sends prioritized Telegram alerts

Run locally (Windows PowerShell)
```powershell
.\.venv\Scripts\python.exe trade_agent.py --backtest
```
Run locally (Ubuntu/macOS)
```bash
.venv/bin/python trade_agent.py --backtest
```
More commands and tips: [features/TRADE_AGENT.md](features/TRADE_AGENT.md)

---

## Feature 2 — Backtesting
What it does
- Validates the core strategy historically, returns key metrics and reports

Quick usage (Python API)
```powershell
.\.venv\Scripts\python.exe - << 'PY'
from backtest import BacktestEngine, PerformanceAnalyzer
engine = BacktestEngine("RELIANCE.NS", "2022-01-01", "2023-12-31")
results = engine.run_backtest()
analyzer = PerformanceAnalyzer(engine)
print(analyzer.generate_report(save_to_file=False))
PY
```
More options and examples: [features/BACKTEST.md](features/BACKTEST.md)

---

## Deployment (Unified Service)
Windows (recommended)
- Guide: [deployment/WINDOWS_UNIFIED.md](deployment/WINDOWS_UNIFIED.md)
- One persistent service using NSSM; auto-start on boot; log rotation
- Task Scheduler alternative: [deployment/WINDOWS_UNIFIED_TASK.md](deployment/WINDOWS_UNIFIED_TASK.md)

Ubuntu (recommended)
- Guide: [deployment/UBUNTU_UNIFIED.md](deployment/UBUNTU_UNIFIED.md)
- One persistent systemd service; minimal operational overhead

Multi‑service docs (advanced)
- Windows multi‑service overview: [documents/deployment/windows/WINDOWS_SERVICES_GUIDE.md](../documents/deployment/windows/WINDOWS_SERVICES_GUIDE.md)
- Ubuntu services comparison: [documents/deployment/ubuntu/SERVICES_COMPARISON.md](../documents/deployment/ubuntu/SERVICES_COMPARISON.md)

---

## Known Issues
- See: [KNOWN_ISSUES.md](KNOWN_ISSUES.md) (one-liners + workarounds)

---

## Release Notes (25.4.1)
- Summary: [releases/25.4.1.md](releases/25.4.1.md)
- Bug fixes: one-liners with links to details
- Enhancements: one-liners with links to details

---

## Support
- Logs: logs/trade_agent_YYYYMMDD.log
- Python 3.12 setup help: see [Known Issues — Python 3.12 environment setup](KNOWN_ISSUES.md#python-312-environment-setup)
- Telegram test (Windows)
```powershell
.\\.venv\\Scripts\\python.exe -c "from core.telegram import send_telegram; send_telegram('Test OK')"
```
- Telegram test (Ubuntu/macOS)
```bash
.venv/bin/python -c "from core.telegram import send_telegram; send_telegram('Test OK')"
```
