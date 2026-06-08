"""
Resolve NSE screener symbols to tradable company equities (-EQ, INE ISIN).

Used before analysis (primary gate) and at order placement (defense in depth).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster

logger = logging.getLogger(__name__)

T2T_SUFFIXES = ("-BE", "-BL", "-BZ")


class TradabilityDenyReason(StrEnum):
    """Why a symbol is not a tradable company equity."""

    MF_ETF_UNIT = "mf_etf_unit"
    T2T_ONLY = "t2t_only"
    NO_EQ_LISTING = "no_eq_listing"
    MISSING_ISIN = "missing_isin"
    UNKNOWN_ISIN = "unknown_isin"


@dataclass(frozen=True)
class ResolvedEquity:
    """Tradable NSE company equity listing."""

    symbol: str
    isin: str
    base: str


@dataclass(frozen=True)
class DeniedEquity:
    """Symbol rejected for mean-reversion equity trading."""

    base: str
    reason: TradabilityDenyReason
    detail: str = ""


def normalize_base_symbol(symbol: str) -> str:
    """Strip exchange suffix and segment suffix to bare NSE base."""
    sym = (symbol or "").strip().upper()
    sym = sym.replace(".NS", "").replace(".BO", "")
    if "-" in sym:
        sym = sym.split("-", 1)[0]
    return sym


def is_company_equity_isin(isin: str | None) -> bool:
    return (isin or "").strip().upper().startswith("INE")


def is_mf_or_etf_isin(isin: str | None) -> bool:
    return (isin or "").strip().upper().startswith("INF")


def _isin_from_instrument_entry(instrument_entry: dict | None) -> str | None:
    if not instrument_entry:
        return None
    raw = instrument_entry.get("instrument") or {}
    isin = raw.get("pISIN") or raw.get("isin")
    return (isin or "").strip() or None


def resolve_tradable_equity(
    symbol: str,
    scrip_master: KotakNeoScripMaster,
    *,
    exchange: str = "NSE",
) -> ResolvedEquity | DeniedEquity:
    """
    Resolve ``symbol`` to a tradable ``-EQ`` company equity using EQ-first scrip lookup.

    Never uses bare-base first-wins map order for the allow/deny decision.
    """
    base = normalize_base_symbol(symbol)
    if not base:
        return DeniedEquity(base="", reason=TradabilityDenyReason.NO_EQ_LISTING, detail="empty symbol")

    eq_key = f"{base}-EQ"
    eq_entry = scrip_master.get_instrument(eq_key, exchange=exchange)
    if eq_entry and (eq_entry.get("symbol") or "").upper().endswith("-EQ"):
        isin = _isin_from_instrument_entry(eq_entry)
        if is_mf_or_etf_isin(isin):
            return DeniedEquity(
                base=base,
                reason=TradabilityDenyReason.MF_ETF_UNIT,
                detail=isin or "",
            )
        if is_company_equity_isin(isin):
            return ResolvedEquity(symbol=eq_entry["symbol"].upper(), isin=isin, base=base)
        if not isin:
            return DeniedEquity(base=base, reason=TradabilityDenyReason.MISSING_ISIN)
        return DeniedEquity(
            base=base,
            reason=TradabilityDenyReason.UNKNOWN_ISIN,
            detail=isin,
        )

    for suffix in ("BE", "BL", "BZ"):
        t2t_key = f"{base}-{suffix}"
        t2t_entry = scrip_master.get_instrument(t2t_key, exchange=exchange)
        if t2t_entry and (t2t_entry.get("symbol") or "").upper().endswith(f"-{suffix}"):
            return DeniedEquity(base=base, reason=TradabilityDenyReason.T2T_ONLY)

    return DeniedEquity(base=base, reason=TradabilityDenyReason.NO_EQ_LISTING)


def denial_message(denied: DeniedEquity) -> str:
    """Human-readable error for order placement."""
    if denied.reason == TradabilityDenyReason.MF_ETF_UNIT:
        return (
            f"Symbol {denied.base} is a mutual fund / ETF unit (ISIN {denied.detail or 'INF…'}) "
            f"which is not supported. Only company equity (-EQ, INE ISIN) is allowed."
        )
    if denied.reason == TradabilityDenyReason.T2T_ONLY:
        return (
            f"Symbol {denied.base} is only available in a T2T segment (-BE/-BL/-BZ) "
            f"which is not supported. Only -EQ segment stocks are allowed for trading."
        )
    if denied.reason == TradabilityDenyReason.NO_EQ_LISTING:
        return (
            f"Symbol {denied.base} has no -EQ listing in scrip master. "
            f"Please verify the symbol is correct."
        )
    if denied.reason == TradabilityDenyReason.MISSING_ISIN:
        return f"Symbol {denied.base}-EQ has no pISIN in scrip master; tradability unknown."
    return f"Symbol {denied.base} is not tradable as company equity ({denied.reason})."


def load_cached_scrip_master(
    *,
    cache_dir: str = "data/scrip_master",
    exchange: str = "NSE",
) -> KotakNeoScripMaster | None:
    """Load the latest cached scrip master without broker authentication."""
    try:
        from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
    except ImportError:
        logger.error("KotakNeoScripMaster unavailable; cannot load scrip cache")
        return None

    scrip_master = KotakNeoScripMaster(cache_dir=cache_dir, exchanges=[exchange])
    instruments = scrip_master._load_from_cache(exchange)
    if not instruments:
        return None
    scrip_master.scrip_data[exchange] = instruments
    scrip_master._build_symbol_map(exchange, instruments)
    return scrip_master


def build_scrip_master_from_instruments(
    instruments: list[dict],
    *,
    exchange: str = "NSE",
) -> KotakNeoScripMaster:
    """Build an in-memory scrip master (tests and fixtures)."""
    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster

    scrip_master = KotakNeoScripMaster(cache_dir="data/scrip_master", exchanges=[exchange])
    scrip_master.scrip_data[exchange] = instruments
    scrip_master._build_symbol_map(exchange, instruments)
    return scrip_master


def is_tradable_equity(
    symbol: str,
    scrip_master: KotakNeoScripMaster | None,
    *,
    exchange: str = "NSE",
) -> bool:
    """Return True when ``symbol`` resolves to tradable company equity."""
    if scrip_master is None:
        return True
    return isinstance(resolve_tradable_equity(symbol, scrip_master, exchange=exchange), ResolvedEquity)
