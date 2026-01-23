from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.infrastructure.db.models import TradeMode, Users

from ..core.deps import get_current_user, get_db
from ..services.pdf_generator import PdfGenerator

router = APIRouter()


@router.get("/pnl/pdf")
def generate_pnl_pdf(
    period: str = Query(
        default="custom",
        description="Report period: daily|weekly|monthly|custom",
        regex="^(daily|weekly|monthly|custom)$",
    ),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    include_unrealized: bool = Query(default=True),
    trade_mode: TradeMode = Query(default=TradeMode.PAPER),
    db: Session = Depends(get_db),  # noqa: B008
    current: Users = Depends(get_current_user),  # noqa: B008
):
    """
    Generate a P&L PDF report for the given range or preset period.
    Returns a streamed PDF response.
    """
    try:
        today = date.today()
        if period != "custom":
            if period == "daily":
                start_date = today
                end_date = today
            elif period == "weekly":
                start_date = today - timedelta(days=6)
                end_date = today
            elif period == "monthly":
                start_date = today - timedelta(days=29)
                end_date = today
        else:
            if not end_date:
                end_date = today
            if not start_date:
                start_date = end_date - timedelta(days=30)

        generator = PdfGenerator()
        pdf_bytes = generator.generate_pnl_report(
            db=db,
            user_id=current.id,
            trade_mode=trade_mode,
            start_date=start_date,
            end_date=end_date,
            include_unrealized=include_unrealized,
        )

        filename = f"pnl_report_{trade_mode.value}_{start_date}_{end_date}.pdf"
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {e}") from e
