from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import bindparam, func, outerjoin, select, text, update
from sqlalchemy.orm import Session

from src.infrastructure.db.models import (
    Orders,
    OrderStatus,
    Positions,
    Signals,
    SignalStatus,
    UserSignalStatus,
)
from src.infrastructure.db.timezone_utils import IST, ist_now
from src.infrastructure.persistence.audit_log_repository import AuditLogRepository
from src.infrastructure.utils.holiday_calendar import get_next_trading_day

# Trading day constants
SATURDAY = 5  # weekday() returns 5 for Saturday
SUNDAY = 6  # weekday() returns 6 for Sunday
MARKET_CLOSE_TIME = time(15, 30)  # 3:30 PM IST


class SignalsRepository:
    """
    Repository for managing trading signals with expiry logic.

    Important Notes:
    - All signal timestamps are stored/assumed to be in IST (Indian Standard Time)
    - SQLite stores datetimes as naive (no timezone), but we treat them as IST
    - Each database session should call mark_time_expired_signals() independently
    - Session isolation: Changes in one session aren't visible to others until commit
    - Always call mark_time_expired_signals() before querying signals for consistency
    """

    def __init__(self, db: Session, user_id: int | None = None):
        self.db = db
        self.user_id = user_id  # Optional: for per-user operations

    def recent(self, limit: int = 100, active_only: bool = False) -> list[Signals]:
        """
        Get recent signals, optionally filtered to active only.

        Note: This method does NOT call mark_time_expired_signals() automatically.
        Callers should call mark_time_expired_signals() before using this method
        to ensure expired signals are not returned.

        Args:
            limit: Maximum number of signals to return
            active_only: If True, only return signals with ACTIVE status

        Returns:
            List of Signals, ordered by timestamp (most recent first)
        """
        stmt = select(Signals).order_by(Signals.ts.desc())
        if active_only:
            stmt = stmt.where(Signals.status == SignalStatus.ACTIVE)
        stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def by_date(self, target_date: date, limit: int = 100) -> list[Signals]:
        """
        Get signals for a specific date (IST timezone).

        Note: This method does NOT call mark_time_expired_signals() automatically.
        Callers should call mark_time_expired_signals() before using this method
        to ensure expired signals are not returned.

        Args:
            target_date: Date to filter by (assumed to be in IST timezone)
            limit: Maximum number of signals to return

        Returns:
            List of Signals for the specified date, ordered by timestamp (most recent first)
        """
        # Use SQLAlchemy's func.date() to extract date from ts column (works with both SQLite and PostgreSQL)
        # Format: 'YYYY-MM-DD'
        target_date_str = target_date.isoformat()

        # Query: filter by date part of ts using cross-database compatible date() function
        stmt = (
            select(Signals)
            .where(func.date(Signals.ts) == target_date_str)
            .order_by(Signals.ts.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def by_date_range(self, start_date: date, end_date: date, limit: int = 100) -> list[Signals]:
        """
        Get signals within a date range (IST timezone).

        Note: This method does NOT call mark_time_expired_signals() automatically.
        Callers should call mark_time_expired_signals() before using this method
        to ensure expired signals are not returned.

        Args:
            start_date: Start date (inclusive, assumed to be in IST timezone)
            end_date: End date (inclusive, assumed to be in IST timezone)
            limit: Maximum number of signals to return

        Returns:
            List of Signals within the date range, ordered by timestamp (most recent first)
        """
        # Use SQLAlchemy's func.date() to extract date from ts column (works with both SQLite and PostgreSQL)
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()

        # Query: filter by date range using cross-database compatible date() function
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
        # PostgreSQL can handle timezone-aware datetimes, but we normalize for consistency
        if before_timestamp.tzinfo is not None:
            before_timestamp = before_timestamp.replace(tzinfo=None)

        # Build SQL query to avoid Python-side datetime comparison issues
        # Use direct datetime comparison for cross-database compatibility
        # SQLite's julianday() doesn't exist in PostgreSQL, so use direct comparison
        # Note: Use LOWER() for case-insensitive status comparison
        # since SQLite stores enums as strings
        if exclude_symbols:
            # Use SQLAlchemy update() to avoid SQL injection warnings
            # Symbols come from internal code, not user input, but using ORM is safer
            # Use bindparam() to properly bind the timestamp parameter
            # Use synchronize_session=False to avoid Python-side datetime comparison
            # which fails when comparing naive (DB) vs aware (Python) datetimes
            before_timestamp_param = bindparam("before_timestamp", before_timestamp)
            stmt = (
                update(Signals)
                .where(
                    Signals.status == SignalStatus.ACTIVE,
                    Signals.ts < before_timestamp_param,
                    ~Signals.symbol.in_(exclude_symbols),
                )
                .values(status=SignalStatus.EXPIRED)
            )
            result = self.db.execute(stmt, execution_options={"synchronize_session": False})
        else:
            # Use raw SQL for better performance when no symbol exclusion
            # Direct datetime comparison works in both SQLite and PostgreSQL
            sql = text(
                """
                UPDATE signals
                SET status = :status
                WHERE status = :active_status
                  AND ts < :before_timestamp
                """
            )
            result = self.db.execute(
                sql,
                {
                    "status": SignalStatus.EXPIRED.value,  # "expired"
                    "active_status": SignalStatus.ACTIVE.value,  # "active"
                    "before_timestamp": before_timestamp,  # Pass datetime object directly
                },
            )
        # Commit the expiration update
        # Note: This commit happens within the same transaction as signal updates,
        # so updated signal timestamps are visible when checking for expiration
        self.db.commit()
        rowcount = result.rowcount
        return rowcount

    def mark_as_traded(self, symbol: str, user_id: int | None = None, reason: str = None) -> bool:
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

        prev_status = existing.status if existing else signal.status
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
        # Audit log
        audit_log_repo = AuditLogRepository(self.db)
        audit_log_repo.create(
            user_id=user_id,
            action="update",
            resource_type="signal",
            resource_id=signal.id,
            changes={
                "previous_status": prev_status.value,
                "new_status": SignalStatus.TRADED.value,
                "reason": reason or "order_placed",
            },
        )
        return True

    def mark_as_rejected(self, symbol: str, user_id: int | None = None, reason: str = None) -> bool:
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

        prev_status = existing.status if existing else signal.status
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
        # Audit log
        audit_log_repo = AuditLogRepository(self.db)
        audit_log_repo.create(
            user_id=user_id,
            action="update",
            resource_type="signal",
            resource_id=signal.id,
            changes={
                "previous_status": prev_status.value,
                "new_status": SignalStatus.REJECTED.value,
                "reason": reason or "manual_reject",
            },
        )
        return True

    def mark_as_failed(self, signal_id: int, user_id: int, reason: str = None) -> bool:
        """
        Mark a user-specific TRADED signal as FAILED.

        This is used when an order fails, is rejected, or is cancelled.
        The signal was previously marked as TRADED, but the order didn't succeed.

        Args:
            signal_id: Signal ID
            user_id: User ID

        Returns:
            True if signal was found and marked, False otherwise
        """
        if not user_id:
            return False

        # Check if user has a TRADED status override for this signal
        user_status = self.db.execute(
            select(UserSignalStatus).where(
                UserSignalStatus.user_id == user_id,
                UserSignalStatus.signal_id == signal_id,
                UserSignalStatus.status == SignalStatus.TRADED,
            )
        ).scalar_one_or_none()

        if user_status:
            prev_status = user_status.status
            user_status.status = SignalStatus.FAILED
            user_status.marked_at = ist_now()
            self.db.commit()
            # Audit log
            audit_log_repo = AuditLogRepository(self.db)
            audit_log_repo.create(
                user_id=user_id,
                action="update",
                resource_type="signal",
                resource_id=signal_id,
                changes={
                    "previous_status": prev_status.value,
                    "new_status": SignalStatus.FAILED.value,
                    "reason": reason or "order_failed",
                },
            )
            return True
        return False

    def mark_as_active(
        self, symbol: str, user_id: int | None = None, reason: str = None
    ) -> bool:  # noqa: PLR0911
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
        # Rule: Signal expires at the end of the next trading day's market hours (3:30 PM IST)
        # This check must happen before allowing reactivation to prevent reactivating old signals
        # Note: signal.ts may be naive (from SQLite), but _is_signal_expired_by_market_close handles this
        if self._is_signal_expired_by_market_close(signal.ts):
            return False

        # Find and delete user-specific status override
        existing = self.db.execute(
            select(UserSignalStatus).where(
                UserSignalStatus.user_id == user_id, UserSignalStatus.signal_id == signal.id
            )
        ).scalar_one_or_none()

        if existing:
            prev_status = existing.status
            # Delete the override to revert to base signal status
            self.db.delete(existing)
            self.db.commit()
            # Audit log
            audit_log_repo = AuditLogRepository(self.db)
            audit_log_repo.create(
                user_id=user_id,
                action="update",
                resource_type="signal",
                resource_id=signal.id,
                changes={
                    "previous_status": prev_status.value,
                    "new_status": SignalStatus.ACTIVE.value,
                    "reason": reason or "manual_reactivate",
                },
            )
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
            # Audit log
            audit_log_repo = AuditLogRepository(self.db)
            audit_log_repo.create(
                user_id=user_id,
                action="update",
                resource_type="signal",
                resource_id=signal.id,
                changes={
                    "previous_status": signal.status.value,
                    "new_status": SignalStatus.ACTIVE.value,
                    "reason": reason or "manual_reactivate",
                },
            )
            return True

        # Base status is something else (shouldn't happen), return False
        return False

    def get_amo_signal_expiry_time(self, signal_timestamp: datetime) -> datetime:
        """
        Calculate the expiry time for an AMO signal based on next trading day market open.

        Rule: AMO signals expire at market open on the next trading day (9:15 AM IST).

        Args:
            signal_timestamp: Signal creation timestamp (naive or timezone-aware)

        Returns:
            datetime: Expiry time (next trading day at 9:15 AM IST, timezone-aware)
        """
        from datetime import time as dt_time

        # Ensure signal timestamp is timezone-aware (IST)
        if signal_timestamp.tzinfo is None:
            signal_timestamp = signal_timestamp.replace(tzinfo=IST)
        else:
            signal_timestamp = signal_timestamp.astimezone(IST)

        # Get signal date
        signal_date = signal_timestamp.date()

        # Get next trading day (skips weekends and holidays)
        next_trading_day = get_next_trading_day(signal_date)

        # Return market open time on next trading day (9:15 AM IST, timezone-aware)
        market_open_time = dt_time(9, 15)  # 9:15 AM
        return datetime.combine(next_trading_day, market_open_time).replace(tzinfo=IST)

    def _is_amo_signal_expired(self, signal_timestamp: datetime) -> bool:
        """
        Check if an AMO signal is expired based on next trading day market open time (9:15 AM IST).

        Rule: AMO signals expire at market open on the next trading day.

        Args:
            signal_timestamp: Signal creation timestamp (naive or timezone-aware)

        Returns:
            True if signal is expired, False otherwise
        """
        # Get expiry time for this AMO signal
        expiry_time = self.get_amo_signal_expiry_time(signal_timestamp)

        # Check if current time has passed expiry time
        now = ist_now()
        return now >= expiry_time

    def _has_amo_order(self, signal: Signals) -> bool:
        """
        Check if a signal has an associated AMO order.

        Phase 2.2: Option B - Derive from orders (no schema change).
        Checks if there's a pending buy order for this signal's symbol.

        Args:
            signal: Signal to check

        Returns:
            True if signal has an AMO order, False otherwise
        """
        from src.infrastructure.db.models import Orders, OrderStatus

        # Check if there's a pending buy order for this symbol
        # AMO orders are typically placed before market open and are pending until 9:15 AM
        base_symbol = signal.symbol.split(".")[0].split("-")[0].upper()

        # Try multiple symbol variants
        candidates = [signal.symbol, base_symbol]
        if not signal.symbol.endswith(".NS"):
            candidates.append(f"{base_symbol}.NS")
        if "-" not in signal.symbol:
            candidates.append(f"{base_symbol}-EQ")

        for candidate in candidates:
            order = self.db.execute(
                select(Orders).where(
                    Orders.symbol == candidate,
                    Orders.side == "buy",
                    Orders.status == OrderStatus.PENDING,
                )
            ).scalar_one_or_none()

            if order:
                # Check if order was placed before market open (likely AMO)
                # AMO orders are placed before 9:15 AM
                from datetime import time as dt_time

                if order.placed_at:
                    placed_time = order.placed_at.time() if hasattr(order.placed_at, "time") else None
                    if placed_time and placed_time < dt_time(9, 15):
                        return True
                # If we can't determine from time, assume pending buy orders are AMO
                # (This is a heuristic - in practice, most pending buy orders before market open are AMO)
                return True

        return False

    def get_signal_expiry_time(self, signal_timestamp: datetime) -> datetime:
        """
        Calculate the expiry time for a signal based on next trading day market close.

        Rule: Signal is valid until the end of the next trading day's market hours (3:30 PM IST).

        Args:
            signal_timestamp: Signal creation timestamp (naive or timezone-aware)
                - If naive, assumed to be in IST timezone
                - If timezone-aware, converted to IST

        Returns:
            datetime: Expiry time (next trading day at 3:30 PM IST, timezone-aware)

        Examples:
            - Signal Monday 4:00 PM → Expires Tuesday 3:30 PM
            - Signal Friday 4:00 PM → Expires Monday 3:30 PM (skip weekend)
            - Signal Tuesday before holiday → Expires after holiday (skip holiday)
            - Signal Friday before holiday weekend → Expires Monday after weekend (skip holiday + weekend)

        Note:
            SQLite stores datetimes as naive (no timezone). When reading from database,
            timestamps are assumed to be in IST. This method handles both naive and
            timezone-aware datetimes correctly.
        """
        # Ensure signal timestamp is timezone-aware (IST)
        # SQLite stores datetimes as naive, so we assume naive = IST
        if signal_timestamp.tzinfo is None:
            signal_timestamp = signal_timestamp.replace(tzinfo=IST)
        else:
            signal_timestamp = signal_timestamp.astimezone(IST)

        # Get signal date
        signal_date = signal_timestamp.date()

        # Get next trading day (skips weekends and holidays)
        next_trading_day = get_next_trading_day(signal_date)

        # Return market close time on next trading day (timezone-aware in IST)
        return datetime.combine(next_trading_day, MARKET_CLOSE_TIME).replace(tzinfo=IST)

    def _is_signal_expired_by_market_close(self, signal_timestamp: datetime) -> bool:
        """
        Check if a signal is expired based on next trading day market close time (3:30 PM IST).

        Rule: Signal expires at the end of the next trading day's market hours.
        - Signal from Monday → Expires Tuesday 3:30 PM
        - Signal from Friday → Expires Monday 3:30 PM (skip weekend)
        - Weekends and holidays are skipped when finding next trading day

        Args:
            signal_timestamp: Signal creation timestamp (naive or timezone-aware)
                - If naive, assumed to be in IST timezone
                - If timezone-aware, converted to IST

        Returns:
            True if signal is expired, False otherwise
        """
        # Get expiry time for this signal (handles naive and timezone-aware datetimes)
        expiry_time = self.get_signal_expiry_time(signal_timestamp)

        # Check if current time has passed expiry time
        now = ist_now()
        return now >= expiry_time

    def mark_time_expired_signals(self) -> int:
        """
        Mark ACTIVE and REJECTED signals as EXPIRED if they have passed their time-based expiry.

        Rule: Signals expire at the end of the next trading day's market hours (3:30 PM IST).
        This function should be called periodically or before querying signals to ensure
        database consistency.

        Important:
            - This method should be called before querying signals in any code path
            - Each database session should call this independently (session isolation)
            - This method is idempotent (safe to call multiple times)
            - Uses a small time window check to minimize race conditions
            - Also checks REJECTED signals to ensure they're expired if past expiry time

        Returns:
            Number of signals marked as expired
        """
        # Get all ACTIVE and REJECTED signals
        signals_to_check = list(
            self.db.execute(
                select(Signals).where(
                    Signals.status.in_([SignalStatus.ACTIVE, SignalStatus.REJECTED])
                )
            )
            .scalars()
            .all()
        )

        # Get all symbols with open positions (quantity > 0 AND closed_at IS NULL)
        open_position_symbols = set(
            row
            for row in self.db.execute(
                select(Positions.symbol).where(
                    Positions.quantity > 0,
                    Positions.closed_at.is_(None),  # Only open positions, not closed ones
                )
            )
            .scalars()
            .all()
        )

        # Get all symbols with pending/ongoing buy orders
        pending_order_symbols = set(
            row
            for row in self.db.execute(
                select(Orders.symbol).where(
                    Orders.status.in_([OrderStatus.PENDING, OrderStatus.ONGOING]),
                    Orders.side == "buy",
                )
            )
            .scalars()
            .all()
        )

        audit_log_repo = AuditLogRepository(self.db)
        expired_count = 0
        SYSTEM_USER_ID = 1  # Must exist in users table
        audit_logs = []  # Collect audit logs for bulk insert

        for signal in signals_to_check:
            # Exclude if open position or pending buy order
            if signal.symbol in open_position_symbols or signal.symbol in pending_order_symbols:
                continue
            if signal.status in [
                SignalStatus.ACTIVE,
                SignalStatus.REJECTED,
            ]:
                # Phase 2.2: Check if signal has AMO order - use AMO expiry logic if so
                if self._has_amo_order(signal):
                    is_expired = self._is_amo_signal_expired(signal.ts)
                else:
                    is_expired = self._is_signal_expired_by_market_close(signal.ts)

                if is_expired:
                    prev_status = signal.status
                    signal.status = SignalStatus.EXPIRED
                    expired_count += 1
                    # Collect audit log entry for bulk insert
                    audit_logs.append(
                        {
                            "user_id": SYSTEM_USER_ID,
                            "action": "update",
                            "resource_type": "signal",
                            "resource_id": signal.id,
                            "changes": {
                                "previous_status": prev_status.value,
                                "new_status": SignalStatus.EXPIRED.value,
                                "reason": "eod_expiry",
                                "symbol": signal.symbol,
                            },
                        }
                    )

        # Bulk insert all audit logs at once (more efficient than individual creates)
        if audit_logs:
            audit_log_repo.create_bulk(audit_logs)

        if expired_count > 0:
            self.db.commit()
        return expired_count

    def get_active_signals(self, limit: int = 100) -> list[Signals]:
        """
        Get only ACTIVE signals.

        Before returning, checks and updates time-expired signals to ensure
        database consistency.
        """
        # Check and update time-expired signals before querying
        self.mark_time_expired_signals()

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

        Before returning, checks and updates time-expired signals to ensure
        database consistency.

        Args:
            user_id: User ID to get personalized status for
            limit: Maximum number of signals to return
            status_filter: Filter by effective status (after applying user overrides)

        Returns:
            List of (Signals, SignalStatus) tuples
        """
        # Mark time-expired signals before querying to ensure database consistency
        self.mark_time_expired_signals()

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
            # Determine effective status:
            # - User actions (TRADED/REJECTED/FAILED) always take precedence and are shown as effective status
            # - Base signal status (ACTIVE/EXPIRED) is shown separately in base_status field
            # - This allows frontend to display: "traded, expired" or "rejected, active" etc.
            if user_status in [SignalStatus.TRADED, SignalStatus.REJECTED, SignalStatus.FAILED]:
                # User has completed an action (TRADED/REJECTED/FAILED) - show this as effective status
                # Base status will show separately (e.g., "traded, expired" or "rejected, active")
                effective_status = user_status
            elif signal.status == SignalStatus.EXPIRED:
                # Base signal is EXPIRED and no user action - show as EXPIRED
                # User cannot override EXPIRED with ACTIVE (time-based expiry is final)
                effective_status = SignalStatus.EXPIRED
            else:
                # Use user status if exists, otherwise use base signal status
                effective_status = user_status if user_status else signal.status

            # Apply status filter if provided
            if status_filter is None or effective_status == status_filter:
                signals_with_status.append((signal, effective_status))

        return signals_with_status
