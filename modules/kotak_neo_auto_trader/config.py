#!/usr/bin/env python3
"""
Configuration for Kotak Neo Auto Trader
"""

from datetime import time
from config.strategy_config import StrategyConfig

# Portfolio constraints
MAX_PORTFOLIO_SIZE = 6
CAPITAL_PER_TRADE = 100000  # fixed capital per entry (₹1 lakh per stock)

# Scheduling
RUN_TIME = time(hour=16, minute=0)  # 16:00 local time
MARKET_DAYS = {0, 1, 2, 3, 4}  # Mon=0 .. Sun=6

# Data/config paths
ANALYSIS_DIR = "analysis_results"
RECOMMENDED_SOURCE = "auto"  # auto|csv|json
RECOMMENDED_CSV_GLOB = "bulk_analysis_final_*.csv"  # inside ANALYSIS_DIR (post-scored)
TRADES_HISTORY_PATH = "data/trades_history.json"

# Indicator params - Sync RSI period with StrategyConfig for consistency
# Keep EMA_SHORT/EMA_LONG separate (auto-trader specific)
_strategy_config = StrategyConfig.default()
RSI_PERIOD = _strategy_config.rsi_period  # Default: 10, synced with main strategy
EMA_SHORT = 9  # Auto-trader specific
EMA_LONG = 200  # Auto-trader specific

# Order defaults
DEFAULT_EXCHANGE = "NSE"
DEFAULT_PRODUCT = "CNC"
DEFAULT_ORDER_TYPE = "MARKET"  # use MARKET for AMO entries, can be LIMIT
DEFAULT_VARIETY = "AMO"  # After Market Orders
DEFAULT_VALIDITY = "DAY"

# Behavior toggles
ALLOW_DUPLICATE_RECOMMENDATIONS_SAME_DAY = False
EXIT_ON_EMA9_OR_RSI50 = True

# CSV filtering from trade_agent --backtest
MIN_COMBINED_SCORE = 25  # only take rows with final_verdict in {buy,strong_buy} and combined_score >= this

# Safety
MIN_QTY = 1
