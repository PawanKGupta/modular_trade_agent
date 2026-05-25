#!/usr/bin/env python3
"""
Price Manager Utility Functions
Utilities for working with different price manager implementations
"""

import inspect
from typing import Any

from modules.kotak_neo_auto_trader.utils.symbol_utils import (
    extract_base_symbol,
    normalize_subscription_symbol,
)


def get_ltp_from_manager(
    price_manager: Any, symbol: str, ticker: str | None = None
) -> float | None:
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
    if not price_manager or not hasattr(price_manager, "get_ltp"):
        return None

    def _fetch(sym: str) -> float | None:
        if not sym:
            return None
        try:
            sig = inspect.signature(price_manager.get_ltp)
            param_count = len(sig.parameters)
            if param_count >= 2:
                return price_manager.get_ltp(sym, ticker)
            return price_manager.get_ltp(sym)
        except TypeError:
            try:
                return price_manager.get_ltp(sym)
            except TypeError:
                if ticker:
                    return price_manager.get_ltp(sym, ticker)
                return None
        except Exception:
            return None

    try:
        ltp = _fetch(symbol)
        if ltp is not None and ltp > 0:
            return ltp
        # Align lookup with subscription keys (DMART-EQ vs DMART)
        if symbol and "-" in symbol:
            alt = extract_base_symbol(symbol)
            ltp = _fetch(alt)
            if ltp is not None and ltp > 0:
                return ltp
        if symbol and "-" not in symbol:
            ltp = _fetch(normalize_subscription_symbol(symbol))
            if ltp is not None and ltp > 0:
                return ltp
        return None
    except Exception:
        return None
