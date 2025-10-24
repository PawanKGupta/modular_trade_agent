"""
Kotak Neo Auto Trader Module
Modular implementation for portfolio management and trading operations
"""

# Main imports for easy access
from .trader import KotakNeoTrader
from .auth import KotakNeoAuth
from .portfolio import KotakNeoPortfolio
from .orders import KotakNeoOrders
from .auto_trade_engine import AutoTradeEngine
from . import config

# Version info
__version__ = "1.1.0"
__author__ = "Trading Agent"

# Export main classes
__all__ = [
    "KotakNeoTrader",
    "KotakNeoAuth", 
    "KotakNeoPortfolio",
    "KotakNeoOrders",
    "AutoTradeEngine",
    "config",
]
