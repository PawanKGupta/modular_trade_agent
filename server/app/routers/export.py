"""Export API router (Phase 0.7 + Phase 3.1)"""

import csv
import io
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.infrastructure.db.models import Orders, Positions, Signals, TradeMode, Users
from src.infrastructure.persistence.export_job_repository import ExportJobRepository
from src.infrastructure.persistence.pnl_repository import PnlRepository
from src.infrastructure.persistence.positions_repository import PositionsRepository

from ..core.deps import get_current_user, get_db

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/jobs", response_model=list[dict])
def list_export_jobs(
    status: str | None = Query(default=None, description="Filter by status"),
    data_type: str | None = Query(default=None, description="Filter by data type"),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of jobs to return"),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    List export jobs for the current user (Phase 0.7).

    Returns list of export job records showing status, progress, and results.
    """
    try:
        job_repo = ExportJobRepository(db)

        # Get jobs filtered by status if provided
        if status:
            jobs = job_repo.get_by_user(current.id, status=status, limit=limit)
        else:
            jobs = job_repo.get_by_user(current.id, limit=limit)

        # Filter by data_type if provided
        if data_type:
            jobs = [job for job in jobs if job.data_type == data_type]

        # Convert to dict for response
        return [
            {
                "id": job.id,
                "export_type": job.export_type,
                "data_type": job.data_type,
                "date_range_start": (
                    job.date_range_start.isoformat() if job.date_range_start else None
                ),
                "date_range_end": job.date_range_end.isoformat() if job.date_range_end else None,
                "status": job.status,
                "progress": job.progress,
                "file_path": job.file_path,
                "file_size": job.file_size,
                "records_exported": job.records_exported,
                "duration_seconds": job.duration_seconds,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
            for job in jobs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch export jobs: {str(e)}") from e


@router.get("/jobs/{job_id}", response_model=dict)
def get_export_job(
    job_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Get details of a specific export job (Phase 0.7).

    Returns full details of the export job including status, progress, and results.
    """
    try:
        job_repo = ExportJobRepository(db)
        job = job_repo.get_by_id(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Export job not found")

        # Verify job belongs to current user
        if job.user_id != current.id:
            raise HTTPException(status_code=403, detail="Access denied")

        return {
            "id": job.id,
            "export_type": job.export_type,
            "data_type": job.data_type,
            "date_range_start": job.date_range_start.isoformat() if job.date_range_start else None,
            "date_range_end": job.date_range_end.isoformat() if job.date_range_end else None,
            "status": job.status,
            "progress": job.progress,
            "file_path": job.file_path,
            "file_size": job.file_size,
            "records_exported": job.records_exported,
            "duration_seconds": job.duration_seconds,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch export job: {str(e)}") from e


# Phase 3.1: CSV Export Endpoints


@router.get("/pnl/csv")
def export_pnl_csv(
    start_date: date | None = Query(default=None, description="Start date for export (YYYY-MM-DD)"),
    end_date: date | None = Query(default=None, description="End date for export (YYYY-MM-DD)"),
    include_unrealized: bool = Query(default=True, description="Include unrealized P&L in totals"),
    trade_mode: TradeMode = Query(default=TradeMode.PAPER, description="Trading mode"),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Export P&L data as CSV (Phase 3.1).

    Returns CSV file with daily P&L records including realized/unrealized P&L, fees, and total.
    """
    try:
        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Fetch P&L data
        pnl_repo = PnlRepository(db)
        pnl_records = pnl_repo.range(
            user_id=current.id,
            start=start_date,
            end=end_date,
        )

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "date",
                "realized_pnl",
                "unrealized_pnl",
                "fees",
                "total_pnl",
                "trade_mode",
            ],
        )
        writer.writeheader()

        for record in pnl_records:
            total_pnl = (
                record.realized_pnl
                + (record.unrealized_pnl if include_unrealized else 0)
                - record.fees
            )
            writer.writerow(
                {
                    "date": record.date.isoformat(),
                    "realized_pnl": f"{record.realized_pnl:.2f}",
                    "unrealized_pnl": f"{record.unrealized_pnl:.2f}",
                    "fees": f"{record.fees:.2f}",
                    "total_pnl": f"{total_pnl:.2f}",
                    "trade_mode": trade_mode.value,
                }
            )

        # Prepare response
        output.seek(0)
        filename = f"pnl_{trade_mode.value}_{start_date}_{end_date}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error(f"Failed to export P&L CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export P&L data: {str(e)}") from e


@router.get("/trades/csv")
def export_trades_csv(
    start_date: date | None = Query(default=None, description="Start date for export (YYYY-MM-DD)"),
    end_date: date | None = Query(default=None, description="End date for export (YYYY-MM-DD)"),
    trade_mode: TradeMode = Query(default=TradeMode.PAPER, description="Trading mode"),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Export closed trades/positions as CSV (Phase 3.1).

    Returns CSV file with trade history including entry/exit prices, P&L, and holding periods.
    """
    try:
        # Default to last 90 days if no dates provided
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=90)

        # Fetch closed positions
        closed_positions = (
            db.query(Positions)
            .filter(
                Positions.user_id == current.id,
                Positions.closed_at.isnot(None),
                func.date(Positions.closed_at) >= start_date,
                func.date(Positions.closed_at) <= end_date,
            )
            .order_by(Positions.closed_at.desc())
            .all()
        )

        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "symbol",
                "entry_date",
                "exit_date",
                "quantity",
                "entry_price",
                "exit_price",
                "realized_pnl",
                "pnl_percentage",
                "fees",
                "holding_days",
                "trade_mode",
            ],
        )
        writer.writeheader()

        for pos in closed_positions:
            holding_days = (
                (pos.closed_at.date() - pos.opened_at.date()).days
                if pos.closed_at and pos.opened_at
                else 0
            )
            pnl_pct = (
                ((pos.exit_price / pos.avg_price) - 1) * 100
                if pos.avg_price and pos.exit_price
                else 0
            )

            writer.writerow(
                    {
                        "symbol": pos.symbol,
                        "entry_date": pos.opened_at.isoformat() if pos.opened_at else "",
                        "exit_date": pos.closed_at.isoformat() if pos.closed_at else "",
                    "quantity": pos.quantity,
                    "entry_price": f"{pos.avg_price:.2f}" if pos.avg_price else "",
                    "exit_price": f"{pos.exit_price:.2f}" if pos.exit_price else "",
                    "realized_pnl": f"{pos.realized_pnl:.2f}" if pos.realized_pnl else "0.00",
                    "pnl_percentage": f"{pnl_pct:.2f}",
                        "fees": "0.00",
                    "holding_days": holding_days,
                        "trade_mode": trade_mode.value,
                }
            )

        output.seek(0)
        filename = f"trades_{trade_mode.value}_{start_date}_{end_date}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error(f"Failed to export trades CSV: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to export trade history: {str(e)}"
        ) from e


@router.get("/signals/csv")
def export_signals_csv(
    start_date: date | None = Query(default=None, description="Start date for export (YYYY-MM-DD)"),
    end_date: date | None = Query(default=None, description="End date for export (YYYY-MM-DD)"),
    verdict: str | None = Query(default=None, description="Filter by verdict"),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Export signals/buying zone data as CSV (Phase 3.1).

    Returns CSV file with signals including buy range, target, stop loss, justifications, and indicators.
    """
    try:
        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Fetch signals (date-based filter to avoid tz issues)
        query = db.query(Signals).filter(
            func.date(Signals.ts) >= start_date,
            func.date(Signals.ts) <= end_date,
        )

        if verdict:
            query = query.filter(Signals.verdict == verdict)

        signals = query.order_by(Signals.ts.desc()).all()

        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "symbol",
                "created_at",
                "verdict",
                "buy_range_low",
                "buy_range_high",
                "target",
                "stop_loss",
                "last_close",
                "rsi",
                "signals",
                "justification",
                "ml_verdict",
                "ml_confidence",
            ],
        )
        writer.writeheader()

        for signal in signals:
            # Parse buy_range if it's a string
            buy_range_low = buy_range_high = ""
            if signal.buy_range:
                if isinstance(signal.buy_range, (list, tuple)) and len(signal.buy_range) >= 2:
                    buy_range_low = f"{signal.buy_range[0]:.2f}"
                    buy_range_high = f"{signal.buy_range[1]:.2f}"
                elif isinstance(signal.buy_range, dict):
                    low = signal.buy_range.get("low") or signal.buy_range.get("min")
                    high = signal.buy_range.get("high") or signal.buy_range.get("max")
                    if low is not None:
                        buy_range_low = f"{float(low):.2f}"
                    if high is not None:
                        buy_range_high = f"{float(high):.2f}"

            writer.writerow(
                {
                    "symbol": signal.symbol,
                    "created_at": signal.ts.isoformat() if signal.ts else "",
                    "verdict": signal.verdict or "",
                    "buy_range_low": buy_range_low,
                    "buy_range_high": buy_range_high,
                    "target": f"{signal.target:.2f}" if signal.target else "",
                    "stop_loss": f"{signal.stop:.2f}" if signal.stop else "",
                    "last_close": f"{signal.last_close:.2f}" if signal.last_close else "",
                    "rsi": f"{signal.rsi10:.2f}" if getattr(signal, "rsi10", None) else "",
                    "signals": ", ".join(signal.signals) if signal.signals else "",
                    "justification": (
                        ", ".join(signal.justification) if signal.justification else ""
                    ),
                    "ml_verdict": signal.ml_verdict or "",
                    "ml_confidence": f"{signal.ml_confidence:.2f}" if signal.ml_confidence else "",
                }
            )

        output.seek(0)
        filename = f"signals_{start_date}_{end_date}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error(f"Failed to export signals CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export signals: {str(e)}") from e


@router.get("/orders/csv")
def export_orders_csv(
    start_date: date | None = Query(default=None, description="Start date for export (YYYY-MM-DD)"),
    end_date: date | None = Query(default=None, description="End date for export (YYYY-MM-DD)"),
    status: str | None = Query(default=None, description="Filter by order status"),
    trade_mode: TradeMode = Query(default=TradeMode.PAPER, description="Trading mode"),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Export orders as CSV (Phase 3.1).

    Returns CSV file with order details including status, prices, quantities, fills, and timestamps.
    """
    try:
        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Fetch orders (date-based filter to avoid tz issues)
        query = db.query(Orders).filter(
            Orders.user_id == current.id,
            Orders.trade_mode == trade_mode,
            func.date(Orders.placed_at) >= start_date,
            func.date(Orders.placed_at) <= end_date,
        )

        if status:
            query = query.filter(Orders.status == status)

        orders = query.order_by(Orders.placed_at.desc()).all()

        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "order_id",
                "symbol",
                "side",
                "order_type",
                "status",
                "quantity",
                "filled_quantity",
                "price",
                "average_price",
                "placed_at",
                "updated_at",
                "trade_mode",
            ],
        )
        writer.writeheader()

        for order in orders:
            writer.writerow(
                {
                    "order_id": order.order_id or order.id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "order_type": order.order_type,
                    "status": order.status,
                    "quantity": order.quantity,
                    "filled_quantity": order.execution_qty or 0,
                    "price": f"{order.price:.2f}" if order.price else "",
                    "average_price": f"{order.avg_price:.2f}" if order.avg_price else "",
                    "placed_at": order.placed_at.isoformat() if order.placed_at else "",
                    "updated_at": order.updated_at.isoformat() if order.updated_at else "",
                    "trade_mode": order.trade_mode.value,
                }
            )

        output.seek(0)
        filename = f"orders_{trade_mode.value}_{start_date}_{end_date}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error(f"Failed to export orders CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export orders: {str(e)}") from e


@router.get("/portfolio/csv")
def export_portfolio_csv(
    trade_mode: TradeMode = Query(default=TradeMode.PAPER, description="Trading mode"),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Export current portfolio holdings as CSV (Phase 3.1).

    Returns CSV file with current positions including entry prices, current values, P&L, and allocation.
    """
    try:
        # Fetch open positions
        positions_repo = PositionsRepository(db)
        open_positions = (
            db.query(positions_repo.model)
            .filter(
                positions_repo.model.user_id == current.id,
                positions_repo.model.closed_at.is_(None),
            )
            .order_by(positions_repo.model.symbol)
            .all()
        )

        # Calculate total portfolio value for allocation percentages
        total_value = sum(
            pos.quantity * (pos.current_price or pos.entry_price or 0) for pos in open_positions
        )

        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "symbol",
                "quantity",
                "entry_price",
                "current_price",
                "entry_value",
                "current_value",
                "unrealized_pnl",
                "unrealized_pnl_pct",
                "allocation_pct",
                "entry_date",
                "holding_days",
                "trade_mode",
            ],
        )
        writer.writeheader()

        for pos in open_positions:
            # Positions model does not store current_price; use avg_price as proxy
            current_price = pos.avg_price or 0
            entry_value = pos.quantity * (pos.avg_price or 0)
            current_value = pos.quantity * current_price
            unrealized_pnl = current_value - entry_value
            unrealized_pnl_pct = (
                (((current_price / pos.avg_price) - 1) * 100) if pos.avg_price else 0
            )
            allocation_pct = (current_value / total_value * 100) if total_value > 0 else 0
            holding_days = ((date.today() - pos.opened_at.date()).days) if pos.opened_at else 0

            writer.writerow(
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "entry_price": f"{pos.avg_price:.2f}" if pos.avg_price else "",
                    "current_price": f"{current_price:.2f}",
                    "entry_value": f"{entry_value:.2f}",
                    "current_value": f"{current_value:.2f}",
                    "unrealized_pnl": f"{unrealized_pnl:.2f}",
                    "unrealized_pnl_pct": f"{unrealized_pnl_pct:.2f}",
                    "allocation_pct": f"{allocation_pct:.2f}",
                    "entry_date": pos.opened_at.isoformat() if pos.opened_at else "",
                    "holding_days": holding_days,
                    "trade_mode": trade_mode.value,
                }
            )

        output.seek(0)
        filename = f"portfolio_{trade_mode.value}_{date.today()}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error(f"Failed to export portfolio CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export portfolio: {str(e)}") from e
