# Modular Trade Agent - Linux Executable

## Quick Start Guide

### First Time Setup

1. **Extract Files**
   ```bash
   tar -xzf ModularTradeAgent-Linux-v1.0.0.tar.gz
   cd ModularTradeAgent-Linux-v1.0.0
   ```

2. **Create Configuration File**
   ```bash
   cp kotak_neo.env.example kotak_neo.env
   nano kotak_neo.env  # or vi, vim, gedit, etc.
   ```
   
Edit with your Kotak Neo credentials:
```env
KOTAK_CONSUMER_KEY=your_key_here
KOTAK_CONSUMER_SECRET=your_secret_here
KOTAK_MOBILE_NUMBER=9876543210
KOTAK_PASSWORD=your_password
KOTAK_MPIN=123456
KOTAK_ENVIRONMENT=prod
```

3. **Make Scripts Executable**
   ```bash
   chmod +x *.sh ModularTradeAgent
   ```

4. **Run the Application**
   ```bash
   ./start.sh
   # or directly:
   ./ModularTradeAgent
   ```

### What's Included

```
ModularTradeAgent/
  ├── ModularTradeAgent           ← Main application (executable)
  ├── start.sh                    ← Easy launcher
  ├── backup_data.sh              ← Backup utility
  ├── health_check.sh             ← System monitor
  ├── install_service.sh          ← Service installer
  ├── uninstall_service.sh        ← Service uninstaller
  ├── kotak_neo.env.example       ← Config template
  ├── README.md                   ← This file
  ├── data/                       ← Trade history (auto-created)
  └── documents/                  ← Documentation
```

## System Requirements

- **OS**: Ubuntu 20.04+, Debian 10+, CentOS 8+, or any modern Linux (x86_64)
- **Python**: NOT required! ✅
- **Internet**: Required for API calls
- **RAM**: Minimum 2 GB
- **Disk Space**: 200 MB

## Features

✅ **Automated Trading**
- Reads buy/sell signals from analysis
- Places AMO orders before market open
- Manages positions with RSI/EMA exit strategies

✅ **Position Monitoring**
- Real-time position tracking
- Automatic exit on conditions met
- Telegram notifications

✅ **Retry Logic**
- Handles insufficient balance
- Retries failed orders
- Quantity mismatch handling

✅ **EOD Cleanup**
- Daily reconciliation
- Manual trade detection
- Position summaries

## Running as systemd Service

### Install Service

```bash
sudo ./install_service.sh
```

This sets up:
- **Buy orders**: Daily at 4:00 PM IST (Mon-Fri)
- **Sell orders**: Daily at 9:15 AM IST (Mon-Fri)
- **Auto-start**: Service runs automatically on boot

### Manage Service

```bash
# View service status
systemctl status tradeagent-buy.timer
systemctl status tradeagent-sell.timer

# View logs
journalctl -u tradeagent-buy.service -f
journalctl -u tradeagent-sell.service -f

# Manual execution
systemctl start tradeagent-buy.service
systemctl start tradeagent-sell.service

# Stop service
systemctl stop tradeagent-buy.timer
systemctl stop tradeagent-sell.timer

# Uninstall service
sudo ./uninstall_service.sh
```

## Configuration

### Environment Variables

Edit `kotak_neo.env`:

| Variable | Description | Example |
|----------|-------------|---------|
| `KOTAK_NEO_CONSUMER_KEY` | API Consumer Key | `abc123...` |
| `KOTAK_NEO_CONSUMER_SECRET` | API Consumer Secret | `xyz789...` |
| `KOTAK_NEO_MOBILE_NUMBER` | Registered mobile | `9876543210` |
| `KOTAK_NEO_PASSWORD` | Login password | `MyPass@123` |
| `KOTAK_NEO_MPIN` | M-PIN for transactions | `123456` |

### Optional Settings

Additional settings in `kotak_neo.env`:

```env
# Trading Configuration
MAX_PORTFOLIO_SIZE=10
CAPITAL_PER_TRADE=100000
MIN_QTY=1

# Exit Strategy
EXIT_ON_EMA9_OR_RSI50=true

# Telegram Notifications (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Logs and Data

### Log Files
```bash
# View logs in real-time
tail -f logs/trade_agent_$(date +%Y%m%d).log

# Search for errors
grep ERROR logs/trade_agent_*.log

# View last 100 lines
tail -100 logs/trade_agent_$(date +%Y%m%d).log
```

### Trade History
- Location: `data/trades_history.json`
- Backup regularly for record-keeping:
  ```bash
  ./backup_data.sh
  ```

### Failed Orders
- Automatically retried until market open
- Cleared after successful placement

## Troubleshooting

### Application Won't Start

**Symptom**: Permission denied or file not found
- **Solution**: Make executable
  ```bash
  chmod +x ModularTradeAgent start.sh
  ./ModularTradeAgent
  ```

### Login Failed

**Symptom**: "Authentication failed" error
- **Check**: Credentials in `kotak_neo.env` are correct
- **Check**: Mobile number format (no +91 prefix)
- **Check**: MPIN is 6 digits

### Orders Not Placing

**Symptom**: "Insufficient balance" errors
- **Check**: Account has sufficient cash
- **Action**: Orders will retry automatically

### Permission Errors

**Symptom**: "Permission denied" when creating files
- **Solution**: Check file/directory permissions
  ```bash
  chmod 755 .
  chmod 644 kotak_neo.env
  chmod 755 *.sh ModularTradeAgent
  ```

## Health Check

Run system diagnostics:

```bash
./health_check.sh
```

This checks:
- Executable status
- Configuration validity
- Data directory
- Disk space
- Memory availability
- Internet connectivity
- Service status
- Log files

## Backup & Restore

### Create Backup
```bash
./backup_data.sh
```

Creates timestamped backup in `backups/` directory.

### Restore from Backup
```bash
# List available backups
ls -lh backups/

# Extract backup
tar -xzf backups/backup_20251028_120000.tar.gz -C backups/

# Restore files
cp -r backups/backup_20251028_120000/* .
```

## Security Best Practices

1. **Protect Credentials**
   ```bash
   chmod 600 kotak_neo.env
   ```
   - Never share or commit to version control
   - Use strong passwords

2. **Regular Backups**
   - Backup `data/trades_history.json` weekly
   - Keep copies of successful configurations

3. **Test Before Live**
   - Test with small quantities first
   - Verify exit strategies work as expected
   - Monitor for first few days

4. **Monitor Execution**
   - Check trade history daily
   - Verify orders placed correctly
   - Watch for Telegram alerts

## Updating

When a new version is released:

1. **Backup your data**:
   ```bash
   ./backup_data.sh
   ```

2. **Download new version**:
   ```bash
   wget https://github.com/your-repo/ModularTradeAgent-Linux-v1.1.0.tar.gz
   ```

3. **Extract to new directory**:
   ```bash
   tar -xzf ModularTradeAgent-Linux-v1.1.0.tar.gz
   cd ModularTradeAgent-Linux-v1.1.0
   ```

4. **Restore configuration**:
   ```bash
   cp ../ModularTradeAgent-Linux-v1.0.0/kotak_neo.env .
   cp -r ../ModularTradeAgent-Linux-v1.0.0/data .
   ```

5. **Reinstall service** (if using):
   ```bash
   sudo ./uninstall_service.sh  # From old directory
   sudo ./install_service.sh    # From new directory
   ```

## Support

### Common Questions

**Q: Do I need Python installed?**
A: No! The executable is completely standalone.

**Q: Can I run multiple instances?**
A: Not recommended. Use one instance per trading account.

**Q: What happens if my system restarts?**
A: If installed as a service, it will auto-start.

**Q: Can I modify the trading strategy?**
A: Not in the executable. You need the source code for customization.

### Getting Help

1. **Check logs** for error messages
2. **Run health check**: `./health_check.sh`
3. **Review documentation** in `documents/` folder
4. **Verify configuration** in `kotak_neo.env`
5. **Test with small amounts** first

## Disclaimer

⚠️ **Important**: 
- This is trading automation software
- Use at your own risk
- Test thoroughly before live trading
- Monitor automated trades regularly
- Understand the trading strategy before using

## Version Information

- **Application**: Modular Trade Agent
- **Version**: 26.1.1
- **Build Date**: 2025-10-28
- **Platform**: Linux x86_64

---

**Ready to start?** 
1. Configure `kotak_neo.env`
2. Run `./start.sh`
3. Monitor your first automated trades!

Happy Trading! 🚀📈
