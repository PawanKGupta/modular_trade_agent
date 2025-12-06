from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import bindparam, func, outerjoin, select, text, update
from sqlalchemy.orm import Session

from src.infrastructure.db.models import Signals, SignalStatus, UserSignalStatus
from src.infrastructure.db.timezone_utils import IST, ist_now


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

    def mark_old_signals_as_expired(
        self, before_timestamp: datetime | None = None, exclude_symbols: set[str] | None = None
    ) -> int:
        """
        Mark old signals as EXPIRED.

        By default, marks all ACTIVE signals from previous analysis runs as EXPIRED.
        This is called before each analysis run to expire stale signals.

        Args:
            before_timestamp: Mark signals before this time as expired (defaults to current time)
            exclude_symbols: Set of symbols to exclude from expiration
                (e.g., symbols that appear in new analysis)

        Returns:
            Number of signals marked as expired
        """
        if before_timestamp is None:
            before_timestamp = ist_now()

        # Convert to naive datetime for database comparison (SQLite stores as naive)
        if before_timestamp.tzinfo is not None:
            before_timestamp = before_timestamp.replace(tzinfo=None)

        # Format timestamp for SQL (SQLite datetime format)
        # SQLite's julianday() can parse various formats, but we'll use a consistent format
        # Use the format that matches what SQLite stores:
        # YYYY-MM-DD HH:MM:SS or YYYY-MM-DD HH:MM:SS.ffffff
        # julianday() handles both formats correctly
        timestamp_str = before_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        if before_timestamp.microsecond:
            timestamp_str += f".{before_timestamp.microsecond:06d}"

        # Build SQL query to avoid Python-side datetime comparison issues
        # Use julianday() for reliable numeric comparison
        # This handles both with and without microseconds correctly
        # Note: Use LOWER() for case-insensitive status comparison
        # since SQLite stores enums as strings
        if exclude_symbols:
            # Use SQLAlchemy update() to avoid SQL injection warnings
            # Symbols come from internal code, not user input, but using ORM is safer
            # Use bindparam() to properly bind the timestamp parameter
            before_timestamp_param = bindparam("before_timestamp", timestamp_str)
            stmt = (
                update(Signals)
                .where(
                    Signals.status == SignalStatus.ACTIVE,
                    func.julianday(Signals.ts) < func.julianday(before_timestamp_param),
                    ~Signals.symbol.in_(exclude_symbols),
                )
                .values(status=SignalStatus.EXPIRED)
            )
            result = self.db.execute(stmt)
        else:
            sql = text(
                """
                UPDATE signals
                SET status = :status
                WHERE status = :active_status
                  AND julianday(ts) < julianday(:before_timestamp)
                """
            )
            result = self.db.execute(
                sql,
                {
                    "status": SignalStatus.EXPIRED.value,  # "expired"
                    "active_status": SignalStatus.ACTIVE.value,  # "active"
                    "before_timestamp": timestamp_str,
                },
            )
        # Commit the expiration update
        # Note: This commit happens within the same transaction as signal updates,
        # so updated signal timestamps are visible when checking for expiration
        self.db.commit()
        rowcount = result.rowcount
        return rowcount

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

        # Find the signal (don't restrict by base status - user may have overridden it)
        signal = self.db.execute(
            select(Signals).where(Signals.symbol == symbol).order_by(Signals.ts.desc()).limit(1)
        ).scalar_one_or_none()

        if not signal:
            return False

        # Check if user already has a status override for this signal
        existing = self.db.execute(
            select(UserSignalStatus).where(
                UserSignalStatus.user_id == user_id, UserSignalStatus.signal_id == signal.id
            )
        ).scalar_one_or_none()

        # If user has an override, allow updating to TRADED regardless of base status
        # If no override exists, only allow if base signal is ACTIVE or EXPIRED
        if not existing and signal.status not in [SignalStatus.ACTIVE, SignalStatus.EXPIRED]:
            return False

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

            # Check if signal is expired based on market close time (3:30 PM IST)
            if self._is_signal_expired_by_market_close(signal.ts):
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

        # Check if signal is expired based on market close time (3:30 PM IST)
        # Rules:
        # - Signals before yesterday's 3:30 PM are expired
        # - Signals after yesterday's 3:30 PM are active until today's 3:30 PM
        if self._is_signal_expired_by_market_close(signal.ts):
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
        # If base status is ACTIVE, we're done
        if signal.status == SignalStatus.ACTIVE:
            return True

        # If base status is REJECTED or TRADED, we need to create a user override
        # to mark it as ACTIVE for this user (since we can't change base status for all users)
        if signal.status in [SignalStatus.REJECTED, SignalStatus.TRADED]:
            # Create user-specific override to mark as ACTIVE
            user_status = UserSignalStatus(
                user_id=user_id,
                signal_id=signal.id,
                symbol=signal.symbol,
                status=SignalStatus.ACTIVE,
                marked_at=ist_now(),
            )
            self.db.add(user_status)
            self.db.commit()
            return True

        # Base status is something else (shouldn't happen), return False
        return False

    def _is_signal_expired_by_market_close(self, signal_timestamp: datetime) -> bool:
        """
        Check if a signal is expired based on market close time (3:30 PM IST).

        Rules:
        - Signals from day before yesterday (2 days ago) are expired
        - Signals generated yesterday are active until today's 3:30 PM

        Args:
            signal_timestamp: Signal creation timestamp

        Returns:
            True if signal is expired, False otherwise
        """
        # Ensure signal timestamp is timezone-aware (IST)
        if signal_timestamp.tzinfo is None:
            signal_timestamp = signal_timestamp.replace(tzinfo=IST)
        else:
            signal_timestamp = signal_timestamp.astimezone(IST)

        now = ist_now()
        market_close_time = time(15, 30)  # 3:30 PM IST

        # Get signal date and today's date
        signal_date = signal_timestamp.date()
        today_date = now.date()
        yesterday_date = today_date - timedelta(days=1)
        day_before_yesterday_date = today_date - timedelta(days=2)

        # Signal is expired if:
        # 1. Signal was created on day before yesterday or earlier, OR
        # 2. Signal was created yesterday but current time >= today's 3:30 PM
        if signal_date <= day_before_yesterday_date:
            return True  # Signal from day before yesterday or earlier is expired

        if signal_date == yesterday_date and now >= datetime.combine(
            today_date, market_close_time
        ).replace(tzinfo=IST):
            return True  # Signal from yesterday but past today's 3:30 PM is expired

        return False  # Signal is still active

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

    def get_user_signal_status_by_symbol(self, symbol: str, user_id: int) -> SignalStatus | None:
        """
        Get user-specific status for a signal by symbol (checks latest signal for that symbol).

        Returns:
            User's status if they have one, otherwise None (uses base signal status)
        """
        # Find the latest signal for this symbol
        signal = self.db.execute(
            select(Signals).where(Signals.symbol == symbol).order_by(Signals.ts.desc()).limit(1)
        ).scalar_one_or_none()

        if not signal:
            return None

        # Get user status for this signal
        return self.get_user_signal_status(signal.id, user_id)

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
