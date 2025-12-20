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
        # Mahashivratri - Feb 26, 2025
        assert is_nse_holiday(date(2025, 2, 26)) is True

        # Holi - Mar 14, 2025
        assert is_nse_holiday(date(2025, 3, 14)) is True

        # Diwali Laxmi Pujan - Oct 21, 2025
        assert is_nse_holiday(date(2025, 10, 21)) is True

        # Christmas - Dec 25, 2025
        assert is_nse_holiday(date(2025, 12, 25)) is True

    def test_regular_weekday_not_holiday(self):
        """Regular weekdays should not be detected as holidays"""
        # Regular Monday
        assert is_nse_holiday(date(2025, 12, 1)) is False

        # Regular Tuesday
        assert is_nse_holiday(date(2025, 12, 2)) is False

        # Regular Wednesday
        assert is_nse_holiday(date(2025, 12, 3)) is False

    def test_weekend_not_holiday(self):
        """Weekends should not be detected as holidays (they're non-trading days but not holidays)"""
        # Saturday
        assert is_nse_holiday(date(2025, 12, 6)) is False

        # Sunday
        assert is_nse_holiday(date(2025, 12, 7)) is False

    def test_get_holiday_name(self):
        """Should return holiday name for known holidays"""
        # Mahashivratri
        assert get_holiday_name(date(2025, 2, 26)) == "Mahashivratri"

        # Holi
        assert get_holiday_name(date(2025, 3, 14)) == "Holi"

        # Diwali Laxmi Pujan
        assert get_holiday_name(date(2025, 10, 21)) == "Diwali Laxmi Pujan"

        # Christmas
        assert get_holiday_name(date(2025, 12, 25)) == "Christmas"

    def test_get_holiday_name_returns_none_for_non_holidays(self):
        """Should return None for non-holiday dates"""
        # Regular weekday
        assert get_holiday_name(date(2025, 12, 1)) is None

        # Weekend
        assert get_holiday_name(date(2025, 12, 6)) is None


class TestTradingDayCheck:
    """Test is_trading_day() function"""

    def test_regular_weekday_is_trading_day(self):
        """Regular weekdays should be trading days"""
        # Regular Monday
        assert is_trading_day(date(2025, 12, 1)) is True

        # Regular Tuesday
        assert is_trading_day(date(2025, 12, 2)) is True

    def test_weekend_not_trading_day(self):
        """Weekends should not be trading days"""
        # Saturday
        assert is_trading_day(date(2025, 12, 6)) is False

        # Sunday
        assert is_trading_day(date(2025, 12, 7)) is False

    def test_holiday_not_trading_day(self):
        """Holidays should not be trading days"""
        # Mahashivratri - Feb 26, 2025 (Wednesday)
        assert is_trading_day(date(2025, 2, 26)) is False

        # Holi - Mar 14, 2025 (Friday)
        assert is_trading_day(date(2025, 3, 14)) is False

        # Diwali Laxmi Pujan - Oct 21, 2025 (Tuesday)
        assert is_trading_day(date(2025, 10, 21)) is False

    def test_holiday_on_weekend(self):
        """Holiday falling on weekend should still be detected correctly"""
        # Note: None of the 2025 holidays fall on weekends, but test the logic
        # If a holiday falls on Saturday/Sunday, it's still a holiday but weekend check comes first
        pass  # No 2025 holidays on weekends to test


class TestNextTradingDay:
    """Test get_next_trading_day() function"""

    def test_next_trading_day_regular_weekday(self):
        """Next trading day from regular weekday should be next day"""
        # Monday -> Tuesday
        assert get_next_trading_day(date(2025, 12, 1)) == date(2025, 12, 2)

        # Tuesday -> Wednesday
        assert get_next_trading_day(date(2025, 12, 2)) == date(2025, 12, 3)

    def test_next_trading_day_skips_weekend(self):
        """Next trading day should skip weekends"""
        # Friday -> Monday (skip Saturday, Sunday)
        assert get_next_trading_day(date(2025, 12, 5)) == date(2025, 12, 8)

        # Thursday -> Friday (normal)
        assert get_next_trading_day(date(2025, 12, 4)) == date(2025, 12, 5)

    def test_next_trading_day_skips_holiday(self):
        """Next trading day should skip holidays"""
        # Tuesday, Apr 9 -> Friday, Apr 11 (skip holiday on Apr 10 - Shri Mahavir Jayanti)
        assert get_next_trading_day(date(2025, 4, 9)) == date(2025, 4, 11)

        # Monday, Apr 13 -> Tuesday, Apr 15 (skip holiday on Apr 14 - Dr. Baba Saheb Ambedkar Jayanti)
        assert get_next_trading_day(date(2025, 4, 13)) == date(2025, 4, 15)

    def test_next_trading_day_skips_holiday_and_weekend(self):
        """Next trading day should skip both holidays and weekends"""
        # Friday, Apr 17 -> Monday, Apr 21 (skip Good Friday on Apr 18 + weekend)
        assert get_next_trading_day(date(2025, 4, 17)) == date(2025, 4, 21)

    def test_next_trading_day_skips_multiple_holidays(self):
        """Next trading day should skip multiple consecutive holidays"""
        # Monday, Oct 20 -> Thursday, Oct 23 (skip Oct 21 and Oct 22 - Diwali holidays)
        assert get_next_trading_day(date(2025, 10, 20)) == date(2025, 10, 23)

    def test_next_trading_day_from_holiday(self):
        """Next trading day from a holiday should be the next trading day"""
        # Holiday: Monday, Mar 31 (Id-Ul-Fitr) -> Tuesday, Apr 1
        assert get_next_trading_day(date(2025, 3, 31)) == date(2025, 4, 1)

        # Holiday: Friday, Mar 14 (Holi) -> Monday, Mar 17 (skip weekend)
        assert get_next_trading_day(date(2025, 3, 14)) == date(2025, 3, 17)

    def test_next_trading_day_from_weekend(self):
        """Next trading day from weekend should be Monday"""
        # Saturday -> Monday
        assert get_next_trading_day(date(2025, 12, 6)) == date(2025, 12, 8)

        # Sunday -> Monday
        assert get_next_trading_day(date(2025, 12, 7)) == date(2025, 12, 8)
