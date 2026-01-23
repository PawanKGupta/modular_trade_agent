"""Portfolio Calculation Service (Phase 0.3)

Calculates portfolio metrics and creates snapshots for historical tracking.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from src.infrastructure.db.models import PortfolioSnapshot, TradeMode
from src.infrastructure.persistence.pnl_repository import PnlRepository
from src.infrastructure.persistence.portfolio_snapshot_repository import (
    PortfolioSnapshotRepository,
)
from src.infrastructure.persistence.positions_repository import PositionsRepository

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class PortfolioCalculationService:
    """Service for calculating portfolio metrics and creating snapshots"""

    def __init__(self, db: Session):
        self.db = db
        self.snapshot_repo = PortfolioSnapshotRepository(db)
        self.positions_repo = PositionsRepository(db)
        self.pnl_repo = PnlRepository(db)

    def calculate_portfolio_metrics(
        self, user_id: int, snapshot_date: date, trade_mode: TradeMode | None = None
    ) -> dict:
        """
        Calculate portfolio metrics for a specific date.

        Args:
            user_id: User ID
            snapshot_date: Date to calculate metrics for
            trade_mode: Optional trade mode filter (PAPER or BROKER)

        Returns:
            Dictionary with portfolio metrics:
                - total_value: Total portfolio value (cash + holdings)
                - invested_value: Capital invested
                - available_cash: Available cash
                - unrealized_pnl: Unrealized P&L from open positions
                - realized_pnl: Realized P&L (from PnlDaily table)
                - open_positions_count: Number of open positions
                - closed_positions_count: Number of closed positions
                - total_return: Total return percentage
                - daily_return: Daily return percentage
        """
        # Get positions and filter open (as of snapshot_date)
        # Note: For historical snapshots, we need positions that were open on that date
        # For now, we'll use current positions (can be enhanced later for true historical snapshots)
        all_positions = self.positions_repo.list(user_id)
        open_positions = [p for p in all_positions if p.closed_at is None]

        # Filter by trade_mode if provided (requires trade_mode in positions - future enhancement)
        # For now, we'll calculate based on all positions

        # Calculate portfolio value from open positions
        # Note: This requires current prices, which may not be available for historical dates
        # For EOD snapshots, we should use closing prices from that day
        portfolio_value = 0.0
        invested_value = 0.0
        unrealized_pnl = 0.0
        open_positions_count = 0

        for position in open_positions:
            if position.quantity > 0:
                # For historical snapshots, we'd need historical prices
                # For now, use current unrealized_pnl from position
                cost_basis = position.avg_price * position.quantity
                invested_value += cost_basis
                unrealized_pnl += position.unrealized_pnl
                # Estimate market value (cost_basis + unrealized_pnl)
                portfolio_value += cost_basis + position.unrealized_pnl
                open_positions_count += 1

        # Get closed positions count
        closed_positions_count = sum(1 for p in all_positions if p.closed_at is not None)

        # Get realized P&L from PnlDaily table
        pnl_data = self.pnl_repo.range(user_id, snapshot_date, snapshot_date)
        realized_pnl = sum(pnl.realized_pnl for pnl in pnl_data if pnl.realized_pnl) or 0.0

        # Get available cash
        # Note: This requires cash tracking - for now, estimate from initial capital
        # For broker trading, get from broker API
        # For paper trading, get from paper trading store
        available_cash = 0.0  # Placeholder - needs implementation

        total_value = available_cash + portfolio_value

        # Calculate returns
        # Get previous day's snapshot for daily return calculation
        from datetime import timedelta

        prev_date = snapshot_date - timedelta(days=1)
        prev_snapshot = self.snapshot_repo.get_by_date(user_id, prev_date)

        if prev_snapshot:
            prev_total_value = prev_snapshot.total_value
            if prev_total_value > 0:
                daily_return = ((total_value - prev_total_value) / prev_total_value) * 100
            else:
                daily_return = 0.0
        else:
            daily_return = 0.0

        # Calculate total return (requires initial capital - placeholder for now)
        initial_capital = invested_value + available_cash  # Estimate
        if initial_capital > 0:
            total_return = ((total_value - initial_capital) / initial_capital) * 100
        else:
            total_return = 0.0

        return {
            "total_value": total_value,
            "invested_value": invested_value,
            "available_cash": available_cash,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "open_positions_count": open_positions_count,
            "closed_positions_count": closed_positions_count,
            "total_return": total_return,
            "daily_return": daily_return,
        }

    def create_snapshot(
        self,
        user_id: int,
        snapshot_date: date,
        snapshot_type: str = "eod",
        trade_mode: TradeMode | None = None,
    ) -> PortfolioSnapshot:
        """
        Create a portfolio snapshot for a specific date.

        Args:
            user_id: User ID
            snapshot_date: Date for the snapshot
            snapshot_type: Type of snapshot ('eod' or 'intraday')
            trade_mode: Optional trade mode filter

        Returns:
            Created or updated PortfolioSnapshot
        """
        # Calculate metrics
        metrics = self.calculate_portfolio_metrics(user_id, snapshot_date, trade_mode)

        # Create or update snapshot
        snapshot = self.snapshot_repo.upsert_daily(
            user_id=user_id,
            snapshot_date=snapshot_date,
            snapshot_data=metrics,
            snapshot_type=snapshot_type,
        )

        logger.info(
            f"Created portfolio snapshot for user {user_id} on {snapshot_date}: "
            f"total_value={metrics['total_value']:.2f}, "
            f"total_return={metrics['total_return']:.2f}%"
        )

        return snapshot
