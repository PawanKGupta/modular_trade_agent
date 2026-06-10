"""Unit tests for shared 9:05 pre-market adjustment helpers."""

from math import floor

import pytest

from modules.kotak_neo_auto_trader.utils.premarket_adjustment import (
    compute_premarket_qty,
    needs_premarket_market_finalize,
)


def test_compute_premarket_qty_floors_capital():
    assert compute_premarket_qty(200_000, 101.0) == floor(200_000 / 101.0)


def test_compute_premarket_qty_rejects_invalid_price():
    with pytest.raises(ValueError):
        compute_premarket_qty(200_000, 0)


def test_limit_always_finalizes_even_when_qty_unchanged():
    assert needs_premarket_market_finalize(is_limit=True, new_qty=2000, original_qty=2000)


def test_market_skips_when_qty_unchanged():
    assert not needs_premarket_market_finalize(
        is_limit=False, new_qty=2000, original_qty=2000
    )


def test_market_finalizes_when_qty_changes():
    assert needs_premarket_market_finalize(is_limit=False, new_qty=1904, original_qty=2000)
