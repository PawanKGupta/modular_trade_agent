# Paper Trading Tests

## Running Tests

### Run all paper trading tests

```bash
pytest tests/paper_trading/ -v
```

### Run specific test file

```bash
pytest tests/paper_trading/test_paper_trading_basic.py -v
```

### Run specific test class

```bash
pytest tests/paper_trading/test_paper_trading_basic.py::TestMarketOrders -v
```

### Run specific test

```bash
pytest tests/paper_trading/test_paper_trading_basic.py::TestMarketOrders::test_place_market_buy -v
```

## Test Coverage

### Current Tests

- ✅ **TestConnection**: Connection management
- ✅ **TestInitialization**: Account initialization
- ✅ **TestMarketOrders**: Market order execution
- ✅ **TestSellOrders**: Sell order validation
- ✅ **TestPortfolio**: Portfolio management & averaging
- ✅ **TestOrderRetrieval**: Order search and retrieval
- ✅ **TestAccountLimits**: Account limits and balance
- ✅ **TestPersistence**: State persistence

### Future Test Ideas

- Limit order execution
- Slippage calculation
- Fee calculation
- Market hours enforcement
- AMO order execution
- Order cancellation
- Multiple symbol trading
- Error handling
- Edge cases (zero quantity, negative prices, etc.)

## Test Configuration

Tests use a separate storage path (`paper_trading/test`) to avoid interfering with actual paper trading data.

## Cleanup

Tests automatically cleanup after themselves using fixtures and the `broker.reset()` method.

## Adding New Tests

1. Create test file in `tests/paper_trading/`
2. Import required modules
3. Create fixtures for broker and config
4. Write test classes and methods
5. Run with pytest

Example:

```python
import pytest
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters import PaperTradingBrokerAdapter

@pytest.fixture
def broker():
    broker = PaperTradingBrokerAdapter()
    broker.connect()
    yield broker
    broker.reset()

def test_something(broker):
    # Your test here
    assert True
```

