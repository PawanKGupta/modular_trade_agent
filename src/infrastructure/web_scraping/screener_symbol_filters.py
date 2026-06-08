"""
Filter ChartInk / screener symbols to single-stock equities.

Bonds, ETFs, and index products often appear on reversal screens but lack usable
OHLCV on yfinance and produce ``no_data`` rows in batch analysis.

Unified tradability filter (name heuristics + scrip ``pISIN`` / EQ-first) runs
before batch analysis via ``filter_tradable_screener_symbols``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from src.infrastructure.brokers.tradable_equity_resolver import (
    DeniedEquity,
    load_cached_scrip_master,
    resolve_tradable_equity,
)

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
    "SILVER",
    "CPSE",
)

# Prefixes for dated / series bond symbols (e.g. BHARATBOND-APR31).
_EXCLUDED_PREFIXES = ("BHARATBOND",)

# Known commodity / thematic ETFs (extend when new tickers appear on screens).
_EXCLUDED_EXACT = frozenset(
    {
        "SILVERAG",
        "AXISILVER",
        "MOSILVER",
        "ESILVER",
        "GOLDBEES",
        "SILVERBEES",
        "GOLDETF",
        "SILVERETF",
        "SETFGOLD",
        "SETFSILVER",
        "CNXPSE",
    }
)


def is_equity_screener_symbol(symbol: str) -> bool:
    """
    Return True if ``symbol`` passes fast name-based screener heuristics.

    Args:
        symbol: Raw screener token (no ``.NS`` suffix required).

    Returns:
        False for bonds, ETFs, indices, and empty tokens.
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        return False
    if sym in _EXCLUDED_EXACT:
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
    Keep only symbols passing name heuristics, preserving order.

    Skipped symbols are logged at INFO.
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


def filter_tradable_screener_symbols(
    symbols: Iterable[str],
    *,
    scrip_master=None,
    exchange: str = "NSE",
) -> list[str]:
    """
    Unified pre-analysis filter: name heuristics then scrip tradability resolver.

    When scrip cache is unavailable, returns name-filtered symbols only and logs
    an error (degraded mode — resolver cannot validate ISIN / EQ).
    """
    name_filtered = filter_equity_screener_symbols(symbols)
    if not name_filtered:
        return []

    master = scrip_master if scrip_master is not None else load_cached_scrip_master(exchange=exchange)
    if master is None:
        logger.error(
            "Scrip master cache unavailable; tradability resolver skipped. "
            "Only name heuristics applied (%d symbols).",
            len(name_filtered),
        )
        return name_filtered

    tradable: list[str] = []
    for sym in name_filtered:
        result = resolve_tradable_equity(sym, master, exchange=exchange)
        if isinstance(result, DeniedEquity):
            logger.info(
                "Skipping non-tradable screener symbol: %s (reason=%s)",
                sym,
                result.reason,
            )
            continue
        tradable.append(sym)
    return tradable


def parse_and_filter_screener_csv(stocks_csv: str) -> list[str]:
    """Parse comma-separated screener output; name heuristics only (legacy)."""
    if not stocks_csv or not stocks_csv.strip():
        return []
    return filter_equity_screener_symbols(stocks_csv.split(","))


def parse_and_filter_tradable_screener_csv(
    stocks_csv: str,
    *,
    scrip_master=None,
    exchange: str = "NSE",
) -> list[str]:
    """Parse comma-separated screener output; unified tradability filter."""
    if not stocks_csv or not stocks_csv.strip():
        return []
    return filter_tradable_screener_symbols(
        stocks_csv.split(","),
        scrip_master=scrip_master,
        exchange=exchange,
    )
