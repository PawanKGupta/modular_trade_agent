"""Map NSE ``TckrSymb`` values to/from ``price_cache`` ticker keys (``SYMBOL.NS``)."""

from __future__ import annotations

from modules.kotak_neo_auto_trader.utils.symbol_utils import extract_ticker_base, normalize_symbol


def to_cache_ticker(tckr_symb: str) -> str:
    """
    Convert NSE ticker symbol to cache key used in ``price_cache``.

    Examples:
        DMART -> DMART.NS
        RELIANCE.NS -> RELIANCE.NS
    """
    base = extract_ticker_base(tckr_symb)
    if not base:
        return ""
    return f"{base}.NS"


def base_from_cache_ticker(ticker: str) -> str:
    """Extract NSE ``TckrSymb`` base from a cache ticker (``RELIANCE.NS`` -> ``RELIANCE``)."""
    return extract_ticker_base(normalize_symbol(ticker))


def ensure_cache_ticker(ticker: str) -> str:
    """Normalize any ticker input to ``BASE.NS`` form."""
    base = base_from_cache_ticker(ticker)
    if not base:
        return ""
    return f"{base}.NS"
