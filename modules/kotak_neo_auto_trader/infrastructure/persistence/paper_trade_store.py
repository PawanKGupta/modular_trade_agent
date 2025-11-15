"""
Paper Trade Store
Persists paper trading data to JSON files
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from threading import Lock


class PaperTradeStore:
    """
    Storage layer for paper trading data

    Manages persistent storage of:
    - Account state (balance, capital)
    - Orders (all orders history)
    - Holdings (current portfolio)
    - Transactions (trade history)
    """

    def __init__(self, storage_path: str = "paper_trading/data", auto_save: bool = True):
        """
        Initialize storage

        Args:
            storage_path: Directory to store data files
            auto_save: Whether to auto-save after mutations
        """
        self.storage_path = Path(storage_path)
        self.auto_save = auto_save
        self._lock = Lock()  # Thread safety

        # File paths
        self.account_file = self.storage_path / "account.json"
        self.orders_file = self.storage_path / "orders.json"
        self.holdings_file = self.storage_path / "holdings.json"
        self.transactions_file = self.storage_path / "transactions.json"
        self.config_file = self.storage_path / "config.json"

        # In-memory cache
        self._account: Optional[Dict[str, Any]] = None
        self._orders: List[Dict[str, Any]] = []
        self._holdings: Dict[str, Dict[str, Any]] = {}
        self._transactions: List[Dict[str, Any]] = []

        # Initialize storage
        self._initialize_storage()

    def _initialize_storage(self) -> None:
        """Create storage directory and load existing data"""
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Load existing data or create new
        self._load_all()

    # ===== ACCOUNT METHODS =====

    def initialize_account(self, initial_capital: float, config: Dict[str, Any] = None) -> None:
        """
        Initialize account with starting capital

        Args:
            initial_capital: Starting capital in INR
            config: Optional configuration dict
        """
        with self._lock:
            self._account = {
                "initial_capital": initial_capital,
                "available_cash": initial_capital,
                "margin_used": 0.0,
                "total_pnl": 0.0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
            }

            if config:
                with open(self.config_file, 'w') as f:
                    json.dump(config, f, indent=2)

            if self.auto_save:
                self._save_account()

    def get_account(self) -> Optional[Dict[str, Any]]:
        """Get current account state"""
        with self._lock:
            return self._account.copy() if self._account else None

    def update_account(self, updates: Dict[str, Any]) -> None:
        """
        Update account fields

        Args:
            updates: Dictionary of fields to update
        """
        with self._lock:
            if not self._account:
                raise ValueError("Account not initialized")

            self._account.update(updates)
            self._account["last_updated"] = datetime.now().isoformat()

            if self.auto_save:
                self._save_account()

    def update_balance(self, available_cash: float, margin_used: float = 0.0) -> None:
        """Update account balance"""
        self.update_account({
            "available_cash": available_cash,
            "margin_used": margin_used,
        })

    def update_pnl(self, total_pnl: float, realized_pnl: float, unrealized_pnl: float) -> None:
        """Update P&L values"""
        self.update_account({
            "total_pnl": total_pnl,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
        })

    # ===== ORDER METHODS =====

    def add_order(self, order: Dict[str, Any]) -> None:
        """
        Add a new order

        Args:
            order: Order dictionary
        """
        with self._lock:
            self._orders.append(order)

            if self.auto_save:
                self._save_orders()

    def get_all_orders(self) -> List[Dict[str, Any]]:
        """Get all orders"""
        with self._lock:
            return self._orders.copy()

    def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by ID"""
        with self._lock:
            for order in self._orders:
                if order.get("order_id") == order_id:
                    return order.copy()
            return None

    def update_order(self, order_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing order

        Args:
            order_id: Order ID to update
            updates: Fields to update

        Returns:
            True if order found and updated, False otherwise
        """
        with self._lock:
            for i, order in enumerate(self._orders):
                if order.get("order_id") == order_id:
                    self._orders[i].update(updates)
                    self._orders[i]["last_updated"] = datetime.now().isoformat()

                    if self.auto_save:
                        self._save_orders()
                    return True
            return False

    def get_orders_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Get all orders for a symbol"""
        with self._lock:
            return [o.copy() for o in self._orders if o.get("symbol") == symbol]

    def get_pending_orders(self) -> List[Dict[str, Any]]:
        """Get all pending/open orders"""
        with self._lock:
            return [
                o.copy() for o in self._orders
                if o.get("status") in ["PENDING", "OPEN", "PARTIALLY_FILLED"]
            ]

    # ===== HOLDING METHODS =====

    def add_or_update_holding(self, symbol: str, holding: Dict[str, Any]) -> None:
        """
        Add or update a holding

        Args:
            symbol: Stock symbol
            holding: Holding dictionary
        """
        with self._lock:
            self._holdings[symbol] = holding
            self._holdings[symbol]["last_updated"] = datetime.now().isoformat()

            if self.auto_save:
                self._save_holdings()

    def get_holding(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get holding by symbol"""
        with self._lock:
            return self._holdings.get(symbol, {}).copy() if symbol in self._holdings else None

    def get_all_holdings(self) -> Dict[str, Dict[str, Any]]:
        """Get all holdings"""
        with self._lock:
            return {k: v.copy() for k, v in self._holdings.items()}

    def remove_holding(self, symbol: str) -> bool:
        """
        Remove a holding (when quantity becomes 0)

        Args:
            symbol: Stock symbol

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if symbol in self._holdings:
                del self._holdings[symbol]

                if self.auto_save:
                    self._save_holdings()
                return True
            return False

    # ===== TRANSACTION METHODS =====

    def add_transaction(self, transaction: Dict[str, Any]) -> None:
        """
        Add a transaction record

        Args:
            transaction: Transaction dictionary
        """
        with self._lock:
            transaction["timestamp"] = datetime.now().isoformat()
            self._transactions.append(transaction)

            if self.auto_save:
                self._save_transactions()

    def get_all_transactions(self) -> List[Dict[str, Any]]:
        """Get all transactions"""
        with self._lock:
            return self._transactions.copy()

    def get_transactions_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Get transactions for a symbol"""
        with self._lock:
            return [t.copy() for t in self._transactions if t.get("symbol") == symbol]

    # ===== PERSISTENCE METHODS =====

    def _save_account(self) -> None:
        """Save account to file (internal, assumes lock held)"""
        if self._account:
            with open(self.account_file, 'w') as f:
                json.dump(self._account, f, indent=2)

    def _save_orders(self) -> None:
        """Save orders to file (internal, assumes lock held)"""
        with open(self.orders_file, 'w') as f:
            json.dump(self._orders, f, indent=2)

    def _save_holdings(self) -> None:
        """Save holdings to file (internal, assumes lock held)"""
        with open(self.holdings_file, 'w') as f:
            json.dump(self._holdings, f, indent=2)

    def _save_transactions(self) -> None:
        """Save transactions to file (internal, assumes lock held)"""
        with open(self.transactions_file, 'w') as f:
            json.dump(self._transactions, f, indent=2)

    def save_all(self) -> None:
        """Save all data to files"""
        with self._lock:
            self._save_account()
            self._save_orders()
            self._save_holdings()
            self._save_transactions()

    def _load_all(self) -> None:
        """Load all data from files"""
        # Load account
        if self.account_file.exists():
            with open(self.account_file, 'r') as f:
                self._account = json.load(f)

        # Load orders
        if self.orders_file.exists():
            with open(self.orders_file, 'r') as f:
                self._orders = json.load(f)
        else:
            self._orders = []

        # Load holdings
        if self.holdings_file.exists():
            with open(self.holdings_file, 'r') as f:
                self._holdings = json.load(f)
        else:
            self._holdings = {}

        # Load transactions
        if self.transactions_file.exists():
            with open(self.transactions_file, 'r') as f:
                self._transactions = json.load(f)
        else:
            self._transactions = []

    def reload(self) -> None:
        """Reload all data from files"""
        with self._lock:
            self._load_all()

    # ===== BACKUP & RESET =====

    def create_backup(self) -> Path:
        """
        Create a backup of all data

        Returns:
            Path to backup directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.storage_path.parent / "backups" / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Copy all files
        for file in [self.account_file, self.orders_file, self.holdings_file,
                     self.transactions_file, self.config_file]:
            if file.exists():
                shutil.copy2(file, backup_dir / file.name)

        return backup_dir

    def restore_backup(self, backup_dir: Path) -> None:
        """
        Restore from a backup

        Args:
            backup_dir: Path to backup directory
        """
        if not backup_dir.exists():
            raise ValueError(f"Backup directory not found: {backup_dir}")

        # Copy files back
        for file in [self.account_file, self.orders_file, self.holdings_file,
                     self.transactions_file, self.config_file]:
            backup_file = backup_dir / file.name
            if backup_file.exists():
                shutil.copy2(backup_file, file)

        # Reload data
        self.reload()

    def reset(self) -> None:
        """
        Reset all data (delete everything)
        WARNING: This is destructive!
        """
        with self._lock:
            self._account = None
            self._orders = []
            self._holdings = {}
            self._transactions = []

            # Delete files
            for file in [self.account_file, self.orders_file, self.holdings_file,
                         self.transactions_file]:
                if file.exists():
                    file.unlink()

    # ===== STATISTICS =====

    def get_statistics(self) -> Dict[str, Any]:
        """Get storage statistics"""
        with self._lock:
            return {
                "total_orders": len(self._orders),
                "pending_orders": len([o for o in self._orders if o.get("status") in ["PENDING", "OPEN"]]),
                "completed_orders": len([o for o in self._orders if o.get("status") == "COMPLETE"]),
                "total_holdings": len(self._holdings),
                "total_transactions": len(self._transactions),
                "account_initialized": self._account is not None,
                "storage_path": str(self.storage_path),
            }

