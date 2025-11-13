#!/usr/bin/env python3
"""
Price Manager Utility Functions
Utilities for working with different price manager implementations
"""

import inspect
from typing import Optional, Callable, Any


def get_ltp_from_manager(
    price_manager: Any,
    symbol: str,
    ticker: Optional[str] = None
) -> Optional[float]:
    """
    Get LTP from price manager with automatic signature detection.
    
    Handles both LivePriceCache (single arg) and LivePriceManager (two args) interfaces.
    
    Args:
        price_manager: Price manager instance (LivePriceCache or LivePriceManager)
        symbol: Symbol to lookup (e.g., 'DALBHARAT-EQ' or 'DALBHARAT')
        ticker: Optional ticker (e.g., 'DALBHARAT.NS') for LivePriceManager compatibility
        
    Returns:
        LTP value or None if not available
    """
    if not price_manager or not hasattr(price_manager, 'get_ltp'):
        return None
    
    try:
        # Check method signature to determine argument count
        sig = inspect.signature(price_manager.get_ltp)
        param_count = len(sig.parameters)
        
        if param_count >= 2:
            # LivePriceManager: get_ltp(symbol, ticker)
            return price_manager.get_ltp(symbol, ticker)
        else:
            # LivePriceCache: get_ltp(symbol)
            return price_manager.get_ltp(symbol)
    except Exception:
        # Fallback: try single arg first, then two args
        try:
            return price_manager.get_ltp(symbol)
        except TypeError:
            if ticker:
                return price_manager.get_ltp(symbol, ticker)
            return None


