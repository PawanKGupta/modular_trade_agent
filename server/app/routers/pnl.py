from datetime import date, timedelta

# ruff: noqa: B008
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.infrastructure.db.models import PnlCalculationAudit, TradeMode, Users
from src.infrastructure.persistence.pnl_audit_repository import PnlAuditRepository
from src.infrastructure.persistence.pnl_repository import PnlRepository

from ..core.deps import get_current_user, get_db
from ..schemas.pnl import DailyPnl, PnlSummary
from ..services.pnl_calculation_service import PnlCalculationService

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


@router.post("/calculate")
def calculate_pnl(
    target_date: date | None = Query(default=None),
    trade_mode: str | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Trigger on-demand P&L calculation for a specific date or today.

    Args:
        target_date: Date to calculate P&L for (defaults to today)
        trade_mode: Filter by trade mode ('paper' or 'broker'). If None, includes all.

    Returns:
        Calculated PnlDaily record
    """
    try:
        service = PnlCalculationService(db)
        calculation_date = target_date or date.today()

        # Parse trade_mode if provided
        mode = None
        if trade_mode:
            try:
                mode = TradeMode(trade_mode.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid trade_mode: {trade_mode}. Must be 'paper' or 'broker'"
                ) from None

        record = service.calculate_daily_pnl(current.id, calculation_date, mode)

        return {
            "date": record.date.isoformat(),
            "realized_pnl": record.realized_pnl,
            "unrealized_pnl": record.unrealized_pnl,
            "fees": record.fees,
            "total_pnl": record.realized_pnl + record.unrealized_pnl - record.fees,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate P&L: {str(e)}") from e


@router.post("/backfill")
def backfill_pnl(
    start_date: date = Query(...),
    end_date: date = Query(...),
    trade_mode: str | None = Query(default=None),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Backfill historical P&L data for a date range.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        trade_mode: Filter by trade mode ('paper' or 'broker'). If None, includes all.

    Returns:
        Summary of backfill operation
    """
    try:
        # Validate date range
        if start_date > end_date:
            raise HTTPException(status_code=400, detail="start_date must be <= end_date")

        # Limit to 1 year at a time to prevent long-running operations
        max_days = 365
        if (end_date - start_date).days > max_days:
            raise HTTPException(
                status_code=400,
                detail=f"Date range cannot exceed {max_days} days. Please split into smaller ranges.",
            )

        service = PnlCalculationService(db)

        # Parse trade_mode if provided
        mode = None
        if trade_mode:
            try:
                mode = TradeMode(trade_mode.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid trade_mode: {trade_mode}. Must be 'paper' or 'broker'"
                ) from None

        records = service.calculate_date_range(current.id, start_date, end_date, mode)

        return {
            "message": "Backfill completed successfully",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "records_created": len(records),
            "trade_mode": trade_mode,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to backfill P&L: {str(e)}") from e
