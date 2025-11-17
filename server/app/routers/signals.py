# ruff: noqa: B008
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Signals
from src.infrastructure.persistence.signals_repository import SignalsRepository

from ..core.deps import get_current_user, get_db

router = APIRouter()


@router.get("/buying-zone")
def buying_zone(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    repo = SignalsRepository(db)
    items: list[Signals] = repo.recent(limit=limit)
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
            # Timestamp
            "ts": s.ts.isoformat(),
        }
        for s in items
    ]
