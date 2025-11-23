"""Trading day utility functions for order expiry calculation"""

from datetime import datetime, time, timedelta

from src.infrastructure.db.timezone_utils import ist_now

MARKET_CLOSE_TIME = time(15, 30)  # 3:30 PM IST
SATURDAY = 5  # weekday() returns 5 for Saturday
SUNDAY = 6  # weekday() returns 6 for Sunday


def get_next_trading_day_close(failed_at: datetime) -> datetime:
    """
    Calculate next trading day market close from failure time.
    Excludes weekends and holidays.

    Args:
        failed_at: When order failed (datetime)

    Returns:
        datetime: Next trading day market close (3:30 PM IST)

    Example:
        - failed_at: Monday 4:05 PM → Returns: Tuesday 3:30 PM
        - failed_at: Friday 4:05 PM → Returns: Monday 3:30 PM (skip weekend)
    """
    # Start from day after failure
    next_day = failed_at.date() + timedelta(days=1)

    # Skip weekends (Saturday=5, Sunday=6)
    while next_day.weekday() >= SATURDAY:
        next_day += timedelta(days=1)

    # TODO: Skip holidays (add holiday checking logic)
    # For now, just skip weekends

    # Return market close time on next trading day
    return datetime.combine(next_day, MARKET_CLOSE_TIME)


def is_trading_day(check_date: datetime | None = None) -> bool:
    """
    Check if a date is a trading day (Mon-Fri, excluding holidays).

    Args:
        check_date: Date to check (defaults to today)

    Returns:
        True if trading day, False otherwise
    """
    if check_date is None:
        check_date = ist_now()

    # Check if weekday (Monday=0, Sunday=6)
    weekday = check_date.weekday()
    if weekday >= SATURDAY:  # Saturday or Sunday
        return False

    # TODO: Add holiday checking logic
    # For now, just check weekday

    return True
