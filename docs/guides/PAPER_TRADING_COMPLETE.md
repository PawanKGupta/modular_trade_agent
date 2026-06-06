# ≡ƒôè Paper Trading System - Complete Guide

A complete paper trading system for testing your trading strategies without risking real money. Mimics Kotak Neo broker behavior with realistic execution, fees, and portfolio management.

**Last Updated:** 2026-05-28
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Web UI Setup](#web-ui-setup)
4. [Python API Setup](#python-api-setup)
5. [Configuration](#configuration)
6. [Usage Guide](#usage-guide)
7. [Unified Service Integration](#unified-service-integration)
8. [Advanced Features](#advanced-features)
9. [Reports & Analytics](#reports--analytics)
10. [Troubleshooting](#troubleshooting)
11. [Best Practices](#best-practices)

---

## Overview

### Purpose

Test your **mean reversion to EMA9 strategy** safely:
- No real money at risk
- Realistic market simulation
- Complete P&L tracking
- Learn and improve without losses

### Key Features

| Feature | Description |
|---------|-------------|
| ≡ƒöî **Drop-in Replacement** | Implements `IBrokerGateway` - swap with real broker |
| ≡ƒÆ░ **Virtual Capital** | Start with any amount (default Γé╣1 lakh) |
| ≡ƒôê **Live Prices** | Integrates with your existing data fetcher |
| ≡ƒÆ╕ **Realistic Fees** | Brokerage, STT, transaction charges, GST |
| ≡ƒÄ▓ **Slippage Simulation** | Realistic price slippage on execution |
| ≡ƒôè **Portfolio Tracking** | Holdings, averaging, P&L calculation |
| ≡ƒÆ╛ **Persistent State** | All data saved to JSON files |
| ≡ƒôæ **Detailed Reports** | Portfolio, orders, transactions, metrics |
| ΓÅ░ **Market Hours** | Enforce trading hours (optional) |
| ≡ƒöä **AMO Orders** | After Market Orders support |
| ≡ƒîÉ **Web UI** | Access via web interface |

---

## Quick Start

### 5-Minute Setup

```python
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig

# Create broker with Γé╣1 lakh
config = PaperTradingConfig(initial_capital=100000.0)
broker = PaperTradingBrokerAdapter(user_id=1, config=config)
broker.connect()

print(f"Balance: Γé╣{broker.get_available_balance().amount:,.2f}")
# Output: Balance: Γé╣100,000.00
```

### Place Your First Order

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
# Output: Order placed: PT202511130001
```

### Check Portfolio

```python
holdings = broker.get_holdings()
for h in holdings:
    print(f"{h.symbol}: {h.quantity} @ Γé╣{h.average_price.amount}")
```

### Generate Report

```python
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter

reporter = PaperTradeReporter(broker.store)
reporter.print_summary()
```

---

## Web UI Setup

**Paper trading is now accessible via the web interface!**

### Access Paper Trading

1. **Start the application** (Docker or manual setup)
2. **Access Web UI**: `http://localhost:5173`
3. **Login** with your account
4. **Navigate to Paper Trading**: `/dashboard/paper-trading`
5. **View Portfolio**: See your virtual holdings, balance, and P&L
6. **View History**: Check all paper trading transactions

### Configuration

- Paper trading capital is configured via Trading Config (`/dashboard/config`)
- Default: Γé╣1,00,000 (can be customized per user)
- Each user has their own separate paper trading portfolio
- Data stored in: `paper_trading/user_{user_id}/`

### API Endpoints

- `GET /api/v1/user/paper-trading/portfolio` - Get portfolio (DB-backed metrics; see below)
- `GET /api/v1/user/paper-trading/history` - Get trade history (paper orders and closed positions only)
- `POST /api/v1/user/paper-trading/execute` - Execute paper trade

### Web API portfolio vs simulator files

The dashboard **portfolio** and **history** endpoints read from the **application database** (`positions`, `orders`, user trading config), not from `paper_trading/user_{id}/account.json`:

| Field | Source |
|--------|--------|
| `initial_capital` | `UserTradingConfig.paper_trading_initial_capital` |
| `realized_pnl` / history `net_pnl` | Sum of closed paper positions (`trade_mode == PAPER` or user in paper mode with symbol-matched buy) |
| Open holdings / `unrealized_pnl` | Open paper positions + live marks |
| `available_cash` | **Derived** so `total_value = initial_capital + total_pnl` (display identity; may differ from the simulator wallet in `account.json`) |

Per-user JSON under `paper_trading/user_{user_id}/` (`account.json`, `orders.json`, etc.) is still used by the **Python paper broker adapter** during execution and reporting. After trades are persisted to the DB, the web API is the source of truth for portfolio and history totals.

---

## Python API Setup

### Basic Setup

```python
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig

# Create configuration
config = PaperTradingConfig(
    initial_capital=100000.0,  # Γé╣1 lakh
    enable_slippage=True,
    enable_fees=True,
    price_source="live"  # or "mock" for testing
)

# Initialize adapter
broker = PaperTradingBrokerAdapter(user_id=1, config=config)
broker.connect()

# Now use it exactly like the real broker!
# All IBrokerGateway methods are available
```

### Using with Existing Use Cases

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

---

## Configuration

### Default Configuration

```python
config = PaperTradingConfig()  # Uses sensible defaults
```

**Default Settings:**
- Initial Capital: Γé╣100,000
- Slippage: 0.1-0.3%
- Brokerage: 0.03%
- STT: 0.1% (sell side)
- Market Hours: 09:15 - 15:30

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
    transaction_charges_percentage=0.00325,
    gst_percentage=18.0,

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

---

## Usage Guide

### Basic Operations

#### Initialize & Connect

```python
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter
from modules.kotak_neo_auto_trader.config.paper_trading_config import PaperTradingConfig

config = PaperTradingConfig(initial_capital=100000.0)
broker = PaperTradingBrokerAdapter(user_id=1, config=config)
broker.connect()
print(f"Balance: Γé╣{broker.get_available_balance().amount:,.2f}")
```

#### Disconnect

```python
# Disconnect (auto-saves state)
broker.disconnect()

# Reconnect later
broker.connect()  # State is restored!
```

### Order Management

#### Place Market BUY Order

```python
from modules.kotak_neo_auto_trader.domain import Order, OrderType, TransactionType

order = Order(
    symbol="INFY",
    quantity=10,
    order_type=OrderType.MARKET,
    transaction_type=TransactionType.BUY
)
order_id = broker.place_order(order)
```

#### Place Limit Order

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

#### Place SELL Order

```python
order = Order(
    symbol="INFY",
    quantity=5,
    order_type=OrderType.MARKET,
    transaction_type=TransactionType.SELL
)
order_id = broker.place_order(order)
```

#### Get Order Status

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

#### Cancel Order

```python
success = broker.cancel_order(order_id)
if success:
    print("Order cancelled")
```

### Portfolio Management

#### View Holdings

```python
# Get all holdings
holdings = broker.get_holdings()

for holding in holdings:
    print(f"{holding.symbol}: {holding.quantity} shares")
    print(f"  Avg Price: Γé╣{holding.average_price.amount:.2f}")
    print(f"  Current: Γé╣{holding.current_price.amount:.2f}")
    print(f"  P&L: Γé╣{holding.calculate_pnl().amount:.2f}")
```

#### View Specific Holding

```python
holding = broker.get_holding("INFY")
if holding:
    print(f"Quantity: {holding.quantity}")
    print(f"Cost Basis: Γé╣{holding.calculate_cost_basis().amount:.2f}")
    print(f"Market Value: Γé╣{holding.calculate_market_value().amount:.2f}")
    print(f"P&L %: {holding.calculate_pnl_percentage():.2f}%")
```

#### Account Information

```python
# Available balance
balance = broker.get_available_balance()
print(f"Cash: Γé╣{balance.amount:,.2f}")

# Account limits
limits = broker.get_account_limits()
print(f"Available Cash: Γé╣{limits['available_cash'].amount:,.2f}")
print(f"Portfolio Value: Γé╣{limits['portfolio_value'].amount:,.2f}")
print(f"Total Value: Γé╣{limits['total_value'].amount:,.2f}")
```

### Advanced Scenarios

#### Averaging Down (Your Strategy!)

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
print(f"Average Price: Γé╣{holding.average_price.amount:.2f}")
print(f"Total Quantity: {holding.quantity}")
```

#### EMA9 Exit Strategy

```python
# Monitor price relative to EMA9
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

### Sell target parity with live Kotak (placement time)

Paper trading and live Kotak use the same helper at **sell placement**:

- **Module:** `modules/kotak_neo_auto_trader/services/sell_target_service.py`
- **`compute_sell_target()`** — realtime daily EMA9 (`IndicatorService.calculate_ema9_realtime`) plus NSE/BSE tick rounding (`round_sell_price`)
- **Paper:** `PaperTradingServiceAdapter._calculate_ema9()` and the paper portfolio API (`GET /paper-trading/portfolio`) call this helper with `live_price_manager=None` (Yahoo / cached OHLCV for LTP).
- **Live:** `SellOrderManager` uses the same EMA9 formula and delegates tick rounding to `round_sell_price` (via `round_to_tick_size`).

**What should match** when you compare targets at the moment a sell limit is placed:

| Factor | Paper | Live Kotak |
|--------|-------|------------|
| EMA9 formula | Realtime EMA9 (yesterday EMA + today LTP) | Same |
| Tick rounding | `round_sell_price` (fallback NSE/BSE rules if no scrip master) | Same helper; Kotak scrip master used when available |

**What can still differ** (expected):

1. **LTP source** — Paper uses Yahoo; live prefers Kotak live quotes when configured. Same formula, different input price.
2. **Tick size** — Live may use Kotak scrip-master tick; paper uses exchange fallback rules unless scrip is passed.
3. **Circuit limits** — Live uses `prepare_broker_sell_limit_price` (defer-only when EMA9 > upper circuit from Kotak quotes); paper does not apply this gate. See [Sell Order Implementation](../kotak_neo_trader/SELL_ORDER_IMPLEMENTATION_COMPLETE.md#circuit-limits-and-defer-only-placement).
4. **After placement** — Live sell monitor can **lower** the limit when EMA9 drops; paper keeps the **frozen** target until re-entry or exit (see `test_frozen_target_never_updates`).

### Target exit: paper vs integrated backtest

| Runtime | Data | How target is hit |
|---------|------|-------------------|
| **Integrated backtest** (`integrated_backtest.py`) | Daily OHLC only | `high >= frozen EMA9` on the bar → exit at target |
| **Paper trading** (`_monitor_sell_orders`) | Live LTP + open limit + Yahoo daily bar | (1) Limit fills when **LTP ≥ limit**; (2) if LTP did not fill but **Yahoo daily high ≥ target**, **fill the pending sell limit** at target price; (3) **RSI > 50** → market sell |

Paper uses live limit fills first; the daily-high path fills the same pending limit (not a separate market order) when the session high touched target.

For sell-order architecture and monitoring, see [Sell Order Implementation](../kotak_neo_trader/SELL_ORDER_IMPLEMENTATION_COMPLETE.md).

---

## Unified Service Integration

### Running Unified Service with Paper Trading

You have **TWO options** to run the unified trading service:

1. **Live Trading** (Real Money) - `run_trading_service.py`
2. **Paper Trading** (Simulated) - `run_trading_service_paper.py`

### Paper Trading Service Adapter

**Location:** `src/application/services/paper_trading_service_adapter.py`

The `PaperTradingServiceAdapter` provides a `TradingService`-compatible interface for paper trading mode. This allows individual services to work in paper trading mode without requiring broker credentials.

**Key Features:**
- Drop-in replacement for real trading service
- Uses `PaperTradingBrokerAdapter` instead of real broker
- Supports all trading operations (analysis, order placement, monitoring)
- Per-user paper trading portfolios
- Integration with `IndividualServiceManager`

### Comparison

| Feature | Live Trading | Paper Trading |
|---------|-------------|---------------|
| **Real Money** | Γ£à Yes | Γ¥î No (Virtual) |
| **Kotak Neo Login** | Γ£à Required | Γ¥î Not needed |
| **Order Execution** | Γ£à Real broker | Γ£à Simulated |
| **Market Analysis** | Γ£à Real data | Γ£à Real data |
| **Portfolio Tracking** | Γ£à Real holdings | Γ£à Virtual holdings |
| **Reports** | Γ£à Real P&L | Γ£à Simulated P&L |
| **Risk** | ΓÜá∩╕Å Financial risk | Γ£à No risk |

### Web UI (Recommended)

The web UI provides the easiest way to manage paper trading:

1. **Access**: `http://localhost:5173/dashboard/service`
2. **Start Service**: Click "Start Service" button
3. **Monitor**: View service status, logs, and task history
4. **Paper Trading**: Access via `/dashboard/paper-trading`

### CLI (Advanced Users)

```bash
# Run with default settings (Γé╣1 lakh virtual capital)
python modules/kotak_neo_auto_trader/run_trading_service_paper.py

# With custom capital
python modules/kotak_neo_auto_trader/run_trading_service_paper.py --capital 200000

# With custom storage path
python modules/kotak_neo_auto_trader/run_trading_service_paper.py --storage-path paper_trading/my_account
```

---

## Advanced Features

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

### Price Feeds

**Live Prices:**
```python
config = PaperTradingConfig(price_source="live")
# Uses your existing DataFetcher to get real-time prices
# Falls back to YFinance if broker data unavailable
```

**Mock Prices:**
```python
config = PaperTradingConfig(price_source="mock")
# Generates deterministic mock prices (for testing)
```

**Manual Price Setting:**
```python
# For unit tests
broker.price_provider.set_mock_price("INFY", 1450.50)
```

---

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
print(f"Total P&L: Γé╣{summary['total_pnl']:,.2f}")
print(f"Return %: {summary['return_percentage']:.2f}%")

# Holdings report
holdings_report = reporter.holdings_report()
for holding in holdings_report:
    print(f"{holding['symbol']}: P&L Γé╣{holding['pnl']:.2f}")

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

### Example Output

```
============================================================
≡ƒôè PAPER TRADING SUMMARY
============================================================
Initial Capital:    Γé╣       100,000.00
Current Value:      Γé╣        98,450.75
Cash Balance:       Γé╣        65,320.50
Portfolio Value:    Γé╣        33,130.25
------------------------------------------------------------
Total P&L:          Γé╣        -1,549.25 (-1.55%)
  Realized:         Γé╣          -850.00
  Unrealized:       Γé╣          -699.25
------------------------------------------------------------
Holdings Count:                      3
============================================================
```

---

## Data Storage

### Simulator (Python adapter)

The in-process paper broker persists state under `paper_trading/user_{user_id}/` (or legacy `paper_trading/data/`):

```
paper_trading/user_{user_id}/
  account.json       # Simulator wallet (cash, marks during execution)
  orders.json        # Adapter order log
  holdings.json      # Adapter holdings snapshot
  transactions.json  # Execution history
  config.json        # Adapter configuration
```

### Web API (FastAPI)

Portfolio and trade-history responses are built from the **shared DB** (`positions`, `orders`, trading config). They filter to **paper** rows only and align realized P&L between `/portfolio` and `/history` via the same closed-position rules. Do not expect `available_cash` on the API to match `account.json` byte-for-byte; the API uses a derived cash balance for consistent `total_value`.

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

# Account is reset to initial capital
# All orders and holdings are cleared
```

---

## Troubleshooting

### Prices Not Available

```python
# Solution 1: Use mock prices
config = PaperTradingConfig(price_source="mock")

# Solution 2: Check DataFetcher is working
from core.data_fetcher import DataFetcher
fetcher = DataFetcher()
data = fetcher.fetch_data_yfinance("INFY", period="1d")
```

### Insufficient Funds Error

```python
# Check balance
balance = broker.get_available_balance()
print(f"Balance: Γé╣{balance.amount}")

# Check order value
# Remember: Total cost = Order value + Charges
```

### State Not Persisting

```python
# Ensure auto_save is enabled
config = PaperTradingConfig(auto_save=True)

# Or manually save
broker.store.save_all()
```

### Orders Rejected

```python
# Check balance
balance = broker.get_available_balance()

# Check holdings (for sell orders)
holding = broker.get_holding(symbol)
```

---

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
    print("ΓÜá∩╕Å Stop loss triggered!")
    # Exit all positions
```

### 5. Use Configuration Presets

```python
# For testing strategy logic
config = PaperTradingConfig.minimal_fees()

# For realistic simulation
config = PaperTradingConfig.realistic()
```

---

## Architecture

```
Paper Trading System
Γöé
Γö£ΓöÇΓöÇ PaperTradingBrokerAdapter (IBrokerGateway)
Γöé   Γö£ΓöÇΓöÇ OrderSimulator (execution, slippage, fees)
Γöé   Γö£ΓöÇΓöÇ PortfolioManager (holdings, P&L)
Γöé   Γö£ΓöÇΓöÇ PriceProvider (live/mock prices)
Γöé   ΓööΓöÇΓöÇ PaperTradeStore (persistence)
Γöé
Γö£ΓöÇΓöÇ Configuration (PaperTradingConfig)
Γöé   Γö£ΓöÇΓöÇ Capital settings
Γöé   Γö£ΓöÇΓöÇ Execution settings
Γöé   Γö£ΓöÇΓöÇ Fee structure
Γöé   ΓööΓöÇΓöÇ Storage settings
Γöé
ΓööΓöÇΓöÇ Reporting (PaperTradeReporter)
    Γö£ΓöÇΓöÇ Portfolio summary
    Γö£ΓöÇΓöÇ Order history
    Γö£ΓöÇΓöÇ Performance metrics
    ΓööΓöÇΓöÇ Export (JSON/CSV)
```

---

## Integration

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

---

## Important Notes

- **No Real Money**: This is simulation only
- **Price Accuracy**: Mock prices are for testing; live prices need data source
- **Slippage Varies**: Real market conditions may differ
- **No Market Impact**: Assumes infinite liquidity
- **Backup Data**: Create backups before resetting

---

## Next Steps

1. Run the example: `python examples/paper_trading_example.py`
2. Test your strategy with paper trading
3. Analyze results and refine strategy
4. Go live with confidence when ready!

---

**Remember**: Paper trading is for learning and testing. Real trading involves actual risk. Trade responsibly!
