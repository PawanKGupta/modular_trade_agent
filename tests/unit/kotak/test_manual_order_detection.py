"""
Tests for manual order detection in place_new_entries() and retry_pending_orders_from_db().

This tests the bug fix where manual AMO orders placed outside the system
are detected and linked to database records.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.auto_trade_engine import AutoTradeEngine
from src.infrastructure.db.models import OrderStatus as DbOrderStatus


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
        engine.strategy_config = Mock()
        engine.strategy_config.user_capital = 50000.0
        engine.strategy_config.max_portfolio_size = 10
        engine.strategy_config.default_variety = "AMO"
        engine.strategy_config.default_exchange = "NSE"
        engine.strategy_config.default_product = "CNC"
        return engine


class TestManualOrderDetection:
    """Test manual order detection and handling"""

    def test_check_for_manual_orders_finds_amo_order(self, auto_trade_engine):
        """Test that _check_for_manual_orders detects manual AMO orders"""
        symbol = "RELIANCE-EQ"

        # Mock broker orders response - manual AMO order exists
        manual_order = {
            "neoOrdNo": "MANUAL123",
            "trdSym": symbol,
            "orderStatus": "open",
            "transactionType": "BUY",
            "quantity": 10,
            "price": 2450.0,
            "variety": "AMO",
        }

        # Mock get_pending_orders to return list of orders
        auto_trade_engine.orders.get_pending_orders.return_value = [manual_order]

        # Mock OrderFieldExtractor to extract fields from order
        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.OrderFieldExtractor"
        ) as MockExtractor:
            MockExtractor.get_symbol.return_value = symbol
            MockExtractor.get_transaction_type.return_value = "BUY"
            MockExtractor.get_order_id.return_value = "MANUAL123"
            MockExtractor.get_quantity.return_value = 10
            MockExtractor.get_price.return_value = 2450.0

            # Mock DB order not found (so it's treated as manual)
            auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = None

            # Mock symbol variants
            auto_trade_engine._symbol_variants = Mock(return_value=[symbol, "RELIANCE"])

            # Call detection
            result = auto_trade_engine._check_for_manual_orders(symbol)

            # Verify detection
            assert result["has_manual_order"] is True
            assert len(result["manual_orders"]) == 1
            assert result["manual_orders"][0]["order_id"] == "MANUAL123"
            assert result["manual_orders"][0]["quantity"] == 10

    def test_check_for_manual_orders_no_order_found(self, auto_trade_engine):
        """Test that _check_for_manual_orders returns False when no manual order exists"""
        symbol = "RELIANCE-EQ"

        # Mock get_pending_orders to return empty list
        auto_trade_engine.orders.get_pending_orders.return_value = []

        # Call detection
        result = auto_trade_engine._check_for_manual_orders(symbol)

        # Verify no detection
        assert result["has_manual_order"] is False
        assert len(result.get("manual_orders", [])) == 0

    def test_check_for_manual_orders_handles_system_order(self, auto_trade_engine):
        """Test that _check_for_manual_orders distinguishes between manual and system orders"""
        symbol = "RELIANCE-EQ"

        # Mock broker orders response - order exists
        broker_order = {
            "neoOrdNo": "SYSTEM123",
            "trdSym": symbol,
            "orderStatus": "open",
            "transactionType": "BUY",
            "quantity": 10,
            "price": 2450.0,
        }

        # Mock get_pending_orders to return list of orders
        auto_trade_engine.orders.get_pending_orders.return_value = [broker_order]

        # Mock OrderFieldExtractor to extract fields from order
        with patch(
            "modules.kotak_neo_auto_trader.auto_trade_engine.OrderFieldExtractor"
        ) as MockExtractor:
            MockExtractor.get_symbol.return_value = symbol
            MockExtractor.get_transaction_type.return_value = "BUY"
            MockExtractor.get_order_id.return_value = "SYSTEM123"
            MockExtractor.get_quantity.return_value = 10
            MockExtractor.get_price.return_value = 2450.0

            # Mock DB order EXISTS (so it's treated as system order)
            mock_db_order = Mock()
            auto_trade_engine.orders_repo.get_by_broker_order_id.return_value = mock_db_order

            # Mock symbol variants
            auto_trade_engine._symbol_variants = Mock(return_value=[symbol, "RELIANCE"])

            # Call detection
            result = auto_trade_engine._check_for_manual_orders(symbol)

            # Verify it's detected as system order, not manual
            assert result["has_manual_order"] is False
            assert result["has_system_order"] is True
            assert len(result["system_orders"]) == 1
            assert result["system_orders"][0]["order_id"] == "SYSTEM123"

    def test_retry_pending_orders_links_manual_order(self, auto_trade_engine):
        """Test that retry_pending_orders_from_db links manual order to DB record"""
        symbol = "RELIANCE"
        broker_symbol = "RELIANCE-EQ"
        ticker = "RELIANCE.NS"

        # Mock DB order with FAILED status (RETRY_PENDING merged into FAILED)
        mock_db_order = Mock()
        mock_db_order.id = 1
        mock_db_order.symbol = symbol
        mock_db_order.status = DbOrderStatus.FAILED
        mock_db_order.quantity = 10
        mock_db_order.ticker = ticker
        mock_db_order.retry_count = 0

        auto_trade_engine.orders_repo.get_retriable_failed_orders.return_value = [mock_db_order]
        auto_trade_engine.orders_repo.update = Mock()

        # Mock manual order detection
        auto_trade_engine._check_for_manual_orders = Mock(
            return_value={
                "has_manual_order": True,
                "manual_orders": [
                    {
                        "order_id": "MANUAL123",
                        "quantity": 10,
                        "price": 2450.0,
                    }
                ],
            }
        )

        # Mock other dependencies
        auto_trade_engine.has_holding = Mock(return_value=False)
        auto_trade_engine.current_symbols_in_portfolio = Mock(return_value=[])

        # Mock indicator_service (Phase 4: code uses indicator_service.get_daily_indicators_dict)
        auto_trade_engine.indicator_service = Mock()
        auto_trade_engine.indicator_service.get_daily_indicators_dict = Mock(
            return_value={
                "close": 2450.0,
                "rsi10": 25.0,
                "ema9": 2500.0,
                "ema200": 2400.0,
                "avg_volume": 1000000,
            }
        )
        auto_trade_engine._calculate_execution_capital = Mock(return_value=50000.0)

        # Mock order_validation_service (Phase 3.1: code uses OrderValidationService)
        auto_trade_engine.order_validation_service = Mock()
        auto_trade_engine.order_validation_service.check_portfolio_capacity = Mock(
            return_value=(True, 5, 10)
        )
        auto_trade_engine.order_validation_service.check_duplicate_order = Mock(
            return_value=(False, None)
        )

        # Call retry
        result = auto_trade_engine.retry_pending_orders_from_db()

        # Verify manual order was detected
        auto_trade_engine._check_for_manual_orders.assert_called_once_with(symbol)

        # Verify DB order was updated with manual order details
        auto_trade_engine.orders_repo.update.assert_called_once()
        call_args = auto_trade_engine.orders_repo.update.call_args
        assert call_args[0][0] == mock_db_order
        assert call_args[1]["broker_order_id"] == "MANUAL123"
        assert call_args[1]["quantity"] == 10  # Manual order qty
        assert call_args[1]["status"] == DbOrderStatus.PENDING

        # Verify order was not placed via broker API
        assert not auto_trade_engine.orders.place_market_buy.called

        # Verify result
        assert result["skipped"] == 1

    def test_should_skip_retry_due_to_manual_order_similar_qty(self, auto_trade_engine):
        """Test that retry is skipped when manual order has similar quantity"""
        symbol = "RELIANCE"
        retry_qty = 10

        manual_order_info = {
            "has_manual_order": True,
            "manual_orders": [
                {
                    "order_id": "MANUAL123",
                    "quantity": 11,  # Within 2 shares of retry qty (abs(11-10)=1 <= 2)
                    "price": 2450.0,
                }
            ],
        }

        should_skip, reason = auto_trade_engine._should_skip_retry_due_to_manual_order(
            symbol, retry_qty, manual_order_info
        )

        assert should_skip is True
        # Should match because abs(11-10)=1 <= 2, so it returns "similar"
        assert "similar" in reason.lower() or ">= retry qty" in reason.lower()

    def test_should_skip_retry_due_to_manual_order_larger_qty(self, auto_trade_engine):
        """Test that retry is skipped when manual order has larger quantity"""
        symbol = "RELIANCE"
        retry_qty = 10

        manual_order_info = {
            "has_manual_order": True,
            "manual_orders": [
                {
                    "order_id": "MANUAL123",
                    "quantity": 15,  # 50% larger (15 > 10 * 1.5 = 15 is NOT > 15, so will match >= condition first)
                    "price": 2450.0,
                }
            ],
        }

        should_skip, reason = auto_trade_engine._should_skip_retry_due_to_manual_order(
            symbol, retry_qty, manual_order_info
        )

        assert should_skip is True
        # Since 15 >= 10, it matches the first condition (>= retry qty), not the "much larger" condition
        assert ">= retry qty" in reason.lower() or "larger" in reason.lower()
