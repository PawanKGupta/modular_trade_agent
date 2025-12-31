"""
NSE (National Stock Exchange) holiday calendar for trading day calculations.

This module contains the list of market holidays for NSE.
Holidays are stored as date objects for easy comparison.

Note: This list should be updated annually with the official NSE holiday calendar.
"""

from datetime import date, timedelta

# NSE Holidays for 2026 with names
NSE_HOLIDAYS_2026: dict[date, str] = {
    date(2026, 1, 26): "Republic Day",
    date(2026, 3, 3): "Holi",
    date(2026, 3, 26): "Shri Ram Navami",
    date(2026, 3, 31): "Shri Mahavir Jayanti",
    date(2026, 4, 3): "Good Friday",
    date(2026, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2026, 5, 1): "Maharashtra Day",
    date(2026, 5, 28): "Bakri Id",
    date(2026, 6, 26): "Muharram",
    date(2026, 9, 14): "Ganesh Chaturthi",
    date(2026, 10, 2): "Mahatma Gandhi Jayanti",
    date(2026, 10, 20): "Dussehra",
    date(2026, 11, 10): "Diwali-Balipratipada",
    date(2026, 11, 24): "Prakash Gurpurb Sri Guru Nanak Dev",
    date(2026, 12, 25): "Christmas",
}

# Combine all holiday sets (for future years, add more sets here)
ALL_NSE_HOLIDAYS: dict[date, str] = NSE_HOLIDAYS_2026

# Set of holiday dates for quick lookup
ALL_NSE_HOLIDAY_DATES: set[date] = set(ALL_NSE_HOLIDAYS.keys())


def is_nse_holiday(check_date: date) -> bool:
    """
    Check if a given date is an NSE market holiday.

    Args:
        check_date: Date to check

    Returns:
        True if the date is a market holiday, False otherwise
    """
    return check_date in ALL_NSE_HOLIDAY_DATES


def get_holiday_name(check_date: date) -> str | None:
    """
    Get the name of the holiday for a given date.

    Args:
        check_date: Date to check

    Returns:
        Holiday name if the date is a holiday, None otherwise
    """
    return ALL_NSE_HOLIDAYS.get(check_date)


def is_trading_day(check_date: date) -> bool:
    """
    Check if a date is a trading day (Mon-Fri, excluding weekends and holidays).

    Args:
        check_date: Date to check

    Returns:
        True if trading day, False otherwise
    """
    # Check if weekend (Saturday=5, Sunday=6)
    SATURDAY_WEEKDAY = 5
    if check_date.weekday() >= SATURDAY_WEEKDAY:
        return False

    # Check if holiday
    if check_date in ALL_NSE_HOLIDAY_DATES:
        return False

    return True


def get_next_trading_day(start_date: date) -> date:
    """
    Get the next trading day from a given date, skipping weekends and holidays.

    Args:
        start_date: Starting date

    Returns:
        Next trading day (date object)
    """
    next_day = start_date + timedelta(days=1)

    # Skip weekends and holidays until we find a trading day
    while not is_trading_day(next_day):
        next_day += timedelta(days=1)

    return next_day
