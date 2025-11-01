# Ubuntu Installation & Service Management

Complete Ubuntu/Linux setup for the Modular Trade Agent with automated systemd services.

---

## 📁 Directory Structure

```
ubuntu/
├── installers/          # Installation scripts
│   ├── setup_ubuntu.sh                      # Main installer (signal generation only)
│   ├── setup_complete_services_ubuntu.sh    # Complete setup (all 5 services)
│   ├── setup_multi_services.sh              # Optional multi-service setup
│   ├── fix_ubuntu_system.sh                 # System troubleshooting
│   └── make_executable.sh                   # Make all scripts executable
│
├── tests/               # Testing & verification scripts
│   ├── verify_installation.sh               # Verify complete installation
│   ├── test_all_services.sh                 # Test all services individually
│   └── cleanup_old_services.sh              # Remove duplicate services
│
└── docs/                # Documentation
    ├── INSTALL_UBUNTU.md                    # Complete installation guide
    ├── UBUNTU_QUICKSTART.md                 # 5-minute quick start
    ├── UBUNTU_COMMANDS.md                   # Command reference
    ├── TROUBLESHOOTING_UBUNTU.md            # Error solutions
    └── SERVICES_COMPARISON.md               # Windows vs Ubuntu comparison
```

---

## 🚀 Quick Start

### Option 1: Multiple Services (5 separate services)

```bash
cd ~/modular_trade_agent
chmod +x setup_ubuntu.sh
sudo ./setup_ubuntu.sh
```

**Creates:**
1. Trade Analysis (4:00 PM) - Generate signals
2. Auto Trade (9:00 AM & 4:05 PM) - Place orders
3. Position Monitor (every 1 min) - Monitor positions
4. Sell Orders (9:15 AM) - Manage sell orders
5. EOD Cleanup (3:35 PM) - Daily reconciliation

**Best for:** Granular control, debugging individual tasks

### Option 2: Unified Service (1 persistent service - Recommended)

```bash
cd ~/modular_trade_agent
chmod +x setup_ubuntu_unified.sh
sudo ./setup_ubuntu_unified.sh
```

**Creates:**
- 1 unified service handling all trading tasks
- Maintains persistent session all day
- Better resource management
- No JWT expiry issues

**Best for:** Production deployment, resource efficiency

---

## 🔍 Verification

After installation, verify everything works:

```bash
cd ~/modular_trade_agent
chmod +x scripts/deploy/ubuntu/tests/*.sh
sudo scripts/deploy/ubuntu/tests/verify_installation.sh
```

---

## 🧪 Testing

Test all services individually:

```bash
cd ~/modular_trade_agent
sudo scripts/deploy/ubuntu/tests/test_all_services.sh
```

This will:
- Stop all services
- Test each service manually
- Test systemd integration
- Restart services
- Show comprehensive report

---

## 📊 Service Management

### View All Services
```bash
systemctl list-timers tradeagent-*
```

### View Logs
```bash
journalctl -u tradeagent-analysis.service -f
journalctl -u tradeagent-autotrade.service -f
journalctl -u tradeagent-monitor.service -f
```

### Manual Execution
```bash
sudo systemctl start tradeagent-analysis.service
sudo systemctl start tradeagent-autotrade.service
```

### Stop All Services
```bash
sudo systemctl stop tradeagent-*.timer
```

---

## 🗑️ Uninstallation

### Remove All Services

```bash
cd ~/modular_trade_agent
chmod +x uninstall_ubuntu_services.sh
sudo ./uninstall_ubuntu_services.sh
```

This will:
- Stop all running services
- Disable all timers
- Remove all service files from /etc/systemd/system/
- Reload systemd daemon

**Note:** This only removes services. Project files, configs, and data remain.

---

## 📚 Documentation

- **[INSTALL_UBUNTU.md](INSTALL_UBUNTU.md)** - Complete installation guide
- **[UBUNTU_QUICKSTART.md](UBUNTU_QUICKSTART.md)** - Quick 5-minute setup
- **[UBUNTU_COMMANDS.md](UBUNTU_COMMANDS.md)** - All commands reference
- **[TROUBLESHOOTING_UBUNTU.md](TROUBLESHOOTING_UBUNTU.md)** - Fix common errors
- **[SERVICES_COMPARISON.md](SERVICES_COMPARISON.md)** - Windows vs Ubuntu

---

## 🎯 Use Cases

### I want trade signals only
→ Use `setup_ubuntu.sh` (Option 1)

### I want full automation
→ Use `setup_complete_services_ubuntu.sh` (Option 2)

### I want morning/EOD summaries
→ Use `setup_multi_services.sh` (Optional extras)

---

## ⚠️ Requirements

- Ubuntu 20.04+ or Debian 10+
- Python 3.8+
- Sudo access
- Internet connection
- Telegram bot token & chat ID

**For automated trading (Option 2):**
- Kotak Neo credentials
- `kotak_neo.env` configured

---

## 🔧 Troubleshooting

### Installation Issues
```bash
# Fix system issues first
sudo scripts/deploy/ubuntu/installers/fix_ubuntu_system.sh

# Then re-run installer
sudo scripts/deploy/ubuntu/installers/setup_ubuntu.sh
```

### Service Issues
```bash
# Clean up duplicates
sudo scripts/deploy/ubuntu/tests/cleanup_old_services.sh

# Verify installation
sudo scripts/deploy/ubuntu/tests/verify_installation.sh
```

### Check Logs
```bash
# Application logs
tail -f ~/modular_trade_agent/logs/trade_agent_$(date +%Y%m%d).log

# Service logs
journalctl -u tradeagent-analysis.service -n 50
```

---

## 📦 What Gets Installed

### Files Created:
- `/etc/systemd/system/tradeagent-*.service` - Service definitions
- `/etc/systemd/system/tradeagent-*.timer` - Scheduled timers
- `~/modular_trade_agent/.venv/` - Python virtual environment
- `~/modular_trade_agent/cred.env` - Configuration file
- `~/modular_trade_agent/logs/` - Log files

### Services Registered:
- `tradeagent-analysis.timer` - Analysis scheduler
- `tradeagent-autotrade.timer` - Auto trade scheduler (if Option 2)
- `tradeagent-monitor.timer` - Position monitor (if Option 2)
- `tradeagent-sell.timer` - Sell orders (if Option 2)
- `tradeagent-eod.timer` - EOD cleanup (if Option 2)

---

## 🆘 Getting Help

1. **Check documentation** in `docs/` directory
2. **Run verification** script: `verify_installation.sh`
3. **Check logs** for error messages
4. **Read troubleshooting** guide: `TROUBLESHOOTING_UBUNTU.md`
5. **Test services** individually: `test_all_services.sh`

---

## 🔄 Uninstallation

```bash
# Stop and remove services
sudo systemctl stop tradeagent-*.timer
sudo systemctl disable tradeagent-*.timer
sudo rm /etc/systemd/system/tradeagent-*.{service,timer}
sudo systemctl daemon-reload

# Remove installation (optional)
rm -rf ~/modular_trade_agent
```

---

## ✅ Quick Commands

```bash
# Install (signal generation only)
sudo ubuntu/installers/setup_ubuntu.sh

# Install (complete automation)
sudo ubuntu/installers/setup_complete_services_ubuntu.sh

# Verify
sudo ubuntu/tests/verify_installation.sh

# Test all services
sudo ubuntu/tests/test_all_services.sh

# View services
systemctl list-timers tradeagent-*

# View logs
journalctl -u tradeagent-analysis.service -f
```

---

For detailed instructions, see [INSTALL_UBUNTU.md](docs/INSTALL_UBUNTU.md) or [UBUNTU_QUICKSTART.md](docs/UBUNTU_QUICKSTART.md).

**Happy Trading! 📈**
