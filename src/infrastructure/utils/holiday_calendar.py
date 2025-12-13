"""
NSE (National Stock Exchange) holiday calendar for trading day calculations.

This module contains the list of market holidays for NSE.
Holidays are stored as date objects for easy comparison.

Note: This list should be updated annually with the official NSE holiday calendar.
"""

from datetime import date, timedelta

# NSE Holidays for 2025 with names
NSE_HOLIDAYS_2025: dict[date, str] = {
    date(2025, 2, 26): "Mahashivratri",
    date(2025, 3, 14): "Holi",
    date(2025, 3, 31): "Id-Ul-Fitr (Ramadan Eid)",
    date(2025, 4, 10): "Shri Mahavir Jayanti",
    date(2025, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2025, 4, 18): "Good Friday",
    date(2025, 5, 1): "Maharashtra Day",
    date(2025, 8, 15): "Independence Day / Parsi New Year",
    date(2025, 8, 27): "Shri Ganesh Chaturthi",
    date(2025, 10, 2): "Mahatma Gandhi Jayanti/Dussehra",
    date(2025, 10, 21): "Diwali Laxmi Pujan",
    date(2025, 10, 22): "Balipratipada",
    date(2025, 11, 5): "Prakash Gurpurb Sri Guru Nanak Dev",
    date(2025, 12, 13): "TEST - Holiday for Testing",  # TODO: Remove before commit
    date(2025, 12, 25): "Christmas",
}

# Combine all holiday sets (for future years, add more sets here)
ALL_NSE_HOLIDAYS: dict[date, str] = NSE_HOLIDAYS_2025

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
    if check_date.weekday() >= 5:
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
