import builtins
import sys
import types
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

import src.infrastructure.data_providers.yfinance_provider as mod
from src.domain.interfaces.data_provider import DataFetchError
from src.infrastructure.data_providers.yfinance_provider import YFinanceProvider


def _install_fake_yf(monkeypatch, ticker_cls, now):
    """Install a fake yfinance module and pin ist_now() to a fixed time."""
    fake_yf = types.SimpleNamespace(Ticker=ticker_cls)
    monkeypatch.setattr(mod, "yf", fake_yf)
    monkeypatch.setitem(builtins.__dict__, "yfinance", fake_yf)
    sys.modules["yfinance"] = fake_yf
    monkeypatch.setattr(mod, "ist_now", lambda: now)


def make_df(rows=5):
    dates = pd.date_range("2024-01-01", periods=rows, freq="D")
    base = np.arange(1, rows + 1)
    return pd.DataFrame(
        {
            "date": dates,
            "open": base.astype(float),
            "high": base.astype(float) + 1,
            "low": base.astype(float) - 1,
            "close": base.astype(float) + 0.5,
            "volume": (base * 100).astype(int),
        }
    )


def test_fetch_daily_and_weekly_data(monkeypatch):
    def fake_fetch_ohlcv_yf(ticker, days, interval, end_date=None, add_current_day=True):
        df = make_df(10)
        return df

    monkeypatch.setattr(mod, "fetch_ohlcv_yf", fake_fetch_ohlcv_yf)

    provider = YFinanceProvider()

    daily = provider.fetch_daily_data("AAA.NS", days=30)
    assert not daily.empty and list(daily.columns) >= [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    weekly = provider.fetch_weekly_data("AAA.NS", weeks=4)
    assert not weekly.empty


def test_fetch_multi_timeframe_data(monkeypatch):
    def fake_legacy_fetch_multi_timeframe(ticker, end_date=None, add_current_day=True):
        return {"daily": make_df(20), "weekly": make_df(20)}

    monkeypatch.setattr(mod, "legacy_fetch_multi_timeframe", fake_legacy_fetch_multi_timeframe)

    provider = YFinanceProvider()
    daily, weekly = provider.fetch_multi_timeframe_data("BBB.NS")
    assert not daily.empty and not weekly.empty


def test_fetch_raises_on_empty(monkeypatch):
    def empty_fetch(*args, **kwargs):
        return pd.DataFrame()

    monkeypatch.setattr(mod, "fetch_ohlcv_yf", empty_fetch)

    provider = YFinanceProvider()
    with pytest.raises(DataFetchError):
        provider.fetch_daily_data("CCC.NS")


def test_current_price_and_fundamentals(monkeypatch):
    class FakeTicker:
        def __init__(self, ticker):
            self.info = {
                "currentPrice": 123.45,
                "trailingPE": 20.5,
                "priceToBook": 3.2,
                "marketCap": 1000,
                "dividendYield": 0.01,
                "beta": 1.1,
                "fiftyTwoWeekHigh": 150,
                "fiftyTwoWeekLow": 90,
            }

    fake_yf = types.SimpleNamespace(Ticker=FakeTicker)
    monkeypatch.setitem(builtins.__dict__, "yfinance", fake_yf)
    monkeypatch.setattr(mod, "yf", fake_yf)

    # Patch module import to return our fake_yf
    sys.modules["yfinance"] = fake_yf

    provider = YFinanceProvider()
    price = provider.fetch_current_price("DDD.NS")
    assert price == 123.45

    fundamentals = provider.fetch_fundamental_data("EEE.NS")
    assert fundamentals["pe_ratio"] == 20.5


# ---------------------------------------------------------------------------
# AMO fill price: at_open behaviour (market-open window) regression tests
# ---------------------------------------------------------------------------

# 9:15:30 AM IST -> inside the 09:15-09:20 market-open window
MARKET_OPEN_TIME = datetime(2026, 6, 11, 9, 15, 30)
# 12:00 PM IST -> outside the market-open window
MID_SESSION_TIME = datetime(2026, 6, 11, 12, 0, 0)


def _today_1m_history():
    """1m bars whose latest bar is dated today (2026-06-11)."""
    idx = pd.to_datetime([datetime(2026, 6, 11, 9, 15), datetime(2026, 6, 11, 9, 16)])
    return pd.DataFrame({"Open": [148.0, 149.0], "Close": [148.5, 149.5]}, index=idx)


def _stale_1m_history():
    """1m bars whose latest bar is dated yesterday (2026-06-10) - the original bug."""
    idx = pd.to_datetime([datetime(2026, 6, 10, 9, 15), datetime(2026, 6, 10, 15, 29)])
    return pd.DataFrame({"Open": [140.0, 145.0], "Close": [141.0, 146.0]}, index=idx)


def test_at_open_uses_first_open_from_today_1m_history(monkeypatch):
    """In the open window, at_open should return today's first 1m open price."""

    class FakeTicker:
        def __init__(self, ticker):
            self.info = {"regularMarketOpen": 150.0, "currentPrice": 152.0}

        def history(self, *args, **kwargs):
            return _today_1m_history()

    _install_fake_yf(monkeypatch, FakeTicker, MARKET_OPEN_TIME)

    provider = YFinanceProvider()
    # open of the first bar, NOT close/current/regularMarketOpen
    assert provider.fetch_current_price("RELIANCE.NS", at_open=True) == 148.0


def test_at_open_stale_history_falls_back_to_regular_market_open(monkeypatch):
    """Regression: if 1m history is yesterday's, the date guard must reject it.

    Must NOT return yesterday's open (140.0) or close (146.0); falls back to
    today's regularMarketOpen from info.
    """

    class FakeTicker:
        def __init__(self, ticker):
            self.info = {"regularMarketOpen": 150.0, "currentPrice": 152.0}

        def history(self, *args, **kwargs):
            return _stale_1m_history()

    _install_fake_yf(monkeypatch, FakeTicker, MARKET_OPEN_TIME)

    provider = YFinanceProvider()
    assert provider.fetch_current_price("RELIANCE.NS", at_open=True) == 150.0


def test_at_open_empty_history_falls_back_to_regular_market_open(monkeypatch):
    """When 1m history is empty, fall back to info regularMarketOpen."""

    class FakeTicker:
        def __init__(self, ticker):
            self.info = {"regularMarketOpen": 150.0, "currentPrice": 152.0}

        def history(self, *args, **kwargs):
            return pd.DataFrame()

    _install_fake_yf(monkeypatch, FakeTicker, MARKET_OPEN_TIME)

    provider = YFinanceProvider()
    assert provider.fetch_current_price("RELIANCE.NS", at_open=True) == 150.0


def test_at_open_falls_back_to_open_field_when_no_regular_market_open(monkeypatch):
    """info 'open' is used when 'regularMarketOpen' is missing."""

    class FakeTicker:
        def __init__(self, ticker):
            self.info = {"open": 149.5, "currentPrice": 152.0}

        def history(self, *args, **kwargs):
            return pd.DataFrame()

    _install_fake_yf(monkeypatch, FakeTicker, MARKET_OPEN_TIME)

    provider = YFinanceProvider()
    assert provider.fetch_current_price("RELIANCE.NS", at_open=True) == 149.5


def test_at_open_outside_window_uses_current_price(monkeypatch):
    """at_open=True but outside the open window -> normal current price."""

    class FakeTicker:
        def __init__(self, ticker):
            self.info = {"regularMarketOpen": 150.0, "currentPrice": 155.5}

        def history(self, *args, **kwargs):  # pragma: no cover - must not be used
            raise AssertionError("history() must not be called outside the open window")

    _install_fake_yf(monkeypatch, FakeTicker, MID_SESSION_TIME)

    provider = YFinanceProvider()
    assert provider.fetch_current_price("RELIANCE.NS", at_open=True) == 155.5


def test_default_at_open_false_uses_current_price_even_in_window(monkeypatch):
    """Without at_open, the open-price path is never taken (no regression for LTP)."""

    class FakeTicker:
        def __init__(self, ticker):
            self.info = {"regularMarketOpen": 150.0, "currentPrice": 152.0}

        def history(self, *args, **kwargs):  # pragma: no cover - must not be used
            raise AssertionError("history() must not be called when at_open is False")

    _install_fake_yf(monkeypatch, FakeTicker, MARKET_OPEN_TIME)

    provider = YFinanceProvider()
    assert provider.fetch_current_price("RELIANCE.NS") == 152.0


def test_at_open_caches_open_price_for_the_day(monkeypatch):
    """The immutable session open is cached, so repeated at_open reads hit yfinance once."""
    calls = {"history": 0}

    class FakeTicker:
        def __init__(self, ticker):
            self.info = {"regularMarketOpen": 150.0, "currentPrice": 152.0}

        def history(self, *args, **kwargs):
            calls["history"] += 1
            return _today_1m_history()

    _install_fake_yf(monkeypatch, FakeTicker, MARKET_OPEN_TIME)

    provider = YFinanceProvider()
    assert provider.fetch_current_price("RELIANCE.NS", at_open=True) == 148.0
    assert provider.fetch_current_price("RELIANCE.NS", at_open=True) == 148.0
    # Second call served from the per-day cache, not a fresh history fetch.
    assert calls["history"] == 1
