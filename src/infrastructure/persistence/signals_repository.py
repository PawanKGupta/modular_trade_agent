from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, outerjoin, select, update
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Signals, SignalStatus, UserSignalStatus
from src.infrastructure.db.timezone_utils import ist_now


class SignalsRepository:
    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id  # Optional: for per-user operations

    def recent(self, limit: int = 100, active_only: bool = False) -> list[Signals]:
        """Get recent signals, optionally filtered by status"""
        stmt = select(Signals).order_by(Signals.ts.desc())
        if active_only:
            stmt = stmt.where(Signals.status == SignalStatus.ACTIVE)
        stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def by_date(self, target_date: date, limit: int = 100) -> list[Signals]:
        """Get signals for a specific date (IST timezone)"""
        # Use SQLite's date() function to extract date from ts column
        # Format: 'YYYY-MM-DD'
        target_date_str = target_date.isoformat()

        # Query: filter by date part of ts using SQLite date() function
        stmt = (
            select(Signals)
            .where(func.date(Signals.ts) == target_date_str)
            .order_by(Signals.ts.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def by_date_range(self, start_date: date, end_date: date, limit: int = 100) -> list[Signals]:
        """Get signals within a date range (IST timezone)"""
        # Use SQLite's date() function to extract date from ts column
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()

        # Query: filter by date range using SQLite date() function
        stmt = (
            select(Signals)
            .where(func.date(Signals.ts) >= start_date_str, func.date(Signals.ts) <= end_date_str)
            .order_by(Signals.ts.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def last_n_dates(self, n: int, limit: int = 100) -> list[Signals]:
        """Get signals from the last N unique dates"""
        # Get distinct dates from the last N days
        now = ist_now()
        end_date = now.date()
        start_date = end_date - timedelta(days=n - 1)

        return self.by_date_range(start_date, end_date, limit=limit)

    def add_many(self, signals: list[Signals]) -> int:
        self.db.add_all(signals)
        self.db.commit()
        return len(signals)

    def mark_old_signals_as_expired(self, before_timestamp: datetime | None = None) -> int:
        """
        Mark old signals as EXPIRED.

        By default, marks all ACTIVE signals from previous analysis runs as EXPIRED.
        This is called before each analysis run to expire stale signals.

        Args:
            before_timestamp: Mark signals before this time as expired (defaults to current time)

        Returns:
            Number of signals marked as expired
        """
        if before_timestamp is None:
            before_timestamp = ist_now()

        # Mark all ACTIVE signals before the timestamp as EXPIRED
        result = self.db.execute(
            update(Signals)
            .where(Signals.status == SignalStatus.ACTIVE, Signals.ts < before_timestamp)
            .values(status=SignalStatus.EXPIRED)
        )
        self.db.commit()
        return result.rowcount

    def mark_as_traded(self, symbol: str, user_id: int | None = None) -> bool:
        """
        Mark a signal as TRADED for a specific user.

        Creates a UserSignalStatus entry to track per-user status.
        The base signal remains ACTIVE for other users.

        Args:
            symbol: Stock symbol
            user_id: User ID (uses self.user_id if not provided)

        Returns:
            True if signal was found and marked, False otherwise
        """
        user_id = user_id or self.user_id
        if not user_id:
            # Fallback to old behavior if no user_id (backward compatibility)
            result = self.db.execute(
                update(Signals)
                .where(Signals.symbol == symbol, Signals.status == SignalStatus.ACTIVE)
                .values(status=SignalStatus.TRADED)
            )
            self.db.commit()
            return result.rowcount > 0

        # Find the signal
        signal = self.db.execute(
            select(Signals)
            .where(Signals.symbol == symbol)
            .where(Signals.status.in_([SignalStatus.ACTIVE, SignalStatus.EXPIRED]))
            .order_by(Signals.ts.desc())
            .limit(1)
        ).scalar_one_or_none()

        if not signal:
            return False

        # Create or update user-specific status
        existing = self.db.execute(
            select(UserSignalStatus).where(
                UserSignalStatus.user_id == user_id, UserSignalStatus.signal_id == signal.id
            )
        ).scalar_one_or_none()

        if existing:
            existing.status = SignalStatus.TRADED
            existing.marked_at = ist_now()
        else:
            user_status = UserSignalStatus(
                user_id=user_id,
                signal_id=signal.id,
                symbol=symbol,
                status=SignalStatus.TRADED,
                marked_at=ist_now(),
            )
            self.db.add(user_status)

        self.db.commit()
        return True

    def mark_as_rejected(self, symbol: str, user_id: int | None = None) -> bool:
        """
        Mark a signal as REJECTED for a specific user.

        Creates a UserSignalStatus entry to track per-user status.
        The base signal remains ACTIVE for other users.

        Args:
            symbol: Stock symbol
            user_id: User ID (uses self.user_id if not provided)

        Returns:
            True if signal was found and marked, False otherwise
        """
        user_id = user_id or self.user_id
        if not user_id:
            # Fallback to old behavior if no user_id (backward compatibility)
            result = self.db.execute(
                update(Signals)
                .where(Signals.symbol == symbol, Signals.status == SignalStatus.ACTIVE)
                .values(status=SignalStatus.REJECTED)
            )
            self.db.commit()
            return result.rowcount > 0

        # Find the signal
        signal = self.db.execute(
            select(Signals)
            .where(Signals.symbol == symbol)
            .where(Signals.status.in_([SignalStatus.ACTIVE, SignalStatus.EXPIRED]))
            .order_by(Signals.ts.desc())
            .limit(1)
        ).scalar_one_or_none()

        if not signal:
            return False

        # Create or update user-specific status
        existing = self.db.execute(
            select(UserSignalStatus).where(
                UserSignalStatus.user_id == user_id, UserSignalStatus.signal_id == signal.id
            )
        ).scalar_one_or_none()

        if existing:
            existing.status = SignalStatus.REJECTED
            existing.marked_at = ist_now()
        else:
            user_status = UserSignalStatus(
                user_id=user_id,
                signal_id=signal.id,
                symbol=symbol,
                status=SignalStatus.REJECTED,
                marked_at=ist_now(),
            )
            self.db.add(user_status)

        self.db.commit()
        return True

    def mark_as_active(self, symbol: str, user_id: int | None = None) -> bool:  # noqa: PLR0911
        """
        Mark a signal as ACTIVE again for a specific user (reactivate).

        Removes the user-specific status override, allowing the signal to use
        its base status. Cannot reactivate if the base signal is EXPIRED.

        Args:
            symbol: Stock symbol
            user_id: User ID (uses self.user_id if not provided)

        Returns:
            True if signal was found and reactivated, False otherwise
        """
        user_id = user_id or self.user_id
        if not user_id:
            # Fallback: try to update base signal if it's REJECTED or TRADED
            # First check if signal exists and is already ACTIVE
            signal = self.db.execute(
                select(Signals).where(Signals.symbol == symbol).order_by(Signals.ts.desc()).limit(1)
            ).scalar_one_or_none()

            if not signal:
                return False

            # If already ACTIVE, return True
            if signal.status == SignalStatus.ACTIVE:
                return True

            # Cannot reactivate if expired
            if signal.status == SignalStatus.EXPIRED:
                return False

            # Check if signal is expired based on timestamp (from previous day)
            signal_date = signal.ts.date()
            today = ist_now().date()
            if signal_date < today:
                # Signal is from a previous day, consider it expired
                return False

            # Update REJECTED or TRADED to ACTIVE
            result = self.db.execute(
                update(Signals)
                .where(
                    Signals.symbol == symbol,
                    Signals.status.in_([SignalStatus.REJECTED, SignalStatus.TRADED]),
                )
                .values(status=SignalStatus.ACTIVE)
            )
            self.db.commit()
            return result.rowcount > 0

        # Find the signal
        signal = self.db.execute(
            select(Signals).where(Signals.symbol == symbol).order_by(Signals.ts.desc()).limit(1)
        ).scalar_one_or_none()

        if not signal:
            return False

        # Cannot reactivate if base signal is EXPIRED
        if signal.status == SignalStatus.EXPIRED:
            return False

        # Check if signal is expired based on timestamp (from previous day)
        signal_date = signal.ts.date()
        today = ist_now().date()
        if signal_date < today:
            # Signal is from a previous day, consider it expired
            return False

        # Find and delete user-specific status override
        existing = self.db.execute(
            select(UserSignalStatus).where(
                UserSignalStatus.user_id == user_id, UserSignalStatus.signal_id == signal.id
            )
        ).scalar_one_or_none()

        if existing:
            # Delete the override to revert to base signal status
            self.db.delete(existing)
            self.db.commit()
            return True

        # No override exists, signal is already using base status
        # Only return True if base status is ACTIVE
        return signal.status == SignalStatus.ACTIVE

    def get_active_signals(self, limit: int = 100) -> list[Signals]:
        """Get only ACTIVE signals"""
        stmt = (
            select(Signals)
            .where(Signals.status == SignalStatus.ACTIVE)
            .order_by(Signals.ts.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_user_signal_status(self, signal_id: int, user_id: int) -> SignalStatus | None:
        """
        Get user-specific status for a signal.

        Returns:
            User's status if they have one, otherwise None (uses base signal status)
        """
        user_status = self.db.execute(
            select(UserSignalStatus).where(
                UserSignalStatus.user_id == user_id, UserSignalStatus.signal_id == signal_id
            )
        ).scalar_one_or_none()

        return user_status.status if user_status else None

    def get_signals_with_user_status(
        self, user_id: int, limit: int = 100, status_filter: SignalStatus | None = None
    ) -> list[tuple[Signals, SignalStatus]]:
        """
        Get signals with per-user status applied.

        Returns list of (signal, effective_status) tuples where:
        - effective_status is user's custom status (TRADED/REJECTED) if they have one
        - otherwise it's the base signal status (ACTIVE/EXPIRED)

        Args:
            user_id: User ID to get personalized status for
            limit: Maximum number of signals to return
            status_filter: Filter by effective status (after applying user overrides)

        Returns:
            List of (Signals, SignalStatus) tuples
        """
        # Join signals with user_signal_status
        stmt = (
            select(Signals, UserSignalStatus.status)
            .select_from(
                outerjoin(
                    Signals,
                    UserSignalStatus,
                    (Signals.id == UserSignalStatus.signal_id)
                    & (UserSignalStatus.user_id == user_id),
                )
            )
            .order_by(Signals.ts.desc())
            .limit(limit)
        )

        results = self.db.execute(stmt).all()

        # Build list with effective status
        signals_with_status = []
        for signal, user_status in results:
            # Use user status if exists, otherwise use base signal status
            effective_status = user_status if user_status else signal.status

            # Apply status filter if provided
            if status_filter is None or effective_status == status_filter:
                signals_with_status.append((signal, effective_status))

        return signals_with_status
