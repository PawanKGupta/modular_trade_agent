# Regression Fixes After Retry Logic Bug Fixes

This document explains the regression failures that occurred after fixing the retry logic bugs and how they were resolved.

## Issues Fixed

### 1. Unit Tests: Mock `order_metadata` for Ticker Extraction

**Problem:** After the bug fix, retry logic now extracts ticker from `order_metadata.get("ticker")` first, then falls back to constructing from symbol. Unit tests were only mocking `mock_db_order.ticker` directly, which no longer works.

**Files Affected:**
- `tests/unit/kotak/test_capital_recalculation_on_retry.py`
- `tests/unit/kotak/test_retry_service_migration.py`

**Fix:** Added `mock_db_order.order_metadata = {"ticker": ticker}` to all mock order setups.

**Example:**
```python
# Before (broken)
mock_db_order = Mock()
mock_db_order.ticker = "RELIANCE.NS"

# After (fixed)
mock_db_order = Mock()
mock_db_order.ticker = "RELIANCE.NS"
mock_db_order.order_metadata = {"ticker": "RELIANCE.NS"}  # ✅ Added
```

### 2. Paper Trading Tests: Wrong Import Path for Recommendation

**Problem:** Tests were importing `Recommendation` from a non-existent module:
```python
from modules.kotak_neo_auto_trader.recommendation import Recommendation  # ❌ Wrong
```

**Files Affected:**
- `tests/integration/kotak/test_paper_trading_workflow_integration.py`

**Fix:** Changed import to correct path:
```python
from modules.kotak_neo_auto_trader.auto_trade_engine import Recommendation  # ✅ Correct
```

### 3. Paper Trading Tests: Wrong Recommendation Constructor Parameters

**Problem:** Tests were using old `Recommendation` constructor with parameters that don't exist:
```python
Recommendation(
    ticker="RELIANCE.NS",
    symbol="RELIANCE",  # ❌ Doesn't exist
    verdict="buy",
    rsi=25.0,           # ❌ Doesn't exist
    ema9=2500.0,        # ❌ Doesn't exist
    close=2450.0,       # ❌ Doesn't exist
)
```

**Fix:** Updated to use correct constructor signature:
```python
Recommendation(
    ticker="RELIANCE.NS",
    verdict="buy",
    last_close=2450.0,  # ✅ Correct
)
```

### 4. Paper Trading Tests: TypeError with Summary Comparison

**Problem:** `summary.get("placed", 0) >= 1` was failing with `TypeError: '>=' not supported between instances of 'int' and 'Mock'`. This suggests `summary.get("placed", 0)` was returning a Mock instead of an int.

**Fix:** Added type checks to ensure summary is a dict and values are ints:
```python
# Before (broken)
summary = service.engine.place_new_entries(recs)
assert summary.get("placed", 0) >= 1

# After (fixed)
summary = service.engine.place_new_entries(recs)
# Ensure summary is a dict, not a Mock
assert isinstance(summary, dict), f"Expected dict, got {type(summary)}"
placed_count = summary.get("placed", 0)
assert isinstance(placed_count, int), f"Expected int, got {type(placed_count)}"
assert placed_count >= 1
```

## Summary

All regression failures were due to:
1. **Missing mocks** for the new `order_metadata` extraction logic
2. **Wrong import paths** for `Recommendation` class
3. **Outdated constructor calls** using non-existent parameters
4. **Type safety issues** with Mock objects in assertions

These fixes ensure tests work correctly with the new retry logic that extracts ticker from `order_metadata` first.
