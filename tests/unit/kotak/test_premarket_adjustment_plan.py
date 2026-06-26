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
    assert not needs_premarket_market_finalize(is_limit=False, new_qty=2000, original_qty=2000)


def test_market_finalizes_when_qty_changes():
    assert needs_premarket_market_finalize(is_limit=False, new_qty=1904, original_qty=2000)


def test_compute_premarket_qty_applies_cap(monkeypatch):
    from modules.kotak_neo_auto_trader import config

    monkeypatch.setattr(config, "MAX_ORDER_VALUE", 500000)
    # execution_capital = 600_000, price = 100.0. Normal qty = 6000. Capped qty = 5000.
    assert compute_premarket_qty(600_000, 100.0, min_qty=1) == 5000


def test_compute_premarket_qty_capped_below_min(monkeypatch):
    from modules.kotak_neo_auto_trader import config

    monkeypatch.setattr(config, "MAX_ORDER_VALUE", 500000)
    # execution_capital = 600_000, price = 60_000.0, min_qty = 10.
    # Normal qty = 10. Max allowed = 8. Since 8 < 10, it should return 0.
    assert compute_premarket_qty(600_000, 60_000.0, min_qty=10) == 0
