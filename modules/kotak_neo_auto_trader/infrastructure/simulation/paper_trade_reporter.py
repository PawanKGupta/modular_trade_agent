"""
Paper Trade Reporter
Generate reports and analytics for paper trading
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from pathlib import Path

import sys

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

from ..persistence import PaperTradeStore


class PaperTradeReporter:
    """
    Generate reports and analytics for paper trading

    Features:
    - Portfolio summary
    - Order history
    - P&L reports
    - Performance metrics
    - Export to CSV/JSON
    """

    def __init__(self, store: PaperTradeStore):
        """
        Initialize reporter

        Args:
            store: Paper trade store
        """
        self.store = store

    # ===== PORTFOLIO REPORTS =====

    def portfolio_summary(self) -> Dict[str, Any]:
        """
        Generate portfolio summary

        Returns:
            Dictionary with portfolio details
        """
        account = self.store.get_account()
        holdings = self.store.get_all_holdings()

        if not account:
            return {"error": "Account not initialized"}

        # Calculate totals
        total_cost_basis = sum(
            h.get("quantity", 0) * float(h.get("average_price", 0)) for h in holdings.values()
        )
        total_market_value = sum(
            h.get("quantity", 0) * float(h.get("current_price", 0)) for h in holdings.values()
        )

        total_pnl = float(account.get("total_pnl", 0.0))
        initial_capital = float(account["initial_capital"])

        return {
            "account_value": account["available_cash"] + total_market_value,
            "cash_balance": account["available_cash"],
            "portfolio_value": total_market_value,
            "cost_basis": total_cost_basis,
            "total_pnl": total_pnl,
            "realized_pnl": float(account.get("realized_pnl", 0.0)),
            "unrealized_pnl": float(account.get("unrealized_pnl", 0.0)),
            "initial_capital": initial_capital,
            "return_percentage": (
                (total_pnl / initial_capital) * 100 if initial_capital > 0 else 0.0
            ),
            "holdings_count": len(holdings),
            "created_at": account.get("created_at"),
            "last_updated": account.get("last_updated"),
        }

    def holdings_report(self) -> List[Dict[str, Any]]:
        """
        Generate holdings report

        Returns:
            List of holdings with details
        """
        holdings = self.store.get_all_holdings()

        report = []
        for symbol, holding in holdings.items():
            quantity = holding.get("quantity", 0)
            avg_price = holding.get("average_price", 0.0)
            current_price = holding.get("current_price", 0.0)

            cost_basis = quantity * avg_price
            market_value = quantity * current_price
            pnl = market_value - cost_basis
            pnl_percentage = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0

            report.append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "average_price": avg_price,
                    "current_price": current_price,
                    "cost_basis": cost_basis,
                    "market_value": market_value,
                    "pnl": pnl,
                    "pnl_percentage": pnl_percentage,
                    "last_updated": holding.get("last_updated"),
                }
            )

        # Sort by P&L descending
        report.sort(key=lambda x: x["pnl"], reverse=True)

        return report

    # ===== ORDER REPORTS =====

    def order_history(
        self, limit: Optional[int] = None, symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate order history report

        Args:
            limit: Maximum number of orders to return
            symbol: Filter by symbol

        Returns:
            List of orders
        """
        if symbol:
            orders = self.store.get_orders_by_symbol(symbol)
        else:
            orders = self.store.get_all_orders()

        # Sort by created_at descending (newest first)
        orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        if limit:
            orders = orders[:limit]

        return orders

    def order_statistics(self) -> Dict[str, Any]:
        """
        Generate order statistics

        Returns:
            Dictionary with order stats
        """
        orders = self.store.get_all_orders()

        total_orders = len(orders)
        buy_orders = sum(1 for o in orders if o.get("transaction_type") == "BUY")
        sell_orders = sum(1 for o in orders if o.get("transaction_type") == "SELL")

        completed_orders = [o for o in orders if o.get("status") == "COMPLETE"]
        pending_orders = [
            o for o in orders if o.get("status") in ["PENDING", "OPEN", "PARTIALLY_FILLED"]
        ]
        cancelled_orders = [o for o in orders if o.get("status") == "CANCELLED"]
        rejected_orders = [o for o in orders if o.get("status") == "REJECTED"]

        return {
            "total_orders": total_orders,
            "buy_orders": buy_orders,
            "sell_orders": sell_orders,
            "completed_orders": len(completed_orders),
            "pending_orders": len(pending_orders),
            "cancelled_orders": len(cancelled_orders),
            "rejected_orders": len(rejected_orders),
            "success_rate": (
                (len(completed_orders) / total_orders * 100) if total_orders > 0 else 0.0
            ),
        }

    # ===== TRANSACTION REPORTS =====

    def transaction_history(
        self, limit: Optional[int] = None, symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate transaction history

        Args:
            limit: Maximum number of transactions
            symbol: Filter by symbol

        Returns:
            List of transactions
        """
        if symbol:
            transactions = self.store.get_transactions_by_symbol(symbol)
        else:
            transactions = self.store.get_all_transactions()

        # Sort by timestamp descending
        transactions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        if limit:
            transactions = transactions[:limit]

        return transactions

    # ===== PERFORMANCE METRICS =====

    def performance_metrics(self) -> Dict[str, Any]:
        """
        Calculate performance metrics

        Returns:
            Dictionary with performance metrics
        """
        account = self.store.get_account()
        transactions = self.store.get_all_transactions()

        if not account:
            return {"error": "Account not initialized"}

        # Calculate win rate
        completed_sells = [t for t in transactions if t.get("transaction_type") == "SELL"]

        # Note: Proper P&L calculation would require matching buys with sells
        # For simplicity, we use overall P&L from account

        total_pnl = account.get("total_pnl", 0.0)
        initial_capital = account["initial_capital"]
        return_pct = (total_pnl / initial_capital) * 100 if initial_capital > 0 else 0.0

        # Calculate trade metrics
        total_trades = len(completed_sells)

        return {
            "total_pnl": total_pnl,
            "realized_pnl": account.get("realized_pnl", 0.0),
            "unrealized_pnl": account.get("unrealized_pnl", 0.0),
            "return_percentage": return_pct,
            "total_trades": total_trades,
            "initial_capital": initial_capital,
            "current_value": account["available_cash"] + account.get("unrealized_pnl", 0.0),
        }

    # ===== EXPORT FUNCTIONS =====

    def export_to_json(self, filepath: str) -> None:
        """
        Export complete report to JSON

        Args:
            filepath: Path to save JSON file
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "portfolio_summary": self.portfolio_summary(),
            "holdings": self.holdings_report(),
            "order_history": self.order_history(limit=100),
            "order_statistics": self.order_statistics(),
            "transaction_history": self.transaction_history(limit=100),
            "performance_metrics": self.performance_metrics(),
        }

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"? Report exported to: {filepath}")

    def export_to_csv(self, output_dir: str) -> None:
        """
        Export reports to CSV files

        Args:
            output_dir: Directory to save CSV files
        """
        try:
            import csv

            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Export holdings
            holdings = self.holdings_report()
            if holdings:
                with open(output_path / "holdings.csv", "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=holdings[0].keys())
                    writer.writeheader()
                    writer.writerows(holdings)

            # Export orders
            orders = self.order_history()
            if orders:
                with open(output_path / "orders.csv", "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=orders[0].keys())
                    writer.writeheader()
                    writer.writerows(orders)

            # Export transactions
            transactions = self.transaction_history()
            if transactions:
                with open(output_path / "transactions.csv", "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=transactions[0].keys())
                    writer.writeheader()
                    writer.writerows(transactions)

            logger.info(f"? CSV reports exported to: {output_path}")

        except ImportError:
            logger.error("? csv module not available")

    # ===== DISPLAY FUNCTIONS =====

    def print_summary(self) -> None:
        """Print portfolio summary to console"""
        summary = self.portfolio_summary()

        print("\n" + "=" * 60)
        print("? PAPER TRADING SUMMARY")
        print("=" * 60)
        print(f"Initial Capital:    Rs {summary['initial_capital']:>15,.2f}")
        print(f"Current Value:      Rs {summary['account_value']:>15,.2f}")
        print(f"Cash Balance:       Rs {summary['cash_balance']:>15,.2f}")
        print(f"Portfolio Value:    Rs {summary['portfolio_value']:>15,.2f}")
        print("-" * 60)
        print(
            f"Total P&L:          Rs {summary['total_pnl']:>15,.2f} ({summary['return_percentage']:+.2f}%)"
        )
        print(f"  Realized:         Rs {summary['realized_pnl']:>15,.2f}")
        print(f"  Unrealized:       Rs {summary['unrealized_pnl']:>15,.2f}")
        print("-" * 60)
        print(f"Holdings Count:     {summary['holdings_count']:>16}")
        print("=" * 60 + "\n")

    def print_holdings(self) -> None:
        """Print holdings report to console"""
        holdings = self.holdings_report()

        if not holdings:
            print("\n? No holdings\n")
            return

        print("\n" + "=" * 100)
        print("? HOLDINGS")
        print("=" * 100)
        print(
            f"{'Symbol':<10} {'Qty':>8} {'Avg Price':>12} {'Current':>12} {'Cost Basis':>14} {'Mkt Value':>14} {'P&L':>12} {'P&L %':>8}"
        )
        print("-" * 100)

        for holding in holdings:
            print(
                f"{holding['symbol']:<10} "
                f"{holding['quantity']:>8} "
                f"Rs {holding['average_price']:>11,.2f} "
                f"Rs {holding['current_price']:>11,.2f} "
                f"Rs {holding['cost_basis']:>13,.2f} "
                f"Rs {holding['market_value']:>13,.2f} "
                f"Rs {holding['pnl']:>11,.2f} "
                f"{holding['pnl_percentage']:>7.2f}%"
            )

        print("=" * 100 + "\n")

    def print_recent_orders(self, limit: int = 10) -> None:
        """Print recent orders"""
        orders = self.order_history(limit=limit)

        if not orders:
            print("\n? No orders\n")
            return

        print(f"\n? RECENT ORDERS (Last {limit})")
        print("=" * 120)
        print(
            f"{'Order ID':<18} {'Symbol':<10} {'Type':<6} {'Side':<5} {'Qty':>6} {'Price':>10} {'Status':<15} {'Placed At':<20}"
        )
        print("-" * 120)

        for order in orders:
            price_str = f"Rs {order.get('price', 0):.2f}" if order.get("price") else "MKT"
            placed_at = order.get("placed_at", "")[:19] if order.get("placed_at") else "-"

            print(
                f"{order.get('order_id', ''):<18} "
                f"{order.get('symbol', ''):<10} "
                f"{order.get('order_type', ''):<6} "
                f"{order.get('transaction_type', ''):<5} "
                f"{order.get('quantity', 0):>6} "
                f"{price_str:>10} "
                f"{order.get('status', ''):<15} "
                f"{placed_at:<20}"
            )

        print("=" * 120 + "\n")
