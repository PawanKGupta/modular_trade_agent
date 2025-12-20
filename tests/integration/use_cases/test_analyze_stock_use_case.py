import src.application.use_cases.analyze_stock as analyze_mod
from src.application.dto.analysis_request import AnalysisRequest
from src.application.use_cases.analyze_stock import AnalyzeStockUseCase


class DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def test_analyze_stock_success_without_backtest(monkeypatch):
    # Patch legacy analyze to return a minimal successful dict
    def fake_legacy_analyze_ticker(
        ticker, enable_multi_timeframe, export_to_csv, as_of_date, config=None
    ):
        return {
            "ticker": ticker,
            "status": "success",
            "verdict": "buy",
            "rsi": 25.0,
            "buy_range": [100.0, 105.0],
            "last_close": 102.0,
            "timeframe_analysis": {"alignment_score": 6},
            "justification": ["pattern:hammer"],
        }

    monkeypatch.setattr(analyze_mod, "legacy_analyze_ticker", fake_legacy_analyze_ticker)

    uc = AnalyzeStockUseCase()
    req = AnalysisRequest(ticker="RELIANCE.NS", enable_backtest=False, export_to_csv=False)
    resp = uc.execute(req)

    assert resp.is_success()
    assert resp.verdict in ["buy", "strong_buy"]
    assert resp.buy_range == (100.0, 105.0)


def test_analyze_stock_with_backtest_and_final_verdict(monkeypatch):
    def fake_legacy_analyze_ticker(
        ticker, enable_multi_timeframe, export_to_csv, as_of_date, config=None
    ):
        return {
            "ticker": ticker,
            "status": "success",
            "verdict": "buy",
            "rsi": 18.0,
            "buy_range": [100.0, 105.0],
            "last_close": 102.0,
            "timeframe_analysis": {"alignment_score": 8},
            "justification": ["pattern:hammer"],
        }

    def fake_run_stock_backtest(symbol, years_back=2, dip_mode=False, config=None):
        return {
            "backtest_score": 65.0,
            "total_trades": 6,
            "total_return_pct": 40.0,
            "win_rate": 60.0,
            "vs_buy_hold": 10.0,
        }

    monkeypatch.setattr(analyze_mod, "legacy_analyze_ticker", fake_legacy_analyze_ticker)
    monkeypatch.setattr(analyze_mod, "run_stock_backtest", fake_run_stock_backtest)

    uc = AnalyzeStockUseCase()
    req = AnalysisRequest(ticker="INFY.NS", enable_backtest=True, export_to_csv=False)
    resp = uc.execute(req)

    assert resp.is_success()
    assert resp.final_verdict in ["buy", "strong_buy"]
    assert resp.combined_score >= resp.backtest_score * 0.4  # sanity check
