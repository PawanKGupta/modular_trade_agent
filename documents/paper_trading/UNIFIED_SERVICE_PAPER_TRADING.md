# Running Unified Service with Paper Trading

## 🎯 Overview

You have **TWO options** to run the unified trading service:

1. **Live Trading** (Real Money) - `run_trading_service.py`
2. **Paper Trading** (Simulated) - `run_trading_service_paper.py`

---

## 📊 Comparison

| Feature | Live Trading | Paper Trading |
|---------|-------------|---------------|
| **Real Money** | ✅ Yes | ❌ No (Virtual) |
| **Kotak Neo Login** | ✅ Required | ❌ Not needed |
| **Order Execution** | ✅ Real broker | ✅ Simulated |
| **Market Analysis** | ✅ Real data | ✅ Real data |
| **Portfolio Tracking** | ✅ Real holdings | ✅ Virtual holdings |
| **Reports** | ✅ Real P&L | ✅ Simulated P&L |
| **Risk** | ⚠️ Financial risk | ✅ No risk |

---

## 🚀 Quick Start

### Option 1: Paper Trading Service (RECOMMENDED FOR TESTING)

Test your strategy without risk:

```bash
# Run with default settings (₹1 lakh virtual capital)
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service_paper.py

# Run with custom capital
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service_paper.py --capital 200000

# Run with custom storage path
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service_paper.py --storage paper_trading/my_test
```

### Option 2: Live Trading Service (PRODUCTION)

Real trading with real money:

```bash
# Requires Kotak Neo credentials in kotak_neo.env
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service.py
```

---

## ⚙️ Paper Trading Service Details

### What It Does

The paper trading service runs the **same workflows** as live trading:

| Time | Task | Description |
|------|------|-------------|
| **4:00 PM** | Market Analysis | Analyzes stocks (same as live) |
| **4:05 PM** | Place Buy Orders | Places virtual buy orders |
| **9:15 AM** | Sell Monitoring | Monitors sell conditions |
| **6:00 PM** | EOD Cleanup | Generates daily reports |

### What's Different

- ✅ **No Login Required** - No Kotak Neo credentials needed
- ✅ **Virtual Money** - Starts with configurable capital
- ✅ **Simulated Execution** - Orders execute instantly with slippage
- ✅ **Realistic Fees** - Includes brokerage, STT, etc.
- ✅ **Data Persistence** - All trades saved to JSON files
- ✅ **Daily Reports** - P&L tracking and performance metrics

---

## 📁 Data Storage

### Paper Trading Data Location

```
paper_trading/unified_service/
├── account.json          # Balance, capital, P&L
├── orders.json           # All paper trade orders
├── holdings.json         # Virtual portfolio
├── transactions.json     # Trade history
└── reports/              # Daily reports
    ├── report_20251113.json
    ├── report_20251114.json
    └── ...
```

### Live Trading Data Location

```
# Uses your existing trading data locations
# (configured in your current setup)
```

---

## 🔄 Switching Between Paper and Live

### Test Strategy with Paper Trading

1. **Start Paper Trading Service**
   ```bash
   .venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service_paper.py --capital 100000
   ```

2. **Let It Run for Days/Weeks**
   - Monitor paper trading P&L
   - Review reports daily
   - Validate strategy performance

3. **Analyze Results**
   ```bash
   # Check reports in paper_trading/unified_service/reports/
   ```

4. **If Satisfied, Switch to Live Trading**
   ```bash
   # Stop paper trading service
   # Start live trading service
   .venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service.py
   ```

---

## 📊 Monitoring Paper Trading

### View Real-Time Status

While the service is running, check logs:

```bash
# Logs show paper trading activity
tail -f logs/trade_agent_*.log
```

### Generate Reports

The service automatically generates reports at 6:00 PM. You can also check anytime:

```python
# In Python
from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter
from modules.kotak_neo_auto_trader.infrastructure.persistence import PaperTradeStore

store = PaperTradeStore("paper_trading/unified_service")
reporter = PaperTradeReporter(store)

reporter.print_summary()
reporter.print_holdings()
reporter.print_recent_orders(limit=10)
```

---

## ⚠️ Important Notes

### Paper Trading Limitations

1. **Price Execution**
   - Paper trading uses live prices but execution is instant
   - Real trading may have delays and rejections

2. **Market Impact**
   - Paper trading assumes infinite liquidity
   - Large real orders may impact market price

3. **Slippage**
   - Simulated slippage may differ from reality
   - Real slippage depends on market conditions

4. **Order Rejections**
   - Paper trading has simplified rejection logic
   - Real broker may reject for various reasons

### When to Use Each

**Use Paper Trading When:**
- ✅ Testing new strategy
- ✅ Learning the system
- ✅ Validating changes
- ✅ Practicing without risk
- ✅ Backtesting with live data

**Use Live Trading When:**
- ✅ Strategy is proven in paper trading
- ✅ Comfortable with the system
- ✅ Ready to take real positions
- ✅ Have proper risk management
- ✅ Monitor actively

---

## 🛠️ Advanced Configuration

### Custom Paper Trading Configuration

Modify `run_trading_service_paper.py` to customize:

```python
self.config = PaperTradingConfig(
    initial_capital=100000.0,      # Starting capital
    enable_slippage=True,           # Simulate slippage
    slippage_range=(0.1, 0.3),     # 0.1-0.3% slippage
    enable_fees=True,               # Include fees
    brokerage_percentage=0.03,      # 0.03% brokerage
    enforce_market_hours=True,      # Block after hours
    price_source="live",            # Use live prices
)
```

### Integration with Your Analysis

The paper trading service will use your existing `trade_agent.py` analysis:

```python
def run_analysis(self):
    """Run market analysis"""
    import trade_agent
    
    # Run your analysis
    results = trade_agent.main(export_csv=True)
    
    # Results are used for paper trading
    # (orders go to paper broker instead of real broker)
```

---

## 🎯 Recommended Workflow

### Phase 1: Paper Trading (1-2 weeks)

1. Start paper trading service
2. Let it run continuously
3. Review daily reports
4. Track performance metrics
5. Validate strategy effectiveness

### Phase 2: Evaluation

1. Analyze paper trading results
2. Check win rate and P&L
3. Review max drawdown
4. Verify strategy assumptions
5. Make adjustments if needed

### Phase 3: Live Trading (When Ready)

1. Stop paper trading service
2. Backup paper trading data
3. Start live trading service
4. Start with small positions
5. Scale up gradually

---

## 📈 Success Criteria

Before switching to live trading, ensure:

- ✅ **Positive P&L** over 2+ weeks paper trading
- ✅ **Win Rate** >50% (for your strategy)
- ✅ **Max Drawdown** acceptable to you
- ✅ **Strategy Logic** validated
- ✅ **Risk Management** in place
- ✅ **You're Comfortable** with the system

---

## 🆘 Troubleshooting

### Paper Trading Service Won't Start

```bash
# Check if storage directory exists
mkdir -p paper_trading/unified_service

# Check Python version
python --version  # Should be 3.10+

# Check dependencies
pip install -r requirements.txt
```

### Orders Not Executing in Paper Trading

- Check logs for errors
- Verify price provider is working
- Ensure market hours enforcement setting
- Check available balance

### Can't Switch to Live Trading

- Verify Kotak Neo credentials
- Check `kotak_neo.env` file exists
- Ensure only ONE service is running
- Stop paper trading before starting live

---

## 📚 Related Documentation

- **[Paper Trading Setup](./SETUP.md)** - Detailed setup guide
- **[Paper Trading Usage](./USAGE.md)** - Usage examples
- **[Unified Service Docs](../../documents/architecture/UNIFIED_TRADING_SERVICE.md)** - Live service docs
- **[Test Coverage](./TEST_COVERAGE_REPORT.md)** - Test validation

---

## ✅ Quick Reference

```bash
# PAPER TRADING (No Risk)
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service_paper.py

# LIVE TRADING (Real Money)
.venv\Scripts\python.exe modules\kotak_neo_auto_trader\run_trading_service.py

# View Paper Trading Reports
python -c "from modules.kotak_neo_auto_trader.infrastructure.simulation import PaperTradeReporter; from modules.kotak_neo_auto_trader.infrastructure.persistence import PaperTradeStore; PaperTradeReporter(PaperTradeStore('paper_trading/unified_service')).print_summary()"
```

---

**Remember**: Paper trading is a tool for validation. Always test thoroughly before risking real capital! 🎯

