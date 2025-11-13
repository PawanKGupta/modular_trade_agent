"""
Paper Trading Broker Adapter
Simulates broker operations without real money
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

from ...domain import (
    Order, Holding, Money, IBrokerGateway,
    OrderType, TransactionType, OrderStatus, Exchange
)
from ...config.paper_trading_config import PaperTradingConfig
from ..persistence import PaperTradeStore
from ..simulation import PortfolioManager, OrderSimulator, PriceProvider


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

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None,
        storage_path: Optional[str] = None
    ):
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
            cache_duration_seconds=self.config.price_cache_duration_seconds
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
                f"🆕 Initializing new paper trading account with "
                f"₹{self.config.initial_capital:,.2f}"
            )
            self.store.initialize_account(
                self.config.initial_capital,
                config=self.config.to_dict()
            )
        else:
            # Restore existing state
            logger.info(
                f"♻️ Restoring paper trading account "
                f"(Balance: ₹{account['available_cash']:,.2f})"
            )
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
                last_updated=datetime.fromisoformat(holding_data["last_updated"])
            )
            self.portfolio._holdings[symbol] = holding

        logger.info(f"♻️ Restored {len(holdings)} holdings")

    # ===== CONNECTION MANAGEMENT =====

    def connect(self) -> bool:
        """Establish connection (simulated)"""
        if self._connected:
            logger.info("✅ Already connected to paper trading")
            return True

        self._connected = True
        logger.info("✅ Connected to paper trading system")
        logger.info(f"💰 Available balance: ₹{self.get_available_balance().amount:,.2f}")
        logger.info(f"📊 Holdings: {len(self.portfolio.get_all_holdings())}")

        return True

    def disconnect(self) -> bool:
        """Disconnect (simulated)"""
        if not self._connected:
            return True

        # Save state before disconnect
        self.store.save_all()
        self._connected = False
        logger.info("👋 Disconnected from paper trading system")

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
            f"📝 Placing order: {order.transaction_type.value} "
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
            logger.error(f"❌ Order placement failed: {e}")
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
            estimated_price = self.price_provider.get_price(order.symbol)
            if estimated_price is None:
                order.reject(f"Price not available for {order.symbol}")
                self._save_order(order)
                return

            estimated_value = float(estimated_price) * float(order.quantity)

            # Validate order value
            is_valid, error = self.order_simulator.validate_order_value(
                estimated_value,
                available_cash
            )

            if not is_valid:
                logger.warning(f"⚠️ Order validation failed: {error}")
                order.reject(error)
                self._save_order(order)
                return

        # For sell orders, validate quantity
        if order.is_sell_order():
            can_sell, error = self.portfolio.can_sell(order.symbol, order.quantity)
            if not can_sell:
                logger.warning(f"⚠️ Cannot sell: {error}")
                order.reject(error)
                self._save_order(order)
                return

        # Execute order
        success, message, execution_price = self.order_simulator.execute_order(order)

        if success and execution_price:
            # Mark as executed
            order.execute(execution_price, order.quantity)

            # Update portfolio
            self._update_portfolio_after_execution(order, execution_price)

            # Record transaction
            self._record_transaction(order, execution_price)

            logger.info(
                f"✅ Order executed: {order.symbol} "
                f"{order.quantity} @ ₹{execution_price.amount:.2f}"
            )
        else:
            logger.info(f"⏸️ Order pending: {message}")

        # Save updated order
        self._save_order(order)

    def _update_portfolio_after_execution(self, order: Order, execution_price: Money) -> None:
        """Update portfolio and balance after order execution"""
        account = self.store.get_account()

        if order.is_buy_order():
            # Add holding
            self.portfolio.add_holding(
                order.symbol,
                order.quantity,
                execution_price,
                order.exchange
            )

            # Deduct cash
            order_value = float(execution_price.amount) * order.quantity
            charges = self.order_simulator.calculate_charges(order_value, is_buy=True)
            total_cost = order_value + charges

            new_balance = account["available_cash"] - total_cost
            self.store.update_balance(new_balance)

            logger.info(
                f"💸 Deducted ₹{total_cost:.2f} (Value: ₹{order_value:.2f}, "
                f"Charges: ₹{charges:.2f})"
            )

        else:  # SELL
            # Reduce holding
            remaining_holding, realized_pnl = self.portfolio.reduce_holding(
                order.symbol,
                order.quantity,
                execution_price
            )

            # Add cash
            order_value = float(execution_price.amount) * order.quantity
            charges = self.order_simulator.calculate_charges(order_value, is_buy=False)
            net_proceeds = order_value - charges

            new_balance = account["available_cash"] + net_proceeds
            self.store.update_balance(new_balance)

            logger.info(
                f"💰 Added ₹{net_proceeds:.2f} (Value: ₹{order_value:.2f}, "
                f"Charges: ₹{charges:.2f}, P&L: ₹{realized_pnl.amount:.2f})"
            )

        # Update P&L
        self._update_pnl()

        # Persist holdings
        self._persist_holdings()

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
            logger.warning(f"⚠️ Order not found: {order_id}")
            return False

        # Check if order can be cancelled
        status = order_dict.get("status")
        if status not in ["PENDING", "OPEN"]:
            logger.warning(f"⚠️ Cannot cancel order in {status} status")
            return False

        # Update order status
        self.store.update_order(order_id, {
            "status": "CANCELLED",
            "cancelled_at": datetime.now().isoformat()
        })

        logger.info(f"🚫 Cancelled order: {order_id}")
        return True

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        order_dict = self.store.get_order_by_id(order_id)
        if not order_dict:
            return None

        return self._dict_to_order(order_dict)

    def get_all_orders(self) -> List[Order]:
        """Get all orders"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        orders_data = self.store.get_all_orders()
        return [self._dict_to_order(o) for o in orders_data]

    def get_pending_orders(self) -> List[Order]:
        """Get pending orders"""
        if not self.is_connected():
            raise ConnectionError("Not connected")

        orders_data = self.store.get_pending_orders()
        return [self._dict_to_order(o) for o in orders_data]

    # ===== PORTFOLIO MANAGEMENT =====

    def get_holdings(self) -> List[Holding]:
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

    def get_holding(self, symbol: str) -> Optional[Holding]:
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

    def get_account_limits(self) -> Dict[str, Any]:
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

    def search_orders_by_symbol(self, symbol: str) -> List[Order]:
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

        # Check if order exists
        existing = self.store.get_order_by_id(order.order_id)

        if existing:
            # Update existing order
            self.store.update_order(order.order_id, order_dict)
        else:
            # Add new order
            self.store.add_order(order_dict)

    def _record_transaction(self, order: Order, execution_price: Money) -> None:
        """Record a transaction"""
        transaction = {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "transaction_type": order.transaction_type.value,
            "quantity": order.quantity,
            "price": float(execution_price.amount),
            "order_value": float(execution_price.amount) * order.quantity,
            "charges": self.order_simulator.calculate_charges(
                float(execution_price.amount) * order.quantity,
                order.is_buy_order()
            ),
            "timestamp": datetime.now().isoformat(),
        }

        self.store.add_transaction(transaction)

    def _update_pnl(self) -> None:
        """Update P&L in account"""
        realized_pnl = self.portfolio.get_realized_pnl()
        unrealized_pnl = self.portfolio.calculate_unrealized_pnl()
        total_pnl = realized_pnl + unrealized_pnl

        self.store.update_pnl(
            float(total_pnl.amount),
            float(realized_pnl.amount),
            float(unrealized_pnl.amount)
        )

    def _persist_holdings(self) -> None:
        """Persist holdings to storage"""
        holdings = self.portfolio.to_dict_list()

        for holding in holdings:
            # Convert Money strings to float values for JSON serialization
            holding_data = holding.copy()
            holding_data["average_price"] = float(holding["average_price"].replace("₹","").replace(",",""))
            holding_data["current_price"] = float(holding["current_price"].replace("₹","").replace(",",""))
            holding_data["cost_basis"] = float(holding["cost_basis"].replace("₹","").replace(",",""))
            holding_data["market_value"] = float(holding["market_value"].replace("₹","").replace(",",""))
            holding_data["pnl"] = float(holding["pnl"].replace("₹","").replace(",","").replace("+",""))
            self.store.add_or_update_holding(holding["symbol"], holding_data)

    def _dict_to_order(self, order_dict: Dict) -> Order:
        """Convert dictionary to Order entity"""
        order = Order(
            symbol=order_dict["symbol"],
            quantity=order_dict["quantity"],
            order_type=OrderType[order_dict["order_type"]],
            transaction_type=TransactionType[order_dict["transaction_type"]],
            price=Money(float(order_dict["price"])) if order_dict.get("price") else None,
            order_id=order_dict.get("order_id"),
            status=OrderStatus[order_dict["status"]],
            remarks=order_dict.get("remarks", "")
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
        logger.warning("⚠️ Resetting paper trading account...")
        self.store.reset()
        self.portfolio.reset()
        self._order_counter = 0
        self._initialize()
        logger.info("✅ Account reset complete")

    def get_summary(self) -> Dict:
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

