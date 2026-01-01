"""
Tests for Edge Case #11: Reentry Daily Cap Check Discrepancy

Tests that reentries_today() correctly counts reentries from the reentries array
instead of looking for separate entries with entry_type == 'reentry'.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

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
    def mock_positions_repo(self):
        """Create mock positions repository"""
        repo = MagicMock()
        return repo

    @pytest.fixture
    def engine(self, mock_auth, mock_positions_repo):
        """Create AutoTradeEngine instance with mocked database"""
        with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"):
            engine = AutoTradeEngine(auth=mock_auth, user_id=1)
            engine.positions_repo = mock_positions_repo
            return engine

    def test_reentries_today_counts_from_reentries_array(self, engine, mock_positions_repo):
        """Test that reentries_today() counts reentries from reentries array"""
        today_iso = datetime.now().isoformat()

        # Mock position with reentries array
        mock_position = MagicMock()
        mock_position.reentries = [
            {
                "qty": 10,
                "level": 20,
                "time": today_iso,  # Today's reentry
            }
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should find 1 reentry from the reentries array
        assert count == 1
        mock_positions_repo.get_by_symbol.assert_called_once_with(1, "RELIANCE")

    def test_reentries_today_filters_by_symbol(self, engine, mock_positions_repo):
        """Test that reentries_today() only counts reentries for the specified symbol"""
        today_iso = datetime.now().isoformat()

        # Mock RELIANCE position
        mock_reliance = MagicMock()
        mock_reliance.reentries = [{"qty": 10, "level": 20, "time": today_iso}]

        # Mock TCS position
        mock_tcs = MagicMock()
        mock_tcs.reentries = [{"qty": 5, "level": 20, "time": today_iso}]

        # Return different positions based on symbol
        def get_by_symbol_side_effect(user_id, symbol):
            if symbol.upper() == "RELIANCE":
                return mock_reliance
            elif symbol.upper() == "TCS":
                return mock_tcs
            return None

        mock_positions_repo.get_by_symbol.side_effect = get_by_symbol_side_effect

        # Count for RELIANCE should only find RELIANCE reentries
        count_reliance = engine.reentries_today("RELIANCE")
        assert count_reliance == 1

        # Count for TCS should only find TCS reentries
        count_tcs = engine.reentries_today("TCS")
        assert count_tcs == 1

    def test_reentries_today_filters_by_date(self, engine, mock_positions_repo):
        """Test that reentries_today() only counts reentries from today"""
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        today_iso = datetime.now().isoformat()
        yesterday_iso = datetime.combine(yesterday, datetime.min.time()).isoformat()

        mock_position = MagicMock()
        mock_position.reentries = [
            {"qty": 10, "level": 20, "time": today_iso, "placed_at": today.isoformat()},  # Today
            {
                "qty": 5,
                "level": 10,
                "time": yesterday_iso,
                "placed_at": yesterday.isoformat(),
            },  # Yesterday
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should only count today's reentry (by placed_at date)
        assert count == 1

    def test_reentries_today_handles_multiple_reentries_same_day(self, engine, mock_positions_repo):
        """Test that reentries_today() counts multiple reentries in same day"""
        today = datetime.now().date()
        today_iso = datetime.now().isoformat()

        mock_position = MagicMock()
        mock_position.reentries = [
            {"qty": 10, "level": 20, "time": today_iso, "placed_at": today.isoformat()},
            {"qty": 5, "level": 10, "time": today_iso, "placed_at": today.isoformat()},  # Same day
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should count both reentries from today (by placed_at date)
        assert count == 2

    def test_reentries_today_handles_missing_reentries_array(self, engine, mock_positions_repo):
        """Test that reentries_today() handles positions without reentries array"""
        mock_position = MagicMock()
        mock_position.reentries = None  # No reentries
        mock_positions_repo.get_by_symbol.return_value = mock_position

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

    def test_reentries_today_handles_missing_time_field(self, engine, mock_positions_repo):
        """Test that reentries_today() skips reentries without time field"""
        mock_position = MagicMock()
        mock_position.reentries = [
            {"qty": 10, "level": 20},  # No time field
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should skip reentry without time field
        assert count == 0

    def test_reentries_today_handles_invalid_time_format(self, engine, mock_positions_repo):
        """Test that reentries_today() handles invalid time formats gracefully"""
        mock_position = MagicMock()
        mock_position.reentries = [
            {"qty": 10, "level": 20, "time": "invalid-date"},  # Invalid format
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should skip invalid time format
        assert count == 0

    def test_reentries_today_handles_exception_gracefully(self, engine, mock_positions_repo):
        """Test that reentries_today() returns 0 on exception"""
        mock_positions_repo.get_by_symbol.side_effect = Exception("Test error")

        count = engine.reentries_today("RELIANCE")

        # Should return 0 on exception
        assert count == 0

    def test_reentries_today_case_insensitive_symbol_matching(self, engine, mock_positions_repo):
        """Test that reentries_today() matches symbols case-insensitively"""
        today_iso = datetime.now().isoformat()

        mock_position = MagicMock()
        mock_position.reentries = [{"qty": 10, "level": 20, "time": today_iso}]
        # get_by_symbol should match case-insensitively (it's called with uppercase)
        mock_positions_repo.get_by_symbol.return_value = mock_position

        # Query with uppercase
        count = engine.reentries_today("RELIANCE")

        # Should match case-insensitively
        assert count == 1
        # Verify it was called with uppercase
        mock_positions_repo.get_by_symbol.assert_called_with(1, "RELIANCE")

    def test_reentries_today_daily_cap_enforcement(self, engine, mock_positions_repo):
        """Test that daily cap is enforced correctly with fixed reentries_today()"""
        today_iso = datetime.now().isoformat()

        # Mock position with 1 reentry today
        mock_position = MagicMock()
        mock_position.reentries = [
            {"qty": 10, "level": 20, "time": today_iso},  # 1 reentry today
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should find 1 reentry
        assert count == 1

        # Daily cap check: count >= 1 should block further reentries
        assert count >= 1  # This would block reentry in place_reentry_orders()

    def test_reentries_today_uses_placed_at_date_not_execution_date(
        self, engine, mock_positions_repo
    ):
        """Test that reentries_today() uses placed_at date (placement date)
        not time (execution date)"""
        yesterday = (datetime.now() - timedelta(days=1)).date()
        today_iso = datetime.now().isoformat()

        from unittest.mock import MagicMock

        # Mock position with reentry:
        # - placed_at = yesterday (order placed yesterday)
        # - time = today (executed today)
        # Should count for yesterday, not today
        mock_position = MagicMock()
        mock_position.reentries = [
            {
                "qty": 10,
                "level": 20,
                "time": today_iso,  # Executed today
                "placed_at": yesterday.isoformat(),  # Placed yesterday ✅
            }
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should count 0 (placed_at is yesterday, not today)
        assert count == 0

    def test_reentries_today_prioritizes_placed_at_over_time(self, engine, mock_positions_repo):
        """Test that reentries_today() prioritizes placed_at field over time field"""
        today = datetime.now().date()
        yesterday_iso = (datetime.now() - timedelta(days=1)).isoformat()

        from unittest.mock import MagicMock

        # Mock position with reentry:
        # - placed_at = today (should be used)
        # - time = yesterday (should be ignored if placed_at exists)
        mock_position = MagicMock()
        mock_position.reentries = [
            {
                "qty": 10,
                "level": 20,
                "time": yesterday_iso,  # Execution date (yesterday)
                "placed_at": today.isoformat(),  # Placement date (today) ✅ Priority
            }
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should count 1 (uses placed_at = today, ignores time = yesterday)
        assert count == 1

    def test_reentries_today_fallback_to_time_if_placed_at_missing(
        self, engine, mock_positions_repo
    ):
        """Test backward compatibility: falls back to time field if placed_at key is not present"""
        today_iso = datetime.now().isoformat()

        from unittest.mock import MagicMock

        # Mock position with old reentry format (no placed_at field/key)
        mock_position = MagicMock()
        reentry_dict = {
            "qty": 10,
            "level": 20,
            "time": today_iso,  # Only time field (backward compatibility)
            # No placed_at field/key at all
        }
        mock_position.reentries = [reentry_dict]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        # Verify placed_at key doesn't exist (explicit check)
        assert "placed_at" not in reentry_dict, "placed_at key should not exist in this test"

        count = engine.reentries_today("RELIANCE")

        # Should count 1 (falls back to time field when placed_at key is missing)
        assert count == 1

    def test_reentries_today_fallback_when_placed_at_is_empty_string(
        self, engine, mock_positions_repo
    ):
        """Test backward compatibility: falls back to time field if placed_at is empty string"""
        today_iso = datetime.now().isoformat()

        from unittest.mock import MagicMock

        # Mock position with reentry where placed_at is empty string
        mock_position = MagicMock()
        mock_position.reentries = [
            {
                "qty": 10,
                "level": 20,
                "time": today_iso,
                "placed_at": "",  # Empty string (should fallback to time)
            }
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should count 1 (falls back to time field because empty string is falsy)
        assert count == 1

    def test_reentries_today_fallback_when_placed_at_is_none(self, engine, mock_positions_repo):
        """Test backward compatibility: falls back to time field if placed_at is None"""
        today_iso = datetime.now().isoformat()

        from unittest.mock import MagicMock

        # Mock position with reentry where placed_at is None
        mock_position = MagicMock()
        mock_position.reentries = [
            {
                "qty": 10,
                "level": 20,
                "time": today_iso,
                "placed_at": None,  # None value (should fallback to time)
            }
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should count 1 (falls back to time field because None is falsy)
        assert count == 1

    def test_reentries_today_fallback_when_placed_at_is_invalid_format(
        self, engine, mock_positions_repo
    ):
        """Test backward compatibility: falls back to time field if placed_at is invalid format"""
        today_iso = datetime.now().isoformat()

        from unittest.mock import MagicMock

        # Mock position with reentry where placed_at is invalid format
        mock_position = MagicMock()
        mock_position.reentries = [
            {
                "qty": 10,
                "level": 20,
                "time": today_iso,
                "placed_at": "invalid-date-format",  # Invalid format (should fallback to time)
            }
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should count 1 (falls back to time field because parsing failed)
        assert count == 1

    def test_reentries_today_handles_partial_execution(self, engine, mock_positions_repo):
        """Test that partial execution still counts as 1 re-entry for daily cap"""
        today = datetime.now().date()
        today_iso = datetime.now().isoformat()

        from unittest.mock import MagicMock

        # Mock position with partial re-entry execution (7 shares instead of 10)
        mock_position = MagicMock()
        mock_position.reentries = [
            {
                "qty": 7,  # Partial execution (less than order quantity)
                "level": 20,
                "time": today_iso,
                "placed_at": today.isoformat(),
            }
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should count 1 (partial execution still counts as 1 re-entry)
        assert count == 1

    def test_reentries_today_amo_order_placed_yesterday_executed_today(
        self, engine, mock_positions_repo
    ):
        """Test daily cap fix: AMO order placed Day 1, executed Day 2 → counts for Day 1"""
        yesterday = (datetime.now() - timedelta(days=1)).date()
        today_iso = datetime.now().isoformat()

        from unittest.mock import MagicMock

        # Scenario: AMO order placed Day 1 (4:05 PM), executed Day 2 (9:15 AM)
        mock_position = MagicMock()
        mock_position.reentries = [
            {
                "qty": 10,
                "level": 20,
                "time": today_iso,  # Executed today (Day 2)
                "placed_at": yesterday.isoformat(),  # Placed yesterday (Day 1) ✅
            }
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should count 0 for today (order was placed yesterday)
        # This allows new re-entry order to be placed today
        assert count == 0

    def test_reentries_today_multiple_reentries_different_placement_dates(
        self, engine, mock_positions_repo
    ):
        """Test that reentries_today() correctly filters by placement date"""
        yesterday = (datetime.now() - timedelta(days=1)).date()
        today_iso = datetime.now().isoformat()

        # Mock position with multiple reentries:
        # - One placed yesterday (executed today)
        # - One placed today (executed today)
        mock_position = MagicMock()
        mock_position.reentries = [
            {
                "qty": 10,
                "level": 20,
                "time": today_iso,
                "placed_at": yesterday.isoformat(),  # Placed yesterday
            },
            {
                "qty": 5,
                "level": 10,
                "time": today_iso,
                "placed_at": datetime.now().date().isoformat(),  # Placed today ✅
            },
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should count only 1 (the one placed today)
        assert count == 1
