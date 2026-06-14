"""Unit tests for tradable equity resolver (EQ-first, pISIN INF/INE)."""

import pytest

from src.infrastructure.brokers.tradable_equity_resolver import (
    DeniedEquity,
    ResolvedEquity,
    TradabilityDenyReason,
    build_scrip_master_from_instruments,
    denial_message,
    is_company_equity_isin,
    is_mf_or_etf_isin,
    resolve_tradable_equity,
)


def _inst(symbol: str, isin: str) -> dict:
    return {"pTrdSymbol": symbol, "pISIN": isin}


@pytest.mark.parametrize(
    ("isin", "company", "etf"),
    [
        ("INE297H01019", True, False),
        ("INF769K01KG6", False, True),
        (None, False, False),
    ],
)
def test_isin_prefix_helpers(isin, company, etf):
    assert is_company_equity_isin(isin) is company
    assert is_mf_or_etf_isin(isin) is etf


def test_resolve_gallantt_eq_when_bl_also_listed():
    """GALLANTT-EQ must win over GALLANTT-BL (regression for false T2T)."""
    sm = build_scrip_master_from_instruments(
        [
            _inst("GALLANTT-BL", "INE297H01019"),
            _inst("GALLANTT-EQ", "INE297H01019"),
        ]
    )
    result = resolve_tradable_equity("GALLANTT", sm)
    assert isinstance(result, ResolvedEquity)
    assert result.symbol == "GALLANTT-EQ"


def test_resolve_silverag_etf_denied():
    sm = build_scrip_master_from_instruments([_inst("SILVERAG-EQ", "INF769K01KG6")])
    result = resolve_tradable_equity("SILVERAG", sm)
    assert isinstance(result, DeniedEquity)
    assert result.reason == TradabilityDenyReason.MF_ETF_UNIT


def test_resolve_salsteel_t2t_only():
    sm = build_scrip_master_from_instruments([_inst("SALSTEEL-BE", "INE123A01012")])
    result = resolve_tradable_equity("SALSTEEL", sm)
    assert isinstance(result, DeniedEquity)
    assert result.reason == TradabilityDenyReason.T2T_ONLY


def test_resolve_unknown_no_eq():
    sm = build_scrip_master_from_instruments([_inst("RELIANCE-EQ", "INE002A01018")])
    result = resolve_tradable_equity("NOTALIST", sm)
    assert isinstance(result, DeniedEquity)
    assert result.reason == TradabilityDenyReason.NO_EQ_LISTING


def test_denial_message_mf_etf():
    denied = DeniedEquity(base="SILVERAG", reason=TradabilityDenyReason.MF_ETF_UNIT, detail="INF1")
    assert "ETF" in denial_message(denied)
