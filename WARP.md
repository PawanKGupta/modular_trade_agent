# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a cloud-automated trading system for Indian stock markets (NSE) that specializes in **core reversal strategy** using multi-timeframe analysis with historical backtesting validation. The system runs automatically on GitHub Actions at 4PM IST weekdays, identifies high-probability oversold bounces in strong uptrending stocks, validates them against 2-year historical performance, and delivers trade alerts via Telegram.

The system has two main components:
1. **Analysis & Recommendation Engine** - Core trading system that analyzes stocks and generates signals
2. **Execution Module** (`modules/kotak_neo_auto_trader/`) - Optional automated order placement via Kotak Neo broker API

### Key Architecture Components

1. **Core Strategy Engine** (`core/analysis.py`, `core/scoring.py`)
   - Multi-timeframe analysis combining daily + weekly confirmation
   - Signal classification: STRONG_BUY → BUY → WATCH → AVOID
   - Smart buy range and stop-loss calculation based on support levels
   - Priority ranking system based on risk-reward, RSI, volume, and MTF alignment

2. **Backtesting Framework** (`backtest/`)
   - Validates strategies against 2 years of historical data
   - EMA200 + RSI10 pyramiding strategy with averaging-down logic
   - Adaptive entry conditions: RSI < 30 above EMA200, RSI < 20 below EMA200
   - Position management with max 10 positions per stock
   - Performance analytics with win rates, drawdown, Sharpe ratio

3. **Data Pipeline** (`core/data_fetcher.py`, `core/scrapping.py`)
   - Web scraping from ChartInk screener using Selenium (non-headless for cloud)
   - Multi-timeframe data fetching from Yahoo Finance
   - Data leakage prevention in backtests (excludes current-day data)
   - Enhanced data quality with 800+ days for accurate EMA200

4. **Intelligence Layer**
   - `core/timeframe_analysis.py`: MTF dip-buying analysis with 0-10 alignment scoring
   - `core/volume_analysis.py`: Intelligent volume quality assessment
   - `core/news_sentiment.py`: 30-day news sentiment analysis (NLTK-based)
   - `core/backtest_scoring.py`: Historical validation integration

5. **Risk Management**
   - Support-based stop losses (5-6% typical)
   - Resistance-aware profit targets (2-4x risk-reward)
   - Dynamic buy ranges (0.6% typical)
   - Automatic filtering of poor historical performers

## Development Commands

### Running the System

```pwsh
# Activate virtual environment first
.venv\Scripts\activate

# Standard run with all features
python trade_agent.py

# Enable backtest scoring (slower, more accurate)
python trade_agent.py --backtest

# Disable CSV export (faster)
python trade_agent.py --no-csv

# Disable multi-timeframe analysis
python trade_agent.py --no-mtf

# Enable dip-buying mode (more permissive thresholds)
python trade_agent.py --dip-mode

# Full analysis with backtest and dip mode
python trade_agent.py --backtest --dip-mode
```

### Backtesting

```pwsh
# Basic backtest
python run_backtest.py RELIANCE.NS 2022-01-01 2023-12-31

# With detailed analysis and exports
python run_backtest.py ORIENTCEM.NS 2025-01-15 2025-06-15 --export-trades --generate-report

# Custom capital and parameters
python run_backtest.py TCS.NS 2023-01-01 2024-12-31 --capital 200000 --max-positions 5

# Run example scenarios
python examples\backtest_example.py
```

### Testing

```pwsh
# Test Telegram connection
python test_telegram.py

# Test backtest integration
python test_backtest_integration.py

# Test integrated workflow
python integrated_backtest.py
```

### Installing Dependencies

```pwsh
# Install from requirements.txt
pip install -r requirements.txt

# Individual key packages
pip install pandas yfinance selenium webdriver-manager nltk beautifulsoup4 python-dotenv
```

### Kotak Neo Auto Trader (Execution Module)

Optional automated order placement module for executing trades via Kotak Neo broker API.

```pwsh
# Step 1: Generate recommendations with backtest scoring
python trade_agent.py --backtest

# Step 2: Place AMO orders from the final CSV
python -m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env --csv analysis_results\bulk_analysis_final_*.csv

# Auto-pick newest CSV (omit --csv flag)
python -m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env

# Logout after placement (default: keeps session active)
python -m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env --logout
```

## Configuration

### Environment Setup

Create `cred.env` in root directory:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Optional: Override defaults
NEWS_SENTIMENT_ENABLED=true
NEWS_SENTIMENT_LOOKBACK_DAYS=30
RETRY_MAX_ATTEMPTS=3
```

### Trading Parameters

Edit `config/settings.py`:
```python
LOOKBACK_DAYS = 90                    # Historical data period
MIN_VOLUME_MULTIPLIER = 1.0           # Minimum volume (80% threshold)
RSI_OVERSOLD = 30                     # RSI oversold level
VOLUME_MULTIPLIER_FOR_STRONG = 1.2    # Strong volume threshold
```

### GitHub Actions Secrets

For cloud automation, set in repository Settings → Secrets:
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `TELEGRAM_CHAT_ID`: Your chat/channel ID

### Kotak Neo Auto Trader Configuration

For automated order execution (optional):

**Credentials** - Create `modules/kotak_neo_auto_trader/kotak_neo.env`:
```env
KOTAK_CONSUMER_KEY=your_key
KOTAK_CONSUMER_SECRET=your_secret
KOTAK_MOBILE_NUMBER=your_mobile
KOTAK_PASSWORD=your_password
# Use one of the following for 2FA:
KOTAK_TOTP_SECRET=your_totp_secret
# OR
KOTAK_MPIN=your_mpin
KOTAK_ENVIRONMENT=prod
```

**Trading Parameters** - Edit `modules/kotak_neo_auto_trader/config.py`:
```python
CAPITAL_PER_TRADE = 100000       # Fixed capital per entry
MAX_PORTFOLIO_SIZE = 6           # Maximum concurrent positions
MIN_QTY = 1                      # Minimum order quantity
MIN_COMBINED_SCORE = 25          # Minimum score threshold
DEFAULT_EXCHANGE = "NSE"
DEFAULT_PRODUCT = "CNC"           # Cash and Carry
DEFAULT_VARIETY = "AMO"          # After Market Orders
DEFAULT_ORDER_TYPE = "MARKET"    # Market orders for AMO
```

## Core Trading Logic

### Signal Classification Rules

**STRONG_BUY** = ALL core conditions + excellent MTF (≥8/10) or excellent uptrend dip pattern + strong volume
**BUY** = ALL core conditions + good MTF (≥5/10) or pattern confirmation
**WATCH** = Partial setup (RSI < 30 + volume ≥ 80%) but missing core criteria or fundamental red flags
**AVOID** = Not in uptrend + RSI not oversold + insufficient volume

**Core Conditions (all required for BUY/STRONG_BUY)**:
1. RSI10 < 30 (oversold)
2. Price > EMA200 (uptrend)
3. Volume ≥ 80% of 20-day average
4. PE > 0 (positive earnings)

### Backtesting Strategy

**Initial Entry**:
- Above EMA200: RSI < 30 (standard uptrend dip buying)
- Below EMA200: RSI < 20 (extreme oversold required)

**Pyramiding (averaging down, no EMA200 check)**:
1. RSI < 10: First time immediate, subsequent times need RSI > 30 reset
2. RSI < 20: First time immediate, subsequent times need RSI > 30 reset
3. RSI < 30: Always needs RSI > 30 reset (after initial entry)

**Position Limits**: Max 10 positions per stock, ₹100,000 capital per position

### Priority Ranking System

Stocks sorted by trading priority score (max 100 points):
- Risk-reward ratio: 40 points (≥4.0x = 40pts, ≥3.0x = 30pts)
- RSI oversold level: 25 points (≤15 = 25pts, ≤20 = 20pts)
- Volume strength: 20 points (≥4.0x = 20pts, ≥2.0x = 15pts)
- MTF alignment: 10 points (capped at score/10)
- PE ratio: 10 points (≤15 = 10pts, penalty for ≥50)
- Backtest score: 15 points (≥40 = 15pts, ≥30 = 10pts)

## Module Architecture

### Data Flow

```
trade_agent.py (main orchestrator)
    ↓
core/scrapping.py (get stock list from ChartInk)
    ↓
core/data_fetcher.py (fetch OHLCV daily + weekly)
    ↓
core/analysis.py (analyze each stock)
    ├─→ core/indicators.py (RSI, EMA, etc.)
    ├─→ core/timeframe_analysis.py (MTF confirmation)
    ├─→ core/volume_analysis.py (volume quality)
    ├─→ core/news_sentiment.py (sentiment analysis)
    └─→ core/patterns.py (candlestick patterns)
    ↓
core/backtest_scoring.py (historical validation)
    ↓
trade_agent.py (priority ranking + filtering)
    ↓
core/telegram.py (send alerts)
```

### Key Files

**Core System**:
- `trade_agent.py`: Main execution script, orchestrates entire flow, handles priority ranking
- `core/analysis.py`: Core analysis engine with signal classification and smart calculations
- `core/scoring.py`: Signal strength scoring (0-100 scale)
- `core/data_fetcher.py`: Data retrieval with retry logic and circuit breakers
- `core/timeframe_analysis.py`: Multi-timeframe dip-buying analysis class
- `core/backtest_scoring.py`: Integrates backtest validation into live analysis
- `backtest/backtest_engine.py`: Core backtesting logic with pyramiding
- `backtest/position_manager.py`: Trade execution and position tracking
- `backtest/performance_analyzer.py`: Performance metrics and reporting
- `utils/retry_handler.py`: Exponential backoff retry decorator
- `utils/circuit_breaker.py`: Fail-fast pattern for unreliable services

**Kotak Neo Auto Trader Module** (`modules/kotak_neo_auto_trader/`):
- `auto_trade_engine.py`: Main engine for automated order placement and portfolio management
- `run_place_amo.py`: CLI script for placing AMO orders from analysis CSV
- `auth.py`: Kotak Neo authentication with session caching (daily token reuse)
- `orders.py`: Order placement and management API wrapper
- `portfolio.py`: Portfolio/holdings retrieval API wrapper
- `trader.py`: High-level trading interface
- `storage.py`: Trade history persistence (JSON)
- `config.py`: Trading parameters and constraints

### Data Structures

**Analysis Result** (returned by `analyze_ticker`):
```python
{
    'ticker': str,
    'status': 'success' | 'no_data' | 'data_error',
    'verdict': 'strong_buy' | 'buy' | 'watch' | 'avoid',
    'final_verdict': str,  # After backtest scoring
    'strength_score': float,  # 0-100
    'combined_score': float,  # Current + historical
    'last_close': float,
    'buy_range': [low, high],
    'target': float,
    'stop': float,
    'rsi': float,
    'pe': float,
    'volume_multiplier': float,
    'timeframe_analysis': {
        'alignment_score': int,  # 0-10
        'confirmation': str,
        'daily_analysis': {...},
        'weekly_analysis': {...}
    },
    'backtest': {
        'score': float,  # 0-100
        'total_return_pct': float,
        'win_rate': float,
        'total_trades': int
    }
}
```

**MTF Analysis Structure**:
```python
{
    'alignment_score': 0-10,  # Overall agreement
    'confirmation': 'excellent_uptrend_dip' | 'strong' | 'moderate' | 'weak' | 'none',
    'daily_analysis': {
        'trend': 'uptrend' | 'downtrend' | 'sideways',
        'support_analysis': {
            'quality': 'strong' | 'moderate' | 'weak',
            'distance_pct': float,
            'support_level': float
        },
        'oversold_analysis': {
            'severity': 'extreme' | 'high' | 'moderate'
        },
        'volume_exhaustion': {
            'exhaustion_score': int
        }
    },
    'weekly_analysis': {...}  # Similar structure
}
```

## Important Patterns

### Data Leakage Prevention

When fetching data for backtesting, **NEVER include current day** to avoid look-ahead bias:
```python
# WRONG - includes current day
end_for_fetch = pd.Timestamp.today()

# CORRECT - excludes current day
end_for_fetch = pd.Timestamp.today() - pd.Timedelta(days=1)
```

### EMA200 Accuracy

For TradingView-matching EMA200 calculations, fetch **800+ days** of historical data:
```python
# Ensure sufficient data for accurate EMA200
required_trading_days = max(EMA_PERIOD * 1.5, 300)
required_calendar_days = int(required_trading_days * 1.4)
auto_start_date = start_date - timedelta(days=required_calendar_days)
```

### Error Handling Pattern

All external API calls should use retry + circuit breaker:
```python
from utils.retry_handler import retry_on_exception
from utils.circuit_breaker import yfinance_circuit_breaker

@yfinance_circuit_breaker
@retry_on_exception(retries=3, base_delay=1.0)
def fetch_data(ticker):
    return yf.download(ticker, ...)
```

### CSV Export Pattern

For bulk analysis, always use the batch function with CSV export:
```python
from core.analysis import analyze_multiple_tickers

results, csv_filepath = analyze_multiple_tickers(
    tickers, 
    enable_multi_timeframe=True,
    export_to_csv=True
)
```

## Cloud Execution (GitHub Actions)

The system is configured for automatic cloud execution via `.github/workflows/trading-agent.yml`.

**Key Features**:
- Runs at 4PM IST (10:30 AM UTC) on weekdays
- Uses Xvfb for virtual display (non-headless Chrome for scraping)
- Installs Chrome + ChromeDriver automatically
- Uploads results as artifacts (30-day retention)
- Executes with backtest scoring: `python trade_agent.py --backtest`

**Debugging Cloud Runs**:
1. Check Actions tab → Select run → View logs
2. Download artifacts for CSV/log files
3. Test locally first with same command
4. Verify Telegram secrets are set correctly

## Common Tasks

### Adding a New Technical Indicator

1. Add calculation to `core/indicators.py`
2. Update `compute_indicators()` in same file
3. Use indicator in `core/analysis.py` for signal logic
4. Update `assess_setup_quality()` if relevant to quality scoring

### Modifying Signal Classification

Edit `core/analysis.py`:
- Adjust thresholds in signal classification logic (lines ~400-600)
- Update `assess_fundamental_quality()`, `assess_setup_quality()` for quality scoring
- Modify `calculate_smart_buy_range()` or `calculate_smart_stop_loss()` for price levels

### Changing Backtest Strategy Rules

Edit `backtest/backtest_engine.py`:
- Modify `_check_entry_conditions()` for entry logic
- Update `_check_exit_conditions()` for exit logic
- Adjust `backtest/backtest_config.py` for parameters

### Adding New Stock Filters

Edit `core/analysis.py`:
- Add filter check in `analyze_ticker()` function
- Return appropriate error status if filter fails
- Update quality assessment functions if needed

### Working with Kotak Neo Auto Trader

**Testing order placement without execution**:
- Use `mock_client.py` or `run_auto_trade_mock.py` for dry-run testing
- Check session cache at `modules/kotak_neo_auto_trader/session_cache.json`

**Modifying order logic**:
- Edit `auto_trade_engine.py` → `place_new_entries()` for entry logic
- Sizing logic: `qty = floor(CAPITAL_PER_TRADE / last_close)`
- Pre-checks: skip if in holdings, cancel pending BUY orders, verify funds

**Adding exit/re-entry logic**:
- Currently focuses on entry only (AMO placement)
- Exit logic exists in `auto_trade_engine.py` but GTT not supported by this integration
- Consider manual exits or integration with different order types

**Session management**:
- Sessions cached daily in `session_cache.json` (automatically reused)
- Token expires EOD, requires fresh login next trading day
- Use `--logout` flag to explicitly terminate session

## Code Style Notes

- Use type hints where practical (especially in backtest modules)
- Log at appropriate levels: DEBUG (verbose), INFO (progress), WARNING (issues), ERROR (failures)
- Keep functions focused and under 100 lines when possible
- Use descriptive variable names (e.g., `support_distance_pct` not `dist`)
- Add docstrings for complex logic, especially strategy rules
- Follow existing patterns for error handling (try/except with logger)

## Windows-Specific Notes

This codebase runs on Windows with PowerShell:
- Use `.venv\Scripts\activate` (not `source .venv/bin/activate`)
- Path separators automatically handled by `os.path.join()`
- Selenium configured for Windows Chrome paths
- Line endings: CRLF (Windows standard)

## Kotak Neo Auto Trader Integration

### Execution Flow

```
trade_agent.py --backtest
    ↓
analysis_results/bulk_analysis_final_*.csv
    ↓
run_place_amo.py (reads CSV)
    ↓
auto_trade_engine.py (filters & validates)
    ├─→ Check portfolio cap (MAX_PORTFOLIO_SIZE)
    ├─→ Filter by final_verdict + combined_score >= MIN_COMBINED_SCORE
    ├─→ Skip if already in holdings
    ├─→ Cancel any pending BUY orders for symbol
    ├─→ Check account limits/funds
    └─→ Place AMO MARKET order
    ↓
Kotak Neo API (via orders.py)
```

### Key Features

1. **Execution-Only Module**: Does NOT recompute analysis; trusts CSV from trade_agent
2. **Session Caching**: Reuses daily token from `session_cache.json` to avoid repeated 2FA
3. **Portfolio Constraints**: Max 6 positions (configurable), ₹100k per trade
4. **Pre-Flight Checks**:
   - Skip if symbol already in holdings
   - Cancel duplicate pending BUY orders (handles variants: -EQ, -BE, -BL, -BZ)
   - Verify sufficient account funds before placing order
   - Send Telegram alert if funds insufficient (shows required/available/shortfall)
5. **AMO-Only**: Places After Market Orders (executes next trading day at market open)
6. **No GTT Support**: GTT (Good Till Triggered) orders not supported by this integration

### Important Notes

- **Security**: NEVER commit `kotak_neo.env` (contains API keys and credentials)
- **Testing**: Use mock client for dry-runs before live execution
- **Data Source**: Module expects `final_verdict` and `combined_score` columns (from `--backtest` flag)
- **Symbol Format**: Automatically converts `RELIANCE.NS` → `RELIANCE` for broker API
- **Order Sizing**: `qty = floor(CAPITAL_PER_TRADE / last_close)` with min qty = 1
- **2FA Handling**: Auto-detects 2FA gate and attempts force re-login once before skipping
- **Trade History**: Persists to `data/trades_history.json` for tracking

### Troubleshooting

**"Portfolio cap reached" message**:
- System has MAX_PORTFOLIO_SIZE (default 6) concurrent positions
- Exit some positions manually or increase limit in `config.py`

**"Insufficient funds" notification**:
- AMO order requires funds available before market open
- Check account limits via portfolio API or broker platform
- System tries multiple field names for balance detection: `marginAvailable`, `availableMargin`, `cash`, etc.

**Session/authentication errors**:
- Delete `session_cache.json` to force fresh login
- Verify credentials in `kotak_neo.env`
- Check TOTP_SECRET or MPIN for 2FA
- 2FA errors on cached sessions are normal - system falls back to fresh login automatically

**Orders not placed**:
- Verify CSV has `final_verdict` column (requires `--backtest` flag)
- Check `combined_score >= MIN_COMBINED_SCORE` (default 25)
- Review logs for specific rejection reasons

**Invalid ticker errors (`.NS` without symbol)**:
- Fixed: System now validates symbols before constructing tickers
- Trade history reconciliation skips invalid/empty symbols gracefully

### Recent Improvements (2025-10-26)

**Bug Fixes**:
1. **Ticker Parsing**: Fixed `.NS` ticker generation when symbol is missing/empty in trade history
2. **Balance Detection**: Enhanced to try multiple API field name variants for available funds
3. **2FA Session Handling**: Improved error handling for `None` responses and cached sessions
4. **NoneType Iteration**: Fixed auth checks that failed when API returned `None`

**Testing Enhancements**:
- Weekend check can be temporarily disabled for testing (see `auto_trade_engine.py` line 586)
- Portfolio fetched 3 times per run (intentional for accuracy): pre-trade sync, validation, post-trade sync
- Debug logging added for API response field inspection
