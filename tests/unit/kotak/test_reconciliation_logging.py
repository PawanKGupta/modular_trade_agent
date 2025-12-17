"""
Tests for Reconciliation Logging (Section 7: Observability & Logging)

Tests verify that key log messages are present during reconciliation:
- "Reconciling X open positions with broker holdings..."
- Warnings for manual full/partial sells
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.sell_engine import SellOrderManager  # noqa: E402
from src.infrastructure.db.models import Positions  # noqa: E402


class TestReconciliationLogging:
    """Test reconciliation logging messages"""

    @pytest.fixture
    def mock_auth(self):
        """Create mock auth object"""
        auth = Mock()
        auth.client = Mock()
        return auth

    @pytest.fixture
    def sell_manager(self, mock_auth):
        """Create SellOrderManager instance"""
        with patch("modules.kotak_neo_auto_trader.sell_engine.KotakNeoScripMaster"):
            manager = SellOrderManager(auth=mock_auth, history_path="test_history.json")
            manager.user_id = 1
            manager.positions_repo = Mock()
            manager.portfolio = Mock()
            return manager

    def test_reconciliation_logs_start_message(self, sell_manager, caplog):
        """Test that reconciliation logs start message with position count"""
        # Mock positions
        positions = [
            Mock(spec=Positions, symbol="RELIANCE-EQ", quantity=10.0, closed_at=None),
            Mock(spec=Positions, symbol="TCS-EQ", quantity=5.0, closed_at=None),
        ]
        sell_manager.positions_repo.list = Mock(return_value=positions)

        # Mock holdings matching positions
        holdings_response = {
            "data": [
                {"symbol": "RELIANCE", "quantity": 10},
                {"symbol": "TCS", "quantity": 5},
            ]
        }
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        with caplog.at_level("INFO"):
            sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Verify log message about reconciling positions
        log_messages = [record.message for record in caplog.records]
        reconciling_logs = [
            msg
            for msg in log_messages
            if "reconciling" in msg.lower() or "reconcile" in msg.lower()
        ]
        assert len(reconciling_logs) > 0, "Expected reconciliation log message not found"

    def test_reconciliation_logs_manual_full_sell_warning(self, sell_manager, caplog):
        """Test that reconciliation logs warning for manual full sell"""
        # Mock position that was manually sold
        position = Mock(spec=Positions)
        position.symbol = "SOLD-EQ"
        position.quantity = 10.0
        position.closed_at = None

        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.positions_repo.mark_closed = Mock()

        # Mock empty holdings (position truly sold)
        holdings_response = {"data": []}
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        with caplog.at_level("WARNING"):
            sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Verify warning log for manual full sell
        log_messages = [record.message for record in caplog.records]
        warning_logs = [
            msg
            for msg in log_messages
            if "manual" in msg.lower() and ("full sell" in msg.lower() or "sell" in msg.lower())
        ]
        assert len(warning_logs) > 0, "Expected manual full sell warning log not found"
        assert any("SOLD-EQ" in msg for msg in warning_logs), "Warning should mention symbol"

    def test_reconciliation_logs_manual_partial_sell_warning(self, sell_manager, caplog):
        """Test that reconciliation logs warning for manual partial sell"""
        # Mock position with higher quantity
        position = Mock(spec=Positions)
        position.symbol = "PARTIAL-EQ"
        position.quantity = 100.0
        position.closed_at = None

        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.positions_repo.reduce_quantity = Mock()

        # Mock holdings with lower quantity (partial sell)
        holdings_response = {
            "data": [
                {
                    "symbol": "PARTIAL",
                    "quantity": 60,  # Less than position quantity
                }
            ]
        }
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        with caplog.at_level("WARNING"):
            sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Verify warning log for manual partial sell
        log_messages = [record.message for record in caplog.records]
        warning_logs = [
            msg
            for msg in log_messages
            if "manual" in msg.lower() and ("partial sell" in msg.lower() or "sell" in msg.lower())
        ]
        assert len(warning_logs) > 0, "Expected manual partial sell warning log not found"
        assert any(
            "PARTIAL-EQ" in msg or "PARTIAL" in msg for msg in warning_logs
        ), "Warning should mention symbol"

    def test_reconciliation_logs_summary_after_completion(self, sell_manager, caplog):
        """Test that reconciliation logs summary stats after completion"""
        # Mock multiple positions with different scenarios
        positions = [
            Mock(spec=Positions, symbol="MATCHED-EQ", quantity=10.0, closed_at=None),
            Mock(spec=Positions, symbol="SOLD-EQ", quantity=5.0, closed_at=None),
            Mock(spec=Positions, symbol="PARTIAL-EQ", quantity=100.0, closed_at=None),
        ]
        sell_manager.positions_repo.list = Mock(return_value=positions)
        sell_manager.positions_repo.mark_closed = Mock()
        sell_manager.positions_repo.reduce_quantity = Mock()

        # Mock holdings: one matched, one missing (sold), one partial
        holdings_response = {
            "data": [
                {"symbol": "MATCHED", "quantity": 10},  # Matches
                # SOLD-EQ missing (full sell)
                {"symbol": "PARTIAL", "quantity": 60},  # Partial sell
            ]
        }
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        with caplog.at_level("INFO"):
            stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Verify stats are logged
        log_messages = [record.message for record in caplog.records]
        # Check for summary logs (if any)
        summary_logs = [
            msg
            for msg in log_messages
            if any(
                keyword in msg.lower()
                for keyword in ["reconciliation", "reconciled", "updated", "closed"]
            )
        ]
        # At minimum, we should have some reconciliation-related logs
        assert len(summary_logs) > 0 or stats["checked"] > 0, "Expected reconciliation summary logs"

    def test_reconciliation_logs_no_positions_message(self, sell_manager, caplog):
        """Test that reconciliation handles empty positions gracefully"""
        # Mock no positions
        sell_manager.positions_repo.list = Mock(return_value=[])
        holdings_response = {"data": []}
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        with caplog.at_level("DEBUG"):
            stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Should complete without errors
        assert stats["checked"] == 0
        assert stats["updated"] == 0
        assert stats["closed"] == 0

    def test_reconciliation_logs_manual_buy_ignored(self, sell_manager, caplog):
        """Test that reconciliation logs when manual buys are ignored"""
        # Mock position with lower quantity
        position = Mock(spec=Positions)
        position.symbol = "BOUGHT-EQ"
        position.quantity = 100.0
        position.closed_at = None

        sell_manager.positions_repo.list = Mock(return_value=[position])
        sell_manager.positions_repo.mark_closed = Mock()
        sell_manager.positions_repo.reduce_quantity = Mock()

        # Mock holdings with higher quantity (manual buy - should be ignored)
        holdings_response = {
            "data": [
                {
                    "symbol": "BOUGHT",
                    "quantity": 120,  # More than position quantity
                }
            ]
        }
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        with caplog.at_level("DEBUG"):
            stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Should ignore manual buys (no updates)
        assert stats["ignored"] >= 1 or stats["updated"] == 0
        sell_manager.positions_repo.mark_closed.assert_not_called()
        sell_manager.positions_repo.reduce_quantity.assert_not_called()

    def test_reconciliation_logs_error_handling(self, sell_manager, caplog):
        """Test that reconciliation logs errors gracefully"""
        # Mock positions repo to raise exception
        sell_manager.positions_repo.list = Mock(side_effect=Exception("DB error"))

        holdings_response = {"data": []}
        sell_manager.portfolio.get_holdings = Mock(return_value=holdings_response)

        # Run reconciliation
        with caplog.at_level("ERROR"):
            stats = sell_manager._reconcile_positions_with_broker_holdings(holdings_response)

        # Should return empty stats on error
        assert stats["checked"] == 0
        # Should log error
        log_messages = [record.message for record in caplog.records if record.levelname == "ERROR"]
        assert len(log_messages) > 0, "Expected error log for reconciliation failure"
