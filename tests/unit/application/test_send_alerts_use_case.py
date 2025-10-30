from datetime import datetime
import builtins
import types
import pytest

from src.application.use_cases.send_alerts import SendAlertsUseCase
from src.application.dto.analysis_response import AnalysisResponse, BulkAnalysisResponse


def make_resp(ticker, verdict='buy', final=None, combined=30.0, last_close=100.0, mtf=5.0):
    return AnalysisResponse(
        ticker=ticker,
        status='success',
        timestamp=datetime.now(),
        verdict=verdict,
        final_verdict=final,
        last_close=last_close,
        buy_range=(95.0, 100.0),
        target=115.0,
        stop_loss=90.0,
        rsi=25.0,
        mtf_alignment_score=mtf,
        backtest_score=40.0,
        combined_score=combined,
        priority_score=60.0,
        metadata={'risk_reward_ratio': 2.0, 'pe': 20.0, 'volume_multiplier': 1.5},
    )


def test_send_alerts_no_candidates_returns_true(monkeypatch):
    monkeypatch.setattr('src.application.use_cases.send_alerts.send_telegram', lambda m: None)
    uc = SendAlertsUseCase()
    bulk = BulkAnalysisResponse(
        results=[make_resp('AAA.NS', verdict='watch', combined=10)],
        total_analyzed=1, successful=1, failed=0, buyable_count=0, timestamp=datetime.now(), execution_time_seconds=0.1
    )
    assert uc.execute(bulk) is True


def test_send_alerts_with_candidates_and_strong_buys(monkeypatch):
    sent = {'msg': None}
    monkeypatch.setattr('src.application.use_cases.send_alerts.send_telegram', lambda m: sent.__setitem__('msg', m))

    uc = SendAlertsUseCase()
    r1 = make_resp('AAA.NS', verdict='buy', combined=50)
    r2 = make_resp('BBB.NS', verdict='strong_buy', combined=60)
    bulk = BulkAnalysisResponse(
        results=[r1, r2], total_analyzed=2, successful=2, failed=0, buyable_count=2, timestamp=datetime.now(), execution_time_seconds=0.1
    )
    assert uc.execute(bulk, min_combined_score=0.0) is True
    assert 'STRONG BUY' in sent['msg'] and 'BUY* candidates' in sent['msg']


def test_send_alerts_uses_final_verdict_and_min_score(monkeypatch):
    sent = {'msg': None}
    monkeypatch.setattr('src.application.use_cases.send_alerts.send_telegram', lambda m: sent.__setitem__('msg', m))
    uc = SendAlertsUseCase()
    # r1 would be filtered by combined score when min_score=55
    r1 = make_resp('AAA.NS', verdict='buy', final='watch', combined=50)
    r2 = make_resp('BBB.NS', verdict='watch', final='buy', combined=60)
    bulk = BulkAnalysisResponse(
        results=[r1, r2], total_analyzed=2, successful=2, failed=0, buyable_count=1, timestamp=datetime.now(), execution_time_seconds=0.1
    )
    assert uc.execute(bulk, min_combined_score=55, use_final_verdict=True) is True
    # Only BBB should be present
    assert 'BBB.NS' in sent['msg'] and 'AAA.NS' not in sent['msg']


def test_send_alerts_handles_telegram_failure(monkeypatch):
    def boom(msg):
        raise RuntimeError('send failed')
    monkeypatch.setattr('src.application.use_cases.send_alerts.send_telegram', boom)
    uc = SendAlertsUseCase()
    r = make_resp('AAA.NS', verdict='buy', combined=60)
    bulk = BulkAnalysisResponse(
        results=[r], total_analyzed=1, successful=1, failed=0, buyable_count=1, timestamp=datetime.now(), execution_time_seconds=0.1
    )
    assert uc.execute(bulk) is False
