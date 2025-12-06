"""
Tests for Edge Case #11: Reentry Daily Cap Check Discrepancy

Tests that reentries_today() correctly counts reentries from the reentries array
instead of looking for separate entries with entry_type == 'reentry'.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine  # noqa: E402


class TestReentriesTodayEdgeCase11:
    """Test Edge Case #11: reentries_today() checks reentries array correctly"""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock()
        auth.is_authenticated.return_value = True
        return auth

    @pytest.fixture
    def engine(self, mock_auth):
        """Create AutoTradeEngine instance"""
        with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"):
            engine = AutoTradeEngine(auth=mock_auth, user_id=1)
            return engine

    def test_reentries_today_counts_from_reentries_array(self, engine):
        """Test that reentries_today() counts reentries from reentries array"""
        today_iso = datetime.now().isoformat()

        # Mock trade history with reentries in array (correct format)
        mock_history = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "entry_type": "initial",  # Not "reentry"!
                    "entry_time": "2025-01-20T09:00:00",
                    "reentries": [
                        {
                            "qty": 10,
                            "level": 20,
                            "time": today_iso,  # Today's reentry
                        }
                    ],
                }
            ]
        }

        engine._load_trades_history = Mock(return_value=mock_history)

        count = engine.reentries_today("RELIANCE")

        # Should find 1 reentry from the reentries array
        assert count == 1

    def test_reentries_today_filters_by_symbol(self, engine):
        """Test that reentries_today() only counts reentries for the specified symbol"""
        today_iso = datetime.now().isoformat()

        mock_history = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "entry_type": "initial",
                    "reentries": [{"qty": 10, "level": 20, "time": today_iso}],
                },
                {
                    "symbol": "TCS",
                    "entry_type": "initial",
                    "reentries": [{"qty": 5, "level": 20, "time": today_iso}],
                },
            ]
        }

        engine._load_trades_history = Mock(return_value=mock_history)

        # Count for RELIANCE should only find RELIANCE reentries
        count_reliance = engine.reentries_today("RELIANCE")
        assert count_reliance == 1

        # Count for TCS should only find TCS reentries
        count_tcs = engine.reentries_today("TCS")
        assert count_tcs == 1

    def test_reentries_today_filters_by_date(self, engine):
        """Test that reentries_today() only counts reentries from today"""
        today_iso = datetime.now().isoformat()
        yesterday_iso = (datetime.now().replace(day=datetime.now().day - 1)).isoformat()

        mock_history = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "entry_type": "initial",
                    "reentries": [
                        {"qty": 10, "level": 20, "time": today_iso},  # Today
                        {"qty": 5, "level": 10, "time": yesterday_iso},  # Yesterday
                    ],
                }
            ]
        }

        engine._load_trades_history = Mock(return_value=mock_history)

        count = engine.reentries_today("RELIANCE")

        # Should only count today's reentry
        assert count == 1

    def test_reentries_today_handles_multiple_reentries_same_day(self, engine):
        """Test that reentries_today() counts multiple reentries in same day"""
        today_iso = datetime.now().isoformat()

        mock_history = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "entry_type": "initial",
                    "reentries": [
                        {"qty": 10, "level": 20, "time": today_iso},
                        {"qty": 5, "level": 10, "time": today_iso},  # Same day
                    ],
                }
            ]
        }

        engine._load_trades_history = Mock(return_value=mock_history)

        count = engine.reentries_today("RELIANCE")

        # Should count both reentries from today
        assert count == 2

    def test_reentries_today_handles_missing_reentries_array(self, engine):
        """Test that reentries_today() handles trades without reentries array"""
        mock_history = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "entry_type": "initial",
                    # No reentries array
                }
            ]
        }

        engine._load_trades_history = Mock(return_value=mock_history)

        count = engine.reentries_today("RELIANCE")

        # Should return 0 (no reentries)
        assert count == 0

    def test_reentries_today_handles_empty_reentries_array(self, engine):
        """Test that reentries_today() handles empty reentries array"""
        mock_history = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "entry_type": "initial",
                    "reentries": [],  # Empty array
                }
            ]
        }

        engine._load_trades_history = Mock(return_value=mock_history)

        count = engine.reentries_today("RELIANCE")

        # Should return 0
        assert count == 0

    def test_reentries_today_handles_missing_time_field(self, engine):
        """Test that reentries_today() skips reentries without time field"""
        mock_history = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "entry_type": "initial",
                    "reentries": [
                        {"qty": 10, "level": 20},  # No time field
                    ],
                }
            ]
        }

        engine._load_trades_history = Mock(return_value=mock_history)

        count = engine.reentries_today("RELIANCE")

        # Should skip reentry without time field
        assert count == 0

    def test_reentries_today_handles_invalid_time_format(self, engine):
        """Test that reentries_today() handles invalid time formats gracefully"""
        mock_history = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "entry_type": "initial",
                    "reentries": [
                        {"qty": 10, "level": 20, "time": "invalid-date"},  # Invalid format
                    ],
                }
            ]
        }

        engine._load_trades_history = Mock(return_value=mock_history)

        count = engine.reentries_today("RELIANCE")

        # Should skip invalid time format
        assert count == 0

    def test_reentries_today_handles_exception_gracefully(self, engine):
        """Test that reentries_today() returns 0 on exception"""
        engine._load_trades_history = Mock(side_effect=Exception("Test error"))

        count = engine.reentries_today("RELIANCE")

        # Should return 0 on exception
        assert count == 0

    def test_reentries_today_case_insensitive_symbol_matching(self, engine):
        """Test that reentries_today() matches symbols case-insensitively"""
        today_iso = datetime.now().isoformat()

        mock_history = {
            "trades": [
                {
                    "symbol": "reliance",  # Lowercase
                    "entry_type": "initial",
                    "reentries": [{"qty": 10, "level": 20, "time": today_iso}],
                }
            ]
        }

        engine._load_trades_history = Mock(return_value=mock_history)

        # Query with uppercase
        count = engine.reentries_today("RELIANCE")

        # Should match case-insensitively
        assert count == 1

    def test_reentries_today_daily_cap_enforcement(self, engine):
        """Test that daily cap is enforced correctly with fixed reentries_today()"""
        today_iso = datetime.now().isoformat()

        # Mock trade history with 1 reentry today
        mock_history = {
            "trades": [
                {
                    "symbol": "RELIANCE",
                    "entry_type": "initial",
                    "reentries": [
                        {"qty": 10, "level": 20, "time": today_iso},  # 1 reentry today
                    ],
                }
            ]
        }

        engine._load_trades_history = Mock(return_value=mock_history)

        count = engine.reentries_today("RELIANCE")

        # Should find 1 reentry
        assert count == 1

        # Daily cap check: count >= 1 should block further reentries
        assert count >= 1  # This would block reentry in place_reentry_orders()
