# Ubuntu Installation Troubleshooting Guide

Quick fixes for common errors during installation.

---

## ❌ Error: `ModuleNotFoundError: No module named 'apt_pkg'`

### Full Error Message:
```
Traceback (most recent call last):
  File "/usr/lib/cnf-update-db", line 3, in <module>
    import apt_pkg
ModuleNotFoundError: No module named 'apt_pkg'
E: Problem executing scripts APT::Update::Post-Invoke-Success
```

### What It Means:
The `command-not-found` package's update script is broken. This is **cosmetic only** and won't affect the trading agent installation.

### Quick Fix:

```bash
# Remove the problematic apt hook and refresh package lists
sudo rm -f /etc/apt/apt.conf.d/50command-not-found
sudo apt-get update
```

### Why This Works:
Removes the problematic apt hook that tries to update the command suggestions database.

---

## ❌ Error: `python3-apt` Missing or Broken

### Fix:
```bash
sudo apt-get install --reinstall python3-apt -y
```

---

## ❌ Error: Package Installation Fails

### Symptoms:
- Packages won't install
- "Unable to locate package" errors
- GPG key errors

### Fix:
```bash
# Update package lists
sudo apt-get update

# Fix broken dependencies
sudo apt-get install -f

# Clean and retry
sudo apt-get clean
sudo apt-get autoclean
sudo apt-get update
```

---

## ❌ Error: Permission Denied

### Symptoms:
- "Permission denied" when running scripts
- Cannot create directories

### Fix:
```bash
# Make scripts executable
chmod +x setup_ubuntu.sh

# Check if running as correct user (not root)
whoami  # Should show your username, not 'root'

# If you need sudo access
sudo usermod -aG sudo $USER
```

---

## ❌ Error: Python Version Too Old

### Check Version:
```bash
python3 --version
```

### Fix (if < 3.8):
```bash
# Ubuntu 20.04+
sudo apt-get install python3.10 python3.10-venv python3.10-dev

# Then modify installer to use python3.10 instead of python3
```

---

## ❌ Error: Chromium/Chrome Not Found

### Symptoms:
- Selenium errors
- "chromedriver not found"

### Fix:
```bash
# Install Chromium
sudo apt-get install chromium-browser chromium-chromedriver

# Or use Firefox instead
sudo apt-get install firefox firefox-geckodriver
# Then edit core/scrapping.py to use Firefox
```

---

## ❌ Error: Virtual Environment Creation Fails

### Symptoms:
- `venv` module not found
- Cannot create virtual environment

### Fix:
```bash
# Install venv module
sudo apt-get install python3-venv

# Or use virtualenv
sudo apt-get install python3-virtualenv
python3 -m virtualenv .venv
```

---

## ❌ Error: pip install fails

### Common Causes & Fixes:

**1. Network/SSL Issues:**
```bash
# Use http instead of https (temporary)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

**2. Disk Space:**
```bash
# Check disk space
df -h

# Clean if needed
sudo apt-get clean
sudo apt-get autoclean
```

**3. Build Dependencies Missing:**
```bash
sudo apt-get install build-essential python3-dev
```

**4. Outdated pip:**
```bash
pip install --upgrade pip
```

---

## ❌ Error: Telegram Test Fails

### Check:
```bash
cd ~/modular_trade_agent
source .venv/bin/activate
python3 -c "from core.telegram import send_telegram; send_telegram('Troubleshooting test OK')"
```

### Common Issues:

**1. Wrong Token/Chat ID:**
- Verify `TELEGRAM_BOT_TOKEN` from @BotFather
- Verify `TELEGRAM_CHAT_ID` from @userinfobot (numbers only, no letters)

**2. Extra Spaces in Config:**
```bash
# Check for spaces
cat cred.env | grep TELEGRAM

# Should be: TELEGRAM_BOT_TOKEN=123456:ABC...
# NOT: TELEGRAM_BOT_TOKEN = 123456:ABC...
```

**3. Network/Firewall:**
```bash
# Test connectivity
curl -I https://api.telegram.org
```

---

## ❌ Error: Systemd Service Won't Start

### Check Status:
```bash
systemctl status tradeagent-unified.service
journalctl -u tradeagent-unified.service -n 50
```

### Common Issues:

**1. Wrong Paths:**
```bash
# Check service file paths
sudo nano /etc/systemd/system/modular-trade-agent.service

# Verify:
# - User/Group match your username
# - WorkingDirectory exists
# - ExecStart paths are correct
```

**2. Permission Issues:**
```bash
# Service needs read access to installation
chmod 755 ~/modular_trade_agent
chmod 644 ~/modular_trade_agent/cred.env
```

**3. Virtual Environment Issues:**
```bash
# Test manually first
cd ~/modular_trade_agent
source .venv/bin/activate
python3 trade_agent.py --backtest
```

---

## 🔧 Complete System Reset

If all else fails:

```bash
# 1. Clean apt and refresh
sudo apt-get clean
sudo apt-get autoclean
sudo apt-get update

# 2. Remove old installation
rm -rf ~/modular_trade_agent

# 3. Clean apt
sudo apt-get clean
sudo apt-get autoclean
sudo apt-get update

# 4. Re-run installer
./setup_ubuntu.sh
```

---

## 📝 Getting More Help

### Collect Debug Information:

```bash
# System info
cat /etc/os-release
python3 --version
pip --version

# Installation logs
ls -la ~/modular_trade_agent/
cat ~/modular_trade_agent/logs/*.log

# Service logs (if applicable)
journalctl -u modular-trade-agent.service -n 100
```

### Create GitHub Issue With:
1. Error message (full traceback)
2. System information (OS version, Python version)
3. Steps you've tried
4. Relevant log excerpts

---

## ✅ Verification Steps

After fixing issues, verify:

```bash
# 1. System dependencies
which python3
which chromium-browser
which git

# 2. Python packages
source ~/modular_trade_agent/.venv/bin/activate
python3 -c "import yfinance, pandas, numpy, selenium; print('OK')"

# 3. Configuration
cat ~/modular_trade_agent/cred.env

# 4. Permissions
ls -la ~/modular_trade_agent/*.sh

# 5. Run test
./run_agent.sh --help
```

---

**Quick Commands Summary:**

```bash
# Re-run installer
./setup_ubuntu.sh

# Test installation
source .venv/bin/activate
python3 -c "from core.telegram import send_telegram; send_telegram('Quick summary test')"

# View logs
tail -f logs/trade_agent_$(date +%Y%m%d).log

# Check service (unified)
systemctl status tradeagent-unified.service
```

---

For more detailed documentation, see `INSTALL_UBUNTU.md`
