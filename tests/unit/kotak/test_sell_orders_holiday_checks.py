"""
Unit tests for run_sell_orders.py holiday checks

Tests verify that the is_trading_day() function correctly identifies holidays as non-trading days.
"""

from datetime import date
from unittest.mock import patch

import pytest

# Import the is_trading_day function from run_sell_orders
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.run_sell_orders import is_trading_day


class TestSellOrdersHolidayChecks:
    """Test run_sell_orders holiday awareness"""

    def test_is_trading_day_holiday(self):
        """Test that is_trading_day returns False for holidays"""
        with patch("modules.kotak_neo_auto_trader.run_sell_orders.ist_now") as mock_ist_now:
            from datetime import datetime
            from src.infrastructure.db.timezone_utils import IST

            # Test known NSE holidays
            # Mahashivratri - Feb 26, 2025 (Wednesday)
            mock_ist_now.return_value = datetime(2025, 2, 26, 10, 0, 0, tzinfo=IST)
            assert is_trading_day() is False

            # Holi - Mar 14, 2025 (Friday)
            mock_ist_now.return_value = datetime(2025, 3, 14, 10, 0, 0, tzinfo=IST)
            assert is_trading_day() is False

            # Diwali Laxmi Pujan - Oct 21, 2025 (Tuesday)
            mock_ist_now.return_value = datetime(2025, 10, 21, 10, 0, 0, tzinfo=IST)
            assert is_trading_day() is False

            # Christmas - Dec 25, 2025 (Thursday)
            mock_ist_now.return_value = datetime(2025, 12, 25, 10, 0, 0, tzinfo=IST)
            assert is_trading_day() is False

    def test_is_trading_day_regular_weekday(self):
        """Test that is_trading_day returns True for regular weekdays (not holidays)"""
        with patch("modules.kotak_neo_auto_trader.run_sell_orders.ist_now") as mock_ist_now:
            from datetime import datetime
            from src.infrastructure.db.timezone_utils import IST

            # Regular Monday (not a holiday)
            mock_ist_now.return_value = datetime(2025, 12, 1, 10, 0, 0, tzinfo=IST)
            assert is_trading_day() is True

            # Regular Tuesday (not a holiday)
            mock_ist_now.return_value = datetime(2025, 12, 2, 10, 0, 0, tzinfo=IST)
            assert is_trading_day() is True

            # Regular Wednesday (not a holiday)
            mock_ist_now.return_value = datetime(2025, 12, 3, 10, 0, 0, tzinfo=IST)
            assert is_trading_day() is True

    def test_is_trading_day_weekend(self):
        """Test that is_trading_day returns False for weekends"""
        with patch("modules.kotak_neo_auto_trader.run_sell_orders.ist_now") as mock_ist_now:
            from datetime import datetime
            from src.infrastructure.db.timezone_utils import IST

            # Saturday
            mock_ist_now.return_value = datetime(2025, 12, 6, 10, 0, 0, tzinfo=IST)
            assert is_trading_day() is False

            # Sunday
            mock_ist_now.return_value = datetime(2025, 12, 7, 10, 0, 0, tzinfo=IST)
            assert is_trading_day() is False

