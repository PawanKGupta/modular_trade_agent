"""
Paper Trading Broker Adapter
Simulates broker operations without real money
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

from ...config.paper_trading_config import PaperTradingConfig
from ...domain import (
    Exchange,
    Holding,
    IBrokerGateway,
    Money,
    Order,
    OrderStatus,
    OrderType,
    TransactionType,
)
from ..persistence import PaperTradeStore
from ..simulation import OrderSimulator, PortfolioManager, PriceProvider


class PaperTradingBrokerAdapter(IBrokerGateway):
    """
    Paper trading adapter implementing IBrokerGateway

    Simulates all broker operations:
    - Order placement and execution
    - Portfolio management
    - Balance tracking
    - P&L calculation

    No real money involved - perfect for testing strategies!
    """

    def __init__(self, config: PaperTradingConfig | None = None, storage_path: str | None = None):
        """
        Initialize paper trading adapter

        Args:
            config: Paper trading configuration (uses default if None)
            storage_path: Custom storage path (optional)
        """
        # Configuration
        self.config = config or PaperTradingConfig.default()

        # Storage
        storage_path = storage_path or self.config.storage_path
        self.store = PaperTradeStore(storage_path, auto_save=self.config.auto_save)

        # Components
        self.price_provider = PriceProvider(
            mode=self.config.price_source,
            cache_duration_seconds=self.config.price_cache_duration_seconds,
        )
        self.order_simulator = OrderSimulator(self.config, self.price_provider)
        self.portfolio = PortfolioManager()

        # State
        self._connected = False
        self._order_counter = 0

        # Initialize if needed
        self._initialize()

    def _initialize(self) -> None:
        """Initialize or restore state"""
        account = self.store.get_account()

        if account is None:
            # First time - initialize account
            logger.info(
                f"? Initializing new paper trading account with "
                f"Rs {self.config.initial_capital:,.2f}"
            )
            self.store.initialize_account(self.config.initial_capital, config=self.config.to_dict())
        else:
            # Restore existing state
            logger.info(
                f"?? Restoring paper trading account (Balance: Rs {account['available_cash']:,.2f})"
            )
            # Always save the current config to ensure max_position_size and other settings are up-to-date
            config_file = self.store.storage_path / "config.json"
            import json

            with open(config_file, "w") as f:
                json.dump(self.config.to_dict(), f, indent=2)
            self._restore_state()

    def _restore_state(self) -> None:
        """Restore portfolio from storage"""
        holdings = self.store.get_all_holdings()

        for symbol, holding_data in holdings.items():
            holding = Holding(
                symbol=symbol,
                exchange=Exchange[holding_data.get("exchange", "NSE")],
                quantity=holding_data["quantity"],
                average_price=Money(holding_data["average_price"]),
                current_price=Money(holding_data["current_price"]),
                last_updated=datetime.fromisoformat(holding_data["last_updated"]),
            )
            self.portfolio._holdings[symbol] = holding

        logger.info(f"?? Restored {len(holdings)} holdings")

    # ===== CONNECTION MANAGEMENT =====

    def connect(self) -> bool:
        """Establish connection (simulated)"""
        if self._connected:
            logger.info("? Already connected to paper trading")
            return True

        self._connected = True
        logger.info("? Connected to paper trading system")
        logger.info(f"? Available balance: Rs {self.get_available_balance().amount:,.2f}")
        logger.info(f"? Holdings: {len(self.portfolio.get_all_holdings())}")

        return True

    def disconnect(self) -> bool:
        """Disconnect (simulated)"""
        if not self._connected:
            return True

        # Save state before disconnect
        self.store.save_all()
        self._connected = False
        logger.info("? Disconnected from paper trading system")

        return True

    def is_connected(self) -> bool:
        """Check if connected"""
        return self._connected

    # ===== ORDER MANAGEMENT =====

    def place_order(self, order: Order) -> str:
        """
        Place an order (simulate execution)

        Args:
            order: Order to place

        Returns:
            Order ID

        Raises:
            ConnectionError: If not connected
            ValueError: If order validation fails
            RuntimeError: If order placement fails
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to paper trading system")

        # Generate order ID
        order_id = self._generate_order_id()

        logger.info(
            f"? Placing order: {order.transaction_type.value} "
            f"{order.quantity} {order.symbol} @ "
            f"{order.order_type.value}"
        )

        try:
            # Mark as placed
            order.place(order_id)

            # Save order
            self._save_order(order)

            # Try to execute immediately (for market orders)
            if order.order_type == OrderType.MARKET:
                self._execute_order(order)

            return order_id

        except Exception as e:
            import traceback

            logger.error(f"? Order placement failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Order placement failed: {e}")

    def _execute_order(self, order: Order) -> None:
        """
        Execute an order

        Args:
            order: Order to execute
        """
        # Get current balance
        account = self.store.get_account()
        available_cash = account["available_cash"]

        # For buy orders, validate funds first
        if order.is_buy_order():
            # Estimate order value
            # Try to get original ticker from order metadata (for .NS suffix)
            price_symbol = order.symbol
            if (
                hasattr(order, "metadata")
                and order.metadata
                and "original_ticker" in order.metadata
            ):
                price_symbol = order.metadata["original_ticker"]
            elif (
                hasattr(order, "_metadata")
                and order._metadata
                and "original_ticker" in order._metadata
            ):
                price_symbol = order._metadata["original_ticker"]
            # Try with .NS suffix if not present
            elif not price_symbol.endswith(".NS") and not price_symbol.endswith(".BO"):
                price_symbol = f"{price_symbol}.NS"

            estimated_price = self.price_provider.get_price(price_symbol)
            if estimated_price is None:
                order.reject(f"Price not available for {order.symbol} (tried {price_symbol})")
                self._save_order(order)
                return

            estimated_value = float(estimated_price) * float(order.quantity)

            # Validate order value
            is_valid, error = self.order_simulator.validate_order_value(
                estimated_value, available_cash
            )

            if not is_valid:
                logger.warning(f"[WARN]? Order validation failed: {error}")
                order.reject(error)
                self._save_order(order)
                return

        # For sell orders, validate quantity
        if order.is_sell_order():
            can_sell, error = self.portfolio.can_sell(order.symbol, order.quantity)
            if not can_sell:
                logger.warning(f"[WARN]? Cannot sell: {error}")
                order.reject(error)
                self._save_order(order)
                return

        # Execute order
        success, message, execution_price = self.order_simulator.execute_order(order)

        if success and execution_price:
            # Mark as executed
            order.execute(execution_price, order.quantity)

            # Update portfolio and get P&L for sell orders
            trade_info = self._update_portfolio_after_execution(order, execution_price)

            # Record transaction with P&L info
            self._record_transaction(order, execution_price, trade_info)

            logger.info(
                f"? Order executed: {order.symbol} "
                f"{order.quantity} @ Rs {execution_price.amount:.2f}"
            )
        else:
            # Order execution failed or pending
            logger.warning(
                f"[WARN]? Order execution failed for {order.symbol}: {message}. "
                f"Order remains in {order.status.value} status."
            )

        # Save updated order
        self._save_order(order)

    def _update_portfolio_after_execution(
        self, order: Order, execution_price: Money
    ) -> dict | None:
        """
        Update portfolio and balance after order execution

        Returns:
            Trade info dict for sell orders (entry_price, realized_pnl, etc.), None for buy orders
        """
        account = self.store.get_account()
        trade_info = None

        if order.is_buy_order():
            # Add holding
            self.portfolio.add_holding(
                order.symbol, order.quantity, execution_price, order.exchange
            )

            # Deduct cash
            order_value = float(execution_price.amount) * order.quantity
            charges = self.order_simulator.calculate_charges(order_value, is_buy=True)
            total_cost = order_value + charges

            new_balance = account["available_cash"] - total_cost
            self.store.update_balance(new_balance)

            logger.info(
                f"? Deducted Rs {total_cost:.2f} (Value: Rs {order_value:.2f}, "
                f"Charges: Rs {charges:.2f})"
            )

        else:  # SELL
            # Get entry price before reducing holding
            holding = self.portfolio.get_holding(order.symbol)
            entry_price = holding.average_price.amount if holding else 0.0

            # Reduce holding
            remaining_holding, realized_pnl = self.portfolio.reduce_holding(
                order.symbol, order.quantity, execution_price
            )

            # Add cash
            order_value = float(execution_price.amount) * order.quantity
            charges = self.order_simulator.calculate_charges(order_value, is_buy=False)
            net_proceeds = order_value - charges

            new_balance = account["available_cash"] + net_proceeds
            self.store.update_balance(new_balance)

            # Prepare trade info for transaction recording
            trade_info = {
                "entry_price": entry_price,
                "exit_price": execution_price.amount,
                "realized_pnl": realized_pnl.amount,
                "charges": charges,
            }

            logger.info(
                f"? Added Rs {net_proceeds:.2f} (Value: Rs {order_value:.2f}, "
                f"Charges: Rs {charges:.2f}, P&L: Rs {realized_pnl.amount:.2f})"
            )

        # Update P&L
        self._update_pnl()

        # Persist holdings
        self._persist_holdings()

        return trade_info

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled, False otherwise
        """
        if not self.is_connected():
            raise ConnectionError("Not connected")

        order_dict = self.store.get_order_by_id(order_id)
        if not order_dict:
            logger.warning(f"[WARN]? Order not found: {order_id}")
            return False

        # Check if order can be cancelled
        status = order_dict.get("status")
        if status not in ["PENDING", "OPEN"]:
            logger.warning(f"[WARN]? Cannot cancel order in {status} status")
            return False

        # Update order status
        self.store.update_order(
            order_id, {"status": "CANCELLED", "cancelled_at": datetime.now().isoformat()}
        )

        logger.info(f"? Cancelled order: {order_id}")
        return True

    def get_order(self, order_id: str) -> Order | None:
        """Get order by ID"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        order_dict = self.store.get_order_by_id(order_id)
        if not order_dict:
            return None

        return self._dict_to_order(order_dict)

    def get_all_orders(self) -> list[Order]:
        """Get all orders"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        orders_data = self.store.get_all_orders()
        return [self._dict_to_order(o) for o in orders_data]

    def get_pending_orders(self) -> list[Order]:
        """Get pending orders"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        orders_data = self.store.get_pending_orders()
        return [self._dict_to_order(o) for o in orders_data]

    def check_and_execute_pending_orders(self) -> dict:
        """
        Check all pending limit orders and execute if price conditions are met

        Returns:
            Summary dict with counts of checked and executed orders
        """
        if not self.is_connected():
            raise ConnectionError("Not connected")

        summary = {"checked": 0, "executed": 0, "still_pending": 0}

        pending_orders = self.get_pending_orders()
        summary["checked"] = len(pending_orders)

        for order in pending_orders:
            # Only check limit orders (market orders execute immediately)
            if order.order_type != OrderType.LIMIT:
                continue

            # Try to execute the order
            try:
                self._execute_order(order)

                # Check if order executed (status changed from OPEN/PENDING)
                if order.is_executed():
                    summary["executed"] += 1
                    logger.info(
                        f"Pending limit order executed: {order.symbol} "
                        f"{order.transaction_type.value} @ Rs {order.execution_price.amount:.2f}"
                    )
                else:
                    summary["still_pending"] += 1
            except Exception as e:
                logger.error(f"Error checking/executing pending order {order.order_id}: {e}")
                summary["still_pending"] += 1

        if summary["executed"] > 0:
            logger.info(
                f"Pending orders check: {summary['executed']} executed, "
                f"{summary['still_pending']} still pending"
            )

        return summary

    # ===== PORTFOLIO MANAGEMENT =====

    def get_holdings(self) -> list[Holding]:
        """Get all holdings"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        # Update current prices
        holdings = self.portfolio.get_all_holdings()
        symbols = [h.symbol for h in holdings]

        if symbols:
            prices = self.price_provider.get_prices(symbols)
            self.portfolio.update_prices(prices)

        return holdings

    def get_holding(self, symbol: str) -> Holding | None:
        """Get holding for symbol"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        holding = self.portfolio.get_holding(symbol)

        if holding:
            # Update current price
            price = self.price_provider.get_price(symbol)
            if price:
                self.portfolio.update_price(symbol, Money(price))

        return holding

    # ===== ACCOUNT MANAGEMENT =====

    def get_account_limits(self) -> dict[str, Any]:
        """Get account limits"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        account = self.store.get_account()
        portfolio_value = self.portfolio.calculate_portfolio_value()

        return {
            "available_cash": Money(account["available_cash"]),
            "margin_used": Money(account.get("margin_used", 0.0)),
            "margin_available": Money(account["available_cash"]),
            "collateral": portfolio_value,
            "portfolio_value": portfolio_value,
            "total_value": Money(account["available_cash"]) + portfolio_value,
        }

    def get_available_balance(self) -> Money:
        """Get available cash balance"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        account = self.store.get_account()
        return Money(account["available_cash"])

    # ===== UTILITY METHODS =====

    def search_orders_by_symbol(self, symbol: str) -> list[Order]:
        """Search orders by symbol"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        orders_data = self.store.get_orders_by_symbol(symbol)
        return [self._dict_to_order(o) for o in orders_data]

    def cancel_pending_buys_for_symbol(self, symbol: str) -> int:
        """Cancel all pending BUY orders for symbol"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        orders = self.search_orders_by_symbol(symbol)
        cancelled_count = 0

        for order in orders:
            if order.is_buy_order() and order.is_active():
                if self.cancel_order(order.order_id):
                    cancelled_count += 1

        return cancelled_count

    # ===== HELPER METHODS =====

    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        self._order_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d")
        return f"PT{timestamp}{self._order_counter:04d}"

    def _save_order(self, order: Order) -> None:
        """Save order to storage"""
        order_dict = order.to_dict()

        # Convert price to float for JSON serialization
        if order_dict.get("price"):
            price_str = str(order_dict["price"])
            price_clean = price_str.replace("Rs ", "").replace(",", "").strip()
            order_dict["price"] = float(price_clean) if price_clean else None

        # Convert executed_price to float
        if order_dict.get("executed_price"):
            exec_price_str = str(order_dict["executed_price"])
            exec_price_clean = exec_price_str.replace("Rs ", "").replace(",", "").strip()
            order_dict["executed_price"] = float(exec_price_clean) if exec_price_clean else None

        # Check if order exists
        existing = self.store.get_order_by_id(order.order_id)

        if existing:
            # Update existing order
            self.store.update_order(order.order_id, order_dict)
        else:
            # Add new order
            self.store.add_order(order_dict)

    def _record_transaction(
        self, order: Order, execution_price: Money, trade_info: dict | None = None
    ) -> None:
        """
        Record a transaction with P&L for sell orders

        Args:
            order: The executed order
            execution_price: Execution price
            trade_info: Optional dict with entry_price, realized_pnl, etc. for sell orders
        """
        order_value = float(execution_price.amount) * order.quantity
        charges = self.order_simulator.calculate_charges(order_value, order.is_buy_order())

        transaction = {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "transaction_type": order.transaction_type.value,
            "quantity": order.quantity,
            "price": float(execution_price.amount),
            "order_value": order_value,
            "charges": charges,
            "timestamp": datetime.now().isoformat(),
        }

        # For sell orders, include P&L information from trade_info
        if order.is_sell_order() and trade_info:
            entry_price = trade_info["entry_price"]
            exit_price = trade_info["exit_price"]
            realized_pnl = trade_info["realized_pnl"]
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

            transaction["entry_price"] = float(entry_price)
            transaction["exit_price"] = float(exit_price)
            transaction["realized_pnl"] = float(realized_pnl)
            transaction["pnl_percentage"] = float(pnl_pct)
            transaction["exit_reason"] = (
                order._metadata.get("exit_reason", "Target Hit")
                if hasattr(order, "_metadata") and order._metadata
                else "Manual"
            )

            logger.info(
                f"? Trade completed: {order.symbol} - "
                f"Entry: Rs {entry_price:.2f}, Exit: Rs {exit_price:.2f}, "
                f"P&L: Rs {realized_pnl:+.2f} ({pnl_pct:+.2f}%)"
            )

        self.store.add_transaction(transaction)

    def _update_pnl(self) -> None:
        """Update P&L in account"""
        realized_pnl = self.portfolio.get_realized_pnl()
        unrealized_pnl = self.portfolio.calculate_unrealized_pnl()
        total_pnl = realized_pnl + unrealized_pnl

        self.store.update_pnl(
            float(total_pnl.amount), float(realized_pnl.amount), float(unrealized_pnl.amount)
        )

    def _persist_holdings(self) -> None:
        """Persist holdings to storage"""
        holdings = self.portfolio.to_dict_list()

        for holding in holdings:
            # Convert Money strings to float values for JSON serialization
            holding_data = holding.copy()
            holding_data["average_price"] = float(
                holding["average_price"].replace("Rs ", "").replace(",", "")
            )
            holding_data["current_price"] = float(
                holding["current_price"].replace("Rs ", "").replace(",", "")
            )
            holding_data["cost_basis"] = float(
                holding["cost_basis"].replace("Rs ", "").replace(",", "")
            )
            holding_data["market_value"] = float(
                holding["market_value"].replace("Rs ", "").replace(",", "")
            )
            holding_data["pnl"] = float(
                holding["pnl"].replace("Rs ", "").replace(",", "").replace("+", "")
            )
            self.store.add_or_update_holding(holding["symbol"], holding_data)

    def _dict_to_order(self, order_dict: dict) -> Order:
        """Convert dictionary to Order entity"""
        # Parse price - handle both numeric and formatted strings (for backward compatibility)
        price = None
        if order_dict.get("price"):
            price_val = order_dict["price"]
            if isinstance(price_val, (int, float)):
                price = Money(float(price_val))
            else:
                # Handle formatted string (backward compatibility)
                price_str = str(price_val)
                price_clean = price_str.replace("Rs ", "").replace(",", "").strip()
                if price_clean:
                    price = Money(float(price_clean))

        order = Order(
            symbol=order_dict["symbol"],
            quantity=order_dict["quantity"],
            order_type=OrderType[order_dict["order_type"]],
            transaction_type=TransactionType[order_dict["transaction_type"]],
            price=price,
            order_id=order_dict.get("order_id"),
            status=OrderStatus[order_dict["status"]],
            remarks=order_dict.get("remarks", ""),
        )

        # Restore timestamps
        if order_dict.get("placed_at"):
            order.placed_at = datetime.fromisoformat(order_dict["placed_at"])
        if order_dict.get("executed_at"):
            order.executed_at = datetime.fromisoformat(order_dict["executed_at"])
        if order_dict.get("cancelled_at"):
            order.cancelled_at = datetime.fromisoformat(order_dict["cancelled_at"])

        return order

    # ===== ADMIN METHODS =====

    def reset(self) -> None:
        """Reset paper trading account (WARNING: Destructive!)"""
        logger.warning("[WARN]? Resetting paper trading account...")
        self.store.reset()
        self.portfolio.reset()
        self._order_counter = 0
        self._initialize()
        logger.info("? Account reset complete")

    def get_summary(self) -> dict:
        """Get comprehensive account summary"""
        if not self.is_connected():
            self.connect()

        account = self.store.get_account()
        portfolio_summary = self.portfolio.get_summary()

        return {
            "account": account,
            "portfolio": portfolio_summary,
            "statistics": self.store.get_statistics(),
            "price_cache": self.price_provider.get_cache_info(),
        }
