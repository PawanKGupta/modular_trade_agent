"""
Comprehensive tests for all re-entry edge cases.

This test file covers all 42 edge cases identified in the re-entry implementation:
- Reset Detection & Cycles (4 cases)
- Level Progression & Skipping (5 cases)
- Initial Entry Blocking (4 cases)
- Reset Behavior (5 cases)
- Cycle-Based Blocking (4 cases)
- levels_taken Updates (4 cases)
- Order Placement & Execution (4 cases)
- Service Restart Scenarios (4 cases)
- Complex Scenarios (8 cases)
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine


@pytest.fixture
def mock_auth():
    """Mock authentication"""
    mock_auth_instance = Mock()
    mock_auth_instance.is_authenticated.return_value = True
    return mock_auth_instance


@pytest.fixture
def engine(mock_auth):
    """Create AutoTradeEngine instance"""
    with patch(
        "modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth", return_value=mock_auth
    ):
        return AutoTradeEngine(auth=mock_auth, user_id=1)


@pytest.fixture
def mock_position():
    """Create a mock position"""
    position = Mock()
    position.entry_rsi = None
    position.reentries = None
    position.user_id = 1
    position.symbol = "RELIANCE-EQ"  # Full symbol after migration
    return position


class TestResetDetectionAndCycles:
    """Category 1: Reset Detection & Cycles (4 cases)"""

    def test_edge_case_1_1_service_restart_between_rsi_above_and_below_30(
        self, engine, mock_position
    ):
        """Edge Case 1.1: Service restart between RSI > 30 and < 30"""
        # Setup: Service stopped after RSI > 30, restarted when RSI < 30
        # Position has last_rsi_above_30 stored from previous run
        now = datetime.now()
        yesterday = now - timedelta(days=1)

        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": yesterday.isoformat(),  # Stored from previous run
                "last_rsi_value": 32.0,
            },
            "reentries": [],
        }

        # Current RSI < 30 (service restarted)
        current_rsi = 25.0
        entry_rsi = 28.0

        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )

        # Should detect reset on startup
        assert metadata_updates.get("current_cycle") == 1  # Incremented from 0
        assert metadata_updates.get("last_rsi_above_30") is None  # Cleared
        assert next_level == 30  # Reset triggers level 30

    def test_edge_case_1_2_multiple_reset_cycles(self, engine, mock_position):
        """Edge Case 1.2: Multiple reset cycles"""
        # Cycle 0: RSI > 30 → < 30 (reset 1)
        # Cycle 1: RSI > 30 → < 30 (reset 2)

        # First reset: Cycle 0 → Cycle 1
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=2)).isoformat(),
                "last_rsi_value": 32.0,
            },
            "reentries": [{"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0}],
        }

        current_rsi = 25.0
        entry_rsi = 28.0

        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )

        # First reset detected
        assert metadata_updates.get("current_cycle") == 1

        # Second reset: Cycle 1 → Cycle 2
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 1,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=1)).isoformat(),
                "last_rsi_value": 33.0,
            },
            "reentries": [
                {"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0},
                {"qty": 10, "level": 30, "cycle": 1, "rsi": 25.0},
            ],
        }

        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )

        # Second reset detected
        assert metadata_updates.get("current_cycle") == 2

    def test_edge_case_1_3_reset_in_same_day(self, engine, mock_position):
        """Edge Case 1.3: Reset in same day"""
        # RSI > 30 in morning, < 30 in afternoon (same day)

        # Morning: RSI > 30
        current_rsi = 32.0
        entry_rsi = 28.0

        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )

        # Should store last_rsi_above_30
        assert metadata_updates.get("last_rsi_above_30") is not None
        assert next_level is None  # No re-entry when RSI > 30

        # Afternoon: RSI < 30 (same day)
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": metadata_updates.get("last_rsi_above_30"),
                "last_rsi_value": 32.0,
            },
            "reentries": [],
        }

        current_rsi = 25.0
        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )

        # Should detect reset same day
        assert metadata_updates.get("current_cycle") == 1
        assert next_level == 30

    def test_edge_case_1_4_multiple_resets_same_cycle(self, engine, mock_position):
        """Edge Case 1.4: Multiple resets, same cycle (no reset between)"""
        # RSI > 30, < 30, > 30, < 30 (no reset between)
        # Only first reset should increment cycle

        # First: RSI > 30
        current_rsi = 32.0
        entry_rsi = 28.0

        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )
        assert metadata_updates.get("last_rsi_above_30") is not None

        # Second: RSI < 30 (first reset)
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": metadata_updates.get("last_rsi_above_30"),
                "last_rsi_value": 32.0,
            },
            "reentries": [],
        }

        current_rsi = 25.0
        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )
        assert metadata_updates.get("current_cycle") == 1
        assert metadata_updates.get("last_rsi_above_30") is None  # Cleared

        # Third: RSI > 30 again (store new timestamp)
        current_rsi = 32.0
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 1,
                "last_rsi_above_30": None,  # Cleared from previous reset
                "last_rsi_value": 25.0,
            },
            "reentries": [],
        }

        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )
        assert metadata_updates.get("last_rsi_above_30") is not None  # New timestamp stored

        # Fourth: RSI < 30 again (second reset)
        current_rsi = 25.0
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 1,
                "last_rsi_above_30": metadata_updates.get("last_rsi_above_30"),
                "last_rsi_value": 32.0,
            },
            "reentries": [],
        }

        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )
        assert metadata_updates.get("current_cycle") == 2  # Incremented again


class TestLevelProgressionAndSkipping:
    """Category 2: Level Progression & Skipping (5 cases)"""

    def test_edge_case_2_1_normal_sequential_progression(self, engine, mock_position):
        """Edge Case 2.1: Normal sequential progression (30 → 20 → 10)"""
        entry_rsi = 25.0  # Entry at RSI < 30

        # Step 1: RSI < 20 (should trigger level 20)
        current_rsi = 18.0
        mock_position.reentries = None  # No re-entries yet

        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)
        assert next_level == 20

        # Step 2: After level 20 executed, RSI < 10 (should trigger level 10)
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [{"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0}],
        }

        current_rsi = 8.0
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)
        assert next_level == 10

    def test_edge_case_2_2_skip_level_20_to_10(self, engine, mock_position):
        """Edge Case 2.2: Skip level 20 → level 10"""
        entry_rsi = 29.0  # Entry at RSI < 30
        current_rsi = 8.0  # RSI drops directly to < 10

        mock_position.reentries = None  # No re-entries yet

        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Should allow skipping level 20, go directly to level 10
        assert next_level == 10

    def test_edge_case_2_3_backtrack_prevention(self, engine, mock_position):
        """Edge Case 2.3: Backtrack prevention"""
        entry_rsi = 29.0  # Entry at RSI < 30

        # First: Skip to level 10
        current_rsi = 8.0
        mock_position.reentries = None

        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)
        assert next_level == 10

        # After level 10 executed, try to backtrack to level 20
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [{"qty": 10, "level": 10, "cycle": 0, "rsi": 8.0}],
        }

        current_rsi = 12.0  # RSI between 10 and 20
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Should block backtrack to level 20
        assert next_level is None

    def test_edge_case_2_4_skip_level_30_to_20(self, engine, mock_position):
        """Edge Case 2.4: Skip level 30 → level 20"""
        entry_rsi = 35.0  # Entry at RSI >= 30
        current_rsi = 18.0  # RSI < 20

        mock_position.reentries = None

        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Should allow skipping level 30, go directly to level 20
        assert next_level == 20

    def test_edge_case_2_5_skip_level_30_to_10(self, engine, mock_position):
        """Edge Case 2.5: Skip level 30 → level 10"""
        entry_rsi = 35.0  # Entry at RSI >= 30
        current_rsi = 8.0  # RSI < 10

        mock_position.reentries = None

        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Should allow skipping level 30 and 20, go directly to level 10
        assert next_level == 10


class TestInitialEntryBlocking:
    """Category 3: Initial Entry Blocking (4 cases)"""

    def test_edge_case_3_1_initial_entry_at_rsi_lt_30_blocks_level_30(self, engine, mock_position):
        """Edge Case 3.1: Initial entry at RSI < 30 blocks level 30 re-entry"""
        mock_position.entry_rsi = 25.0  # Entry at RSI < 30
        mock_position.reentries = None

        # Mock positions_repo
        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should block re-entry at level 30
        assert engine.has_reentry_at_level("RELIANCE", 30) is True

    def test_edge_case_3_2_initial_entry_at_rsi_lt_20_blocks_level_20(self, engine, mock_position):
        """Edge Case 3.2: Initial entry at RSI < 20 blocks level 20 re-entry"""
        mock_position.entry_rsi = 18.0  # Entry at RSI < 20
        mock_position.reentries = None

        # Mock positions_repo to return our mock_position
        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should block re-entry at level 20
        assert engine.has_reentry_at_level("RELIANCE", 20) is True

    def test_edge_case_3_3_initial_entry_at_rsi_lt_10_blocks_level_10(self, engine, mock_position):
        """Edge Case 3.3: Initial entry at RSI < 10 blocks level 10 re-entry"""
        mock_position.entry_rsi = 9.0  # Entry at RSI < 10
        mock_position.reentries = None

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should block re-entry at level 10
        assert engine.has_reentry_at_level("RELIANCE", 10) is True

    def test_edge_case_3_4_reset_allows_reentry_at_initial_level(self, engine, mock_position):
        """Edge Case 3.4: Reset allows re-entry at initial level"""
        mock_position.entry_rsi = 18.0  # Entry at RSI < 20
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 1},  # Reset happened (cycle 1)
            "reentries": [],
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should allow re-entry at level 20 after reset (allow_reset=True)
        assert engine.has_reentry_at_level("RELIANCE", 20, allow_reset=True) is False


class TestResetBehavior:
    """Category 4: Reset Behavior (5 cases)"""

    def test_edge_case_4_1_reset_triggers_level_30(self, engine, mock_position):
        """Edge Case 4.1: Reset triggers level 30"""
        entry_rsi = 25.0
        current_rsi = 29.0  # RSI < 30

        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=1)).isoformat(),
                "last_rsi_value": 32.0,
            },
            "reentries": [],
        }

        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Reset should trigger level 30
        assert next_level == 30

    def test_edge_case_4_2_reset_triggers_level_20(self, engine, mock_position):
        """Edge Case 4.2: Reset triggers level 20"""
        entry_rsi = 18.0
        current_rsi = 18.0  # RSI < 20

        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=1)).isoformat(),
                "last_rsi_value": 32.0,
            },
            "reentries": [],
        }

        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Reset should trigger level 20 (not 30)
        assert next_level == 20

    def test_edge_case_4_3_reset_triggers_level_10(self, engine, mock_position):
        """Edge Case 4.3: Reset triggers level 10"""
        entry_rsi = 8.0
        current_rsi = 8.0  # RSI < 10

        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=1)).isoformat(),
                "last_rsi_value": 32.0,
            },
            "reentries": [],
        }

        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Reset should trigger level 10 (not 30 or 20)
        assert next_level == 10

    def test_edge_case_4_4_reset_at_rsi_between_20_30(self, engine, mock_position):
        """Edge Case 4.4: Reset at RSI between 20-30"""
        entry_rsi = 25.0
        current_rsi = 21.0  # RSI between 20 and 30

        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=1)).isoformat(),
                "last_rsi_value": 32.0,
            },
            "reentries": [],
        }

        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Reset should trigger level 30 (RSI 21 < 30, not < 20)
        assert next_level == 30

    def test_edge_case_4_5_reset_at_rsi_between_10_20(self, engine, mock_position):
        """Edge Case 4.5: Reset at RSI between 10-20"""
        entry_rsi = 18.0
        current_rsi = 11.0  # RSI between 10 and 20

        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=1)).isoformat(),
                "last_rsi_value": 32.0,
            },
            "reentries": [],
        }

        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Reset should trigger level 20 (RSI 11 < 20, not < 10)
        assert next_level == 20


class TestCycleBasedBlocking:
    """Category 5: Cycle-Based Blocking (4 cases)"""

    def test_edge_case_5_1_same_level_in_same_cycle(self, engine, mock_position):
        """Edge Case 5.1: Same level in same cycle"""
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [{"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0}],
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should block duplicate re-entry at level 20 in same cycle
        assert engine.has_reentry_at_level("RELIANCE", 20) is True

    def test_edge_case_5_2_same_level_in_different_cycle(self, engine, mock_position):
        """Edge Case 5.2: Same level in different cycle"""
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 1},  # Current cycle is 1
            "reentries": [
                {"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0}  # Old re-entry in cycle 0
            ],
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should allow re-entry at level 20 in cycle 1 (different cycle)
        assert engine.has_reentry_at_level("RELIANCE", 20) is False

    def test_edge_case_5_3_old_reentries_without_cycle(self, engine, mock_position):
        """Edge Case 5.3: Old re-entries without cycle field"""
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 1},
            "reentries": [{"qty": 10, "level": 20, "rsi": 18.0}],  # Old format, no cycle field
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should assume cycle 0 for old re-entries, allow in cycle 1
        assert engine.has_reentry_at_level("RELIANCE", 20) is False

    def test_edge_case_5_4_multiple_cycles_same_level(self, engine, mock_position):
        """Edge Case 5.4: Multiple cycles, same level"""
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 2},
            "reentries": [
                {"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0},
                {"qty": 10, "level": 20, "cycle": 1, "rsi": 18.0},
            ],
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should allow re-entry at level 20 in cycle 2 (different cycle)
        assert engine.has_reentry_at_level("RELIANCE", 20) is False


class TestLevelsTakenUpdates:
    """Category 6: levels_taken Updates (4 cases)"""

    def test_edge_case_6_1_levels_taken_from_executed_reentries(self, engine, mock_position):
        """Edge Case 6.1: levels_taken updated from executed re-entries"""
        entry_rsi = 25.0
        current_rsi = 8.0  # RSI < 10

        # Position has executed re-entry at level 20
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [{"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0}],
        }

        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Should detect level 20 is taken, allow level 10
        assert next_level == 10

    def test_edge_case_6_2_intermediate_levels_marked_when_skip(self, engine, mock_position):
        """Edge Case 6.2: Intermediate levels marked when skip"""
        entry_rsi = 29.0
        current_rsi = 8.0  # RSI < 10

        # Position has executed re-entry at level 10 (skipped 20)
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [{"qty": 10, "level": 10, "cycle": 0, "rsi": 8.0}],
        }

        current_rsi = 12.0  # RSI between 10 and 20
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Should block backtrack to level 20 (intermediate level marked)
        assert next_level is None

    def test_edge_case_6_3_levels_taken_persists_across_days(self, engine, mock_position):
        """Edge Case 6.3: levels_taken persists across days"""
        entry_rsi = 25.0

        # Position has re-entry from yesterday
        yesterday = datetime.now() - timedelta(days=1)
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [
                {"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0, "time": yesterday.isoformat()}
            ],
        }

        current_rsi = 8.0  # RSI < 10
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Should still detect level 20 is taken (persists across days)
        assert next_level == 10

    def test_edge_case_6_4_levels_taken_reset_on_new_cycle(self, engine, mock_position):
        """Edge Case 6.4: levels_taken reset on new cycle"""
        entry_rsi = 25.0

        # Position has re-entries in cycle 0
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=1)).isoformat(),
                "last_rsi_value": 32.0,
            },
            "reentries": [
                {"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0},
                {"qty": 10, "level": 10, "cycle": 0, "rsi": 8.0},
            ],
        }

        current_rsi = 29.0  # RSI < 30 (reset condition)
        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )

        # Reset should increment cycle and allow level 30 again
        assert metadata_updates.get("current_cycle") == 1
        assert next_level == 30


class TestBackwardCompatibility:
    """Additional: Backward Compatibility Tests"""

    def test_reentries_today_handles_old_format(self, engine, mock_position):
        """Test that reentries_today handles old format (list)"""
        today = datetime.now().date()

        # Old format: reentries is a list
        mock_position.reentries = [
            {
                "qty": 10,
                "level": 20,
                "rsi": 18.0,
                "placed_at": today.isoformat(),
                "time": datetime.now().isoformat(),
            }
        ]

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")
        assert count == 1

    def test_reentries_today_handles_new_format(self, engine, mock_position):
        """Test that reentries_today handles new format (dict with metadata)"""
        today = datetime.now().date()

        # New format: reentries is a dict with metadata
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": None,
                "last_rsi_value": 18.0,
            },
            "reentries": [
                {
                    "qty": 10,
                    "level": 20,
                    "cycle": 0,
                    "rsi": 18.0,
                    "placed_at": today.isoformat(),
                    "time": datetime.now().isoformat(),
                }
            ],
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        count = engine.reentries_today("RELIANCE")
        assert count == 1


class TestOrderPlacementAndExecution:
    """Category 7: Order Placement & Execution (4 cases)"""

    def test_edge_case_7_1_partial_execution(self, engine, mock_position):
        """Edge Case 7.1: Partial execution"""
        # Position has partial re-entry execution (5 out of 10 shares)
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [{"qty": 5, "level": 20, "cycle": 0, "rsi": 18.0}],  # Partial execution
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should still count as 1 re-entry (level 20 is taken)
        assert engine.has_reentry_at_level("RELIANCE", 20) is True

    def test_edge_case_7_2_amo_placement_vs_execution_date(self, engine, mock_position):
        """Edge Case 7.2: AMO placement vs execution date"""
        # Order placed Day 1, executed Day 2
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [
                {
                    "qty": 10,
                    "level": 20,
                    "cycle": 0,
                    "rsi": 18.0,
                    "placed_at": yesterday.isoformat(),  # Placed yesterday
                    "time": datetime.now().isoformat(),  # Executed today
                }
            ],
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # reentries_today should count based on placed_at (yesterday), not execution date
        count = engine.reentries_today("RELIANCE")
        assert count == 0  # Not today (placed yesterday)

    def test_edge_case_7_3_order_cancelled_failed(self, engine, mock_position):
        """Edge Case 7.3: Order cancelled/failed"""
        # Only executed orders update positions table
        # Cancelled/failed orders don't appear in reentries array
        mock_position.reentries = None  # No executed re-entries

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should not count cancelled/failed orders
        count = engine.reentries_today("RELIANCE")
        assert count == 0

    def test_edge_case_7_4_retry_failed_order(self, engine, mock_position):
        """Edge Case 7.4: Retry failed order"""
        # First order failed, retried next day
        today = datetime.now().date()

        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [
                {
                    "qty": 10,
                    "level": 20,
                    "cycle": 0,
                    "rsi": 18.0,
                    "placed_at": today.isoformat(),  # Retry placed today
                }
            ],
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should count retry order (new placed_at date)
        count = engine.reentries_today("RELIANCE")
        assert count == 1


class TestServiceRestartScenarios:
    """Category 8: Service Restart Scenarios (4 cases)"""

    def test_edge_case_8_1_service_restart_after_rsi_above_30(self, engine, mock_position):
        """Edge Case 8.1: Service restart after RSI > 30"""
        # Service stopped after RSI > 30, metadata stored in DB
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=2)).isoformat(),
                "last_rsi_value": 32.0,
            },
            "reentries": [],
        }

        # Service restarts, RSI still < 30
        current_rsi = 25.0
        entry_rsi = 28.0

        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )

        # Should detect reset on startup
        assert metadata_updates.get("current_cycle") == 1
        assert next_level == 30

    def test_edge_case_8_2_service_restart_multiple_times(self, engine, mock_position):
        """Edge Case 8.2: Service restart multiple times"""
        # Multiple restarts, RSI fluctuates, cycle tracking persists
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 2,  # Persisted from previous runs
                "last_rsi_above_30": None,
                "last_rsi_value": 25.0,
            },
            "reentries": [
                {"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0},
                {"qty": 10, "level": 30, "cycle": 1, "rsi": 25.0},
            ],
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Cycle should persist across restarts
        cycle_meta = engine._get_position_cycle_metadata(mock_position)
        assert cycle_meta.get("current_cycle") == 2

    def test_edge_case_8_3_fresh_start_duplicate_check(self, engine, mock_position):
        """Edge Case 8.3: Service starts fresh, finds duplicate"""
        # Service starts, finds RSI < 20, places order, restarts, finds RSI < 20 again
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [
                {"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0}  # Placed before restart
            ],
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should block duplicate (same cycle)
        assert engine.has_reentry_at_level("RELIANCE", 20) is True

    def test_edge_case_8_4_service_starts_at_915_executes_at_916(self, engine, mock_position):
        """Edge Case 8.4: Service starts at 9:15 AM, places and executes at 9:16 AM"""
        # Service starts, finds RSI < 20, places and executes quickly
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [
                {
                    "qty": 10,
                    "level": 20,
                    "cycle": 0,
                    "rsi": 18.0,
                    "placed_at": datetime.now().date().isoformat(),
                    "time": datetime.now().isoformat(),
                }
            ],
        }

        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position

        # Should count as 1 re-entry
        count = engine.reentries_today("RELIANCE")
        assert count == 1


class TestComplexScenarios:
    """Category 9: Complex Scenarios (8 cases)"""

    def test_edge_case_9_1_complex_multi_cycle_pattern(self, engine, mock_position):
        """Edge Case 9.1: Complex multi-cycle pattern"""
        # entry_rsi=25, rsi->18, rsi->8, rsi->35, rsi->29, rsi->9, rsi->31, rsi->21, rsi->11
        entry_rsi = 25.0

        # Day 1: RSI = 18 (place level 20)
        current_rsi = 18.0
        mock_position.reentries = None
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)
        assert next_level == 20

        # Day 2: RSI = 8 (place level 10)
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [{"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0}],
        }
        current_rsi = 8.0
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)
        assert next_level == 10

        # Day 4: RSI = 29 (reset, place level 30)
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=1)).isoformat(),
                "last_rsi_value": 35.0,
            },
            "reentries": [
                {"qty": 10, "level": 20, "cycle": 0, "rsi": 18.0},
                {"qty": 10, "level": 10, "cycle": 0, "rsi": 8.0},
            ],
        }
        current_rsi = 29.0
        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )
        assert metadata_updates.get("current_cycle") == 1
        assert next_level == 30

    def test_edge_case_9_2_rsi_oscillating_at_30(self, engine, mock_position):
        """Edge Case 9.2: RSI oscillating at 30"""
        entry_rsi = 29.0

        # RSI = 30 (no reset, RSI must be > 30)
        current_rsi = 30.0
        mock_position.reentries = None
        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )

        # RSI = 30 is not > 30, so no reset flag stored
        assert next_level is None
        assert metadata_updates.get("last_rsi_above_30") is None

        # RSI = 29 (no reset, no last_rsi_above_30)
        current_rsi = 29.0
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Should block level 30 (initial entry check)
        engine.positions_repo = Mock()
        engine.positions_repo.get_by_symbol.return_value = mock_position
        mock_position.entry_rsi = 29.0
        assert engine.has_reentry_at_level("RELIANCE", 30) is True

    def test_edge_case_9_3_skip_then_reset(self, engine, mock_position):
        """Edge Case 9.3: Skip then reset"""
        entry_rsi = 25.0

        # Skip to level 10
        current_rsi = 8.0
        mock_position.reentries = None
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)
        assert next_level == 10

        # Reset
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=1)).isoformat(),
                "last_rsi_value": 35.0,
            },
            "reentries": [{"qty": 10, "level": 10, "cycle": 0, "rsi": 8.0}],
        }
        current_rsi = 18.0
        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )
        assert metadata_updates.get("current_cycle") == 1
        assert next_level == 20  # Reset triggers appropriate level

    def test_edge_case_9_4_entry_lt_20_then_reset(self, engine, mock_position):
        """Edge Case 9.4: Entry < 20, then reset"""
        entry_rsi = 18.0

        # First re-entry at level 10
        current_rsi = 8.0
        mock_position.reentries = None
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)
        assert next_level == 10

        # Reset
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": (datetime.now() - timedelta(hours=1)).isoformat(),
                "last_rsi_value": 35.0,
            },
            "reentries": [{"qty": 10, "level": 10, "cycle": 0, "rsi": 8.0}],
        }
        current_rsi = 18.0
        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )
        assert metadata_updates.get("current_cycle") == 1
        assert next_level == 20  # Reset allows level 20 (allow_reset=True)

    def test_edge_case_9_5_entry_lt_10(self, engine, mock_position):
        """Edge Case 9.5: Entry < 10"""
        entry_rsi = 9.0

        # All levels should be marked as taken from entry
        current_rsi = 8.0
        mock_position.reentries = None
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Should return None (all levels taken, need reset)
        assert next_level is None

    def test_edge_case_9_6_rsi_equal_30_no_reset(self, engine, mock_position):
        """Edge Case 9.6: RSI = 30 (no reset)"""
        entry_rsi = 29.0

        # RSI = 30 (not > 30, so no reset flag)
        current_rsi = 30.0
        mock_position.reentries = None
        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )

        # RSI = 30 is not > 30, so no reset flag stored
        # The code checks `if current_rsi > 30`, so RSI = 30 won't trigger reset
        assert next_level is None
        assert metadata_updates.get("last_rsi_above_30") is None

    def test_edge_case_9_7_rsi_above_30_with_reset(self, engine, mock_position):
        """Edge Case 9.7: RSI > 30 (with reset)"""
        entry_rsi = 29.0

        # RSI > 30 (store reset flag)
        current_rsi = 31.0
        mock_position.reentries = None
        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )
        assert metadata_updates.get("last_rsi_above_30") is not None

        # RSI < 30 (reset detected)
        mock_position.reentries = {
            "_cycle_metadata": {
                "current_cycle": 0,
                "last_rsi_above_30": metadata_updates.get("last_rsi_above_30"),
                "last_rsi_value": 31.0,
            },
            "reentries": [],
        }
        current_rsi = 11.0
        next_level, metadata_updates = engine._determine_reentry_level(
            entry_rsi, current_rsi, mock_position
        )
        assert metadata_updates.get("current_cycle") == 1
        assert next_level == 20  # Reset triggers appropriate level (11 < 20)

    def test_edge_case_9_8_skip_level_then_backtrack_attempt(self, engine, mock_position):
        """Edge Case 9.8: Skip level, then backtrack attempt"""
        entry_rsi = 29.0

        # Skip to level 10
        current_rsi = 8.0
        mock_position.reentries = None
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)
        assert next_level == 10

        # After level 10 executed, try to backtrack to level 20
        mock_position.reentries = {
            "_cycle_metadata": {"current_cycle": 0},
            "reentries": [{"qty": 10, "level": 10, "cycle": 0, "rsi": 8.0}],
        }
        current_rsi = 12.0  # RSI between 10 and 20
        next_level, _ = engine._determine_reentry_level(entry_rsi, current_rsi, mock_position)

        # Should block backtrack to level 20
        assert next_level is None
