"""
Configuration Module
Trading and paper trading configuration

This module re-exports all settings from the parent config.py
plus adds paper trading configuration.
"""

import sys
from pathlib import Path

# Import paper trading config
from .paper_trading_config import PaperTradingConfig

# Import all settings from parent config.py to maintain backward compatibility
parent_dir = Path(__file__).parent.parent
config_file = parent_dir / "config.py"

if config_file.exists():
    # Import the parent config.py module
    import importlib.util
    spec = importlib.util.spec_from_file_location("kotak_config", config_file)
    if spec and spec.loader:
        kotak_config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(kotak_config)
        
        # Re-export all config variables
        RSI_PERIOD = getattr(kotak_config, 'RSI_PERIOD', 10)
        TRADES_HISTORY_PATH = getattr(kotak_config, 'TRADES_HISTORY_PATH', 'data/trades_history.json')
        MAX_PORTFOLIO_SIZE = getattr(kotak_config, 'MAX_PORTFOLIO_SIZE', 6)
        CAPITAL_PER_TRADE = getattr(kotak_config, 'CAPITAL_PER_TRADE', 100000)
        MIN_COMBINED_SCORE = getattr(kotak_config, 'MIN_COMBINED_SCORE', 25)
        DEFAULT_EXCHANGE = getattr(kotak_config, 'DEFAULT_EXCHANGE', 'NSE')
        DEFAULT_PRODUCT = getattr(kotak_config, 'DEFAULT_PRODUCT', 'CNC')
        DEFAULT_VARIETY = getattr(kotak_config, 'DEFAULT_VARIETY', 'AMO')
        EMA_SHORT = getattr(kotak_config, 'EMA_SHORT', 9)
        EMA_LONG = getattr(kotak_config, 'EMA_LONG', 200)
        RUN_TIME = getattr(kotak_config, 'RUN_TIME', None)
        MARKET_DAYS = getattr(kotak_config, 'MARKET_DAYS', {0, 1, 2, 3, 4})
        ANALYSIS_DIR = getattr(kotak_config, 'ANALYSIS_DIR', 'analysis_results')
        RECOMMENDED_SOURCE = getattr(kotak_config, 'RECOMMENDED_SOURCE', 'auto')
        RECOMMENDED_CSV_GLOB = getattr(kotak_config, 'RECOMMENDED_CSV_GLOB', 'bulk_analysis_final_*.csv')
        DEFAULT_ORDER_TYPE = getattr(kotak_config, 'DEFAULT_ORDER_TYPE', 'MARKET')
        DEFAULT_VALIDITY = getattr(kotak_config, 'DEFAULT_VALIDITY', 'DAY')
        ALLOW_DUPLICATE_RECOMMENDATIONS_SAME_DAY = getattr(kotak_config, 'ALLOW_DUPLICATE_RECOMMENDATIONS_SAME_DAY', False)
        EXIT_ON_EMA9_OR_RSI50 = getattr(kotak_config, 'EXIT_ON_EMA9_OR_RSI50', True)
        MIN_QTY = getattr(kotak_config, 'MIN_QTY', 1)

__all__ = [
    "PaperTradingConfig",
    # Re-exported from config.py for backward compatibility
    "RSI_PERIOD",
    "TRADES_HISTORY_PATH",
    "MAX_PORTFOLIO_SIZE",
    "CAPITAL_PER_TRADE",
    "MIN_COMBINED_SCORE",
    "DEFAULT_EXCHANGE",
    "DEFAULT_PRODUCT",
    "DEFAULT_VARIETY",
    "EMA_SHORT",
    "EMA_LONG",
    "RUN_TIME",
    "MARKET_DAYS",
    "ANALYSIS_DIR",
    "RECOMMENDED_SOURCE",
    "RECOMMENDED_CSV_GLOB",
    "DEFAULT_ORDER_TYPE",
    "DEFAULT_VALIDITY",
    "ALLOW_DUPLICATE_RECOMMENDATIONS_SAME_DAY",
    "EXIT_ON_EMA9_OR_RSI50",
    "MIN_QTY",
]

