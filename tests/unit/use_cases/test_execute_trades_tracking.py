"""
Tests for order tracking in ExecuteTradesUseCase
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from modules.kotak_neo_auto_trader.domain.entities import Holding
from modules.kotak_neo_auto_trader.domain.value_objects import Exchange, Money
from modules.kotak_neo_auto_trader.infrastructure.broker_adapters.mock_broker_adapter import (
    MockBrokerAdapter,
)
from src.application.dto.analysis_response import AnalysisResponse, BulkAnalysisResponse
from src.application.use_cases.execute_trades import ExecuteTradesUseCase


class TestExecuteTradesOrderTracking:
    """Tests for order tracking in ExecuteTradesUseCase"""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        self.user_id = 1
        self.db_session = MagicMock()
        self.mock_broker_gateway = MockBrokerAdapter()

        # Mock PlaceOrderUseCase
        self.mock_place_order_uc = MagicMock()
        self.mock_place_order_uc.execute.return_value = MagicMock(success=True, order_id="ORDER123")
        monkeypatch.setattr(
            "src.application.use_cases.execute_trades.PlaceOrderUseCase",
            lambda broker_gateway: self.mock_place_order_uc,
        )

        # Mock order tracker
        self.mock_add_pending_order = MagicMock()
        monkeypatch.setattr(
            "src.application.use_cases.execute_trades.add_pending_order",
            self.mock_add_pending_order,
        )

        # Mock configure_order_tracker
        self.mock_configure_order_tracker = MagicMock()
        monkeypatch.setattr(
            "src.application.use_cases.execute_trades.configure_order_tracker",
            self.mock_configure_order_tracker,
        )

        # Mock logger to prevent console output during tests
        self.mock_logger = MagicMock()
        monkeypatch.setattr("src.application.use_cases.execute_trades.logger", self.mock_logger)

    def make_analysis_response(self, ticker, last_close, verdict="buy", combined_score=50.0):
        """Helper to create an AnalysisResponse"""
        return AnalysisResponse(
            ticker=ticker,
            status="success",
            timestamp=datetime.now(),
            verdict=verdict,
            last_close=last_close,
            combined_score=combined_score,
        )

    def test_order_tracking_when_monitoring_active(self, monkeypatch):
        """Test that orders are tracked when monitoring service is active"""
        # Mock monitoring service as running
        # The imports are inside _is_order_monitoring_active, so patch where they're used
        mock_conflict_service = MagicMock()
        mock_conflict_service.is_unified_service_running.return_value = True
        monkeypatch.setattr(
            "src.application.use_cases.execute_trades.ConflictDetectionService",
            lambda db: mock_conflict_service,
        )

        # Also mock IndividualServiceStatusRepository
        mock_status_repo = MagicMock()
        mock_status_repo.get_by_user_and_task.return_value = None
        monkeypatch.setattr(
            "src.application.use_cases.execute_trades.IndividualServiceStatusRepository",
            lambda db: mock_status_repo,
        )

        rec = self.make_analysis_response("STOCK1.NS", 100.0)
        bulk_resp = BulkAnalysisResponse(
            results=[rec],
            total_analyzed=1,
            successful=1,
            failed=0,
            buyable_count=1,
            timestamp=datetime.now(),
            execution_time_seconds=0.1,
        )

        uc = ExecuteTradesUseCase(
            broker_gateway=self.mock_broker_gateway,
            user_id=self.user_id,
            db_session=self.db_session,
        )
        summary = uc.execute(bulk_resp, place_sells_for_non_buyable=False)

        assert summary.success
        assert len(summary.orders_placed) == 1
        # Verify order was tracked
        self.mock_add_pending_order.assert_called_once()
        call_args = self.mock_add_pending_order.call_args
        # The order_id from the mock is "ORDER123"
        actual_order_id = call_args[1]["order_id"]
        assert actual_order_id == "ORDER123"
        assert call_args[1]["symbol"] == "STOCK1.NS"
        # Verify log message indicates monitoring is active
        # The debug message should be called with the monitoring message
        # Check all debug calls to find the one with monitoring info
        debug_calls = [str(call) for call in self.mock_logger.debug.call_args_list]
        monitoring_call_found = any(
            "monitoring" in str(call).lower() and "sync" in str(call).lower()
            for call in debug_calls
        )
        assert (
            monitoring_call_found
        ), f"Monitoring debug message not found. Debug calls: {debug_calls}"

    def test_order_tracking_when_monitoring_inactive(self, monkeypatch):
        """Test that orders are tracked when monitoring service is inactive"""
        # Mock monitoring service as not running
        # Patch where they're imported in execute_trades.py
        mock_conflict_service = MagicMock()
        mock_conflict_service.is_unified_service_running.return_value = False
        monkeypatch.setattr(
            "src.application.use_cases.execute_trades.ConflictDetectionService",
            lambda db: mock_conflict_service,
        )

        mock_status_repo = MagicMock()
        mock_status_repo.get_by_user_and_task.return_value = None
        monkeypatch.setattr(
            "src.application.use_cases.execute_trades.IndividualServiceStatusRepository",
            lambda db: mock_status_repo,
        )

        rec = self.make_analysis_response("STOCK2.NS", 200.0)
        bulk_resp = BulkAnalysisResponse(
            results=[rec],
            total_analyzed=1,
            successful=1,
            failed=0,
            buyable_count=1,
            timestamp=datetime.now(),
            execution_time_seconds=0.1,
        )

        uc = ExecuteTradesUseCase(
            broker_gateway=self.mock_broker_gateway,
            user_id=self.user_id,
            db_session=self.db_session,
        )
        summary = uc.execute(bulk_resp, place_sells_for_non_buyable=False)

        assert summary.success
        assert len(summary.orders_placed) == 1
        # Verify order was tracked
        self.mock_add_pending_order.assert_called_once()
        # Verify log message suggests manual sync
        # Check that info was called with the manual sync message
        info_calls = [str(call) for call in self.mock_logger.info.call_args_list]
        manual_sync_call_found = any(
            "monitoring service is not running" in str(call).lower() and "sync" in str(call).lower()
            for call in info_calls
        )
        assert (
            manual_sync_call_found
        ), f"Manual sync info message not found. Info calls: {info_calls}"

    def test_order_tracking_handles_failure_gracefully(self, monkeypatch):
        """Test that order placement succeeds even if tracking fails"""
        # Mock add_pending_order to raise exception
        self.mock_add_pending_order.side_effect = Exception("Tracking failed")

        # Mock monitoring service as not running
        mock_conflict_service = MagicMock()
        mock_conflict_service.is_unified_service_running.return_value = False
        monkeypatch.setattr(
            "src.application.services.conflict_detection_service.ConflictDetectionService",
            lambda db: mock_conflict_service,
        )

        mock_status_repo = MagicMock()
        mock_status_repo.get_by_user_and_task.return_value = None
        monkeypatch.setattr(
            "src.infrastructure.persistence.individual_service_status_repository.IndividualServiceStatusRepository",
            lambda db: mock_status_repo,
        )

        rec = self.make_analysis_response("STOCK3.NS", 300.0)
        bulk_resp = BulkAnalysisResponse(
            results=[rec],
            total_analyzed=1,
            successful=1,
            failed=0,
            buyable_count=1,
            timestamp=datetime.now(),
            execution_time_seconds=0.1,
        )

        uc = ExecuteTradesUseCase(
            broker_gateway=self.mock_broker_gateway,
            user_id=self.user_id,
            db_session=self.db_session,
        )
        summary = uc.execute(bulk_resp, place_sells_for_non_buyable=False)

        # Order placement should still succeed
        assert summary.success
        assert len(summary.orders_placed) == 1
        # Verify tracking was attempted
        self.mock_add_pending_order.assert_called_once()
        # Verify error was logged but didn't fail order placement
        self.mock_logger.warning.assert_any_call("Failed to track order ORDER123: Tracking failed")

    def test_order_tracking_skipped_when_no_order_id(self, monkeypatch):
        """Test that tracking is skipped when order_id is empty"""
        # Mock place order to return empty order_id
        self.mock_place_order_uc.execute.return_value = MagicMock(success=True, order_id="")

        rec = self.make_analysis_response("STOCK4.NS", 400.0)
        bulk_resp = BulkAnalysisResponse(
            results=[rec],
            total_analyzed=1,
            successful=1,
            failed=0,
            buyable_count=1,
            timestamp=datetime.now(),
            execution_time_seconds=0.1,
        )

        uc = ExecuteTradesUseCase(
            broker_gateway=self.mock_broker_gateway,
            user_id=self.user_id,
            db_session=self.db_session,
        )
        summary = uc.execute(bulk_resp, place_sells_for_non_buyable=False)

        assert summary.success
        assert len(summary.orders_placed) == 1
        # Verify tracking was not called (no order_id)
        self.mock_add_pending_order.assert_not_called()

    def test_order_tracking_skipped_when_no_user_id(self):
        """Test that tracking is skipped when user_id is not provided"""
        rec = self.make_analysis_response("STOCK5.NS", 500.0)
        bulk_resp = BulkAnalysisResponse(
            results=[rec],
            total_analyzed=1,
            successful=1,
            failed=0,
            buyable_count=1,
            timestamp=datetime.now(),
            execution_time_seconds=0.1,
        )

        uc = ExecuteTradesUseCase(
            broker_gateway=self.mock_broker_gateway,
            user_id=None,  # No user_id
            db_session=self.db_session,
        )
        summary = uc.execute(bulk_resp, place_sells_for_non_buyable=False)

        assert summary.success
        assert len(summary.orders_placed) == 1
        # Verify tracking was not called (no user_id)
        self.mock_add_pending_order.assert_not_called()

    def test_order_tracking_skipped_when_no_db_session(self):
        """Test that tracking is skipped when db_session is not provided"""
        rec = self.make_analysis_response("STOCK6.NS", 600.0)
        bulk_resp = BulkAnalysisResponse(
            results=[rec],
            total_analyzed=1,
            successful=1,
            failed=0,
            buyable_count=1,
            timestamp=datetime.now(),
            execution_time_seconds=0.1,
        )

        uc = ExecuteTradesUseCase(
            broker_gateway=self.mock_broker_gateway,
            user_id=self.user_id,
            db_session=None,  # No db_session
        )
        summary = uc.execute(bulk_resp, place_sells_for_non_buyable=False)

        assert summary.success
        assert len(summary.orders_placed) == 1
        # Verify tracking was not called (no db_session)
        self.mock_add_pending_order.assert_not_called()

    def test_order_tracking_includes_metadata(self, monkeypatch):
        """Test that order tracking includes proper metadata"""
        # Mock monitoring service as running
        mock_conflict_service = MagicMock()
        mock_conflict_service.is_unified_service_running.return_value = True
        monkeypatch.setattr(
            "src.application.services.conflict_detection_service.ConflictDetectionService",
            lambda db: mock_conflict_service,
        )

        rec = self.make_analysis_response(
            "STOCK7.NS", 700.0, verdict="strong_buy", combined_score=75.0
        )
        bulk_resp = BulkAnalysisResponse(
            results=[rec],
            total_analyzed=1,
            successful=1,
            failed=0,
            buyable_count=1,
            timestamp=datetime.now(),
            execution_time_seconds=0.1,
        )

        uc = ExecuteTradesUseCase(
            broker_gateway=self.mock_broker_gateway,
            user_id=self.user_id,
            db_session=self.db_session,
        )
        summary = uc.execute(bulk_resp, place_sells_for_non_buyable=False)

        assert summary.success
        # Verify tracking was called with proper metadata
        self.mock_add_pending_order.assert_called_once()
        call_kwargs = self.mock_add_pending_order.call_args[1]
        assert call_kwargs["order_metadata"]["verdict"] == "strong_buy"
        assert call_kwargs["order_metadata"]["combined_score"] == 75.0
        assert "execution_capital" in call_kwargs["order_metadata"]
        assert call_kwargs["entry_type"] == "initial"

    def test_sell_order_tracking(self, monkeypatch):
        """Test that sell orders are also tracked"""
        # Mock holdings
        mock_holding = Holding(
            symbol="STOCK8.NS",
            exchange=Exchange.NSE,
            quantity=10,
            average_price=Money(Decimal("100.00")),
            current_price=Money(Decimal("110.00")),
            last_updated=datetime.now(),
        )
        # Mock get_holdings method
        self.mock_broker_gateway.get_holdings = MagicMock(return_value=[mock_holding])

        # Mock monitoring service as running
        mock_conflict_service = MagicMock()
        mock_conflict_service.is_unified_service_running.return_value = True
        monkeypatch.setattr(
            "src.application.services.conflict_detection_service.ConflictDetectionService",
            lambda db: mock_conflict_service,
        )

        # No buy candidates, so sell orders will be placed
        bulk_resp = BulkAnalysisResponse(
            results=[],
            total_analyzed=0,
            successful=0,
            failed=0,
            buyable_count=0,
            timestamp=datetime.now(),
            execution_time_seconds=0.1,
        )

        uc = ExecuteTradesUseCase(
            broker_gateway=self.mock_broker_gateway,
            user_id=self.user_id,
            db_session=self.db_session,
        )
        summary = uc.execute(bulk_resp, place_sells_for_non_buyable=True, sell_percentage=100)

        assert summary.success
        # Verify sell order was tracked
        assert self.mock_add_pending_order.call_count >= 1
        # Check that at least one call was for sell order
        calls = self.mock_add_pending_order.call_args_list
        sell_calls = [c for c in calls if c[1].get("entry_type") == "exit"]
        assert len(sell_calls) > 0
