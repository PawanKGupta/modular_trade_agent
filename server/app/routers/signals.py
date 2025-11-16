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
    # Map to client shape
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "rsi10": s.rsi10,
            "ema9": s.ema9,
            "ema200": s.ema200,
            "distance_to_ema9": s.distance_to_ema9,
            "clean_chart": s.clean_chart,
            "monthly_support_dist": s.monthly_support_dist,
            "confidence": s.confidence,
            "ts": s.ts.isoformat(),
        }
        for s in items
    ]
