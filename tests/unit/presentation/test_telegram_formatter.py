from datetime import datetime
from src.presentation.formatters.telegram_formatter import TelegramFormatter
from src.application.dto.analysis_response import AnalysisResponse, BulkAnalysisResponse


def make_resp(ticker="RELIANCE.NS", verdict="buy", rsi=25.0, mtf=7.0, backtest=55.0, combined=45.0, priority=90.0,
               buy_range=(100.0, 105.0), target=115.0, stop=95.0, pe=20.0, vol_mult=1.8, rr=2.5,
               sentiment={"enabled": True, "used": 2, "label": "positive", "score": 0.3}):
    meta = {
        'risk_reward_ratio': rr,
        'pe': pe,
        'volume_multiplier': vol_mult,
        'timeframe_analysis': {
            'daily_analysis': {
                'support_analysis': {'quality': 'strong', 'distance_pct': 1.2},
                'oversold_analysis': {'severity': 'high'},
                'volume_exhaustion': {'exhaustion_score': 2},
            }
        },
        'news_sentiment': sentiment,
    }
    return AnalysisResponse(
        ticker=ticker,
        status='success',
        timestamp=datetime.now(),
        verdict=verdict,
        last_close=102.0,
        buy_range=buy_range,
        target=target,
        stop_loss=stop,
        rsi=rsi,
        mtf_alignment_score=mtf,
        backtest_score=backtest,
        combined_score=combined,
        priority_score=priority,
        metadata=meta,
    )


def test_format_bulk_response_with_candidates():
    fmt = TelegramFormatter()
    r1 = make_resp(ticker='AAA.NS', verdict='strong_buy', priority=120.0)
    r2 = make_resp(ticker='BBB.NS', verdict='buy')
    bulk = BulkAnalysisResponse(
        results=[r1, r2], total_analyzed=2, successful=2, failed=0, buyable_count=2, timestamp=datetime.now(), execution_time_seconds=0.2
    )

    msg = fmt.format_bulk_response(bulk, include_backtest=True)
    assert "STRONG BUY" in msg
    assert "*BUY* candidates" in msg
    assert "AAA.NS" in msg and "BBB.NS" in msg


def test_format_bulk_response_no_candidates():
    fmt = TelegramFormatter()
    r = make_resp(verdict='watch')
    bulk = BulkAnalysisResponse(
        results=[r], total_analyzed=1, successful=1, failed=0, buyable_count=0, timestamp=datetime.now(), execution_time_seconds=0.1
    )
    msg = fmt.format_bulk_response(bulk)
    assert msg.startswith("*No buy candidates")


def test_format_stock_detailed_and_simple_and_summary():
    fmt = TelegramFormatter()
    r = make_resp()
    detailed = fmt.format_stock_detailed(r, 1)
    assert "1. RELIANCE.NS" in detailed
    assert "Buy (" in detailed
    assert "Target" in detailed and "Stop" in detailed
    assert "RSI:" in detailed and "MTF:" in detailed and "RR:" in detailed
    assert "Backtest:" in detailed and "Score:" in detailed and "Priority:" in detailed

    simple = fmt.format_stock_simple(r)
    assert "RELIANCE.NS" in simple and "BUY" in simple and "Priority:" in simple

    bulk = BulkAnalysisResponse(
        results=[r], total_analyzed=1, successful=1, failed=0, buyable_count=1, timestamp=datetime.now(), execution_time_seconds=0.3
    )
    summary = fmt.format_summary(bulk)
    assert "Analysis Summary" in summary and "Total: 1" in summary