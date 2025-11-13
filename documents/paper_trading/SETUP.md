# Paper Trading System - Setup Guide

## 📋 Overview

The paper trading system allows you to test your trading strategies without risking real money. It simulates all broker operations including order execution, portfolio management, P&L tracking, and more.

## 🎯 Features

- ✅ **Complete Broker Simulation**: Implements full `IBrokerGateway` interface
- ✅ **Realistic Execution**: Slippage, fees, market hours enforcement
- ✅ **Portfolio Tracking**: Holdings, P&L, cost basis
- ✅ **Persistent State**: All data saved to JSON files
- ✅ **Live Prices**: Integration with existing data fetcher
- ✅ **Detailed Reports**: Portfolio, orders, transactions, performance metrics
- ✅ **Drop-in Replacement**: Swap with real broker using same interface

## 🚀 Quick Start

### 1. Basic Usage

```python
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig

# Create configuration
config = PaperTradingConfig(
    initial_capital=100000.0,  # ₹1 lakh
    enable_slippage=True,
    enable_fees=True,
    price_source="live"  # or "mock" for testing
)

# Initialize adapter
broker = PaperTradingBrokerAdapter(config)
broker.connect()

# Now use it exactly like the real broker!
# All IBrokerGateway methods are available
```

### 2. Using with Existing Use Cases

```python
from modules.kotak_neo_auto_trader.application.use_cases import PlaceOrderUseCase
from modules.kotak_neo_auto_trader.application.dto import OrderRequest

# Create use case with paper trading broker
place_order_uc = PlaceOrderUseCase(broker_gateway=broker)

# Place orders as usual
order_req = OrderRequest.market_buy(
    symbol="INFY",
    quantity=10,
    variety=OrderVariety.REGULAR,
    product_type=ProductType.CNC
)

response = place_order_uc.execute(order_req)
if response.success:
    print(f"Order placed: {response.order_id}")
```

## ⚙️ Configuration Options

### Default Configuration

```python
config = PaperTradingConfig()  # Uses sensible defaults
```

### Custom Configuration

```python
config = PaperTradingConfig(
    # Capital
    initial_capital=100000.0,
    
    # Execution
    enable_slippage=True,
    slippage_percentage=0.2,
    execution_delay_ms=100,
    
    # Fees
    enable_fees=True,
    brokerage_percentage=0.03,
    stt_percentage=0.1,
    
    # Market Hours
    enforce_market_hours=True,
    market_open_time="09:15",
    market_close_time="15:30",
    
    # Storage
    storage_path="paper_trading/data",
    auto_save=True,
    
    # Price Feed
    price_source="live",  # "live", "mock", or "historical"
)
```

### Configuration Presets

```python
# Minimal fees (for testing)
config = PaperTradingConfig.minimal_fees()

# Realistic market conditions
config = PaperTradingConfig.realistic()
```

## 📊 Generating Reports

```python
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter

# Create reporter
reporter = PaperTradeReporter(broker.store)

# Print summary to console
reporter.print_summary()
reporter.print_holdings()
reporter.print_recent_orders(limit=10)

# Export to files
reporter.export_to_json("paper_trading/report.json")
reporter.export_to_csv("paper_trading/reports/")
```

## 💾 Data Storage

All data is stored in JSON files in the configured storage directory:

```
paper_trading/data/
├── account.json          # Balance, P&L
├── orders.json           # All orders
├── holdings.json         # Current portfolio
├── transactions.json     # Trade history
└── config.json          # Configuration
```

### Backup & Restore

```python
# Create backup
backup_path = broker.store.create_backup()
print(f"Backup created: {backup_path}")

# Restore from backup
broker.store.restore_backup(backup_path)
```

### Reset Account

```python
# WARNING: This deletes all data!
broker.reset()
```

## 🔄 State Persistence

The paper trading system automatically saves state after each operation. When you reconnect, your portfolio and balance are restored:

```python
# Session 1
broker = PaperTradingBrokerAdapter(config)
broker.connect()
# ... place orders ...
broker.disconnect()

# Session 2 (later)
broker = PaperTradingBrokerAdapter(config)  # Same config/path
broker.connect()
# Your portfolio and balance are restored!
```

## 💡 Price Feeds

### Live Prices

```python
config = PaperTradingConfig(price_source="live")
# Uses your existing DataFetcher to get real-time prices
```

### Mock Prices

```python
config = PaperTradingConfig(price_source="mock")
# Generates deterministic mock prices (for testing)
```

### Manual Price Setting

```python
# For unit tests
broker.price_provider.set_mock_price("INFY", 1450.50)
```

## 🎯 Use Cases

### 1. Strategy Testing

Test your mean reversion strategy without risk:

```python
# Your strategy code works exactly the same
# Just swap KotakNeoBrokerAdapter with PaperTradingBrokerAdapter
```

### 2. Backtesting Integration

```python
# Use paper trading adapter with historical price replay
# (Future enhancement)
```

### 3. Training & Learning

```python
# Practice trading without financial risk
# Test different position sizes, averaging down, etc.
```

### 4. Debugging

```python
# Test edge cases:
# - Insufficient funds
# - Invalid symbols
# - Market hours violations
# - Averaging down scenarios
```

## 🔧 Advanced Features

### Market Hours Enforcement

```python
config = PaperTradingConfig(
    enforce_market_hours=True,
    market_open_time="09:15",
    market_close_time="15:30"
)
# Orders outside market hours will be rejected
```

### AMO Orders

```python
config = PaperTradingConfig(
    allow_amo_orders=True,
    amo_execution_time="09:15"
)
# AMO orders will execute at market open
```

### Slippage Simulation

```python
config = PaperTradingConfig(
    enable_slippage=True,
    slippage_range=(0.1, 0.3)  # Random between 0.1% - 0.3%
)
```

### Trading Fees

```python
config = PaperTradingConfig(
    enable_fees=True,
    brokerage_percentage=0.03,
    stt_percentage=0.1,
    transaction_charges_percentage=0.00325,
    gst_percentage=18.0
)
```

## 🚨 Important Notes

1. **No Real Money**: Paper trading uses simulated money only
2. **Price Accuracy**: Live prices depend on data source availability
3. **Slippage**: Real market slippage may vary
4. **Execution**: Real orders may experience partial fills or rejections
5. **Market Impact**: Paper trading doesn't account for market impact
6. **Liquidity**: Assumes infinite liquidity (always fills)

## 📈 Performance Metrics

The reporter calculates various metrics:

- **Total P&L**: Realized + Unrealized
- **Return %**: (P&L / Initial Capital) × 100
- **Win Rate**: % of profitable trades
- **Holdings Count**: Number of positions
- **Order Statistics**: Success rate, pending orders, etc.

## 🔗 Integration with Existing System

The paper trading adapter is a **drop-in replacement** for Kotak Neo:

```python
# Real trading
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import KotakNeoBrokerAdapter
broker = KotakNeoBrokerAdapter(auth_handler)

# Paper trading (just change this line!)
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
broker = PaperTradingBrokerAdapter(config)

# Everything else remains the same!
use_case = PlaceOrderUseCase(broker_gateway=broker)
```

## 🆘 Troubleshooting

### Issue: Prices not available

```python
# Solution 1: Use mock prices
config = PaperTradingConfig(price_source="mock")

# Solution 2: Check DataFetcher is working
from core.data_fetcher import DataFetcher
fetcher = DataFetcher()
data = fetcher.fetch_data_yfinance("INFY", period="1d")
```

### Issue: Insufficient funds error

```python
# Check balance
balance = broker.get_available_balance()
print(f"Balance: ₹{balance.amount}")

# Check order value
# Remember: Total cost = Order value + Charges
```

### Issue: State not persisting

```python
# Ensure auto_save is enabled
config = PaperTradingConfig(auto_save=True)

# Or manually save
broker.store.save_all()
```

## 📚 Next Steps

- See [USAGE.md](./USAGE.md) for detailed usage examples
- See [EXAMPLES.md](./EXAMPLES.md) for specific scenarios
- Run `python examples/paper_trading_example.py` for a demo

## 💬 Support

For issues or questions:
1. Check existing documentation
2. Review example scripts
3. Check logs in `paper_trading/data/` directory

