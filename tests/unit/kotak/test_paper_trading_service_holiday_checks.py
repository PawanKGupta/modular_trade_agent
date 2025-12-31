"""
Unit tests for PaperTradingService holiday checks

Tests verify that PaperTradingService correctly identifies holidays as non-trading days.
"""

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
        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service_paper.ist_now"
        ) as mock_ist_now:
            from datetime import datetime

            from src.infrastructure.db.timezone_utils import IST

            # Test known NSE holidays for 2026
            # Republic Day - Jan 26, 2026 (Monday)
            mock_ist_now.return_value = datetime(2026, 1, 26, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is False

            # Holi - Mar 3, 2026 (Tuesday)
            mock_ist_now.return_value = datetime(2026, 3, 3, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is False

            # Diwali-Balipratipada - Nov 10, 2026 (Tuesday)
            mock_ist_now.return_value = datetime(2026, 11, 10, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is False

    def test_is_trading_day_regular_weekday(self, paper_trading_service):
        """Test that is_trading_day returns True for regular weekdays (not holidays)"""
        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service_paper.ist_now"
        ) as mock_ist_now:
            from datetime import datetime

            from src.infrastructure.db.timezone_utils import IST

            # Regular Monday (not a holiday)
            mock_ist_now.return_value = datetime(2026, 12, 1, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is True

            # Regular Tuesday (not a holiday)
            mock_ist_now.return_value = datetime(2026, 12, 2, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is True

    def test_is_trading_day_weekend(self, paper_trading_service):
        """Test that is_trading_day returns False for weekends"""
        with patch(
            "modules.kotak_neo_auto_trader.run_trading_service_paper.ist_now"
        ) as mock_ist_now:
            from datetime import datetime

            from src.infrastructure.db.timezone_utils import IST

            # Saturday
            mock_ist_now.return_value = datetime(2026, 12, 6, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is False

            # Sunday
            mock_ist_now.return_value = datetime(2026, 12, 7, 10, 0, 0, tzinfo=IST)
            assert paper_trading_service.is_trading_day() is False
