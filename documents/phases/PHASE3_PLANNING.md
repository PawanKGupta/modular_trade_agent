# Phase 3: Exit Strategy & Risk Management

**Project:** Kotak Neo Auto Trader  
**Phase:** 3  
**Status:** Planning  
**Target Completion:** TBD  

---

## Overview

Phase 3 focuses on implementing intelligent exit strategies, dynamic position sizing, and comprehensive risk management to protect capital and maximize returns.

**Core Objectives:**
1. Automated exit execution based on technical indicators
2. Dynamic position sizing based on volatility and risk
3. Portfolio-level risk management
4. Performance tracking and analytics
5. Advanced monitoring and alerts

---

## Phase 3 Features Breakdown

### Module 1: Exit Strategy Manager 🎯

**Purpose:** Automatically exit positions based on predefined technical conditions

#### Exit Conditions:

1. **EMA9 Crossunder Exit**
   - Price crosses below EMA9 (daily timeframe)
   - Indicates trend reversal
   - Exit entire position

2. **RSI50 Exit**
   - RSI crosses above 50 (from below)
   - Indicates momentum exhaustion
   - Exit entire position

3. **Stop-Loss Exit**
   - Fixed percentage stop-loss (e.g., -5%)
   - Trailing stop-loss option
   - Exit entire position immediately

4. **Profit Target Exit**
   - Fixed percentage target (e.g., +10%)
   - Multiple target levels (partial exits)
   - Exit portion or entire position

5. **Time-Based Exit**
   - Maximum holding period (e.g., 30 days)
   - Exit if no profit after X days
   - Force exit stale positions

#### Implementation Details:

```python
class ExitStrategyManager:
    """
    Manages exit strategy execution for tracked positions.
    
    Features:
    - Multiple exit condition checks
    - Priority-based exit execution
    - Partial vs full position exits
    - Telegram notifications on exits
    - Exit reason tracking
    """
    
    def __init__(
        self,
        portfolio_client,
        orders_client,
        tracking_scope,
        telegram_notifier
    ):
        self.portfolio = portfolio_client
        self.orders = orders_client
        self.tracking = tracking_scope
        self.telegram = telegram_notifier
        
        # Exit parameters (configurable)
        self.enable_ema9_exit = True
        self.enable_rsi50_exit = True
        self.enable_stop_loss = True
        self.enable_profit_target = True
        self.enable_time_based = True
        
        self.stop_loss_pct = -5.0  # -5%
        self.profit_target_pct = 10.0  # +10%
        self.max_holding_days = 30
    
    def evaluate_exits_for_all_positions(self) -> Dict[str, Any]:
        """Check all active positions for exit conditions."""
        pass
    
    def check_exit_conditions(self, symbol: str) -> Optional[ExitSignal]:
        """Check if symbol meets any exit condition."""
        pass
    
    def execute_exit(self, symbol: str, exit_reason: str) -> bool:
        """Execute exit order for symbol."""
        pass
```

**Files to Create:**
- `modules/kotak_neo_auto_trader/exit_strategy.py`
- `modules/kotak_neo_auto_trader/exit_conditions.py`

**Estimated Effort:** 3-4 days

---

### Module 2: Position Sizing Calculator 📊

**Purpose:** Calculate optimal position size based on risk parameters

#### Sizing Strategies:

1. **Fixed Capital Method** (Current)
   - Fixed ₹1 lakh per position
   - Simple but not risk-adjusted

2. **Fixed Risk Percentage Method**
   - Risk X% of capital per trade (e.g., 2%)
   - Position size = (Account * Risk%) / (Entry - StopLoss)
   - More conservative

3. **Volatility-Based Sizing (ATR)**
   - Adjust size based on ATR (Average True Range)
   - Smaller positions for volatile stocks
   - Larger positions for stable stocks

4. **Kelly Criterion**
   - Optimal fraction based on win rate and payoff
   - Requires historical performance data
   - More aggressive when edge is clear

5. **Portfolio Heat Management**
   - Limit total capital at risk across all positions
   - Adjust individual sizes based on portfolio exposure
   - Prevent overconcentration

#### Implementation:

```python
class PositionSizer:
    """
    Calculates optimal position size based on risk parameters.
    
    Supports multiple sizing strategies:
    - Fixed capital
    - Fixed risk percentage
    - Volatility-based (ATR)
    - Kelly Criterion
    - Portfolio heat management
    """
    
    def __init__(
        self,
        portfolio_client,
        tracking_scope,
        default_strategy: str = "fixed_risk"
    ):
        self.portfolio = portfolio_client
        self.tracking = tracking_scope
        self.strategy = default_strategy
        
        # Risk parameters
        self.risk_per_trade_pct = 2.0  # 2% per trade
        self.max_portfolio_heat = 10.0  # 10% total
        self.max_position_size_pct = 20.0  # 20% of capital
    
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: float,
        strategy: Optional[str] = None
    ) -> int:
        """Calculate optimal quantity for position."""
        pass
    
    def get_available_capital(self) -> float:
        """Get available capital for new positions."""
        pass
    
    def get_portfolio_heat(self) -> float:
        """Calculate current portfolio heat (total risk)."""
        pass
```

**Files to Create:**
- `modules/kotak_neo_auto_trader/position_sizer.py`
- `modules/kotak_neo_auto_trader/risk_calculator.py`

**Estimated Effort:** 2-3 days

---

### Module 3: Risk Manager 🛡️

**Purpose:** Portfolio-level risk management and circuit breakers

#### Risk Controls:

1. **Daily Loss Limit**
   - Stop trading if daily loss exceeds X%
   - Reset at market open next day
   - Telegram alert when triggered

2. **Maximum Drawdown Limit**
   - Stop trading if drawdown from peak exceeds X%
   - Requires manual intervention to resume
   - Critical risk protection

3. **Position Correlation Analysis**
   - Limit correlated positions
   - Prevent sector overconcentration
   - Diversification enforcement

4. **Margin Usage Monitor**
   - Track margin utilization percentage
   - Alert when exceeding threshold
   - Prevent margin calls

5. **Circuit Breaker Events**
   - Market crash detection (NIFTY -3% in day)
   - Exit all positions or stop trading
   - Emergency risk protection

#### Implementation:

```python
class RiskManager:
    """
    Portfolio-level risk management and circuit breakers.
    
    Features:
    - Daily loss limits
    - Maximum drawdown protection
    - Position correlation analysis
    - Margin monitoring
    - Circuit breaker events
    """
    
    def __init__(
        self,
        portfolio_client,
        tracking_scope,
        telegram_notifier
    ):
        self.portfolio = portfolio_client
        self.tracking = tracking_scope
        self.telegram = telegram_notifier
        
        # Risk limits
        self.daily_loss_limit_pct = -3.0  # -3% per day
        self.max_drawdown_pct = -10.0  # -10% from peak
        self.max_margin_usage_pct = 70.0  # 70% margin
        self.max_correlated_positions = 2  # Max 2 from same sector
        
        # State tracking
        self.peak_equity = 0.0
        self.today_start_equity = 0.0
        self.circuit_breaker_triggered = False
    
    def check_risk_limits(self) -> Dict[str, Any]:
        """Check all risk limits and return status."""
        pass
    
    def is_daily_loss_exceeded(self) -> bool:
        """Check if daily loss limit exceeded."""
        pass
    
    def is_max_drawdown_exceeded(self) -> bool:
        """Check if max drawdown exceeded."""
        pass
    
    def get_position_correlation(self, symbol1: str, symbol2: str) -> float:
        """Calculate correlation between two positions."""
        pass
    
    def trigger_circuit_breaker(self, reason: str) -> None:
        """Trigger emergency circuit breaker."""
        pass
```

**Files to Create:**
- `modules/kotak_neo_auto_trader/risk_manager.py`
- `modules/kotak_neo_auto_trader/circuit_breaker.py`

**Estimated Effort:** 3-4 days

---

### Module 4: Performance Analytics 📈

**Purpose:** Track and analyze trading performance

#### Metrics to Track:

1. **Win Rate Metrics**
   - Total trades
   - Winning trades
   - Losing trades
   - Win rate percentage

2. **Return Metrics**
   - Average gain per winning trade
   - Average loss per losing trade
   - Profit factor (gross profit / gross loss)
   - Expectancy per trade

3. **Risk-Adjusted Returns**
   - Sharpe ratio
   - Sortino ratio
   - Maximum drawdown
   - Recovery factor

4. **Trade Distribution**
   - Trade duration histogram
   - P&L distribution
   - Win/loss streaks
   - Best/worst trades

5. **Time Series Analysis**
   - Equity curve
   - Cumulative returns
   - Rolling returns
   - Monthly/weekly performance

#### Implementation:

```python
class PerformanceAnalytics:
    """
    Comprehensive performance tracking and analytics.
    
    Features:
    - Win rate calculation
    - Return metrics
    - Risk-adjusted metrics
    - Equity curve generation
    - Report generation
    """
    
    def __init__(self, trades_history_path: str):
        self.history_path = trades_history_path
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate all performance metrics."""
        pass
    
    def get_win_rate(self) -> float:
        """Calculate win rate percentage."""
        pass
    
    def get_sharpe_ratio(self, risk_free_rate: float = 0.05) -> float:
        """Calculate Sharpe ratio."""
        pass
    
    def generate_equity_curve(self) -> List[Dict[str, Any]]:
        """Generate equity curve data."""
        pass
    
    def generate_performance_report(self) -> str:
        """Generate detailed performance report."""
        pass
    
    def send_weekly_report(self) -> None:
        """Send weekly performance report via Telegram."""
        pass
```

**Files to Create:**
- `modules/kotak_neo_auto_trader/analytics.py`
- `modules/kotak_neo_auto_trader/metrics.py`
- `modules/kotak_neo_auto_trader/reporting.py`

**Estimated Effort:** 4-5 days

---

### Module 5: Advanced Monitoring & Alerts 🚨

**Purpose:** Real-time monitoring and proactive alerts

#### Alert Types:

1. **Price Alerts**
   - Target price reached
   - Support/resistance breach
   - Significant price movement (>3% in 5 min)

2. **Technical Indicator Alerts**
   - RSI extremes (overbought/oversold)
   - EMA crossovers
   - Volume spikes
   - Momentum divergence

3. **Risk Alerts**
   - Stop-loss triggered
   - Daily loss limit approaching
   - Margin usage high
   - Correlation spike

4. **Market Condition Alerts**
   - NIFTY circuit breaker
   - Market volatility spike (VIX)
   - Sector rotation detected
   - News sentiment change

5. **System Health Alerts**
   - API connection issues
   - Order placement failures
   - Data feed delays
   - Module errors

#### Implementation:

```python
class AlertManager:
    """
    Advanced monitoring and alert system.
    
    Features:
    - Real-time price monitoring
    - Technical indicator alerts
    - Risk threshold alerts
    - Market condition monitoring
    - System health checks
    """
    
    def __init__(
        self,
        portfolio_client,
        tracking_scope,
        telegram_notifier
    ):
        self.portfolio = portfolio_client
        self.tracking = tracking_scope
        self.telegram = telegram_notifier
        
        # Alert configuration
        self.enable_price_alerts = True
        self.enable_technical_alerts = True
        self.enable_risk_alerts = True
        self.enable_market_alerts = True
        self.enable_system_alerts = True
        
        # Thresholds
        self.price_movement_threshold = 3.0  # 3%
        self.volume_spike_threshold = 2.0  # 2x average
    
    def monitor_positions(self) -> None:
        """Continuously monitor all positions."""
        pass
    
    def check_price_alerts(self, symbol: str) -> List[Alert]:
        """Check for price-based alerts."""
        pass
    
    def check_technical_alerts(self, symbol: str) -> List[Alert]:
        """Check for technical indicator alerts."""
        pass
    
    def check_system_health(self) -> List[Alert]:
        """Check system health and connectivity."""
        pass
    
    def send_alert(self, alert: Alert) -> None:
        """Send alert via Telegram."""
        pass
```

**Files to Create:**
- `modules/kotak_neo_auto_trader/alert_manager.py`
- `modules/kotak_neo_auto_trader/market_monitor.py`
- `modules/kotak_neo_auto_trader/system_health.py`

**Estimated Effort:** 3-4 days

---

## Phase 3 Implementation Plan

### Stage 1: Exit Strategy (Week 1-2)
**Priority:** High  
**Dependencies:** None  

**Tasks:**
1. Create `exit_strategy.py` module
2. Implement EMA9 and RSI50 exit conditions
3. Implement stop-loss logic
4. Add exit execution methods
5. Integrate with tracking scope
6. Add Telegram notifications
7. Write unit tests
8. Test with real positions

**Deliverables:**
- Exit strategy module working
- Exits executing automatically
- Notifications on exits
- Test coverage >80%

---

### Stage 2: Position Sizing (Week 2-3)
**Priority:** High  
**Dependencies:** Risk Manager (basic)  

**Tasks:**
1. Create `position_sizer.py` module
2. Implement fixed risk percentage method
3. Implement volatility-based sizing
4. Add portfolio heat calculation
5. Integrate with order placement
6. Add configuration options
7. Write unit tests
8. Test with different strategies

**Deliverables:**
- Position sizer module working
- Multiple sizing strategies available
- Portfolio heat tracking
- Test coverage >80%

---

### Stage 3: Risk Management (Week 3-4)
**Priority:** Critical  
**Dependencies:** Position Sizer  

**Tasks:**
1. Create `risk_manager.py` module
2. Implement daily loss limit
3. Implement max drawdown protection
4. Add circuit breaker logic
5. Implement correlation analysis
6. Add margin monitoring
7. Integrate with trading engine
8. Write unit tests
9. Test circuit breaker scenarios

**Deliverables:**
- Risk manager module working
- All risk limits enforced
- Circuit breakers functional
- Emergency stop working
- Test coverage >80%

---

### Stage 4: Analytics (Week 4-5)
**Priority:** Medium  
**Dependencies:** Completed trades data  

**Tasks:**
1. Create `analytics.py` module
2. Implement win rate calculation
3. Implement return metrics
4. Calculate Sharpe/Sortino ratios
5. Generate equity curve
6. Create performance reports
7. Add weekly report automation
8. Write unit tests
9. Test with historical data

**Deliverables:**
- Analytics module working
- All metrics calculated
- Reports generated
- Weekly automation working
- Test coverage >70%

---

### Stage 5: Advanced Monitoring (Week 5-6)
**Priority:** Medium  
**Dependencies:** Risk Manager, Analytics  

**Tasks:**
1. Create `alert_manager.py` module
2. Implement price monitoring
3. Add technical indicator alerts
4. Implement risk alerts
5. Add market condition monitoring
6. Create system health checks
7. Integrate with Telegram
8. Write unit tests
9. Test alert scenarios

**Deliverables:**
- Alert manager working
- All alert types functional
- Real-time monitoring active
- System health tracked
- Test coverage >70%

---

## Configuration Updates

### New Config Parameters:

```python
# config.py additions

# Exit Strategy
EXIT_EMA9_ENABLED = True
EXIT_RSI50_ENABLED = True
EXIT_STOP_LOSS_ENABLED = True
EXIT_PROFIT_TARGET_ENABLED = True
EXIT_TIME_BASED_ENABLED = False

STOP_LOSS_PCT = -5.0  # -5%
PROFIT_TARGET_PCT = 10.0  # +10%
TRAILING_STOP_ENABLED = False
TRAILING_STOP_PCT = 3.0  # 3%
MAX_HOLDING_DAYS = 30

# Position Sizing
POSITION_SIZING_STRATEGY = "fixed_risk"  # fixed_capital|fixed_risk|volatility|kelly
RISK_PER_TRADE_PCT = 2.0  # 2% of capital
MAX_POSITION_SIZE_PCT = 20.0  # 20% of capital
MAX_PORTFOLIO_HEAT = 10.0  # 10% total risk

# Risk Management
DAILY_LOSS_LIMIT_PCT = -3.0  # -3% per day
MAX_DRAWDOWN_PCT = -10.0  # -10% from peak
MAX_MARGIN_USAGE_PCT = 70.0  # 70% margin
MAX_CORRELATED_POSITIONS = 2  # Max 2 from same sector
CIRCUIT_BREAKER_NIFTY_DROP = -3.0  # Trigger on -3% NIFTY

# Analytics
ENABLE_ANALYTICS = True
WEEKLY_REPORT_DAY = "Sunday"
MONTHLY_REPORT_DAY = 1  # 1st of month

# Alerts
ENABLE_PRICE_ALERTS = True
ENABLE_TECHNICAL_ALERTS = True
ENABLE_RISK_ALERTS = True
ENABLE_MARKET_ALERTS = True
PRICE_MOVEMENT_THRESHOLD = 3.0  # 3%
VOLUME_SPIKE_THRESHOLD = 2.0  # 2x average
```

---

## Integration with Existing System

### Phase 1 & 2 Integration Points:

1. **Tracking Scope** → Exit Strategy
   - Exit manager reads active positions
   - Updates tracking on exit execution

2. **Order Tracker** → Exit Strategy
   - Exit orders tracked like entry orders
   - Status verification for exit orders

3. **Reconciliation** → Analytics
   - Trade history feeds analytics
   - Performance calculated from reconciled data

4. **Telegram Notifier** → All Modules
   - Exit notifications
   - Risk alerts
   - Performance reports
   - System alerts

5. **EOD Cleanup** → Analytics
   - Daily statistics include performance
   - Weekly report generation
   - Monthly summary

---

## Testing Strategy

### Unit Tests:
- Each module: >70% coverage
- Critical paths: 100% coverage
- Edge cases covered
- Mock broker responses

### Integration Tests:
1. Exit Strategy + Tracking Scope
2. Position Sizer + Risk Manager
3. Risk Manager + Circuit Breaker
4. Analytics + EOD Cleanup
5. Alert Manager + Telegram

### End-to-End Tests:
1. Full trade lifecycle (entry → monitoring → exit)
2. Risk limit scenarios
3. Circuit breaker activation
4. Performance report generation
5. Alert triggering

### Dry-Run Testing:
1. Test with small positions (₹500-1000)
2. Monitor for 1 week
3. Verify exits execute correctly
4. Check risk limits enforced
5. Review analytics accuracy

---

## Success Criteria

### Phase 3 Complete When:

1. ✅ Exit strategy executes automatically
2. ✅ Position sizing adjusts dynamically
3. ✅ Risk limits enforced portfolio-wide
4. ✅ Circuit breakers trigger correctly
5. ✅ Analytics calculate accurately
6. ✅ Weekly reports generated
7. ✅ Alerts sent for all conditions
8. ✅ All tests passing (>70% coverage)
9. ✅ Dry-run successful (1 week)
10. ✅ Documentation complete

---

## Risk Assessment

### Potential Risks:

1. **Exit Timing Issues**
   - Risk: Exits execute at unfavorable prices
   - Mitigation: Use limit orders with tolerance
   - Mitigation: Add slippage buffer

2. **Circuit Breaker False Positives**
   - Risk: Trading stopped unnecessarily
   - Mitigation: Multiple confirmation checks
   - Mitigation: Manual override option

3. **Position Sizing Errors**
   - Risk: Over-leveraging or under-utilizing
   - Mitigation: Hard caps on size
   - Mitigation: Portfolio heat limits

4. **Performance Calculation Bugs**
   - Risk: Inaccurate metrics mislead decisions
   - Mitigation: Thorough testing with known data
   - Mitigation: Cross-verify with broker reports

5. **Alert Fatigue**
   - Risk: Too many alerts ignored
   - Mitigation: Prioritize critical alerts
   - Mitigation: Configurable alert levels

---

## Timeline & Milestones

### Week 1-2: Exit Strategy
- Day 1-3: Module structure + EMA9/RSI50 exits
- Day 4-6: Stop-loss + profit targets
- Day 7-10: Integration + testing
- **Milestone:** Exits executing automatically

### Week 2-3: Position Sizing
- Day 11-13: Fixed risk sizing
- Day 14-16: Volatility-based sizing
- Day 17-20: Portfolio heat + testing
- **Milestone:** Dynamic sizing working

### Week 3-4: Risk Management
- Day 21-23: Daily loss + drawdown limits
- Day 24-26: Circuit breakers + correlation
- Day 27-30: Integration + testing
- **Milestone:** Risk controls active

### Week 4-5: Analytics
- Day 31-33: Metrics calculation
- Day 34-36: Equity curve + reports
- Day 37-40: Weekly automation + testing
- **Milestone:** Reports generating

### Week 5-6: Advanced Monitoring
- Day 41-43: Alert framework + price alerts
- Day 44-46: Technical + risk alerts
- Day 47-50: System health + testing
- **Milestone:** Monitoring active

### Week 7: Integration & Testing
- Day 51-54: End-to-end integration
- Day 55-56: Comprehensive testing
- Day 57: Dry-run preparation
- **Milestone:** Phase 3 ready for dry-run

---

## Documentation Requirements

### New Documents:
1. `EXIT_STRATEGY_GUIDE.md` - Exit conditions and configuration
2. `POSITION_SIZING_GUIDE.md` - Sizing strategies explained
3. `RISK_MANAGEMENT_GUIDE.md` - Risk limits and controls
4. `ANALYTICS_GUIDE.md` - Metrics and interpretation
5. `ALERTS_CONFIGURATION.md` - Alert setup and customization

### Updated Documents:
1. `README.md` - Add Phase 3 overview
2. `TESTING_GUIDE.md` - Phase 3 test procedures
3. `DEPLOYMENT_GUIDE.md` - Phase 3 deployment steps

---

## Post-Phase 3 Enhancements

### Future Considerations:

1. **Machine Learning Integration**
   - Predict exit timing
   - Optimize position sizing
   - Anomaly detection

2. **Multi-Timeframe Analysis**
   - Coordinate exits across timeframes
   - Trend confirmation
   - Better entry/exit timing

3. **Options Strategies**
   - Hedging with options
   - Income generation (covered calls)
   - Protective puts

4. **Backtesting Framework**
   - Test strategies on historical data
   - Optimize parameters
   - Walk-forward analysis

5. **Portfolio Rebalancing**
   - Automatic rebalancing
   - Sector rotation
   - Momentum ranking

---

## Questions for Consideration

Before starting implementation:

1. **Exit Strategy Priority:**
   - Which exit condition is most important? (EMA9, RSI50, stop-loss?)
   - Should we implement partial exits?
   - Trailing stop-loss vs fixed?

2. **Position Sizing Strategy:**
   - Start with fixed risk or volatility-based?
   - What risk % per trade? (1%, 2%, 3%?)
   - Kelly Criterion too aggressive?

3. **Risk Limits:**
   - Daily loss limit? (-3%, -5%?)
   - Max drawdown tolerance? (-10%, -15%?)
   - Circuit breaker on what NIFTY drop? (-3%, -5%?)

4. **Analytics Frequency:**
   - Daily, weekly, or monthly reports?
   - Real-time metrics needed?
   - Historical comparison depth?

5. **Alert Configuration:**
   - Which alerts are most critical?
   - Alert frequency (real-time vs periodic)?
   - Separate Telegram channel for alerts?

---

**Status:** Planning Complete  
**Next Step:** Prioritize features and begin Stage 1 (Exit Strategy)  
**Estimated Total Duration:** 6-7 weeks  
**Complexity:** High  
**Risk Level:** Medium  

Ready to start implementation? 🚀
