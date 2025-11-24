"""
Unit tests for OrderStatusVerifier Phase 3.2 enhancements

Tests verify the new methods for exposing verification results
and sharing them across services.

Phase 3.2: Consolidate Order Verification
"""

from unittest.mock import Mock, patch
from datetime import datetime, timedelta

import pytest

from modules.kotak_neo_auto_trader.order_status_verifier import (
    OrderStatusVerifier,
    get_order_status_verifier,
)


class TestOrderStatusVerifierResultSharing:
    """Test OrderStatusVerifier result sharing methods"""

    def test_get_verification_result(self):
        """Test get_verification_result() returns stored result"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        # Store a verification result
        order_id = "ORDER123"
        result = {
            "order_id": order_id,
            "symbol": "RELIANCE",
            "status": "EXECUTED",
            "executed_qty": 10,
            "rejection_reason": None,
            "verified_at": datetime.now().isoformat(),
            "broker_order": {"nOrdNo": order_id, "ordSt": "complete"},
        }
        verifier._verification_results[order_id] = result

        # Get the result
        retrieved_result = verifier.get_verification_result(order_id)

        assert retrieved_result is not None
        assert retrieved_result["order_id"] == order_id
        assert retrieved_result["status"] == "EXECUTED"
        assert retrieved_result["executed_qty"] == 10

    def test_get_verification_result_not_found(self):
        """Test get_verification_result() returns None for non-existent order"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        result = verifier.get_verification_result("NONEXISTENT")

        assert result is None

    def test_get_verification_results_for_symbol(self):
        """Test get_verification_results_for_symbol() returns matching results"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        # Store multiple verification results for same symbol
        verifier._verification_results["ORDER1"] = {
            "order_id": "ORDER1",
            "symbol": "RELIANCE",
            "status": "EXECUTED",
            "executed_qty": 10,
            "verified_at": datetime.now().isoformat(),
            "broker_order": None,
        }
        verifier._verification_results["ORDER2"] = {
            "order_id": "ORDER2",
            "symbol": "RELIANCE-EQ",
            "status": "PENDING",
            "executed_qty": 0,
            "verified_at": datetime.now().isoformat(),
            "broker_order": None,
        }
        verifier._verification_results["ORDER3"] = {
            "order_id": "ORDER3",
            "symbol": "TATA",
            "status": "REJECTED",
            "executed_qty": 0,
            "verified_at": datetime.now().isoformat(),
            "broker_order": None,
        }

        # Get results for RELIANCE (should match both ORDER1 and ORDER2)
        results = verifier.get_verification_results_for_symbol("RELIANCE")

        assert len(results) == 2
        order_ids = [r["order_id"] for r in results]
        assert "ORDER1" in order_ids
        assert "ORDER2" in order_ids
        assert "ORDER3" not in order_ids

    def test_get_verification_results_for_symbol_no_matches(self):
        """Test get_verification_results_for_symbol() returns empty list for no matches"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        results = verifier.get_verification_results_for_symbol("NONEXISTENT")

        assert results == []

    def test_get_last_verification_counts(self):
        """Test get_last_verification_counts() returns stored counts"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        # Store last verification counts
        counts = {
            "checked": 5,
            "executed": 2,
            "rejected": 1,
            "cancelled": 1,
            "partial": 0,
            "still_pending": 1,
        }
        verifier._last_verification_counts = counts.copy()

        retrieved_counts = verifier.get_last_verification_counts()

        assert retrieved_counts == counts
        # Ensure it's a copy, not the same dict
        assert retrieved_counts is not verifier._last_verification_counts

    def test_get_last_verification_counts_empty(self):
        """Test get_last_verification_counts() returns empty dict if no counts stored"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        counts = verifier.get_last_verification_counts()

        assert counts == {}

    def test_should_skip_verification_recent_check(self):
        """Test should_skip_verification() returns True if check was recent"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        # Set last check time to 10 minutes ago (within 15 minute threshold)
        verifier._last_check_time = datetime.now() - timedelta(minutes=10)

        should_skip = verifier.should_skip_verification(minutes_threshold=15)

        assert should_skip is True

    def test_should_skip_verification_old_check(self):
        """Test should_skip_verification() returns False if check was old"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        # Set last check time to 20 minutes ago (outside 15 minute threshold)
        verifier._last_check_time = datetime.now() - timedelta(minutes=20)

        should_skip = verifier.should_skip_verification(minutes_threshold=15)

        assert should_skip is False

    def test_should_skip_verification_no_check(self):
        """Test should_skip_verification() returns False if never checked"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        # No last check time set
        verifier._last_check_time = None

        should_skip = verifier.should_skip_verification(minutes_threshold=15)

        assert should_skip is False

    def test_verify_pending_orders_stores_results(self):
        """Test that verify_pending_orders() stores verification results"""
        broker_client = Mock()

        # Mock order tracker with pending orders
        mock_tracker = Mock()
        mock_pending_order = {
            "order_id": "ORDER123",
            "symbol": "RELIANCE",
            "qty": 10,
        }
        mock_tracker.get_pending_orders = Mock(return_value=[mock_pending_order])

        # Mock broker orders
        mock_broker_order = {
            "nOrdNo": "ORDER123",
            "ordSt": "complete",
            "fldQty": 10,
        }

        verifier = OrderStatusVerifier(
            broker_client, order_tracker=mock_tracker
        )

        # Mock _fetch_broker_orders to return our mock order
        verifier._fetch_broker_orders = Mock(return_value=[mock_broker_order])

        # Call verify_pending_orders
        counts = verifier.verify_pending_orders()

        # Verify counts are stored
        assert verifier._last_verification_counts == counts
        assert "checked" in verifier._last_verification_counts
        assert counts["checked"] == 1

    def test_get_last_check_time(self):
        """Test get_last_check_time() returns stored check time"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        check_time = datetime.now()
        verifier._last_check_time = check_time

        retrieved_time = verifier.get_last_check_time()

        assert retrieved_time == check_time

    def test_get_last_check_time_none(self):
        """Test get_last_check_time() returns None if never checked"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        retrieved_time = verifier.get_last_check_time()

        assert retrieved_time is None

    def test_get_next_check_time(self):
        """Test get_next_check_time() returns estimated next check time"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client, check_interval_seconds=1800)

        check_time = datetime.now()
        verifier._last_check_time = check_time

        next_check_time = verifier.get_next_check_time()

        assert next_check_time is not None
        assert next_check_time == check_time + timedelta(seconds=1800)

    def test_get_next_check_time_none(self):
        """Test get_next_check_time() returns None if never checked"""
        broker_client = Mock()
        verifier = OrderStatusVerifier(broker_client)

        next_check_time = verifier.get_next_check_time()

        assert next_check_time is None


class TestEODCleanupOrderVerificationSkip:
    """Test EOD Cleanup conditional verification"""

    @patch("modules.kotak_neo_auto_trader.eod_cleanup.logger")
    def test_verify_all_pending_orders_skips_recent_check(self, mock_logger):
        """Test that EOD cleanup skips verification if OrderStatusVerifier ran recently"""
        from modules.kotak_neo_auto_trader.eod_cleanup import EODCleanup

        broker_client = Mock()
        mock_verifier = Mock()
        mock_verifier.should_skip_verification = Mock(return_value=True)
        mock_verifier.get_last_check_time = Mock(
            return_value=datetime.now() - timedelta(minutes=10)
        )
        mock_verifier.get_last_verification_counts = Mock(
            return_value={
                "checked": 5,
                "executed": 2,
                "rejected": 1,
                "still_pending": 2,
            }
        )

        cleanup = EODCleanup(
            broker_client=broker_client, order_verifier=mock_verifier
        )

        result = cleanup._verify_all_pending_orders()

        # Verify OrderStatusVerifier.should_skip_verification was called
        mock_verifier.should_skip_verification.assert_called_once_with(
            minutes_threshold=15
        )

        # Verify verify_pending_orders() was NOT called (we're using cached results)
        # Check that verify_pending_orders was not called by checking call_count
        verify_call_count = (
            mock_verifier.verify_pending_orders.call_count
            if hasattr(mock_verifier.verify_pending_orders, "call_count")
            else 0
        )
        assert verify_call_count == 0

        # Verify result contains skipped flag and source
        assert result.get("skipped") is True
        assert result.get("source") == "OrderStatusVerifier"
        assert result["checked"] == 5

    @patch("modules.kotak_neo_auto_trader.eod_cleanup.logger")
    def test_verify_all_pending_orders_runs_old_check(self, mock_logger):
        """Test that EOD cleanup runs verification if OrderStatusVerifier ran long ago"""
        from modules.kotak_neo_auto_trader.eod_cleanup import EODCleanup

        broker_client = Mock()
        mock_verifier = Mock()
        mock_verifier.should_skip_verification = Mock(return_value=False)
        mock_verifier.verify_pending_orders = Mock(
            return_value={
                "checked": 3,
                "executed": 1,
                "rejected": 0,
                "still_pending": 2,
            }
        )

        cleanup = EODCleanup(
            broker_client=broker_client, order_verifier=mock_verifier
        )

        result = cleanup._verify_all_pending_orders()

        # Verify OrderStatusVerifier.should_skip_verification was called
        mock_verifier.should_skip_verification.assert_called_once_with(
            minutes_threshold=15
        )

        # Verify verify_pending_orders() WAS called
        mock_verifier.verify_pending_orders.assert_called_once()

        # Verify result does not contain skipped flag
        assert result.get("skipped") is not True
        assert result["checked"] == 3

    @patch("modules.kotak_neo_auto_trader.eod_cleanup.logger")
    def test_verify_all_pending_orders_no_verifier(self, mock_logger):
        """Test that EOD cleanup handles missing OrderStatusVerifier gracefully"""
        from modules.kotak_neo_auto_trader.eod_cleanup import EODCleanup

        broker_client = Mock()
        cleanup = EODCleanup(broker_client=broker_client, order_verifier=None)

        result = cleanup._verify_all_pending_orders()

        assert result.get("skipped") is True


class TestSellMonitorOrderVerificationIntegration:
    """Test Sell Monitor (SellOrderManager) integration with OrderStatusVerifier"""

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoMarketData")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    def test_check_order_execution_uses_verifier_results(
        self,
        mock_auth,
        mock_scrip,
        mock_market,
        mock_portfolio,
        mock_orders,
    ):
        """Test that check_order_execution() uses OrderStatusVerifier results first"""
        from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager

        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance

        # Mock OrderStatusVerifier with results
        mock_verifier = Mock()
        mock_verifier.get_verification_result = Mock(
            side_effect=lambda order_id: (
                {
                    "order_id": order_id,
                    "status": "EXECUTED",
                    "symbol": "RELIANCE",
                    "executed_qty": 10,
                    "verified_at": datetime.now().isoformat(),
                    "broker_order": None,
                }
                if order_id == "ORDER123"
                else None
            )
        )

        sell_manager = SellOrderManager(
            auth=mock_auth_instance, order_verifier=mock_verifier
        )

        # Add active sell orders
        sell_manager.active_sell_orders = {
            "RELIANCE": {"order_id": "ORDER123", "target_price": 2500.0},
            "TATA": {"order_id": "ORDER456", "target_price": 1500.0},
        }

        executed_ids = sell_manager.check_order_execution()

        # Verify OrderStatusVerifier.get_verification_result was called
        mock_verifier.get_verification_result.assert_called()

        # Verify executed order ID is in results
        assert "ORDER123" in executed_ids

        # Verify orders.get_executed_orders() was NOT called (fallback)
        # This is tricky to verify, but if verifier has results, it shouldn't call API

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoMarketData")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    def test_has_completed_sell_order_uses_verifier_results(
        self,
        mock_auth,
        mock_scrip,
        mock_market,
        mock_portfolio,
        mock_orders,
    ):
        """Test that has_completed_sell_order() uses OrderStatusVerifier results first"""
        from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
        from modules.kotak_neo_auto_trader.utils.order_field_extractor import (
            OrderFieldExtractor,
        )

        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance

        # Mock OrderStatusVerifier with results
        mock_verifier = Mock()
        mock_broker_order = {"nOrdNo": "ORDER123", "price": 2500.0, "fldQty": 10}

        with patch.object(
            OrderFieldExtractor, "get_price", return_value=2500.0
        ):
            mock_verifier.get_verification_results_for_symbol = Mock(
                return_value=[
                    {
                        "order_id": "ORDER123",
                        "status": "EXECUTED",
                        "symbol": "RELIANCE",
                        "executed_qty": 10,
                        "verified_at": datetime.now().isoformat(),
                        "broker_order": mock_broker_order,
                    }
                ]
            )

            sell_manager = SellOrderManager(
                auth=mock_auth_instance, order_verifier=mock_verifier
            )

            result = sell_manager.has_completed_sell_order("RELIANCE")

            # Verify OrderStatusVerifier.get_verification_results_for_symbol was called
            mock_verifier.get_verification_results_for_symbol.assert_called_once_with(
                "RELIANCE"
            )

            # Verify result is returned from verifier
            assert result is not None
            assert result["order_id"] == "ORDER123"
            assert result["price"] == 2500.0

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoMarketData")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    def test_check_order_execution_fallback_to_api(
        self,
        mock_auth,
        mock_scrip,
        mock_market,
        mock_portfolio,
        mock_orders,
    ):
        """Test that check_order_execution() falls back to API if verifier has no results"""
        from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager

        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance

        mock_orders_instance = Mock()
        mock_orders.return_value = mock_orders_instance
        mock_orders_instance.get_executed_orders = Mock(
            return_value=[
                {"neoOrdNo": "ORDER789", "ordSt": "complete", "fldQty": 5}
            ]
        )

        # Mock OrderStatusVerifier with no results
        mock_verifier = Mock()
        mock_verifier.get_verification_result = Mock(return_value=None)

        sell_manager = SellOrderManager(
            auth=mock_auth_instance, order_verifier=mock_verifier
        )
        sell_manager.orders = mock_orders_instance

        # Add active sell orders
        sell_manager.active_sell_orders = {
            "RELIANCE": {"order_id": "ORDER789", "target_price": 2500.0},
        }

        executed_ids = sell_manager.check_order_execution()

        # Verify fallback to API was used
        mock_orders_instance.get_executed_orders.assert_called_once()

        # Verify executed order ID is in results
        assert "ORDER789" in executed_ids

    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoOrders")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoPortfolio")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoMarketData")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster")
    @patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoAuth")
    def test_has_completed_sell_order_fallback_to_api(
        self,
        mock_auth,
        mock_scrip,
        mock_market,
        mock_portfolio,
        mock_orders,
    ):
        """Test that has_completed_sell_order() falls back to API if verifier has no results"""
        from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager
        from modules.kotak_neo_auto_trader.utils.order_field_extractor import (
            OrderFieldExtractor,
        )
        from modules.kotak_neo_auto_trader.utils.order_status_parser import (
            OrderStatusParser,
        )

        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance

        mock_orders_instance = Mock()
        mock_orders.return_value = mock_orders_instance
        mock_orders_instance.get_orders = Mock(
            return_value={
                "data": [
                    {
                        "neoOrdNo": "ORDER789",
                        "ordSt": "complete",
                        "tradingSymbol": "RELIANCE-EQ",
                        "price": 2500.0,
                        "transactionType": "SELL",
                    }
                ]
            }
        )

        # Mock OrderStatusVerifier with no results
        mock_verifier = Mock()
        mock_verifier.get_verification_results_for_symbol = Mock(return_value=[])

        from modules.kotak_neo_auto_trader.utils.symbol_utils import (
            extract_base_symbol,
        )

        with patch.object(
            OrderFieldExtractor, "is_sell_order", return_value=True
        ), patch.object(
            OrderFieldExtractor, "get_symbol", return_value="RELIANCE-EQ"
        ), patch(
            "modules.kotak_neo_auto_trader.sell_engine.extract_base_symbol",
            return_value="RELIANCE",
        ), patch.object(
            OrderStatusParser, "is_completed", return_value=True
        ), patch.object(
            OrderFieldExtractor, "get_order_id", return_value="ORDER789"
        ), patch.object(
            OrderFieldExtractor, "get_price", return_value=2500.0
        ):
            sell_manager = SellOrderManager(
                auth=mock_auth_instance, order_verifier=mock_verifier
            )
            sell_manager.orders = mock_orders_instance

            result = sell_manager.has_completed_sell_order("RELIANCE")

            # Verify fallback to API was used
            mock_orders_instance.get_orders.assert_called_once()

            # Verify result is returned from API
            assert result is not None
            assert result["order_id"] == "ORDER789"
            assert result["price"] == 2500.0

