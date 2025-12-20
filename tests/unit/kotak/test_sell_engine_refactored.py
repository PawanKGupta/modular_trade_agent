#!/usr/bin/env python3
"""
Tests for refactored sell_engine methods (Phase 1 refactoring)
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager


class TestRefactoredSellEngineMethods:
    """Test refactored methods in SellOrderManager"""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock(spec=KotakNeoAuth)
        auth.client = Mock()
        return auth

    @pytest.fixture
    def sell_manager(self, mock_auth):
        """Create SellOrderManager instance"""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            # Mock the orders object properly
            manager.orders = Mock()
            return manager

    def test_detect_manual_sells_no_orders(self, sell_manager):
        """Test _detect_manual_sells with no executed orders"""
        sell_manager.orders.get_executed_orders.return_value = []
        result = sell_manager._detect_manual_sells()
        assert result == {}

    def test_detect_manual_sells_with_bot_order(self, sell_manager):
        """Test _detect_manual_sells ignores bot orders"""
        # Setup: bot order tracked
        sell_manager.active_sell_orders = {"RELIANCE": {"order_id": "12345", "qty": 10}}

        # Executed order matches bot order ID
        executed_orders = [
            {"nOrdNo": "12345", "trdSym": "RELIANCE-EQ", "trnsTp": "S", "qty": 10, "avgPrc": 2500.0}
        ]
        sell_manager.orders.get_executed_orders.return_value = executed_orders

        result = sell_manager._detect_manual_sells()
        assert result == {}  # Should be empty (bot order, not manual)

    def test_detect_manual_sells_with_manual_order(self, sell_manager):
        """Test _detect_manual_sells detects manual sell"""
        # Setup: bot has different order ID
        sell_manager.active_sell_orders = {"RELIANCE": {"order_id": "99999", "qty": 10}}

        # Executed order has different order ID (manual sell)
        executed_orders = [
            {
                "nOrdNo": "12345",  # Different from bot order
                "trdSym": "RELIANCE-EQ",
                "trnsTp": "S",
                "qty": 5,
                "avgPrc": 2500.0,
            }
        ]
        sell_manager.orders.get_executed_orders.return_value = executed_orders

        result = sell_manager._detect_manual_sells()
        assert "RELIANCE" in result
        assert result["RELIANCE"]["qty"] == 5
        assert len(result["RELIANCE"]["orders"]) == 1
        assert result["RELIANCE"]["orders"][0]["order_id"] == "12345"

    def test_detect_manual_sells_ignores_buy_orders(self, sell_manager):
        """Test _detect_manual_sells ignores BUY orders"""
        executed_orders = [
            {
                "nOrdNo": "12345",
                "trdSym": "RELIANCE-EQ",
                "trnsTp": "B",  # BUY order
                "qty": 10,
                "avgPrc": 2500.0,
            }
        ]
        sell_manager.orders.get_executed_orders.return_value = executed_orders

        result = sell_manager._detect_manual_sells()
        assert result == {}

    def test_is_tracked_order(self, sell_manager):
        """Test _is_tracked_order helper"""
        sell_manager.active_sell_orders = {
            "RELIANCE": {"order_id": "12345"},
            "TCS": {"order_id": "67890"},
        }

        assert sell_manager._is_tracked_order("12345") is True
        assert sell_manager._is_tracked_order("67890") is True
        assert sell_manager._is_tracked_order("99999") is False

    def test_parse_circuit_limits_from_rejection(self, sell_manager):
        """Extract upper/lower circuit from rejection text"""
        rejection = (
            "RMS:Rule: Check circuit limit including square off order exceeds : "
            "Circuit breach, Order Price :34.65, Low Price Range:30.32 High Price Range:33.51"
        )
        limits = sell_manager._parse_circuit_limits_from_rejection(rejection)
        assert limits == {"upper": 33.51, "lower": 30.32}

    def test_remove_rejected_orders_moves_to_waiting_on_circuit_breach(self, sell_manager):
        """When rejection is circuit breach, move symbol to waiting_for_circuit_expansion"""
        sell_manager.active_sell_orders = {
            "TARAPUR": {
                "order_id": "123",
                "target_price": 34.65,
                "qty": 306,
                "ticker": "TARAPUR.NS",
                "placed_symbol": "TARAPUR-BE",
            }
        }

        broker_orders = [
            {
                "nOrdNo": "123",
                "status": "REJECTED",
                "rejRsn": (
                    "RMS:Rule: Check circuit limit including square off order exceeds : "
                    "Circuit breach, Order Price :34.65, Low Price Range:30.32 High Price Range:33.51"
                ),
            }
        ]
        sell_manager.orders.get_orders.return_value = {"data": broker_orders}

        with patch.object(sell_manager, "_remove_from_tracking") as mock_remove:
            sell_manager._remove_rejected_orders()

        waiting = sell_manager.waiting_for_circuit_expansion.get("TARAPUR")
        assert waiting is not None
        assert waiting["upper_circuit"] == 33.51
        assert waiting["lower_circuit"] == 30.32
        assert waiting["ema9_target"] == 34.65
        assert waiting["trade"]["qty"] == 306
        assert waiting["trade"]["placed_symbol"] == "TARAPUR-BE"
        mock_remove.assert_called_once_with("TARAPUR")

    def test_retry_places_order_when_ema9_within_circuit(self, sell_manager):
        """Retry triggers only when EMA9 is within upper circuit"""
        sell_manager.waiting_for_circuit_expansion = {
            "TARAPUR": {
                "upper_circuit": 33.51,
                "lower_circuit": 30.32,
                "ema9_target": 34.65,
                "trade": {
                    "symbol": "TARAPUR",
                    "placed_symbol": "TARAPUR-BE",
                    "ticker": "TARAPUR.NS",
                    "qty": 306,
                },
                "rejection_reason": "Circuit breach",
            }
        }

        sell_manager.get_current_ema9 = Mock(return_value=33.00)  # Within circuit
        sell_manager.place_sell_order = Mock(return_value="SELL-1")
        sell_manager._register_order = Mock()

        retried = sell_manager._check_and_retry_circuit_expansion()

        assert retried == 1
        assert "TARAPUR" not in sell_manager.waiting_for_circuit_expansion
        sell_manager.place_sell_order.assert_called_once()
        sell_manager._register_order.assert_called_once()

    def test_handle_manual_sells_full_exit(self, sell_manager):
        """Test _handle_manual_sells with full exit"""
        # Setup tracked order
        sell_manager.active_sell_orders = {"RELIANCE": {"order_id": "99999", "qty": 10}}

        # Manual sell info (sold all shares)
        manual_sells = {
            "RELIANCE": {"qty": 10, "orders": [{"order_id": "12345", "qty": 10, "price": 2500.0}]}
        }

        # Mock dependencies
        sell_manager.orders.cancel_order = Mock()
        sell_manager._update_trade_history_for_manual_sell = Mock()

        sell_manager._handle_manual_sells(manual_sells)

        # Should cancel bot order
        sell_manager.orders.cancel_order.assert_called_once_with("99999")
        # Should update trade history
        sell_manager._update_trade_history_for_manual_sell.assert_called_once()
        # Should remove from tracking
        assert "RELIANCE" not in sell_manager.active_sell_orders

    def test_handle_manual_sells_partial_exit(self, sell_manager):
        """Test _handle_manual_sells with partial exit"""
        sell_manager.active_sell_orders = {"RELIANCE": {"order_id": "99999", "qty": 10}}

        # Manual sell info (sold partial shares)
        manual_sells = {
            "RELIANCE": {"qty": 5, "orders": [{"order_id": "12345", "qty": 5, "price": 2500.0}]}
        }

        sell_manager.orders.cancel_order = Mock()
        sell_manager._update_trade_history_for_manual_sell = Mock()

        sell_manager._handle_manual_sells(manual_sells)

        # Should cancel bot order
        sell_manager.orders.cancel_order.assert_called_once()
        # Should update trade history
        sell_manager._update_trade_history_for_manual_sell.assert_called_once()
        # Should remove from tracking
        assert "RELIANCE" not in sell_manager.active_sell_orders

    def test_cancel_bot_order_for_manual_sell(self, sell_manager):
        """Test _cancel_bot_order_for_manual_sell"""
        order_info = {"order_id": "12345"}
        sell_manager.orders.cancel_order = Mock()

        sell_manager._cancel_bot_order_for_manual_sell("RELIANCE", order_info)

        sell_manager.orders.cancel_order.assert_called_once_with("12345")

    def test_cancel_bot_order_no_order_id(self, sell_manager):
        """Test _cancel_bot_order_for_manual_sell with no order_id"""
        order_info = {}  # No order_id
        sell_manager.orders.cancel_order = Mock()

        sell_manager._cancel_bot_order_for_manual_sell("RELIANCE", order_info)

        # Should not call cancel_order
        sell_manager.orders.cancel_order.assert_not_called()

    def test_mark_trade_as_closed(self, sell_manager):
        """Test _mark_trade_as_closed"""
        trade = {"entry_price": 2000.0, "status": "open"}
        sell_info = {"orders": [{"qty": 5, "price": 2500.0}, {"qty": 5, "price": 2550.0}]}
        sold_qty = 10

        sell_manager._mark_trade_as_closed(trade, sell_info, sold_qty, "MANUAL_EXIT")

        assert trade["status"] == "closed"
        assert trade["exit_reason"] == "MANUAL_EXIT"
        assert trade["exit_price"] == 2525.0  # Average of (2500*5 + 2550*5) / 10
        assert trade["pnl"] == 5250.0  # (2525 - 2000) * 10
        assert abs(trade["pnl_pct"] - 26.25) < 0.01  # ((2525/2000) - 1) * 100

    def test_calculate_avg_price_from_orders(self, sell_manager):
        """Test _calculate_avg_price_from_orders"""
        orders = [{"qty": 5, "price": 2500.0}, {"qty": 5, "price": 2550.0}]

        avg_price = sell_manager._calculate_avg_price_from_orders(orders)

        assert avg_price == 2525.0  # (2500*5 + 2550*5) / 10

    def test_calculate_avg_price_empty_list(self, sell_manager):
        """Test _calculate_avg_price_from_orders with empty list"""
        avg_price = sell_manager._calculate_avg_price_from_orders([])
        assert avg_price == 0.0

    def test_find_order_in_broker_orders(self, sell_manager):
        """Test _find_order_in_broker_orders"""
        broker_orders = [
            {"nOrdNo": "12345", "trdSym": "RELIANCE-EQ"},
            {"nOrdNo": "67890", "trdSym": "TCS-EQ"},
            {"orderId": "99999", "trdSym": "INFY-EQ"},
        ]

        result = sell_manager._find_order_in_broker_orders("12345", broker_orders)
        assert result is not None
        assert result["nOrdNo"] == "12345"

        result = sell_manager._find_order_in_broker_orders("99999", broker_orders)
        assert result is not None
        assert result["orderId"] == "99999"

        result = sell_manager._find_order_in_broker_orders("00000", broker_orders)
        assert result is None

    def test_remove_from_tracking(self, sell_manager):
        """Test _remove_from_tracking"""
        sell_manager.active_sell_orders = {
            "RELIANCE": {"order_id": "12345"},
            "TCS": {"order_id": "67890"},
        }
        sell_manager.lowest_ema9 = {"RELIANCE": 2500.0, "TCS": 3000.0}

        sell_manager._remove_from_tracking("RELIANCE")

        assert "RELIANCE" not in sell_manager.active_sell_orders
        assert "RELIANCE" not in sell_manager.lowest_ema9
        assert "TCS" in sell_manager.active_sell_orders
        assert "TCS" in sell_manager.lowest_ema9

    def test_remove_rejected_orders(self, sell_manager):
        """Test _remove_rejected_orders"""
        sell_manager.active_sell_orders = {
            "RELIANCE": {"order_id": "12345"},
            "TCS": {"order_id": "67890"},
        }

        # Mock broker orders
        broker_orders = {
            "data": [{"nOrdNo": "12345", "ordSt": "rejected"}, {"nOrdNo": "67890", "ordSt": "open"}]
        }
        sell_manager.orders.get_orders.return_value = broker_orders

        sell_manager._remove_rejected_orders()

        # RELIANCE should be removed (rejected)
        assert "RELIANCE" not in sell_manager.active_sell_orders
        # TCS should remain (not rejected)
        assert "TCS" in sell_manager.active_sell_orders

    def test_remove_rejected_orders_cancelled(self, sell_manager):
        """Test _remove_rejected_orders with cancelled orders"""
        sell_manager.active_sell_orders = {"RELIANCE": {"order_id": "12345"}}

        broker_orders = {"data": [{"nOrdNo": "12345", "ordSt": "cancelled"}]}
        sell_manager.orders.get_orders.return_value = broker_orders

        sell_manager._remove_rejected_orders()

        assert "RELIANCE" not in sell_manager.active_sell_orders

    def test_detect_and_handle_manual_buys(self, sell_manager):
        """Test _detect_and_handle_manual_buys"""
        with patch(
            "modules.kotak_neo_auto_trader.sell_engine.check_manual_buys_of_failed_orders"
        ) as mock_check:
            mock_check.return_value = ["RELIANCE", "TCS"]

            result = sell_manager._detect_and_handle_manual_buys()

            assert result == ["RELIANCE", "TCS"]
            mock_check.assert_called_once_with(sell_manager.history_path, sell_manager.orders)

    def test_detect_and_handle_manual_buys_empty(self, sell_manager):
        """Test _detect_and_handle_manual_buys with no manual buys"""
        with patch(
            "modules.kotak_neo_auto_trader.sell_engine.check_manual_buys_of_failed_orders"
        ) as mock_check:
            mock_check.return_value = []

            result = sell_manager._detect_and_handle_manual_buys()

            assert result == []

    def test_cleanup_rejected_orders_integration(self, sell_manager):
        """Test _cleanup_rejected_orders integration"""
        # Setup
        sell_manager.active_sell_orders = {"RELIANCE": {"order_id": "12345", "qty": 10}}

        # Mock all dependencies
        with (
            patch.object(sell_manager, "_detect_and_handle_manual_buys") as mock_detect_buys,
            patch.object(sell_manager, "_detect_manual_sells") as mock_detect_sells,
            patch.object(sell_manager, "_handle_manual_sells") as mock_handle_sells,
            patch.object(sell_manager, "_remove_rejected_orders") as mock_remove_rejected,
        ):
            mock_detect_buys.return_value = []
            mock_detect_sells.return_value = {}

            sell_manager._cleanup_rejected_orders()

            # Verify all methods called
            mock_detect_buys.assert_called_once()
            mock_detect_sells.assert_called_once()
            mock_remove_rejected.assert_called_once()
            # Should not call handle_manual_sells (empty dict)
            mock_handle_sells.assert_not_called()

    def test_cleanup_rejected_orders_with_manual_sells(self, sell_manager):
        """Test _cleanup_rejected_orders with manual sells detected"""
        with (
            patch.object(sell_manager, "_detect_and_handle_manual_buys") as mock_detect_buys,
            patch.object(sell_manager, "_detect_manual_sells") as mock_detect_sells,
            patch.object(sell_manager, "_handle_manual_sells") as mock_handle_sells,
            patch.object(sell_manager, "_remove_rejected_orders") as mock_remove_rejected,
        ):
            mock_detect_buys.return_value = []
            mock_detect_sells.return_value = {"RELIANCE": {"qty": 5, "orders": []}}

            sell_manager._cleanup_rejected_orders()

            # Should call handle_manual_sells
            mock_handle_sells.assert_called_once_with({"RELIANCE": {"qty": 5, "orders": []}})

    def test_get_active_orders_initializes_lowest_ema9_from_target_price(self, sell_manager):
        """Test that _get_active_orders initializes lowest_ema9 from target_price when syncing from OrderStateManager"""
        # Setup OrderStateManager mock
        mock_state_manager = Mock()
        mock_state_manager.get_active_sell_orders.return_value = {
            "DALBHARAT": {
                "order_id": "251106000008974",
                "target_price": 2095.53,
                "qty": 233,
                "ticker": "DALBHARAT.NS",
            },
            "RELIANCE": {
                "order_id": "12345",
                "target_price": 2500.0,
                "qty": 10,
                "ticker": "RELIANCE.NS",
            },
        }
        sell_manager.state_manager = mock_state_manager
        sell_manager.lowest_ema9 = {}  # Empty initially

        # Call _get_active_orders
        result = sell_manager._get_active_orders()

        # Verify orders synced
        assert "DALBHARAT" in result
        assert "RELIANCE" in result

        # Verify lowest_ema9 initialized from target_price
        assert sell_manager.lowest_ema9["DALBHARAT"] == 2095.53
        assert sell_manager.lowest_ema9["RELIANCE"] == 2500.0

    def test_get_active_orders_skips_zero_target_price(self, sell_manager):
        """Test that _get_active_orders skips initializing lowest_ema9 when target_price is 0"""
        mock_state_manager = Mock()
        mock_state_manager.get_active_sell_orders.return_value = {
            "DALBHARAT": {
                "order_id": "251106000008974",
                "target_price": 0.0,  # Zero price from duplicate bug
                "qty": 233,
                "ticker": "DALBHARAT.NS",
            }
        }
        sell_manager.state_manager = mock_state_manager
        sell_manager.lowest_ema9 = {}

        result = sell_manager._get_active_orders()

        # Order should be synced
        assert "DALBHARAT" in result

        # But lowest_ema9 should NOT be initialized (target_price is 0)
        assert "DALBHARAT" not in sell_manager.lowest_ema9

    def test_check_and_update_single_stock_initializes_lowest_ema9_from_target_price(
        self, sell_manager
    ):
        """Test that _check_and_update_single_stock initializes lowest_ema9 from target_price if not set"""
        order_info = {
            "order_id": "12345",
            "target_price": 2095.53,
            "qty": 233,
            "ticker": "DALBHARAT.NS",
            "placed_symbol": "DALBHARAT-EQ",
        }
        sell_manager.lowest_ema9 = {}  # Empty initially

        # Mock get_current_ema9
        with (
            patch.object(sell_manager, "get_current_ema9", return_value=2095.27),
            patch.object(sell_manager, "round_to_tick_size", return_value=2095.30),
            patch.object(sell_manager, "update_sell_order", return_value=False),
        ):
            result = sell_manager._check_and_update_single_stock("DALBHARAT", order_info, [])

            # Verify lowest_ema9 initialized from target_price
            assert sell_manager.lowest_ema9["DALBHARAT"] == 2095.53

    def test_check_and_update_single_stock_initializes_lowest_ema9_from_current_ema9_when_target_zero(
        self, sell_manager
    ):
        """Test that _check_and_update_single_stock initializes lowest_ema9 from current EMA9 when target_price is 0"""
        order_info = {
            "order_id": "251106000008974",
            "target_price": 0.0,  # Zero price from duplicate bug
            "qty": 233,
            "ticker": "DALBHARAT.NS",
            "placed_symbol": "DALBHARAT-EQ",
        }
        sell_manager.lowest_ema9 = {}  # Empty initially

        current_ema9 = 2095.27
        rounded_ema9 = 2095.30

        # Mock get_current_ema9
        with (
            patch.object(sell_manager, "get_current_ema9", return_value=current_ema9),
            patch.object(sell_manager, "round_to_tick_size", return_value=rounded_ema9),
            patch.object(sell_manager, "update_sell_order", return_value=False),
        ):
            result = sell_manager._check_and_update_single_stock("DALBHARAT", order_info, [])

            # Verify lowest_ema9 initialized from current EMA9 (not target_price)
            assert sell_manager.lowest_ema9["DALBHARAT"] == rounded_ema9

    def test_check_and_update_single_stock_handles_zero_target_price_display(self, sell_manager):
        """Test that _check_and_update_single_stock handles zero target_price for display"""
        order_info = {
            "order_id": "251106000008974",
            "target_price": 0.0,  # Zero price
            "qty": 233,
            "ticker": "DALBHARAT.NS",
            "placed_symbol": "DALBHARAT-EQ",
        }
        sell_manager.lowest_ema9 = {"DALBHARAT": 2095.30}  # Already initialized

        current_ema9 = 2095.27
        rounded_ema9 = 2095.30

        with (
            patch.object(sell_manager, "get_current_ema9", return_value=current_ema9),
            patch.object(sell_manager, "round_to_tick_size", return_value=rounded_ema9),
            patch.object(sell_manager, "update_sell_order", return_value=False),
            patch("modules.kotak_neo_auto_trader.sell_engine.logger") as mock_logger,
        ):
            result = sell_manager._check_and_update_single_stock("DALBHARAT", order_info, [])

            # Verify log was called with correct values
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            # Should show Target=2095.30 (from lowest_ema9), not 0.0
            assert any("Target=Rs 2095.30" in str(call) for call in log_calls)
            assert any("Lowest=Rs 2095.30" in str(call) for call in log_calls)

    def test_check_and_update_single_stock_handles_missing_target_price(self, sell_manager):
        """Test that _check_and_update_single_stock handles missing target_price"""
        order_info = {
            "order_id": "12345",
            # No target_price key
            "qty": 10,
            "ticker": "RELIANCE.NS",
            "placed_symbol": "RELIANCE-EQ",
        }
        sell_manager.lowest_ema9 = {}  # Empty initially

        current_ema9 = 2500.0
        rounded_ema9 = 2500.0

        with (
            patch.object(sell_manager, "get_current_ema9", return_value=current_ema9),
            patch.object(sell_manager, "round_to_tick_size", return_value=rounded_ema9),
            patch.object(sell_manager, "update_sell_order", return_value=False),
        ):
            result = sell_manager._check_and_update_single_stock("RELIANCE", order_info, [])

            # Verify lowest_ema9 initialized from current EMA9
            assert sell_manager.lowest_ema9["RELIANCE"] == rounded_ema9

    def test_check_and_update_single_stock_preserves_existing_lowest_ema9(self, sell_manager):
        """Test that _check_and_update_single_stock doesn't overwrite existing lowest_ema9"""
        order_info = {
            "order_id": "12345",
            "target_price": 2500.0,
            "qty": 10,
            "ticker": "RELIANCE.NS",
            "placed_symbol": "RELIANCE-EQ",
        }
        # Already has lower value
        sell_manager.lowest_ema9 = {"RELIANCE": 2480.0}

        current_ema9 = 2500.0
        rounded_ema9 = 2500.0

        with (
            patch.object(sell_manager, "get_current_ema9", return_value=current_ema9),
            patch.object(sell_manager, "round_to_tick_size", return_value=rounded_ema9),
            patch.object(sell_manager, "update_sell_order", return_value=False),
        ):
            result = sell_manager._check_and_update_single_stock("RELIANCE", order_info, [])

            # Verify existing lowest_ema9 preserved (not overwritten)
            assert sell_manager.lowest_ema9["RELIANCE"] == 2480.0


class TestCircuitLimitHandling:
    """Test circuit limit rejection handling and retry logic"""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock(spec=KotakNeoAuth)
        auth.client = Mock()
        return auth

    @pytest.fixture
    def sell_manager(self, mock_auth):
        """Create SellOrderManager instance"""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.orders = Mock()
            return manager

    def test_parse_circuit_limits_valid_message(self, sell_manager):
        """Test parsing circuit limits from valid rejection message"""
        rejection_msg = (
            "RMS:Rule: Check circuit limit including square off order exceeds : "
            "Circuit breach, Order Price :34.65, Low Price Range:30.32 High Price Range:33.51"
        )
        result = sell_manager._parse_circuit_limits_from_rejection(rejection_msg)

        assert result is not None
        assert result["upper"] == 33.51
        assert result["lower"] == 30.32

    def test_parse_circuit_limits_with_spaces(self, sell_manager):
        """Test parsing circuit limits with spaces in message"""
        rejection_msg = "High Price Range: 33.51 Low Price Range: 30.32"
        result = sell_manager._parse_circuit_limits_from_rejection(rejection_msg)

        assert result is not None
        assert result["upper"] == 33.51
        assert result["lower"] == 30.32

    def test_parse_circuit_limits_case_insensitive(self, sell_manager):
        """Test parsing is case insensitive"""
        rejection_msg = "HIGH PRICE RANGE:33.51 LOW PRICE RANGE:30.32"
        result = sell_manager._parse_circuit_limits_from_rejection(rejection_msg)

        assert result is not None
        assert result["upper"] == 33.51
        assert result["lower"] == 30.32

    def test_parse_circuit_limits_missing_high(self, sell_manager):
        """Test parsing when high price range is missing"""
        rejection_msg = "Low Price Range:30.32"
        result = sell_manager._parse_circuit_limits_from_rejection(rejection_msg)

        assert result is None

    def test_parse_circuit_limits_missing_low(self, sell_manager):
        """Test parsing when low price range is missing"""
        rejection_msg = "High Price Range:33.51"
        result = sell_manager._parse_circuit_limits_from_rejection(rejection_msg)

        assert result is None

    def test_parse_circuit_limits_empty_message(self, sell_manager):
        """Test parsing with empty rejection message"""
        result = sell_manager._parse_circuit_limits_from_rejection("")
        assert result is None

    def test_parse_circuit_limits_none(self, sell_manager):
        """Test parsing with None rejection message"""
        result = sell_manager._parse_circuit_limits_from_rejection(None)
        assert result is None

    def test_parse_circuit_limits_invalid_format(self, sell_manager):
        """Test parsing with invalid format"""
        rejection_msg = "Some other error message"
        result = sell_manager._parse_circuit_limits_from_rejection(rejection_msg)
        assert result is None

    def test_remove_rejected_orders_circuit_limit_breach(self, sell_manager):
        """Test that circuit limit rejections are stored in waiting list"""
        from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor
        from modules.kotak_neo_auto_trader.utils.order_status_parser import OrderStatusParser

        # Setup active order
        sell_manager.active_sell_orders = {
            "TARAPUR": {
                "order_id": "12345",
                "target_price": 34.65,  # EMA9 target
                "placed_symbol": "TARAPUR-BE",
                "ticker": "TARAPUR.NS",
                "qty": 306,
            }
        }

        # Mock broker order with circuit limit rejection
        broker_order = {
            "nOrdNo": "12345",
            "ordSt": "REJECTED",
            "rejRsn": (
                "RMS:Rule: Check circuit limit including square off order exceeds : "
                "Circuit breach, Order Price :34.65, Low Price Range:30.32 High Price Range:33.51"
            ),
        }

        # Mock get_orders response
        sell_manager.orders.get_orders.return_value = {"data": [broker_order]}

        # Mock OrderStatusParser
        with (
            patch.object(OrderStatusParser, "is_rejected", return_value=True),
            patch.object(OrderStatusParser, "is_cancelled", return_value=False),
            patch.object(OrderStatusParser, "parse_status", return_value=Mock(value="REJECTED")),
            patch.object(
                OrderFieldExtractor, "get_rejection_reason", return_value=broker_order["rejRsn"]
            ),
            patch.object(OrderFieldExtractor, "get_order_id", return_value="12345"),
            patch.object(sell_manager, "_remove_from_tracking") as mock_remove,
        ):
            sell_manager._remove_rejected_orders()

        # Verify order was stored in waiting list
        assert "TARAPUR" in sell_manager.waiting_for_circuit_expansion
        wait_info = sell_manager.waiting_for_circuit_expansion["TARAPUR"]
        assert wait_info["upper_circuit"] == 33.51
        assert wait_info["lower_circuit"] == 30.32
        assert wait_info["ema9_target"] == 34.65
        assert wait_info["trade"]["qty"] == 306

        # Verify order was removed from active tracking
        mock_remove.assert_called_once_with("TARAPUR")

    def test_remove_rejected_orders_circuit_limit_but_ema9_below(self, sell_manager):
        """Test that circuit limit rejection is ignored if EMA9 is below upper circuit"""
        from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor
        from modules.kotak_neo_auto_trader.utils.order_status_parser import OrderStatusParser

        # Setup active order with EMA9 below circuit
        sell_manager.active_sell_orders = {
            "TARAPUR": {
                "order_id": "12345",
                "target_price": 32.00,  # Below upper circuit of 33.51
                "placed_symbol": "TARAPUR-BE",
                "ticker": "TARAPUR.NS",
                "qty": 306,
            }
        }

        broker_order = {
            "nOrdNo": "12345",
            "ordSt": "REJECTED",
            "rejRsn": "Circuit breach, High Price Range:33.51 Low Price Range:30.32",
        }

        sell_manager.orders.get_orders.return_value = {"data": [broker_order]}

        with (
            patch.object(OrderStatusParser, "is_rejected", return_value=True),
            patch.object(OrderStatusParser, "is_cancelled", return_value=False),
            patch.object(OrderStatusParser, "parse_status", return_value=Mock(value="REJECTED")),
            patch.object(
                OrderFieldExtractor, "get_rejection_reason", return_value=broker_order["rejRsn"]
            ),
            patch.object(OrderFieldExtractor, "get_order_id", return_value="12345"),
            patch.object(sell_manager, "_remove_from_tracking") as mock_remove,
        ):
            sell_manager._remove_rejected_orders()

        # Should not be in waiting list (EMA9 is below circuit)
        assert "TARAPUR" not in sell_manager.waiting_for_circuit_expansion
        # Should be removed as regular rejection
        mock_remove.assert_called_once_with("TARAPUR")

    def test_remove_rejected_orders_regular_rejection(self, sell_manager):
        """Test that regular rejections (not circuit limit) are handled normally"""
        from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor
        from modules.kotak_neo_auto_trader.utils.order_status_parser import OrderStatusParser

        sell_manager.active_sell_orders = {
            "RELIANCE": {
                "order_id": "12345",
                "target_price": 2500.0,
                "placed_symbol": "RELIANCE-EQ",
                "qty": 10,
            }
        }

        broker_order = {
            "nOrdNo": "12345",
            "ordSt": "REJECTED",
            "rejRsn": "Insufficient funds",
        }

        sell_manager.orders.get_orders.return_value = {"data": [broker_order]}

        with (
            patch.object(OrderStatusParser, "is_rejected", return_value=True),
            patch.object(OrderStatusParser, "is_cancelled", return_value=False),
            patch.object(OrderStatusParser, "parse_status", return_value=Mock(value="REJECTED")),
            patch.object(
                OrderFieldExtractor, "get_rejection_reason", return_value=broker_order["rejRsn"]
            ),
            patch.object(OrderFieldExtractor, "get_order_id", return_value="12345"),
            patch.object(sell_manager, "_remove_from_tracking") as mock_remove,
        ):
            sell_manager._remove_rejected_orders()

        # Should not be in waiting list
        assert "RELIANCE" not in sell_manager.waiting_for_circuit_expansion
        # Should be removed as regular rejection
        mock_remove.assert_called_once_with("RELIANCE")

    def test_check_and_retry_circuit_expansion_empty_waiting_list(self, sell_manager):
        """Test retry when waiting list is empty"""
        sell_manager.waiting_for_circuit_expansion = {}
        result = sell_manager._check_and_retry_circuit_expansion()
        assert result == 0

    def test_check_and_retry_circuit_expansion_ema9_still_above_circuit(self, sell_manager):
        """Test retry when EMA9 is still above circuit limit"""
        sell_manager.waiting_for_circuit_expansion = {
            "TARAPUR": {
                "upper_circuit": 33.51,
                "lower_circuit": 30.32,
                "ema9_target": 34.65,
                "trade": {
                    "placed_symbol": "TARAPUR-BE",
                    "ticker": "TARAPUR.NS",
                    "qty": 306,
                },
            }
        }

        # EMA9 is still above circuit
        with patch.object(sell_manager, "get_current_ema9", return_value=34.00):
            result = sell_manager._check_and_retry_circuit_expansion()

        assert result == 0
        # Should still be in waiting list
        assert "TARAPUR" in sell_manager.waiting_for_circuit_expansion

    def test_check_and_retry_circuit_expansion_ema9_within_circuit_success(self, sell_manager):
        """Test successful retry when EMA9 drops within circuit limit"""
        sell_manager.waiting_for_circuit_expansion = {
            "TARAPUR": {
                "upper_circuit": 33.51,
                "lower_circuit": 30.32,
                "ema9_target": 34.65,
                "trade": {
                    "placed_symbol": "TARAPUR-BE",
                    "ticker": "TARAPUR.NS",
                    "qty": 306,
                },
            }
        }

        # EMA9 is now within circuit
        current_ema9 = 33.00
        with (
            patch.object(sell_manager, "get_current_ema9", return_value=current_ema9),
            patch.object(sell_manager, "place_sell_order", return_value="NEW123") as mock_place,
            patch.object(sell_manager, "_register_order") as mock_register,
        ):
            result = sell_manager._check_and_retry_circuit_expansion()

        assert result == 1
        # Should be removed from waiting list
        assert "TARAPUR" not in sell_manager.waiting_for_circuit_expansion
        # Should have placed order at min(current_ema9, ema9_target) = 33.00
        mock_place.assert_called_once()
        call_args = mock_place.call_args
        assert call_args[0][1] == 33.00  # target_price
        # Should have registered order
        mock_register.assert_called_once()

    def test_check_and_retry_circuit_expansion_ema9_at_circuit_boundary(self, sell_manager):
        """Test retry when EMA9 is exactly at circuit limit"""
        sell_manager.waiting_for_circuit_expansion = {
            "TARAPUR": {
                "upper_circuit": 33.51,
                "lower_circuit": 30.32,
                "ema9_target": 34.65,
                "trade": {
                    "placed_symbol": "TARAPUR-BE",
                    "ticker": "TARAPUR.NS",
                    "qty": 306,
                },
            }
        }

        # EMA9 is exactly at upper circuit
        current_ema9 = 33.51
        with (
            patch.object(sell_manager, "get_current_ema9", return_value=current_ema9),
            patch.object(sell_manager, "place_sell_order", return_value="NEW123"),
            patch.object(sell_manager, "_register_order"),
        ):
            result = sell_manager._check_and_retry_circuit_expansion()

        assert result == 1
        assert "TARAPUR" not in sell_manager.waiting_for_circuit_expansion

    def test_check_and_retry_circuit_expansion_ema9_below_target(self, sell_manager):
        """Test retry uses current EMA9 when it's lower than stored target"""
        sell_manager.waiting_for_circuit_expansion = {
            "TARAPUR": {
                "upper_circuit": 33.51,
                "lower_circuit": 30.32,
                "ema9_target": 34.65,  # Higher target
                "trade": {
                    "placed_symbol": "TARAPUR-BE",
                    "ticker": "TARAPUR.NS",
                    "qty": 306,
                },
            }
        }

        # Current EMA9 is lower than stored target
        current_ema9 = 32.50
        with (
            patch.object(sell_manager, "get_current_ema9", return_value=current_ema9),
            patch.object(sell_manager, "place_sell_order", return_value="NEW123") as mock_place,
            patch.object(sell_manager, "_register_order"),
        ):
            result = sell_manager._check_and_retry_circuit_expansion()

        assert result == 1
        # Should use current_ema9 (32.50) not ema9_target (34.65)
        call_args = mock_place.call_args
        assert call_args[0][1] == 32.50

    def test_check_and_retry_circuit_expansion_place_order_fails(self, sell_manager):
        """Test retry when order placement fails"""
        sell_manager.waiting_for_circuit_expansion = {
            "TARAPUR": {
                "upper_circuit": 33.51,
                "lower_circuit": 30.32,
                "ema9_target": 34.65,
                "trade": {
                    "placed_symbol": "TARAPUR-BE",
                    "ticker": "TARAPUR.NS",
                    "qty": 306,
                },
            }
        }

        current_ema9 = 33.00
        with (
            patch.object(sell_manager, "get_current_ema9", return_value=current_ema9),
            patch.object(sell_manager, "place_sell_order", return_value=None),
        ):
            result = sell_manager._check_and_retry_circuit_expansion()

        assert result == 0
        # Should still be in waiting list (will retry next cycle)
        assert "TARAPUR" in sell_manager.waiting_for_circuit_expansion

    def test_check_and_retry_circuit_expansion_no_ticker(self, sell_manager):
        """Test retry when ticker is missing"""
        sell_manager.waiting_for_circuit_expansion = {
            "TARAPUR": {
                "upper_circuit": 33.51,
                "lower_circuit": 30.32,
                "ema9_target": 34.65,
                "trade": {
                    "placed_symbol": "TARAPUR-BE",
                    "ticker": "",  # Missing ticker
                    "qty": 306,
                },
            }
        }

        # Should extract ticker from symbol
        with (
            patch.object(sell_manager, "get_current_ema9", return_value=33.00),
            patch.object(sell_manager, "place_sell_order", return_value="NEW123"),
            patch.object(sell_manager, "_register_order"),
        ):
            result = sell_manager._check_and_retry_circuit_expansion()

        # Should still work (ticker extracted from symbol)
        assert result == 1

    def test_check_and_retry_circuit_expansion_ema9_fetch_fails(self, sell_manager):
        """Test retry when EMA9 fetch fails"""
        sell_manager.waiting_for_circuit_expansion = {
            "TARAPUR": {
                "upper_circuit": 33.51,
                "lower_circuit": 30.32,
                "ema9_target": 34.65,
                "trade": {
                    "placed_symbol": "TARAPUR-BE",
                    "ticker": "TARAPUR.NS",
                    "qty": 306,
                },
            }
        }

        with patch.object(sell_manager, "get_current_ema9", return_value=None):
            result = sell_manager._check_and_retry_circuit_expansion()

        assert result == 0
        # Should still be in waiting list
        assert "TARAPUR" in sell_manager.waiting_for_circuit_expansion

    def test_check_and_retry_circuit_expansion_exception_handling(self, sell_manager):
        """Test that exceptions are handled gracefully"""
        sell_manager.waiting_for_circuit_expansion = {
            "TARAPUR": {
                "upper_circuit": 33.51,
                "lower_circuit": 30.32,
                "ema9_target": 34.65,
                "trade": {
                    "placed_symbol": "TARAPUR-BE",
                    "ticker": "TARAPUR.NS",
                    "qty": 306,
                },
            }
        }

        # Simulate exception
        with patch.object(sell_manager, "get_current_ema9", side_effect=Exception("API Error")):
            result = sell_manager._check_and_retry_circuit_expansion()

        assert result == 0
        # Should still be in waiting list (will retry next cycle)
        assert "TARAPUR" in sell_manager.waiting_for_circuit_expansion

    def test_check_and_retry_circuit_expansion_multiple_symbols(self, sell_manager):
        """Test retry with multiple symbols in waiting list"""
        sell_manager.waiting_for_circuit_expansion = {
            "TARAPUR": {
                "upper_circuit": 33.51,
                "ema9_target": 34.65,
                "trade": {"placed_symbol": "TARAPUR-BE", "ticker": "TARAPUR.NS", "qty": 306},
            },
            "THYROCARE": {
                "upper_circuit": 450.00,
                "ema9_target": 460.00,
                "trade": {"placed_symbol": "THYROCARE-EQ", "ticker": "THYROCARE.NS", "qty": 23},
            },
        }

        # TARAPUR: EMA9 within circuit, THYROCARE: still above
        with (
            patch.object(sell_manager, "get_current_ema9", side_effect=[33.00, 455.00]),
            patch.object(sell_manager, "place_sell_order", side_effect=["NEW123", None]),
            patch.object(sell_manager, "_register_order"),
        ):
            result = sell_manager._check_and_retry_circuit_expansion()

        assert result == 1  # Only TARAPUR succeeded
        assert "TARAPUR" not in sell_manager.waiting_for_circuit_expansion
        assert "THYROCARE" in sell_manager.waiting_for_circuit_expansion  # Still waiting
