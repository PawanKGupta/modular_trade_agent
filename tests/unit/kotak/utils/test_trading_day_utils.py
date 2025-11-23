"""
Tests for trading day utility functions.

Tests:
1. get_next_trading_day_close() - weekend skipping
2. is_trading_day() - weekday/holiday checking
3. Edge cases
"""

from datetime import datetime

from modules.kotak_neo_auto_trader.utils.trading_day_utils import (
    MARKET_CLOSE_TIME,
    get_next_trading_day_close,
    is_trading_day,
)


class TestTradingDayUtils:
    """Test trading day utility functions"""

    def test_get_next_trading_day_close_weekday(self):
        """Test next trading day calculation for weekday"""
        # Monday 4 PM -> Tuesday 3:30 PM
        monday = datetime(2025, 1, 6, 16, 0)  # Monday 4 PM
        next_close = get_next_trading_day_close(monday)

        assert next_close.date() == datetime(2025, 1, 7).date()  # Tuesday
        assert next_close.time() == MARKET_CLOSE_TIME  # 3:30 PM

    def test_get_next_trading_day_close_friday(self):
        """Test next trading day calculation skips weekend"""
        # Friday 4 PM -> Monday 3:30 PM (skip Saturday, Sunday)
        friday = datetime(2025, 1, 3, 16, 0)  # Friday 4 PM
        next_close = get_next_trading_day_close(friday)

        assert next_close.date() == datetime(2025, 1, 6).date()  # Monday (skipped weekend)
        assert next_close.time() == MARKET_CLOSE_TIME

    def test_get_next_trading_day_close_saturday(self):
        """Test next trading day calculation from Saturday"""
        # Saturday -> Monday 3:30 PM (skip Sunday)
        saturday = datetime(2025, 1, 4, 10, 0)  # Saturday 10 AM
        next_close = get_next_trading_day_close(saturday)

        assert next_close.date() == datetime(2025, 1, 6).date()  # Monday
        assert next_close.time() == MARKET_CLOSE_TIME

    def test_get_next_trading_day_close_sunday(self):
        """Test next trading day calculation from Sunday"""
        # Sunday -> Monday 3:30 PM
        sunday = datetime(2025, 1, 5, 10, 0)  # Sunday 10 AM
        next_close = get_next_trading_day_close(sunday)

        assert next_close.date() == datetime(2025, 1, 6).date()  # Monday
        assert next_close.time() == MARKET_CLOSE_TIME

    def test_get_next_trading_day_close_before_market_close(self):
        """Test next trading day when failed before market close"""
        # Monday 2 PM -> Tuesday 3:30 PM (same day hasn't closed yet)
        monday_afternoon = datetime(2025, 1, 6, 14, 0)  # Monday 2 PM
        next_close = get_next_trading_day_close(monday_afternoon)

        assert next_close.date() == datetime(2025, 1, 7).date()  # Tuesday
        assert next_close.time() == MARKET_CLOSE_TIME

    def test_get_next_trading_day_close_after_market_close(self):
        """Test next trading day when failed after market close"""
        # Monday 4 PM (after 3:30 PM close) -> Tuesday 3:30 PM
        monday_evening = datetime(2025, 1, 6, 16, 0)  # Monday 4 PM
        next_close = get_next_trading_day_close(monday_evening)

        assert next_close.date() == datetime(2025, 1, 7).date()  # Tuesday
        assert next_close.time() == MARKET_CLOSE_TIME

    def test_is_trading_day_weekday(self):
        """Test is_trading_day returns True for weekdays"""
        monday = datetime(2025, 1, 6)  # Monday
        tuesday = datetime(2025, 1, 7)  # Tuesday
        friday = datetime(2025, 1, 3)  # Friday

        assert is_trading_day(monday) is True
        assert is_trading_day(tuesday) is True
        assert is_trading_day(friday) is True

    def test_is_trading_day_weekend(self):
        """Test is_trading_day returns False for weekends"""
        saturday = datetime(2025, 1, 4)  # Saturday
        sunday = datetime(2025, 1, 5)  # Sunday

        assert is_trading_day(saturday) is False
        assert is_trading_day(sunday) is False

    def test_is_trading_day_defaults_to_today(self):
        """Test is_trading_day defaults to current date"""
        # Should work without argument (uses ist_now())
        result = is_trading_day()
        assert isinstance(result, bool)
