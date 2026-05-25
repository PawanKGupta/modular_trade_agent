"""Tests for LivePriceCache subscription symbol normalization."""

from modules.kotak_neo_auto_trader.utils.symbol_utils import normalize_subscription_symbol


def test_normalize_subscription_symbol_adds_eq_suffix():
    assert normalize_subscription_symbol("dmart") == "DMART-EQ"


def test_normalize_subscription_symbol_preserves_segment():
    assert normalize_subscription_symbol("SALSTEEL-BE") == "SALSTEEL-BE"
    assert normalize_subscription_symbol("DMART-EQ") == "DMART-EQ"


def test_normalize_subscription_symbol_empty():
    assert normalize_subscription_symbol("") == ""
    assert normalize_subscription_symbol("  ") == ""
