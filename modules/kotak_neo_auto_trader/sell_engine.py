#!/usr/bin/env python3
"""
Sell Order Management Engine for Kotak Neo Auto Trader

Manages profit-taking sell orders with EMA9 target tracking:
1. Places limit sell orders at market open (9:15 AM) with daily EMA9 as target
2. Monitors and updates orders every minute with lowest EMA9 value
3. Tracks order execution and updates trade history
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from datetime import time as dt_time
from decimal import ROUND_UP, Decimal
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.kotak_neo_auto_trader.services import (  # noqa: E402
    get_indicator_service,
    get_price_service,
)
from utils.logger import logger  # noqa: E402

try:
    from . import config
    from .auth import KotakNeoAuth
    from .market_data import KotakNeoMarketData
    from .order_state_manager import OrderStateManager
    from .orders import KotakNeoOrders
    from .portfolio import KotakNeoPortfolio
    from .scrip_master import KotakNeoScripMaster
    from .storage import (
        check_manual_buys_of_failed_orders,
        load_history,
        save_history,
    )
    from .utils.order_field_extractor import OrderFieldExtractor
    from .utils.order_status_parser import OrderStatusParser
    from .utils.symbol_utils import extract_base_symbol, extract_ticker_base
except ImportError:
    from modules.kotak_neo_auto_trader import config
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.market_data import KotakNeoMarketData
    from modules.kotak_neo_auto_trader.order_state_manager import OrderStateManager
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
    from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
    from modules.kotak_neo_auto_trader.storage import (
        check_manual_buys_of_failed_orders,
        load_history,
        save_history,
    )
    from modules.kotak_neo_auto_trader.utils.order_field_extractor import OrderFieldExtractor
    from modules.kotak_neo_auto_trader.utils.order_status_parser import OrderStatusParser
    from modules.kotak_neo_auto_trader.utils.symbol_utils import (
        extract_base_symbol,
        extract_ticker_base,
    )


class SellOrderManager:
    """
    Manages automated sell orders with EMA9 target tracking
    """

    def __init__(
        self,
        auth: KotakNeoAuth,
        positions_repo=None,  # Optional: PositionsRepository for database-only position tracking
        user_id: int | None = None,  # Optional: User ID for database operations
        orders_repo=None,  # Optional: OrdersRepository for metadata enrichment
        history_path: str = None,  # Deprecated: Kept for backward compatibility only
        max_workers: int = 10,
        price_manager=None,
        order_state_manager: OrderStateManager | None = None,
        order_verifier=None,  # Phase 3.2: Optional OrderStatusVerifier for shared results
    ):
        """
        Initialize sell order manager

        Args:
            auth: Authenticated Kotak Neo session
            positions_repo: PositionsRepository (optional) - required for database-only position tracking via get_open_positions()
            user_id: User ID (optional) - required for database operations via get_open_positions()
            orders_repo: OrdersRepository (optional) - for enriching position metadata
            history_path: Deprecated - kept for backward compatibility only, not used for position tracking
            max_workers: Maximum threads for parallel monitoring
            price_manager: Optional LivePriceManager for real-time prices
            order_state_manager: Optional OrderStateManager for unified state management
            order_verifier: Optional OrderStatusVerifier for shared results

        Note:
            positions_repo and user_id are required when calling get_open_positions().
            They are optional in __init__ for backward compatibility with test files and standalone scripts.
        """

        self.auth = auth
        self.orders = KotakNeoOrders(auth)
        self.portfolio = KotakNeoPortfolio(auth, price_manager=price_manager)
        self.market_data = KotakNeoMarketData(auth)
        self.history_path = history_path or config.TRADES_HISTORY_PATH  # Deprecated, kept for OrderStateManager
        self.max_workers = max_workers
        self.price_manager = price_manager
        self.positions_repo = positions_repo
        self.orders_repo = orders_repo  # For metadata enrichment
        self.user_id = user_id
        self.order_verifier = order_verifier  # Phase 3.2: OrderStatusVerifier for shared results

        # Initialize OrderStateManager if not provided (for backward compatibility)
        self.state_manager = order_state_manager
        if self.state_manager is None:
            try:
                # Try to create OrderStateManager with same history_path
                data_dir = str(Path(self.history_path).parent) if self.history_path else "data"
                self.state_manager = OrderStateManager(
                    history_path=self.history_path, data_dir=data_dir
                )
                logger.debug("OrderStateManager initialized automatically")
            except Exception as e:
                logger.debug(f"OrderStateManager not available, using legacy mode: {e}")
                self.state_manager = None

        # Initialize scrip master for symbol/token resolution
        self.scrip_master = KotakNeoScripMaster(
            auth_client=auth.client if hasattr(auth, "client") else None
        )

        # Load scrip master data (use cache if available)
        try:
            self.scrip_master.load_scrip_master(force_download=False)
            logger.info("Scrip master loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load scrip master: {e}. Will use symbols as-is.")

        # Initialize unified services
        self.price_service = get_price_service(
            live_price_manager=self.price_manager, enable_caching=True
        )
        self.indicator_service = get_indicator_service(
            price_service=self.price_service, enable_caching=True
        )
        # PositionLoader removed - using database-only tracking via PositionsRepository

        # Track active sell orders {symbol: {'order_id': str, 'target_price': float}}
        # Legacy mode: Used when OrderStateManager is not available
        self.active_sell_orders: dict[str, dict[str, Any]] = {}

        # Track lowest EMA9 values {symbol: float}
        self.lowest_ema9: dict[str, float] = {}

        logger.info(f"SellOrderManager initialized with {max_workers} worker threads")

    def _register_order(
        self,
        symbol: str,
        order_id: str,
        target_price: float,
        qty: int,
        ticker: str | None = None,
        **kwargs,
    ) -> None:
        """
        Helper method to register order using OrderStateManager if available, otherwise legacy mode.

        Args:
            symbol: Trading symbol
            order_id: Order ID
            target_price: Target price
            qty: Quantity
            ticker: Optional ticker symbol
            **kwargs: Additional metadata
        """
        if self.state_manager:
            self.state_manager.register_sell_order(
                symbol=symbol,
                order_id=order_id,
                target_price=target_price,
                qty=qty,
                ticker=ticker,
                **kwargs,
            )
            # Sync active_sell_orders for backward compatibility
            base_symbol = extract_base_symbol(symbol).upper()
            self.active_sell_orders[base_symbol] = {
                "order_id": order_id,
                "target_price": target_price,
                "qty": qty,
                "ticker": ticker,
                **kwargs,
            }
        else:
            # Legacy mode
            base_symbol = extract_base_symbol(symbol).upper()
            self.active_sell_orders[base_symbol] = {
                "order_id": order_id,
                "target_price": target_price,
                "qty": qty,
                "ticker": ticker,
                **kwargs,
            }

    def _update_order_price(self, symbol: str, new_price: float) -> bool:
        """
        Helper method to update order price using OrderStateManager if available.

        Args:
            symbol: Trading symbol
            new_price: New target price

        Returns:
            True if updated, False otherwise
        """
        if self.state_manager:
            result = self.state_manager.update_sell_order_price(symbol, new_price)
            if result:
                # Sync active_sell_orders for backward compatibility
                base_symbol = extract_base_symbol(symbol).upper()
                if base_symbol in self.active_sell_orders:
                    self.active_sell_orders[base_symbol]["target_price"] = new_price
            return result
        else:
            # Legacy mode
            base_symbol = extract_base_symbol(symbol).upper()
            if base_symbol in self.active_sell_orders:
                self.active_sell_orders[base_symbol]["target_price"] = new_price
                return True
            return False

    def _remove_order(self, symbol: str, reason: str | None = None) -> bool:
        """
        Helper method to remove order using OrderStateManager if available.

        Args:
            symbol: Trading symbol
            reason: Optional reason for removal

        Returns:
            True if removed, False otherwise
        """
        base_symbol = extract_base_symbol(symbol).upper()

        if self.state_manager:
            # Always sync from OrderStateManager first to ensure consistency
            state_orders = self.state_manager.get_active_sell_orders()
            self.active_sell_orders.update(state_orders)

            # Try to remove from OrderStateManager (may or may not be there)
            result = self.state_manager.remove_from_tracking(symbol, reason=reason)

            # Always remove from self.active_sell_orders if present (for backward compatibility)
            # This ensures removal even if OrderStateManager didn't have it
            removed = False
            if base_symbol in self.active_sell_orders:
                del self.active_sell_orders[base_symbol]
                removed = True

            # Return True if either OrderStateManager had it or we removed from local dict
            return result or removed
        else:
            # Legacy mode
            if base_symbol in self.active_sell_orders:
                del self.active_sell_orders[base_symbol]
                return True
            return False

    def _get_active_orders(self) -> dict[str, dict[str, Any]]:
        """
        Helper method to get active orders, syncing from OrderStateManager if available.

        Returns:
            Dict of active sell orders
        """
        if self.state_manager:
            # Sync from OrderStateManager
            state_orders = self.state_manager.get_active_sell_orders()
            self.active_sell_orders.update(state_orders)

            # Initialize lowest_ema9 from target_price if not already set
            for symbol, order_info in state_orders.items():
                if symbol not in self.lowest_ema9:
                    target_price = order_info.get("target_price", 0)
                    if target_price > 0:
                        self.lowest_ema9[symbol] = target_price

        return self.active_sell_orders

    def _mark_order_executed(
        self,
        symbol: str,
        order_id: str,
        execution_price: float,
        execution_qty: int | None = None,
    ) -> bool:
        """
        Helper method to mark order as executed using OrderStateManager if available.

        Args:
            symbol: Trading symbol
            order_id: Order ID
            execution_price: Execution price
            execution_qty: Optional execution quantity

        Returns:
            True if successful, False otherwise
        """
        if self.state_manager:
            result = self.state_manager.mark_order_executed(
                symbol=symbol,
                order_id=order_id,
                execution_price=execution_price,
                execution_qty=execution_qty,
            )
            if result:
                # Sync active_sell_orders for backward compatibility
                base_symbol = extract_base_symbol(symbol).upper()
                if base_symbol in self.active_sell_orders:
                    del self.active_sell_orders[base_symbol]
            return result
        else:
            # Legacy mode - just remove from tracking
            base_symbol = extract_base_symbol(symbol).upper()
            if base_symbol in self.active_sell_orders:
                del self.active_sell_orders[base_symbol]
                return True
            return False

    @staticmethod
    def round_to_tick_size(price: float, exchange: str = "NSE") -> float:
        """
        Round price to exchange-specific tick size

        NSE Tick Size Rules (Cash Equity Segment):
        - All price ranges: Rs 0.05 (as per NSE circular)

        BSE Tick Size Rules:
        - Rs 0 to Rs 10: Rs 0.01
        - Rs 10+ to Rs 20: Rs 0.05
        - Rs 20+ to Rs 50: Rs 0.05
        - Rs 50+: Rs 0.05

        Args:
            price: Price to round
            exchange: Exchange name ("NSE" or "BSE")

        Returns:
            Price rounded to valid tick size (rounded UP to next valid tick)
        """
        if price <= 0:
            return price

        # Determine tick size based on exchange and price
        if exchange.upper() == "BSE":
            # BSE has price-dependent tick sizes
            if price < 10:
                tick_size = 0.01
            else:
                tick_size = 0.05
        # NSE tick size rules (cash equity segment)
        # 0-100: Rs 0.05
        # 100-1000: Rs 0.05
        # 1000+: Rs 0.10
        elif price >= 1000:
            tick_size = 0.10
        else:
            tick_size = 0.05

        # Round UP to next valid tick (ceiling)
        # Use decimal arithmetic to avoid floating point precision issues
        # Convert to Decimal for precise arithmetic
        price_decimal = Decimal(str(price))
        tick_decimal = Decimal(str(tick_size))

        # Round UP to next tick (always round in favor of seller)
        rounded = (price_decimal / tick_decimal).quantize(
            Decimal("1"), rounding=ROUND_UP
        ) * tick_decimal

        # Convert back to float with 2 decimal places
        return float(rounded.quantize(Decimal("0.01")))

    def get_open_positions(self) -> list[dict[str, Any]]:
        """
        Get all open positions from database (positions table).

        Database-only: No file fallback. Uses positions table as single source of truth.

        Returns:
            List of open trade entries in format expected by sell order placement
        """
        if not self.positions_repo or not self.user_id:
            raise ValueError(
                "PositionsRepository and user_id are required for database-only position tracking. "
                "Please provide positions_repo and user_id when initializing SellOrderManager."
            )

        open_positions = []
        positions = self.positions_repo.list(self.user_id)

        for pos in positions:
            if pos.closed_at is None:  # Open position
                # Get ticker and placed_symbol from matching ONGOING order if available
                ticker = f"{pos.symbol}.NS"
                placed_symbol = f"{pos.symbol}-EQ"

                # Try to get ticker and placed_symbol from most recent ONGOING order
                if self.orders_repo:
                    try:
                        from src.infrastructure.db.models import OrderStatus as DbOrderStatus
                        from .utils.symbol_utils import extract_base_symbol

                        ongoing_orders = self.orders_repo.list(
                            self.user_id, status=DbOrderStatus.ONGOING
                        )
                        for order in ongoing_orders:
                            if (
                                order.side.lower() == "buy"
                                and extract_base_symbol(order.symbol).upper()
                                == pos.symbol.upper()
                            ):
                                # Found matching order - use its metadata
                                if order.order_metadata and isinstance(
                                    order.order_metadata, dict
                                ):
                                    ticker = order.order_metadata.get("ticker", ticker)
                                placed_symbol = order.symbol  # Full broker symbol
                                break
                    except Exception as e:
                        logger.debug(
                            f"Failed to enrich position metadata from orders: {e}"
                        )

                # Convert Positions model to trade dict format
                open_positions.append(
                    {
                        "symbol": pos.symbol,
                        "ticker": ticker,
                        "qty": pos.quantity,
                        "entry_price": pos.avg_price,
                        "entry_time": pos.opened_at.isoformat(),
                        "status": "open",
                        "placed_symbol": placed_symbol,
                    }
                )

        logger.debug(f"Loaded {len(open_positions)} open positions from database")
        return open_positions

    def get_current_ema9(self, ticker: str, broker_symbol: str = None) -> float | None:
        """
        Calculate real-time daily EMA9 value using current LTP

        EMA9 updates in real-time during trading as current candle forms.
        Formula: Today's EMA9 = (Current LTP x k) + (Yesterday's EMA9 x (1 - k))
        where k = 2 / (period + 1) = 2 / 10 = 0.2

        This method now uses IndicatorService for calculation, maintaining exact same behavior.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            broker_symbol: Broker symbol for LTP fetch (e.g., 'RELIANCE-EQ')

        Returns:
            Current real-time EMA9 value or None if failed
        """
        # Use IndicatorService for real-time EMA9 calculation
        # This maintains exact same logic as before but uses unified service
        return self.indicator_service.calculate_ema9_realtime(
            ticker=ticker, broker_symbol=broker_symbol, current_ltp=None
        )

    def get_current_ltp(self, ticker: str, broker_symbol: str = None) -> float | None:
        """
        Get current Last Traded Price for a ticker
        Uses LivePriceManager if available, falls back to yfinance

        This method now uses PriceService for fetching, maintaining exact same behavior.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            broker_symbol: Broker symbol (e.g., 'RELIANCE-EQ') - optional

        Returns:
            Current LTP or None
        """
        # Extract base symbol using utility function
        base_symbol = extract_ticker_base(ticker)

        # Use PriceService for real-time price fetching
        # This maintains exact same logic as before but uses unified service
        return self.price_service.get_realtime_price(
            symbol=base_symbol, ticker=ticker, broker_symbol=broker_symbol
        )

    def place_sell_order(self, trade: dict[str, Any], target_price: float) -> str | None:
        """
        Place a limit sell order for a position

        Args:
            trade: Trade entry from history
            target_price: Target sell price (EMA9)

        Returns:
            Order ID if successful, None otherwise
        """
        try:
            symbol = trade.get("placed_symbol") or trade.get("symbol")
            if not symbol:
                logger.error("No symbol found in trade entry")
                return None

            # Ensure symbol has exchange suffix
            if not symbol.endswith(("-EQ", "-BE", "-BL", "-BZ")):
                symbol = f"{symbol}-EQ"

            # Try to get correct trading symbol from scrip master
            if self.scrip_master and self.scrip_master.symbol_map:
                correct_symbol = self.scrip_master.get_trading_symbol(symbol)
                if correct_symbol:
                    logger.debug(f"Resolved {symbol} -> {correct_symbol} via scrip master")
                    symbol = correct_symbol

            qty = trade.get("qty", 0)
            if qty <= 0:
                logger.warning(f"Invalid quantity {qty} for {symbol}")
                return None

            # Round price to valid tick size
            rounded_price = self.round_to_tick_size(target_price)
            if rounded_price != target_price:
                logger.debug(
                    f"Rounded price from Rs {target_price:.4f} to Rs {rounded_price:.2f} (tick size)"
                )

            # Place limit sell order
            logger.info(f"Placing LIMIT SELL order: {symbol} x{qty} @ Rs {rounded_price:.2f}")

            response = self.orders.place_limit_sell(
                symbol=symbol,
                quantity=qty,
                price=rounded_price,
                variety="REGULAR",  # Regular day order (not AMO)
                exchange=config.DEFAULT_EXCHANGE,
                product=config.DEFAULT_PRODUCT,
            )

            if not response:
                logger.error(f"Failed to place sell order for {symbol}")
                return None

            # Extract order ID - try multiple response formats
            order_id = (
                response.get("nOrdNo")  # Direct field (most common)
                or response.get("data", {}).get("nOrdNo")
                or response.get("data", {}).get("order_id")
                or response.get("data", {}).get("neoOrdNo")
                or response.get("order", {}).get("neoOrdNo")
                or response.get("neoOrdNo")
                or response.get("orderId")
            )

            if order_id:
                logger.info(
                    f"Sell order placed: {symbol} @ Rs {rounded_price:.2f}, Order ID: {order_id}"
                )
                return str(order_id)
            else:
                logger.warning(f"Order placed but no ID returned: {response}")
                return None

        except Exception as e:
            logger.error(f"Error placing sell order: {e}")
            return None

    def update_sell_order(self, order_id: str, symbol: str, qty: int, new_price: float) -> bool:
        """
        Update (modify) an existing sell order with new price
        Uses modify_order API instead of cancel+replace for efficiency

        Args:
            order_id: Existing order ID
            symbol: Trading symbol
            qty: Order quantity
            new_price: New target price

        Returns:
            True if successful
        """
        try:
            # Round price to valid tick size
            rounded_price = self.round_to_tick_size(new_price)
            if rounded_price != new_price:
                logger.debug(
                    f"Rounded price from Rs {new_price:.4f} to Rs {rounded_price:.2f} (tick size)"
                )

            # Modify existing order directly (more efficient than cancel+replace)
            logger.info(f"Modifying order {order_id}: {symbol} x{qty} @ Rs {rounded_price:.2f}")

            modify_resp = self.orders.modify_order(
                order_id=str(order_id),
                quantity=qty,
                price=rounded_price,
                order_type="L",  # L = Limit order
            )

            if not modify_resp:
                logger.error(f"Failed to modify order {order_id}")
                # Fallback to cancel+replace if modify fails
                logger.info(f"Falling back to cancel+replace for order {order_id}")
                return self._cancel_and_replace_order(order_id, symbol, qty, rounded_price)

            # Validate modification response
            if isinstance(modify_resp, dict):
                stat = modify_resp.get("stat", "")
                if stat == "Ok":
                    logger.info(f"Order modified successfully: {symbol} @ Rs {rounded_price:.2f}")

                    # Update tracking (order_id stays same, just update price)
                    self._update_order_price(symbol, rounded_price)

                    return True
                else:
                    logger.warning(f"Modify order returned non-Ok status: {modify_resp}")
                    # Fallback to cancel+replace
                    logger.info(f"Falling back to cancel+replace for order {order_id}")
                    return self._cancel_and_replace_order(order_id, symbol, qty, rounded_price)

            return False

        except Exception as e:
            logger.error(f"Error updating sell order: {e}")
            # Try fallback on exception
            try:
                logger.info("Falling back to cancel+replace due to error")
                return self._cancel_and_replace_order(order_id, symbol, qty, rounded_price)
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return False

    def _cancel_and_replace_order(self, order_id: str, symbol: str, qty: int, price: float) -> bool:
        """
        Fallback method: Cancel existing order and place new one
        Used when modify_order fails

        Args:
            order_id: Existing order ID to cancel
            symbol: Trading symbol
            qty: Order quantity
            price: New target price (already rounded)

        Returns:
            True if successful
        """
        try:
            # Cancel existing order
            logger.info(f"Cancelling order {order_id}")
            cancel_resp = self.orders.cancel_order(order_id)

            if not cancel_resp:
                logger.error(f"Failed to cancel order {order_id}")
                return False

            # Place new order with updated price
            logger.info(f"Placing new sell order: {symbol} x{qty} @ Rs {price:.2f}")
            response = self.orders.place_limit_sell(
                symbol=symbol,
                quantity=qty,
                price=price,
                variety="REGULAR",
                exchange=config.DEFAULT_EXCHANGE,
                product=config.DEFAULT_PRODUCT,
            )

            if not response:
                logger.error(f"Failed to place replacement sell order for {symbol}")
                return False

            # Extract new order ID
            new_order_id = (
                response.get("nOrdNo")
                or response.get("data", {}).get("nOrdNo")
                or response.get("data", {}).get("order_id")
                or response.get("data", {}).get("neoOrdNo")
                or response.get("order", {}).get("neoOrdNo")
                or response.get("neoOrdNo")
                or response.get("orderId")
            )

            if new_order_id:
                logger.info(
                    f"Replacement order placed: {symbol} @ Rs {price:.2f}, Order ID: {new_order_id}"
                )
                # Update tracking with new order ID
                base_symbol = extract_base_symbol(symbol)
                old_entry = self.active_sell_orders.get(base_symbol, {})
                self._register_order(
                    symbol=symbol,
                    order_id=str(new_order_id),
                    target_price=price,
                    qty=qty,
                    ticker=old_entry.get("ticker"),
                    placed_symbol=symbol,
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Error in cancel+replace: {e}")
            return False

    def check_order_execution(self) -> list[str]:
        """
        Check which sell orders have been executed

        Phase 3.2: Consolidate order verification
        - First checks OrderStatusVerifier results if available (avoids duplicate API calls)
        - Falls back to direct API call if OrderStatusVerifier doesn't have results

        Returns:
            List of executed order IDs
        """
        executed_ids = []

        # Phase 3.2: Check OrderStatusVerifier results first if available
        if self.order_verifier:
            try:
                # Get verification results for all our tracked sell orders
                for symbol, order_info in self.active_sell_orders.items():
                    order_id = order_info.get("order_id")
                    if not order_id:
                        continue

                    # Check OrderStatusVerifier result for this order
                    result = self.order_verifier.get_verification_result(order_id)
                    if result and result.get('status') == 'EXECUTED':
                        executed_ids.append(str(order_id))
                        logger.info(
                            f"Sell order executed (from OrderStatusVerifier): Order ID {order_id}"
                        )

                # If we found results from OrderStatusVerifier, return them
                if executed_ids:
                    return executed_ids
            except Exception as e:
                logger.debug(f"Error checking OrderStatusVerifier results: {e}")
                # Fall through to direct API call

        # Fallback: Use direct API call if OrderStatusVerifier not available or no results found
        try:
            executed_orders = self.orders.get_executed_orders()

            if not executed_orders:
                return []

            # Filter for our tracked sell orders
            for order in executed_orders:
                order_id = order.get("neoOrdNo") or order.get("orderId")
                if order_id and any(
                    info.get("order_id") == str(order_id)
                    for info in self.active_sell_orders.values()
                ):
                    executed_ids.append(str(order_id))
                    logger.info(f"Sell order executed: Order ID {order_id}")

            return executed_ids

        except Exception as e:
            logger.error(f"Error checking order execution: {e}")
            return []

    def mark_position_closed(self, symbol: str, exit_price: float, order_id: str) -> bool:
        """
        Mark a position as closed in trade history

        Args:
            symbol: Trading symbol (base, without suffix)
            exit_price: Execution price
            order_id: Order ID

        Returns:
            True if successful
        """
        try:
            history = load_history(self.history_path)
            trades = history.get("trades", [])

            updated = False
            for trade in trades:
                trade_symbol = trade.get("symbol", "").upper()
                if trade_symbol == symbol.upper() and trade.get("status") == "open":
                    # Mark as closed
                    trade["status"] = "closed"
                    trade["exit_price"] = exit_price
                    trade["exit_time"] = datetime.now().isoformat()
                    trade["exit_reason"] = "EMA9_TARGET"
                    trade["sell_order_id"] = order_id

                    # Calculate P&L
                    entry_price = trade.get("entry_price", 0)
                    qty = trade.get("qty", 0)
                    if entry_price and qty:
                        pnl = (exit_price - entry_price) * qty
                        pnl_pct = ((exit_price / entry_price) - 1) * 100
                        trade["pnl"] = pnl
                        trade["pnl_pct"] = pnl_pct
                        logger.info(
                            f"Position closed: {symbol} - P&L: Rs {pnl:.2f} ({pnl_pct:+.2f}%)"
                        )

                    updated = True
                    break

            if updated:
                save_history(self.history_path, history)
                logger.info(f"Trade history updated: {symbol} marked as closed")

                # Directly update positions table if available (optimization)
                if self.positions_repo and self.user_id:
                    try:
                        pos = self.positions_repo.get_by_symbol(self.user_id, symbol)
                        if pos:
                            pos.closed_at = datetime.now()
                            self.positions_repo.db.commit()
                            logger.debug(f"Position {symbol} marked as closed in DB")
                    except Exception as e:
                        logger.warning(f"Failed to update position in DB: {e}")

                return True
            else:
                logger.warning(f"No open position found for {symbol} in trade history")
                return False

        except Exception as e:
            logger.error(f"Error marking position closed: {e}")
            return False

    def is_market_open(self) -> bool:
        """
        Check if market is currently open (9:15 AM - 3:30 PM)

        Returns:
            True if market is open
        """
        now = datetime.now().time()
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 30)

        return market_open <= now <= market_close

    def _cleanup_rejected_orders(self):
        """
        Remove rejected/cancelled orders from active tracking
        Also detects manual buys of bot-recommended stocks
        """
        try:
            # 1. Detect manual buys
            self._detect_and_handle_manual_buys()

            # 2. Detect manual sells and handle
            manual_sells = self._detect_manual_sells()
            if manual_sells:
                self._handle_manual_sells(manual_sells)

            # 3. Remove rejected/cancelled orders
            self._remove_rejected_orders()

        except Exception as e:
            logger.warning(f"Error cleaning up rejected orders: {e}")

    def _detect_and_handle_manual_buys(self) -> list[str]:
        """
        Detect manual buys of failed orders.

        Returns:
            List of symbols that were manually bought
        """
        manual_buys = check_manual_buys_of_failed_orders(self.history_path, self.orders)
        if manual_buys:
            logger.info(
                f"Detected {len(manual_buys)} manual buys of bot recommendations: {', '.join(manual_buys)}"
            )
        return manual_buys

    def _detect_manual_sells(self) -> dict[str, dict[str, Any]]:
        """
        Detect manual sell orders by checking executed SELL orders.

        Returns:
            Dict mapping symbol -> {'qty': int, 'orders': List[Dict]}
        """
        executed_orders = self.orders.get_executed_orders()
        if not executed_orders:
            return {}

        manual_sells = {}

        for order in executed_orders:
            # Only check SELL orders
            if not OrderFieldExtractor.is_sell_order(order):
                continue

            order_id = OrderFieldExtractor.get_order_id(order)
            symbol = extract_base_symbol(OrderFieldExtractor.get_symbol(order))

            # Check if this is a manual sell (order_id not in our tracked orders)
            if not self._is_tracked_order(order_id) and symbol:
                qty = OrderFieldExtractor.get_quantity(order)
                avg_price = OrderFieldExtractor.get_price(order)

                if qty > 0:
                    if symbol not in manual_sells:
                        manual_sells[symbol] = {"qty": 0, "orders": []}

                    manual_sells[symbol]["qty"] += qty
                    manual_sells[symbol]["orders"].append(
                        {"order_id": order_id, "qty": qty, "price": avg_price}
                    )

        return manual_sells

    def _is_tracked_order(self, order_id: str) -> bool:
        """
        Check if order_id is in our tracked orders.

        Args:
            order_id: Order ID to check

        Returns:
            True if order is tracked, False otherwise
        """
        return any(info.get("order_id") == order_id for info in self.active_sell_orders.values())

    def _handle_manual_sells(self, manual_sells: dict[str, dict[str, Any]]):
        """
        Handle detected manual sells: cancel bot orders, update trade history.

        Args:
            manual_sells: Dict mapping symbol -> sell info
        """
        rejected_symbols = []

        for symbol, sell_info in manual_sells.items():
            symbol_upper = symbol.upper()

            # Skip if not in tracked orders
            tracked_symbol = next(
                (s for s in self.active_sell_orders.keys() if s.upper() == symbol_upper), None
            )
            if not tracked_symbol:
                continue

            order_info = self.active_sell_orders[tracked_symbol]
            sold_qty = sell_info["qty"]
            tracked_qty = order_info.get("qty", 0)
            remaining_qty = tracked_qty - sold_qty

            logger.warning(f"Manual sell detected for {symbol}: sold {sold_qty} shares")

            # Cancel existing bot order (wrong quantity now)
            self._cancel_bot_order_for_manual_sell(symbol, order_info)

            # Update trade history
            self._update_trade_history_for_manual_sell(symbol, sell_info, remaining_qty)

            # Remove from tracking
            rejected_symbols.append(tracked_symbol)
            if remaining_qty > 0:
                logger.info(
                    f"Removing {symbol} from tracking: will place new order with qty={remaining_qty}"
                )
            else:
                logger.info(f"Removing {symbol} from tracking: fully sold manually")

        # Remove from tracking
        for symbol in rejected_symbols:
            self._remove_from_tracking(symbol)

    def _cancel_bot_order_for_manual_sell(self, symbol: str, order_info: dict[str, Any]):
        """
        Cancel bot order when manual sell detected.

        Args:
            symbol: Symbol name
            order_info: Order info dict
        """
        order_id = order_info.get("order_id")
        if order_id:
            try:
                logger.info(f"Cancelling order {order_id} for {symbol} due to manual sale")
                self.orders.cancel_order(order_id)
            except Exception as e:
                logger.warning(f"Failed to cancel order {order_id}: {e}")

    def _update_trade_history_for_manual_sell(
        self, symbol: str, sell_info: dict[str, Any], remaining_qty: int
    ):
        """
        Update trade history for manual sell.

        Args:
            symbol: Symbol name
            sell_info: Manual sell info dict
            remaining_qty: Remaining quantity after manual sell
        """
        try:
            history = load_history(self.history_path)
            trades = history.get("trades", [])

            symbol_upper = symbol.upper()
            sold_qty = sell_info["qty"]

            for trade in trades:
                if (
                    trade.get("symbol", "").upper() == symbol_upper
                    and trade.get("status") == "open"
                ):
                    if remaining_qty <= 0:
                        # Full manual exit
                        self._mark_trade_as_closed(trade, sell_info, sold_qty, "MANUAL_EXIT")
                        logger.info(
                            f"Trade history updated: {symbol} marked as manually closed (full exit)"
                        )
                    else:
                        # Partial manual exit
                        trade["qty"] = remaining_qty

                        if "partial_exits" not in trade:
                            trade["partial_exits"] = []

                        avg_price = self._calculate_avg_price_from_orders(sell_info["orders"])
                        trade["partial_exits"].append(
                            {
                                "qty": sold_qty,
                                "exit_time": datetime.now().isoformat(),
                                "exit_reason": "MANUAL_PARTIAL_EXIT",
                                "exit_price": avg_price,
                            }
                        )

                        logger.info(
                            f"Trade history updated: {symbol} qty reduced to {remaining_qty} (sold {sold_qty} manually)"
                        )
                    break

            save_history(self.history_path, history)
        except Exception as e:
            logger.warning(f"Could not update trade history for manual sale of {symbol}: {e}")

    def _mark_trade_as_closed(
        self, trade: dict[str, Any], sell_info: dict[str, Any], sold_qty: int, exit_reason: str
    ):
        """
        Mark trade as closed in trade history.

        Args:
            trade: Trade dict from history
            sell_info: Manual sell info dict
            sold_qty: Quantity sold
            exit_reason: Exit reason string
        """
        trade["status"] = "closed"
        trade["exit_time"] = datetime.now().isoformat()
        trade["exit_reason"] = exit_reason

        avg_price = self._calculate_avg_price_from_orders(sell_info["orders"])
        trade["exit_price"] = avg_price

        entry_price = trade.get("entry_price", 0)
        if entry_price and avg_price:
            pnl = (avg_price - entry_price) * sold_qty
            pnl_pct = ((avg_price / entry_price) - 1) * 100
            trade["pnl"] = pnl
            trade["pnl_pct"] = pnl_pct

    def _calculate_avg_price_from_orders(self, orders: list[dict[str, Any]]) -> float:
        """
        Calculate average price from order list.

        Args:
            orders: List of order dicts with 'price' and 'qty'

        Returns:
            Average price as float
        """
        if not orders:
            return 0.0

        total_value = sum(o["price"] * o["qty"] for o in orders)
        total_qty = sum(o["qty"] for o in orders)

        return total_value / total_qty if total_qty > 0 else 0.0

    def _remove_rejected_orders(self):
        """
        Remove rejected/cancelled orders from active tracking.
        """
        all_orders = self.orders.get_orders()
        if not all_orders or "data" not in all_orders:
            return

        rejected_symbols = []

        for symbol, order_info in list(self.active_sell_orders.items()):
            order_id = order_info.get("order_id")
            if not order_id:
                continue

            # Find this order in broker orders
            broker_order = self._find_order_in_broker_orders(order_id, all_orders["data"])
            if broker_order:
                # Check if order is rejected or cancelled
                if OrderStatusParser.is_rejected(broker_order) or OrderStatusParser.is_cancelled(
                    broker_order
                ):
                    status = OrderStatusParser.parse_status(broker_order)
                    rejected_symbols.append(symbol)
                    logger.info(
                        f"Removing {symbol} from tracking: order {order_id} is {status.value}"
                    )

        # Clean up rejected/cancelled orders
        for symbol in rejected_symbols:
            self._remove_from_tracking(symbol)

        if rejected_symbols:
            logger.info(f"Cleaned up {len(rejected_symbols)} invalid orders from tracking")

    def _find_order_in_broker_orders(
        self, order_id: str, broker_orders: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """
        Find order in broker orders list by order ID.

        Args:
            order_id: Order ID to find
            broker_orders: List of broker order dicts

        Returns:
            Order dict if found, None otherwise
        """
        for order in broker_orders:
            broker_order_id = OrderFieldExtractor.get_order_id(order)
            if str(broker_order_id) == str(order_id):
                return order
        return None

    def _remove_from_tracking(self, symbol: str, reason: str | None = None):
        """
        Remove symbol from active tracking.

        Args:
            symbol: Symbol to remove
            reason: Optional reason for removal
        """
        self._remove_order(symbol, reason=reason)
        if symbol in self.lowest_ema9:
            del self.lowest_ema9[symbol]

    def has_completed_sell_order(self, symbol: str) -> dict[str, Any] | None:
        """
        Check if a symbol has a completed/executed sell order.

        Phase 3.2: Consolidate order verification
        - First checks OrderStatusVerifier results if available (avoids duplicate API calls)
        - Falls back to direct API call if OrderStatusVerifier doesn't have results

        Args:
            symbol: Base symbol (e.g., 'DALBHARAT') or full symbol (e.g., 'DALBHARAT-EQ')

        Returns:
            Dict with order details {'order_id': str, 'price': float} if completed order found,
            None otherwise
        """
        # Phase 3.2: Check OrderStatusVerifier results first if available
        if self.order_verifier:
            try:
                # Get verification results for this symbol
                verification_results = self.order_verifier.get_verification_results_for_symbol(symbol)

                # Check if any result shows EXECUTED status (completed sell order)
                for result in verification_results:
                    if result.get('status') == 'EXECUTED':
                        # Extract price from broker_order if available
                        broker_order = result.get('broker_order')
                        order_price = 0.0
                        if broker_order:
                            order_price = OrderFieldExtractor.get_price(broker_order) or 0.0

                        order_id = result.get('order_id', '')
                        logger.info(
                            f"Found completed sell order for {symbol} from OrderStatusVerifier: "
                            f"Order ID {order_id}, Price: Rs {order_price:.2f}"
                        )
                        return {"order_id": order_id, "price": order_price}
            except Exception as e:
                logger.debug(f"Error checking OrderStatusVerifier results for {symbol}: {e}")
                # Fall through to direct API call

        # Fallback: Use direct API call if OrderStatusVerifier not available or no results found
        try:
            # Use get_orders() directly to get ALL orders (including completed ones)
            all_orders = self.orders.get_orders()
            if not all_orders or "data" not in all_orders:
                return None

            # Extract base symbol for comparison using utility function
            base_symbol = extract_base_symbol(symbol)

            # Check for completed SELL orders matching the symbol
            for order in all_orders.get("data", []):
                # Check transaction type - only SELL orders
                if not OrderFieldExtractor.is_sell_order(order):
                    continue

                # Extract order symbol using utility function
                order_symbol = OrderFieldExtractor.get_symbol(order)
                order_base_symbol = extract_base_symbol(order_symbol)

                # Check if symbol matches
                if order_base_symbol != base_symbol:
                    continue

                # Check order status - look for completed/executed/filled
                if OrderStatusParser.is_completed(order):
                    order_id = OrderFieldExtractor.get_order_id(order)
                    order_price = OrderFieldExtractor.get_price(order)

                    logger.info(
                        f"Found completed sell order for {base_symbol}: Order ID {order_id}, Price: Rs {order_price:.2f}"
                    )

                    return {"order_id": order_id, "price": order_price}

            return None

        except Exception as e:
            logger.debug(f"Error checking for completed sell order for {symbol}: {e}")
            return None

    def get_existing_sell_orders(self) -> dict[str, dict[str, Any]]:
        """
        Get existing pending sell orders from broker to avoid duplicates

        Returns:
            Dict mapping symbol -> order info {order_id, qty, price}
        """
        try:
            existing_orders = {}

            # Get pending orders from broker
            pending = self.orders.get_pending_orders()
            if not pending:
                return existing_orders

            # Filter for SELL orders only
            for order in pending:
                try:
                    if not OrderFieldExtractor.is_sell_order(order):
                        continue

                    # Extract symbol (remove -EQ suffix)
                    symbol = extract_base_symbol(OrderFieldExtractor.get_symbol(order))

                    # Extract order details
                    qty = OrderFieldExtractor.get_quantity(order)
                    price = OrderFieldExtractor.get_price(order)
                    order_id = OrderFieldExtractor.get_order_id(order)

                    if symbol and qty > 0:
                        existing_orders[symbol.upper()] = {
                            "order_id": order_id,
                            "qty": qty,
                            "price": price,
                        }
                        logger.debug(f"Found existing sell order: {symbol} x{qty} @ Rs {price:.2f}")

                except Exception as e:
                    logger.debug(f"Error parsing order: {e}")
                    continue

            if existing_orders:
                logger.info(f"Found {len(existing_orders)} existing sell orders in broker")

            return existing_orders

        except Exception as e:
            logger.warning(f"Could not fetch existing orders: {e}. Will proceed with placement.")
            return {}

    def run_at_market_open(self) -> int:
        """
        Place sell orders for all open positions at market open
        Checks for existing orders to avoid duplicates

        Returns:
            Number of orders placed
        """
        logger.info("? Running sell order placement at market open...")

        open_positions = self.get_open_positions()
        if not open_positions:
            logger.info("No open positions to place sell orders")
            return 0

        # Check for existing sell orders to avoid duplicates
        existing_orders = self.get_existing_sell_orders()

        orders_placed = 0

        for trade in open_positions:
            symbol = trade.get("symbol")
            ticker = trade.get("ticker")
            qty = trade.get("qty", 0)

            if not symbol or not ticker:
                logger.warning(f"Skipping trade with missing symbol/ticker: {trade}")
                continue

            # Check if position already has a completed sell order (already sold)
            completed_order_info = self.has_completed_sell_order(symbol)
            if completed_order_info:
                logger.info(
                    f"Skipping {symbol}: Already has completed sell order - position already sold"
                )
                # Update trade history to mark position as closed
                order_id = completed_order_info.get("order_id", "")
                order_price = completed_order_info.get("price", 0)
                if self.state_manager:
                    if self._mark_order_executed(symbol, order_id, order_price):
                        logger.info(
                            f"Updated trade history: {symbol} marked as closed (Order ID: {order_id}, Price: Rs {order_price:.2f})"
                        )
                elif self.mark_position_closed(symbol, order_price, order_id):
                    logger.info(
                        f"Updated trade history: {symbol} marked as closed (Order ID: {order_id}, Price: Rs {order_price:.2f})"
                    )
                continue

            # Check for existing order with same symbol and quantity (avoid duplicate)
            if symbol.upper() in existing_orders:
                existing = existing_orders[symbol.upper()]
                if existing["qty"] == qty:
                    logger.info(
                        f"Skipping {symbol}: Existing sell order found (Order ID: {existing['order_id']}, Qty: {qty}, Price: Rs {existing['price']:.2f})"
                    )
                    # Track the existing order for monitoring
                    # IMPORTANT: Must include ticker for monitoring to work
                    self._register_order(
                        symbol=symbol,
                        order_id=existing["order_id"],
                        target_price=existing["price"],
                        qty=qty,
                        ticker=ticker,  # From trade history (e.g., GLENMARK.NS)
                        placed_symbol=trade.get("placed_symbol") or f"{symbol}-EQ",
                    )
                    self.lowest_ema9[symbol] = existing["price"]
                    orders_placed += 1  # Count as placed (existing)
                    logger.debug(
                        f"Tracked {symbol}: ticker={ticker}, order_id={existing['order_id']}"
                    )
                    continue

            # Get current EMA9 as target (real-time with LTP)
            broker_sym = trade.get("placed_symbol") or f"{symbol}-EQ"
            ema9 = self.get_current_ema9(ticker, broker_symbol=broker_sym)
            if not ema9:
                logger.warning(f"Skipping {symbol}: Failed to calculate EMA9")
                continue

            # Check if price is reasonable (not too far from entry)
            entry_price = trade.get("entry_price", 0)
            if entry_price and ema9 < entry_price * 0.95:  # More than 5% below entry
                logger.warning(
                    f"Skipping {symbol}: EMA9 (Rs {ema9:.2f}) is too low (entry: Rs {entry_price:.2f})"
                )
                continue

            # Place sell order
            order_id = self.place_sell_order(trade, ema9)

            if order_id:
                # Track the order
                self._register_order(
                    symbol=symbol,
                    order_id=order_id,
                    target_price=ema9,
                    qty=qty,
                    ticker=ticker,
                    placed_symbol=trade.get("placed_symbol") or f"{symbol}-EQ",
                )
                self.lowest_ema9[symbol] = ema9
                orders_placed += 1

        # Clean up any rejected orders from tracking
        self._cleanup_rejected_orders()

        logger.info(f"Placed {orders_placed} sell orders at market open")
        return orders_placed

    def _check_and_update_single_stock(
        self, symbol: str, order_info: dict[str, Any], executed_ids: list[str]
    ) -> dict[str, Any]:
        """
        Check and update a single stock (used for parallel processing)

        Args:
            symbol: Stock symbol
            order_info: Order information dict
            executed_ids: List of executed order IDs

        Returns:
            Dict with result info
        """
        result = {"symbol": symbol, "action": None, "ema9": None, "success": False}

        try:
            order_id = order_info.get("order_id")

            # Check if this order was executed
            if order_id in executed_ids:
                current_price = order_info.get("target_price", 0)
                # Use OrderStateManager if available, otherwise legacy method
                if self.state_manager:
                    self._mark_order_executed(symbol, order_id, current_price)
                else:
                    self.mark_position_closed(symbol, current_price, order_id)
                result["action"] = "executed"
                result["success"] = True
                return result

            # Get current EMA9
            ticker = order_info.get("ticker")
            if not ticker:
                logger.warning(f"No ticker found for {symbol}")
                return result

            broker_sym = order_info.get("placed_symbol")
            current_ema9 = self.get_current_ema9(ticker, broker_symbol=broker_sym)
            if not current_ema9:
                logger.warning(f"Failed to calculate EMA9 for {symbol}")
                return result

            result["ema9"] = current_ema9

            # Round EMA9 to tick size BEFORE comparing (avoid unnecessary updates)
            rounded_ema9 = self.round_to_tick_size(current_ema9)

            # Check if ROUNDED EMA9 is lower than lowest seen
            # Initialize lowest_ema9 from target_price if not set
            if symbol not in self.lowest_ema9:
                target_price = order_info.get("target_price", 0)
                if target_price > 0:
                    self.lowest_ema9[symbol] = target_price
                else:
                    # If target_price is 0 or missing, use current EMA9 as initial value
                    self.lowest_ema9[symbol] = rounded_ema9

            lowest_so_far = self.lowest_ema9.get(symbol, float("inf"))
            current_target = order_info.get("target_price", 0)

            # If target_price is 0 or missing, use lowest_so_far as target
            if current_target <= 0:
                current_target = lowest_so_far if lowest_so_far != float("inf") else rounded_ema9

            # Log EMA9 values for monitoring
            logger.info(
                f"{symbol}: Current EMA9=Rs {rounded_ema9:.2f}, Target=Rs {current_target:.2f}, Lowest=Rs {lowest_so_far:.2f}"
            )

            if rounded_ema9 < lowest_so_far:
                logger.info(
                    f"{symbol}: New lower EMA9 found - Rs {rounded_ema9:.2f} (was Rs {lowest_so_far:.2f})"
                )

                # Update sell order
                success = self.update_sell_order(
                    order_id=order_id,
                    symbol=order_info.get("placed_symbol"),
                    qty=order_info.get("qty"),
                    new_price=rounded_ema9,
                )

                if success:
                    result["action"] = "updated"
                    result["success"] = True
                    return result

            result["action"] = "checked"
            result["success"] = True

        except Exception as e:
            logger.error(f"Error checking {symbol}: {e}")
            result["action"] = "error"

        return result

    def monitor_and_update(self) -> dict[str, int]:  # noqa: PLR0912, PLR0915
        """
        Monitor EMA9 and update sell orders if lower value found (parallel processing)

        Returns:
            Dict with statistics
        """
        stats = {"checked": 0, "updated": 0, "executed": 0}

        # Clean up any rejected/cancelled orders before monitoring
        self._cleanup_rejected_orders()

        if not self.active_sell_orders:
            logger.debug("No active sell orders to monitor")
            return stats

        logger.debug(f"Monitoring {len(self.active_sell_orders)} active sell orders in parallel...")

        # Check for executed orders first (single API call)
        executed_ids = self.check_order_execution()

        # Remove executed orders BEFORE monitoring (don't waste API calls on executed orders)
        symbols_executed = []
        for symbol, order_info in list(self.active_sell_orders.items()):
            order_id = order_info.get("order_id")

            # Check if sell order has been completed (via get_orders() to catch all statuses)
            completed_order_info = self.has_completed_sell_order(symbol)
            if completed_order_info:
                logger.info(f"{symbol} sell order completed - removing from monitoring")
                # Mark position as closed in trade history
                # Use order price from completed order info, fallback to target_price
                order_price = completed_order_info.get("price", 0)
                if order_price == 0:
                    order_price = order_info.get("target_price", 0)

                # Use order_id from completed order info if available, fallback to tracked order_id
                completed_order_id = completed_order_info.get("order_id", "")
                if not completed_order_id:
                    completed_order_id = order_id or "completed"

                if self.state_manager:
                    if self._mark_order_executed(symbol, completed_order_id, order_price):
                        symbols_executed.append(symbol)
                        logger.info(f"Position closed: {symbol} - removing from tracking")
                elif self.mark_position_closed(symbol, order_price, completed_order_id):
                    symbols_executed.append(symbol)
                    logger.info(f"Position closed: {symbol} - removing from tracking")
                continue

            # Also check executed_ids (from get_executed_orders())
            if order_id in executed_ids:
                # Mark position as closed in trade history
                current_price = order_info.get("target_price", 0)
                if self.state_manager:
                    if self._mark_order_executed(symbol, order_id, current_price):
                        symbols_executed.append(symbol)
                        logger.info(f"Order executed: {symbol} - removing from tracking")
                elif self.mark_position_closed(symbol, current_price, order_id):
                    symbols_executed.append(symbol)
                    logger.info(f"Order executed: {symbol} - removing from tracking")

        # Clean up executed orders
        for symbol in symbols_executed:
            # Remove from tracking (OrderStateManager handles this if available)
            self._remove_order(symbol, reason="Executed")
            if symbol in self.lowest_ema9:
                del self.lowest_ema9[symbol]

        stats["executed"] = len(symbols_executed)

        # If no orders left to monitor, return
        if not self.active_sell_orders:
            if stats["executed"] > 0:
                logger.info(f"Monitor cycle: {stats['executed']} executed, all orders completed")
            return stats

        # Process remaining active stocks in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all monitoring tasks (only for non-executed orders)
            future_to_symbol = {
                executor.submit(
                    self._check_and_update_single_stock,
                    symbol,
                    order_info,
                    [],  # Empty list - executed orders already removed
                ): symbol
                for symbol, order_info in self.active_sell_orders.items()
            }

            # Process results as they complete
            symbols_to_update_ema = {}

            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]

                try:
                    result = future.result()
                    action = result.get("action")

                    if action == "updated":
                        symbols_to_update_ema[symbol] = result.get("ema9")
                        stats["updated"] += 1
                    elif action in ["checked", "error"]:
                        stats["checked"] += 1

                except Exception as e:
                    logger.error(f"Error processing result for {symbol}: {e}")
                    stats["checked"] += 1

            # Update lowest EMA9 tracking for updated orders
            for symbol, ema9 in symbols_to_update_ema.items():
                if symbol in self.active_sell_orders:
                    self.lowest_ema9[symbol] = ema9

        logger.info(
            f"Monitor cycle: {stats['checked']} checked, {stats['updated']} updated, {stats['executed']} executed"
        )
        return stats
