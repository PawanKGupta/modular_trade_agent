# ruff: noqa: B008
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Signals, SignalStatus
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
    status_filter: str | None = Query(
        "active",
        description="Filter by status: 'active', 'expired', 'traded', 'rejected', or 'all'",
    ),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    repo = SignalsRepository(db, user_id=user.id)
    now = ist_now()
    today = now.date()

    # Parse status filter
    status_enum = None
    if status_filter and status_filter != "all":
        try:
            status_enum = SignalStatus(status_filter.lower())
        except ValueError:
            # Invalid status filter, ignore
            pass

    # Get signals with per-user status applied
    if date_filter == "today":
        base_signals: list[Signals] = repo.by_date(today, limit=limit)
    elif date_filter == "yesterday":
        yesterday = today - timedelta(days=1)
        base_signals = repo.by_date(yesterday, limit=limit)
    elif date_filter == "last_10_days":
        base_signals = repo.last_n_dates(n=10, limit=limit)
    else:
        # Default: recent (no date filter)
        base_signals = repo.recent(limit=limit)

    # Apply per-user status using repository method
    items_with_status = repo.get_signals_with_user_status(
        user_id=user.id,
        limit=limit,
        status_filter=status_enum
    )
    
    # If we already filtered by date, filter the results
    if date_filter:
        base_signal_ids = {s.id for s in base_signals}
        items_with_status = [(s, status) for s, status in items_with_status if s.id in base_signal_ids]
    # Map to client shape with all analysis result fields (use effective status)
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "status": effective_status.value,  # Use per-user status
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
        for s, effective_status in items_with_status
    ]


@router.patch("/signals/{symbol}/reject")
def reject_signal(
    symbol: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Mark a signal as REJECTED - user manually decided not to trade it"""
    repo = SignalsRepository(db, user_id=user.id)
    success = repo.mark_as_rejected(symbol, user_id=user.id)

    if not success:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active signal found for symbol: {symbol}",
        )

    return {
        "message": f"Signal for {symbol} marked as REJECTED",
        "symbol": symbol,
        "status": "rejected",
    }
