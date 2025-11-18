# ruff: noqa: B008
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Signals
from src.infrastructure.db.timezone_utils import ist_now
from src.infrastructure.persistence.signals_repository import SignalsRepository

from ..core.deps import get_current_user, get_db

router = APIRouter()


@router.get("/buying-zone")
def buying_zone(
    limit: int = Query(100, ge=1, le=500),
    date_filter: str | None = Query(
        None,
        description="Filter by date: 'today', 'yesterday', or 'last_10_days'",
    ),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    repo = SignalsRepository(db)
    now = ist_now()
    today = now.date()

    if date_filter == "today":
        items: list[Signals] = repo.by_date(today, limit=limit)
    elif date_filter == "yesterday":
        yesterday = today - timedelta(days=1)
        items = repo.by_date(yesterday, limit=limit)
    elif date_filter == "last_10_days":
        items = repo.last_n_dates(n=10, limit=limit)
    else:
        # Default: recent (no date filter)
        items = repo.recent(limit=limit)
    # Map to client shape with all analysis result fields
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            # Technical indicators
            "rsi10": s.rsi10,
            "ema9": s.ema9,
            "ema200": s.ema200,
            "distance_to_ema9": s.distance_to_ema9,
            "clean_chart": s.clean_chart,
            "monthly_support_dist": s.monthly_support_dist,
            "confidence": s.confidence,
            # Scoring fields
            "backtest_score": s.backtest_score,
            "combined_score": s.combined_score,
            "strength_score": s.strength_score,
            "priority_score": s.priority_score,
            # ML fields
            "ml_verdict": s.ml_verdict,
            "ml_confidence": s.ml_confidence,
            "ml_probabilities": s.ml_probabilities,
            # Trading parameters
            "buy_range": s.buy_range,
            "target": s.target,
            "stop": s.stop,
            "last_close": s.last_close,
            # Fundamental data
            "pe": s.pe,
            "pb": s.pb,
            "fundamental_assessment": s.fundamental_assessment,
            "fundamental_ok": s.fundamental_ok,
            # Volume data
            "avg_vol": s.avg_vol,
            "today_vol": s.today_vol,
            "volume_analysis": s.volume_analysis,
            "volume_pattern": s.volume_pattern,
            "volume_description": s.volume_description,
            "vol_ok": s.vol_ok,
            "volume_ratio": s.volume_ratio,
            # Analysis metadata
            "verdict": s.verdict,
            "signals": s.signals,
            "justification": s.justification,
            "timeframe_analysis": s.timeframe_analysis,
            "news_sentiment": s.news_sentiment,
            "candle_analysis": s.candle_analysis,
            "chart_quality": s.chart_quality,
            # Additional analysis fields
            "final_verdict": s.final_verdict,
            "rule_verdict": s.rule_verdict,
            "verdict_source": s.verdict_source,
            "backtest_confidence": s.backtest_confidence,
            "vol_strong": s.vol_strong,
            "is_above_ema200": s.is_above_ema200,
            # Dip buying features
            "dip_depth_from_20d_high_pct": s.dip_depth_from_20d_high_pct,
            "consecutive_red_days": s.consecutive_red_days,
            "dip_speed_pct_per_day": s.dip_speed_pct_per_day,
            "decline_rate_slowing": s.decline_rate_slowing,
            "volume_green_vs_red_ratio": s.volume_green_vs_red_ratio,
            "support_hold_count": s.support_hold_count,
            # Additional metadata
            "liquidity_recommendation": s.liquidity_recommendation,
            "trading_params": s.trading_params,
            # Timestamp
            "ts": s.ts.isoformat(),
        }
        for s in items
    ]
