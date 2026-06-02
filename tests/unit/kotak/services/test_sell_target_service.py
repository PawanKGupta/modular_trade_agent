"""Tests for unified sell target (EMA9) calculation."""

from unittest.mock import MagicMock, patch

import pytest

from modules.kotak_neo_auto_trader.services.sell_target_service import (
    compute_sell_target,
    is_price_on_tick_grid,
    nse_fallback_tick_size_by_price,
    prepare_broker_sell_limit_price,
    resolve_tick_size,
    round_sell_price,
)


class TestRoundSellPrice:
    def test_nse_rounds_up_to_five_paise(self):
        assert round_sell_price(100.01, exchange="NSE") == 100.05

    def test_nse_high_price_ten_paise_tick(self):
        assert round_sell_price(1000.01, exchange="NSE") == 1000.10

    def test_bse_low_price_one_paisa(self):
        assert round_sell_price(5.001, exchange="BSE") == 5.01

    def test_uses_scrip_master_tick_when_available(self):
        scrip = MagicMock()
        scrip.get_tick_size.return_value = 0.25
        assert (
            round_sell_price(100.1, exchange="NSE", symbol="FOO-EQ", scrip_master=scrip) == 100.25
        )

    def test_nse_5000_band_rounds_high_priced_ema9(self):
        """Regression: LINDEINDIA-style targets must not stay at 7140.9 on a 0.10-only tick."""
        assert round_sell_price(7140.9, exchange="NSE") == 7141.0
        assert round_sell_price(7088.3, exchange="NSE") == 7088.5

    def test_scrip_fine_tick_uses_band_floor_for_high_prices(self):
        scrip = MagicMock()
        scrip.get_tick_size.return_value = 0.10
        tick, source = resolve_tick_size(
            7140.9, exchange="NSE", symbol="LINDEINDIA-EQ", scrip_master=scrip
        )
        assert tick == 0.50
        assert source == "scrip_master+band_floor"
        assert round_sell_price(7140.9, exchange="NSE", symbol="LINDEINDIA-EQ", scrip_master=scrip) == 7141.0

    def test_is_price_on_tick_grid_detects_invalid_high_price_paise(self):
        assert is_price_on_tick_grid(7140.9, 0.10) is True
        assert is_price_on_tick_grid(7140.9, 0.50) is False
        assert is_price_on_tick_grid(7141.0, 0.50) is True


class TestPrepareBrokerSellLimitPrice:
    def test_places_valid_high_price_target(self):
        prepared = prepare_broker_sell_limit_price(7140.9, exchange="NSE", symbol="LINDEINDIA-EQ")
        assert prepared.action == "place"
        assert prepared.price == 7141.0

    def test_rejects_non_positive(self):
        prepared = prepare_broker_sell_limit_price(0.0, exchange="NSE")
        assert prepared.action == "invalid_tick"
        assert prepared.price is None


class TestNseFallbackTickBands:
    def test_bands(self):
        assert nse_fallback_tick_size_by_price(500) == 0.05
        assert nse_fallback_tick_size_by_price(2500) == 0.10
        assert nse_fallback_tick_size_by_price(7140) == 0.50
        assert nse_fallback_tick_size_by_price(25000) == 1.00


class TestComputeSellTarget:
    @patch("modules.kotak_neo_auto_trader.services.sell_target_service.round_sell_price")
    def test_delegates_to_indicator_and_rounds(self, mock_round):
        mock_ind = MagicMock()
        mock_ind.calculate_ema9_realtime.return_value = 2565.4321
        mock_ps = MagicMock()
        mock_round.return_value = 2565.45

        result = compute_sell_target(
            "RELIANCE.NS",
            broker_symbol="RELIANCE-EQ",
            indicator_service=mock_ind,
            price_service=mock_ps,
            round_price=True,
        )

        assert result == 2565.45
        mock_ind.calculate_ema9_realtime.assert_called_once_with(
            ticker="RELIANCE.NS",
            broker_symbol="RELIANCE-EQ",
            current_ltp=None,
        )
        mock_round.assert_called_once()

    def test_returns_none_when_ema_missing(self):
        mock_ind = MagicMock()
        mock_ind.calculate_ema9_realtime.return_value = None
        assert (
            compute_sell_target(
                "RELIANCE.NS",
                indicator_service=mock_ind,
                price_service=MagicMock(),
                round_price=False,
            )
            is None
        )

    def test_skips_rounding_when_disabled(self):
        mock_ind = MagicMock()
        mock_ind.calculate_ema9_realtime.return_value = 2565.4321
        result = compute_sell_target(
            "RELIANCE.NS",
            indicator_service=mock_ind,
            price_service=MagicMock(),
            round_price=False,
        )
        assert result == pytest.approx(2565.4321)


class TestSellTargetPlacementParity:
    """Lock shared rounding between compute_sell_target and SellOrderManager."""

    def test_compute_sell_target_matches_sell_order_manager_rounding(self):
        from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager

        scrip = MagicMock()
        scrip.get_tick_size.return_value = 0.10
        ema9 = 1000.03
        mock_ind = MagicMock()
        mock_ind.calculate_ema9_realtime.return_value = ema9

        via_helper = compute_sell_target(
            "RELIANCE.NS",
            broker_symbol="RELIANCE-EQ",
            indicator_service=mock_ind,
            price_service=MagicMock(),
            scrip_master=scrip,
            exchange="NSE",
            round_price=True,
        )
        mgr = MagicMock()
        mgr.scrip_master = scrip
        via_manager = SellOrderManager.round_to_tick_size(
            mgr, ema9, exchange="NSE", symbol="RELIANCE-EQ"
        )

        assert via_helper == via_manager
        assert via_helper == round_sell_price(
            ema9, exchange="NSE", symbol="RELIANCE-EQ", scrip_master=scrip
        )

    def test_compute_sell_target_forwards_explicit_ltp(self):
        mock_ind = MagicMock()
        mock_ind.calculate_ema9_realtime.return_value = 2500.0
        ltp = 2488.5

        compute_sell_target(
            "RELIANCE.NS",
            broker_symbol="RELIANCE-EQ",
            indicator_service=mock_ind,
            price_service=MagicMock(),
            round_price=False,
            current_ltp=ltp,
        )

        mock_ind.calculate_ema9_realtime.assert_called_once_with(
            ticker="RELIANCE.NS",
            broker_symbol="RELIANCE-EQ",
            current_ltp=ltp,
        )
