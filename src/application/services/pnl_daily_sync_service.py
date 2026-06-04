"""Keep ``pnldaily`` aligned with closed broker positions (billing + PnL UI source)."""

from __future__ import annotations

import logging
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import PnlDaily, Positions
from src.infrastructure.persistence.pnl_repository import PnlRepository

logger = logging.getLogger(__name__)


class PnlDailySyncService:
    """Materialize realized PnL into ``pnldaily`` from closed positions."""

    def __init__(self, db: Session):
        self.db = db
        self._pnl_repo = PnlRepository(db)

    def record_position_close(
        self,
        user_id: int,
        closed_at: datetime,
        realized_pnl: float,
    ) -> None:
        """Increment ``pnldaily.realized_pnl`` for the position's close date."""
        if realized_pnl is None:
            return
        day = closed_at.date()
        existing = self.db.execute(
            select(PnlDaily).where(PnlDaily.user_id == user_id, PnlDaily.date == day)
        ).scalar_one_or_none()
        amount = float(realized_pnl)
        if existing:
            existing.realized_pnl = float(existing.realized_pnl or 0.0) + amount
            self.db.commit()
            self.db.refresh(existing)
            return
        self._pnl_repo.upsert(
            PnlDaily(
                user_id=user_id,
                date=day,
                realized_pnl=amount,
                unrealized_pnl=0.0,
                fees=0.0,
            )
        )

    def materialize_calendar_month(self, user_id: int, year: int, month: int) -> float:
        """
        Rebuild ``pnldaily`` realized totals for each close day in the month from
        ``positions`` (source of truth) and return the month sum.
        """
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end, datetime.max.time())

        positions = list(
            self.db.execute(
                select(Positions).where(
                    Positions.user_id == user_id,
                    Positions.closed_at.isnot(None),
                    Positions.closed_at >= start_dt,
                    Positions.closed_at <= end_dt,
                    Positions.realized_pnl.isnot(None),
                )
            ).scalars()
        )

        by_date: dict[date, float] = defaultdict(float)
        for pos in positions:
            closed_at = pos.closed_at
            if closed_at is None:
                continue
            by_date[closed_at.date()] += float(pos.realized_pnl)

        existing_rows = list(
            self.db.execute(
                select(PnlDaily).where(
                    PnlDaily.user_id == user_id,
                    PnlDaily.date >= start,
                    PnlDaily.date <= end,
                )
            ).scalars()
        )

        dirty = False
        for day, amount in by_date.items():
            existing = self.db.execute(
                select(PnlDaily).where(PnlDaily.user_id == user_id, PnlDaily.date == day)
            ).scalar_one_or_none()
            if existing:
                existing.realized_pnl = amount
            else:
                self.db.add(
                    PnlDaily(
                        user_id=user_id,
                        date=day,
                        realized_pnl=amount,
                        unrealized_pnl=0.0,
                        fees=0.0,
                    )
                )
            dirty = True

        for row in existing_rows:
            if row.date not in by_date and float(row.realized_pnl or 0.0) != 0.0:
                row.realized_pnl = 0.0
                dirty = True

        if dirty:
            self.db.commit()

        month_total = sum(by_date.values())
        logger.info(
            "Materialized pnldaily for user %s %04d-%02d from %d closed position(s): total=%.4f",
            user_id,
            year,
            month,
            len(positions),
            month_total,
        )
        return float(month_total)
