"""
Tests for Sell Order DB Persistence

Tests the fix where place_sell_order() persists sell orders to the orders table.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager  # noqa: E402


class TestSellOrderDBPersistence:
    """Test sell order persistence to database"""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock()
        auth.client = Mock()
        return auth

    @pytest.fixture
    def sell_manager(self, mock_auth):
        """Create SellOrderManager with DB repos"""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.user_id = 1
            manager.positions_repo = Mock()
            manager.orders_repo = Mock()
            manager.orders = Mock()
            manager.scrip_master = Mock()
            # Mock get_trading_symbol to return the symbol as-is
            manager.scrip_master.get_trading_symbol = Mock(
                side_effect=lambda symbol, exchange: symbol
            )
            manager.strategy_config = Mock()
            manager.strategy_config.default_exchange = "NSE"
            return manager

    def test_place_sell_order_persists_to_db_happy_path(self, sell_manager):
        """Test that place_sell_order persists to DB when successful"""
        # Mock broker response
        mock_response = {"nOrdNo": "12345"}
        sell_manager.orders.place_limit_sell = Mock(return_value=mock_response)

        # Mock create_amo
        sell_manager.orders_repo.create_amo = Mock()

        # Prepare trade dict
        trade = {
            "symbol": "ASTERDM-EQ",
            "placed_symbol": "ASTERDM-EQ",
            "ticker": "ASTERDM.NS",
            "qty": 16,
        }

        # Call place_sell_order
        order_id = sell_manager.place_sell_order(trade, target_price=621.35)

        # Assert broker order was placed
        assert order_id == "12345"
        sell_manager.orders.place_limit_sell.assert_called_once()

        # Assert DB persistence was called
        sell_manager.orders_repo.create_amo.assert_called_once()
        call_kwargs = sell_manager.orders_repo.create_amo.call_args[1]

        # Verify all required fields
        assert call_kwargs["user_id"] == 1
        assert call_kwargs["symbol"] == "ASTERDM-EQ"
        assert call_kwargs["side"] == "sell"
        assert call_kwargs["order_type"] == "limit"
        assert call_kwargs["quantity"] == 16.0
        assert call_kwargs["price"] == 621.35
        assert call_kwargs["broker_order_id"] == "12345"
        assert call_kwargs["entry_type"] == "exit"

        # Verify order_metadata
        metadata = call_kwargs["order_metadata"]
        assert metadata["ticker"] == "ASTERDM.NS"
        assert metadata["exchange"] == "NSE"
        assert metadata["base_symbol"] == "ASTERDM"
        assert metadata["full_symbol"] == "ASTERDM-EQ"
        assert metadata["variety"] == "REGULAR"
        assert metadata["source"] == "sell_engine_run_at_market_open"

    def test_place_sell_order_no_db_when_orders_repo_missing(self, sell_manager):
        """Test that DB write is skipped when orders_repo is None"""
        sell_manager.orders_repo = None  # No DB repo

        # Mock broker response
        mock_response = {"nOrdNo": "12345"}
        sell_manager.orders.place_limit_sell = Mock(return_value=mock_response)

        trade = {
            "symbol": "EMKAY-BE",
            "placed_symbol": "EMKAY-BE",
            "ticker": "EMKAY.NS",
            "qty": 376,
        }

        # Call place_sell_order
        order_id = sell_manager.place_sell_order(trade, target_price=269.80)

        # Should still place broker order
        assert order_id == "12345"
        sell_manager.orders.place_limit_sell.assert_called_once()

        # Should not crash (no DB write attempted)

    def test_place_sell_order_no_db_when_user_id_missing(self, sell_manager):
        """Test that DB write is skipped when user_id is None"""
        sell_manager.user_id = None  # No user_id

        # Mock broker response
        mock_response = {"nOrdNo": "12345"}
        sell_manager.orders.place_limit_sell = Mock(return_value=mock_response)

        # Mock create_amo (should not be called)
        sell_manager.orders_repo.create_amo = Mock()

        trade = {
            "symbol": "RELIANCE-EQ",
            "placed_symbol": "RELIANCE-EQ",
            "ticker": "RELIANCE.NS",
            "qty": 10,
        }

        # Call place_sell_order
        order_id = sell_manager.place_sell_order(trade, target_price=2500.0)

        # Should still place broker order
        assert order_id == "12345"
        sell_manager.orders.place_limit_sell.assert_called_once()

        # Should not call create_amo
        sell_manager.orders_repo.create_amo.assert_not_called()

    def test_place_sell_order_handles_db_error_gracefully(self, sell_manager, caplog):
        """Test that DB errors don't crash the flow"""
        # Mock broker response
        mock_response = {"nOrdNo": "12345"}
        sell_manager.orders.place_limit_sell = Mock(return_value=mock_response)

        # Mock create_amo to raise exception
        sell_manager.orders_repo.create_amo = Mock(side_effect=Exception("DB connection failed"))

        trade = {
            "symbol": "TCS-EQ",
            "placed_symbol": "TCS-EQ",
            "ticker": "TCS.NS",
            "qty": 5,
        }

        # Call place_sell_order - should not crash
        order_id = sell_manager.place_sell_order(trade, target_price=3500.0)

        # Should still return broker order ID
        assert order_id == "12345"

        # Should log warning
        assert "Failed to persist sell order" in caplog.text

    def test_place_sell_order_metadata_includes_all_fields(self, sell_manager):
        """Test that order_metadata includes all required fields"""
        mock_response = {"nOrdNo": "67890"}
        sell_manager.orders.place_limit_sell = Mock(return_value=mock_response)
        sell_manager.orders_repo.create_amo = Mock()

        trade = {
            "symbol": "SALSTEEL-BE",
            "placed_symbol": "SALSTEEL-BE",
            "ticker": "SALSTEEL.NS",
            "qty": 100,
        }

        sell_manager.place_sell_order(trade, target_price=37.43)

        # Verify metadata completeness
        call_kwargs = sell_manager.orders_repo.create_amo.call_args[1]
        metadata = call_kwargs["order_metadata"]

        # All fields should be present
        required_fields = ["ticker", "exchange", "base_symbol", "full_symbol", "variety", "source"]
        for field in required_fields:
            assert field in metadata, f"Missing field: {field}"

        # Verify values
        assert metadata["ticker"] == "SALSTEEL.NS"
        assert metadata["base_symbol"] == "SALSTEEL"
        assert metadata["full_symbol"] == "SALSTEEL-BE"

    def test_place_sell_order_handles_different_order_id_formats(self, sell_manager):
        """Test that order ID extraction works for different response formats"""
        # Test different response formats
        test_cases = [
            {"nOrdNo": "11111"},
            {"data": {"nOrdNo": "22222"}},
            {"data": {"order_id": "33333"}},
            {"data": {"neoOrdNo": "44444"}},
            {"order": {"neoOrdNo": "55555"}},
            {"neoOrdNo": "66666"},
            {"orderId": "77777"},
        ]

        for i, mock_response in enumerate(test_cases):
            sell_manager.orders.place_limit_sell = Mock(return_value=mock_response)
            sell_manager.orders_repo.create_amo = Mock()

            trade = {
                "symbol": "TEST-EQ",
                "placed_symbol": "TEST-EQ",
                "ticker": "TEST.NS",
                "qty": 1,
            }

            order_id = sell_manager.place_sell_order(trade, target_price=100.0)

            # Should extract order ID correctly
            expected_ids = ["11111", "22222", "33333", "44444", "55555", "66666", "77777"]
            assert order_id == expected_ids[i]

            # Should persist to DB with correct broker_order_id
            call_kwargs = sell_manager.orders_repo.create_amo.call_args[1]
            assert call_kwargs["broker_order_id"] == expected_ids[i]

    def test_place_sell_order_no_persistence_when_broker_fails(self, sell_manager):
        """Test that DB write is not attempted when broker order fails"""
        # Mock broker to return None (failure)
        sell_manager.orders.place_limit_sell = Mock(return_value=None)
        sell_manager.orders_repo.create_amo = Mock()

        trade = {
            "symbol": "FAIL-EQ",
            "placed_symbol": "FAIL-EQ",
            "ticker": "FAIL.NS",
            "qty": 1,
        }

        # Call place_sell_order
        order_id = sell_manager.place_sell_order(trade, target_price=100.0)

        # Should return None
        assert order_id is None

        # Should not attempt DB write
        sell_manager.orders_repo.create_amo.assert_not_called()

    def test_place_sell_order_no_persistence_when_no_order_id(self, sell_manager):
        """Test that DB write is not attempted when broker doesn't return order ID"""
        # Mock broker to return response without order ID
        mock_response = {"status": "success"}  # No order ID
        sell_manager.orders.place_limit_sell = Mock(return_value=mock_response)
        sell_manager.orders_repo.create_amo = Mock()

        trade = {
            "symbol": "NOID-EQ",
            "placed_symbol": "NOID-EQ",
            "ticker": "NOID.NS",
            "qty": 1,
        }

        # Call place_sell_order
        order_id = sell_manager.place_sell_order(trade, target_price=100.0)

        # Should return None (no order ID)
        assert order_id is None

        # Should not attempt DB write
        sell_manager.orders_repo.create_amo.assert_not_called()
