# Modular Trade Agent

A professional-grade **cloud-automated trading system** for Indian stock markets (NSE) that specializes in **core reversal strategy** using multi-timeframe analysis with **historical backtesting validation**. The system runs automatically on GitHub Actions, identifies high-probability oversold bounces in strong uptrending stocks with simplified decision logic, validates them against 2-year historical performance, and delivers institutional-quality trade alerts via Telegram.

## ✨ **NEW: Intelligent Priority Ranking & Enhanced Data Quality**

🚀 **GitHub Actions Integration**: Fully automated cloud execution at 4PM IST weekdays - no laptop required!

🧠 **Intelligent Backtesting Scoring**: Every stock candidate is validated against 2 years of historical performance using the same RSI10 strategy, providing a **Combined Score** (50% current analysis + 50% historical performance) for superior trade selection.

🎯 **Smart Priority Ranking**: Stocks are now ranked by trading priority within each category (Strong Buy, Buy) based on risk-reward ratio, RSI oversold levels, volume strength, and MTF alignment - ensuring the best trading opportunities appear first.

📈 **Enhanced News Sentiment**: Expanded news lookback period from 3 to 30 days for Indian stocks, providing meaningful sentiment analysis instead of zero values.

🛡️ **Data Leakage Prevention**: Backtesting now properly excludes current-day data to ensure accurate historical validation and prevent look-ahead bias.

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

### 🎯 **Simplified Core Reversal Strategy**
- **RSI < 30 Oversold Filtering**: Only considers truly oversold conditions (RSI10 period)
- **EMA200 Uptrend Confirmation**: Ensures stocks are above long-term moving average (800+ days data for accuracy)
- **Volume Quality Filter**: Minimum 70% of average volume (20-day) for liquidity, 50% for RSI < 30 oversold conditions
- **Fundamental Safety Check**: Flexible filter - avoids loss-making companies (PE < 0 + PB > 5.0), allows growth stocks (PE < 0 + PB < 5.0) with "watch" verdict
- **RSI30 Requirement**: Trading parameters only calculated when RSI < 30 (enforced for dip-buying strategy)
- **TradingView-Accurate EMA200**: Enhanced data fetching ensures calculation matches TradingView within 0.2%
- **Rule-Based Logic**: ML model temporarily disabled, using rule-based logic only until ML is fully trained

### 💰 **Advanced Risk Management**
- **Support-Based Stop Losses**: Stops placed just below key support levels (5-6% typical)
- **Resistance-Aware Targets**: Profit targets respect overhead resistance levels
- **Dynamic Buy Ranges**: Tight 0.6% entry ranges for precise execution
- **Risk-Reward Optimization**: Targets 2-4x risk-reward ratios
- **🆕 Chart Quality Filtering**: Automatically filters stocks with poor chart patterns (gaps, flat movement, extreme candles)
- **🆕 Dynamic Capital Allocation**: Automatically adjusts position size based on stock liquidity (10% of daily volume max)
- **🆕 Liquidity-Based Position Sizing**: Ensures safe position sizing based on average daily volume
- **🆕 Two-Stage ML Approach**: Chart quality filter (Stage 1) + ML model prediction (Stage 2) for improved accuracy

### 📱 **Enhanced Trade Alerts**
- **Smart Priority Ranking**: Stocks sorted by trading priority within each category using multi-factor scoring
- **Priority Factors**: Risk-reward ratio (40pts), RSI oversold levels (25pts), volume strength (20pts), MTF alignment (10pts)
- **Backtest-Enhanced Messages**: Includes 2-year historical performance data with win rates and returns
- **Combined Scoring**: Stocks ranked by current analysis + historical performance
- **Quality Indicators**: Support distance, RSI severity, volume exhaustion analysis
- **Enhanced News Sentiment**: 30-day lookback for meaningful sentiment analysis on Indian stocks
- **Fundamental Context**: PE ratios, earnings quality, and valuation assessments
- **Smart Filtering**: Only sends alerts for stocks that pass all validation checks

### 🔧 **Enhanced System Features**
- **CSV Export System**: Complete analysis data export for record-keeping (includes chart quality and capital info)
- **Quality Filtering**: Multiple layers of fundamental, volume, setup, and chart quality filters  
- **Robust Error Handling**: Circuit breakers and exponential backoff retry logic
- **Data Validation**: Ensures sufficient historical data for accurate analysis
- **🆕 Chart Quality Analysis**: Analyzes gaps, movement, and extreme candles to filter poor-quality charts
- **🆕 Automatic Capital Adjustment**: Dynamically adjusts capital based on liquidity to ensure safe position sizing
- **🆕 Two-Stage ML Integration**: ML models only see stocks that pass chart quality filtering, ensuring distribution match

## 📚 Documentation

**New to the project? Start here:**

- 🚀 **[Getting Started Guide](documents/getting-started/GETTING_STARTED.md)** - Complete beginner's setup walkthrough
- 📖 **[Documentation Index](documents/getting-started/DOCUMENTATION_INDEX.md)** - Comprehensive guide to all documentation
- 🔧 **[WARP.md](WARP.md)** - Developer setup and command reference
- 🪟 **[Windows Executable Guide](documents/deployment/windows/EXECUTABLE_README.md)** - No Python required!

**⭐ Comprehensive Guides (NEW):**
- 🏗️ **[System Architecture Evolution](documents/SYSTEM_ARCHITECTURE_EVOLUTION.md)** - Complete architectural transformation (Phases 1-4)
- 🤖 **[ML Implementation Guide](documents/ML_IMPLEMENTATION_GUIDE.md)** - Complete ML setup, training, and monitoring
- 📊 **[Chart Quality & Capital Adjustment](documents/features/CHART_QUALITY_AND_CAPITAL_ADJUSTMENT.md)** - 🆕 Chart quality filtering and dynamic capital adjustment features
- 🎯 **[Two-Stage ML Approach](documents/features/TWO_STAGE_CHART_QUALITY_ML_APPROACH.md)** - 🆕 Two-stage approach: Chart quality + ML model

**Quick Links:**
- [Architecture Guide](documents/architecture/ARCHITECTURE_GUIDE.md) - System design
- [Deployment Guide](documents/deployment/DEPLOYMENT_READY.md) - Production setup
- [Cloud Deployment](documents/deployment/oracle/ORACLE_CLOUD_DEPLOYMENT.md) - Free Oracle Cloud
- [Commands Reference](documents/reference/COMMANDS.md) - CLI commands
- [Testing Guide](documents/testing/TESTING_GUIDE_PHASE1_PHASE2.md) - Testing procedures

---

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

### Platform Guides
- Windows
  - Executable (no Python required): [Windows Executable](documents/deployment/windows/EXECUTABLE_README.md)
  - Unified Service (continuous): [Windows Unified Service](documents/deployment/windows/WINDOWS_UNIFIED_SERVICE.md)
  - Quick Reference: [Windows Quick Reference](documents/deployment/windows/WINDOWS_QUICK_REFERENCE.md)
- Ubuntu/Debian
  - Install Guide: [Ubuntu Install Guide](documents/deployment/ubuntu/INSTALL_UBUNTU.md)
  - Quickstart: [Ubuntu Quickstart](documents/deployment/ubuntu/UBUNTU_QUICKSTART.md)
  - Services Overview: [Services Comparison](documents/deployment/ubuntu/SERVICES_COMPARISON.md)
- Cloud
  - Oracle Cloud Free Tier: [Oracle Cloud Deployment](documents/deployment/oracle/ORACLE_CLOUD_DEPLOYMENT.md)
  - GCP Deployment: [GCP Deployment](documents/deployment/gcp/GCP_DEPLOYMENT.md)

### Prerequisites

- Python 3.12 or higher
- Windows/Linux/macOS
- Internet connection for data fetching


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
# Chart Quality Configuration
CHART_QUALITY_ENABLED=true
CHART_QUALITY_MIN_SCORE=60.0
CHART_QUALITY_MAX_GAP_FREQUENCY=20.0
CHART_QUALITY_MIN_DAILY_RANGE_PCT=1.5
CHART_QUALITY_MAX_EXTREME_CANDLE_FREQUENCY=15.0
CHART_QUALITY_ENABLED_IN_BACKTEST=true

# Capital & Liquidity Configuration
USER_CAPITAL=200000.0
MAX_POSITION_VOLUME_RATIO=0.10
MIN_ABSOLUTE_AVG_VOLUME=10000  # Lowered from 20,000 to allow more stocks

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

# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Trading Parameters

Modify `config/settings.py` to adjust trading parameters:

```python
LOOKBACK_DAYS = 90                    # Historical data period
MIN_VOLUME_MULTIPLIER = 0.7           # Minimum volume threshold (relaxed for dip-buying)
RSI_OVERSOLD = 30                     # RSI oversold level (required for trading parameters)
VOLUME_MULTIPLIER_FOR_STRONG = 1.2    # Strong volume threshold
MIN_ABSOLUTE_AVG_VOLUME = 10000       # Minimum absolute average volume (lowered from 20,000)
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

# Enable dip-buying mode with more permissive thresholds
python trade_agent.py --dip-mode

# Minimal run (no CSV, no MTF)
python trade_agent.py --no-csv --no-mtf

# Complete analysis with backtest validation
python trade_agent.py --backtest

# Complete analysis with backtest validation and dip-buying mode
python trade_agent.py --backtest --dip-mode
```

### System Process

The system will:
1. **Stock Scraping**: Automatically fetch current stock list from ChartInk screener
2. **Data Fetching**: Download daily and weekly OHLCV data for all stocks (with data leakage prevention)
3. **Multi-Timeframe Analysis**: Analyze daily + weekly trends for alignment
4. **Support/Resistance Analysis**: Identify key levels and proximity
5. **Quality Filtering**: Apply fundamental, volume, and setup filters
6. **Signal Generation**: Create STRONG BUY/BUY/WATCH recommendations
7. **Historical Validation**: Run 2-year backtests on each candidate (if enabled)
8. **Combined Scoring**: Merge current analysis with historical performance
9. **Priority Ranking**: Sort stocks by trading priority using multi-factor scoring system
10. **Smart Filtering**: Exclude stocks with data issues or poor track records
11. **CSV Export**: Save complete analysis data for record-keeping
12. **Enhanced Telegram Alerts**: Send prioritized trade alerts with backtest performance data


### Manual Testing

Test individual components:

**NEW (Recommended - Phase 4):**
```python
from services import AnalysisService

service = AnalysisService()
result = service.analyze_ticker("RELIANCE.NS")
print(result)
```

**OLD (Deprecated but still works):**
```python
from core.analysis import analyze_ticker  # ⚠️ Deprecated in Phase 4
result = analyze_ticker("RELIANCE.NS")  # Shows deprecation warning
print(result)
```

**For batch analysis (Async - Phase 2):**
```python
from services import AsyncAnalysisService
import asyncio

async def analyze():
    service = AsyncAnalysisService(max_concurrent=10)
    results = await service.analyze_batch_async(
        tickers=["RELIANCE.NS", "TCS.NS", "INFY.NS"],
        enable_multi_timeframe=True
    )
    return results

results = asyncio.run(analyze())
```

## 🔬 Backtesting Module

The system includes a sophisticated backtesting framework for evaluating the **EMA200 + RSI10 Pyramiding Strategy**.

### 🎥 Quick Start

See [Backtest README](documents/backtest/README.md) for full API usage. Example:

```python
from backtest import BacktestEngine, PerformanceAnalyzer
engine = BacktestEngine("RELIANCE.NS", "2022-01-01", "2023-12-31")
results = engine.run_backtest()
analyzer = PerformanceAnalyzer(engine)
report = analyzer.generate_report(save_to_file=True)
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
├── documents/                      # Project documentation
│   ├── architecture/               # Architecture design docs
│   ├── deployment/                 # Deployment guides
│   ├── features/                   # Feature documentation
│   ├── phases/                     # Phase completion docs
│   └── getting-started/            # Getting started guides
├── modules/
│   └── kotak_neo_auto_trader/      # Broker integration module
│       ├── run_trading_service.py  # Unified scheduler (continuous)
│       ├── auto_trade_engine.py
│       └── ...
├── services/                       # Service layer (Phase 1-4)
│   ├── analysis_service.py         # Main orchestrator
│   ├── data_service.py            # Data fetching
│   ├── indicator_service.py       # Technical indicators
│   ├── signal_service.py          # Signal detection
│   ├── verdict_service.py         # Verdict determination
│   ├── scoring_service.py         # Scoring (Phase 4)
│   ├── backtest_service.py        # Backtest integration (Phase 4)
│   ├── async_analysis_service.py  # Async batch analysis (Phase 2)
│   ├── cache_service.py           # Caching layer (Phase 2)
│   ├── event_bus.py               # Event-driven architecture (Phase 3)
│   ├── pipeline.py                 # Pipeline pattern (Phase 3)
│   └── models.py                  # Typed data classes (Phase 2)
├── src/                            # Clean architecture (legacy src/ pattern)
│   ├── application/               # Application layer
│   ├── domain/                     # Domain entities
│   └── infrastructure/             # Infrastructure adapters
├── core/                           # Legacy code (deprecated in Phase 4)
│   ├── analysis.py                 # ⚠️ DEPRECATED - Use services
│   ├── scoring.py                  # ⚠️ DEPRECATED - Use services
│   ├── backtest_scoring.py         # ⚠️ DEPRECATED - Use services
│   └── ...                         # Other legacy modules
├── config/                         # Configuration
│   ├── strategy_config.py          # Strategy parameters (Phase 1)
│   └── settings.py
├── backtest/                       # Backtesting framework
│   ├── backtest_engine.py
│   ├── performance_analyzer.py
│   └── README.md
├── tests/                          # Unit/integration tests
├── scripts/                        # Utility scripts
│   ├── validate_phase1.py
│   ├── validate_phase2.py
│   └── validate_all_phases.py
├── utils/                          # Utility modules
│   ├── deprecation.py              # Deprecation utilities (Phase 4)
│   └── logger.py
├── logs/                           # Log files
├── cred.env                        # Environment variables (create this)
├── requirements.txt                # Python dependencies
├── trade_agent.py                  # Main analysis entrypoint
└── README.md
```

## 📊 Technical Indicators

The system uses advanced multi-timeframe technical analysis:

### **Core Indicators**
- **RSI (10-period)**: Identifies oversold conditions (RSI < 30 for entries)
- **EMA 200**: Long-term uptrend confirmation (price must be > EMA200, calculated with 800+ days for accuracy)
- **Volume Quality**: 80% of 20-day average volume minimum for entry signals
- **Support/Resistance Levels**: Dynamic identification of key price levels
- **Volume Exhaustion**: Analyzes selling pressure and volume patterns

### **Multi-Timeframe Analysis**
- **Daily Analysis**: Short-term oversold conditions and support proximity
- **Weekly Analysis**: Long-term uptrend confirmation and momentum
- **Alignment Scoring**: 0-10 score measuring daily+weekly trend agreement
- **Confluence Factors**: Support level agreement across timeframes

## 🎯 Signal Classification (Simplified Core Strategy)

### 🔥 STRONG BUY Signals
Generated when **ALL core conditions met** PLUS:
- ✅ **Core Conditions**: RSI10 < 30 + Price > EMA200 + Volume ≥ 80% avg + No negative earnings
- ✅ **Excellent MTF alignment** (score ≥ 8/10) OR excellent uptrend dip pattern
- ✅ **Strong volume confirmation** or pattern signals (hammer, bullish engulfing)

### 📈 BUY Signals  
Generated when **ALL core conditions met** PLUS:
- ✅ **Core Conditions**: RSI10 < 30 + Price > EMA200 + Volume ≥ 80% avg + No negative earnings
- ✅ **Good MTF alignment** (score ≥ 5/10) OR pattern confirmation
- ✅ **Default for valid reversal setups** meeting core criteria

### 👀 WATCH Signals
Generated when:
- ⚠️ **Partial reversal setup**: RSI < 30 + Volume ≥ 80% but may not be above EMA200
- ⚠️ **Pattern signals present** with adequate volume but missing core criteria
- ⚠️ **Fundamental red flags** (negative earnings) but otherwise valid

### ❌ AVOID Signals Generated When:
- Stock not in uptrend (Price ≤ EMA200) AND RSI not oversold
- Insufficient volume (< 80% of 20-day average) 
- No significant technical signals detected
- Data quality issues or calculation errors

### 🎯 **Key Improvements**:
- **Simplified Logic**: Removed overly complex quality assessments that were blocking valid signals
- **Core Focus**: Emphasizes the three pillars - oversold (RSI < 30), uptrend (> EMA200), liquidity (volume)
- **Volume Protection**: 80% threshold prevents entries during poor participation days
- **TradingView Accuracy**: EMA200 calculation now matches TradingView within 0.2%

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
- **File Logging**: Detailed logs in `logs/trade_agent_YYYYMMDD.log`
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

### Enhanced Telegram Alert with Priority Ranking & Backtest Data
```
Reversal Buy Candidates (today) with Backtest Scoring

📈 BUY candidates (sorted by priority):
1. GALLANTT.NS:
	Buy (533.72-541.78)
	Target 666.83 (+24.0%)
	Stop 505.48 (-6.0%)
	RSI:15.36
	MTF:8/10
	RR:4.0x
	ModSupp:2.6% ExtremeRSI
	PE:28.7
	Vol:4.9x
	News:Neu +0.00 (1)
	Backtest: 33/100 (+4.6% return, 80% win, 5 trades)
	Combined Score: 29.0/100
	Priority Score: 100 ✅ HIGHEST PRIORITY

2. GLENMARK.NS:
	Buy (1839.37-1850.43)
	Target 2008.88 (+8.6%)
	Stop 1739.56 (-6.0%)
	RSI:23.18
	MTF:9/10
	RR:1.4x
	StrongSupp:0.3% HighRSI NearSupport
	PE:69.3
	Vol:1.2x
	News:Neu +0.00 (1)
	Backtest: 43/100 (+6.7% return, 100% win, 2 trades)
	Combined Score: 33.8/100
	Priority Score: 39
```

### Terms Explanation
- **MTF:8/10**: Multi-timeframe alignment score (daily+weekly trend agreement)
- **RR:4.0x**: Risk-reward ratio (potential gain ÷ potential loss) - higher is better
- **StrongSupp:0.5%/ModSupp:2.6%**: Distance to support level (Strong/Moderate/Weak quality)
- **HighRSI/ExtremeRSI**: Oversold severity (High: RSI 20-30, Extreme: RSI <20)
- **NearSupport/CloseSupport**: Proximity to support (Near: <1%, Close: <2%)
- **VolExh**: Volume exhaustion detected (selling pressure weakening)
- **PE:28.7**: Price-to-earnings ratio for valuation context (lower usually better)
- **Vol:4.9x**: Volume ratio vs average (above 1.5x = high, below 0.6x = low)
- **News:Neu +0.00 (1)**: News sentiment with 30-day lookback (Pos/Neg/Neu, score, article count)
- **Backtest:33/100**: Historical performance score over 2 years (win rate, returns, trades)
- **Combined Score:29.0/100**: Final ranking (50% current + 50% historical)
- **Priority Score:100**: Trading priority ranking (risk-reward + RSI + volume + MTF factors)

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

# Enable dip-buying mode for more permissive signals
python trade_agent.py --dip-mode

# Complete analysis with backtest scoring and dip mode
python trade_agent.py --backtest --dip-mode
```

For continuous, all-day operation, use the unified scheduler:
- Windows Service: documents/deployment/windows/WINDOWS_UNIFIED_SERVICE.md
- Ubuntu Service: documents/deployment/ubuntu/INSTALL_UBUNTU.md (Unified Service section)

### Strategy Backtesting
Use the Python API (see documents/backtest/README.md) instead of CLI helpers.

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

**Windows Unified Service (recommended)**:
- See documents/deployment/windows/WINDOWS_UNIFIED_SERVICE.md

**Windows Task Scheduler (alternative)**:
```batch
cd C:\path\to\modular_trade_agent
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service.py --env modules\kotak_neo_auto_trader\kotak_neo.env
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
