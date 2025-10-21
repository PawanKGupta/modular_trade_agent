# Modular Trade Agent

A professional-grade **cloud-automated trading system** for Indian stock markets (NSE) that specializes in **uptrend dip-buying** using multi-timeframe analysis with **historical backtesting validation**. The system runs automatically on GitHub Actions, identifies high-probability oversold bounces in strong uptrending stocks, validates them against 2-year historical performance, and delivers institutional-quality trade alerts via Telegram.

## ✨ **NEW: Cloud Automation & Intelligent Backtesting**

🚀 **GitHub Actions Integration**: Fully automated cloud execution at 4PM IST weekdays - no laptop required!

🧠 **Intelligent Backtesting Scoring**: Every stock candidate is validated against 2 years of historical performance using the same RSI10 strategy, providing a **Combined Score** (50% current analysis + 50% historical performance) for superior trade selection.

📊 **Enhanced Risk Management**: Stocks with poor historical track records or insufficient data are automatically filtered out, preventing false signals and improving overall system reliability.

## 🚀 Key Features

### ☁️ **Cloud Automation**
- **GitHub Actions Integration**: Runs automatically at 4PM IST weekdays
- **Zero Maintenance**: No laptop/server maintenance required
- **Chrome/Selenium Support**: Full web scraping capabilities in the cloud
- **Telegram Integration**: Instant notifications with comprehensive trade data

### 🧠 **Intelligent Backtesting**
- **2-Year Historical Validation**: Every stock tested against historical performance
- **Combined Scoring System**: 50% current analysis + 50% backtest performance
- **RSI10 Strategy Validation**: Uses same strategy rules for consistency
- **Automatic Filtering**: Stocks with poor history or insufficient data excluded

### 📊 **Multi-Timeframe Analysis (MTF)**
- **Daily + Weekly Confirmation**: Analyzes both timeframes for maximum probability
- **Uptrend Dip-Buying Focus**: Specializes in buying temporary dips in strong uptrends
- **Smart Alignment Scoring**: 0-10 scoring system for setup quality assessment
- **Support Level Analysis**: Identifies and tracks key support/resistance levels

### 🎯 **Professional Entry Strategy**
- **RSI < 30 Oversold Filtering**: Only considers truly oversold conditions
- **EMA200 Uptrend Confirmation**: Ensures stocks are above long-term moving average
- **Support Proximity Filtering**: Prioritizes entries very close to support levels (0-2% away)
- **Volume Exhaustion Analysis**: Detects selling pressure weakening

### 💰 **Advanced Risk Management**
- **Support-Based Stop Losses**: Stops placed just below key support levels (5-6% typical)
- **Resistance-Aware Targets**: Profit targets respect overhead resistance levels
- **Dynamic Buy Ranges**: Tight 0.6% entry ranges for precise execution
- **Risk-Reward Optimization**: Targets 2-4x risk-reward ratios

### 📱 **Enhanced Trade Alerts**
- **Backtest-Enhanced Messages**: Includes 2-year historical performance data
- **Combined Scoring**: Stocks ranked by current analysis + historical performance
- **Performance Metrics**: Win rate, total returns, trade count from backtesting
- **Quality Indicators**: Support distance, RSI severity, volume analysis
- **Fundamental Context**: PE ratios, news sentiment, and valuation assessments
- **Smart Filtering**: Only sends alerts for stocks that pass all validation checks

### 🔧 **Enhanced System Features**
- **CSV Export System**: Complete analysis data export for record-keeping
- **Quality Filtering**: Multiple layers of fundamental, volume, and setup filters  
- **Robust Error Handling**: Circuit breakers and exponential backoff retry logic
- **Data Validation**: Ensures sufficient historical data for accurate analysis

## 📋 Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Backtesting Module](#backtesting-module)
- [Project Structure](#project-structure)
- [Technical Indicators](#technical-indicators)
- [Signal Types](#signal-types)
- [Error Handling](#error-handling)
- [Logging](#logging)
- [Contributing](#contributing)

## 🛠 Installation

### Prerequisites

- Python 3.8 or higher
- Windows/Linux/macOS
- Internet connection for data fetching

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd modular_trade_agent
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   
   # Linux/macOS
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `cred.env` file with your Telegram credentials:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   ```

## ⚙️ Configuration

### Environment Variables

The system supports various configuration options through environment variables:

```env
# Retry Configuration
RETRY_MAX_ATTEMPTS=3
RETRY_BASE_DELAY=1.0
RETRY_MAX_DELAY=30.0
RETRY_BACKOFF_MULTIPLIER=2.0

# Circuit Breaker Configuration
CIRCUITBREAKER_FAILURE_THRESHOLD=3
CIRCUITBREAKER_RECOVERY_TIMEOUT=60.0

# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Trading Parameters

Modify `config/settings.py` to adjust trading parameters:

```python
LOOKBACK_DAYS = 90                    # Historical data period
MIN_VOLUME_MULTIPLIER = 1.0           # Minimum volume threshold
RSI_OVERSOLD = 30                     # RSI oversold level
VOLUME_MULTIPLIER_FOR_STRONG = 1.2    # Strong volume threshold
```

## 🚀 Usage

### Basic Usage

Run the trading agent:

```bash
python trade_agent.py
```

### Command Line Options

```bash
# Standard run with all features
python trade_agent.py

# Enable backtest scoring (slower but more accurate)
python trade_agent.py --backtest

# Disable CSV export (faster execution)
python trade_agent.py --no-csv

# Disable multi-timeframe analysis (single timeframe only)
python trade_agent.py --no-mtf

# Minimal run (no CSV, no MTF)
python trade_agent.py --no-csv --no-mtf

# Complete analysis with backtest validation
python trade_agent.py --backtest
```

### System Process

The system will:
1. **Stock Scraping**: Automatically fetch current stock list from ChartInk screener
2. **Data Fetching**: Download daily and weekly OHLCV data for all stocks
3. **Multi-Timeframe Analysis**: Analyze daily + weekly trends for alignment
4. **Support/Resistance Analysis**: Identify key levels and proximity
5. **Quality Filtering**: Apply fundamental, volume, and setup filters
6. **Signal Generation**: Create STRONG BUY/BUY/WATCH recommendations
7. **Historical Validation**: Run 2-year backtests on each candidate (if enabled)
8. **Combined Scoring**: Merge current analysis with historical performance
9. **Smart Filtering**: Exclude stocks with data issues or poor track records
10. **CSV Export**: Save complete analysis data for record-keeping
11. **Enhanced Telegram Alerts**: Send trade alerts with backtest performance data

### Custom Stock List

Modify the stock list in `trade_agent.py`:

```python
def get_stocks():
    stocks = "NAVA, GLENMARK, VGL, HYUNDAI, ENRIN"
    return [s.strip().upper() + ".NS" for s in stocks.split(",")]
```

### Manual Testing

Test individual components:

```python
from core.analysis import analyze_ticker
result = analyze_ticker("RELIANCE.NS")
print(result)
```

## 🔬 Backtesting Module

The system includes a sophisticated backtesting framework for evaluating the **EMA200 + RSI10 Pyramiding Strategy**.

### 🎥 Quick Start

```bash
# Basic backtest
python run_backtest.py RELIANCE.NS 2022-01-01 2023-12-31

# With detailed analysis
python run_backtest.py ORIENTCEM.NS 2025-01-15 2025-06-15 --export-trades --generate-report

# Custom capital per position
python run_backtest.py TCS.NS 2023-01-01 2024-12-31 --capital 200000
```

### 📋 Strategy Rules

The backtesting module implements a precise **pyramiding averaging-down strategy**:

#### **Initial Entry**
- ✅ **Price > EMA200** AND **RSI10 < 30**
- 💰 **Capital**: ₹100,000 per position
- 🗺 **Execution**: Next day's opening price

#### **Pyramiding Entries** (No EMA200 Check)
1. **RSI < 10**: First time immediate, subsequent times need RSI > 30 reset
2. **RSI < 20**: First time immediate, subsequent times need RSI > 30 reset
3. **RSI < 30**: Always needs RSI > 30 reset (after initial entry)

#### **Key Features**
- 📈 **TradingView-Accurate RSI**: Perfect match with TradingView calculations
- 🔄 **Smart Reset Logic**: Prevents over-trading with proper cycle detection
- 🗺 **Auto Data Adjustment**: Automatically extends data period for reliable EMA200
- 📏 **Maximum 10 Positions**: Controlled risk with position limits

### 📈 Performance Analytics

```python
from backtest import BacktestEngine, PerformanceAnalyzer

# Run backtest
engine = BacktestEngine("RELIANCE.NS", "2022-01-01", "2023-12-31")
results = engine.run_backtest()

# Detailed analysis
analyzer = PerformanceAnalyzer(engine)
report = analyzer.generate_report(save_to_file=True)
trades_csv = analyzer.export_trades_to_csv()
```

### 📄 Sample Results

```
============================================================
BACKTEST SUMMARY - ORIENTCEM.NS
============================================================
Period: 2025-01-15 to 2025-06-15
Total Trades: 5
Total Return: -9.89%
Win Rate: 0.0% (challenging market period)
Strategy vs Buy & Hold: +3.58%
🎉 Strategy OUTPERFORMED buy & hold!
============================================================
```

### 🗂 Available Commands

```bash
# Run examples with multiple scenarios
python backtest_example.py

# Command line options
python run_backtest.py SYMBOL START END [OPTIONS]
  --capital AMOUNT         Capital per position (default: 100000)
  --rsi-period PERIOD      RSI period (default: 10)
  --ema-period PERIOD      EMA period (default: 200)
  --max-positions MAX      Maximum positions (default: 10)
  --no-pyramiding          Disable pyramiding
  --export-trades          Export trades to CSV
  --generate-report        Generate performance report
  --save-report            Save report to file
```

### 🎯 Advanced Features

- **Risk Metrics**: Maximum drawdown, Sharpe ratio, VaR analysis
- **Trade Statistics**: Win rates, holding periods, consecutive trades
- **Time Analysis**: Monthly performance, seasonal patterns
- **CSV Export**: Detailed trade-by-trade data for further analysis
- **Automated Recommendations**: Strategy optimization suggestions
- **Multi-Stock Comparison**: Compare performance across different stocks

## 📁 Project Structure

```
modular_trade_agent/
├── .github/                 # ✨ GitHub Actions Workflow
│   └── workflows/
│       └── trading-agent.yml    # Automated cloud execution at 4PM IST
├── backtest/                # 🆕 Advanced Backtesting Framework
│   ├── __init__.py          # Package initialization
│   ├── backtest_config.py   # Backtesting configuration settings
│   ├── backtest_engine.py   # Core backtesting logic with pyramiding
│   ├── position_manager.py  # Position tracking and trade management
│   ├── performance_analyzer.py # Advanced analytics and reporting
│   └── README.md           # Detailed backtesting documentation
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuration parameters
├── core/
│   ├── __init__.py
│   ├── analysis.py          # Main analysis logic with enhanced filters
│   ├── backtest_scoring.py  # ✨ Historical backtest scoring integration
│   ├── csv_exporter.py      # CSV export system for analysis data
│   ├── data_fetcher.py      # Multi-timeframe data retrieval with retry logic
│   ├── indicators.py        # Technical indicators (RSI, EMA, etc.)
│   ├── patterns.py          # Candlestick patterns
│   ├── scoring.py           # Signal strength scoring
│   ├── scrapping.py         # Web scraping utilities with ChartInk integration
│   ├── telegram.py          # Enhanced Telegram messaging
│   └── timeframe_analysis.py # Multi-timeframe dip-buying analysis engine
├── utils/
│   ├── __init__.py
│   ├── circuit_breaker.py   # Circuit breaker implementation
│   ├── logger.py            # Logging configuration
│   └── retry_handler.py     # Retry logic with exponential backoff
├── Test/
│   ├── backtesting.py      # Legacy backtesting utilities
│   ├── backtest_stocks.py  # Stock backtesting
│   ├── debug_test.py       # Debug utilities
│   └── volume_analysis.py  # Volume analysis
├── backtest_reports/       # 🆕 Generated backtest reports
├── backtest_exports/       # 🆕 Exported trade data (CSV)
├── logs/                   # Log files
├── cred.env               # Environment variables (create this)
├── requirements.txt       # Python dependencies
├── trade_agent.py        # Main execution script with backtest integration
├── test_telegram.py      # ✨ Telegram connection testing
├── test_backtest_integration.py # ✨ Backtest integration testing
├── integrated_backtest.py # ✨ Comprehensive backtest workflow
├── run_backtest.py       # 🆕 Backtesting command-line interface
├── backtest_example.py   # 🆕 Backtesting examples and demonstrations
└── README.md            # This file
```

## 📊 Technical Indicators

The system uses advanced multi-timeframe technical analysis:

### **Core Indicators**
- **RSI (14-period)**: Identifies oversold conditions (RSI < 30 for entries)
- **EMA 200**: Long-term uptrend confirmation (price must be > EMA200)
- **Support/Resistance Levels**: Dynamic identification of key price levels
- **Volume Exhaustion**: Analyzes selling pressure and volume patterns

### **Multi-Timeframe Analysis**
- **Daily Analysis**: Short-term oversold conditions and support proximity
- **Weekly Analysis**: Long-term uptrend confirmation and momentum
- **Alignment Scoring**: 0-10 score measuring daily+weekly trend agreement
- **Confluence Factors**: Support level agreement across timeframes

## 🎯 Signal Classification

### 🔥 STRONG BUY Signals
Generated when:
- ✅ **Excellent uptrend dip** (MTF score 8-9/10) + good fundamentals (PE < 25)
- ✅ **Very close to strong support** (0-1% distance)
- ✅ **Extreme/High oversold** (RSI < 30, preferably < 25)
- ✅ **Volume exhaustion signs** (selling pressure weakening)
- ✅ **Strong uptrend confirmation** (Price > EMA200 + weekly alignment)

### 📈 BUY Signals  
Generated when:
- ✅ **Good uptrend dip** (MTF score 6-7/10)
- ✅ **Close to support** (0-2% distance from strong support)
- ✅ **RSI oversold** (RSI < 30)
- ✅ **Reasonable fundamentals** or volume confirmation
- ✅ **Uptrend context** (Price > EMA200)

### 👀 WATCH Signals
Generated when:
- ⚠️ **Moderate setups** missing key confirmation factors
- ⚠️ **Too far from support** (>4% away from support levels)
- ⚠️ **Weak fundamental quality** or poor volume patterns
- ⚠️ **Lower MTF alignment** (score < 6/10)

### ❌ No Signal Generated When:
- Stock not in uptrend (Price < EMA200)
- RSI not oversold (RSI > 30)
- Very poor MTF alignment (score < 3/10)
- Insufficient data for analysis

## 🛡 Error Handling

The system includes robust error handling:

### Retry Logic
- **Exponential Backoff**: Automatic retry with increasing delays
- **Jitter**: Random delay variation to prevent thundering herd
- **Configurable**: Adjustable retry attempts and delays

### Circuit Breaker
- **Fail Fast**: Prevents cascade failures from unreliable services
- **Auto Recovery**: Automatically tests service recovery
- **State Management**: CLOSED → OPEN → HALF_OPEN states

### Error Categories
- `no_data`: No market data available
- `data_error`: Data fetching/processing failed
- `indicator_error`: Technical indicator calculation failed
- `analysis_error`: General analysis failure

## 📝 Logging

Comprehensive logging system:

- **Console Output**: Real-time execution status
- **File Logging**: Detailed logs in `logs/trade_agent.log`
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Structured Logging**: Timestamped with module information

## 📈 Sample Output

### Console Output
```
2025-10-19 00:15:49 — INFO — circuit_breaker — Circuit breaker 'YFinance_API' initialized
2025-10-19 00:15:51 — SUCCESS — HYUNDAI.NS: buy
2025-10-19 00:15:52 — SUCCESS — RELIANCE.NS: watch
2025-10-19 00:15:53 — WARNING — VGL.NS: data_error - Insufficient data
2025-10-19 00:15:54 — INFO — telegram — Telegram message sent successfully
```

### Enhanced Telegram Alert with Backtest Data
```
Reversal Buy Candidates (today) with Backtest Scoring

🔥 STRONG BUY (Multi-timeframe confirmed):
1. NAVA.NS:
	Buy (603.68-607.32)
	Target 713.05 (+17.2%)
	Stop 571.76 (-6.0%)
	RSI:22.97
	MTF:8/10
	RR:2.9x
	StrongSupp:0.5% HighRSI NearSupport
	PE:16.8
	Vol:0.9x
	News:Neu +0.00 (0)
	Backtest: 35/100 (+4.2% return, 100% win, 3 trades)
	Combined Score: 67.3/100

📈 BUY candidates:
1. GLENMARK.NS:
	Buy (1849.83-1860.97)
	Target 2073.97 (+11.4%)
	Stop 1750.19 (-6.0%)
	RSI:24.0
	MTF:8/10
	RR:1.9x
	StrongSupp:0.3% HighRSI VolExh NearSupport
	PE:69.9
	Vol:1.2x
	News:Pos +0.15 (2)
	Backtest: 36/100 (+9.4% return, 100% win, 2 trades)
	Combined Score: 68.1/100
```

### Terms Explanation
- **MTF:8/10**: Multi-timeframe alignment score (daily+weekly trend agreement)
- **RR:2.9x**: Risk-reward ratio (potential gain ÷ potential loss)
- **StrongSupp:0.5%**: Distance to strong support level
- **HighRSI/ExtremeRSI**: Oversold severity (High: RSI 20-30, Extreme: RSI <20)
- **NearSupport/CloseSupport**: Proximity to support (Near: <1%, Close: <2%)
- **VolExh**: Volume exhaustion detected (selling pressure weakening)
- **PE:16.8**: Price-to-earnings ratio for valuation context
- **Vol:0.9x**: Volume ratio vs average (above 1.5x = high, below 0.6x = low)
- **News:Neu +0.00 (0)**: News sentiment (Pos/Neg/Neu, score, article count)
- **Backtest:35/100**: Historical performance score over 2 years
- **Combined Score:67.3/100**: Final ranking (50% current + 50% historical)

## 📄 CSV Export & Analysis Data

The system automatically exports comprehensive analysis data to CSV files:

### **Export Files Generated**
```
analysis_results/
├── bulk_analysis_YYYYMMDD_HHMMSS.csv    # Latest batch analysis
├── master_analysis.csv                   # Historical master file
└── [TICKER]_analysis_YYYYMMDD_HHMMSS.csv  # Individual stock files
```

### **CSV Data Fields (40+ columns)**
- **Basic Info**: Timestamp, ticker, verdict, last_close, signals
- **Trading Parameters**: buy_range_low/high, target, stop, potential_gain_pct
- **Technical Indicators**: RSI, PE, PB, volume ratios
- **MTF Analysis**: alignment_score, confirmation, daily/weekly analysis details
- **Support/Resistance**: Quality, distance, levels for both timeframes
- **Setup Quality**: Oversold conditions, volume exhaustion, reversion scores

### **Using CSV Data**
```python
import pandas as pd

# Load latest analysis
df = pd.read_csv('analysis_results/bulk_analysis_latest.csv')

# Filter strong buys
strong_buys = df[df['verdict'] == 'strong_buy']

# Analyze by MTF score
high_quality = df[df['mtf_alignment_score'] >= 8]

# Export filtered results
strong_buys.to_csv('filtered_strong_buys.csv', index=False)
```

## 🚀 Getting Started

### Live Trading Signals
```bash
# Run the main trading system
python trade_agent.py

# With custom options
python trade_agent.py --no-csv --no-mtf
```

### Strategy Backtesting
```bash
# Quick backtest
python run_backtest.py RELIANCE.NS 2022-01-01 2023-12-31

# Comprehensive analysis
python run_backtest.py ORIENTCEM.NS 2025-01-15 2025-06-15 --export-trades --generate-report

# Try multiple examples
python backtest_example.py
```

### Programmatic Usage
```python
# Live analysis
from core.analysis import analyze_ticker
result = analyze_ticker("RELIANCE.NS")

# Backtesting
from backtest import BacktestEngine, PerformanceAnalyzer
engine = BacktestEngine("RELIANCE.NS", "2022-01-01", "2023-12-31")
results = engine.run_backtest()
analyzer = PerformanceAnalyzer(engine)
report = analyzer.generate_report(save_to_file=True)
```

## 🔧 Troubleshooting

### Common Issues

1. **No data for stocks**: Check ticker symbols (should end with `.NS` for NSE)
2. **Telegram not working**: Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
3. **Module import errors**: Ensure virtual environment is activated
4. **Unicode errors**: Check console encoding settings

### Debug Mode

Enable debug logging in `utils/logger.py`:
```python
logger.setLevel(logging.DEBUG)
```

## 🚀 Cloud Deployment (Recommended)

### GitHub Actions Automation

The system is **pre-configured** to run automatically on GitHub Actions:

1. **Fork/Clone this repository** to your GitHub account
2. **Set up Secrets** in your repository:
   - Go to Settings → Secrets and variables → Actions
   - Add `TELEGRAM_BOT_TOKEN` with your bot token
   - Add `TELEGRAM_CHAT_ID` with your chat ID
3. **Enable GitHub Actions** (usually enabled by default)
4. **Done!** The system will run automatically at 4PM IST weekdays

**Benefits of Cloud Automation:**
- ✅ **Zero Maintenance**: No laptop/server management
- ✅ **Always Running**: Never miss market opportunities
- ✅ **Free Execution**: GitHub provides free Actions minutes
- ✅ **Full Chrome Support**: Web scraping works perfectly
- ✅ **Reliable Notifications**: Telegram alerts always delivered

### Local Automation (Alternative)

If you prefer running locally:

**Windows Task Scheduler**:
```batch
cd C:\path\to\modular_trade_agent
.venv\Scripts\python.exe trade_agent.py --backtest
```

**Linux Cron**:
```bash
30 10 * * 1-5 cd /path/to/modular_trade_agent && .venv/bin/python trade_agent.py --backtest
```

### Monitoring
- Monitor log files for errors
- Set up Telegram alerts for system failures
- Track signal performance over time

## 📄 License

This project is for educational and personal use only. Please comply with your broker's API terms and local trading regulations.

## ⚠️ Disclaimer

This software is for educational purposes only. It is not financial advice. Trading involves risk, and you should consult with a qualified financial advisor before making investment decisions. The authors are not responsible for any financial losses incurred through the use of this software.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For questions or issues:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review log files for error details
3. Create an issue with detailed error information