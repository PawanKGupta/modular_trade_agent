import numpy as np
import pandas as pd

# Keep for helper functions (run_simple_backtest, calculate_wilder_rsi)
import core.backtest_scoring as bts

# Phase 4.8: Update to use BacktestService instead of core.backtest_scoring
from services.backtest_service import BacktestService


def test_calculate_backtest_score_components():
    """Test BacktestService.calculate_backtest_score (Phase 4.8: migrated from core)"""
    service = BacktestService()
    results = {
        "total_return_pct": 25.0,
        "win_rate": 60.0,
        "strategy_vs_buy_hold": 5.0,
        "total_trades": 6,
        "total_positions": 6,
        "full_results": {
            "positions": [
                {"entry_date": "2024-01-01", "exit_date": "2024-01-20"},
                {"entry_date": "2024-02-01", "exit_date": "2024-02-10"},
            ]
        },
    }
    score = service.calculate_backtest_score(results)
    assert 0 < score <= 100


def test_calculate_backtest_score_zero_trades():
    """Test BacktestService.calculate_backtest_score with zero trades"""
    service = BacktestService()
    assert service.calculate_backtest_score({"total_trades": 0}) == 0.0


def test_calculate_wilder_rsi_values():
    prices = pd.Series(np.linspace(100, 110, 50))
    rsi = bts.calculate_wilder_rsi(prices, period=10)
    assert len(rsi) == 50
    assert rsi.min() >= 0 and rsi.max() <= 100


def _make_yf_df(n=100):
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 120, n))
    high = close + 1
    low = close - 1
    vol = pd.Series(np.linspace(100000, 200000, n))
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": vol}, index=dates
    )


def test_run_simple_backtest_monkeypatched(monkeypatch):
    # Patch yfinance.download to return deterministic data
    class FakeYF:
        @staticmethod
        def download(symbol, start=None, end=None, progress=False):
            return _make_yf_df(150)

    # Patch module reference directly
    monkeypatch.setattr(bts, "yf", FakeYF, raising=False)

    res = bts.run_simple_backtest("AAA.NS", years_back=1, dip_mode=False)
    assert set(
        ["symbol", "total_return_pct", "win_rate", "total_trades", "vs_buy_hold", "execution_rate"]
    ).issubset(res.keys())
    assert res["total_trades"] >= 0


def test_run_stock_backtest_simple_mode(monkeypatch):
    # Force simple mode
    monkeypatch.setattr(bts, "BACKTEST_MODE", "simple", raising=False)

    # Patch yfinance	same as above
    class FakeYF:
        @staticmethod
        def download(symbol, start=None, end=None, progress=False):
            return _make_yf_df(120)

    monkeypatch.setattr(bts, "yf", FakeYF, raising=False)

    out = bts.run_stock_backtest("BBB.NS", years_back=1)
    assert "backtest_score" in out
    assert "total_trades" in out


def test_add_backtest_scores_to_results(monkeypatch):
    # Mock run_stock_backtest to avoid network and control outputs
    # Updated to match new function signature with config parameter
    def fake_run_stock_backtest(ticker, years_back=2, dip_mode=False, config=None):
        return {
            "backtest_score": 60.0,
            "total_return_pct": 30.0,
            "win_rate": 55.0,
            "total_trades": 6,
            "vs_buy_hold": 10.0,
            "execution_rate": 100.0,
        }

    monkeypatch.setattr(bts, "run_stock_backtest", fake_run_stock_backtest)

    stocks = [
        {
            "ticker": "CCC.NS",
            "strength_score": 20.0,
            "rsi": 18.0,
            "timeframe_analysis": {"alignment_score": 8},
        }
    ]
    enhanced = bts.add_backtest_scores_to_results(stocks, years_back=1)
    assert len(enhanced) == 1
    item = enhanced[0]
    assert "backtest" in item and "combined_score" in item
    # Combined score = (current_score * 0.5) + (backtest_score * 0.5)
    # = (20.0 * 0.5) + (60.0 * 0.5) = 10.0 + 30.0 = 40.0
    assert abs(item["combined_score"] - 40.0) < 1e-6


def test_run_stock_backtest_integrated_mode_avg_return_calculation(monkeypatch):
    """Test that avg_return is calculated from positions when using integrated backtest mode"""
    # Force integrated mode
    monkeypatch.setattr(bts, "BACKTEST_MODE", "integrated", raising=False)

    # Mock run_integrated_backtest to return positions with return_pct
    def fake_run_integrated_backtest(
        stock_name,
        date_range,
        capital_per_position=50000,
        skip_trade_agent_validation=False,
        config=None,
    ):
        return {
            "stock_name": "TEST.NS",
            "total_return_pct": 15.0,
            "win_rate": 75.0,
            "executed_trades": 4,
            "strategy_vs_buy_hold": 5.0,
            "trade_agent_accuracy": 100.0,
            "positions": [
                {"return_pct": 8.0},  # 8% return
                {"return_pct": 5.0},  # 5% return
                {"return_pct": 2.0},  # 2% return
                {"return_pct": 0.0},  # 0% return (break even)
            ],
        }

    monkeypatch.setattr(bts, "run_integrated_backtest", fake_run_integrated_backtest)

    # Mock calculate_backtest_score
    def fake_calculate_backtest_score(backtest_results, dip_mode=False):
        return 50.0

    monkeypatch.setattr(bts, "calculate_backtest_score", fake_calculate_backtest_score)

    result = bts.run_stock_backtest("TEST.NS", years_back=2)

    # Verify avg_return is calculated correctly: (8 + 5 + 2 + 0) / 4 = 3.75
    assert "avg_return" in result
    assert abs(result["avg_return"] - 3.75) < 1e-6
    assert result["win_rate"] == 75.0
    assert result["total_trades"] == 4


def test_run_stock_backtest_integrated_mode_avg_return_no_positions(monkeypatch):
    """Test that avg_return is 0 when there are no positions"""
    # Force integrated mode
    monkeypatch.setattr(bts, "BACKTEST_MODE", "integrated", raising=False)

    # Mock run_integrated_backtest to return no positions
    def fake_run_integrated_backtest(
        stock_name,
        date_range,
        capital_per_position=50000,
        skip_trade_agent_validation=False,
        config=None,
    ):
        return {
            "stock_name": "TEST.NS",
            "total_return_pct": 0.0,
            "win_rate": 0.0,
            "executed_trades": 0,
            "strategy_vs_buy_hold": 0.0,
            "trade_agent_accuracy": 100.0,
            "positions": [],  # No positions
        }

    monkeypatch.setattr(bts, "run_integrated_backtest", fake_run_integrated_backtest)

    # Mock calculate_backtest_score
    def fake_calculate_backtest_score(backtest_results, dip_mode=False):
        return 0.0

    monkeypatch.setattr(bts, "calculate_backtest_score", fake_calculate_backtest_score)

    result = bts.run_stock_backtest("TEST.NS", years_back=2)

    # Verify avg_return is 0 when no positions
    assert "avg_return" in result
    assert result["avg_return"] == 0.0


def test_run_stock_backtest_integrated_mode_avg_return_with_none_values(monkeypatch):
    """Test that avg_return calculation handles None values in return_pct"""
    # Force integrated mode
    monkeypatch.setattr(bts, "BACKTEST_MODE", "integrated", raising=False)

    # Mock run_integrated_backtest to return positions with some None return_pct
    def fake_run_integrated_backtest(
        stock_name,
        date_range,
        capital_per_position=50000,
        skip_trade_agent_validation=False,
        config=None,
    ):
        return {
            "stock_name": "TEST.NS",
            "total_return_pct": 10.0,
            "win_rate": 66.7,
            "executed_trades": 3,
            "strategy_vs_buy_hold": 5.0,
            "trade_agent_accuracy": 100.0,
            "positions": [
                {"return_pct": 5.0},  # 5% return
                {"return_pct": None},  # None (should be skipped)
                {"return_pct": 3.0},  # 3% return
            ],
        }

    monkeypatch.setattr(bts, "run_integrated_backtest", fake_run_integrated_backtest)

    # Mock calculate_backtest_score
    def fake_calculate_backtest_score(backtest_results, dip_mode=False):
        return 45.0

    monkeypatch.setattr(bts, "calculate_backtest_score", fake_calculate_backtest_score)

    result = bts.run_stock_backtest("TEST.NS", years_back=2)

    # Verify avg_return is calculated only from non-None values: (5 + 3) / 2 = 4.0
    assert "avg_return" in result
    assert abs(result["avg_return"] - 4.0) < 1e-6


def test_run_stock_backtest_simple_mode_avg_return_preserved(monkeypatch):
    """Test that avg_return from simple backtest mode is preserved"""
    # Force simple mode
    monkeypatch.setattr(bts, "BACKTEST_MODE", "simple", raising=False)

    # Mock run_simple_backtest to return avg_return
    def fake_run_simple_backtest(stock_symbol, years_back=2, dip_mode=False, config=None):
        return {
            "symbol": "TEST.NS",
            "backtest_score": 0,  # Will be calculated later
            "total_return_pct": 12.0,
            "win_rate": 80.0,
            "total_trades": 5,
            "vs_buy_hold": 8.0,
            "execution_rate": 100.0,
            "avg_return": 2.5,  # avg_return from simple backtest
        }

    monkeypatch.setattr(bts, "run_simple_backtest", fake_run_simple_backtest)

    # Mock calculate_backtest_score
    def fake_calculate_backtest_score(backtest_results, dip_mode=False):
        return 55.0

    monkeypatch.setattr(bts, "calculate_backtest_score", fake_calculate_backtest_score)

    result = bts.run_stock_backtest("TEST.NS", years_back=2)

    # Verify avg_return from simple backtest is preserved
    assert "avg_return" in result
    assert result["avg_return"] == 2.5
