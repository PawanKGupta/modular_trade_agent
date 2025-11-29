# Fix: Exclude Today's Incomplete Candle During Market Hours

## Problem
The candle quality analysis was incorrectly penalizing stocks by including **today's incomplete/partial candle** during market hours. This caused false penalties because:
- Intraday candles are not complete and can be misleading
- Example: GLENMARK got penalized for a "large red candle" when today's actual candle was tiny (-0.13%)

## Root Cause
The system was analyzing the 3 most recent candles including today's partial candle when run during market hours (9:15 AM - 3:30 PM IST).

## Solution
Modified `core/candle_analysis.py` to:

1. **Detect market hours** - Added `is_market_open()` function that checks:
   - Current time is between 9:15 AM - 3:30 PM IST
   - Current day is a weekday (Mon-Fri)

2. **Detect today's candle** - Added `is_today_candle()` function to identify if a candle is from today

3. **Exclude incomplete candles** - Modified `analyze_recent_candle_quality()` to:
   - Check if market is currently open
   - If open and last candle is from today, exclude it
   - Only analyze **completed candles** (yesterday and before)
   - Add `excluded_today` flag to return dict for transparency

## Changes Made

### Files Modified
- `core/candle_analysis.py`
  - Added `from datetime import datetime, time` import
  - Added `is_market_open()` function
  - Added `is_today_candle()` function
  - Modified `analyze_recent_candle_quality()` to exclude today's candle during market hours
  - Updated return dict to include `excluded_today: bool` field

### Test Files Created
- `test_candle_fix.py` - Verifies the candle exclusion logic
- `test_market_hours.py` - Tests market hours detection
- `check_glenmark.py` - Manual verification script for GLENMARK data

## Behavior

### During Market Hours (9:15 AM - 3:30 PM, Mon-Fri)
- ✅ Excludes today's incomplete candle
- ✅ Analyzes only 3 completed candles (yesterday and 2 days before)
- ✅ `excluded_today = True` in result

### Outside Market Hours (After 3:30 PM, weekends)
- ✅ Includes all candles (today's is now complete)
- ✅ Analyzes 3 most recent candles including today
- ✅ `excluded_today = False` in result

## Example
**Before Fix (during market hours):**
- Analyzed: Today (partial), Yesterday, 2 days ago
- Result: False penalties based on incomplete data

**After Fix (during market hours):**
- Analyzed: Yesterday, 2 days ago, 3 days ago
- Result: Accurate penalties based on completed candles only

## Testing
Run the test to verify:
```powershell
.\.venv\Scripts\python.exe test_candle_fix.py
```

Expected output:
- If market closed: `excluded_today = False` (includes all candles)
- If market open: `excluded_today = True` (excludes today)

## Impact
- ✅ More accurate candle quality analysis during trading hours
- ✅ Eliminates false penalties from incomplete candles
- ✅ Better buy/sell signal accuracy
- ✅ No impact on after-hours or end-of-day analysis
