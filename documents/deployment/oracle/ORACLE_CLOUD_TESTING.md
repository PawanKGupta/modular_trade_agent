# Oracle Cloud Testing (OCI) - Validation Guide

Use this checklist to validate your Modular Trade Agent on an Oracle Cloud VM (Ubuntu 22.04).

---

## 1) Prerequisites
- VM created and accessible via SSH (ubuntu user)
- Repo cloned at: `/home/ubuntu/modular_trade_agent`
- Credentials:
  - `modules/kotak_neo_auto_trader/kotak_neo.env` (Kotak Neo)
  - `cred.env` (Telegram, etc.)

---

## 2) Environment sanity checks
```bash
# SSH into the VM
ssh ubuntu@YOUR_PUBLIC_IP

cd ~/modular_trade_agent

# Python and git
python3 --version
pip3 --version

# Install deps (first time or after updates)
pip3 install -r requirements.txt
```

---

## 3) Analysis smoke test (no broker calls)
```bash
cd ~/modular_trade_agent
# Run analysis with backtesting and write logs
python3 -m src.presentation.cli.application analyze --backtest >> /home/ubuntu/logs/analysis.log 2>&1

# Verify output/logs
ls -lh analysis_results/
tail -n 100 /home/ubuntu/logs/analysis.log
```
Expected: CSV files under `analysis_results/` and no critical errors in logs.

---

## 4) Broker authentication test (Kotak Neo)
```bash
cd ~/modular_trade_agent
python3 - <<'PY'
from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
auth = KotakNeoAuth('modules/kotak_neo_auto_trader/kotak_neo.env')
print('Login:', auth.login())
PY
```
Expected: `Login: True` (or a valid session).

---

## 5) View current holdings

Heredoc (most reliable):
```bash
cd ~/modular_trade_agent
python3 - <<'PY'
from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
import json

a = KotakNeoAuth('modules/kotak_neo_auto_trader/kotak_neo.env')
a.login()
p = KotakNeoPortfolio(a.client)
print(json.dumps(p.get_holdings(), indent=2))
PY
```

One‑liner alternative:
```bash
python3 -c "from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio; from modules.kotak_neo_auto_trader.auth import KotakNeoAuth; a=KotakNeoAuth('modules/kotak_neo_auto_trader/kotak_neo.env'); a.login(); p=KotakNeoPortfolio(a.client); import json; print(json.dumps(p.get_holdings(), indent=2))"
```

---

## 6) Sell engine dry run (single iteration)
```bash
cd ~/modular_trade_agent
# Run once and exit quickly (no long monitor loop)
python3 -m modules.kotak_neo_auto_trader.run_sell_orders \
  --env modules/kotak_neo_auto_trader/kotak_neo.env \
  --run-once --skip-wait >> /home/ubuntu/logs/sell-engine-test.log 2>&1

tail -n 100 /home/ubuntu/logs/sell-engine-test.log
```
Expected: starts, fetches holdings/positions, exits cleanly.

---

## 7) Cron validation (if using cron)
```bash
# Show crontab
crontab -l

# Typical entries (from docs):
# 30 10 * * 1-5 cd /home/ubuntu/modular_trade_agent && /usr/bin/python3 -m src.presentation.cli.application analyze --backtest >> /home/ubuntu/logs/analysis.log 2>&1
# 35 10 * * 1-5 cd /home/ubuntu/modular_trade_agent && /usr/bin/python3 -m modules.kotak_neo_auto_trader.run_auto_trade --env modules/kotak_neo_auto_trader/kotak_neo.env >> /home/ubuntu/logs/buy-orders.log 2>&1
# 45 3  * * 1-5 cd /home/ubuntu/modular_trade_agent && /usr/bin/python3 -m modules.kotak_neo_auto_trader.run_sell_orders >> /home/ubuntu/logs/sell-engine.log 2>&1

# Verify recent cron activity
grep CRON /var/log/syslog | tail -n 50
```

---

## 8) Systemd validation (if using service instead of cron)
```bash
# Example service from docs: trading-sell-engine.service
sudo systemctl daemon-reload
sudo systemctl enable trading-sell-engine
sudo systemctl start trading-sell-engine

# Status and logs
sudo systemctl status trading-sell-engine
journalctl -u trading-sell-engine -n 100 -f
```

---

## 9) Logs
```bash
# App logs
ls -lh /home/ubuntu/logs/

tail -f /home/ubuntu/logs/analysis.log
 tail -f /home/ubuntu/logs/buy-orders.log
 tail -f /home/ubuntu/logs/sell-engine.log
```

---

## 10) Health check
If packaged: use `scripts/health_check.sh` (Linux) or run the Python check directly:
```bash
cd ~/modular_trade_agent
python3 health_check.py
```

---

## Safety checklist before production
- [ ] Credentials valid (login and holdings fetch OK)
- [ ] Analysis produces CSVs without errors
- [ ] Cron or systemd configured and enabled (choose one)
- [ ] Logs writing under `/home/ubuntu/logs/`
- [ ] Dry-run of sell engine successful
- [ ] Timezone/UTC offsets correct for schedules

---

## Troubleshooting quick refs
- Auth errors: recheck `modules/kotak_neo_auto_trader/kotak_neo.env`
- Missing deps: `pip3 install -r requirements.txt`
- Cron not running: `sudo systemctl status cron` and check `/var/log/syslog`
- Permissions: ensure repo/log files owned by `ubuntu` user

---

## Useful one‑liners
```bash
# Show next timers (if using systemd timers)
systemctl list-timers | grep trading

# Tail today’s app log
LOG=\"/home/ubuntu/logs/trade_agent_$(date +%Y%m%d).log\"; tail -n 100 \"$LOG\" || true
```
