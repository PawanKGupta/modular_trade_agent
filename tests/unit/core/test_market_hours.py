"""
Tests for market hours detection functionality
"""

from datetime import datetime
from unittest.mock import patch

from core.volume_analysis import get_current_market_time, is_market_hours, is_pre_open_session
from src.infrastructure.db.timezone_utils import IST


def _ist(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 15, hour, minute, 0, tzinfo=IST)


class TestMarketHours:
    """Test market hours detection including pre-market"""

    @patch("core.volume_analysis.ist_now")
    def test_is_market_hours_before_premarket(self, mock_ist_now):
        """Test that times before 9:00 AM are not market hours"""
        mock_ist_now.return_value = _ist(8, 59)
        assert is_market_hours() is False

        mock_ist_now.return_value = _ist(8, 0)
        assert is_market_hours() is False

    @patch("core.volume_analysis.ist_now")
    def test_is_market_hours_premarket(self, mock_ist_now):
        """Test that pre-market hours (9:00 AM - 9:15 AM) are considered market hours"""
        mock_ist_now.return_value = _ist(9, 0)
        assert is_market_hours() is True

        mock_ist_now.return_value = _ist(9, 5)
        assert is_market_hours() is True

        mock_ist_now.return_value = _ist(9, 10)
        assert is_market_hours() is True

        mock_ist_now.return_value = _ist(9, 14)
        assert is_market_hours() is True

    @patch("core.volume_analysis.ist_now")
    def test_is_pre_open_session(self, mock_ist_now):
        """Pre-open (9:00–before 9:15) uses LIMIT placement; 9:15+ uses MARKET."""
        mock_ist_now.return_value = _ist(9, 1)
        assert is_pre_open_session() is True

        mock_ist_now.return_value = _ist(9, 3)
        assert is_pre_open_session() is True

        mock_ist_now.return_value = _ist(9, 14)
        assert is_pre_open_session() is True

        mock_ist_now.return_value = _ist(9, 15)
        assert is_pre_open_session() is False

        mock_ist_now.return_value = _ist(12, 0)
        assert is_pre_open_session() is False

    @patch("core.volume_analysis.ist_now")
    def test_is_market_hours_regular_market(self, mock_ist_now):
        """Test that regular market hours (9:15 AM - 3:30 PM) are market hours"""
        mock_ist_now.return_value = _ist(9, 15)
        assert is_market_hours() is True

        mock_ist_now.return_value = _ist(12, 0)
        assert is_market_hours() is True

        mock_ist_now.return_value = _ist(14, 0)
        assert is_market_hours() is True

        mock_ist_now.return_value = _ist(15, 30)
        assert is_market_hours() is True

    @patch("core.volume_analysis.ist_now")
    def test_is_market_hours_after_market_close(self, mock_ist_now):
        """Test that times after 3:30 PM are not market hours"""
        mock_ist_now.return_value = _ist(15, 31)
        assert is_market_hours() is False

        mock_ist_now.return_value = _ist(16, 0)
        assert is_market_hours() is False

        mock_ist_now.return_value = _ist(18, 0)
        assert is_market_hours() is False

    @patch("core.volume_analysis.ist_now")
    def test_get_current_market_time(self, mock_ist_now):
        """Test get_current_market_time returns correct fractional hours"""
        mock_ist_now.return_value = _ist(9, 0)
        assert get_current_market_time() == 9.0

        mock_ist_now.return_value = _ist(9, 15)
        assert get_current_market_time() == 9.25

        mock_ist_now.return_value = _ist(9, 30)
        assert get_current_market_time() == 9.5

        mock_ist_now.return_value = _ist(12, 0)
        assert get_current_market_time() == 12.0

        mock_ist_now.return_value = _ist(15, 30)
        assert get_current_market_time() == 15.5
