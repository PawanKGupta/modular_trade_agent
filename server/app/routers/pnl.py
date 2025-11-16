from datetime import date, timedelta

# ruff: noqa: B008
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Users
from src.infrastructure.persistence.pnl_repository import PnlRepository

from ..core.deps import get_current_user, get_db
from ..schemas.pnl import DailyPnl, PnlSummary

router = APIRouter()


@router.get("/daily", response_model=list[DailyPnl])
def daily_pnl(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    # default to last 30 days
    end = end or date.today()
    start = start or (end - timedelta(days=30))
    repo = PnlRepository(db)
    records = repo.range(current.id, start, end)
    # realized + unrealized - fees as "pnl" for now
    return [
        DailyPnl(date=r.date, pnl=(r.realized_pnl + r.unrealized_pnl - r.fees)) for r in records
    ]


@router.get("/summary", response_model=PnlSummary)
def pnl_summary(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    end = end or date.today()
    start = start or (end - timedelta(days=30))
    repo = PnlRepository(db)
    records = repo.range(current.id, start, end)
    total = 0.0
    days_green = 0
    days_red = 0
    for r in records:
        pnl = r.realized_pnl + r.unrealized_pnl - r.fees
        total += pnl
        if pnl >= 0:
            days_green += 1
        else:
            days_red += 1
    return PnlSummary(totalPnl=round(total, 2), daysGreen=days_green, daysRed=days_red)
