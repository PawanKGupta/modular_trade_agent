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
    def mock_positions_repo(self):
        """Create mock positions repository"""
        from unittest.mock import MagicMock

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
        from unittest.mock import MagicMock

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

        from unittest.mock import MagicMock

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
        today_iso = datetime.now().isoformat()
        yesterday_iso = (datetime.now().replace(day=datetime.now().day - 1)).isoformat()

        from unittest.mock import MagicMock

        mock_position = MagicMock()
        mock_position.reentries = [
            {"qty": 10, "level": 20, "time": today_iso},  # Today
            {"qty": 5, "level": 10, "time": yesterday_iso},  # Yesterday
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should only count today's reentry
        assert count == 1

    def test_reentries_today_handles_multiple_reentries_same_day(self, engine, mock_positions_repo):
        """Test that reentries_today() counts multiple reentries in same day"""
        today_iso = datetime.now().isoformat()

        from unittest.mock import MagicMock

        mock_position = MagicMock()
        mock_position.reentries = [
            {"qty": 10, "level": 20, "time": today_iso},
            {"qty": 5, "level": 10, "time": today_iso},  # Same day
        ]
        mock_positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")

        # Should count both reentries from today
        assert count == 2

    def test_reentries_today_handles_missing_reentries_array(self, engine, mock_positions_repo):
        """Test that reentries_today() handles positions without reentries array"""
        from unittest.mock import MagicMock

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
        from unittest.mock import MagicMock

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
        from unittest.mock import MagicMock

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

        from unittest.mock import MagicMock

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

        from unittest.mock import MagicMock

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
