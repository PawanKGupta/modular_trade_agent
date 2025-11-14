"""
Test Persistence Layer
"""

import pytest
import json
from pathlib import Path
from modules.kotak_neo_auto_trader.infrastructure.persistence import PaperTradeStore


class TestPaperTradeStore:
    """Test data persistence"""

    @pytest.fixture
    def store(self, tmp_path):
        """Create store with temporary storage"""
        storage_path = tmp_path / "paper_trading"
        return PaperTradeStore(str(storage_path), auto_save=False)

    def test_initialize_account(self, store):
        """Test account initialization"""
        store.initialize_account(100000.0)

        account = store.get_account()
        assert account is not None
        assert account["initial_capital"] == 100000.0
        assert account["available_cash"] == 100000.0

    def test_update_account(self, store):
        """Test account updates"""
        store.initialize_account(100000.0)
        store.update_account({"available_cash": 95000.0})

        account = store.get_account()
        assert account["available_cash"] == 95000.0

    def test_update_balance(self, store):
        """Test balance update"""
        store.initialize_account(100000.0)
        store.update_balance(90000.0, margin_used=5000.0)

        account = store.get_account()
        assert account["available_cash"] == 90000.0
        assert account["margin_used"] == 5000.0

    def test_update_pnl(self, store):
        """Test P&L update"""
        store.initialize_account(100000.0)
        store.update_pnl(500.0, 200.0, 300.0)

        account = store.get_account()
        assert account["total_pnl"] == 500.0
        assert account["realized_pnl"] == 200.0
        assert account["unrealized_pnl"] == 300.0

    def test_add_order(self, store):
        """Test adding orders"""
        order = {
            "order_id": "PT001",
            "symbol": "INFY",
            "quantity": 10,
            "order_type": "MARKET",
            "transaction_type": "BUY",
            "status": "PENDING"
        }

        store.add_order(order)
        orders = store.get_all_orders()

        assert len(orders) == 1
        assert orders[0]["order_id"] == "PT001"

    def test_get_order_by_id(self, store):
        """Test retrieving order by ID"""
        order = {
            "order_id": "PT002",
            "symbol": "TCS",
            "quantity": 5,
            "order_type": "MARKET",
            "transaction_type": "BUY",
            "status": "PENDING"
        }

        store.add_order(order)
        retrieved = store.get_order_by_id("PT002")

        assert retrieved is not None
        assert retrieved["symbol"] == "TCS"

    def test_update_order(self, store):
        """Test updating an order"""
        order = {
            "order_id": "PT003",
            "symbol": "RELIANCE",
            "quantity": 8,
            "status": "PENDING"
        }

        store.add_order(order)
        success = store.update_order("PT003", {"status": "COMPLETE"})

        assert success is True
        updated = store.get_order_by_id("PT003")
        assert updated["status"] == "COMPLETE"

    def test_get_orders_by_symbol(self, store):
        """Test filtering orders by symbol"""
        store.add_order({"order_id": "PT004", "symbol": "INFY", "status": "COMPLETE"})
        store.add_order({"order_id": "PT005", "symbol": "TCS", "status": "COMPLETE"})
        store.add_order({"order_id": "PT006", "symbol": "INFY", "status": "PENDING"})

        infy_orders = store.get_orders_by_symbol("INFY")
        assert len(infy_orders) == 2

    def test_get_pending_orders(self, store):
        """Test filtering pending orders"""
        store.add_order({"order_id": "PT007", "status": "COMPLETE"})
        store.add_order({"order_id": "PT008", "status": "PENDING"})
        store.add_order({"order_id": "PT009", "status": "OPEN"})

        pending = store.get_pending_orders()
        assert len(pending) == 2

    def test_add_holding(self, store):
        """Test adding holdings"""
        holding = {
            "quantity": 10,
            "average_price": 1450.00,
            "current_price": 1450.00
        }

        store.add_or_update_holding("INFY", holding)
        retrieved = store.get_holding("INFY")

        assert retrieved is not None
        assert retrieved["quantity"] == 10

    def test_update_holding(self, store):
        """Test updating holdings"""
        holding = {"quantity": 10, "average_price": 1450.00}
        store.add_or_update_holding("INFY", holding)

        updated = {"quantity": 15, "average_price": 1400.00}
        store.add_or_update_holding("INFY", updated)

        retrieved = store.get_holding("INFY")
        assert retrieved["quantity"] == 15

    def test_remove_holding(self, store):
        """Test removing holdings"""
        holding = {"quantity": 10, "average_price": 1450.00}
        store.add_or_update_holding("INFY", holding)

        success = store.remove_holding("INFY")
        assert success is True

        retrieved = store.get_holding("INFY")
        assert retrieved is None

    def test_get_all_holdings(self, store):
        """Test getting all holdings"""
        store.add_or_update_holding("INFY", {"quantity": 10})
        store.add_or_update_holding("TCS", {"quantity": 5})

        holdings = store.get_all_holdings()
        assert len(holdings) == 2

    def test_add_transaction(self, store):
        """Test adding transactions"""
        transaction = {
            "order_id": "PT010",
            "symbol": "INFY",
            "quantity": 10,
            "price": 1450.00
        }

        store.add_transaction(transaction)
        transactions = store.get_all_transactions()

        assert len(transactions) == 1

    def test_get_transactions_by_symbol(self, store):
        """Test filtering transactions by symbol"""
        store.add_transaction({"symbol": "INFY", "quantity": 10})
        store.add_transaction({"symbol": "TCS", "quantity": 5})
        store.add_transaction({"symbol": "INFY", "quantity": 5})

        infy_transactions = store.get_transactions_by_symbol("INFY")
        assert len(infy_transactions) == 2

    def test_save_and_load(self, tmp_path):
        """Test saving and loading data"""
        storage_path = tmp_path / "paper_trading"

        # Create and save data
        store1 = PaperTradeStore(str(storage_path), auto_save=True)
        store1.initialize_account(100000.0)
        store1.add_order({"order_id": "PT011", "symbol": "INFY"})
        store1.save_all()

        # Load in new instance
        store2 = PaperTradeStore(str(storage_path))
        account = store2.get_account()
        orders = store2.get_all_orders()

        assert account["initial_capital"] == 100000.0
        assert len(orders) == 1

    def test_create_backup(self, tmp_path):
        """Test creating backups"""
        storage_path = tmp_path / "paper_trading"
        store = PaperTradeStore(str(storage_path))
        store.initialize_account(100000.0)

        backup_path = store.create_backup()
        assert backup_path.exists()

    def test_reset(self, store):
        """Test resetting data"""
        store.initialize_account(100000.0)
        store.add_order({"order_id": "PT012"})

        store.reset()

        account = store.get_account()
        orders = store.get_all_orders()

        assert account is None
        assert len(orders) == 0

    def test_get_statistics(self, store):
        """Test getting statistics"""
        store.initialize_account(100000.0)
        store.add_order({"order_id": "PT013", "status": "PENDING"})
        store.add_order({"order_id": "PT014", "status": "COMPLETE"})

        stats = store.get_statistics()

        assert stats["total_orders"] == 2
        assert stats["pending_orders"] == 1
        assert stats["account_initialized"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

