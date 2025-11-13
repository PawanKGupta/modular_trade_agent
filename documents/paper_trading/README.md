# 📊 Paper Trading System

A complete paper trading system for testing your trading strategies without risking real money. Mimics Kotak Neo broker behavior with realistic execution, fees, and portfolio management.

## 🎯 Purpose

Test your **mean reversion to EMA9 strategy** safely:
- No real money at risk
- Realistic market simulation
- Complete P&L tracking
- Learn and improve without losses

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔌 **Drop-in Replacement** | Implements `IBrokerGateway` - swap with real broker |
| 💰 **Virtual Capital** | Start with any amount (default ₹1 lakh) |
| 📈 **Live Prices** | Integrates with your existing data fetcher |
| 💸 **Realistic Fees** | Brokerage, STT, transaction charges, GST |
| 🎲 **Slippage Simulation** | Realistic price slippage on execution |
| 📊 **Portfolio Tracking** | Holdings, averaging, P&L calculation |
| 💾 **Persistent State** | All data saved to JSON files |
| 📑 **Detailed Reports** | Portfolio, orders, transactions, metrics |
| ⏰ **Market Hours** | Enforce trading hours (optional) |
| 🔄 **AMO Orders** | After Market Orders support |

## 🚀 Quick Start

```python
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig

# Initialize with ₹1 lakh
config = PaperTradingConfig(initial_capital=100000.0)
broker = PaperTradingBrokerAdapter(config)
broker.connect()

# Place orders (same as real broker!)
from modules.kotak_neo_auto_trader.domain import Order, OrderType, TransactionType

order = Order(
    symbol="INFY",
    quantity=10,
    order_type=OrderType.MARKET,
    transaction_type=TransactionType.BUY
)
order_id = broker.place_order(order)

# Check holdings
holdings = broker.get_holdings()
for h in holdings:
    print(f"{h.symbol}: {h.quantity} @ ₹{h.average_price.amount}")

# Generate report
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter
reporter = PaperTradeReporter(broker.store)
reporter.print_summary()
```

## 📚 Documentation

- **[SETUP.md](./SETUP.md)** - Installation and configuration
- **[USAGE.md](./USAGE.md)** - Detailed usage guide
- **[examples/paper_trading_example.py](../../examples/paper_trading_example.py)** - Complete example

## 🏗️ Architecture

```
Paper Trading System
│
├── PaperTradingBrokerAdapter (IBrokerGateway)
│   ├── OrderSimulator (execution, slippage, fees)
│   ├── PortfolioManager (holdings, P&L)
│   ├── PriceProvider (live/mock prices)
│   └── PaperTradeStore (persistence)
│
├── Configuration (PaperTradingConfig)
│   ├── Capital settings
│   ├── Execution settings
│   ├── Fee structure
│   └── Storage settings
│
└── Reporting (PaperTradeReporter)
    ├── Portfolio summary
    ├── Order history
    ├── Performance metrics
    └── Export (JSON/CSV)
```

## 💡 Use Cases

### 1. Strategy Testing
Test your mean reversion strategy before going live:
```python
# Test with paper trading first
broker = PaperTradingBrokerAdapter(config)

# When confident, switch to real
# broker = KotakNeoBrokerAdapter(auth_handler)
```

### 2. Learning & Practice
Practice trading without financial risk:
```python
config = PaperTradingConfig(
    initial_capital=50000.0,
    enable_fees=True,
    enable_slippage=True
)
```

### 3. Backtesting Integration
Combine with historical data for backtesting:
```python
# Set mock prices from historical data
for timestamp, price in historical_data:
    broker.price_provider.set_mock_price(symbol, price)
    # Execute strategy
```

### 4. Position Sizing Tests
Test different position sizes safely:
```python
# Conservative
position_size = balance * 0.05

# Aggressive
position_size = balance * 0.20

# Test both without risk!
```

## 📊 Example Output

```
============================================================
📊 PAPER TRADING SUMMARY
============================================================
Initial Capital:    ₹       100,000.00
Current Value:      ₹        98,450.75
Cash Balance:       ₹        65,320.50
Portfolio Value:    ₹        33,130.25
------------------------------------------------------------
Total P&L:          ₹        -1,549.25 (-1.55%)
  Realized:         ₹          -850.00
  Unrealized:       ₹          -699.25
------------------------------------------------------------
Holdings Count:                      3
============================================================

============================================================
📊 HOLDINGS
============================================================
Symbol     Qty    Avg Price      Current    Cost Basis      Mkt Value         P&L    P&L %
----------------------------------------------------------------------------------------------------
INFY        10   ₹  1,450.50   ₹  1,465.75   ₹  14,505.00   ₹  14,657.50   ₹  152.50    1.05%
TCS          5   ₹  3,520.00   ₹  3,495.50   ₹  17,600.00   ₹  17,477.50   ₹ -122.50   -0.70%
RELIANCE     8   ₹  2,580.00   ₹  2,558.25   ₹  20,640.00   ₹  20,466.00   ₹ -174.00   -0.84%
============================================================
```

## ⚙️ Configuration

### Default Settings
- Initial Capital: ₹100,000
- Slippage: 0.1-0.3%
- Brokerage: 0.03%
- STT: 0.1% (sell side)
- Market Hours: 09:15 - 15:30

### Customize
```python
config = PaperTradingConfig(
    initial_capital=200000.0,
    enable_slippage=True,
    slippage_range=(0.2, 0.4),
    enable_fees=True,
    brokerage_percentage=0.03,
    price_source="live",
    storage_path="my_paper_trading"
)
```

## 💾 Data Storage

All data persists in JSON files:

```
paper_trading/data/
├── account.json          # Balance, P&L, capital
├── orders.json           # All orders (buy/sell)
├── holdings.json         # Current positions
├── transactions.json     # Execution history
└── config.json          # Configuration
```

Your portfolio is automatically restored when you reconnect!

## 🔄 Integration

Works seamlessly with existing code:

```python
# Existing use case
from modules.kotak_neo_auto_trader.application.use_cases import PlaceOrderUseCase

# Works with paper trading
use_case = PlaceOrderUseCase(broker_gateway=paper_broker)

# Works with real broker
use_case = PlaceOrderUseCase(broker_gateway=real_broker)

# Same code, different broker!
```

## 📈 Your Strategy

Perfect for testing your mean reversion strategy:

```python
# 1. Screen for RSI10 < 30
# 2. Check price > EMA200
# 3. Place paper trade
if rsi10 < 30 and price > ema200:
    order = Order(
        symbol=ticker,
        quantity=10,
        order_type=OrderType.MARKET,
        transaction_type=TransactionType.BUY
    )
    broker.place_order(order)

# 4. Monitor for EMA9 exit
if price >= ema9:
    # Sell position
    broker.place_order(sell_order)
```

## 🎓 Learning Path

1. **Start Here**: Run `python examples/paper_trading_example.py`
2. **Read Docs**: [SETUP.md](./SETUP.md) and [USAGE.md](./USAGE.md)
3. **Test Strategy**: Use with mock prices
4. **Go Live (Paper)**: Use with live prices
5. **Analyze**: Review reports and metrics
6. **Refine**: Adjust strategy based on results
7. **Go Real**: Switch to real broker when confident

## 🚨 Important Notes

- **No Real Money**: This is simulation only
- **Price Accuracy**: Mock prices are for testing; live prices need data source
- **Slippage Varies**: Real market conditions may differ
- **No Market Impact**: Assumes infinite liquidity
- **Backup Data**: Create backups before resetting

## 🛠️ Troubleshooting

**Q: Prices not updating?**
```python
# Check price provider
cache_info = broker.price_provider.get_cache_info()
print(cache_info)

# Clear cache
broker.price_provider.clear_cache()
```

**Q: State not persisting?**
```python
# Ensure auto-save is enabled
config = PaperTradingConfig(auto_save=True)

# Manual save
broker.store.save_all()
```

**Q: Orders rejected?**
```python
# Check balance
balance = broker.get_available_balance()

# Check holdings (for sell orders)
holding = broker.get_holding(symbol)
```

## 📦 Components

| Component | Purpose |
|-----------|---------|
| `PaperTradingBrokerAdapter` | Main broker interface |
| `PaperTradingConfig` | Configuration management |
| `OrderSimulator` | Execution with slippage/fees |
| `PortfolioManager` | Holdings and P&L tracking |
| `PriceProvider` | Price feed (live/mock) |
| `PaperTradeStore` | Data persistence |
| `PaperTradeReporter` | Reports and analytics |

## 🎯 Benefits

✅ **Risk-Free**: Test without losing money
✅ **Realistic**: Slippage, fees, market hours
✅ **Educational**: Learn by doing
✅ **Fast Iteration**: Test multiple strategies quickly
✅ **Data-Driven**: Detailed reports and metrics
✅ **Confidence Building**: Go live when ready

## 🚀 Next Steps

1. Run the example: `python examples/paper_trading_example.py`
2. Read [SETUP.md](./SETUP.md) for detailed setup
3. Read [USAGE.md](./USAGE.md) for usage patterns
4. Integrate with your strategy
5. Test thoroughly
6. Analyze results
7. Go live with confidence!

## 📞 Support

- Check documentation first
- Review example scripts
- Examine storage files for debugging
- Enable verbose logging for troubleshooting

---

**Remember**: Paper trading is for learning and testing. Real trading involves actual risk. Trade responsibly!

