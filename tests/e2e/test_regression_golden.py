import os
import json
from datetime import datetime
import pytest

from src.application.use_cases.analyze_stock import AnalyzeStockUseCase
from src.application.dto.analysis_request import AnalysisRequest


@pytest.mark.e2e
@pytest.mark.slow
def test_backtest_scoring_recommendation_regression_against_golden():
    # Only run when explicitly enabled to avoid flaky CI due to network/data updates
    if os.getenv('RUN_E2E') not in ('1', 'true', 'True', 'YES', 'yes'):
        pytest.skip('E2E regression test skipped (set RUN_E2E=1 to run)')

    base_dir = os.path.dirname(__file__)
    golden_path = os.path.join(base_dir, '..', 'data', 'golden', 'backtest_regression.json')
    golden_path = os.path.normpath(golden_path)

    with open(golden_path, 'r', encoding='utf-8') as f:
        golden = json.load(f)

    date_range = golden.get('date_range')  # [start, end]
    end_date_str = date_range[1]
    end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')

    tickers = golden.get('tickers', [])
    expectations = golden.get('expectations', {})

    uc = AnalyzeStockUseCase()

    for ticker in tickers:
        exp = expectations.get(ticker, {})
        req = AnalysisRequest(
            ticker=ticker,
            enable_multi_timeframe=True,
            enable_backtest=True,
            export_to_csv=False,
            dip_mode=False,
            end_date=end_dt,
        )
        resp = uc.execute(req)
        assert resp.is_success(), f"Analysis failed for {ticker}: {resp.status} {resp.error_message}"

        # Validate backtest and combined scores against minimums if provided
        min_bt = exp.get('min_backtest_score')
        if min_bt is not None:
            assert resp.backtest_score >= min_bt, f"{ticker} backtest_score {resp.backtest_score} < {min_bt}"

        min_comb = exp.get('min_combined_score')
        if min_comb is not None:
            assert resp.combined_score >= min_comb, f"{ticker} combined_score {resp.combined_score} < {min_comb}"

        # Optionally validate final verdict membership (be lenient to avoid flakiness)
        allowed = exp.get('final_verdict_in')
        if allowed:
            fv = resp.final_verdict or resp.verdict
            assert fv in allowed, f"{ticker} final verdict {fv} not in allowed {allowed}"

        # Optional upper bounds to catch runaway scores
        max_bt = exp.get('max_backtest_score')
        if max_bt is not None:
            assert resp.backtest_score <= max_bt, f"{ticker} backtest_score {resp.backtest_score} > {max_bt}"

        max_comb = exp.get('max_combined_score')
        if max_comb is not None:
            assert resp.combined_score <= max_comb, f"{ticker} combined_score {resp.combined_score} > {max_comb}"
