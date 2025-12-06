"""
Tests for Flaw #7: Sell Order Update Failure Handling

Tests that failed sell order updates are automatically detected and fixed
by the periodic mismatch check in monitor_and_update().
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager


class TestSellOrderUpdateFailureHandling:
    """Test that failed sell order updates are automatically detected and fixed"""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock()
        auth.client = Mock()
        return auth

    @pytest.fixture
    def mock_positions_repo(self):
        """Create mock positions repository"""
        repo = Mock()
        return repo

    @pytest.fixture
    def sell_manager(self, mock_auth, mock_positions_repo):
        """Create SellOrderManager instance with mocked dependencies"""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.positions_repo = mock_positions_repo
            manager.user_id = 1
            manager.orders = Mock()
            manager.get_existing_sell_orders = Mock(return_value={})
            manager.update_sell_order = Mock(return_value=True)
            manager._register_order = Mock()
            manager.active_sell_orders = {}
            return manager

    def test_check_and_fix_sell_order_mismatches_detects_mismatch(
        self, sell_manager, mock_positions_repo
    ):
        """Test that _check_and_fix_sell_order_mismatches detects quantity mismatch"""
        # Setup: Position has 110 shares, sell order has 100 shares (mismatch)
        position = Mock()
        position.quantity = 110.0
        position.closed_at = None

        mock_positions_repo.get_by_symbol = Mock(return_value=position)

        # Active sell order tracked
        sell_manager.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL123",
                "qty": 100,  # Mismatch: position has 110
                "target_price": 9.50,
                "ticker": "RELIANCE.NS",
                "placed_symbol": "RELIANCE-EQ",
            }
        }

        # Broker has sell order with 100 shares
        sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE": {
                    "order_id": "SELL123",
                    "qty": 100,  # Mismatch with position (110)
                    "price": 9.50,
                }
            }
        )

        # Check and fix mismatches
        fixed_count = sell_manager._check_and_fix_sell_order_mismatches()

        # Verify: Mismatch detected and fixed
        assert fixed_count == 1
        assert sell_manager.update_sell_order.called
        update_call = sell_manager.update_sell_order.call_args[1]
        assert update_call["qty"] == 110  # Updated to match position
        assert update_call["symbol"] == "RELIANCE"
        assert update_call["order_id"] == "SELL123"

    def test_check_and_fix_sell_order_mismatches_no_mismatch(
        self, sell_manager, mock_positions_repo
    ):
        """Test that _check_and_fix_sell_order_mismatches doesn't update when quantities match"""
        # Setup: Position and sell order both have 100 shares (no mismatch)
        position = Mock()
        position.quantity = 100.0
        position.closed_at = None

        mock_positions_repo.get_by_symbol = Mock(return_value=position)

        sell_manager.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL123",
                "qty": 100,
                "target_price": 9.50,
                "ticker": "RELIANCE.NS",
                "placed_symbol": "RELIANCE-EQ",
            }
        }

        sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE": {
                    "order_id": "SELL123",
                    "qty": 100,  # Matches position
                    "price": 9.50,
                }
            }
        )

        # Check and fix mismatches
        fixed_count = sell_manager._check_and_fix_sell_order_mismatches()

        # Verify: No mismatch, no update
        assert fixed_count == 0
        assert not sell_manager.update_sell_order.called

    def test_check_and_fix_sell_order_mismatches_handles_closed_position(
        self, sell_manager, mock_positions_repo
    ):
        """Test that _check_and_fix_sell_order_mismatches skips closed positions"""
        # Setup: Position is closed
        position = Mock()
        position.quantity = 100.0
        position.closed_at = datetime.now()  # Position is closed

        mock_positions_repo.get_by_symbol = Mock(return_value=position)

        sell_manager.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL123",
                "qty": 100,
                "target_price": 9.50,
            }
        }

        sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE": {
                    "order_id": "SELL123",
                    "qty": 100,
                    "price": 9.50,
                }
            }
        )

        # Check and fix mismatches
        fixed_count = sell_manager._check_and_fix_sell_order_mismatches()

        # Verify: Closed position skipped, no update
        assert fixed_count == 0
        assert not sell_manager.update_sell_order.called

    def test_check_and_fix_sell_order_mismatches_handles_missing_sell_order(
        self, sell_manager, mock_positions_repo
    ):
        """Test that _check_and_fix_sell_order_mismatches handles missing sell order in broker"""
        # Setup: Position exists, but sell order not found in broker (executed/cancelled)
        position = Mock()
        position.quantity = 100.0
        position.closed_at = None

        mock_positions_repo.get_by_symbol = Mock(return_value=position)

        sell_manager.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL123",
                "qty": 100,
                "target_price": 9.50,
            }
        }

        # Sell order not found in broker (executed/cancelled)
        sell_manager.get_existing_sell_orders = Mock(return_value={})

        # Check and fix mismatches
        fixed_count = sell_manager._check_and_fix_sell_order_mismatches()

        # Verify: Missing sell order skipped, no update
        assert fixed_count == 0
        assert not sell_manager.update_sell_order.called

    def test_check_and_fix_sell_order_mismatches_retries_on_failure(
        self, sell_manager, mock_positions_repo
    ):
        """Test that _check_and_fix_sell_order_mismatches retries on update failure"""
        # Setup: Position has 110 shares, sell order has 100 shares (mismatch)
        position = Mock()
        position.quantity = 110.0
        position.closed_at = None

        mock_positions_repo.get_by_symbol = Mock(return_value=position)

        sell_manager.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL123",
                "qty": 100,
                "target_price": 9.50,
                "ticker": "RELIANCE.NS",
                "placed_symbol": "RELIANCE-EQ",
            }
        }

        sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE": {
                    "order_id": "SELL123",
                    "qty": 100,
                    "price": 9.50,
                }
            }
        )

        # First update attempt fails (broker API error)
        sell_manager.update_sell_order = Mock(return_value=False)

        # Check and fix mismatches
        fixed_count = sell_manager._check_and_fix_sell_order_mismatches()

        # Verify: Update attempted but failed (will retry in next cycle)
        assert fixed_count == 0  # Not fixed yet
        assert sell_manager.update_sell_order.called  # But update was attempted
        update_call = sell_manager.update_sell_order.call_args[1]
        assert update_call["qty"] == 110  # Correct quantity attempted

    def test_check_and_fix_sell_order_mismatches_handles_multiple_mismatches(
        self, sell_manager, mock_positions_repo
    ):
        """Test that _check_and_fix_sell_order_mismatches handles multiple mismatches"""
        # Setup: Multiple positions with mismatches
        position1 = Mock()
        position1.quantity = 110.0
        position1.closed_at = None

        position2 = Mock()
        position2.quantity = 75.0
        position2.closed_at = None

        def get_by_symbol_side_effect(user_id, symbol):
            if symbol == "RELIANCE":
                return position1
            elif symbol == "TATASTEEL":
                return position2
            return None

        mock_positions_repo.get_by_symbol = Mock(side_effect=get_by_symbol_side_effect)

        sell_manager.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL123",
                "qty": 100,  # Mismatch: position has 110
                "target_price": 9.50,
                "ticker": "RELIANCE.NS",
                "placed_symbol": "RELIANCE-EQ",
            },
            "TATASTEEL": {
                "order_id": "SELL456",
                "qty": 50,  # Mismatch: position has 75
                "target_price": 8.00,
                "ticker": "TATASTEEL.NS",
                "placed_symbol": "TATASTEEL-EQ",
            },
        }

        sell_manager.get_existing_sell_orders = Mock(
            return_value={
                "RELIANCE": {
                    "order_id": "SELL123",
                    "qty": 100,
                    "price": 9.50,
                },
                "TATASTEEL": {
                    "order_id": "SELL456",
                    "qty": 50,
                    "price": 8.00,
                },
            }
        )

        # Check and fix mismatches
        fixed_count = sell_manager._check_and_fix_sell_order_mismatches()

        # Verify: Both mismatches detected and fixed
        assert fixed_count == 2
        assert sell_manager.update_sell_order.call_count == 2

        # Verify first update
        first_call = sell_manager.update_sell_order.call_args_list[0][1]
        assert first_call["qty"] == 110
        assert first_call["symbol"] == "RELIANCE"

        # Verify second update
        second_call = sell_manager.update_sell_order.call_args_list[1][1]
        assert second_call["qty"] == 75
        assert second_call["symbol"] == "TATASTEEL"

    def test_check_and_fix_sell_order_mismatches_handles_exceptions_gracefully(
        self, sell_manager, mock_positions_repo
    ):
        """Test that _check_and_fix_sell_order_mismatches handles exceptions gracefully"""
        # Setup: Exception when getting position
        mock_positions_repo.get_by_symbol = Mock(side_effect=Exception("Database error"))

        sell_manager.active_sell_orders = {
            "RELIANCE": {
                "order_id": "SELL123",
                "qty": 100,
                "target_price": 9.50,
            }
        }

        # Check and fix mismatches (should not raise exception)
        fixed_count = sell_manager._check_and_fix_sell_order_mismatches()

        # Verify: Exception handled gracefully, no update attempted
        assert fixed_count == 0
        assert not sell_manager.update_sell_order.called

