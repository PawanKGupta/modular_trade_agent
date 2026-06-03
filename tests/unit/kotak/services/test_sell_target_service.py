"""Tests for unified sell target (EMA9) calculation."""

from unittest.mock import MagicMock, patch

import pytest

from modules.kotak_neo_auto_trader.services.sell_target_service import (
    cap_sell_price_to_upper_circuit,
    compute_sell_target,
    fetch_circuit_limits_for_symbol,
    is_price_on_tick_grid,
    nse_fallback_tick_size_by_price,
    parse_circuit_limits_from_quote_payload,
    parse_circuit_limits_from_rejection,
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

    def test_defers_when_ema9_above_upper_circuit_axiscades_case(self):
        """Regression: 2 Jun AXISCADES EMA9 1860.40 vs upper 1859.20 — defer, do not cap."""
        limits = {"upper": 1859.20, "lower": 1682.20}
        prepared = prepare_broker_sell_limit_price(
            1860.40,
            exchange="NSE",
            symbol="AXISCADES-EQ",
            circuit_limits=limits,
        )
        assert prepared.action == "defer_circuit"
        assert prepared.price is None
        assert any("circuit_defer" in adj for adj in prepared.adjustments)

    def test_places_when_ema9_within_upper_circuit(self):
        limits = {"upper": 1900.0, "lower": 1600.0}
        prepared = prepare_broker_sell_limit_price(
            1847.40,
            exchange="NSE",
            symbol="AXISCADES-EQ",
            circuit_limits=limits,
        )
        assert prepared.action == "place"
        assert prepared.price is not None
        assert prepared.price <= limits["upper"]

    def test_parse_circuit_limits_from_rejection_message(self):
        msg = (
            "RMS:Rule: Check circuit limit including square off order exceeds : "
            "Circuit breach, Order Price :1860.40,  Low Price Range:1682.20 "
            "High Price Range:1859.20"
        )
        limits = parse_circuit_limits_from_rejection(msg)
        assert limits == {"upper": 1859.20, "lower": 1682.20}

    def test_parse_circuit_limits_from_quote_payload(self):
        payload = [
            {
                "upper_circuit_limit": "1859.20",
                "lower_circuit_limit": "1682.20",
                "trading_symbol": "AXISCADES-EQ",
            }
        ]
        limits = parse_circuit_limits_from_quote_payload(payload)
        assert limits == {"upper": 1859.20, "lower": 1682.20}

    def test_fetch_circuit_limits_from_market_data(self):
        scrip = MagicMock()
        scrip.get_instrument.return_value = {"token": "12345"}
        scrip.EXCHANGE_SEGMENT_MAP = {"NSE": "nse_cm"}
        market = MagicMock()
        market.get_quote.return_value = [
            {"upper_circuit_limit": 1859.2, "lower_circuit_limit": 1682.2}
        ]
        limits = fetch_circuit_limits_for_symbol(
            market_data=market,
            scrip_master=scrip,
            symbol="AXISCADES-EQ",
            exchange="NSE",
        )
        assert limits == {"upper": 1859.2, "lower": 1682.2}
        market.get_quote.assert_called()

    def test_cap_sell_price_to_upper_circuit(self):
        capped = cap_sell_price_to_upper_circuit(
            1860.40, 1859.20, exchange="NSE", symbol="AXISCADES-EQ"
        )
        assert capped <= 1859.20


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
