# Data Flow: `trade_agent.py --backtest`

## Overview
This document details the complete data flow when running `python trade_agent.py --backtest`, which enables backtest-enhanced stock analysis with historical performance validation.

## Command Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Entry Point: trade_agent.py --backtest                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. ARGUMENT PARSING (lines 396-410)                             │
│   • Parse --backtest flag → enable_backtest_scoring=True        │
│   • Parse --dip-mode flag → dip_mode=True (optional)            │
│   • Parse --no-csv, --no-mtf flags                              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. STOCK LIST RETRIEVAL (lines 264-269)                         │
│   Function: get_stocks()                                         │
│   • Scrapes stock list from screener website                    │
│   • Returns list of tickers (e.g., ["RELIANCE.NS", ...])        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. INITIAL ANALYSIS (lines 274-301)                             │
│   Function: analyze_multiple_tickers() OR loop analyze_ticker() │
│                                                                  │
│   For each ticker:                                               │
│   ┌──────────────────────────────────────────────────────────┐ │
│   │ 3a. Data Fetching (core/analysis.py:327-370)            │ │
│   │   • Fetch multi-timeframe data (daily + weekly)         │ │
│   │   • fetch_multi_timeframe_data() from data.py           │ │
│   │   • Add current day data (live mode only)               │ │
│   └──────────────────┬───────────────────────────────────────┘ │
│                      │                                           │
│   ┌──────────────────▼───────────────────────────────────────┐ │
│   │ 3b. Technical Indicators (lines 351-366)                │ │
│   │   • compute_indicators(): RSI, EMA, Volume, etc.        │ │
│   │   • Clip data to as_of_date if backtesting              │ │
│   └──────────────────┬───────────────────────────────────────┘ │
│                      │                                           │
│   ┌──────────────────▼───────────────────────────────────────┐ │
│   │ 3c. Signal Detection (lines 379-421)                    │ │
│   │   • Pattern signals: hammer, engulfing, divergence      │ │
│   │   • RSI oversold signals (< 30)                         │ │
│   │   • Multi-timeframe confirmation (if enabled)           │ │
│   │     - TimeframeAnalysis.get_dip_buying_confirmation()  │ │
│   └──────────────────┬───────────────────────────────────────┘ │
│                      │                                           │
│   ┌──────────────────▼───────────────────────────────────────┐ │
│   │ 3d. Volume Analysis (lines 422-438)                     │ │
│   │   • assess_volume_quality_intelligent()                 │ │
│   │   • Time-adjusted volume (intraday aware)               │ │
│   │   • analyze_volume_pattern()                            │ │
│   └──────────────────┬───────────────────────────────────────┘ │
│                      │                                           │
│   ┌──────────────────▼───────────────────────────────────────┐ │
│   │ 3e. Fundamental Data (lines 443-452)                    │ │
│   │   • Fetch PE, PB from yfinance                          │ │
│   │   • Handle failures gracefully                          │ │
│   └──────────────────┬───────────────────────────────────────┘ │
│                      │                                           │
│   ┌──────────────────▼───────────────────────────────────────┐ │
│   │ 3f. Verdict Determination (lines 454-505)               │ │
│   │   Logic:                                                │ │
│   │   • Check RSI oversold + volume + fundamentals          │ │
│   │   • Above EMA200: RSI < 30 (standard)                   │ │
│   │   • Below EMA200: RSI < 20 (extreme)                    │ │
│   │   • MTF alignment score affects verdict strength        │ │
│   │   Outcomes: "avoid", "watch", "buy", "strong_buy"       │ │
│   └──────────────────┬───────────────────────────────────────┘ │
│                      │                                           │
│   ┌──────────────────▼───────────────────────────────────────┐ │
│   │ 3g. Trading Parameters (if buy/strong_buy)               │ │
│   │   • calculate_smart_buy_range()                         │ │
│   │   • calculate_smart_stop_loss()                         │ │
│   │   • calculate_smart_target()                            │ │
│   └──────────────────┬───────────────────────────────────────┘ │
│                      │                                           │
│                      └──► Result object with verdict             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. STRENGTH SCORE CALCULATION (lines 303-306)                   │
│   Function: compute_strength_score()                            │
│   • Score based on: signals, volume, MTF, support proximity     │
│   • Range: 0-100                                                 │
│   • Required for backtest scoring                               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌═════════════════════════════════════════════════════════════════┐
║ 5. BACKTEST SCORING (lines 308-338) - CORE OF --backtest        ║
║   Function: add_backtest_scores_to_results()                    ║
║   from core/backtest_scoring.py                                 ║
╠═════════════════════════════════════════════════════════════════╣
║                                                                  ║
║   For each stock result:                                         ║
║   ┌──────────────────────────────────────────────────────────┐ ║
║   │ 5a. Run Historical Backtest                              │ ║
║   │   Function: run_stock_backtest()                         │ ║
║   │   (lines 286-348)                                        │ ║
║   │                                                           │ ║
║   │   Mode Selection:                                        │ ║
║   │   • If integrated_backtest available:                    │ ║
║   │     └─► run_integrated_backtest()                        │ ║
║   │         ┌────────────────────────────────────────┐       │ ║
║   │         │ Integrated Backtest Steps:             │       │ ║
║   │         │ 1. Fetch 2-year historical data        │       │ ║
║   │         │ 2. For each day with RSI < 30:         │       │ ║
║   │         │    a. Run full analyze_ticker()        │       │ ║
║   │         │    b. Get verdict from trade agent     │       │ ║
║   │         │    c. Simulate trade execution         │       │ ║
║   │         │    d. Track to target/stop             │       │ ║
║   │         │ 3. Calculate performance metrics       │       │ ║
║   │         └────────────────────────────────────────┘       │ ║
║   │                                                           │ ║
║   │   • Else: run_simple_backtest() (fallback)               │ ║
║   │     └─► Basic RSI strategy without agent                 │ ║
║   │                                                           │ ║
║   │   Returns:                                                │ ║
║   │   • total_return_pct                                     │ ║
║   │   • win_rate                                             │ ║
║   │   • total_trades                                         │ ║
║   │   • vs_buy_hold                                          │ ║
║   │   • execution_rate                                       │ ║
║   └──────────────────┬───────────────────────────────────────┘ ║
║                      │                                           ║
║   ┌──────────────────▼───────────────────────────────────────┐ ║
║   │ 5b. Calculate Backtest Score                            │ ║
║   │   Function: calculate_backtest_score()                  │ ║
║   │   (lines 37-125)                                        │ ║
║   │                                                         │ ║
║   │   Score Components (0-100):                            │ ║
║   │   • Total Return (40%): 0-10% → 0-50pts, 10%+ → 50-100│ ║
║   │   • Win Rate (40%): Direct percentage                  │ ║
║   │   • vs Buy&Hold (20%): Alpha performance               │ ║
║   │   • Confidence adjustment: -20% if < 3 trades          │ ║
║   └──────────────────┬───────────────────────────────────────┘ ║
║                      │                                           ║
║   ┌──────────────────▼───────────────────────────────────────┐ ║
║   │ 5c. Calculate Combined Score                            │ ║
║   │   (line 388)                                            │ ║
║   │                                                         │ ║
║   │   combined_score = (strength_score * 0.5) +            │ ║
║   │                    (backtest_score * 0.5)               │ ║
║   │                                                         │ ║
║   │   • Balances current signals with historical proof     │ ║
║   └──────────────────┬───────────────────────────────────────┘ ║
║                      │                                           ║
║   ┌──────────────────▼───────────────────────────────────────┐ ║
║   │ 5d. Verdict Re-classification                           │ ║
║   │   (lines 392-444)                                       │ ║
║   │                                                         │ ║
║   │   RSI-Based Threshold Adjustment:                      │ ║
║   │   • RSI < 20: 30% lower thresholds (extreme oversold) │ ║
║   │   • RSI < 25: 20% lower thresholds                    │ ║
║   │   • RSI < 30: 10% lower thresholds                    │ ║
║   │                                                         │ ║
║   │   Confidence-Based Thresholds:                         │ ║
║   │   ┌───────────────────────────────────────┐            │ ║
║   │   │ High Confidence (≥5 trades):          │            │ ║
║   │   │ • strong_buy: BS≥60 & CS≥35  OR CS≥60│            │ ║
║   │   │ • buy: BS≥35 & CS≥22  OR CS≥35       │            │ ║
║   │   │ • watch: otherwise                    │            │ ║
║   │   └───────────────────────────────────────┘            │ ║
║   │   ┌───────────────────────────────────────┐            │ ║
║   │   │ Low Confidence (<5 trades):           │            │ ║
║   │   │ • strong_buy: BS≥65 & CS≥42  OR CS≥65│            │ ║
║   │   │ • buy: BS≥40 & CS≥28  OR CS≥45       │            │ ║
║   │   │ • watch: otherwise                    │            │ ║
║   │   └───────────────────────────────────────┘            │ ║
║   │                                                         │ ║
║   │   Output: final_verdict ("buy"/"strong_buy"/"watch")  │ ║
║   └──────────────────┬───────────────────────────────────────┘ ║
║                      │                                           ║
║   ┌──────────────────▼───────────────────────────────────────┐ ║
║   │ 5e. Recalculate Trading Parameters (NEW FIX!)           │ ║
║   │   (lines 456-512)                                       │ ║
║   │                                                         │ ║
║   │   IF final_verdict = "buy" OR "strong_buy":            │ ║
║   │   AND (missing buy_range OR target OR stop):           │ ║
║   │                                                         │ ║
║   │   Then calculate:                                       │ ║
║   │   • buy_range = calculate_smart_buy_range()            │ ║
║   │   • stop = calculate_smart_stop_loss()                 │ ║
║   │   • target = calculate_smart_target()                  │ ║
║   │                                                         │ ║
║   │   Fallback if error:                                    │ ║
║   │   • buy_range = (price*0.995, price*1.01)              │ ║
║   │   • stop = price*0.92                                   │ ║
║   │   • target = price*1.10                                 │ ║
║   └──────────────────┬───────────────────────────────────────┘ ║
║                      │                                           ║
║                      └──► Enhanced result with:                  ║
║                           • backtest metrics                     ║
║                           • combined_score                       ║
║                           • final_verdict                        ║
║                           • backtest_confidence                  ║
║                           • all trading parameters               ║
╚═════════════════════╩═══════════════════════════════════════════╝
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. SORTING & PRIORITIZATION (lines 313-341)                     │
│   Function: compute_trading_priority_score()                    │
│                                                                  │
│   Priority Score Components (0-100+):                           │
│   • Risk-Reward Ratio: Up to 40 points (≥4.0 → 40pts)          │
│   • RSI Level: Up to 25 points (≤15 → 25pts)                   │
│   • Volume Strength: Up to 20 points (≥4x → 20pts)             │
│   • MTF Alignment: Up to 10 points                             │
│   • PE Ratio: Up to 10 points (≤15 → 10pts)                    │
│   • Backtest Score: Up to 15 points (≥40 → 15pts)              │
│                                                                  │
│   Results sorted by priority score (highest first)             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. CSV EXPORT (lines 316-338)                                   │
│   File: analysis_results/bulk_analysis_final_{timestamp}.csv    │
│                                                                  │
│   Columns exported:                                             │
│   • ticker, status, verdict, final_verdict                      │
│   • combined_score, strength_score, last_close                  │
│   • buy_range, target, stop                                     │
│   • timeframe_analysis (stringified dict)                       │
│   • backtest (stringified dict with all metrics)                │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. FILTERING FOR TELEGRAM (lines 343-358)                       │
│                                                                  │
│   Filter criteria:                                               │
│   • final_verdict = "buy" OR "strong_buy"                       │
│   • status = "success"                                           │
│   • combined_score ≥ 25                                          │
│                                                                  │
│   Separate into:                                                 │
│   • strong_buys (final_verdict = "strong_buy")                  │
│   • regular_buys (final_verdict = "buy")                        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. TELEGRAM NOTIFICATION (lines 359-394)                        │
│   Function: send_telegram()                                     │
│                                                                  │
│   Message Format:                                               │
│   *Reversal Buy Candidates (today) with Backtest Scoring*      │
│                                                                  │
│   🔥 *STRONG BUY* (Multi-timeframe confirmed):                  │
│   1) TICKER - ₹123.45                                           │
│      Buy: 120-125 | Target: 140 | Stop: 115                    │
│      RSI:25 MTF:9/10 RR:3.2x                                    │
│      StrongSupp:1.2% ExtremeRSI NearSupport                     │
│      PE:15.2 Vol:2.1x News:Neu +0.00 (0)                        │
│      Backtest: 58/100 (+6.5% return, 100% win, 2 trades)       │
│      Combined Score: 42.3/100                                   │
│      Confidence: 🟡 Medium                                       │
│                                                                  │
│   📈 *BUY* candidates:                                           │
│   [Similar format for regular buys]                             │
└─────────────────────────────────────────────────────────────────┘

## Key Data Structures

### Stock Result Object (after initial analysis)
```python
{
    'ticker': 'RELIANCE.NS',
    'status': 'success',
    'verdict': 'buy',              # Original verdict
    'last_close': 2450.50,
    'rsi': 25.3,
    'signals': ['rsi_oversold', 'excellent_uptrend_dip'],
    'buy_range': (2440, 2460),
    'target': 2680,
    'stop': 2255,
    'strength_score': 65,           # From compute_strength_score()
    'timeframe_analysis': {
        'alignment_score': 9,
        'confirmation': 'excellent_uptrend_dip',
        'daily_analysis': {...},
        'weekly_analysis': {...}
    },
    'pe': 22.5,
    'pb': 2.8,
    'avg_vol': 5000000,
    'today_vol': 8000000
}
```

### Enhanced Result Object (after backtest scoring)
```python
{
    # ... all fields from above, plus:

    'backtest': {
        'score': 58.5,              # Backtest score (0-100)
        'total_return_pct': 6.5,    # Historical return
        'win_rate': 100.0,          # Win percentage
        'total_trades': 2,          # Number of trades
        'vs_buy_hold': 45.2,        # Alpha vs buy-and-hold
        'execution_rate': 8.3       # % of signals executed
    },
    'combined_score': 42.3,         # (strength_score + backtest_score) / 2
    'final_verdict': 'buy',         # Re-classified verdict
    'backtest_confidence': 'Medium' # Based on trade count
}
```

## Performance Characteristics

### Execution Time (for 50 stocks)
- **Without --backtest**: ~2-3 minutes
  - Initial analysis only
  - No historical backtesting

- **With --backtest**: ~15-25 minutes
  - Initial analysis: ~2-3 minutes
  - Backtest scoring: ~12-20 minutes (depends on data availability)
    - Per stock: ~15-30 seconds
    - Uses integrated backtest with full trade agent simulation

### Memory Usage
- Initial analysis: ~200-300 MB
- With backtest: ~500-800 MB (historical data caching)

## Error Handling

### Backtest Errors
If backtest fails for a stock:
1. Logs error but continues
2. Sets backtest_score = 0
3. combined_score = strength_score (fallback)
4. Stock still included in results

### Missing Parameters
If verdict upgraded but parameters missing:
1. Attempts to recalculate buy_range, target, stop
2. On failure, uses safe defaults:
   - buy_range: (price*0.995, price*1.01)
   - stop: price*0.92
   - target: price*1.10

## Configuration Options

### Command-Line Flags
- `--backtest`: Enable backtest scoring (main flag)
- `--dip-mode`: More permissive volume thresholds
- `--no-csv`: Disable CSV export
- `--no-mtf`: Disable multi-timeframe analysis

### Environment Variables
- None (uses default config from config.py)

## Related Files

### Core Files
- `trade_agent.py`: Main entry point
- `core/analysis.py`: Stock analysis logic
- `core/backtest_scoring.py`: Backtest integration
- `integrated_backtest.py`: Full backtest simulation
- `core/scoring.py`: Strength score calculation

### Data Files
- `core/data.py`: Data fetching (yfinance)
- `core/mtf_analysis.py`: Multi-timeframe confirmation
- `core/volume_analysis.py`: Volume quality assessment

### Output Files
- `analysis_results/bulk_analysis_final_*.csv`: Final results with backtest data
- `analysis_results/bulk_analysis_*.csv`: Initial analysis (if CSV enabled)

## Recent Fixes

### 2025-11-02: Conservative Bias & Missing Parameters
1. **Reduced thresholds** for verdict upgrades (10-20% reduction)
2. **Added parameter recalculation** for upgraded verdicts
3. Both fixes implemented in `core/backtest_scoring.py`

See: `documents/bug_fixes/FIX_CONSERVATIVE_BIAS_AND_MISSING_TARGETS.md`
