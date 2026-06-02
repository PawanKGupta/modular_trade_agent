"""Tests for NSE UDiFF bhavcopy fetcher."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.infrastructure.data_providers.nse_bhavcopy_fetcher import (
    NseBhavcopyFetcher,
    bhavcopy_url,
    find_equity_bar,
    parse_equity_bars,
)
from src.infrastructure.data_providers.nse_symbol import to_cache_ticker

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "nse_bhavcopy_sample.csv"


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.read_csv(FIXTURE)


def test_bhavcopy_url_format():
    url = bhavcopy_url(date(2026, 6, 2))
    assert "20260602" in url
    assert url.endswith("_F_0000.csv.zip")


def test_parse_equity_bars_filters_eq_and_parses_ohlcv(sample_df):
    bars = parse_equity_bars(sample_df)
    assert len(bars) == 2
    dmart = next(b for b in bars if b.tckr_symb == "DMART")
    assert dmart.close == 4057.0
    assert dmart.trade_date == date(2026, 6, 2)
    assert dmart.volume == 467977


def test_find_equity_bar(sample_df):
    bar = find_equity_bar(sample_df, "DMART")
    assert bar is not None
    assert bar.high == 4068.9


def test_to_cache_ticker():
    assert to_cache_ticker("DMART") == "DMART.NS"
    assert to_cache_ticker("RELIANCE.NS") == "RELIANCE.NS"


def test_download_uses_disk_cache(tmp_path, sample_df, monkeypatch):
    cache_dir = tmp_path / "bhav"
    cache_dir.mkdir()
    cached = cache_dir / "bhav_20260602.csv"
    sample_df.to_csv(cached, index=False)

    fetcher = NseBhavcopyFetcher(cache_dir=cache_dir, request_delay_s=0)

    def fail_http(_url, **_kw):
        raise AssertionError("should not HTTP when cache hit")

    monkeypatch.setattr(fetcher, "_http_get", fail_http)
    df = fetcher.download_bhavcopy(date(2026, 6, 2))
    assert df is not None
    assert len(df) == 2
