"""Regression: LTP source logging and priority unchanged."""

from unittest.mock import Mock, patch

import pandas as pd

from modules.kotak_neo_auto_trader.services.price_service import PriceService
from tests.ist_clock import ist_now_naive


@patch("modules.kotak_neo_auto_trader.services.price_service.get_ltp_from_manager")
def test_kotak_live_ltp_logs_source_at_info(mock_get_ltp, caplog):
    import logging

    caplog.set_level(logging.INFO)

    mock_get_ltp.return_value = 4097.2
    service = PriceService(live_price_manager=Mock(), enable_caching=False)
    result = service.get_realtime_price("DMART", "DMART.NS", "DMART-EQ")

    assert result == 4097.2
    assert any("source=kotak_live" in r.message for r in caplog.records)


@patch("core.data_fetcher.get_cached_ohlcv")
def test_yahoo_fallback_logs_source_at_info(mock_fetch, caplog):
    import logging

    caplog.set_level(logging.INFO)

    mock_fetch.return_value = pd.DataFrame(
        {"close": [4117.9], "date": [ist_now_naive()]}
    )
    service = PriceService(live_price_manager=None, enable_caching=False)
    result = service.get_realtime_price("DMART", "DMART.NS", "DMART-EQ")

    assert result == 4117.9
    assert any("source=yahoo_1m" in r.message for r in caplog.records)


@patch("modules.kotak_neo_auto_trader.services.price_service.get_ltp_from_manager")
def test_live_manager_still_preferred_over_broker_map(mock_get_ltp):
    mock_get_ltp.return_value = 2550.0
    service = PriceService(live_price_manager=Mock(), enable_caching=False)
    result = service.get_realtime_price(
        "RELIANCE",
        "RELIANCE.NS",
        "RELIANCE-EQ",
        broker_price_map={"RELIANCE-EQ": 2400.0},
    )
    assert result == 2550.0
    mock_get_ltp.assert_called_once()
