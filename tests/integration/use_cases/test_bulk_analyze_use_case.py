from datetime import datetime
from src.application.use_cases.bulk_analyze import BulkAnalyzeUseCase
from src.application.dto.analysis_request import BulkAnalysisRequest, AnalysisRequest
from src.application.dto.analysis_response import AnalysisResponse, BulkAnalysisResponse


class FakeAnalyzeStock:
    def execute(self, request: AnalysisRequest):
        # Return deterministic responses per ticker
        if request.ticker == 'AAA.NS':
            return AnalysisResponse(
                ticker='AAA.NS', status='success', timestamp=datetime.now(),
                verdict='buy', combined_score=50.0, priority_score=60.0
            )
        return AnalysisResponse(
            ticker=request.ticker, status='success', timestamp=datetime.now(),
            verdict='watch', combined_score=10.0, priority_score=10.0
        )


def test_bulk_analyze_sorts_and_counts():
    uc = BulkAnalyzeUseCase(
        analyze_stock_use_case=FakeAnalyzeStock()
    )

    req = BulkAnalysisRequest(
        tickers=['AAA.NS', 'BBB.NS'], enable_backtest=False, export_to_csv=False
    )
    resp = uc.execute(req)

    assert resp.total_analyzed == 2
    assert resp.buyable_count == 1
    # Sorted by priority score descending
    assert resp.results[0].ticker == 'AAA.NS'


def test_bulk_analyze_with_backtest_threshold():
    class FakeAnalyzeStockBT(FakeAnalyzeStock):
        def execute(self, request: AnalysisRequest):
            r = super().execute(request)
            # Simulate backtest present
            if r.verdict == 'buy':
                r.final_verdict = 'buy'
                r.combined_score = 30.0
            else:
                r.final_verdict = 'watch'
            return r

    uc = BulkAnalyzeUseCase(
        analyze_stock_use_case=FakeAnalyzeStockBT()
    )

    req = BulkAnalysisRequest(
        tickers=['AAA.NS', 'BBB.NS'], enable_backtest=True, export_to_csv=False, min_combined_score=25.0
    )
    resp = uc.execute(req)

    assert resp.buyable_count == 1  # only AAA qualifies
