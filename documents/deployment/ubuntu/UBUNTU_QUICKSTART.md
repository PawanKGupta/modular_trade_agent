# Ubuntu Quick Start Guide

Get the Modular Trade Agent running on Ubuntu in 5 minutes!

---

## 🚀 One-Command Installation

```bash
# Transfer files to your Ubuntu server, then:
cd modular_trade_agent
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
```

That's it! The installer will guide you through the rest.

---

## 📋 What You'll Need

Before starting, have these ready:

1. **Telegram Bot Token** - Get from [@BotFather](https://t.me/BotFather) on Telegram
2. **Telegram Chat ID** - Get from [@userinfobot](https://t.me/userinfobot) on Telegram
3. **Sudo access** on your Ubuntu machine

---

## 🔧 Installation Files

This project includes several installation scripts:

| File | Purpose | When to Use |
|------|---------|-------------|
| `setup_ubuntu.sh` | Main installer | **Start here** - Full automated installation |
| `fix_ubuntu_system.sh` | System troubleshooter | If you get apt-get errors during install |
| `INSTALL_UBUNTU.md` | Detailed guide | For manual installation or reference |
| `TROUBLESHOOTING_UBUNTU.md` | Error fixes | If something goes wrong |

---

## ⚡ Quick Installation Steps

### Step 1: Get the Files

**Option A - From Git:**
```bash
git clone <your-repo-url> modular_trade_agent
cd modular_trade_agent
```

**Option B - Upload via SCP:**
```bash
# On your Windows machine
scp -r C:\Personal\Projects\TradingView\modular_trade_agent user@your-server:/home/user/
```

### Step 2: Run Installer

```bash
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
```

### Step 3: Enter Credentials

When prompted, enter:
- Telegram Bot Token
- Telegram Chat ID

### Step 4: Choose Options

- **Systemd service?** → Yes (for automatic daily execution at 4PM)
- **Desktop shortcut?** → Yes (if using desktop Ubuntu)

### Step 5: Done!

```bash
cd ~/modular_trade_agent
source .venv/bin/activate
python3 trade_agent.py --backtest
```

---

## ❌ Common Error: `apt_pkg` Not Found

If you see this error:
```
ModuleNotFoundError: No module named 'apt_pkg'
E: Problem executing scripts APT::Update::Post-Invoke-Success
```

**This is harmless!** The installer will continue. To fix it quickly:

```bash
# Remove the problematic apt hook and refresh package lists
sudo rm -f /etc/apt/apt.conf.d/50command-not-found
sudo apt-get update
```

See TROUBLESHOOTING_UBUNTU.md for more details. Then re-run the installer.

---

## 🎯 After Installation

### Manual Run
```bash
cd ~/modular_trade_agent
source .venv/bin/activate
python3 trade_agent.py                   # Standard analysis
python3 trade_agent.py --backtest        # With historical validation (recommended)
```

### Check Logs
```bash
tail -f ~/modular_trade_agent/logs/trade_agent_$(date +%Y%m%d).log
```

### Test Telegram
```bash
cd ~/modular_trade_agent
source .venv/bin/activate
python3 -c "from core.telegram import send_telegram; send_telegram('Test: Telegram OK')"
```

### View Service Status (if using unified service)
```bash
systemctl status tradeagent-unified.service
journalctl -u tradeagent-unified.service -f
```

---

## 📁 Installation Location

Everything installs to: `~/modular_trade_agent/`

```
~/modular_trade_agent/
├── .venv/                  # Python virtual environment
├── logs/                   # Application logs
├── analysis_results/       # CSV exports
├── cred.env               # Your configuration
├── run_agent.sh           # Launcher scripts
└── ...                    # Application files
```

---

## 🔄 Automatic Execution

If you chose to install the systemd service, the agent will run automatically:

- **When**: Every weekday (Mon-Fri) at 4:00 PM IST
- **What**: Runs `python3 trade_agent.py --backtest`
- **Logs**: Check with `journalctl -u modular-trade-agent.service -f`

### Manage Service (unified)
```bash
# Check status
systemctl status tradeagent-unified.service

# Logs
journalctl -u tradeagent-unified.service -f

# Start/Stop
sudo systemctl start tradeagent-unified.service
sudo systemctl stop tradeagent-unified.service
```
```

---

## 🆘 Troubleshooting

### Installation Failed?

1. **Check the error** in the terminal output
2. **Apply the apt_pkg manual fix** (see above) if relevant
3. **Check the troubleshooting guide**: `TROUBLESHOOTING_UBUNTU.md`
4. **Re-run installer**: `./setup_ubuntu.sh`

### Common Issues & Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| `apt_pkg` error | Remove 50command-not-found + `apt-get update` |
| Permission denied | `chmod +x *.sh` |
| Python too old | `sudo apt-get install python3.10` |
| Telegram not working | Check credentials in `cred.env` |
| Service won't start | Check paths in `/etc/systemd/system/modular-trade-agent.service` |

### Still Stuck?

Read the detailed troubleshooting guide:
```bash
cat TROUBLESHOOTING_UBUNTU.md
```

Or the full installation guide:
```bash
cat INSTALL_UBUNTU.md
```

---

## 📚 Documentation

- **Quick Start**: You're reading it! (this file)
- **Installation Guide**: `INSTALL_UBUNTU.md` - Detailed manual installation
- **Troubleshooting**: `TROUBLESHOOTING_UBUNTU.md` - Error fixes
- **Main README**: `README.md` - Project overview and features
- **Backtest Guide**: `backtest/README.md` - Backtesting documentation

---

## ⚙️ Configuration

### Edit Trading Parameters

```bash
nano ~/modular_trade_agent/config/settings.py
```

### Edit Telegram Credentials

```bash
nano ~/modular_trade_agent/cred.env
```

### Command Options
```bash
# Standard run
python3 trade_agent.py

# With backtest validation (recommended)
python3 trade_agent.py --backtest

# Without CSV export
python3 trade_agent.py --no-csv

# Dip-buying mode
python3 trade_agent.py --dip-mode

# Show help
python3 trade_agent.py --help
```
```

---

## ✅ Verification Checklist

After installation, verify everything works:

- [ ] Installation completed without errors
- [ ] `python3 trade_agent.py --help` works
- [ ] Telegram test sends message: `python3 -c "from core.telegram import send_telegram; send_telegram('Test')"`
- [ ] Configuration file exists: `cat cred.env`
- [ ] Virtual environment works: `source .venv/bin/activate`
- [ ] Unified service is active (if used): `systemctl status tradeagent-unified.service`
- [ ] Logs are being created: `ls -la logs/`

---

## 🎓 Next Steps

1. **Test the system**: Run `./run_agent_backtest.sh` manually
2. **Monitor first runs**: Check logs in `logs/` directory
3. **Verify Telegram alerts**: Make sure messages arrive
4. **Review signals**: Don't blindly follow - understand the strategy
5. **Adjust parameters**: Edit `config/settings.py` if needed
6. **Set up monitoring**: Create cron jobs to check logs

---

## ⚠️ Important Reminders

- ✅ **Test first** - Run manually before relying on automation
- ✅ **Monitor logs** - Check daily for errors
- ✅ **Backup config** - Save your `cred.env` file
- ✅ **Secure credentials** - Never share your tokens
- ✅ **Understand signals** - Don't trade blindly
- ✅ **Paper trade first** - Test strategy before real money

---

## 💡 Pro Tips

1. **Use tmux/screen** for long-running processes:
   ```bash
   tmux new -s trading
   ./run_agent_backtest.sh
   # Ctrl+B, then D to detach
   ```

2. **Set up log monitoring**:
   ```bash
   watch -n 60 'tail -20 logs/trade_agent_$(date +%Y%m%d).log'
   ```

3. **Create aliases**:
   ```bash
   echo "alias trade='cd ~/modular_trade_agent && ./run_agent_backtest.sh'" >> ~/.bashrc
   source ~/.bashrc
   # Now just type: trade
   ```

4. **Monitor from mobile** with Telegram:
   - All alerts go to Telegram
   - You can check logs remotely via SSH apps

---

## 📞 Support

- **Documentation**: Check `INSTALL_UBUNTU.md` and `TROUBLESHOOTING_UBUNTU.md`
- **Logs**: Always check `logs/` directory first
- **GitHub Issues**: Create detailed issue with error logs
- **Community**: Check project's GitHub discussions

---

**Ready to start trading? Run the installer and you'll be up in 5 minutes! 🚀**

```bash
./setup_ubuntu.sh
```

Happy Trading! 📈
