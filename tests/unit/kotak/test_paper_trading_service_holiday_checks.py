"""
Unit tests for PaperTradingService holiday checks

Tests verify that PaperTradingService correctly identifies holidays as non-trading days.
"""

from datetime import date
from unittest.mock import patch

import pytest

from modules.kotak_neo_auto_trader.run_trading_service_paper import PaperTradingService


class TestPaperTradingServiceHolidayChecks:
    """Test PaperTradingService holiday awareness"""

    @pytest.fixture
    def paper_trading_service(self):
        """Create a PaperTradingService instance (minimal setup for is_trading_day tests)"""
        # We only need to test is_trading_day(), so we can create a minimal service
        service = PaperTradingService.__new__(PaperTradingService)
        return service

    def test_is_trading_day_holiday(self, paper_trading_service):
        """Test that is_trading_day returns False for holidays"""
        with patch("modules.kotak_neo_auto_trader.run_trading_service_paper.ist_now") as mock_ist_now:
            from datetime import datetime
            from src.infrastructure.db.timezone_utils import IST

            # Test known NSE holidays
            # Mahashivratri - Feb 26, 2025 (Wednesday)
            mock_ist_now.return_value = datetime(2025, 2, 26, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is False

            # Holi - Mar 14, 2025 (Friday)
            mock_ist_now.return_value = datetime(2025, 3, 14, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is False

            # Diwali Laxmi Pujan - Oct 21, 2025 (Tuesday)
            mock_ist_now.return_value = datetime(2025, 10, 21, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is False

    def test_is_trading_day_regular_weekday(self, paper_trading_service):
        """Test that is_trading_day returns True for regular weekdays (not holidays)"""
        with patch("modules.kotak_neo_auto_trader.run_trading_service_paper.ist_now") as mock_ist_now:
            from datetime import datetime
            from src.infrastructure.db.timezone_utils import IST

            # Regular Monday (not a holiday)
            mock_ist_now.return_value = datetime(2025, 12, 1, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is True

            # Regular Tuesday (not a holiday)
            mock_ist_now.return_value = datetime(2025, 12, 2, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is True

    def test_is_trading_day_weekend(self, paper_trading_service):
        """Test that is_trading_day returns False for weekends"""
        with patch("modules.kotak_neo_auto_trader.run_trading_service_paper.ist_now") as mock_ist_now:
            from datetime import datetime
            from src.infrastructure.db.timezone_utils import IST

            # Saturday
            mock_ist_now.return_value = datetime(2025, 12, 6, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is False

            # Sunday
            mock_ist_now.return_value = datetime(2025, 12, 7, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is False

