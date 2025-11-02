import pandas as pd
import pytest

from src.infrastructure.data_providers.yfinance_provider import YFinanceProvider


def test_multi_timeframe_missing_weekly_raises(monkeypatch):
    import src.infrastructure.data_providers.yfinance_provider as mod

    def fake_legacy_fetch_multi_timeframe(ticker, end_date=None, add_current_day=True):
        return {'daily': pd.DataFrame({'date': [1]}) , 'weekly': pd.DataFrame()}  # empty weekly

    monkeypatch.setattr(mod, 'legacy_fetch_multi_timeframe', fake_legacy_fetch_multi_timeframe)

    provider = YFinanceProvider()
    with pytest.raises(Exception):
        provider.fetch_multi_timeframe_data('AAA.NS')


def test_current_price_none_and_fundamentals_error(monkeypatch):
    class FakeTicker:
        def __init__(self, ticker):
            raise RuntimeError('boom')
    
    import types, sys
    fake_yf = types.SimpleNamespace(Ticker=FakeTicker)
    sys.modules['yfinance'] = fake_yf
    import builtins
    monkeypatch.setitem(builtins.__dict__, 'yfinance', fake_yf)

    provider = YFinanceProvider()
    price = provider.fetch_current_price('AAA.NS')
    assert price is None

    # For fundamentals error, patch Ticker to return info but within try
    class FakeTicker2:
        def __init__(self, ticker):
            self.info = {}
    fake_yf2 = types.SimpleNamespace(Ticker=FakeTicker2)
    sys.modules['yfinance'] = fake_yf2
    monkeypatch.setitem(builtins.__dict__, 'yfinance', fake_yf2)
    fundamentals = provider.fetch_fundamental_data('BBB.NS')
    assert isinstance(fundamentals, dict)
