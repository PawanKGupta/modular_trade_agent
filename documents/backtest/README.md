# Backtesting Module

A comprehensive backtesting framework for the **EMA200 + RSI10 Pyramiding Strategy** that evaluates historical performance with detailed analytics and reporting.

## 🎯 Strategy Overview

The backtesting module implements a specific trading strategy with these rules:

### Entry Conditions
1. **Primary Entry**: Price > EMA200 AND RSI10 < 30
2. **Pyramiding Entries**:
   - RSI10 < 20: Add position
   - RSI10 < 10: Add position  
   - RSI10 rises above 30, then falls below 30 again: Add position

### Trade Execution
- Buy at next day's opening price
- Fixed capital allocation: 100,000 per position
- Maximum positions: 10 (configurable)

## 🚀 Quick Start

### Basic Usage

```python
from backtest import BacktestEngine

# Simple backtest
engine = BacktestEngine(
    symbol="RELIANCE.NS",
    start_date="2022-01-01",
    end_date="2023-12-31"
)

results = engine.run_backtest()
engine.print_summary()
```

### Command Line Usage

```bash
# Basic backtest
python run_backtest.py RELIANCE.NS 2022-01-01 2023-12-31

# With custom parameters
python run_backtest.py AAPL 2020-01-01 2023-12-31 --capital 200000 --export-trades --generate-report

# Disable pyramiding
python run_backtest.py TCS.NS 2021-01-01 2023-06-01 --no-pyramiding
```

## 📊 Features

### Core Backtesting
- **Accurate Strategy Implementation**: Follows the exact pyramiding rules
- **Realistic Trade Execution**: Uses next-day open prices
- **Comprehensive Position Tracking**: Monitors all entries and exits
- **Performance Metrics**: Win rate, profit factor, drawdown analysis

### Advanced Analytics
- **Risk Metrics**: Maximum drawdown, volatility, VaR
- **Trade Analysis**: Holding periods, consecutive wins/losses  
- **Time-based Analysis**: Monthly performance breakdown
- **Benchmark Comparison**: Strategy vs buy-and-hold

### Reporting & Export
- **Detailed Reports**: Comprehensive performance analysis
- **CSV Export**: Individual trade data for further analysis
- **Automated Recommendations**: Strategy improvement suggestions

## 📁 Module Structure

```
backtest/
├── __init__.py              # Package initialization
├── backtest_config.py       # Configuration settings
├── backtest_engine.py       # Core backtesting logic
├── position_manager.py      # Position and trade management
├── performance_analyzer.py  # Analytics and reporting
└── README.md               # This file
```

## ⚙️ Configuration

The `BacktestConfig` class allows customization of strategy parameters:

```python
from backtest import BacktestConfig

config = BacktestConfig()
config.POSITION_SIZE = 200000        # Capital per position
config.RSI_PERIOD = 14               # RSI calculation period  
config.EMA_PERIOD = 100              # EMA calculation period
config.MAX_POSITIONS = 5             # Maximum pyramiding positions
config.ENABLE_PYRAMIDING = False     # Disable pyramiding

# Use custom config
engine = BacktestEngine(symbol="INFY.NS", start_date="2022-01-01", 
                       end_date="2023-12-31", config=config)
```

## 📈 Performance Analysis

### Basic Metrics
```python
from backtest import BacktestEngine, PerformanceAnalyzer

# Run backtest
engine = BacktestEngine("RELIANCE.NS", "2022-01-01", "2023-12-31")
results = engine.run_backtest()

# Detailed analysis
analyzer = PerformanceAnalyzer(engine)
metrics = analyzer.analyze_performance()

# Generate report
report = analyzer.generate_report(save_to_file=True)
```

### Export Trade Data
```python
# Export trades to CSV
trades_file = analyzer.export_trades_to_csv()

# Get trades as DataFrame
trades_df = engine.get_trades_dataframe()
print(trades_df.head())
```

## 🎮 Example Scripts

### 1. **run_backtest.py** - Command Line Interface
Easy-to-use command line tool for running backtests:

```bash
python run_backtest.py SYMBOL START_DATE END_DATE [OPTIONS]
```

### 2. **backtest_example.py** - Comprehensive Examples  
Demonstrates various usage patterns:
- Single stock analysis
- Custom configurations
- Multiple stock comparisons
- Different time periods
- Performance reporting

Run examples:
```bash
python backtest_example.py
```

## 📊 Sample Output

### Console Summary
```
============================================================
BACKTEST SUMMARY - RELIANCE.NS
============================================================
Period: 2022-01-01 to 2023-12-31
Total Trades: 8
Total Invested: ₹800,000
Total P&L: ₹75,420
Total Return: +9.43%
Win Rate: 62.5%
Winning Trades: 5
Losing Trades: 3

Buy & Hold Return: +1.2%
Strategy vs B&H: +8.23%
🎉 Strategy OUTPERFORMED buy & hold!
============================================================
```

### Detailed Report
The performance analyzer generates comprehensive reports including:
- **Summary**: Key performance metrics
- **Risk Analysis**: Drawdown, volatility, VaR
- **Trade Analysis**: Holding periods, trade sizes
- **Time Analysis**: Monthly performance breakdown
- **Recommendations**: Strategy improvement suggestions

## 🔧 Customization

### Custom Entry/Exit Logic
Extend the `BacktestEngine` class to implement custom logic:

```python
class CustomBacktestEngine(BacktestEngine):
    def _check_entry_conditions(self, row, current_date):
        # Add custom entry logic
        return super()._check_entry_conditions(row, current_date)
```

### Additional Indicators
Modify `_calculate_indicators()` to add more technical indicators:

```python
def _calculate_indicators(self):
    super()._calculate_indicators()
    # Add custom indicators
    self.data['MACD'] = ta.macd(self.data['Close'])
```

## 📋 Requirements

- Python 3.8+
- pandas
- numpy  
- yfinance
- pandas_ta
- Existing project dependencies

## ⚠️ Important Notes

### Data Limitations
- Uses Yahoo Finance data (free but may have limitations)
- Historical data accuracy depends on data source
- Some stocks may have insufficient historical data

### Strategy Limitations  
- No stop-loss or take-profit implementation
- Positions held until end of backtest period
- No transaction costs included
- No slippage modeling

### Performance Considerations
- Large date ranges require more memory
- Multiple stock analysis can be time-consuming
- Internet connection required for data fetching

## 🚀 Getting Started

1. **Run a simple backtest:**
   ```bash
   python run_backtest.py RELIANCE.NS 2022-01-01 2023-12-31
   ```

2. **Try the examples:**
   ```bash
   python backtest_example.py
   ```

3. **Create your own analysis:**
   ```python
   from backtest import BacktestEngine
   
   engine = BacktestEngine("YOUR_SYMBOL", "2022-01-01", "2023-12-31")
   results = engine.run_backtest()
   ```

## 💡 Tips for Best Results

1. **Choose appropriate date ranges**: At least 1-2 years for meaningful results
2. **Test multiple stocks**: Different stocks behave differently
3. **Compare with buy-and-hold**: Always benchmark against simple strategies
4. **Analyze different market conditions**: Test across bull/bear markets
5. **Review individual trades**: Understanding why trades succeeded/failed

## 🤝 Contributing

This backtesting module is part of the larger trading system. Contributions and improvements are welcome!

## 📄 Disclaimer

**This backtesting module is for educational and analysis purposes only. Past performance does not guarantee future results. Always do your own research and consider consulting with financial professionals before making investment decisions.**