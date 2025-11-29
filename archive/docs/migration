# Field Mapping Analysis: trades_history.json → Orders Table

## Orders Table Columns
- `id` (auto-generated)
- `user_id` (from migration parameter)
- `symbol` ✓
- `side` ✓ (hardcoded as 'buy'/'sell')
- `order_type` ✓ (hardcoded as 'MARKET')
- `quantity` ✓
- `price` (None for market orders)
- `status` ✓
- `avg_price` ✓
- `placed_at` ✓
- `filled_at` ✓
- `closed_at` ✓
- `orig_source` ✓ (hardcoded as 'signal')
- `order_id` (None)
- `broker_order_id` ✓

## trades_history.json Fields

### Mapped Fields ✓
- `symbol` → `symbol` (or via `ticker` using `extract_symbol()`)
- `ticker` → `symbol` (via `extract_symbol()`)
- `entry_price` → `avg_price` (for buy orders)
- `qty` → `quantity`
- `entry_time` → `placed_at`, `filled_at`
- `status` → `status`
- `exit_time` → `closed_at` (for sell orders)
- `exit_price` → `avg_price` (for sell orders)
- `order_response.orderId` → `broker_order_id`

### NOT Mapped Fields ✗
1. **`placed_symbol`** - The actual symbol that was placed (e.g., "GLENMARK-EQ")
   - Might differ from `symbol` or `ticker`
   - Could be important for broker order matching

2. **`signal_type`** - Type of signal (e.g., "buy", "strong_buy")
   - Could indicate signal strength/quality
   - Currently not stored anywhere

3. **`exit_note`** - Notes about exit (e.g., "Sold manually - updated on 2025-10-30")
   - Contains important context about why/how trade was closed
   - Currently lost during migration

## Recommendations

### Option 1: Add metadata JSON column to Orders
Add a `metadata` JSON column to store additional fields:
- `placed_symbol`
- `signal_type`
- `exit_note` (for sell orders)
- Any other trade-specific metadata

### Option 2: Store in Activity table
Store `exit_note` as Activity records when orders are closed.

### Option 3: Use placed_symbol for symbol
If `placed_symbol` is more accurate, use it instead of `symbol`/`ticker`.

### Option 4: Add specific columns
Add dedicated columns:
- `placed_symbol` (String)
- `signal_type` (String)
- `exit_note` (String or Text)

## Current Status
The migration script currently maps all essential trading data but loses:
- Signal type information
- Exit notes/context
- Original placed symbol (if different)
