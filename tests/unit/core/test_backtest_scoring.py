import pandas as pd
import numpy as np
import types
import builtins
import pytest

import core.backtest_scoring as bts


def test_calculate_backtest_score_components():
    results = {
        'total_return_pct': 25.0,
        'win_rate': 60.0,
        'strategy_vs_buy_hold': 5.0,
        'total_trades': 6,
        'total_positions': 6,
        'full_results': {
            'positions': [
                {'entry_date': '2024-01-01', 'exit_date': '2024-01-20'},
                {'entry_date': '2024-02-01', 'exit_date': '2024-02-10'},
            ]
        }
    }
    score = bts.calculate_backtest_score(results)
    assert 0 < score <= 100


def test_calculate_backtest_score_zero_trades():
    assert bts.calculate_backtest_score({'total_trades': 0}) == 0.0


def test_calculate_wilder_rsi_values():
    prices = pd.Series(np.linspace(100, 110, 50))
    rsi = bts.calculate_wilder_rsi(prices, period=10)
    assert len(rsi) == 50
    assert rsi.min() >= 0 and rsi.max() <= 100


def _make_yf_df(n=100):
    dates = pd.date_range('2023-01-01', periods=n, freq='D')
    close = pd.Series(np.linspace(100, 120, n))
    high = close + 1
    low = close - 1
    vol = pd.Series(np.linspace(100000, 200000, n))
    return pd.DataFrame({'Open': close, 'High': high, 'Low': low, 'Close': close, 'Volume': vol}, index=dates)


def test_run_simple_backtest_monkeypatched(monkeypatch):
    # Patch yfinance.download to return deterministic data
    class FakeYF:
        @staticmethod
        def download(symbol, start=None, end=None, progress=False):
            return _make_yf_df(150)

    # Patch module reference directly
    monkeypatch.setattr(bts, 'yf', FakeYF, raising=False)

    res = bts.run_simple_backtest('AAA.NS', years_back=1, dip_mode=False)
    assert set(['symbol','total_return_pct','win_rate','total_trades','vs_buy_hold','execution_rate']).issubset(res.keys())
    assert res['total_trades'] >= 0


def test_run_stock_backtest_simple_mode(monkeypatch):
    # Force simple mode
    monkeypatch.setattr(bts, 'BACKTEST_MODE', 'simple', raising=False)
    # Patch yfinance	same as above
    class FakeYF:
        @staticmethod
        def download(symbol, start=None, end=None, progress=False):
            return _make_yf_df(120)
    monkeypatch.setattr(bts, 'yf', FakeYF, raising=False)

    out = bts.run_stock_backtest('BBB.NS', years_back=1)
    assert 'backtest_score' in out
    assert 'total_trades' in out


def test_add_backtest_scores_to_results(monkeypatch):
    # Mock run_stock_backtest to avoid network and control outputs
    def fake_run_stock_backtest(ticker, years_back=2, dip_mode=False):
        return {
            'backtest_score': 60.0,
            'total_return_pct': 30.0,
            'win_rate': 55.0,
            'total_trades': 6,
            'vs_buy_hold': 10.0,
            'execution_rate': 100.0
        }

    monkeypatch.setattr(bts, 'run_stock_backtest', fake_run_stock_backtest)

    stocks = [
        {
            'ticker': 'CCC.NS',
            'strength_score': 20.0,
            'rsi': 18.0,
            'timeframe_analysis': {'alignment_score': 8}
        }
    ]
    enhanced = bts.add_backtest_scores_to_results(stocks, years_back=1)
    assert len(enhanced) == 1
    item = enhanced[0]
    assert 'backtest' in item and 'combined_score' in item
    assert abs(item['combined_score'] - ((20.0*0.5)+(60.0*0.5))) < 1e-6
