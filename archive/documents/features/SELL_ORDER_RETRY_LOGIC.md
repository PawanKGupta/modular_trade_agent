# Sell Order Retry Logic - Implementation

## Overview
Implemented automatic retry mechanism for sell orders that are rejected due to insufficient quantity. The system now automatically fetches the actual available quantity from the broker and retries the order once.

## Problem Statement
When the system attempts to sell a quantity based on trade history, but the actual quantity in holdings is different (due to manual trades, partial fills, etc.), the sell order gets rejected.

Example:
- Trade history shows: 100 shares of YESBANK
- Actual holdings: 10 shares (manually traded)
- Sell order for 100 shares → **REJECTED**

## Solution
Added intelligent retry logic that:
1. Detects sell order rejection due to insufficient quantity
2. Fetches actual available quantity from broker holdings API
3. Retries sell order with the actual available quantity (ONE TIME only)

## Implementation Details

### Location
File: `modules/kotak_neo_auto_trader/auto_trade_engine.py`
Method: `evaluate_reentries_and_exits()` (lines ~1004-1090)

### Logic Flow

```
1. Place sell order with expected quantity
   ↓
2. Check if order was rejected
   ↓
3. IF rejected due to insufficient quantity:
   ├─→ Fetch holdings from broker API
   ├─→ Find actual available quantity for symbol
   ├─→ Retry sell order with actual quantity
   └─→ Update total_qty to reflect actual sold amount
   ↓
4. Mark entries as closed in trade history
```

### Detection Mechanism

The system detects rejection by checking:
- Response is `None` (order failed)
- Response contains `error` or `errors` keys
- Error message contains keywords: `insufficient`, `quantity`, `qty`, `not enough`, `exceed`

### Holdings Fetch

Uses `portfolio.get_holdings()` API to fetch actual quantity:
```python
holdings_response = self.portfolio.get_holdings()
# Extracts quantity from response['data']
# Handles multiple field name variations: quantity, qty, netQuantity, holdingsQuantity
```

### Symbol Matching

Robust symbol matching handles variations:
- `tradingSymbol`, `symbol`, `instrumentName`
- Removes `-EQ` suffix
- Case-insensitive comparison

### Safety Features

1. **Single Retry**: Only retries once to prevent infinite loops
2. **Quantity Validation**: Only retries if `actual_qty > 0`
3. **Error Handling**: Wrapped in try-except to prevent crashes
4. **Detailed Logging**: Logs all steps for debugging
5. **Telegram Alerts**: Sends notifications when retry fails

## Example Scenario

### Before Implementation
```
[System] Selling 100 shares of YESBANK
[Broker] Order REJECTED - Insufficient quantity (only 10 available)
[System] Trade marked as closed (but not actually sold)
```

### After Implementation
```
[System] Selling 100 shares of YESBANK
[Broker] Order REJECTED - Insufficient quantity
[System] Detecting rejection due to insufficient quantity
[System] Fetching holdings from broker...
[System] Found 10 shares available in holdings (expected 100)
[System] Retrying sell with 10 shares
[Broker] Order ACCEPTED
[System] Trade marked as closed with actual quantity: 10
```

## Benefits

1. **Handles Manual Trades**: Automatically adjusts for manually executed trades
2. **Handles Partial Fills**: Works with partially filled orders
3. **Prevents Failed Exits**: Ensures positions are properly closed even with quantity mismatches
4. **No Manual Intervention**: Fully automated - no user action required

## Logging

The implementation provides detailed logs:
- `Sell order rejected for {symbol} (likely insufficient qty): {response}`
- `Retrying sell order for {symbol} with broker available quantity...`
- `Found {actual_qty} shares available in holdings for {symbol} (expected {total_qty})`
- `Retry sell order placed for {symbol}: {actual_qty} shares`
- `Sell order retry FAILED for {symbol} - Telegram alert sent`

## Telegram Notifications

The system sends Telegram alerts in the following failure scenarios:

### 1. Retry Order Failed
When the retry order also gets rejected:
```
❌ SELL ORDER RETRY FAILED

📊 Symbol: YESBANK
💼 Expected Qty: 100
📦 Available Qty: 10
📈 Price: ₹22.77
📉 RSI10: 56.6
📍 EMA9: ₹22.74

⚠️ Both initial and retry sell orders failed.
🔧 Manual intervention may be required.

⏰ Time: 2025-10-28 13:45:30
```

### 2. Holdings Not Found
When the symbol doesn't exist in holdings:
```
❌ SELL ORDER RETRY FAILED

📊 Symbol: YESBANK
💼 Expected Qty: 100
📦 Available Qty: 0 (not found in holdings)
📈 Price: ₹22.77

⚠️ Cannot retry - symbol not found in holdings.
🔧 Manual check required.
```

### 3. Holdings Fetch Failed
When the broker API fails to respond:
```
❌ SELL ORDER RETRY FAILED

📊 Symbol: YESBANK
💼 Expected Qty: 100
📈 Price: ₹22.77

⚠️ Failed to fetch holdings from broker.
Cannot determine actual available quantity.
🔧 Manual intervention required.
```

### 4. Exception During Retry
When an unexpected error occurs:
```
❌ SELL ORDER RETRY EXCEPTION

📊 Symbol: YESBANK
💼 Expected Qty: 100
📈 Price: ₹22.77

⚠️ Error: ConnectionError: Timeout
🔧 Manual intervention required.
```

## Testing Recommendations

Test with:
1. **Scenario 1**: Sell order with exact matching quantity
2. **Scenario 2**: Sell order with more quantity than available
3. **Scenario 3**: Sell order when holding doesn't exist
4. **Scenario 4**: Manual trade followed by automated sell

## Notes

- This feature works **only for EXIT orders** (not for buy/re-entry)
- Retry happens **immediately** (no delay)
- Logs warnings for failed retries but doesn't stop execution
- Trade history is updated with actual sold quantity

## Related Files

- `auto_trade_engine.py` - Main implementation
- `portfolio.py` - Holdings API interface
- `orders.py` - Order placement interface

## Future Enhancements

Potential improvements:
1. Add retry counter to prevent future edge cases
2. ~~Add Telegram notification for quantity mismatches~~ ✅ **IMPLEMENTED**
3. Store quantity discrepancy in trade history for analytics
4. Extend to re-entry orders (currently only for exits)
5. Add automatic position reconciliation after failed retry
