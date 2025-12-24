from __future__ import annotations

import builtins
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Positions
from src.infrastructure.db.timezone_utils import ist_now

try:
    from utils.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class PositionsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_symbol(self, user_id: int, symbol: str) -> Positions | None:
        """
        Get the most recent open position by symbol.

        Returns only open positions (closed_at IS NULL) to support multiple positions per symbol.
        For closed positions, use get_by_symbol_any(include_closed=True).

        Args:
            user_id: User ID
            symbol: Full trading symbol (e.g., "RELIANCE-EQ", "SALSTEEL-BE")

        Returns:
            Most recent open position, or None if not found
        """
        stmt = (
            select(Positions)
            .where(
                Positions.user_id == user_id,
                Positions.symbol == symbol,
                Positions.closed_at.is_(None),
            )
            .order_by(Positions.opened_at.desc())
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_symbol_for_update(self, user_id: int, symbol: str) -> Positions | None:
        """
        Get the most recent open position by symbol with row-level lock (SELECT ... FOR UPDATE).

        This prevents concurrent modifications by locking the row until the transaction commits.
        Use this when you need to read and then update a position to prevent race conditions.

        Returns only open positions (closed_at IS NULL) to support multiple positions per symbol.

        Args:
            user_id: User ID
            symbol: Full trading symbol (e.g., "RELIANCE-EQ", "SALSTEEL-BE")

        Returns:
            Positions object with row lock, or None if not found
        """
        stmt = (
            select(Positions)
            .where(
                Positions.user_id == user_id,
                Positions.symbol == symbol,
                Positions.closed_at.is_(None),
            )
            .order_by(Positions.opened_at.desc())
            .with_for_update()
            .limit(1)
        )
        result = self.db.execute(stmt).first()
        return result[0] if result else None

    def get_by_symbol_any(
        self, user_id: int, symbol: str, include_closed: bool = False
    ) -> Positions | None:
        """
        Get any position by symbol (open or closed).

        Use this when you need to check if a position exists regardless of closed status.
        For normal operations, use get_by_symbol() which returns only open positions.

        Args:
            user_id: User ID
            symbol: Full trading symbol (e.g., "RELIANCE-EQ", "SALSTEEL-BE")
            include_closed: If True, returns closed positions. If False, same as get_by_symbol().

        Returns:
            Most recent position (open or closed based on include_closed), or None if not found
        """
        stmt = (
            select(Positions)
            .where(Positions.user_id == user_id, Positions.symbol == symbol)
            .order_by(Positions.opened_at.desc())
        )
        if not include_closed:
            stmt = stmt.where(Positions.closed_at.is_(None))
        # Use first() instead of scalar_one_or_none() to handle multiple rows
        # (returns most recent based on order_by)
        result = self.db.execute(stmt).first()
        return result[0] if result else None

    def list(self, user_id: int) -> builtins.list[Positions]:
        stmt = (
            select(Positions)
            .where(Positions.user_id == user_id)
            .order_by(Positions.opened_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def upsert(
        self,
        *,
        user_id: int,
        symbol: str,
        quantity: float,
        avg_price: float,
        opened_at: datetime | None = None,
        reentry_count: int | None = None,
        reentries: dict | None = None,
        initial_entry_price: float | None = None,
        last_reentry_price: float | None = None,
        entry_rsi: float | None = None,
        auto_commit: bool = True,
    ) -> Positions:
        # Use FOR UPDATE lock when updating existing position to prevent race conditions
        # This ensures atomic read-modify-write operations
        # get_by_symbol_for_update() now returns only open positions
        pos = self.get_by_symbol_for_update(user_id, symbol)

        # Application-level validation: Prevent duplicate open positions
        # (Database-level partial unique index handles this for PostgreSQL,
        # but we validate here for SQLite compatibility)
        if pos and pos.closed_at is not None:
            # This shouldn't happen since get_by_symbol_for_update filters closed_at,
            # but defensive check in case of race condition
            logger.warning(f"Found closed position for {symbol}, creating new position instead")
            pos = None

        if pos:
            pos.quantity = quantity
            pos.avg_price = avg_price
            if reentry_count is not None:
                pos.reentry_count = reentry_count
            if reentries is not None:
                pos.reentries = reentries
            if last_reentry_price is not None:
                pos.last_reentry_price = last_reentry_price
            # Only update entry_rsi if it's not already set (preserve original entry RSI)
            if entry_rsi is not None and pos.entry_rsi is None:
                pos.entry_rsi = entry_rsi
        else:
            # New position - set initial_entry_price if provided, otherwise use avg_price
            initial_price = initial_entry_price if initial_entry_price is not None else avg_price
            pos = Positions(
                user_id=user_id,
                symbol=symbol,
                quantity=quantity,
                avg_price=avg_price,
                unrealized_pnl=0.0,
                opened_at=opened_at or ist_now(),
                reentry_count=reentry_count or 0,
                reentries=reentries,
                initial_entry_price=initial_price,
                last_reentry_price=last_reentry_price,
                entry_rsi=entry_rsi,
            )
            self.db.add(pos)
        if auto_commit:
            self.db.commit()
            self.db.refresh(pos)
        return pos

    def count_open(self, user_id: int) -> int:
        """Count open positions for a user"""
        stmt = select(Positions).where(Positions.user_id == user_id, Positions.closed_at.is_(None))
        return len(list(self.db.execute(stmt).scalars().all()))

    def bulk_create(self, positions: list[dict]) -> list[Positions]:
        """Bulk create positions (for migration)"""
        created_positions = []
        for pos_data in positions:
            position = Positions(**pos_data)
            self.db.add(position)
            created_positions.append(position)
        self.db.commit()
        for position in created_positions:
            self.db.refresh(position)
        return created_positions

    def mark_closed(
        self,
        user_id: int,
        symbol: str,
        closed_at: datetime | None = None,
        exit_price: float | None = None,
        exit_reason: str | None = None,
        exit_rsi: float | None = None,
        realized_pnl: float | None = None,
        realized_pnl_pct: float | None = None,
        sell_order_id: int | None = None,
        auto_commit: bool = True,
    ) -> Positions | None:
        """
        Mark a position as closed in the positions table.

        Sets closed_at timestamp, reduces quantity to 0, and populates exit details (Phase 0.2).

        Args:
            user_id: User ID
            symbol: Full trading symbol (e.g., "RELIANCE-EQ", "SALSTEEL-BE")
            closed_at: Closing timestamp (defaults to current time)
            exit_price: Exit price (optional)
            exit_reason: Reason for exit (e.g., 'EMA9_TARGET', 'RSI_EXIT', 'MANUAL')
            exit_rsi: RSI10 value at exit (optional)
            realized_pnl: Realized P&L amount (calculated if not provided and exit_price is set)
            realized_pnl_pct: Realized P&L percentage (calculated if not provided and realized_pnl is set)
            sell_order_id: ID of the sell order that closed this position (optional)
            auto_commit: If True, commit immediately. If False, caller handles commit (for transactions).

        Returns:
            Updated Positions object, or None if position not found
        """
        # Use FOR UPDATE lock to prevent race conditions with concurrent operations
        pos = self.get_by_symbol_for_update(user_id, symbol)
        if not pos:
            logger.warning(f"Position not found for {symbol} (user_id: {user_id})")
            return None

        # Store original quantity before setting to 0 (needed for P&L calculations)
        original_quantity = pos.quantity

        pos.closed_at = closed_at or ist_now()
        pos.quantity = 0.0  # Set quantity to 0 when fully closed

        # Phase 0.2: Populate exit details
        if exit_price is not None:
            pos.exit_price = exit_price
        if exit_reason is not None:
            pos.exit_reason = exit_reason
        if exit_rsi is not None:
            pos.exit_rsi = exit_rsi
        if sell_order_id is not None:
            pos.sell_order_id = sell_order_id

        # Calculate realized P&L if exit_price is provided but realized_pnl is not
        if exit_price is not None and realized_pnl is None:
            realized_pnl = (exit_price - pos.avg_price) * original_quantity
            pos.realized_pnl = realized_pnl
        elif realized_pnl is not None:
            pos.realized_pnl = realized_pnl

        # Calculate realized P&L percentage if realized_pnl is set but percentage is not
        if pos.realized_pnl is not None and realized_pnl_pct is None:
            cost_basis = pos.avg_price * original_quantity
            pos.realized_pnl_pct = (pos.realized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0
        elif realized_pnl_pct is not None:
            pos.realized_pnl_pct = realized_pnl_pct

        if auto_commit:
            self.db.commit()
            self.db.refresh(pos)
        else:
            # Even with auto_commit=False, flush to ensure changes are visible in the same session
            self.db.flush()
        logger.info(
            f"Position marked as closed: {symbol} (closed_at: {pos.closed_at}, "
            f"exit_price: {exit_price}, exit_reason: {exit_reason})"
        )
        return pos

    def reduce_quantity(
        self,
        user_id: int,
        symbol: str,
        sold_quantity: float,
        auto_commit: bool = True,
    ) -> Positions | None:
        """
        Reduce position quantity after partial sell execution.

        Keeps position open (closed_at remains NULL) if quantity > 0 after reduction.

        Args:
            user_id: User ID
            symbol: Full trading symbol (e.g., "RELIANCE-EQ", "SALSTEEL-BE")
            sold_quantity: Quantity sold (to subtract from current quantity)
            auto_commit: If True, commit immediately. If False, caller handles commit (for transactions).

        Returns:
            Updated Positions object, or None if position not found
        """
        # Use FOR UPDATE lock to prevent race conditions with concurrent operations
        pos = self.get_by_symbol_for_update(user_id, symbol)
        if not pos:
            logger.warning(f"Position not found for {symbol} (user_id: {user_id})")
            return None

        new_quantity = max(0.0, pos.quantity - sold_quantity)
        pos.quantity = new_quantity

        # If quantity becomes 0, mark as closed
        if new_quantity == 0:
            pos.closed_at = ist_now()
            logger.info(
                f"Position fully closed after partial sell: {symbol} "
                f"(sold {sold_quantity}, remaining: {new_quantity})"
            )
        else:
            # Keep position open for remaining quantity
            logger.info(
                f"Position quantity reduced: {symbol} "
                f"(sold {sold_quantity}, remaining: {new_quantity})"
            )

        if auto_commit:
            self.db.commit()
            self.db.refresh(pos)
        return pos
