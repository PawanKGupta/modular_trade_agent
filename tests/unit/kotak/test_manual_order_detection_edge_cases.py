"""
Edge case tests for manual order detection.

Tests edge cases and uncovered lines in manual order detection methods.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine


@pytest.fixture
def auto_trade_engine():
    """Create AutoTradeEngine instance with mocked dependencies"""
    with patch("modules.kotak_neo_auto_trader.auto_trade_engine.KotakNeoAuth"):
        engine = AutoTradeEngine(
            enable_verifier=False,
            enable_telegram=False,
            user_id=1,
            db_session=MagicMock(),
        )
        engine.orders = Mock()
        engine.orders_repo = Mock()
        engine.user_id = 1
        return engine


class TestManualOrderDetectionEdgeCases:
    """Test edge cases in manual order detection"""

    def test_check_for_manual_orders_no_orders_repo(self, auto_trade_engine):
        """Test that _check_for_manual_orders handles missing orders_repo gracefully"""
        symbol = "RELIANCE-EQ"

        # Remove orders_repo
        auto_trade_engine.orders_repo = None

        # Call detection - should return early
        result = auto_trade_engine._check_for_manual_orders(symbol)

        # Verify result indicates no manual orders
        assert result["has_manual_order"] is False
        assert len(result.get("manual_orders", [])) == 0

    def test_check_for_manual_orders_no_user_id(self, auto_trade_engine):
        """Test that _check_for_manual_orders handles missing user_id gracefully"""
        symbol = "RELIANCE-EQ"

        # Remove user_id
        auto_trade_engine.user_id = None

        # Call detection - should return early
        result = auto_trade_engine._check_for_manual_orders(symbol)

        # Verify result indicates no manual orders
        assert result["has_manual_order"] is False

    def test_check_for_manual_orders_no_orders_client(self, auto_trade_engine):
        """Test that _check_for_manual_orders handles missing orders client gracefully"""
        symbol = "RELIANCE-EQ"

        # Remove orders client
        auto_trade_engine.orders = None

        # Call detection - should return early
        result = auto_trade_engine._check_for_manual_orders(symbol)

        # Verify result indicates no manual orders
        assert result["has_manual_order"] is False

    def test_check_for_manual_orders_exception_handling(self, auto_trade_engine):
        """Test that _check_for_manual_orders handles exceptions gracefully"""
        symbol = "RELIANCE-EQ"

        # Mock get_pending_orders to raise exception
        auto_trade_engine.orders.get_pending_orders = Mock(side_effect=Exception("API error"))

        # Mock symbol variants
        auto_trade_engine._symbol_variants = Mock(return_value=[symbol, "RELIANCE"])

        # Call detection - should not raise error
        result = auto_trade_engine._check_for_manual_orders(symbol)

        # Verify result indicates no manual orders (graceful failure)
        assert result["has_manual_order"] is False

    def test_check_for_manual_orders_non_buy_order_ignored(self, auto_trade_engine):
        """Test that non-BUY orders are ignored"""
        symbol = "RELIANCE-EQ"

        # Mock broker orders response - SELL order exists
        sell_order = {
            "neoOrdNo": "SELL123",
            "trdSym": symbol,
            "orderStatus": "open",
            "transactionType": "SELL",  # Not BUY
            "quantity": 10,
            "price": 2450.0,
        }

        auto_trade_engine.orders.get_pending_orders.return_value = [sell_order]

        # Mock OrderFieldExtractor
        with patch("modules.kotak_neo_auto_trader.auto_trade_engine.OrderFieldExtractor") as MockExtractor:
            MockExtractor.get_symbol.return_value = symbol
            MockExtractor.get_transaction_type.return_value = "SELL"  # Not BUY
            MockExtractor.get_order_id.return_value = "SELL123"
            MockExtractor.get_quantity.return_value = 10
            MockExtractor.get_price.return_value = 2450.0

            # Mock symbol variants
            auto_trade_engine._symbol_variants = Mock(return_value=[symbol, "RELIANCE"])

            # Call detection
            result = auto_trade_engine._check_for_manual_orders(symbol)

            # Verify SELL order was ignored (not in manual_orders)
            assert result["has_manual_order"] is False
            assert len(result.get("manual_orders", [])) == 0

    def test_check_for_manual_orders_different_symbol_ignored(self, auto_trade_engine):
        """Test that orders for different symbols are ignored"""
        symbol = "RELIANCE-EQ"
        different_symbol = "TCS-EQ"

        # Mock broker orders response - order for different symbol
        order = {
            "neoOrdNo": "ORDER123",
            "trdSym": different_symbol,
            "orderStatus": "open",
            "transactionType": "BUY",
            "quantity": 10,
            "price": 2450.0,
        }

        auto_trade_engine.orders.get_pending_orders.return_value = [order]

        # Mock OrderFieldExtractor
        with patch("modules.kotak_neo_auto_trader.auto_trade_engine.OrderFieldExtractor") as MockExtractor:
            MockExtractor.get_symbol.return_value = different_symbol  # Different symbol
            MockExtractor.get_transaction_type.return_value = "BUY"
            MockExtractor.get_order_id.return_value = "ORDER123"

            # Mock symbol variants - only RELIANCE variants
            auto_trade_engine._symbol_variants = Mock(return_value=[symbol, "RELIANCE"])

            # Call detection
            result = auto_trade_engine._check_for_manual_orders(symbol)

            # Verify different symbol order was ignored
            assert result["has_manual_order"] is False
            assert len(result.get("manual_orders", [])) == 0

    def test_check_for_manual_orders_no_order_id(self, auto_trade_engine):
        """Test that orders without order_id are ignored"""
        symbol = "RELIANCE-EQ"

        # Mock broker orders response - order without order_id
        order = {
            "trdSym": symbol,
            "orderStatus": "open",
            "transactionType": "BUY",
            "quantity": 10,
            "price": 2450.0,
            # Missing neoOrdNo
        }

        auto_trade_engine.orders.get_pending_orders.return_value = [order]

        # Mock OrderFieldExtractor
        with patch("modules.kotak_neo_auto_trader.auto_trade_engine.OrderFieldExtractor") as MockExtractor:
            MockExtractor.get_symbol.return_value = symbol
            MockExtractor.get_transaction_type.return_value = "BUY"
            MockExtractor.get_order_id.return_value = None  # No order ID
            MockExtractor.get_quantity.return_value = 10
            MockExtractor.get_price.return_value = 2450.0

            # Mock symbol variants
            auto_trade_engine._symbol_variants = Mock(return_value=[symbol, "RELIANCE"])

            # Call detection
            result = auto_trade_engine._check_for_manual_orders(symbol)

            # Verify order without ID was ignored
            assert result["has_manual_order"] is False
            assert len(result.get("manual_orders", [])) == 0

    def test_should_skip_retry_due_to_manual_order_no_manual_orders(self, auto_trade_engine):
        """Test that _should_skip_retry_due_to_manual_order returns False when no manual orders"""
        symbol = "RELIANCE"
        retry_qty = 10

        manual_order_info = {
            "has_manual_order": False,  # No manual orders
            "manual_orders": [],
        }

        should_skip, reason = auto_trade_engine._should_skip_retry_due_to_manual_order(
            symbol, retry_qty, manual_order_info
        )

        assert should_skip is False
        assert "No manual orders found" in reason

    def test_should_skip_retry_due_to_manual_order_empty_list(self, auto_trade_engine):
        """Test that _should_skip_retry_due_to_manual_order handles empty manual_orders list"""
        symbol = "RELIANCE"
        retry_qty = 10

        manual_order_info = {
            "has_manual_order": True,  # Says has manual order
            "manual_orders": [],  # But list is empty
        }

        should_skip, reason = auto_trade_engine._should_skip_retry_due_to_manual_order(
            symbol, retry_qty, manual_order_info
        )

        assert should_skip is False
        assert "No manual orders in list" in reason

    def test_should_skip_retry_due_to_manual_order_exact_match(self, auto_trade_engine):
        """Test that retry is skipped when manual order qty exactly matches retry qty"""
        symbol = "RELIANCE"
        retry_qty = 10

        manual_order_info = {
            "has_manual_order": True,
            "manual_orders": [{
                "order_id": "MANUAL123",
                "quantity": 10,  # Exactly matches retry qty
                "price": 2450.0,
            }]
        }

        should_skip, reason = auto_trade_engine._should_skip_retry_due_to_manual_order(
            symbol, retry_qty, manual_order_info
        )

        assert should_skip is True
        assert ">= retry qty" in reason.lower() or "similar" in reason.lower()

    def test_should_skip_retry_due_to_manual_order_proceed_with_different_qty(self, auto_trade_engine):
        """Test that retry proceeds when manual order qty is significantly different"""
        symbol = "RELIANCE"
        retry_qty = 10

        manual_order_info = {
            "has_manual_order": True,
            "manual_orders": [{
                "order_id": "MANUAL123",
                "quantity": 5,  # Much less than retry qty (10)
                "price": 2450.0,
            }]
        }

        should_skip, reason = auto_trade_engine._should_skip_retry_due_to_manual_order(
            symbol, retry_qty, manual_order_info
        )

        # Should proceed (not skip) because manual qty (5) is much less than retry qty (10)
        # and abs(5-10)=5 > 2, so doesn't match "similar" condition
        # Also 5 < 10, so doesn't match ">= retry qty" condition
        # Also 5 < 10 * 1.5 = 15, so doesn't match "much larger" condition
        assert should_skip is False
        assert "will cancel and replace" in reason.lower()

