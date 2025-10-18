# Modular Trade Agent

A professional-grade automated trading system for Indian stock markets (NSE) that specializes in **uptrend dip-buying** using multi-timeframe analysis. The system identifies high-probability oversold bounces in strong uptrending stocks and delivers institutional-quality trade alerts via Telegram.

## 🚀 Key Features

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

### 📱 **Professional Trade Alerts**
- **Comprehensive Telegram Messages**: All critical trade parameters in one alert
- **Priority Ranking**: Stocks ranked by setup quality (🥇🥈🥉)
- **Setup Quality Indicators**: Support distance, RSI severity, volume analysis
- **Fundamental Context**: PE ratios and valuation assessments

### 🔧 **Enhanced System Features**
- **CSV Export System**: Complete analysis data export for record-keeping
- **Quality Filtering**: Multiple layers of fundamental, volume, and setup filters  
- **Robust Error Handling**: Circuit breakers and exponential backoff retry logic
- **Data Validation**: Ensures sufficient historical data for accurate analysis

## 📋 Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
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

# Disable CSV export (faster execution)
python trade_agent.py --no-csv

# Disable multi-timeframe analysis (single timeframe only)
python trade_agent.py --no-mtf

# Minimal run (no CSV, no MTF)
python trade_agent.py --no-csv --no-mtf
```

### System Process

The system will:
1. **Data Fetching**: Download daily and weekly OHLCV data for all stocks
2. **Multi-Timeframe Analysis**: Analyze daily + weekly trends for alignment
3. **Support/Resistance Analysis**: Identify key levels and proximity
4. **Quality Filtering**: Apply fundamental, volume, and setup filters
5. **Signal Generation**: Create STRONG BUY/BUY/WATCH recommendations
6. **CSV Export**: Save complete analysis data for record-keeping
7. **Telegram Alerts**: Send professional trade alerts with all parameters

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

## 📁 Project Structure

```
modular_trade_agent/
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuration parameters
├── core/
│   ├── __init__.py
│   ├── analysis.py          # Main analysis logic with enhanced filters
│   ├── csv_exporter.py      # CSV export system for analysis data
│   ├── data_fetcher.py      # Multi-timeframe data retrieval with retry logic
│   ├── indicators.py        # Technical indicators (RSI, EMA, etc.)
│   ├── patterns.py          # Candlestick patterns
│   ├── scoring.py           # Signal strength scoring
│   ├── scrapping.py         # Web scraping utilities
│   ├── telegram.py          # Enhanced Telegram messaging
│   └── timeframe_analysis.py # Multi-timeframe dip-buying analysis engine
├── utils/
│   ├── __init__.py
│   ├── circuit_breaker.py   # Circuit breaker implementation
│   ├── logger.py            # Logging configuration
│   └── retry_handler.py     # Retry logic with exponential backoff
├── Test/
│   ├── backtesting.py      # Backtesting utilities
│   ├── backtest_stocks.py  # Stock backtesting
│   ├── debug_test.py       # Debug utilities
│   └── volume_analysis.py  # Volume analysis
├── logs/                   # Log files
├── cred.env               # Environment variables (create this)
├── requirements.txt       # Python dependencies
├── trade_agent.py        # Main execution script
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

### Enhanced Telegram Alert
```
Reversal Buy Candidates (today)

🔥 STRONG BUY (Multi-timeframe confirmed):
1. NAVA.NS: Buy (603.68-607.32)
   Target 717.07 (+16.9%) | Stop 576.45 (-6.0%)
   RSI:25.08 MTF:9/10 RR:2.8x | StrongSupp:1.3% HighRSI CloseSupport PE:16.9

📈 BUY candidates:
1. GLENMARK.NS: Buy (1849.83-1860.97)
   Target 2073.97 (+11.4%) | Stop 1750.19 (-6.0%)
   RSI:24.0 MTF:8/10 RR:1.9x | StrongSupp:0.3% HighRSI VolExh NearSupport PE:69.9

2. CURAA.NS: Buy (169.81-170.83)
   Target 211.20 (+24.0%) | Stop 160.10 (-6.0%)
   RSI:18.97 MTF:9/10 RR:4.0x | StrongSupp:0.0% ExtremeRSI NearSupport
```

### Terms Explanation
- **MTF:9/10**: Multi-timeframe alignment score (daily+weekly trend agreement)
- **RR:2.8x**: Risk-reward ratio (potential gain ÷ potential loss)
- **StrongSupp:1.3%**: Distance to strong support level
- **HighRSI/ExtremeRSI**: Oversold severity (High: RSI 20-30, Extreme: RSI <20)
- **NearSupport/CloseSupport**: Proximity to support (Near: <1%, Close: <2%)
- **VolExh**: Volume exhaustion detected (selling pressure weakening)
- **PE:16.9**: Price-to-earnings ratio for valuation context

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

## 🚦 Running in Production

### Automation
Set up scheduled execution using:

**Windows Task Scheduler**:
```batch
cd C:\path\to\modular_trade_agent
.venv\Scripts\python.exe trade_agent.py
```

**Linux Cron**:
```bash
0 9 * * 1-5 cd /path/to/modular_trade_agent && .venv/bin/python trade_agent.py
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