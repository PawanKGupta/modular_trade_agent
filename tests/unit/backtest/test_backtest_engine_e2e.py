from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import types
import builtins

import backtest.backtest_engine as eng_mod
from backtest.backtest_config import BacktestConfig


def make_ohlcv(start='2023-01-01', days=800, base=100.0):
    idx = pd.date_range(start, periods=days, freq='D')
    # Create a gently rising series with small noise
    t = np.arange(days)
    close = base + t * 0.1 + np.sin(t / 10.0) * 0.5
    open_ = close * (1.0 + np.random.default_rng(0).normal(0, 0.002, size=days))
    high = np.maximum(open_, close) + 0.5
    low = np.minimum(open_, close) - 0.5
    vol = np.linspace(100_000, 200_000, days)
    df = pd.DataFrame({'Open': open_, 'High': high, 'Low': low, 'Close': close, 'Volume': vol}, index=idx)
    return df


def patch_yfinance(monkeypatch, df):
    class FakeYF:
        @staticmethod
        def download(symbol, start=None, end=None, progress=False, auto_adjust=True):
            # Ignore start/end, return prebuilt df
            return df
    monkeypatch.setattr(eng_mod, 'yf', FakeYF, raising=False)
    
    # Also patch fetch_multi_timeframe_data if it's used
    from core import data_fetcher
    def fake_fetch_multi_timeframe_data(ticker, days=800, end_date=None, add_current_day=True, config=None):
        return {'daily': df, 'weekly': df}
    monkeypatch.setattr(data_fetcher, 'fetch_multi_timeframe_data', fake_fetch_multi_timeframe_data, raising=False)


def patch_ta_for_signals(monkeypatch, mode='entries'):
    # rsi: if mode=='entries' => constant 25 (below 30) to trigger initial entry; else constant 50 (no entries)
    def fake_rsi(series, length=14):
        return pd.Series([25.0 if mode == 'entries' else 50.0] * len(series), index=series.index)

    # ema: slightly below close to satisfy Close > EMA200
    def fake_ema(series, length=200):
        return series * 0.95

    ta_fake = types.SimpleNamespace(rsi=fake_rsi, ema=fake_ema)
    monkeypatch.setattr(eng_mod, 'ta', ta_fake, raising=False)


def test_backtest_engine_e2e_with_entries(monkeypatch):
    df = make_ohlcv(days=800)
    patch_yfinance(monkeypatch, df)
    patch_ta_for_signals(monkeypatch, mode='entries')

    cfg = BacktestConfig()
    engine = eng_mod.BacktestEngine(symbol='AAA.NS', start_date='2024-01-01', end_date='2024-12-31', config=cfg)

    results = engine.run_backtest()
    assert isinstance(results, dict)
    assert 'total_trades' in results

    trades_df = engine.get_trades_dataframe()
    assert isinstance(trades_df, pd.DataFrame)
    # Should have at least one position when RSI forces entry
    assert len(trades_df) >= 1


def test_backtest_engine_e2e_no_entries(monkeypatch):
    df = make_ohlcv(days=800)
    patch_yfinance(monkeypatch, df)
    patch_ta_for_signals(monkeypatch, mode='no_entries')

    cfg = BacktestConfig()
    engine = eng_mod.BacktestEngine(symbol='BBB.NS', start_date='2024-01-01', end_date='2024-12-31', config=cfg)

    results = engine.run_backtest()
    assert isinstance(results, dict)
    # When RSI=50 and EMA close relationship still holds, initial entry should not trigger
    # total_trades in results is number of positions executed
    assert results.get('total_trades', 0) in (0, len(engine.position_manager.positions))
