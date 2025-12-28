"""
PnL Calculation Service

Calculates daily P&L from positions and orders, populating the pnl_daily table.
Supports both paper trading and broker trading modes.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Orders, PnlDaily, Positions, TradeMode
from src.infrastructure.persistence.orders_repository import OrdersRepository
from src.infrastructure.persistence.pnl_repository import PnlRepository
from src.infrastructure.persistence.positions_repository import PositionsRepository

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class PnlCalculationService:
    """Service for calculating and populating P&L data"""

    # Fee estimation: 0.1% per transaction (buy + sell = 0.2% total)
    DEFAULT_FEE_RATE = 0.001  # 0.1%

    def __init__(self, db: Session):
        self.db = db
        self.positions_repo = PositionsRepository(db)
        self.orders_repo = OrdersRepository(db)
        self.pnl_repo = PnlRepository(db)

    def calculate_realized_pnl(
        self, user_id: int, trade_mode: TradeMode | None = None, target_date: date | None = None
    ) -> dict[date, float]:
        """
        Calculate realized P&L from closed positions.

        Args:
            user_id: User ID
            trade_mode: Filter by trade mode (PAPER or BROKER). If None, includes all.
            target_date: If provided, only calculate for positions closed on this date.
                         If None, calculates for all closed positions.

        Returns:
            Dictionary mapping date -> realized P&L amount
        """
        # Query closed positions
        stmt = select(Positions).where(
            Positions.user_id == user_id,
            Positions.closed_at.isnot(None),
        )

        if target_date:
            # Filter by closed_at date (using date() function for date comparison)
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())
            stmt = stmt.where(
                Positions.closed_at >= start_datetime,
                Positions.closed_at <= end_datetime,
            )

        positions = list(self.db.execute(stmt).scalars().all())

        # Group by date and sum realized P&L
        realized_by_date: dict[date, float] = defaultdict(float)

        for pos in positions:
            # Filter by trade mode if specified
            if trade_mode:
                # Get the buy order to check trade_mode
                buy_order = self._get_buy_order_for_position(user_id, pos.symbol, pos.opened_at)
                if not buy_order or buy_order.trade_mode != trade_mode:
                    continue

            # Use realized_pnl from position if available (Phase 0.2)
            # This is the most accurate as it's calculated when the position is closed
            if pos.realized_pnl is not None:
                pnl = pos.realized_pnl
            elif pos.exit_price is not None and pos.avg_price is not None:
                # Fallback: Calculate from exit_price and avg_price
                # Get quantity from sell order if available, otherwise use a default
                # Note: pos.quantity is 0 when closed, so we need to get it from the sell order
                sold_quantity = 0.0
                if pos.sell_order_id:
                    sell_order = self.orders_repo.get(pos.sell_order_id)
                    if sell_order:
                        sold_quantity = sell_order.quantity or 0.0

                # If we still don't have quantity, we can't calculate accurately
                if sold_quantity == 0:
                    logger.warning(
                        f"Position {pos.id} closed but no quantity available. "
                        f"realized_pnl={pos.realized_pnl}, exit_price={pos.exit_price}, "
                        f"sell_order_id={pos.sell_order_id}. Skipping."
                    )
                    continue

                # Calculate: (exit_price - avg_price) * quantity_sold
                pnl = (pos.exit_price - pos.avg_price) * sold_quantity
            else:
                logger.warning(
                    f"Position {pos.id} closed but no realized_pnl or exit_price. Skipping."
                )
                continue

            # Get the date from closed_at
            closed_date = pos.closed_at.date() if pos.closed_at else date.today()
            realized_by_date[closed_date] += pnl

        return dict(realized_by_date)

    def calculate_unrealized_pnl(
        self,
        user_id: int,
        trade_mode: TradeMode | None = None,
        target_date: date | None = None,
    ) -> dict[date, float]:
        """
        Calculate unrealized P&L from open positions.

        Args:
            user_id: User ID
            trade_mode: Filter by trade mode (PAPER or BROKER). If None, includes all.
            target_date: If provided, calculate as of this date (for historical snapshots).
                         If None, uses current date and current prices.

        Returns:
            Dictionary mapping date -> unrealized P&L amount
        """
        # Query open positions
        stmt = select(Positions).where(
            Positions.user_id == user_id,
            Positions.closed_at.is_(None),
        )

        positions = list(self.db.execute(stmt).scalars().all())

        # Group by date and sum unrealized P&L
        unrealized_by_date: dict[date, float] = defaultdict(float)
        calculation_date = target_date or date.today()

        for pos in positions:
            # Filter by trade mode if specified
            if trade_mode:
                buy_order = self._get_buy_order_for_position(user_id, pos.symbol, pos.opened_at)
                if not buy_order or buy_order.trade_mode != trade_mode:
                    continue

            # Use current price from position if available, otherwise estimate
            # For now, we'll use the unrealized_pnl field if available
            # TODO: Fetch current price from broker API or yfinance for accurate calculation
            if pos.unrealized_pnl is not None:
                pnl = pos.unrealized_pnl
            else:
                # Fallback: Use avg_price as current price (0 unrealized P&L)
                # This is a placeholder until we integrate price fetching
                logger.warning(f"Position {pos.id} has no unrealized_pnl. Using 0 as placeholder.")
                pnl = 0.0

            unrealized_by_date[calculation_date] += pnl

        return dict(unrealized_by_date)

    def calculate_fees(
        self, user_id: int, trade_mode: TradeMode | None = None, target_date: date | None = None
    ) -> dict[date, float]:
        """
        Calculate fees from orders.

        Args:
            user_id: User ID
            trade_mode: Filter by trade mode (PAPER or BROKER). If None, includes all.
            target_date: If provided, only calculate for orders on this date.
                         If None, calculates for all orders.

        Returns:
            Dictionary mapping date -> total fees
        """
        # Query orders directly and apply optional filters
        stmt = select(Orders).where(Orders.user_id == user_id)
        if trade_mode:
            stmt = stmt.where(Orders.trade_mode == trade_mode)
        if target_date:
            # Date-based filter to avoid timezone mismatches
            stmt = stmt.where(func.date(Orders.placed_at) == target_date)

        orders = list(self.db.execute(stmt).scalars().all())

        fees_by_date: dict[date, float] = defaultdict(float)

        for order in orders:
            # Calculate fee: 0.1% of order value
            # Use avg_price if filled, otherwise use price
            order_value = (order.avg_price or order.price or 0) * (order.quantity or 0)
            fee = order_value * self.DEFAULT_FEE_RATE
            order_date = order.placed_at.date() if order.placed_at else target_date or date.today()
            fees_by_date[order_date] += fee

        return dict(fees_by_date)

    def calculate_daily_pnl(
        self,
        user_id: int,
        target_date: date,
        trade_mode: TradeMode | None = None,
    ) -> PnlDaily:
        """
        Calculate P&L for a specific date and upsert into pnl_daily table.

        Args:
            user_id: User ID
            target_date: Date to calculate P&L for
            trade_mode: Filter by trade mode (PAPER or BROKER). If None, includes all.

        Returns:
            PnlDaily record
        """
        # Calculate components
        realized = self.calculate_realized_pnl(user_id, trade_mode, target_date)
        unrealized = self.calculate_unrealized_pnl(user_id, trade_mode, target_date)
        fees = self.calculate_fees(user_id, trade_mode, target_date)

        # Get values for target_date (default to 0 if not found)
        realized_pnl = realized.get(target_date, 0.0)
        unrealized_pnl = unrealized.get(target_date, 0.0)
        fees_amount = fees.get(target_date, 0.0)

        # Create or update PnlDaily record
        pnl_record = PnlDaily(
            user_id=user_id,
            date=target_date,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            fees=fees_amount,
        )

        return self.pnl_repo.upsert(pnl_record)

    def calculate_date_range(
        self,
        user_id: int,
        start_date: date,
        end_date: date,
        trade_mode: TradeMode | None = None,
    ) -> list[PnlDaily]:
        """
        Calculate P&L for a date range and upsert into pnl_daily table.

        Args:
            user_id: User ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            trade_mode: Filter by trade mode (PAPER or BROKER). If None, includes all.

        Returns:
            List of PnlDaily records
        """
        records = []
        current_date = start_date

        while current_date <= end_date:
            record = self.calculate_daily_pnl(user_id, current_date, trade_mode)
            records.append(record)
            current_date += timedelta(days=1)

        return records

    def _get_buy_order_for_position(
        self, user_id: int, symbol: str, opened_at: datetime | None
    ) -> Orders | None:
        """
        Get the buy order that opened a position.

        This is a helper method to determine the trade_mode of a position.
        """
        if not opened_at:
            return None

        # Find buy orders for this symbol around the opened_at time
        orders = self.orders_repo.list(user_id)
        for order in orders:
            if (
                order.symbol == symbol
                and order.side == "buy"
                and order.placed_at
                and abs((order.placed_at - opened_at).total_seconds()) < 3600  # Within 1 hour
            ):
                return order

        return None
