"""Tests for LivePriceCache LTP lookup key fallbacks."""

from unittest.mock import Mock

from modules.kotak_neo_auto_trader.utils.price_manager_utils import get_ltp_from_manager


def test_get_ltp_from_manager_falls_back_to_eq_suffix():
    manager = Mock()
    manager.get_ltp = Mock(side_effect=lambda sym, ticker=None: 100.0 if sym == "DMART-EQ" else None)

    assert get_ltp_from_manager(manager, "DMART", "DMART.NS") == 100.0


def test_get_ltp_from_manager_falls_back_to_base_when_subscribed_base():
    manager = Mock()
    manager.get_ltp = Mock(side_effect=lambda sym, ticker=None: 200.0 if sym == "DMART" else None)

    assert get_ltp_from_manager(manager, "DMART-EQ", "DMART.NS") == 200.0
