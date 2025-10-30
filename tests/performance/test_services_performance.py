import time
import random
import pytest

from src.application.services.filtering_service import FilteringService
from src.application.services.scoring_service import ScoringService


@pytest.mark.performance
def test_filtering_service_throughput_large_list():
    fs = FilteringService(min_combined_score=25)
    n = 20000
    results = []
    for i in range(n):
        results.append({
            "verdict": "strong_buy" if i % 5 == 0 else ("buy" if i % 3 == 0 else "hold"),
            "status": "success",
            "combined_score": 30 if i % 7 else 10,
            "ticker": f"TICK{i}"
        })

    t0 = time.time()
    filtered = fs.filter_buy_candidates(results, enable_backtest_scoring=True)
    dt = time.time() - t0

    # Should finish comfortably fast even on CI; be generous
    assert dt < 1.5
    assert len(filtered) > 0


@pytest.mark.performance
def test_scoring_service_bulk_compute_priority():
    ss = ScoringService()
    n = 5000
    data = []
    for i in range(n):
        data.append({
            "risk_reward_ratio": random.uniform(1.0, 5.0),
            "rsi": random.uniform(10, 60),
            "volume_multiplier": random.uniform(0.8, 5.0),
            "timeframe_analysis": {"alignment_score": random.randint(0, 10)},
            "pe": random.uniform(10, 60),
            "backtest_score": random.uniform(0, 50),
        })

    t0 = time.time()
    scores = [ss.compute_trading_priority_score(d) for d in data]
    dt = time.time() - t0

    assert dt < 1.5
    assert len(scores) == n