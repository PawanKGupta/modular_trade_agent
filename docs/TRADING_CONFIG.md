# Trading Configuration Guide

Complete guide to configuring trading parameters in the Modular Trade Agent.

## Overview

The Trading Configuration page allows you to customize all aspects of your trading strategy, from technical indicators to risk management and order defaults.

## Access

Navigate to **Trading Config** in the sidebar or go to `/dashboard/config`.

## Configuration Sections

### 1. Strategy Configuration

Controls the core technical indicators used for signal generation.

#### RSI Settings

- **RSI Period** (default: 10)
  - Period for RSI calculation
  - Lower values = more sensitive
  - Recommended: 10-14

- **RSI Oversold Threshold** (default: 30)
  - Main oversold level for entry signals
  - Signals generated when RSI < this value
  - Recommended: 25-35

- **RSI Extreme Oversold** (default: 10)
  - Extreme oversold level
  - Used for additional entries
  - Must be < RSI Oversold
  - Recommended: 8-15

- **RSI Near Oversold** (default: 35)
  - Near oversold level
  - Used for early signals
  - Must be > RSI Oversold
  - Recommended: 30-40

**Validation:** Extreme < Oversold < Near (enforced)

### 2. Capital & Position Management

Controls capital allocation and position sizing.

#### Capital Settings

- **User Capital** (default: ₹2,00,000)
  - Total capital available for trading
  - Used for position sizing
  - Adjust based on your account size

- **Paper Trading Initial Capital** (default: ₹10,00,000)
  - Starting capital for paper trading
  - Separate from real trading capital
  - Can be any amount for testing

- **Max Portfolio Size**
  - Maximum number of positions
  - Prevents over-diversification
  - Recommended: 5-10

- **Max Position Volume Ratio** (default: 0.10 = 10%)
  - Maximum position size as % of daily volume
  - Prevents liquidity issues
  - Recommended: 0.05-0.15

- **Min Absolute Average Volume**
  - Minimum average daily volume required
  - Filters out illiquid stocks
  - Recommended: 10,000-50,000

### 3. Chart Quality Filters

Filters stocks based on chart pattern quality.

- **Chart Quality Enabled** (default: true)
  - Enable/disable chart quality filtering
  - Filters poor quality charts

- **Chart Quality Min Score** (default: 60.0)
  - Minimum chart quality score
  - Higher = stricter filtering
  - Range: 0-100

- **Max Gap Frequency** (default: 20.0%)
  - Maximum acceptable gap frequency
  - Filters charts with too many gaps
  - Lower = stricter

- **Min Daily Range %** (default: 1.5%)
  - Minimum daily price range
  - Filters flat/choppy charts
  - Higher = stricter

- **Max Extreme Candle Frequency** (default: 15.0%)
  - Maximum extreme candle frequency
  - Filters volatile/unstable charts
  - Lower = stricter

### 4. Risk Management

Controls stop losses, targets, and risk-reward ratios.

#### Stop Loss Settings

- **Default Stop Loss %** (default: 6.0%)
  - Standard stop loss percentage
  - Applied to most positions
  - Recommended: 5-8%

- **Tight Stop Loss %** (default: 4.0%)
  - Tighter stop for high-confidence trades
  - Applied to strong signals
  - Must be < Default
  - Recommended: 3-5%

- **Min Stop Loss %** (default: 3.0%)
  - Minimum stop loss allowed
  - Safety limit
  - Must be < Tight
  - Recommended: 2-4%

**Validation:** Min < Tight < Default (enforced)

#### Target Settings

- **Default Target %** (default: 8.0%)
  - Standard target percentage
  - Applied to most positions
  - Recommended: 6-12%

- **Strong Buy Target %** (default: 12.0%)
  - Higher target for strong signals
  - Applied to high-confidence trades
  - Recommended: 10-15%

- **Excellent Target %** (default: 15.0%)
  - Highest target for excellent setups
  - Applied to best signals
  - Recommended: 12-20%

#### Risk-Reward Ratios

- **Strong Buy Risk-Reward** (default: 2.0)
  - Minimum risk-reward for strong buys
  - Higher = more selective
  - Recommended: 1.5-3.0

- **Buy Risk-Reward** (default: 1.5)
  - Minimum risk-reward for buys
  - Recommended: 1.2-2.0

- **Excellent Risk-Reward** (default: 2.5)
  - Minimum risk-reward for excellent setups
  - Recommended: 2.0-3.5

### 5. Order Defaults

Default values for order placement.

- **Default Exchange** (default: NSE)
  - Stock exchange
  - Options: NSE, BSE

- **Default Product** (default: MIS)
  - Order product type
  - Options: MIS (Intraday), CNC (Delivery), NRML (Futures)

- **Default Order Type** (default: MARKET)
  - Order execution type
  - Options: MARKET, LIMIT

- **Default Variety** (default: REGULAR)
  - Order variety
  - Options: REGULAR, AMO (After Market Order)

- **Default Validity** (default: DAY)
  - Order validity
  - Options: DAY, IOC (Immediate or Cancel)

### 6. Behavior Toggles

Control system behavior and logic.

- **Allow Duplicate Recommendations Same Day**
  - Allow multiple signals for same stock per day
  - Default: false (recommended)

- **Exit on EMA9 or RSI50**
  - Exit condition
  - Exit when price reaches EMA9 OR RSI > 50
  - Default: true

- **Min Combined Score**
  - Minimum combined score for signals
  - Filters low-quality signals
  - Range: 0-100
  - Higher = more selective

- **Enable Premarket AMO Adjustment**
  - Adjust AMO orders in premarket
  - Default: true

### 7. News Sentiment

Configure news sentiment analysis.

- **News Sentiment Enabled** (default: true)
  - Enable/disable news sentiment analysis

- **Lookback Days** (default: 30)
  - Days to look back for news
  - More days = more data
  - Recommended: 7-30

- **Min Articles** (default: 2)
  - Minimum articles required
  - Filters stocks with insufficient news
  - Recommended: 1-5

- **Positive Threshold** (default: 0.25)
  - Sentiment score for positive news
  - Higher = stricter
  - Range: 0-1

- **Negative Threshold** (default: -0.25)
  - Sentiment score for negative news
  - Lower = stricter
  - Range: -1-0

### 8. ML Configuration

Configure machine learning features.

- **ML Enabled** (default: false)
  - Enable/disable ML-enhanced verdicts
  - Requires trained model

- **ML Model Version**
  - Select ML model version
  - Options: v1, v2, v3, v4, etc.
  - Use latest trained model

- **ML Confidence Threshold** (default: 0.7)
  - Minimum ML confidence required
  - Higher = more selective
  - Range: 0-1
  - Recommended: 0.6-0.8

- **ML Combine with Rules** (default: true)
  - Combine ML verdict with rule-based logic
  - More conservative approach
  - Recommended: true

## Configuration Presets

### Conservative
- Lower risk settings
- Tighter stop losses
- Higher quality filters
- Lower position sizes
- **Use Case:** Risk-averse traders

### Moderate
- Balanced settings
- Default values
- Good for most traders
- **Use Case:** General trading

### Aggressive
- Higher risk settings
- Wider stop losses
- More permissive filters
- Larger position sizes
- **Use Case:** Experienced traders

### Custom
- Your custom settings
- Saved automatically
- **Use Case:** Fine-tuned strategy

## Configuration Workflow

### Initial Setup

1. **Start with Preset:**
   - Choose Conservative, Moderate, or Aggressive
   - Click "Load Preset"

2. **Review Defaults:**
   - Review all sections
   - Understand each parameter

3. **Adjust as Needed:**
   - Modify parameters based on your strategy
   - Test with paper trading

4. **Save Configuration:**
   - Click "Save" to apply changes
   - Changes take effect immediately

### Fine-Tuning

1. **Monitor Performance:**
   - Review P&L regularly
   - Analyze win rate
   - Check signal quality

2. **Adjust Parameters:**
   - Modify underperforming parameters
   - Test changes incrementally

3. **Document Changes:**
   - Note what changed and why
   - Track performance impact

4. **Iterate:**
   - Continue refining
   - Optimize based on results

## Best Practices

### 1. Start Conservative
- Begin with conservative settings
- Gradually increase risk as you gain experience
- Test changes with paper trading

### 2. Understand Each Parameter
- Read parameter descriptions
- Understand impact on signals
- Don't change too many at once

### 3. Test Incrementally
- Change one parameter at a time
- Test with paper trading
- Monitor results before next change

### 4. Document Your Settings
- Note your custom configuration
- Track performance with each setting
- Keep a log of changes

### 5. Regular Review
- Review configuration monthly
- Adjust based on market conditions
- Optimize based on performance

### 6. Use Presets as Starting Point
- Start with a preset
- Customize from there
- Save your custom preset

## Common Configurations

### Day Trading Setup
- Product: MIS (Intraday)
- Tighter stop losses (3-4%)
- Shorter targets (4-6%)
- Higher position sizes
- Exit on EMA9 or RSI50: true

### Swing Trading Setup
- Product: CNC (Delivery)
- Wider stop losses (6-8%)
- Longer targets (10-15%)
- Moderate position sizes
- Exit on EMA9 or RSI50: true

### Conservative Setup
- Chart quality: Strict (high min score)
- Min combined score: High (60+)
- Lower position sizes (5-8%)
- Tighter stop losses
- ML combine with rules: true

### Aggressive Setup
- Chart quality: Permissive (lower min score)
- Min combined score: Low (30-40)
- Higher position sizes (12-15%)
- Wider stop losses
- ML combine with rules: false

## Troubleshooting

### No Signals Generated
- Check RSI thresholds (may be too strict)
- Lower min combined score
- Relax chart quality filters
- Check min absolute volume

### Too Many Signals
- Increase RSI thresholds
- Raise min combined score
- Stricter chart quality filters
- Increase min absolute volume

### Poor Performance
- Review stop loss settings
- Adjust risk-reward ratios
- Check exit conditions
- Review ML settings (if enabled)

### Orders Not Executing
- Check broker credentials
- Verify service is running
- Check order defaults
- Review logs for errors

## Advanced Tips

1. **Seasonal Adjustments:**
   - Adjust parameters for different market conditions
   - Bull market: More aggressive
   - Bear market: More conservative

2. **Sector-Specific Settings:**
   - Different sectors may need different settings
   - Consider sector volatility
   - Adjust position sizes accordingly

3. **Market Regime Awareness:**
   - High volatility: Wider stops
   - Low volatility: Tighter stops
   - Trending market: Higher targets

4. **Backtesting:**
   - Test configurations with historical data
   - Validate parameter choices
   - Optimize based on backtest results

## Configuration Validation

The system validates your configuration:

- **RSI Thresholds:** Must be in order (Extreme < Oversold < Near)
- **Stop Losses:** Must be in order (Min < Tight < Default)
- **Risk-Reward:** Must be positive
- **Percentages:** Must be within reasonable ranges

Invalid configurations will show error messages.

## Saving and Loading

- **Auto-Save:** Changes saved automatically on "Save"
- **Reset:** Reset to defaults anytime
- **Presets:** Load presets to start fresh
- **Persistence:** Settings persist across sessions

## API Access

Configuration can also be managed via API:

- `GET /api/v1/user/trading-config` - Get current config
- `PUT /api/v1/user/trading-config` - Update config
- `POST /api/v1/user/trading-config/reset` - Reset to defaults

See [API Documentation](API.md) for details.
