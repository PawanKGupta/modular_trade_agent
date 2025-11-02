# Phase 4: Use services package directly (consolidated)
from services.scoring_service import ScoringService


def test_compute_strength_score_with_timeframe():
    svc = ScoringService()
    data = {
        'verdict': 'buy',
        'justification': ['pattern:hammer,bullish_engulfing', 'rsi:18', 'good_uptrend_dip_confirmation'],
        'timeframe_analysis': {
            'alignment_score': 8,
            'daily_analysis': {
                'oversold_analysis': {'severity': 'extreme'},
                'support_analysis': {'quality': 'strong'},
                'volume_exhaustion': {'exhaustion_score': 2},
            },
            'weekly_analysis': {},
        },
    }
    score = svc.compute_strength_score(data)
    assert 0 <= score <= 25
    assert score >= 15  # should be reasonably high given inputs


def test_compute_trading_priority_score_and_combined():
    svc = ScoringService()
    stock = {
        'risk_reward_ratio': 3.0,
        'rsi': 22,
        'volume_multiplier': 2.0,
        'timeframe_analysis': {'alignment_score': 7},
        'pe': 20,
        'backtest_score': 35,
    }
    score = svc.compute_trading_priority_score(stock)
    assert score > 0

    combined = svc.compute_combined_score(current_score=20, backtest_score=40, current_weight=0.5, backtest_weight=0.5)
    assert combined == 30
