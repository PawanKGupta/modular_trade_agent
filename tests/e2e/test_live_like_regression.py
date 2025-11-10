import os
import json
from datetime import datetime, timedelta
import math
import pytest

from src.application.use_cases.analyze_stock import AnalyzeStockUseCase
from src.application.dto.analysis_request import AnalysisRequest


GOLDEN_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'data', 'golden', 'live_like_regression.json'))


def _extract_result(resp):
    # Extract a stable subset of fields for regression
    return {
        'ticker': resp.ticker,
        'status': resp.status,
        'verdict': resp.verdict,
        'final_verdict': resp.final_verdict or resp.verdict,
        'last_close': resp.last_close,
        'buy_range': list(resp.buy_range) if resp.buy_range else None,
        'target': resp.target,
        'stop_loss': resp.stop_loss,
        'rsi': resp.rsi,
        'mtf_alignment_score': resp.mtf_alignment_score,
        'backtest_score': resp.backtest_score,
        'combined_score': resp.combined_score,
        'priority_score': resp.priority_score,
        'metadata': {
            'risk_reward_ratio': (resp.metadata or {}).get('risk_reward_ratio'),
            'volume_multiplier': (resp.metadata or {}).get('volume_multiplier'),
            'pe': (resp.metadata or {}).get('pe'),
            # Include a condensed candle_analysis if present
            'candle_analysis': (resp.metadata or {}).get('candle_analysis'),
        }
    }


def _approx_equal(a, b, tol=1.0):
    try:
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return a == b


@pytest.mark.e2e
@pytest.mark.slow
def test_live_like_trade_analysis_regression():
    if os.getenv('RUN_E2E') not in ('1', 'true', 'True', 'YES', 'yes'):
        pytest.skip('E2E regression test skipped (set RUN_E2E=1 to run)')

    with open(GOLDEN_FILE, 'r', encoding='utf-8') as f:
        golden = json.load(f)

    end_dt = datetime.strptime(golden['date_range'][1], '%Y-%m-%d')
    uc = AnalyzeStockUseCase()

    results = {}
    for ticker in golden['tickers']:
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
        results[ticker] = _extract_result(resp)

    if os.getenv('UPDATE_GOLDEN') in ('1', 'true', 'True', 'YES', 'yes'):
        golden['expected'] = results
        with open(GOLDEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(golden, f, indent=2, sort_keys=True)
        pytest.skip('Golden file updated')

    expected = golden.get('expected')
    if not expected:
        pytest.skip('Golden expected results not present. Run with UPDATE_GOLDEN=1 to create them.')

    # Compare current results with expected, using tolerances for numeric values
    for ticker, exp in expected.items():
        cur = results.get(ticker)
        assert cur, f"No current result for {ticker}"

        # String fields exact
        assert cur['status'] == exp['status']
        assert cur['verdict'] == exp['verdict']
        assert cur['final_verdict'] == exp['final_verdict']

        # Numeric approx
        for k in ['last_close', 'target', 'stop_loss', 'rsi', 'mtf_alignment_score', 'backtest_score', 'combined_score', 'priority_score']:
            assert _approx_equal(cur.get(k), exp.get(k), tol=2.0), f"{ticker} {k}: {cur.get(k)} != {exp.get(k)}"

        # Buy range approx (list of two floats)
        if cur['buy_range'] and exp.get('buy_range'):
            assert len(cur['buy_range']) == len(exp['buy_range'])
            for i in range(len(cur['buy_range'])):
                assert _approx_equal(cur['buy_range'][i], exp['buy_range'][i], tol=2.0), f"{ticker} buy_range[{i}] differs"

        # Metadata selective checks
        cur_md = cur.get('metadata') or {}
        exp_md = exp.get('metadata') or {}
        for k in ['risk_reward_ratio', 'volume_multiplier', 'pe']:
            if exp_md.get(k) is not None:
                assert _approx_equal(cur_md.get(k), exp_md.get(k), tol=2.0), f"{ticker} metadata.{k} differs"
