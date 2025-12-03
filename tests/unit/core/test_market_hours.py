"""
Tests for market hours detection functionality
"""

import pytest
from unittest.mock import patch
from datetime import datetime, time as dt_time

from core.volume_analysis import is_market_hours, get_current_market_time


class TestMarketHours:
    """Test market hours detection including pre-market"""

    @patch("core.volume_analysis.datetime")
    def test_is_market_hours_before_premarket(self, mock_datetime):
        """Test that times before 9:00 AM are not market hours"""
        # 8:59 AM
        mock_datetime.now.return_value.hour = 8
        mock_datetime.now.return_value.minute = 59
        assert is_market_hours() is False

        # 8:00 AM
        mock_datetime.now.return_value.hour = 8
        mock_datetime.now.return_value.minute = 0
        assert is_market_hours() is False

    @patch("core.volume_analysis.datetime")
    def test_is_market_hours_premarket(self, mock_datetime):
        """Test that pre-market hours (9:00 AM - 9:15 AM) are considered market hours"""
        # 9:00 AM - start of pre-market
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 0
        assert is_market_hours() is True

        # 9:05 AM - during pre-market
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 5
        assert is_market_hours() is True

        # 9:10 AM - during pre-market
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 10
        assert is_market_hours() is True

        # 9:14 AM - end of pre-market
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 14
        assert is_market_hours() is True

    @patch("core.volume_analysis.datetime")
    def test_is_market_hours_regular_market(self, mock_datetime):
        """Test that regular market hours (9:15 AM - 3:30 PM) are market hours"""
        # 9:15 AM - market open
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 15
        assert is_market_hours() is True

        # 12:00 PM - midday
        mock_datetime.now.return_value.hour = 12
        mock_datetime.now.return_value.minute = 0
        assert is_market_hours() is True

        # 2:00 PM - afternoon
        mock_datetime.now.return_value.hour = 14
        mock_datetime.now.return_value.minute = 0
        assert is_market_hours() is True

        # 3:30 PM - market close
        mock_datetime.now.return_value.hour = 15
        mock_datetime.now.return_value.minute = 30
        assert is_market_hours() is True

    @patch("core.volume_analysis.datetime")
    def test_is_market_hours_after_market_close(self, mock_datetime):
        """Test that times after 3:30 PM are not market hours"""
        # 3:31 PM - just after market close
        mock_datetime.now.return_value.hour = 15
        mock_datetime.now.return_value.minute = 31
        assert is_market_hours() is False

        # 4:00 PM
        mock_datetime.now.return_value.hour = 16
        mock_datetime.now.return_value.minute = 0
        assert is_market_hours() is False

        # 6:00 PM
        mock_datetime.now.return_value.hour = 18
        mock_datetime.now.return_value.minute = 0
        assert is_market_hours() is False

    @patch("core.volume_analysis.datetime")
    def test_get_current_market_time(self, mock_datetime):
        """Test get_current_market_time returns correct fractional hours"""
        # 9:00 AM = 9.0
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 0
        assert get_current_market_time() == 9.0

        # 9:15 AM = 9.25
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 15
        assert get_current_market_time() == 9.25

        # 9:30 AM = 9.5
        mock_datetime.now.return_value.hour = 9
        mock_datetime.now.return_value.minute = 30
        assert get_current_market_time() == 9.5

        # 12:00 PM = 12.0
        mock_datetime.now.return_value.hour = 12
        mock_datetime.now.return_value.minute = 0
        assert get_current_market_time() == 12.0

        # 3:30 PM = 15.5
        mock_datetime.now.return_value.hour = 15
        mock_datetime.now.return_value.minute = 30
        assert get_current_market_time() == 15.5

