# Modular Trade Agent - Ubuntu Installation Guide

Complete guide for installing and setting up the Modular Trade Agent on Ubuntu/Debian systems.

## 📋 Table of Contents

- [System Requirements](#system-requirements)
- [Quick Installation](#quick-installation)
- [Manual Installation](#manual-installation)
- [Configuration](#configuration)
- [Running the Agent](#running-the-agent)
- [Systemd Service Setup](#systemd-service-setup)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

---

## 🖥️ System Requirements

### Minimum Requirements
- **OS**: Ubuntu 20.04+ or Debian 10+
- **Python**: 3.8 or higher
- **RAM**: 2 GB minimum, 4 GB recommended
- **Disk Space**: 500 MB for installation
- **Internet**: Required for data fetching and Telegram alerts

### Supported Distributions
- Ubuntu 20.04 LTS, 22.04 LTS, 24.04 LTS
- Debian 10 (Buster), 11 (Bullseye), 12 (Bookworm)
- Linux Mint 20+
- Pop!_OS 20.04+

---

## ⚡ Quick Installation

### One-Line Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/modular_trade_agent/main/setup_ubuntu.sh | bash
```

Or download and run:

```bash
wget https://raw.githubusercontent.com/YOUR_REPO/modular_trade_agent/main/setup_ubuntu.sh
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
```

### What the Installer Does

The automated installer will:
1. ✅ Check system compatibility (OS, Python version)
2. ✅ Install system dependencies (Python, Chrome, etc.)
3. ✅ Create installation directory (`~/modular_trade_agent`)
4. ✅ Set up Python virtual environment
5. ✅ Install Python packages from requirements.txt
6. ✅ Configure Telegram credentials
7. ✅ Create launcher scripts
8. ✅ Test the installation
9. ✅ (Optional) Install systemd service for automatic execution
10. ✅ (Optional) Create desktop shortcut

### Installation Process

The installer will prompt you for:

1. **Confirmation to proceed**
2. **Telegram Bot Token** (from @BotFather)
3. **Telegram Chat ID** (from @userinfobot)
4. **Systemd service** (y/n for automatic daily execution)
5. **Desktop shortcut** (y/n for convenience launcher)

**Total installation time**: 5-10 minutes depending on internet speed.

---

## 🔧 Manual Installation

If you prefer to install manually or the automated installer fails:

### Step 1: Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    git \
    curl \
    wget \
    chromium-browser \
    chromium-chromedriver
```

### Step 2: Clone Repository

```bash
cd ~
git clone https://github.com/YOUR_REPO/modular_trade_agent.git
cd modular_trade_agent
```

Or if you have the source files:

```bash
cd ~
mkdir modular_trade_agent
cd modular_trade_agent
# Copy your files here
```

### Step 3: Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 4: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Create Configuration File

```bash
nano cred.env
```

Add your credentials:

```env
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Retry Configuration
RETRY_MAX_ATTEMPTS=3
RETRY_BASE_DELAY=1.0
RETRY_MAX_DELAY=30.0
RETRY_BACKOFF_MULTIPLIER=2.0

# Circuit Breaker Configuration
CIRCUITBREAKER_FAILURE_THRESHOLD=3
CIRCUITBREAKER_RECOVERY_TIMEOUT=60.0

# News Sentiment Configuration
NEWS_SENTIMENT_ENABLED=true
NEWS_SENTIMENT_LOOKBACK_DAYS=30
NEWS_SENTIMENT_MIN_ARTICLES=2
NEWS_SENTIMENT_POS_THRESHOLD=0.25
NEWS_SENTIMENT_NEG_THRESHOLD=-0.25
```

Save and exit (Ctrl+X, Y, Enter).

### Step 6: Create Launcher Scripts

```bash
# Main launcher
cat > run_agent.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python3 trade_agent.py "$@"
EOF

# Backtest launcher
cat > run_agent_backtest.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python3 trade_agent.py --backtest "$@"
EOF

# Make executable
chmod +x run_agent.sh run_agent_backtest.sh
```

### Step 7: Test Installation

```bash
source .venv/bin/activate
python3 -c "import yfinance, pandas, numpy, selenium; print('All imports OK!')"
python3 test_telegram.py  # Test Telegram connection
```

---

## ⚙️ Configuration

### Environment Variables (cred.env)

Edit `~/modular_trade_agent/cred.env`:

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes | `123456:ABC-DEF...` |
| `TELEGRAM_CHAT_ID` | Your chat ID from @userinfobot | Yes | `987654321` |
| `NEWS_SENTIMENT_ENABLED` | Enable news sentiment analysis | No | `true` |
| `NEWS_SENTIMENT_LOOKBACK_DAYS` | Days to look back for news | No | `30` |

### Trading Parameters (config/settings.py)

Edit `~/modular_trade_agent/config/settings.py`:

```python
LOOKBACK_DAYS = 90                    # Historical data period
MIN_VOLUME_MULTIPLIER = 1.0           # Minimum volume threshold
RSI_OVERSOLD = 30                     # RSI oversold level
VOLUME_MULTIPLIER_FOR_STRONG = 1.2    # Strong volume threshold
```

### Getting Telegram Credentials

1. **Create Bot**:
   - Open Telegram and search for `@BotFather`
   - Send `/newbot` and follow instructions
   - Copy the bot token provided

2. **Get Chat ID**:
   - Search for `@userinfobot` on Telegram
   - Send `/start`
   - Copy your chat ID (numbers only)

---

## 🚀 Running the Agent

### Command Line Options

```bash
cd ~/modular_trade_agent
source .venv/bin/activate

# Standard run
python3 trade_agent.py

# With backtest validation (recommended)
python3 trade_agent.py --backtest

# Without CSV export
python3 trade_agent.py --no-csv

# Without multi-timeframe analysis
python3 trade_agent.py --no-mtf

# Dip-buying mode (more permissive)
python3 trade_agent.py --dip-mode

# Combined: backtest + dip-mode
python3 trade_agent.py --backtest --dip-mode
```

### Using Launcher Scripts

```bash
cd ~/modular_trade_agent

# Standard analysis
./run_agent.sh

# With backtest validation
./run_agent_backtest.sh

# Run specific backtest
./run_backtest.sh RELIANCE.NS 2022-01-01 2023-12-31
```

### Output Locations

- **Logs**: `~/modular_trade_agent/logs/`
- **Analysis Results**: `~/modular_trade_agent/analysis_results/`
- **Backtest Reports**: `~/modular_trade_agent/backtest_reports/`
- **Backtest Exports**: `~/modular_trade_agent/backtest_exports/`

---

## 🔄 Systemd Service Setup

### Automatic Daily Execution

The installer can set up a systemd service to run automatically at 4:00 PM IST (Mon-Fri).

### Manual Service Installation

If you skipped during installation:

```bash
cd ~/modular_trade_agent
sudo nano /etc/systemd/system/modular-trade-agent.service
```

Add:

```ini
[Unit]
Description=Modular Trade Agent - Automated Trading System
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/modular_trade_agent
ExecStart=/home/YOUR_USERNAME/modular_trade_agent/.venv/bin/python /home/YOUR_USERNAME/modular_trade_agent/trade_agent.py --backtest
Restart=on-failure
RestartSec=60
StandardOutput=append:/home/YOUR_USERNAME/modular_trade_agent/logs/service.log
StandardError=append:/home/YOUR_USERNAME/modular_trade_agent/logs/service_error.log

# Environment
Environment="PATH=/home/YOUR_USERNAME/modular_trade_agent/.venv/bin:/usr/local/bin:/usr/bin:/bin"

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Create timer:

```bash
sudo nano /etc/systemd/system/modular-trade-agent.timer
```

Add:

```ini
[Unit]
Description=Modular Trade Agent Daily Timer
Requires=modular-trade-agent.service

[Timer]
OnCalendar=Mon-Fri 16:00:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable modular-trade-agent.timer
sudo systemctl start modular-trade-agent.timer
```

### Service Management Commands

```bash
# View timer status
systemctl status modular-trade-agent.timer

# View next scheduled run
systemctl list-timers modular-trade-agent.timer

# View logs (real-time)
journalctl -u modular-trade-agent.service -f

# View logs (last 100 lines)
journalctl -u modular-trade-agent.service -n 100

# Manual execution
sudo systemctl start modular-trade-agent.service

# Stop timer
sudo systemctl stop modular-trade-agent.timer

# Disable automatic execution
sudo systemctl disable modular-trade-agent.timer
```

---

## 🔍 Troubleshooting

### Installation Issues

#### Problem: Python version too old

```bash
# Check version
python3 --version

# If < 3.8, install newer version
sudo apt-get install python3.10 python3.10-venv python3.10-dev
```

#### Problem: pip install fails

```bash
# Upgrade pip
python3 -m pip install --upgrade pip

# Install with verbose output
pip install -r requirements.txt -v
```

#### Problem: Chrome/Selenium issues

```bash
# Install Chromium
sudo apt-get install chromium-browser chromium-chromedriver

# Or use Firefox instead (edit core/scrapping.py)
sudo apt-get install firefox firefox-geckodriver
```

### Runtime Issues

#### Problem: No data fetched

- Check internet connection
- Verify ticker symbols end with `.NS` (e.g., `RELIANCE.NS`)
- Check yfinance API status

#### Problem: Telegram not working

```bash
# Test configuration
cd ~/modular_trade_agent
source .venv/bin/activate
python3 test_telegram.py
```

Verify:
- Bot token is correct (from @BotFather)
- Chat ID is correct (numeric, from @userinfobot)
- No extra spaces in cred.env

#### Problem: Permission denied

```bash
# Fix permissions
chmod +x ~/modular_trade_agent/*.sh
chmod 600 ~/modular_trade_agent/cred.env
```

#### Problem: Module import errors

```bash
# Reinstall dependencies
cd ~/modular_trade_agent
source .venv/bin/activate
pip install --force-reinstall -r requirements.txt
```

### Service Issues

#### Problem: Service won't start

```bash
# Check service status
systemctl status modular-trade-agent.service

# View detailed logs
journalctl -u modular-trade-agent.service -n 50

# Check file paths in service file
sudo nano /etc/systemd/system/modular-trade-agent.service
```

#### Problem: Timer not executing

```bash
# Verify timer is active
systemctl is-active modular-trade-agent.timer

# Check next run time
systemctl list-timers modular-trade-agent.timer

# Restart timer
sudo systemctl restart modular-trade-agent.timer
```

### Logs

Check logs for errors:

```bash
# Application logs
tail -f ~/modular_trade_agent/logs/trade_agent_$(date +%Y%m%d).log

# Service logs
journalctl -u modular-trade-agent.service -f

# Search for errors
grep ERROR ~/modular_trade_agent/logs/*.log
```

---

## 🗑️ Uninstallation

### Remove Installation

```bash
# Stop and disable service (if installed)
sudo systemctl stop modular-trade-agent.timer
sudo systemctl disable modular-trade-agent.timer
sudo rm /etc/systemd/system/modular-trade-agent.service
sudo rm /etc/systemd/system/modular-trade-agent.timer
sudo systemctl daemon-reload

# Remove installation directory
rm -rf ~/modular_trade_agent

# Remove desktop shortcut (if created)
rm ~/Desktop/ModularTradeAgent.desktop
```

### Keep Configuration Only

```bash
# Backup configuration
cp ~/modular_trade_agent/cred.env ~/cred.env.backup

# Remove installation
rm -rf ~/modular_trade_agent

# Later restore
mkdir ~/modular_trade_agent
cp ~/cred.env.backup ~/modular_trade_agent/cred.env
```

---

## 📚 Additional Resources

### Documentation
- Main README: `README.md`
- Backtest Guide: `backtest/README.md`
- Security Guide: `SECURITY.md`

### Testing

```bash
cd ~/modular_trade_agent
source .venv/bin/activate

# Test single stock
python3 -c "from core.analysis import analyze_ticker; print(analyze_ticker('RELIANCE.NS'))"

# Test backtest
python3 run_backtest.py RELIANCE.NS 2022-01-01 2023-12-31
```

### Monitoring

Set up a cron job to check logs daily:

```bash
crontab -e
```

Add:

```bash
0 17 * * 1-5 grep -i error ~/modular_trade_agent/logs/trade_agent_$(date +\%Y\%m\%d).log | mail -s "Trade Agent Errors" your@email.com
```

---

## 🆘 Getting Help

1. **Check logs** for error messages
2. **Review configuration** in `cred.env` and `config/settings.py`
3. **Test components** individually (imports, Telegram, data fetching)
4. **Check system resources** (disk space, memory, network)
5. **Create an issue** on GitHub with error logs

---

## ⚠️ Important Notes

- **Always test** with paper trading first
- **Monitor logs** during first few runs
- **Backup data** regularly (especially `analysis_results/`)
- **Keep credentials secure** (`chmod 600 cred.env`)
- **Review signals** before acting on them
- **Stay compliant** with your broker's API terms

---

## 📝 Quick Reference

### File Locations
- Installation: `~/modular_trade_agent/`
- Config: `~/modular_trade_agent/cred.env`
- Logs: `~/modular_trade_agent/logs/`
- Service: `/etc/systemd/system/modular-trade-agent.*`

### Commands
```bash
# Run agent
./run_agent_backtest.sh

# View logs
tail -f logs/trade_agent_$(date +%Y%m%d).log

# Check service
systemctl status modular-trade-agent.timer

# Edit config
nano cred.env
```

---

**Happy Trading! 🚀📈**

For issues or questions, please check the troubleshooting section or create an issue on GitHub.
