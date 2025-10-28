# Ubuntu Commands Quick Reference

Essential commands for managing the Modular Trade Agent on Ubuntu.

---

## 🔍 Verification & Testing

### Complete Installation Check
```bash
cd ~/modular_trade_agent
./verify_installation.sh
```

### Test Telegram Connection
```bash
cd ~/modular_trade_agent
source .venv/bin/activate
python3 test_telegram.py
```

### Quick System Info
```bash
# Check Python version
python3 --version

# Check installation location
ls -la ~/modular_trade_agent/

# Check disk space
df -h ~/modular_trade_agent/
```

---

## 🚀 Running the Agent

### Standard Execution
```bash
cd ~/modular_trade_agent
./run_agent.sh
```

### With Backtest Validation (Recommended)
```bash
cd ~/modular_trade_agent
./run_agent_backtest.sh
```

### With Options
```bash
# No CSV export
./run_agent.sh --no-csv

# Dip-buying mode
./run_agent.sh --dip-mode

# Combined
./run_agent_backtest.sh --dip-mode
```

### Manual Execution (Full Control)
```bash
cd ~/modular_trade_agent
source .venv/bin/activate
python3 trade_agent.py --backtest
```

---

## 📊 Service Management

### Check Service Status
```bash
# Timer status (shows if auto-execution is enabled)
systemctl status modular-trade-agent.timer

# Service status (shows if currently running)
systemctl status modular-trade-agent.service

# Check if timer is active
systemctl is-active modular-trade-agent.timer
```

### View Next Scheduled Run
```bash
systemctl list-timers modular-trade-agent.timer
```

### Manual Service Execution
```bash
# Start service manually
sudo systemctl start modular-trade-agent.service

# Check if it's running
systemctl status modular-trade-agent.service
```

### Start/Stop/Restart
```bash
# Start timer (enable auto-execution)
sudo systemctl start modular-trade-agent.timer

# Stop timer (disable auto-execution)
sudo systemctl stop modular-trade-agent.timer

# Restart timer
sudo systemctl restart modular-trade-agent.timer

# Enable at boot
sudo systemctl enable modular-trade-agent.timer

# Disable at boot
sudo systemctl disable modular-trade-agent.timer
```

### Reload Service Configuration
```bash
# After editing service files
sudo systemctl daemon-reload
sudo systemctl restart modular-trade-agent.timer
```

---

## 📝 Viewing Logs

### Application Logs
```bash
# Today's log (real-time)
tail -f ~/modular_trade_agent/logs/trade_agent_$(date +%Y%m%d).log

# Last 100 lines
tail -100 ~/modular_trade_agent/logs/trade_agent_$(date +%Y%m%d).log

# View all logs
ls -lh ~/modular_trade_agent/logs/

# Search for errors
grep -i error ~/modular_trade_agent/logs/*.log

# Search for specific stock
grep "RELIANCE.NS" ~/modular_trade_agent/logs/*.log
```

### Service Logs (systemd)
```bash
# Real-time service logs
journalctl -u modular-trade-agent.service -f

# Last 50 lines
journalctl -u modular-trade-agent.service -n 50

# Logs from today
journalctl -u modular-trade-agent.service --since today

# Logs from specific time
journalctl -u modular-trade-agent.service --since "2025-01-28 16:00:00"

# Show only errors
journalctl -u modular-trade-agent.service -p err
```

### Export Logs
```bash
# Save logs to file
journalctl -u modular-trade-agent.service > service_logs.txt

# Save with date range
journalctl -u modular-trade-agent.service --since "2025-01-01" --until "2025-01-31" > jan_logs.txt
```

---

## ⚙️ Configuration

### Edit Configuration
```bash
# Main configuration
nano ~/modular_trade_agent/cred.env

# Trading parameters
nano ~/modular_trade_agent/config/settings.py
```

### View Configuration
```bash
# Show Telegram config (without exposing tokens)
grep "TELEGRAM_" ~/modular_trade_agent/cred.env | sed 's/=.*/=***/'

# Show all config
cat ~/modular_trade_agent/cred.env
```

### Backup Configuration
```bash
# Backup config file
cp ~/modular_trade_agent/cred.env ~/cred.env.backup

# With timestamp
cp ~/modular_trade_agent/cred.env ~/cred.env.backup.$(date +%Y%m%d)
```

---

## 🔧 Maintenance

### Update Installation
```bash
cd ~/modular_trade_agent
git pull

# Reinstall dependencies if needed
source .venv/bin/activate
pip install -r requirements.txt --upgrade
```

### Clean Logs
```bash
# Remove old logs (older than 30 days)
find ~/modular_trade_agent/logs/ -name "*.log" -mtime +30 -delete

# Archive logs
tar -czf logs_backup_$(date +%Y%m%d).tar.gz ~/modular_trade_agent/logs/
```

### Check Disk Space
```bash
# Installation size
du -sh ~/modular_trade_agent/

# Logs size
du -sh ~/modular_trade_agent/logs/

# Available space
df -h ~/modular_trade_agent/
```

---

## 🐛 Troubleshooting

### System Health Check
```bash
# Run full verification
./verify_installation.sh

# Fix system issues
./fix_ubuntu_system.sh
```

### Check Dependencies
```bash
cd ~/modular_trade_agent
source .venv/bin/activate

# Test imports
python3 -c "import yfinance, pandas, numpy, selenium; print('All OK')"

# List installed packages
pip list

# Check for package updates
pip list --outdated
```

### Reinstall Dependencies
```bash
cd ~/modular_trade_agent
source .venv/bin/activate

# Reinstall specific package
pip install --force-reinstall yfinance

# Reinstall all
pip install --force-reinstall -r requirements.txt
```

### Reset Virtual Environment
```bash
cd ~/modular_trade_agent

# Remove old venv
rm -rf .venv

# Create new
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Service Troubleshooting
```bash
# Check service file syntax
sudo systemd-analyze verify /etc/systemd/system/modular-trade-agent.service

# View full service output
journalctl -u modular-trade-agent.service -n 100 --no-pager

# Check for failed services
systemctl --failed

# Reset failed state
sudo systemctl reset-failed modular-trade-agent.service
```

---

## 📊 Analysis Results

### View Results
```bash
# List analysis files
ls -lh ~/modular_trade_agent/analysis_results/

# View latest CSV
cat ~/modular_trade_agent/analysis_results/bulk_analysis_*.csv | tail -50

# Count signals by type
grep -c "strong_buy" ~/modular_trade_agent/analysis_results/*.csv
```

### Export/Download Results
```bash
# From server to local (run on local machine)
scp user@server:~/modular_trade_agent/analysis_results/*.csv ./downloads/

# Archive results
cd ~/modular_trade_agent
tar -czf analysis_$(date +%Y%m%d).tar.gz analysis_results/
```

---

## 🔐 Security

### Check Permissions
```bash
# Config file should be 600
ls -l ~/modular_trade_agent/cred.env

# Fix if needed
chmod 600 ~/modular_trade_agent/cred.env

# Installation directory
ls -ld ~/modular_trade_agent/
```

### Secure Credentials
```bash
# Never print credentials
# Instead, check they exist:
grep -q "TELEGRAM_BOT_TOKEN=" ~/modular_trade_agent/cred.env && echo "Token configured" || echo "Token missing"
```

---

## 📈 Monitoring

### Create Monitoring Cron Job
```bash
# Edit crontab
crontab -e

# Add monitoring (check every hour)
0 * * * * grep -i error ~/modular_trade_agent/logs/trade_agent_$(date +\%Y\%m\%d).log && echo "Errors found" | mail -s "Trade Agent Errors" your@email.com
```

### System Resource Usage
```bash
# CPU and Memory usage
top -p $(pgrep -f trade_agent.py)

# If running as service
systemctl status modular-trade-agent.service | grep -E "Memory|CPU"

# Detailed resource usage
ps aux | grep trade_agent
```

---

## 🔄 Automation

### Manual Cron Setup (Alternative to Systemd)
```bash
# Edit crontab
crontab -e

# Add entry (run daily at 4PM)
0 16 * * 1-5 cd ~/modular_trade_agent && .venv/bin/python trade_agent.py --backtest >> logs/cron.log 2>&1
```

### Check Cron Jobs
```bash
# List your cron jobs
crontab -l

# View cron log
grep CRON /var/log/syslog
```

---

## 🆘 Emergency Commands

### Kill Stuck Process
```bash
# Find process
ps aux | grep trade_agent.py

# Kill by PID
kill <PID>

# Force kill
kill -9 <PID>

# Kill all Python processes (careful!)
pkill -f trade_agent.py
```

### Quick Restart Everything
```bash
# Stop service
sudo systemctl stop modular-trade-agent.timer
sudo systemctl stop modular-trade-agent.service

# Wait a moment
sleep 5

# Start service
sudo systemctl start modular-trade-agent.timer

# Verify
systemctl status modular-trade-agent.timer
```

---

## 📦 Backup & Restore

### Full Backup
```bash
cd ~
tar -czf modular_trade_agent_backup_$(date +%Y%m%d).tar.gz modular_trade_agent/
```

### Backup Important Files Only
```bash
cd ~/modular_trade_agent
tar -czf config_backup_$(date +%Y%m%d).tar.gz cred.env config/ analysis_results/ logs/
```

### Restore from Backup
```bash
cd ~
tar -xzf modular_trade_agent_backup_20250128.tar.gz
```

---

## 🎯 Quick Aliases

Add to `~/.bashrc` for convenience:

```bash
# Edit bashrc
nano ~/.bashrc

# Add these aliases
alias trade='cd ~/modular_trade_agent && ./run_agent_backtest.sh'
alias tradelogs='tail -f ~/modular_trade_agent/logs/trade_agent_$(date +%Y%m%d).log'
alias tradestatus='systemctl status modular-trade-agent.timer'
alias tradeconfig='nano ~/modular_trade_agent/cred.env'
alias tradeverify='cd ~/modular_trade_agent && ./verify_installation.sh'

# Reload bashrc
source ~/.bashrc
```

Now you can just type: `trade`, `tradelogs`, `tradestatus`, etc.

---

## 📞 Getting Help

```bash
# View help for main script
cd ~/modular_trade_agent
./run_agent.sh --help

# View documentation
cat INSTALL_UBUNTU.md
cat TROUBLESHOOTING_UBUNTU.md
cat README.md
```

---

**Pro Tip**: Bookmark this file on your server:
```bash
ln -s ~/modular_trade_agent/UBUNTU_COMMANDS.md ~/commands.md
cat ~/commands.md  # Quick access!
```
