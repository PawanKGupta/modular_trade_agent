## Paper Trading System - Usage Guide

## 📖 Table of Contents

1. [Basic Operations](#basic-operations)
2. [Order Management](#order-management)
3. [Portfolio Management](#portfolio-management)
4. [Reports & Analytics](#reports--analytics)
5. [Advanced Scenarios](#advanced-scenarios)

## Basic Operations

### Initialize & Connect

```python
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig

# Create config
config = PaperTradingConfig(initial_capital=100000.0)

# Initialize
broker = PaperTradingBrokerAdapter(config)

# Connect
broker.connect()
print(f"Balance: ₹{broker.get_available_balance().amount:,.2f}")
```

### Disconnect

```python
# Disconnect (auto-saves state)
broker.disconnect()

# Reconnect later
broker.connect()  # State is restored!
```

## Order Management

### Place Market BUY Order

```python
from modules.kotak_neo_auto_trader.domain import Order, Money, OrderType, TransactionType

order = Order(
    symbol="INFY",
    quantity=10,
    order_type=OrderType.MARKET,
    transaction_type=TransactionType.BUY
)

order_id = broker.place_order(order)
print(f"Order placed: {order_id}")
```

### Place Limit BUY Order

```python
order = Order(
    symbol="TCS",
    quantity=5,
    order_type=OrderType.LIMIT,
    transaction_type=TransactionType.BUY,
    price=Money(3500.00)  # Will execute if price <= 3500
)

order_id = broker.place_order(order)
```

### Place Market SELL Order

```python
order = Order(
    symbol="INFY",
    quantity=5,
    order_type=OrderType.MARKET,
    transaction_type=TransactionType.SELL
)

order_id = broker.place_order(order)
```

### Using OrderRequest DTO (Recommended)

```python
from modules.kotak_neo_auto_trader.application.dto import OrderRequest
from modules.kotak_neo_auto_trader.domain import OrderVariety, ProductType

# Market BUY
req = OrderRequest.market_buy(
    symbol="RELIANCE",
    quantity=10,
    variety=OrderVariety.REGULAR,
    product_type=ProductType.CNC
)

# Limit SELL
req = OrderRequest.limit_sell(
    symbol="INFY",
    quantity=5,
    price=1500.00,
    variety=OrderVariety.REGULAR,
    product_type=ProductType.CNC
)
```

### Get Order Status

```python
# Get specific order
order = broker.get_order(order_id)
if order:
    print(f"Status: {order.status.value}")
    print(f"Executed: {order.is_executed()}")

# Get all orders
all_orders = broker.get_all_orders()

# Get pending orders
pending = broker.get_pending_orders()
```

### Cancel Order

```python
success = broker.cancel_order(order_id)
if success:
    print("Order cancelled")
```

### Cancel All Pending BUYs for Symbol

```python
cancelled_count = broker.cancel_pending_buys_for_symbol("INFY")
print(f"Cancelled {cancelled_count} orders")
```

## Portfolio Management

### View Holdings

```python
# Get all holdings
holdings = broker.get_holdings()

for holding in holdings:
    print(f"{holding.symbol}: {holding.quantity} shares")
    print(f"  Avg Price: ₹{holding.average_price.amount:.2f}")
    print(f"  Current: ₹{holding.current_price.amount:.2f}")
    print(f"  P&L: ₹{holding.calculate_pnl().amount:.2f}")
```

### View Specific Holding

```python
holding = broker.get_holding("INFY")
if holding:
    print(f"Quantity: {holding.quantity}")
    print(f"Cost Basis: ₹{holding.calculate_cost_basis().amount:.2f}")
    print(f"Market Value: ₹{holding.calculate_market_value().amount:.2f}")
    print(f"P&L %: {holding.calculate_pnl_percentage():.2f}%")
```

### Account Information

```python
# Available balance
balance = broker.get_available_balance()
print(f"Cash: ₹{balance.amount:,.2f}")

# Account limits
limits = broker.get_account_limits()
print(f"Available Cash: ₹{limits['available_cash'].amount:,.2f}")
print(f"Portfolio Value: ₹{limits['portfolio_value'].amount:,.2f}")
print(f"Total Value: ₹{limits['total_value'].amount:,.2f}")
```

## Reports & Analytics

### Generate Portfolio Summary

```python
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter

reporter = PaperTradeReporter(broker.store)

# Console reports
reporter.print_summary()
reporter.print_holdings()
reporter.print_recent_orders(limit=10)
```

### Get Programmatic Reports

```python
# Portfolio summary
summary = reporter.portfolio_summary()
print(f"Total P&L: ₹{summary['total_pnl']:,.2f}")
print(f"Return %: {summary['return_percentage']:.2f}%")

# Holdings report
holdings_report = reporter.holdings_report()
for holding in holdings_report:
    print(f"{holding['symbol']}: P&L ₹{holding['pnl']:.2f}")

# Order statistics
stats = reporter.order_statistics()
print(f"Total Orders: {stats['total_orders']}")
print(f"Success Rate: {stats['success_rate']:.2f}%")

# Performance metrics
metrics = reporter.performance_metrics()
print(f"Win Rate: {metrics.get('win_rate', 0):.2f}%")
```

### Export Reports

```python
# Export to JSON
reporter.export_to_json("paper_trading/reports/report.json")

# Export to CSV
reporter.export_to_csv("paper_trading/reports/csv/")
```

## Advanced Scenarios

### Averaging Down (Your Strategy!)

```python
# Initial buy
order1 = Order(
    symbol="INFY",
    quantity=10,
    order_type=OrderType.MARKET,
    transaction_type=TransactionType.BUY
)
broker.place_order(order1)

# Stock dips, buy more (averaging down)
order2 = Order(
    symbol="INFY",
    quantity=10,
    order_type=OrderType.MARKET,
    transaction_type=TransactionType.BUY
)
broker.place_order(order2)

# Check averaged price
holding = broker.get_holding("INFY")
print(f"Average Price: ₹{holding.average_price.amount:.2f}")
print(f"Total Quantity: {holding.quantity}")
```

### EMA9 Exit Strategy

```python
# Monitor price relative to EMA9
# (Integrate with your existing indicators)

from core.indicators import Indicators

# Fetch data and calculate EMA9
# ... your existing code ...

# When price reaches EMA9, sell
if current_price >= ema9:
    order = Order(
        symbol="INFY",
        quantity=holding.quantity,  # Sell all
        order_type=OrderType.MARKET,
        transaction_type=TransactionType.SELL
    )
    broker.place_order(order)
```

### Using with Your ML Model

```python
# Your existing ML prediction
# ... model prediction code ...

if ml_verdict == "strong_buy" and rsi10 < 30:
    # Place paper trade
    order = Order(
        symbol=ticker,
        quantity=calculate_position_size(balance),
        order_type=OrderType.MARKET,
        transaction_type=TransactionType.BUY
    )
    broker.place_order(order)
```

### Batch Operations

```python
# Place multiple orders
symbols = ["INFY", "TCS", "RELIANCE", "HDFCBANK"]

for symbol in symbols:
    order = Order(
        symbol=symbol,
        quantity=5,
        order_type=OrderType.MARKET,
        transaction_type=TransactionType.BUY
    )
    try:
        order_id = broker.place_order(order)
        print(f"✅ {symbol}: {order_id}")
    except Exception as e:
        print(f"❌ {symbol}: {e}")
```

### Testing Different Capital Sizes

```python
# Small account
config_small = PaperTradingConfig(
    initial_capital=50000.0,
    storage_path="paper_trading/small_account"
)

# Large account
config_large = PaperTradingConfig(
    initial_capital=500000.0,
    storage_path="paper_trading/large_account"
)

# Run same strategy with different capital
```

### Simulating Market Conditions

```python
# Conservative (no slippage, no fees)
config_ideal = PaperTradingConfig(
    enable_slippage=False,
    enable_fees=False
)

# Realistic (with slippage and fees)
config_realistic = PaperTradingConfig(
    enable_slippage=True,
    slippage_range=(0.1, 0.3),
    enable_fees=True
)

# Aggressive slippage
config_worst = PaperTradingConfig(
    enable_slippage=True,
    slippage_range=(0.3, 0.5)
)
```

### Custom Price Provider

```python
# For testing with known prices
broker.price_provider.set_mock_price("INFY", 1450.00)
broker.price_provider.set_mock_price("TCS", 3500.00)

# Now orders will execute at these prices
```

### Account Summary

```python
# Get comprehensive summary
summary = broker.get_summary()

print("Account:", summary['account'])
print("Portfolio:", summary['portfolio'])
print("Statistics:", summary['statistics'])
```

### Reset Account

```python
# Start fresh (WARNING: Deletes all data!)
broker.reset()

# Account is reset to initial capital
# All orders and holdings are cleared
```

## Integration with Use Cases

### With PlaceOrderUseCase

```python
from modules.kotak_neo_auto_trader.application.use_cases import PlaceOrderUseCase

use_case = PlaceOrderUseCase(broker_gateway=broker)

req = OrderRequest.market_buy("INFY", quantity=10)
response = use_case.execute(req)

if response.success:
    print(f"Order: {response.order_id}")
else:
    print(f"Failed: {response.message}")
```

### With ExecuteTradesUseCase

```python
# Your existing trade execution logic works as-is!
# Just pass paper trading broker instead of real broker

from src.application.use_cases import ExecuteTradesUseCase

execute_uc = ExecuteTradesUseCase(
    broker=broker,  # Paper trading broker
    place_order_uc=place_order_uc,
    default_quantity=10
)

# Execute trades from analysis
# ... your existing code ...
```

## Best Practices

### 1. Always Disconnect

```python
try:
    broker.connect()
    # ... trading operations ...
finally:
    broker.disconnect()  # Ensures state is saved
```

### 2. Check Balance Before Trading

```python
balance = broker.get_available_balance()
estimated_cost = price * quantity * 1.05  # Include 5% buffer

if balance.amount >= estimated_cost:
    # Place order
    pass
else:
    print("Insufficient funds")
```

### 3. Validate Holdings Before Selling

```python
holding = broker.get_holding(symbol)
if holding and holding.quantity >= quantity_to_sell:
    # Place sell order
    pass
else:
    print("Insufficient holding")
```

### 4. Monitor P&L Regularly

```python
reporter = PaperTradeReporter(broker.store)
summary = reporter.portfolio_summary()

if summary['total_pnl'] < -5000:  # Stop loss
    print("⚠️ Stop loss triggered!")
    # Exit all positions
```

### 5. Use Configuration Presets

```python
# For testing strategy logic
config = PaperTradingConfig.minimal_fees()

# For realistic simulation
config = PaperTradingConfig.realistic()
```

## Error Handling

```python
from modules.kotak_neo_auto_trader.domain import Order

try:
    order = Order(
        symbol="INVALID",
        quantity=10,
        order_type=OrderType.MARKET,
        transaction_type=TransactionType.BUY
    )
    order_id = broker.place_order(order)
    
except ValueError as e:
    print(f"Validation error: {e}")
except RuntimeError as e:
    print(f"Execution error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Monitoring & Debugging

### Enable Verbose Logging

```python
config = PaperTradingConfig(
    log_all_operations=True,
    verbose_logging=True
)
```

### Check Storage

```python
# View storage statistics
stats = broker.store.get_statistics()
print(stats)

# Reload data from disk
broker.store.reload()
```

### Price Cache Info

```python
cache_info = broker.price_provider.get_cache_info()
print(f"Cached prices: {cache_info['total_cached']}")

# Clear cache to force fresh fetch
broker.price_provider.clear_cache()
```

## Next Steps

- Review [SETUP.md](./SETUP.md) for installation
- Check `examples/paper_trading_example.py` for complete example
- Integrate with your existing strategy code

