"""Shared Kotak unit-test fixtures (tradable scrip master for resolver contract)."""

from __future__ import annotations

from src.infrastructure.brokers.tradable_equity_resolver import build_scrip_master_from_instruments

# Generic INE company-equity ISIN for unit tests (resolver requires INE…, not INF…).
DEFAULT_TEST_ISIN = "INE002A01018"


def kotak_test_scrip_master(*symbols: str, isin: str = DEFAULT_TEST_ISIN):
    """
    Build a real ``KotakNeoScripMaster`` with ``-EQ`` rows and ``pISIN`` for tests.

    Args:
        symbols: Bare bases (``RELIANCE``) or trading symbols (``RELIANCE-EQ``).
        isin: Company equity ISIN prefix ``INE…``.
    """
    instruments = []
    for sym in symbols:
        trd = sym.upper() if sym.upper().endswith("-EQ") else f"{sym.upper()}-EQ"
        instruments.append({"pTrdSymbol": trd, "pISIN": isin, "pSymbol": "1"})
    return build_scrip_master_from_instruments(instruments)


def assign_tradable_scrip_master(engine, *symbols: str, isin: str = DEFAULT_TEST_ISIN) -> None:
    """Attach tradability-compatible scrip master to an ``AutoTradeEngine`` test instance."""
    engine.scrip_master = kotak_test_scrip_master(*symbols, isin=isin)
