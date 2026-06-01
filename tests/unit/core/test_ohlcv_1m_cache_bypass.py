"""1m OHLCV must not use Postgres price_cache (in-process + Yahoo raw only)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from core import data_fetcher

MINUTE_INTERVAL = "1m"


@pytest.fixture(autouse=True)
def clear_inprocess_ohlcv_cache():
    with data_fetcher._ohlcv_cache_lock:
        data_fetcher._shared_ohlcv_cache.clear()
    yield
    with data_fetcher._ohlcv_cache_lock:
        data_fetcher._shared_ohlcv_cache.clear()


class TestOhlcv1mCacheBypass:
    def test_fetch_ohlcv_yf_1m_uses_inprocess_cache_not_db(self):
        sample = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-05-25 09:15:00"]),
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            }
        )
        with (
            patch(
                "src.infrastructure.db.session.SessionLocal",
            ) as mock_session_local,
            patch.object(
                data_fetcher, "get_cached_ohlcv", return_value=sample
            ) as mock_get_cached,
        ):
            out = data_fetcher.fetch_ohlcv_yf("DMART.NS", days=1, interval=MINUTE_INTERVAL)

        assert out is sample
        mock_get_cached.assert_called_once()
        mock_session_local.assert_not_called()

    def test_get_cached_ohlcv_1m_miss_calls_raw_not_db_backed_fetch(self):
        sample = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-05-25 09:16:00"]),
                "open": [200.0],
                "high": [201.0],
                "low": [199.0],
                "close": [200.5],
                "volume": [500],
            }
        )
        with (
            patch.object(data_fetcher, "fetch_ohlcv_yf_raw", return_value=sample) as mock_raw,
            patch.object(data_fetcher, "fetch_ohlcv_yf") as mock_wrapped,
        ):
            out = data_fetcher.get_cached_ohlcv(
                "DMART.NS", days=1, interval=MINUTE_INTERVAL, add_current_day=True
            )

        assert out is not None
        assert len(out) == 1
        mock_raw.assert_called_once()
        mock_wrapped.assert_not_called()
