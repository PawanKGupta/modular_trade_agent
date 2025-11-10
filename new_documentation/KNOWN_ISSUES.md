1# Known Issues (Quick Reference)

- Ubuntu: ImportError: No module named 'apt_pkg'
  - Cause: python3-apt mismatch after distro upgrades.
  - Fix: see documents/deployment/ubuntu/TROUBLESHOOTING_UBUNTU.md (quick reinstall snippet).

- systemd: ImportError: attempted relative import with no known parent package
  - Fixed in v26.1.1 via absolute import fallbacks.
  - Ensure service uses repo v26.1.1+ and correct WorkingDirectory/ExecStart in systemd unit.

- Data fetch: Insufficient weekly data (only N rows, need 50)
  - Not an error; retried automatically. Happens for newly listed/illiquid symbols.

- Analysis says "avoid" despite uptrend
  - Often liquidity guard: MIN_ABSOLUTE_AVG_VOLUME (e.g., 150k). Adjust in settings if needed.

- Telegram not sending
  - Verify token/chat ID in cred.env; test:
  ```powershell
  .\.venv\Scripts\python.exe -c "from core.telegram import send_telegram; send_telegram('Test OK')"
  ```

- Windows NSSM service won’t start
  - Ensure AppDirectory is project root and AppParameters include the script and --env path.

- Permissions/paths for services
  - systemd: set correct User/Group, WorkingDirectory, venv path, and env file path.
  - Windows: run service with a user that can access the repo and the venv.

- Python version
  - Requires Python 3.12+.

## Python 3.12 environment setup

Windows
- Install Python 3.12 (add to PATH), then create a fresh venv and install deps:
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```
- Always run via .\.venv\Scripts\python.exe (services, tasks, tests).

Ubuntu/Debian
- Install Python 3.12 and venv, then recreate venv and install deps:
```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```
- Ensure systemd ExecStart uses the venv Python:
```ini
ExecStart=/path/to/repo/.venv/bin/python /path/to/repo/modules/kotak_neo_auto_trader/run_trading_service.py --env modules/kotak_neo_auto_trader/kotak_neo.env
```
- If you see ImportError: No module named 'apt_pkg' after distro upgrades: see Ubuntu apt_pkg mismatch quick fix above.
