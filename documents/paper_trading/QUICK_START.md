# Paper Trading - Quick Start

Get started with paper trading in 5 minutes!

## 1. Basic Setup (30 seconds)

```python
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig

# Create broker with ₹1 lakh
config = PaperTradingConfig(initial_capital=100000.0)
broker = PaperTradingBrokerAdapter(config)
broker.connect()

print(f"Balance: ₹{broker.get_available_balance().amount:,.2f}")
```

Output:
```
Balance: ₹100,000.00
```

## 2. Place Your First Order (1 minute)

```python
from modules.kotak_neo_auto_trader.domain import Order, OrderType, TransactionType

# Buy 10 shares of INFY
order = Order(
    symbol="INFY",
    quantity=10,
    order_type=OrderType.MARKET,
    transaction_type=TransactionType.BUY
)

order_id = broker.place_order(order)
print(f"Order placed: {order_id}")
```

Output:
```
Order placed: PT202511130001
```

## 3. Check Your Portfolio (30 seconds)

```python
# View holdings
holdings = broker.get_holdings()

for h in holdings:
    print(f"{h.symbol}: {h.quantity} shares @ ₹{h.average_price.amount:.2f}")
    print(f"P&L: ₹{h.calculate_pnl().amount:.2f}")
```

Output:
```
INFY: 10 shares @ ₹1,450.50
P&L: ₹0.00
```

## 4. Sell Shares (30 seconds)

```python
# Sell 5 shares
sell_order = Order(
    symbol="INFY",
    quantity=5,
    order_type=OrderType.MARKET,
    transaction_type=TransactionType.SELL
)

broker.place_order(sell_order)

# Check updated holding
holding = broker.get_holding("INFY")
print(f"Remaining: {holding.quantity} shares")
```

Output:
```
Remaining: 5 shares
```

## 5. Generate Report (1 minute)

```python
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter

reporter = PaperTradeReporter(broker.store)
reporter.print_summary()
reporter.print_holdings()
```

Output:
```
============================================================
📊 PAPER TRADING SUMMARY
============================================================
Initial Capital:    ₹       100,000.00
Current Value:      ₹       100,450.75
Cash Balance:       ₹        92,700.50
Portfolio Value:    ₹         7,750.25
------------------------------------------------------------
Total P&L:          ₹           450.75 (+0.45%)
  Realized:         ₹           250.00
  Unrealized:       ₹           200.75
------------------------------------------------------------
Holdings Count:                      1
============================================================
```

## 6. Save & Disconnect (10 seconds)

```python
# Disconnect (auto-saves everything)
broker.disconnect()

# Reconnect later - your data is preserved!
broker.connect()
```

## Complete Example

```python
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
from modules.kotak_neo_auto_trader.domain import Order, OrderType, TransactionType
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter

# Setup
config = PaperTradingConfig(initial_capital=100000.0)
broker = PaperTradingBrokerAdapter(config)
broker.connect()

# Buy
buy_order = Order(
    symbol="INFY",
    quantity=10,
    order_type=OrderType.MARKET,
    transaction_type=TransactionType.BUY
)
broker.place_order(buy_order)

# Check
holdings = broker.get_holdings()
print(f"Holdings: {len(holdings)}")

# Report
reporter = PaperTradeReporter(broker.store)
reporter.print_summary()

# Disconnect
broker.disconnect()
```

## Using with Your Strategy

Replace your broker initialization:

```python
# Before (real trading)
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import KotakNeoBrokerAdapter
broker = KotakNeoBrokerAdapter(auth_handler)

# After (paper trading)
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig
config = PaperTradingConfig(initial_capital=100000.0)
broker = PaperTradingBrokerAdapter(config)

# Everything else stays the same!
```

## Using Broker Factory

Simplify broker creation:

```python
from modules.kotak_neo_auto_trader.infrastructure.broker_factory import create_paper_broker

# Quick paper broker
broker = create_paper_broker(
    initial_capital=100000.0,
    enable_slippage=True,
    enable_fees=True
)
broker.connect()
```

## Next Steps

- ✅ **[Read Full Setup Guide](./SETUP.md)** - Configuration options
- ✅ **[Read Usage Guide](./USAGE.md)** - Detailed usage patterns
- ✅ **[Run Example Script](../../examples/paper_trading_example.py)** - Complete demo
- ✅ **[Test Your Strategy](./README.md)** - Start testing!

## Need Help?

- Check [SETUP.md](./SETUP.md) for configuration
- Check [USAGE.md](./USAGE.md) for advanced usage
- Run `python examples/paper_trading_example.py` for demo
- Review tests in `tests/paper_trading/`

## Tips

💡 **Start with mock prices** for testing, then switch to live
💡 **Disable fees** initially to test strategy logic
💡 **Enable realistic mode** before going live
💡 **Backup your data** before resetting
💡 **Review reports** regularly to track performance

---

**Happy Paper Trading! 📊**

