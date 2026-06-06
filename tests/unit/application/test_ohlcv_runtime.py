"""Tests for OHLCV read-only trading context."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from src.application.services.ohlcv_runtime import (
    is_ohlcv_cache_read_only,
    ohlcv_cache_read_only,
    run_with_ohlcv_cache_read_only,
)


def test_read_only_context_flag():
    assert is_ohlcv_cache_read_only() is False
    with ohlcv_cache_read_only():
        assert is_ohlcv_cache_read_only() is True
    assert is_ohlcv_cache_read_only() is False


def test_run_with_read_only_helper():
    def _inner():
        return is_ohlcv_cache_read_only()

    assert run_with_ohlcv_cache_read_only(_inner) is True


def test_fetch_ohlcv_yf_no_yahoo_when_read_only():
    from core.data_fetcher import fetch_ohlcv_yf

    with ohlcv_cache_read_only():
        with patch("config.settings.OHLCV_CACHE_ENABLED", False):
            with patch("core.data_fetcher.fetch_ohlcv_yf_raw") as mock_raw:
                result = fetch_ohlcv_yf("RELIANCE.NS", days=30)
                assert result is None
                mock_raw.assert_not_called()


def test_gap_fill_blocked_in_read_only_context():
    from src.application.services.ohlcv_cache_service import OhlcvCacheService

    db = MagicMock()
    svc = OhlcvCacheService(db)
    with ohlcv_cache_read_only():
        assert (
            svc.gap_fill(
                "RELIANCE.NS",
                pd.Timestamp("2026-01-01").date(),
                pd.Timestamp("2026-06-01").date(),
            )
            == 0
        )
