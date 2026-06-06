"""Tests for symbol price-map lookup helpers (system holdings / LTP resolution)."""

from modules.kotak_neo_auto_trader.utils.symbol_utils import (
    lookup_price_from_map,
    symbol_lookup_keys,
)


def test_symbol_lookup_keys_includes_be_suffix_and_base():
    keys = symbol_lookup_keys("SALSTEEL-BE")
    assert "SALSTEEL-BE" in keys
    assert "SALSTEEL" in keys
    assert keys[0] == "SALSTEEL-BE"


def test_lookup_price_from_map_resolves_eq_position_from_base_key():
    price_map = {"POWERGRID": 301.2}
    assert lookup_price_from_map(price_map, "POWERGRID-EQ") == 301.2


def test_lookup_price_from_map_resolves_be_suffix():
    price_map = {"SALSTEEL-BE": 88.5, "SALSTEEL": 88.5}
    assert lookup_price_from_map(price_map, "SALSTEEL") == 88.5


def test_lookup_price_from_map_ignores_zero_and_missing():
    assert lookup_price_from_map({"IDEA-EQ": 0.0}, "IDEA-EQ") is None
    assert lookup_price_from_map({}, "TCS-EQ") is None
