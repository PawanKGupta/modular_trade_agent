"""
Filter ChartInk / screener symbols to single-stock equities.

Bonds, ETFs, and index products often appear on reversal screens but lack usable
OHLCV on yfinance and produce ``no_data`` rows in batch analysis.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

logger = logging.getLogger(__name__)

# Suffixes typical of ETF / index products on NSE screener exports.
_EXCLUDED_SUFFIXES = ("BEES",)

# Substrings that indicate non-equity instruments (case-insensitive check).
_EXCLUDED_CONTAINS = (
    "ETF",
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "BHARATBOND",
)

# Prefixes for dated / series bond symbols (e.g. BHARATBOND-APR31).
_EXCLUDED_PREFIXES = ("BHARATBOND",)


def is_equity_screener_symbol(symbol: str) -> bool:
    """
    Return True if ``symbol`` should be analyzed as an NSE equity.

    Args:
        symbol: Raw screener token (no ``.NS`` suffix required).

    Returns:
        False for bonds, ETFs, indices, and empty tokens.
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        return False
    if sym.endswith(_EXCLUDED_SUFFIXES):
        return False
    if sym.startswith(_EXCLUDED_PREFIXES):
        return False
    if any(part in sym for part in _EXCLUDED_CONTAINS):
        return False
    return True


def filter_equity_screener_symbols(symbols: Iterable[str]) -> list[str]:
    """
    Keep only equity screener symbols, preserving order.

    Skipped symbols are logged at INFO (same as ChartInkScraper).
    """
    out: list[str] = []
    for raw in symbols:
        sym = (raw or "").strip().upper()
        if not sym:
            continue
        if is_equity_screener_symbol(sym):
            out.append(sym)
        else:
            logger.info("Skipping non-equity symbol from screener: %s", sym)
    return out


def parse_and_filter_screener_csv(stocks_csv: str) -> list[str]:
    """Parse comma-separated screener output and return equity symbols only."""
    if not stocks_csv or not stocks_csv.strip():
        return []
    return filter_equity_screener_symbols(stocks_csv.split(","))
