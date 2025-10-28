# Modular Trade Agent - Windows Executable

## Quick Start Guide

### First Time Setup

1. **Extract Files**
   - Extract all files to a folder (e.g., `C:\TradingAgent`)

2. **Create Configuration File**
   - Rename `kotak_neo.env.example` to `kotak_neo.env`
   - Edit with your Kotak Neo credentials:
     ```env
     KOTAK_NEO_CONSUMER_KEY=your_key_here
     KOTAK_NEO_CONSUMER_SECRET=your_secret_here
     KOTAK_NEO_MOBILE_NUMBER=9876543210
     KOTAK_NEO_PASSWORD=your_password
     KOTAK_NEO_MPIN=123456
     ```

3. **Run the Application**
   - Double-click `START.bat` or `ModularTradeAgent.exe`

### What's Included

```
ModularTradeAgent/
  ├── ModularTradeAgent.exe    ← Main application
  ├── START.bat                ← Easy launcher
  ├── kotak_neo.env.example    ← Template for your credentials
  ├── README.md                ← This file
  └── data/                    ← Trade history (created automatically)
```

## System Requirements

- **OS**: Windows 10/11 (64-bit)
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

## Running as Scheduled Task

### Option 1: Windows Task Scheduler

1. Open **Task Scheduler**
2. Create **Basic Task**:
   - Name: `Trading Agent`
   - Trigger: `Daily at 8:00 AM`
   - Action: `Start a program`
   - Program: `C:\TradingAgent\ModularTradeAgent.exe`
   - Start in: `C:\TradingAgent`

### Option 2: Startup Service (Using NSSM)

1. Download NSSM: https://nssm.cc/download
2. Install as service:
   ```cmd
   nssm install TradingAgent "C:\TradingAgent\ModularTradeAgent.exe"
   nssm set TradingAgent AppDirectory "C:\TradingAgent"
   nssm set TradingAgent Start SERVICE_AUTO_START
   nssm start TradingAgent
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

Additional settings can be added to `kotak_neo.env`:

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
- Console output shows real-time logs
- Redirect to file: `ModularTradeAgent.exe > logs.txt 2>&1`

### Trade History
- Location: `data/trades_history.json`
- Backup regularly for record-keeping

### Failed Orders
- Automatically retried until market open
- Cleared after successful placement

## Troubleshooting

### Application Won't Start

**Symptom**: Double-click does nothing or immediate close
- **Solution**: Run from Command Prompt to see errors:
  ```cmd
  cd C:\TradingAgent
  ModularTradeAgent.exe
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

### Antivirus Warning

**Symptom**: Antivirus blocks or deletes .exe
- **Solution**: Add to antivirus exclusions
- **Reason**: PyInstaller executables sometimes flagged (false positive)

## Security Best Practices

1. **Protect Credentials**
   - Keep `kotak_neo.env` secure
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
   - Copy `kotak_neo.env`
   - Copy `data/` folder

2. **Replace executable**:
   - Delete old `ModularTradeAgent.exe`
   - Copy new `ModularTradeAgent.exe`

3. **Restore configuration**:
   - Keep your `kotak_neo.env` (no changes needed)
   - Keep your `data/` folder

## Support

### Common Questions

**Q: Do I need Python installed?**
A: No! The executable is completely standalone.

**Q: Can I run multiple instances?**
A: Not recommended. Use one instance per trading account.

**Q: What happens if my computer restarts?**
A: Set up as scheduled task or service to auto-start.

**Q: Can I modify the trading strategy?**
A: Not in the executable. You need the source code for customization.

### Getting Help

1. **Check logs** for error messages
2. **Review documentation** in `documents/` folder
3. **Verify configuration** in `kotak_neo.env`
4. **Test with small amounts** first

## Disclaimer

⚠️ **Important**: 
- This is trading automation software
- Use at your own risk
- Test thoroughly before live trading
- Monitor automated trades regularly
- Understand the trading strategy before using

## Version Information

- **Application**: Modular Trade Agent
- **Version**: 1.0.0
- **Build Date**: 2025-10-28
- **Platform**: Windows x64

---

**Ready to start?** 
1. Configure `kotak_neo.env`
2. Run `START.bat`
3. Monitor your first automated trades!

Happy Trading! 🚀📈
