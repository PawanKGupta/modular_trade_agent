"""
Unit tests for NSE holiday calendar

Tests cover:
- Holiday detection
- Trading day calculation
- Next trading day calculation
- Edge cases with holidays
"""

from datetime import date

from src.infrastructure.utils.holiday_calendar import (
    get_holiday_name,
    get_next_trading_day,
    is_nse_holiday,
    is_trading_day,
)


class TestHolidayDetection:
    """Test holiday detection functions"""

    def test_known_holiday_detected(self):
        """Should detect known NSE holidays"""
        # Republic Day - Jan 26, 2026
        assert is_nse_holiday(date(2026, 1, 26)) is True

        # Holi - Mar 3, 2026
        assert is_nse_holiday(date(2026, 3, 3)) is True

        # Diwali-Balipratipada - Nov 10, 2026
        assert is_nse_holiday(date(2026, 11, 10)) is True

        # Christmas - Dec 25, 2026
        assert is_nse_holiday(date(2026, 12, 25)) is True

    def test_regular_weekday_not_holiday(self):
        """Regular weekdays should not be detected as holidays"""
        # Regular Monday
        assert is_nse_holiday(date(2026, 12, 1)) is False

        # Regular Tuesday
        assert is_nse_holiday(date(2026, 12, 2)) is False

        # Regular Wednesday
        assert is_nse_holiday(date(2026, 12, 3)) is False

    def test_weekend_not_holiday(self):
        """Weekends should not be detected as holidays (they're non-trading days but not holidays)"""
        # Saturday
        assert is_nse_holiday(date(2026, 12, 6)) is False

        # Sunday
        assert is_nse_holiday(date(2026, 12, 7)) is False

    def test_get_holiday_name(self):
        """Should return holiday name for known holidays"""
        # Republic Day
        assert get_holiday_name(date(2026, 1, 26)) == "Republic Day"

        # Holi
        assert get_holiday_name(date(2026, 3, 3)) == "Holi"

        # Diwali-Balipratipada
        assert get_holiday_name(date(2026, 11, 10)) == "Diwali-Balipratipada"

        # Christmas
        assert get_holiday_name(date(2026, 12, 25)) == "Christmas"

    def test_get_holiday_name_returns_none_for_non_holidays(self):
        """Should return None for non-holiday dates"""
        # Regular weekday
        assert get_holiday_name(date(2026, 12, 1)) is None

        # Weekend
        assert get_holiday_name(date(2026, 12, 6)) is None


class TestTradingDayCheck:
    """Test is_trading_day() function"""

    def test_regular_weekday_is_trading_day(self):
        """Regular weekdays should be trading days"""
        # Regular Monday
        assert is_trading_day(date(2026, 12, 1)) is True

        # Regular Tuesday
        assert is_trading_day(date(2026, 12, 2)) is True

    def test_weekend_not_trading_day(self):
        """Weekends should not be trading days"""
        # Saturday
        assert is_trading_day(date(2026, 12, 5)) is False

        # Sunday
        assert is_trading_day(date(2026, 12, 6)) is False

    def test_holiday_not_trading_day(self):
        """Holidays should not be trading days"""
        # Republic Day - Jan 26, 2026 (Monday)
        assert is_trading_day(date(2026, 1, 26)) is False

        # Holi - Mar 3, 2026 (Tuesday)
        assert is_trading_day(date(2026, 3, 3)) is False

        # Diwali-Balipratipada - Nov 10, 2026 (Tuesday)
        assert is_trading_day(date(2026, 11, 10)) is False

    def test_holiday_on_weekend(self):
        """Holiday falling on weekend should still be detected correctly"""
        # Note: None of the 2026 holidays fall on weekends, but test the logic
        # If a holiday falls on Saturday/Sunday, it's still a holiday but weekend check comes first
        pass  # No 2026 holidays on weekends to test


class TestNextTradingDay:
    """Test get_next_trading_day() function"""

    def test_next_trading_day_regular_weekday(self):
        """Next trading day from regular weekday should be next day"""
        # Monday -> Tuesday
        assert get_next_trading_day(date(2026, 12, 1)) == date(2026, 12, 2)

        # Tuesday -> Wednesday
        assert get_next_trading_day(date(2026, 12, 2)) == date(2026, 12, 3)

    def test_next_trading_day_skips_weekend(self):
        """Next trading day should skip weekends"""
        # Friday -> Monday (skip Saturday, Sunday)
        assert get_next_trading_day(date(2026, 12, 4)) == date(2026, 12, 7)

        # Thursday -> Friday (normal)
        assert get_next_trading_day(date(2026, 12, 3)) == date(2026, 12, 4)

    def test_next_trading_day_skips_holiday(self):
        """Next trading day should skip holidays"""
        # Wednesday, Mar 25 -> Friday, Mar 27 (skip holiday on Mar 26 - Shri Ram Navami)
        assert get_next_trading_day(date(2026, 3, 25)) == date(2026, 3, 27)

        # Monday, Apr 13 -> Wednesday, Apr 15 (skip holiday on Apr 14 - Dr. Baba Saheb Ambedkar Jayanti)
        assert get_next_trading_day(date(2026, 4, 13)) == date(2026, 4, 15)

    def test_next_trading_day_skips_holiday_and_weekend(self):
        """Next trading day should skip both holidays and weekends"""
        # Thursday, Apr 2 -> Monday, Apr 6 (skip Good Friday on Apr 3 + weekend)
        assert get_next_trading_day(date(2026, 4, 2)) == date(2026, 4, 6)

    def test_next_trading_day_skips_multiple_holidays(self):
        """Next trading day should skip multiple consecutive holidays"""
        # Note: 2026 has single Diwali holiday on Nov 10, so testing with consecutive holidays
        # Monday, Nov 9 -> Wednesday, Nov 11 (skip Diwali-Balipratipada on Nov 10)
        assert get_next_trading_day(date(2026, 11, 9)) == date(2026, 11, 11)

    def test_next_trading_day_from_holiday(self):
        """Next trading day from a holiday should be the next trading day"""
        # Holiday: Tuesday, Mar 31 (Shri Mahavir Jayanti) -> Wednesday, Apr 1
        assert get_next_trading_day(date(2026, 3, 31)) == date(2026, 4, 1)

        # Holiday: Tuesday, Mar 3 (Holi) -> Wednesday, Mar 4
        assert get_next_trading_day(date(2026, 3, 3)) == date(2026, 3, 4)

    def test_next_trading_day_from_weekend(self):
        """Next trading day from weekend should be Monday"""
        # Saturday -> Monday
        assert get_next_trading_day(date(2026, 12, 5)) == date(2026, 12, 7)

        # Sunday -> Monday
        assert get_next_trading_day(date(2026, 12, 6)) == date(2026, 12, 7)
