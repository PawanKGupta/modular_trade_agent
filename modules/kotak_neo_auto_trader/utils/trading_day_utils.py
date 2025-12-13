"""Trading day utility functions for order expiry calculation"""

from datetime import datetime, time, timedelta

from src.infrastructure.db.timezone_utils import IST, ist_now
from src.infrastructure.utils.holiday_calendar import get_next_trading_day, is_trading_day as is_trading_day_check

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
    # Extract date (handle both timezone-aware and naive datetimes)
    if failed_at.tzinfo is None:
        # Naive datetime - assume IST
        failed_date = failed_at.date()
    else:
        # Timezone-aware - convert to IST if needed
        failed_date = failed_at.astimezone(IST).date()

    # Get next trading day (skips weekends and holidays)
    next_trading_day = get_next_trading_day(failed_date)

    # Return market close time on next trading day (timezone-aware in IST)
    return datetime.combine(next_trading_day, MARKET_CLOSE_TIME).replace(tzinfo=IST)


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

    # Extract date if datetime object
    if isinstance(check_date, datetime):
        check_date_obj = check_date.date()
    else:
        check_date_obj = check_date

    # Use holiday calendar to check if trading day
    return is_trading_day_check(check_date_obj)
