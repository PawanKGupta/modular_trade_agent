"""Unit tests for screener symbol equity filters."""

from src.infrastructure.brokers.tradable_equity_resolver import build_scrip_master_from_instruments
from src.infrastructure.web_scraping.screener_symbol_filters import (
    filter_equity_screener_symbols,
    filter_tradable_screener_symbols,
    is_equity_screener_symbol,
    parse_and_filter_screener_csv,
)


def test_is_equity_screener_symbol_rejects_bharat_bond():
    assert not is_equity_screener_symbol("BHARATBOND-APR31")
    assert not is_equity_screener_symbol("bharatbond-apr30")


def test_is_equity_screener_symbol_accepts_equity():
    assert is_equity_screener_symbol("POWERGRID")
    assert is_equity_screener_symbol("KSB")


def test_parse_and_filter_screener_csv():
    raw = "BHARATBOND-APR31, POWERGRID, NIFTYBEES, KSB"
    assert parse_and_filter_screener_csv(raw) == ["POWERGRID", "KSB"]


def test_filter_equity_screener_symbols_preserves_order():
    assert filter_equity_screener_symbols(["KSB", "BHARATBOND-APR31", "AETHER"]) == [
        "KSB",
        "AETHER",
    ]


def test_is_equity_screener_symbol_rejects_silver_and_cpse():
    assert not is_equity_screener_symbol("SILVERAG")
    assert not is_equity_screener_symbol("AXISILVER")
    assert not is_equity_screener_symbol("CNXPSE")


def test_filter_tradable_screener_symbols_uses_resolver():
    sm = build_scrip_master_from_instruments(
        [
            {"pTrdSymbol": "GALLANTT-EQ", "pISIN": "INE297H01019"},
            {"pTrdSymbol": "GALLANTT-BL", "pISIN": "INE297H01019"},
            {"pTrdSymbol": "SILVERAG-EQ", "pISIN": "INF769K01KG6"},
            {"pTrdSymbol": "SALSTEEL-BE", "pISIN": "INE999A01099"},
        ]
    )
    raw = ["GALLANTT", "SILVERAG", "SALSTEEL", "NIFTYBEES"]
    assert filter_tradable_screener_symbols(raw, scrip_master=sm) == ["GALLANTT"]
