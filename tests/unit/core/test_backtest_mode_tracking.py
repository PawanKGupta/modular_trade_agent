"""Phase 0: per-symbol backtest_mode labels for bulk CSV."""

from unittest.mock import patch

import pytest

from core import backtest_scoring as bts


@pytest.mark.parametrize(
    "env_fallback,expect_mode",
    [
        ("true", "simple_fallback"),
        ("false", "failed"),
    ],
)
def test_integrated_failure_respects_fallback_env(env_fallback, expect_mode, monkeypatch):
    monkeypatch.setenv("BULK_BACKTEST_FALLBACK_TO_SIMPLE", env_fallback)
    monkeypatch.setattr(bts, "BACKTEST_MODE", "integrated", raising=False)
    monkeypatch.setattr(
        bts, "run_integrated_backtest", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    with patch.object(bts, "run_simple_backtest") as mock_simple:
        mock_simple.return_value = {
            "symbol": "TEST.NS",
            "backtest_score": 12.0,
            "total_trades": 1,
            "win_rate": 100.0,
            "total_return_pct": 5.0,
        }
        result = bts.run_stock_backtest("TEST.NS", years_back=1)

    assert result["backtest_mode"] == expect_mode
    if expect_mode == "failed":
        assert mock_simple.call_count == 0
    else:
        assert mock_simple.call_count == 1


def test_integrated_success_mode_integrated(monkeypatch):
    monkeypatch.setattr(bts, "BACKTEST_MODE", "integrated", raising=False)
    monkeypatch.setattr(
        bts,
        "run_integrated_backtest",
        lambda **kwargs: {
            "total_return_pct": 10.0,
            "win_rate": 70.0,
            "executed_trades": 3,
            "strategy_vs_buy_hold": 1.0,
            "trade_agent_accuracy": 80.0,
            "positions": [{"return_pct": 2.0}, {"return_pct": 4.0}],
        },
    )
    monkeypatch.setattr(bts, "calculate_backtest_score", lambda *a, **k: 55.0)

    result = bts.run_stock_backtest("TEST.NS", years_back=1)
    assert result["backtest_mode"] == "integrated"


def test_simple_only_mode(monkeypatch):
    monkeypatch.setattr(bts, "BACKTEST_MODE", "simple", raising=False)
    with patch.object(bts, "run_simple_backtest") as mock_simple:
        mock_simple.return_value = {
            "symbol": "TEST.NS",
            "backtest_score": 0.0,
            "total_trades": 0,
        }
        with patch.object(bts, "calculate_backtest_score", return_value=0.0):
            result = bts.run_stock_backtest("TEST.NS", years_back=1)
    assert result["backtest_mode"] == "simple"


def test_fallback_uses_simple_fallback_label(monkeypatch):
    monkeypatch.setenv("BULK_BACKTEST_FALLBACK_TO_SIMPLE", "true")
    monkeypatch.setattr(bts, "BACKTEST_MODE", "integrated", raising=False)
    monkeypatch.setattr(
        bts,
        "run_integrated_backtest",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("yfinance")),
    )
    with patch.object(bts, "run_simple_backtest") as mock_simple:
        mock_simple.return_value = {"symbol": "TEST.NS", "total_trades": 2, "win_rate": 50.0}
        with patch.object(bts, "calculate_backtest_score", return_value=30.0):
            result = bts.run_stock_backtest("TEST.NS", years_back=1)
    assert result["backtest_mode"] == "simple_fallback"
    assert mock_simple.call_count == 1
