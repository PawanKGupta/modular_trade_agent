from datetime import date, timedelta

# ruff: noqa: B008
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.infrastructure.db.models import PnlCalculationAudit, Users
from src.infrastructure.persistence.pnl_audit_repository import PnlAuditRepository
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


@router.get("/audit-history", response_model=list[dict])
def audit_history(
    limit: int = Query(default=50, ge=1, le=500),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Get P&L calculation audit history for the current user (Phase 0.5).

    Returns list of calculation audit records showing when calculations were run,
    their status, performance metrics, and results.
    """
    try:
        audit_repo = PnlAuditRepository(db)

        if status:
            audits = audit_repo.get_by_status(current.id, status, limit=limit)
        else:
            audits = audit_repo.get_by_user(current.id, limit=limit)

        # Convert to dict for response
        return [
            {
                "id": audit.id,
                "calculation_type": audit.calculation_type,
                "date_range_start": audit.date_range_start.isoformat()
                if audit.date_range_start
                else None,
                "date_range_end": audit.date_range_end.isoformat()
                if audit.date_range_end
                else None,
                "positions_processed": audit.positions_processed,
                "orders_processed": audit.orders_processed,
                "pnl_records_created": audit.pnl_records_created,
                "pnl_records_updated": audit.pnl_records_updated,
                "duration_seconds": audit.duration_seconds,
                "status": audit.status,
                "error_message": audit.error_message,
                "triggered_by": audit.triggered_by,
                "created_at": audit.created_at.isoformat(),
            }
            for audit in audits
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit history: {str(e)}") from e
