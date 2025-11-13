import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.application.services.filtering_service import FilteringService


def make_result(ticker, verdict='buy', status='success', combined=30):
    return {
        'ticker': ticker,
        'verdict': verdict,
        'final_verdict': verdict,
        'status': status,
        'combined_score': combined,
    }


def test_filter_buy_and_strong_buy_candidates():
    svc = FilteringService(min_combined_score=25)
    results = [
        make_result('A', 'buy', 'success', 10),
        make_result('B', 'buy', 'success', 35),
        make_result('C', 'strong_buy', 'success', 50),
        make_result('D', 'avoid', 'success', 90),
        make_result('E', 'buy', 'error', 80),
        None,
    ]

    # Without backtest scoring (uses verdict only)
    buys = svc.filter_buy_candidates(results, enable_backtest_scoring=False)
    assert [r['ticker'] for r in buys] == ['A', 'B', 'C']  # status filter excludes E, D is not buy

    # With backtest scoring and threshold (uses combined & final_verdict)
    buys_bt = svc.filter_buy_candidates(results, enable_backtest_scoring=True)
    assert [r['ticker'] for r in buys_bt] == ['B', 'C']

    strong = svc.filter_strong_buy_candidates(results, enable_backtest_scoring=True)
    assert [r['ticker'] for r in strong] == ['C']


def test_remove_invalid_and_score_filters_and_exclusions():
    svc = FilteringService()
    raw = [None, {'a': 1}, 'x']
    cleaned = svc.remove_invalid_results(raw)
    assert cleaned == [{'a': 1}]

    items = [
        {'ticker': 'A', 'combined_score': 10},
        {'ticker': 'B', 'combined_score': 30},
    ]
    assert [r['ticker'] for r in svc.filter_by_score_threshold(items, 20)] == ['B']

    results = [
        {'ticker': 'A'},
        {'ticker': 'B'},
        {'ticker': 'C'},
    ]
    assert [r['ticker'] for r in svc.exclude_tickers(results, ['b'])] == ['A', 'C']

    errs = svc.get_error_results([
        {'ticker': 'OK', 'status': 'success'},
        {'ticker': 'NO', 'status': 'error'},
        {'ticker': 'BAD', 'status': 'success', 'error': 'x'},
    ])
    assert {r['ticker'] for r in errs} == {'NO', 'BAD'}
