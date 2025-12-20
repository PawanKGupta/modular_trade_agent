import asyncio
import builtins
import importlib
import json
import logging
import pathlib
import runpy
import sys
import types
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

# ---------------------------------------------------------------------------
# Stub heavy `services` package (prevents importing full app during unit tests)
# ---------------------------------------------------------------------------
services_stub = types.ModuleType("services")
_original_services_module = sys.modules.get("services")
_original_ml_module = sys.modules.get("services.ml_verdict_service")
_original_rotating_handler = getattr(logging.handlers, "RotatingFileHandler", None)


class StubBacktestService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def add_backtest_scores_to_results(self, results, config=None):
        return results


class StubScoringService:
    def compute_trading_priority_score(self, stock_data):
        return 50


def stub_compute_strength_score(stock_data):
    return 10


services_stub.BacktestService = StubBacktestService
services_stub.ScoringService = StubScoringService
services_stub.compute_strength_score = stub_compute_strength_score
sys.modules["services"] = services_stub

# Stub ML verdict service (loaded optionally inside trade_agent)
ml_stub = types.ModuleType("services.ml_verdict_service")


class StubMLVerdictService:
    def __init__(self, model_path: str, config=None, **_):
        self.model_path = model_path
        self.config = config


ml_stub.MLVerdictService = StubMLVerdictService
sys.modules["services.ml_verdict_service"] = ml_stub

# ---------------------------------------------------------------------------
# Disable RotatingFileHandler to avoid touching filesystem during tests
# ---------------------------------------------------------------------------


class DummyRotatingFileHandler(logging.Handler):
    def __init__(self, *_, **__):
        super().__init__()


logging.handlers.RotatingFileHandler = DummyRotatingFileHandler

import trade_agent  # noqa: E402

# Restore original modules/handlers so other tests aren't affected
if _original_services_module is not None:
    sys.modules["services"] = _original_services_module
else:
    sys.modules.pop("services", None)

if _original_ml_module is not None:
    sys.modules["services.ml_verdict_service"] = _original_ml_module
else:
    sys.modules.pop("services.ml_verdict_service", None)

if _original_rotating_handler is not None:
    logging.handlers.RotatingFileHandler = _original_rotating_handler


def _valid_stock(index=1, verdict="buy", **overrides):
    data = {
        "status": "success",
        "ticker": f"TICK{index}",
        "verdict": verdict,
        "final_verdict": verdict,
        "combined_score": 55,
        "buy_range": [100.0, 110.0],
        "target": 130.0,
        "stop": 95.0,
        "rsi": 25,
        "last_close": 105.0,
        "today_vol": 2_000_000,
        "avg_vol": 1_000_000,
        "timeframe_analysis": {
            "alignment_score": 8,
            "daily_analysis": {
                "support_analysis": {"quality": "strong", "distance_pct": 0.8},
                "oversold_analysis": {"severity": "high"},
                "volume_exhaustion": {"exhaustion_score": 3},
            },
        },
        "news_sentiment": {"enabled": True, "used": 5, "label": "positive", "score": 0.7},
        "execution_capital": 50000.0,
        "capital_adjusted": True,
        "chart_quality": {"score": 85, "status": "clean"},
        "ml_verdict": verdict,
        "ml_confidence": 0.8,
    }
    data.update(overrides)
    return data


def test_get_stocks_returns_normalized_symbols(monkeypatch):
    monkeypatch.setattr(trade_agent, "get_stock_list", lambda: "Reliance , tcs")
    assert trade_agent.get_stocks() == ["RELIANCE.NS", "TCS.NS"]


def test_get_stocks_handles_failure(monkeypatch):
    monkeypatch.setattr(trade_agent, "get_stock_list", lambda: "")
    assert trade_agent.get_stocks() == []


def test_compute_trading_priority_score_success(monkeypatch):
    mock_service = Mock()
    mock_service.compute_trading_priority_score.return_value = 42
    monkeypatch.setattr(trade_agent, "ScoringService", lambda: mock_service)
    assert trade_agent.compute_trading_priority_score({"ticker": "ABC"}) == 42


def test_compute_trading_priority_score_fallback(monkeypatch):
    def _raise():
        raise RuntimeError("boom")

    monkeypatch.setattr(trade_agent, "ScoringService", _raise)
    assert trade_agent.compute_trading_priority_score({"combined_score": 17}) == 17


def test_compute_trading_priority_score_none_data(monkeypatch):
    def _raise():
        raise RuntimeError("boom")

    monkeypatch.setattr(trade_agent, "ScoringService", _raise)
    assert trade_agent.compute_trading_priority_score(None) == 0


def test_trade_agent_reload_handles_missing_model():
    original_exists = pathlib.Path.exists
    try:
        pathlib.Path.exists = lambda self: False
        importlib.reload(trade_agent)
        assert trade_agent._ml_verdict_service is None
    finally:
        pathlib.Path.exists = original_exists
        importlib.reload(trade_agent)


def test_trade_agent_reload_handles_ml_exception():
    original_exists = pathlib.Path.exists
    original_cls = sys.modules["services.ml_verdict_service"].MLVerdictService

    class RaisingML:
        def __init__(self, *_, **__):
            raise RuntimeError("bad model")

    try:
        pathlib.Path.exists = lambda self: True
        sys.modules["services.ml_verdict_service"].MLVerdictService = RaisingML
        importlib.reload(trade_agent)
        assert trade_agent._ml_verdict_service is None
    finally:
        pathlib.Path.exists = original_exists
        sys.modules["services.ml_verdict_service"].MLVerdictService = original_cls
        importlib.reload(trade_agent)


def test_trade_agent_reload_handles_import_error():
    original_exists = pathlib.Path.exists
    original_ml_module = sys.modules.get("services.ml_verdict_service")
    try:
        pathlib.Path.exists = lambda self: True
        sys.modules["services.ml_verdict_service"] = types.ModuleType("services.ml_verdict_service")
        importlib.reload(trade_agent)
        assert trade_agent._ml_verdict_service is None
    finally:
        pathlib.Path.exists = original_exists
        if original_ml_module is not None:
            sys.modules["services.ml_verdict_service"] = original_ml_module
        else:
            sys.modules.pop("services.ml_verdict_service", None)
        importlib.reload(trade_agent)


def test_get_enhanced_stock_info_valid(monkeypatch):
    stock = _valid_stock()
    text = trade_agent.get_enhanced_stock_info(stock, 1)
    assert "TICK1" in text
    assert "Target 130.00" in text


def test_get_enhanced_stock_info_invalid_returns_none():
    stock = _valid_stock()
    stock["target"] = None
    assert trade_agent.get_enhanced_stock_info(stock, 1) is None


def test_get_enhanced_stock_info_invalid_buy_window():
    stock = _valid_stock()
    stock["buy_range"] = [100.0]
    assert trade_agent.get_enhanced_stock_info(stock, 1) is None


def test_get_enhanced_stock_info_rich_fields(monkeypatch):
    stock = _valid_stock()
    stock.update(
        {
            "buy_range": [120.5, 125.0],
            "target": 150.0,
            "stop": 110.0,
            "pe": 32.1,
            "today_vol": 2_100_000,
            "avg_vol": 1_000_000,
            "news_sentiment": {"enabled": True, "used": 3, "label": "negative", "score": -0.35},
            "backtest": {"score": 80, "total_return_pct": 25.5, "win_rate": 72, "total_trades": 40},
            "combined_score": 77.3,
            "backtest_confidence": "High",
            "final_verdict": "strong_buy",
            "ml_verdict": "buy",
            "ml_confidence": 0.82,
            "execution_capital": 60000,
            "capital_adjusted": False,
        }
    )

    text = trade_agent.get_enhanced_stock_info(stock, 2)
    assert "Capital:" in text
    assert "Backtest" in text
    assert "ML:" in text


def test_get_enhanced_stock_info_chart_variants():
    stock = _valid_stock(
        verdict="strong_buy",
        chart_quality={"score": 70, "status": "acceptable"},
        news_sentiment={"enabled": False},
        timeframe_analysis={
            "alignment_score": 6,
            "daily_analysis": {
                "support_analysis": {"quality": "moderate", "distance_pct": 1.5},
                "oversold_analysis": {"severity": "extreme"},
                "volume_exhaustion": {"exhaustion_score": 0},
            },
        },
        today_vol=300_000,
        avg_vol=1_000_000,
        ml_verdict="watch",
        final_verdict="strong_buy",
        ml_confidence="82%",
        backtest_confidence="Medium",
    )
    text = trade_agent.get_enhanced_stock_info(stock, 1)
    assert "Vol:0.3x" in text
    assert "Chart:" in text
    assert "Confidence:" in text


def test_get_enhanced_stock_info_unknown_chart_status():
    stock = _valid_stock(chart_quality={"score": 60, "status": "messy"})
    text = trade_agent.get_enhanced_stock_info(stock, 1)
    assert "Chart:" in text


def test_get_enhanced_stock_info_ml_disagreement():
    stock = _valid_stock(
        verdict="watch",
        final_verdict="watch",
        ml_verdict="strong_buy",
        news_sentiment={"enabled": True, "used": 1, "label": "positive", "score": 0.4},
    )
    text = trade_agent.get_enhanced_stock_info(stock, 1)
    assert "ONLY ML" in text


def test_get_enhanced_stock_info_exception_fallback():
    stock = _valid_stock()
    stock["timeframe_analysis"] = "bad-structure"
    msg = trade_agent.get_enhanced_stock_info(stock, 1)
    assert stock["ticker"] in msg
    assert "Target" in msg


def test_main_async_falls_back(monkeypatch):
    monkeypatch.setattr(trade_agent, "get_stocks", lambda: [])
    assert asyncio.run(trade_agent.main_async()) is None


def test_process_results_without_backtest(monkeypatch):
    stock1 = _valid_stock(verdict="strong_buy")
    stock2 = _valid_stock(index=2, verdict="buy")
    monkeypatch.setattr(trade_agent, "compute_strength_score", lambda r: 10)
    monkeypatch.setattr(trade_agent, "compute_trading_priority_score", lambda r: 50)
    sent = {"calls": []}

    def _send(msg):
        sent["calls"].append(msg)

    monkeypatch.setattr(trade_agent, "send_telegram", _send)
    result = trade_agent._process_results([stock1, stock2], enable_backtest_scoring=False)
    assert len(result) == 2
    assert sent["calls"]


def test_process_results_no_candidates_logs(monkeypatch):
    recorded = []
    monkeypatch.setattr(trade_agent, "compute_strength_score", lambda r: 0)
    monkeypatch.setattr(trade_agent, "compute_trading_priority_score", lambda r: 0)
    monkeypatch.setattr(trade_agent, "send_telegram", lambda msg: recorded.append(msg))
    monkeypatch.setattr(trade_agent.logger, "info", lambda msg: recorded.append(msg))
    trade_agent._process_results(
        [{"status": "error", "ticker": "MISS", "verdict": "avoid"}],
        enable_backtest_scoring=False,
    )
    assert any("No buy candidates" in msg for msg in recorded if isinstance(msg, str))


def test_process_results_with_backtest(monkeypatch):
    stock = _valid_stock()
    base_results = [stock]
    monkeypatch.setattr(trade_agent, "compute_strength_score", lambda r: 15)
    monkeypatch.setattr(trade_agent, "compute_trading_priority_score", lambda r: 80)
    monkeypatch.setattr(trade_agent, "send_telegram", lambda msg: None)
    mock_backtest = Mock()
    mock_backtest.add_backtest_scores_to_results.return_value = base_results
    monkeypatch.setattr(trade_agent, "BacktestService", lambda **kwargs: mock_backtest)
    trade_agent._process_results(base_results, enable_backtest_scoring=True, dip_mode=True)
    mock_backtest.add_backtest_scores_to_results.assert_called_once()


def test_process_results_backtest_exports_csv(monkeypatch):
    stock = _valid_stock()
    stock.update(
        {
            "volume_analysis": {
                "vol_ok": True,
                "vol_strong": False,
                "volume_ratio": 1.4,
                "quality": "good",
            },
            "fundamental_assessment": {
                "fundamental_growth_stock": True,
                "fundamental_avoid": False,
                "fundamental_reason": "solid",
            },
        }
    )

    class CapturingBacktest:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def add_backtest_scores_to_results(self, results, config=None):
            return results

    captured = {}

    class FakeDF:
        def __init__(self, rows):
            captured["rows"] = rows

        def to_csv(self, path, index=False):
            captured["csv"] = path
            captured["index"] = index

    class FixedDatetime(datetime):
        @classmethod
        def now(cls):
            return datetime(2025, 1, 15, 10, 30)

    class DictLike(dict):
        pass

    special_volume = DictLike(stock["volume_analysis"])
    special_volume._treat_as_primitive = True
    stock["volume_analysis"] = special_volume

    special_fundamental = DictLike(stock["fundamental_assessment"])
    special_fundamental._treat_as_primitive = True
    stock["fundamental_assessment"] = special_fundamental

    real_isinstance = builtins.isinstance

    def fake_isinstance(obj, types):
        if getattr(obj, "_treat_as_primitive", False) and types == (str, int, float, bool):
            return True
        return real_isinstance(obj, types)

    monkeypatch.setattr(builtins, "isinstance", fake_isinstance)
    monkeypatch.setattr(
        trade_agent, "BacktestService", lambda **kwargs: CapturingBacktest(**kwargs)
    )
    monkeypatch.setattr(trade_agent, "compute_strength_score", lambda r: 20)
    monkeypatch.setattr(trade_agent, "compute_trading_priority_score", lambda r: 90)
    monkeypatch.setattr(trade_agent, "send_telegram", lambda msg: None)
    monkeypatch.setattr(trade_agent.pd, "DataFrame", FakeDF)
    monkeypatch.setattr(trade_agent.os, "makedirs", lambda *_, **__: None)
    monkeypatch.setattr(trade_agent, "datetime", FixedDatetime)

    results = trade_agent._process_results([stock], enable_backtest_scoring=True, dip_mode=False)
    assert captured["rows"][0]["ticker"] == stock["ticker"]
    assert "vol_ok" in captured["rows"][0]
    assert "fundamental_reason" in captured["rows"][0]
    assert captured["csv"].endswith(".csv")
    assert results


def test_process_results_backtest_handles_export_failure(monkeypatch):
    stock = _valid_stock()

    class ExplodingDF:
        def __init__(self, *_):
            raise OSError("disk full")

    monkeypatch.setattr(trade_agent, "BacktestService", lambda **__: StubBacktestService())
    monkeypatch.setattr(trade_agent.pd, "DataFrame", ExplodingDF)
    warnings = []
    monkeypatch.setattr(trade_agent.logger, "warning", lambda msg, **kwargs: warnings.append(msg))
    trade_agent._process_results([stock], enable_backtest_scoring=True)
    assert warnings


def test_process_results_backtest_uses_row_volume_analysis(monkeypatch):
    stock = _valid_stock()
    stock["volume_analysis"] = {
        "vol_ok": True,
        "vol_strong": False,
        "volume_ratio": 1.1,
        "quality": "ok",
    }

    class FakeDF:
        def __init__(self, rows):
            self.rows = rows

        def to_csv(self, *_, **__):
            pass

    monkeypatch.setattr(trade_agent, "BacktestService", lambda **__: StubBacktestService())
    monkeypatch.setattr(trade_agent.pd, "DataFrame", FakeDF)
    trade_agent._process_results([stock], enable_backtest_scoring=True)


def test_finalize_results_calls_json(monkeypatch, tmp_path):
    called = {}

    def _fake_write(data, path):
        called["path"] = path

    monkeypatch.setattr(trade_agent, "_write_results_json", _fake_write)
    data = [{"ticker": "AAA"}]
    out_path = tmp_path / "res.json"
    res = trade_agent._finalize_results(data, str(out_path))
    assert res == data
    assert str(out_path) == called["path"]


def test_write_results_json(tmp_path):
    class CustomObj:
        pass

    data = [
        {
            "time": datetime(2025, 1, 1, 10, 0),
            "path": Path("abc"),
            "labels": {"x", "y"},
            "custom": CustomObj(),
        }
    ]
    out = tmp_path / "nested" / "results.json"
    trade_agent._write_results_json(data, str(out))
    saved = json.loads(out.read_text())
    assert saved[0]["time"].startswith("2025-01-01")
    assert saved[0]["path"] == "abc"
    assert isinstance(saved[0]["labels"], list)
    assert "CustomObj" in saved[0]["custom"]


def test_write_results_json_handles_failure(monkeypatch, tmp_path):
    data = [{"ticker": "AAA"}]
    target = tmp_path / "results.json"

    def boom(*_, **__):
        raise OSError("disk full")

    warnings = []
    monkeypatch.setattr(trade_agent.json, "dump", boom)
    monkeypatch.setattr(trade_agent.logger, "warning", lambda msg: warnings.append(msg))

    trade_agent._write_results_json(data, str(target))
    assert warnings


def test_main_async_runs_full_flow(monkeypatch):
    monkeypatch.setattr(trade_agent, "get_stocks", lambda: ["AAA"])
    monkeypatch.setattr(trade_agent, "send_telegram", lambda msg: None)

    settings_mod = types.ModuleType("config.settings")
    settings_mod.MAX_CONCURRENT_ANALYSES = 2
    async_mod = types.ModuleType("services.async_analysis_service")

    class DummyAsyncAnalysisService:
        def __init__(self, max_concurrent, config=None):
            self.max_concurrent = max_concurrent
            self.config = config

        async def analyze_batch_async(self, **kwargs):
            return [
                {
                    "status": "success",
                    "ticker": "AAA",
                    "verdict": "buy",
                    "buy_range": [1, 2],
                    "target": 3,
                    "stop": 0.5,
                    "timeframe_analysis": None,
                    "today_vol": 1,
                    "avg_vol": 1,
                    "news_sentiment": {"enabled": False},
                }
            ]

    async_mod.AsyncAnalysisService = DummyAsyncAnalysisService
    monkeypatch.setitem(sys.modules, "config.settings", settings_mod)
    monkeypatch.setitem(sys.modules, "services.async_analysis_service", async_mod)

    results = asyncio.run(
        trade_agent.main_async(
            export_csv=False,
            enable_multi_timeframe=False,
            enable_backtest_scoring=False,
            dip_mode=False,
        )
    )
    assert results and results[0]["ticker"] == "AAA"


def test_main_async_import_error_calls_sequential(monkeypatch):
    monkeypatch.setattr(trade_agent, "get_stocks", lambda: ["AAA"])
    monkeypatch.setattr(trade_agent, "main_sequential", lambda *_, **__: "seq")
    original_async = sys.modules.get("services.async_analysis_service")
    sys.modules["services.async_analysis_service"] = types.ModuleType(
        "services.async_analysis_service"
    )

    try:
        outcome = asyncio.run(trade_agent.main_async())
        assert outcome == "seq"
    finally:
        if original_async is not None:
            sys.modules["services.async_analysis_service"] = original_async
        else:
            sys.modules.pop("services.async_analysis_service", None)


def test_main_sequential_handles_errors(monkeypatch):
    monkeypatch.setattr(trade_agent, "get_stocks", lambda: ["AAA", "BBB", "CCC"])

    def fake_analyze(ticker, **_):
        if ticker == "AAA":
            return {"ticker": ticker, "status": "success", "verdict": "buy"}
        if ticker == "BBB":
            return {"ticker": ticker, "status": "pending", "error": "slow"}
        raise RuntimeError("boom")

    captured = {}

    def fake_process(results, *_, **__):
        captured["results"] = results
        return results

    monkeypatch.setattr(trade_agent, "analyze_ticker", fake_analyze)
    monkeypatch.setattr(trade_agent, "_process_results", fake_process)

    outcome = trade_agent.main_sequential(export_csv=False, enable_multi_timeframe=False)
    assert outcome == captured["results"]
    assert captured["results"][1]["status"] == "pending"
    assert captured["results"][2]["status"] == "fatal_error"


def test_main_sequential_no_stocks(monkeypatch):
    monkeypatch.setattr(trade_agent, "get_stocks", lambda: [])
    logs = []
    monkeypatch.setattr(trade_agent.logger, "error", lambda msg: logs.append(msg))
    assert trade_agent.main_sequential() is None
    assert logs


def test_main_sequential_with_csv(monkeypatch):
    monkeypatch.setattr(trade_agent, "get_stocks", lambda: ["AAA"])

    def fake_analyze_multiple(tickers, **_):
        return (
            [{"ticker": tickers[0], "status": "success", "verdict": "buy"}],
            "fake.csv",
        )

    called = {}

    def fake_process(results, *_, **__):
        called["results"] = results
        return results

    monkeypatch.setattr(trade_agent, "analyze_multiple_tickers", fake_analyze_multiple)
    monkeypatch.setattr(trade_agent, "_process_results", fake_process)

    trade_agent.main_sequential(export_csv=True)
    assert called["results"][0]["ticker"] == "AAA"


def test_main_prefers_async_mode(monkeypatch):
    async def stub_main_async(**kwargs):
        return {"async": kwargs["export_csv"]}

    def run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    monkeypatch.setattr(trade_agent, "main_async", stub_main_async)
    monkeypatch.setattr(asyncio, "run", run)
    result = trade_agent.main(use_async=True, export_csv=False)
    assert result == {"async": False}


def test_main_async_failure_falls_to_sequential(monkeypatch):
    def raising_run(_):
        raise RuntimeError("fail")

    monkeypatch.setattr(asyncio, "run", raising_run)
    monkeypatch.setattr(trade_agent, "main_sequential", lambda **_: "sequential")
    result = trade_agent.main(use_async=True)
    assert result == "sequential"


def test_main_sequential_mode(monkeypatch):
    monkeypatch.setattr(trade_agent, "main_sequential", lambda **_: "seq")
    assert trade_agent.main(use_async=False) == "seq"


def test_trade_agent_cli_entrypoint(monkeypatch):
    analysis_stub = types.ModuleType("core.analysis")
    analysis_stub.analyze_multiple_tickers = lambda *_, **__: (
        [{"status": "success", "ticker": "AAA", "verdict": "buy"}],
        "fake.csv",
    )
    analysis_stub.analyze_ticker = lambda *_, **__: {
        "status": "success",
        "ticker": "AAA",
        "verdict": "buy",
    }
    scrapping_stub = types.ModuleType("core.scrapping")
    scrapping_stub.get_stock_list = lambda: ""
    telegram_stub = types.ModuleType("core.telegram")
    telegram_stub.send_telegram = lambda *_: None

    saved = {}
    for name, module in {
        "core.analysis": analysis_stub,
        "core.scrapping": scrapping_stub,
        "core.telegram": telegram_stub,
    }.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = module

    argv = sys.argv[:]
    sys.argv = ["trade_agent.py", "--no-async", "--no-csv"]

    try:
        runpy.run_path(str(Path("trade_agent.py")), run_name="__main__")
    finally:
        sys.argv = argv
        for name, module in saved.items():
            if module is None:
                del sys.modules[name]
            else:
                sys.modules[name] = module
