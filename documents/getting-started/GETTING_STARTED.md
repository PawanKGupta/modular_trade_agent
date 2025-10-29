# 🚀 Getting Started with Modular Trade Agent

Welcome! This guide will help you set up and run the Modular Trade Agent system from scratch, even if you're new to Python or trading automation.

---

## 📋 Table of Contents

1. [What is This?](#what-is-this)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Detailed Setup](#detailed-setup)
4. [First Run](#first-run)
5. [Understanding the Output](#understanding-the-output)
6. [Next Steps](#next-steps)
7. [Common Issues](#common-issues)

---

## What is This?

The **Modular Trade Agent** is an automated trading analysis system that:

- ✅ **Analyzes** Indian stock markets (NSE) for trading opportunities
- ✅ **Identifies** oversold stocks in strong uptrends (reversal strategy)
- ✅ **Validates** signals using 2-year historical backtesting
- ✅ **Sends** trade alerts via Telegram with buy/sell recommendations
- ✅ **Runs** automatically in the cloud (GitHub Actions) or on your computer

**Think of it as:** Your personal trading research assistant that analyzes stocks and sends you trade recommendations!

---

## Quick Start (5 Minutes)

### For Windows Users (Easiest Method)

**Option 1: Use the Pre-Built Executable (No Python Required!)**

1. Download `ModularTradeAgent.exe` 
2. Double-click to run
3. Follow the on-screen prompts
4. Done! ✅

👉 **See:** [EXECUTABLE_README.md](../../EXECUTABLE_README.md) for details

**Option 2: Use the All-in-One Installer**

1. Download `ModularTradeAgent_Setup.exe`
2. Run as Administrator
3. Enter your Telegram credentials in the GUI
4. The installer handles everything automatically!

👉 **See:** [ALL_IN_ONE_INSTALLER_GUIDE.md](../ALL_IN_ONE_INSTALLER_GUIDE.md) for details

---

### For Developers (Full Setup)

Continue reading below for the complete Python setup.

---

## Detailed Setup

### Step 1: Check Prerequisites

You'll need:

- **Python 3.8+** - [Download Python](https://www.python.org/downloads/)
  - During install, check "Add Python to PATH"
- **Internet connection** - For downloading stock data
- **Telegram account** (optional) - For receiving trade alerts

**Check if Python is installed:**
```powershell
python --version
```
You should see: `Python 3.8.0` or higher

---

### Step 2: Download the Project

**Option A: Using Git (Recommended)**
```powershell
git clone https://github.com/your-repo/modular_trade_agent.git
cd modular_trade_agent
```

**Option B: Download ZIP**
1. Download the ZIP file from GitHub
2. Extract to a folder (e.g., `C:\TradingAgent`)
3. Open PowerShell in that folder

---

### Step 3: Set Up Virtual Environment

A virtual environment keeps this project's dependencies separate from other Python projects.

```powershell
# Create virtual environment
python -m venv .venv

# Activate it (Windows PowerShell)
.venv\Scripts\activate

# You should see (.venv) in your prompt now
```

**On Linux/Mac:**
```bash
source .venv/bin/activate
```

---

### Step 4: Install Dependencies

```powershell
# Install all required packages
pip install -r requirements.txt
```

This will take 2-5 minutes. You'll see packages being downloaded and installed.

---

### Step 5: Configure Telegram (Optional but Recommended)

To receive trade alerts on your phone:

**5.1: Create a Telegram Bot**
1. Open Telegram and search for `@BotFather`
2. Send: `/newbot`
3. Follow prompts to name your bot
4. **Copy the bot token** (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

**5.2: Get Your Chat ID**
1. Search for `@userinfobot` on Telegram
2. Send: `/start`
3. **Copy your chat ID** (looks like: `987654321`)

**5.3: Create Configuration File**

Create a file named `cred.env` in the project root:

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

Replace with your actual token and chat ID!

---

### Step 6: Test Telegram Connection (Optional)

```powershell
python test_telegram.py
```

You should receive a test message on Telegram! 🎉

---

## First Run

### Basic Analysis (Without Backtesting)

```powershell
python trade_agent.py
```

This will:
1. Fetch the latest stock list (takes ~30 seconds)
2. Analyze each stock (1-2 minutes for 10-20 stocks)
3. Generate buy/sell recommendations
4. Send Telegram alerts (if configured)
5. Save results to CSV files

**You'll see output like:**
```
2025-10-29 16:50:30 — INFO — Starting trade agent analysis...
2025-10-29 16:50:45 — SUCCESS — RELIANCE.NS: buy
2025-10-29 16:50:50 — SUCCESS — TCS.NS: strong_buy
2025-10-29 16:51:00 — INFO — Analysis complete! 2 BUY signals found.
```

---

### Advanced Analysis (With Backtesting)

For higher-quality signals validated against 2 years of history:

```powershell
python trade_agent.py --backtest
```

**This takes longer** (5-10 minutes) but provides much better signals with historical validation!

---

## Understanding the Output

### Console Output

```
2025-10-29 16:50:50 — SUCCESS — RELIANCE.NS: strong_buy
```

- **SUCCESS** = Signal generated
- **RELIANCE.NS** = Stock symbol (NSE)
- **strong_buy** = Signal strength (strong_buy > buy > watch > avoid)

---

### Telegram Alert Example

```
📈 BUY candidates (sorted by priority):

1. RELIANCE.NS:
   Buy (2850-2867)
   Target 3100 (+8.6%)
   Stop 2695 (-5.5%)
   RSI:23.18
   MTF:9/10
   RR:1.6x
   StrongSupp:0.3%
   PE:22.5
   Vol:1.2x
   News:Neu +0.00 (1)
   Backtest: 43/100 (+6.7% return, 100% win, 2 trades)
   Combined Score: 38.5/100
   Priority Score: 85 ✅ HIGH PRIORITY
```

**What does this mean?**

- **Buy (2850-2867)** = Buy between ₹2850-₹2867
- **Target 3100** = Sell target at ₹3100 (+8.6% profit)
- **Stop 2695** = Stop-loss at ₹2695 (-5.5% risk)
- **RSI:23.18** = Oversold level (good for reversal)
- **MTF:9/10** = Multi-timeframe alignment score (9/10 is excellent!)
- **RR:1.6x** = Risk-reward ratio (1.6:1)
- **PE:22.5** = Price-to-earnings ratio
- **Backtest:43/100** = Historical performance score
- **Priority Score:85** = Overall priority ranking

👉 **See:** [README.md](../../README.md) section "Terms Explanation" for complete glossary

---

### CSV Output

Results are saved in `analysis_results/`:
- `bulk_analysis_YYYYMMDD_HHMMSS.csv` - Latest run
- `bulk_analysis_final_*.csv` - Final filtered results

Open in Excel or Google Sheets for detailed analysis.

---

## Next Steps

### 1. Automate with GitHub Actions (Recommended)

Run automatically in the cloud at 4 PM IST weekdays:

1. Fork this repository to your GitHub account
2. Go to Settings → Secrets → Actions
3. Add secrets:
   - `TELEGRAM_BOT_TOKEN` = Your bot token
   - `TELEGRAM_CHAT_ID` = Your chat ID
4. Enable GitHub Actions
5. Done! System runs automatically ✅

👉 **See:** [README.md](../../README.md) section "Cloud Deployment"

---

### 2. Deploy to Cloud Server

For 24/7 operation with automated execution:

👉 **See:** [ORACLE_CLOUD_DEPLOYMENT.md](../ORACLE_CLOUD_DEPLOYMENT.md) - Free cloud deployment guide

---

### 3. Set Up Automated Trading (Optional)

To automatically place orders via broker API:

1. Get Kotak Neo API credentials
2. Configure execution module
3. Enable automated order placement

👉 **See:** [KOTAK_NEO_ARCHITECTURE_PLAN.md](../KOTAK_NEO_ARCHITECTURE_PLAN.md)

⚠️ **Warning:** Test thoroughly before enabling automated order placement!

---

### 4. Customize Your Strategy

Want to adjust trading parameters?

Edit `config/settings.py`:
```python
RSI_OVERSOLD = 30              # Change oversold threshold
MIN_VOLUME_MULTIPLIER = 1.0    # Adjust volume filter
LOOKBACK_DAYS = 90             # Change historical period
```

👉 **See:** [ARCHITECTURE_GUIDE.md](../ARCHITECTURE_GUIDE.md) for advanced customization

---

## Common Issues

### Issue 1: "Python not found"

**Solution:**
- Reinstall Python and check "Add Python to PATH"
- Or use full path: `C:\Python39\python.exe trade_agent.py`

---

### Issue 2: "Module not found" errors

**Solution:**
```powershell
# Make sure virtual environment is activated
.venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt
```

---

### Issue 3: "No stocks found"

**Possible causes:**
- Internet connection issue
- ChartInk screener temporarily unavailable
- Weekend/holiday (markets closed)

**Solution:**
- Check your internet connection
- Wait a few minutes and try again
- Run on a weekday during market hours

---

### Issue 4: "Telegram not working"

**Solution:**
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `cred.env`
- Test with: `python test_telegram.py`
- Make sure you've started a chat with your bot first

---

### Issue 5: Antivirus blocking executable

**Solution:**
- Add executable to antivirus exclusions
- This is a false positive (common with PyInstaller)
- Or use Python source code instead of executable

---

## Getting Help

### Documentation Index

👉 **[DOCUMENTATION_INDEX.md](../../DOCUMENTATION_INDEX.md)** - Complete documentation index

### Specific Guides

- **Command Reference:** [COMMANDS.md](../COMMANDS.md)
- **Architecture Details:** [ARCHITECTURE_GUIDE.md](../ARCHITECTURE_GUIDE.md)
- **Troubleshooting:** [README.md](../../README.md) - "Troubleshooting" section
- **Developer Setup:** [WARP.md](../../WARP.md)

### Support Channels

1. Check relevant documentation
2. Review troubleshooting sections
3. Check GitHub Issues
4. Create a new issue with details

---

## Congratulations! 🎉

You've successfully set up the Modular Trade Agent!

**What's happening now:**
- ✅ System analyzes stocks daily
- ✅ Identifies high-probability trading opportunities
- ✅ Validates against 2 years of historical data
- ✅ Sends you prioritized trade alerts

**Remember:**
- 📈 This is an analysis tool, not financial advice
- 🧪 Test with small amounts first
- 📚 Keep learning about the strategy
- ⚠️ Always use proper risk management

---

## Quick Command Reference

```powershell
# Basic run
python trade_agent.py

# With backtesting (recommended)
python trade_agent.py --backtest

# With dip-buying mode
python trade_agent.py --dip-mode

# Fast mode (no CSV export)
python trade_agent.py --no-csv

# Test Telegram
python test_telegram.py

# Run backtest for specific stock
python run_backtest.py RELIANCE.NS 2022-01-01 2023-12-31

# Activate virtual environment
.venv\Scripts\activate
```

---

## Glossary

- **NSE** - National Stock Exchange of India
- **RSI** - Relative Strength Index (momentum indicator)
- **EMA** - Exponential Moving Average (trend indicator)
- **MTF** - Multi-timeframe analysis
- **AMO** - After Market Order
- **PE** - Price-to-Earnings ratio
- **RR** - Risk-Reward ratio

---

**Happy Trading!** 📈

*This system is for educational purposes. Always consult with a financial advisor before making investment decisions.*

---

**Last Updated:** 2025-10-29  
**Version:** 1.0.0
