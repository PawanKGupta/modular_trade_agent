import builtins
from datetime import datetime

import src.application.use_cases.example_usage as ex
from src.application.dto.analysis_response import AnalysisResponse, BulkAnalysisResponse


class FakeAnalyze:
    def execute(self, req):
        return AnalysisResponse(
            ticker=req.ticker,
            status='success',
            timestamp=datetime.now(),
            verdict='buy',
            last_close=100.0,
            priority_score=50.0,
        )


class FakeBulk:
    def __init__(self, resp=None):
        self._resp = resp
    def execute(self, req):
        r = AnalysisResponse(
            ticker='AAA.NS', status='success', timestamp=datetime.now(), verdict='buy', priority_score=60.0
        )
        return BulkAnalysisResponse(
            results=[r], total_analyzed=1, successful=1, failed=0, buyable_count=1, timestamp=datetime.now(), execution_time_seconds=0.1
        )


class FakeSend:
    def execute(self, response, min_combined_score=0.0, use_final_verdict=False):
        return True


def test_example_single_and_bulk_and_alerts(monkeypatch):
    # Silence prints
    monkeypatch.setattr(builtins, 'print', lambda *a, **k: None)

    monkeypatch.setattr(ex, 'AnalyzeStockUseCase', lambda *a, **k: FakeAnalyze())
    monkeypatch.setattr(ex, 'BulkAnalyzeUseCase', lambda *a, **k: FakeBulk())
    monkeypatch.setattr(ex, 'SendAlertsUseCase', lambda *a, **k: FakeSend())

    r1 = ex.example_single_stock_analysis()
    assert r1.is_success()

    r2 = ex.example_bulk_analysis()
    assert r2.total_analyzed == 1

    r3 = ex.example_with_alerts()
    assert r3.total_analyzed >= 1


def test_example_with_custom_services(monkeypatch):
    monkeypatch.setattr(builtins, 'print', lambda *a, **k: None)
    monkeypatch.setattr(ex, 'AnalyzeStockUseCase', lambda *a, **k: FakeAnalyze())
    monkeypatch.setattr(ex, 'BulkAnalyzeUseCase', lambda *a, **k: FakeBulk())
    r = ex.example_with_custom_services()
    assert r.total_analyzed == 1
