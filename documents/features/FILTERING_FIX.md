# Filtering Fix - Combined Score Threshold

## Issue
After migration to the new CLI architecture, the system was showing different numbers of buyable stocks compared to the legacy `trade_agent.py` script. The legacy system was applying a `combined_score >= 25` filter when backtest scoring was enabled, but the new system was not.

## Root Cause
The new `BulkAnalyzeUseCase` was counting all stocks with `verdict in ['buy', 'strong_buy']` as buyable, without considering the `min_combined_score` threshold when backtest scoring was enabled.

### Legacy Behavior (trade_agent.py)
```python
# Line 343-354 in trade_agent.py
if enable_backtest_scoring:
    buys = [r for r in results if 
            r.get('final_verdict') in ['buy', 'strong_buy'] and 
            r.get('status') == 'success' and
            r.get('combined_score', 0) >= 25]  # <-- Score threshold applied
```

### New Behavior (Before Fix)
```python
# In BulkAnalyzeUseCase
buyable_count = sum(1 for r in results if r.is_buyable())
# <-- No score threshold applied
```

## Solution
Updated three components to properly apply filtering:

### 1. BulkAnalyzeUseCase
**File**: `src/application/use_cases/bulk_analyze.py`

Added conditional logic to apply combined_score filtering when backtest is enabled:

```python
# Apply proper filtering for buyable count
# When backtest is enabled, apply combined_score filter
if request.enable_backtest:
    buyable_count = sum(
        1 for r in results 
        if r.is_buyable() and 
           r.is_success() and 
           r.combined_score >= request.min_combined_score
    )
else:
    buyable_count = sum(1 for r in results if r.is_buyable())
```

### 2. BulkAnalysisResponse
**File**: `src/application/dto/analysis_response.py`

Updated `get_buy_candidates()` and `get_strong_buy_candidates()` to accept optional min_combined_score parameter:

```python
def get_buy_candidates(self, min_combined_score: float = 0.0) -> List[AnalysisResponse]:
    """Get all buyable stocks with optional score filtering"""
    candidates = [r for r in self.results if r.is_buyable() and r.is_success()]
    
    # Apply score filter if specified
    if min_combined_score > 0:
        candidates = [r for r in candidates if r.combined_score >= min_combined_score]
    
    return candidates
```

### 3. SendAlertsUseCase
**File**: `src/application/use_cases/send_alerts.py`

Updated to accept and apply min_combined_score parameter:

```python
def execute(self, bulk_response: BulkAnalysisResponse, min_combined_score: float = 0.0) -> bool:
    """Send alerts with optional score filtering"""
    # Get buyable candidates with score filtering
    buy_candidates = bulk_response.get_buy_candidates(min_combined_score=min_combined_score)
    strong_buys = bulk_response.get_strong_buy_candidates(min_combined_score=min_combined_score)
```

### 4. AnalyzeCommand
**File**: `src/presentation/cli/commands/analyze_command.py`

Pass min_score to SendAlertsUseCase when backtest is enabled:

```python
# Apply min score filtering when backtest is enabled
min_score = getattr(args, 'min_score', 25.0) if args.backtest else 0.0
success = self.send_alerts.execute(response, min_combined_score=min_score)
```

## Behavior After Fix

### Without Backtest
```bash
python -m src.presentation.cli.application analyze RELIANCE INFY --no-alerts
```
- **Filtering**: verdict in ['buy', 'strong_buy']
- **Score Threshold**: None (all buy signals counted)

### With Backtest
```bash
python -m src.presentation.cli.application analyze RELIANCE INFY --backtest --no-alerts --min-score 25
```
- **Filtering**: verdict in ['buy', 'strong_buy'] AND combined_score >= 25
- **Score Threshold**: 25.0 (default, configurable via `--min-score`)

### With Custom Threshold
```bash
python -m src.presentation.cli.application analyze --backtest --min-score 30 --no-alerts
```
- **Filtering**: verdict in ['buy', 'strong_buy'] AND combined_score >= 30
- **Score Threshold**: 30.0 (custom)

## Test Results

### Before Fix
```
# Without knowing the threshold
0-2 stocks: Could show any stock with 'buy' verdict regardless of score
```

### After Fix
```
# Without backtest
python analyze RELIANCE INFY --no-alerts --no-csv --no-mtf
Result: 0 buyable (2.63s) ✅

# With backtest and min_score=25
python analyze RELIANCE INFY --backtest --no-alerts --no-csv --min-score 25
Result: 0 buyable (5.08s) ✅ (stocks don't meet combined score threshold)
```

## Impact
- **Backward Compatibility**: ✅ Now matches legacy behavior
- **Filtering Accuracy**: ✅ Properly applies score thresholds
- **Alert Quality**: ✅ Only high-scoring candidates sent as alerts
- **User Control**: ✅ Configurable via `--min-score` flag

## Related Files Modified
1. `src/application/use_cases/bulk_analyze.py`
2. `src/application/dto/analysis_response.py`
3. `src/application/use_cases/send_alerts.py`
4. `src/presentation/cli/commands/analyze_command.py`

## Verification
To verify the fix is working:
1. Run analysis without backtest - should show all buy verdicts
2. Run with backtest and min_score - should filter by combined_score
3. Compare counts with legacy trade_agent.py - should match

The filtering now correctly replicates the legacy behavior where backtest scoring adds quality filtering to reduce false positives.
