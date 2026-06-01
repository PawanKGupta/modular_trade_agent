"""Unit tests for screener symbol equity filters."""

from src.infrastructure.web_scraping.screener_symbol_filters import (
    filter_equity_screener_symbols,
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
