"""Tests for unified sell target (EMA9) calculation."""

from unittest.mock import MagicMock, patch

import pytest

from modules.kotak_neo_auto_trader.services.sell_target_service import (
    compute_sell_target,
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
        assert round_sell_price(100.1, exchange="NSE", symbol="FOO-EQ", scrip_master=scrip) == 100.25


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
