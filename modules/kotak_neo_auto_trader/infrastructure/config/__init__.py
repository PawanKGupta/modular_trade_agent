"""
Configuration Management
Broker and trading configuration

Note: Uses existing config.py from legacy code for now
Future: Can be refactored into broker_config.py and trading_config.py
"""

# For now, we'll use the existing config.py from the parent module
import sys
from pathlib import Path
parent_path = Path(__file__).parent.parent
sys.path.insert(0, str(parent_path))

try:
    import config
except ImportError:
    from ... import config

# Re-export commonly used config values
MAX_PORTFOLIO_SIZE = getattr(config, 'MAX_PORTFOLIO_SIZE', 6)
CAPITAL_PER_TRADE = getattr(config, 'CAPITAL_PER_TRADE', 100000)
MIN_COMBINED_SCORE = getattr(config, 'MIN_COMBINED_SCORE', 25)
DEFAULT_EXCHANGE = getattr(config, 'DEFAULT_EXCHANGE', 'NSE')
DEFAULT_PRODUCT = getattr(config, 'DEFAULT_PRODUCT', 'CNC')
DEFAULT_VARIETY = getattr(config, 'DEFAULT_VARIETY', 'AMO')

__all__ = [
    "config",
    "MAX_PORTFOLIO_SIZE",
    "CAPITAL_PER_TRADE",
    "MIN_COMBINED_SCORE",
    "DEFAULT_EXCHANGE",
    "DEFAULT_PRODUCT",
    "DEFAULT_VARIETY",
]
