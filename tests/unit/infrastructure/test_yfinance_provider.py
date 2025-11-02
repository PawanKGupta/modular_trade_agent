import pandas as pd
import types
import builtins
import pytest

from src.infrastructure.data_providers.yfinance_provider import YFinanceProvider
from src.domain.interfaces.data_provider import DataFetchError


def make_df(rows=5):
    import numpy as np
    dates = pd.date_range("2024-01-01", periods=rows, freq="D")
    base = np.arange(1, rows + 1)
    return pd.DataFrame({
        'date': dates,
        'open': base.astype(float),
        'high': base.astype(float) + 1,
        'low':  base.astype(float) - 1,
        'close': base.astype(float) + 0.5,
        'volume': (base * 100).astype(int),
    })


def test_fetch_daily_and_weekly_data(monkeypatch):
    import src.infrastructure.data_providers.yfinance_provider as mod

    def fake_fetch_ohlcv_yf(ticker, days, interval, end_date=None, add_current_day=True):
        df = make_df(10)
        return df

    monkeypatch.setattr(mod, 'fetch_ohlcv_yf', fake_fetch_ohlcv_yf)

    provider = YFinanceProvider()

    daily = provider.fetch_daily_data('AAA.NS', days=30)
    assert not daily.empty and list(daily.columns) >= ['date','open','high','low','close','volume']

    weekly = provider.fetch_weekly_data('AAA.NS', weeks=4)
    assert not weekly.empty


def test_fetch_multi_timeframe_data(monkeypatch):
    import src.infrastructure.data_providers.yfinance_provider as mod

    def fake_legacy_fetch_multi_timeframe(ticker, end_date=None, add_current_day=True):
        return {'daily': make_df(20), 'weekly': make_df(20)}

    monkeypatch.setattr(mod, 'legacy_fetch_multi_timeframe', fake_legacy_fetch_multi_timeframe)

    provider = YFinanceProvider()
    daily, weekly = provider.fetch_multi_timeframe_data('BBB.NS')
    assert not daily.empty and not weekly.empty


def test_fetch_raises_on_empty(monkeypatch):
    import src.infrastructure.data_providers.yfinance_provider as mod

    def empty_fetch(*args, **kwargs):
        import pandas as pd
        return pd.DataFrame()

    monkeypatch.setattr(mod, 'fetch_ohlcv_yf', empty_fetch)

    provider = YFinanceProvider()
    with pytest.raises(DataFetchError):
        provider.fetch_daily_data('CCC.NS')


def test_current_price_and_fundamentals(monkeypatch):
    class FakeTicker:
        def __init__(self, ticker):
            self.info = {
                'currentPrice': 123.45,
                'trailingPE': 20.5,
                'priceToBook': 3.2,
                'marketCap': 1000,
                'dividendYield': 0.01,
                'beta': 1.1,
                'fiftyTwoWeekHigh': 150,
                'fiftyTwoWeekLow': 90,
            }
    
    fake_yf = types.SimpleNamespace(Ticker=FakeTicker)
    monkeypatch.setitem(builtins.__dict__, 'yfinance', fake_yf)

    # Patch module import to return our fake_yf
    import sys
    sys.modules['yfinance'] = fake_yf

    provider = YFinanceProvider()
    price = provider.fetch_current_price('DDD.NS')
    assert price == 123.45

    fundamentals = provider.fetch_fundamental_data('EEE.NS')
    assert fundamentals['pe_ratio'] == 20.5
