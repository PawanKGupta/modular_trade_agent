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
        self.history_path = (
            history_path or config.TRADES_HISTORY_PATH
        )  # Deprecated, kept for OrderStateManager
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

        # RSI Exit: Cache for RSI10 values {symbol: rsi10_value}
        # Cached at market open (previous day's RSI10), updated with real-time if available
        self.rsi10_cache: dict[str, float] = {}

        # RSI Exit: Track orders converted to market {symbol}
        # Prevents duplicate conversion attempts
        self.converted_to_market: set[str] = set()

        # Circuit limit tracking: Symbols waiting for circuit expansion
        # Format: {symbol: {'upper_circuit': float, 'ema9_target': float, 'trade': dict, 'last_checked': datetime}}
        self.waiting_for_circuit_expansion: dict[str, dict[str, Any]] = {}

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

        Edge Case #17 fix: Validates quantity against broker holdings and uses
        min(positions_qty, broker_qty) to ensure we don't try to sell more than available.

        Returns:
            List of open trade entries in format expected by sell order placement
        """
        if not self.positions_repo or not self.user_id:
            raise ValueError(
                "PositionsRepository and user_id are required for database-only position tracking. "
                "Please provide positions_repo and user_id when initializing SellOrderManager."
            )

        # Fetch broker holdings for validation (Edge Case #17)
        broker_holdings_map = {}
        try:
            from .utils.symbol_utils import extract_base_symbol

            holdings_response = self.portfolio.get_holdings()
            if holdings_response and isinstance(holdings_response, dict):
                holdings_data = holdings_response.get("data", [])
                for holding in holdings_data:
                    symbol = (
                        holding.get("tradingSymbol")
                        or holding.get("symbol")
                        or holding.get("securitySymbol")
                        or ""
                    )
                    if not symbol:
                        continue

                    base_symbol = extract_base_symbol(symbol).upper()
                    qty = int(
                        holding.get("quantity")
                        or holding.get("qty")
                        or holding.get("netQuantity")
                        or holding.get("holdingsQuantity")
                        or 0
                    )

                    if base_symbol and qty > 0:
                        broker_holdings_map[base_symbol] = qty
        except Exception as e:
            logger.debug(f"Could not fetch broker holdings for validation: {e}")

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
                                and extract_base_symbol(order.symbol).upper() == pos.symbol.upper()
                            ):
                                # Found matching order - use its metadata
                                if order.order_metadata and isinstance(order.order_metadata, dict):
                                    ticker = order.order_metadata.get("ticker", ticker)
                                placed_symbol = order.symbol  # Full broker symbol
                                break
                    except Exception as e:
                        logger.debug(f"Failed to enrich position metadata from orders: {e}")

                # Edge Case #17: Use min(positions_qty, broker_qty) for sell order quantity
                # This ensures we don't try to sell more than actually available
                positions_qty = int(pos.quantity)
                broker_qty = broker_holdings_map.get(pos.symbol.upper(), positions_qty)

                # Use the minimum to ensure we don't sell more than available
                # If broker_qty < positions_qty, reconciliation should have updated positions table
                # But we still validate here as a safety check
                sell_qty = min(positions_qty, broker_qty)

                if sell_qty < positions_qty:
                    logger.warning(
                        f"Quantity mismatch for {pos.symbol}: "
                        f"positions table shows {positions_qty}, "
                        f"broker has {broker_qty}. Using {sell_qty} for sell order."
                    )

                # Convert Positions model to trade dict format
                open_positions.append(
                    {
                        "symbol": pos.symbol,
                        "ticker": ticker,
                        "qty": sell_qty,  # Use validated quantity
                        "entry_price": pos.avg_price,
                        "entry_time": pos.opened_at.isoformat(),
                        "status": "open",
                        "placed_symbol": placed_symbol,
                    }
                )

        logger.debug(f"Loaded {len(open_positions)} open positions from database")
        return open_positions

    def _reconcile_positions_with_broker_holdings(self) -> dict[str, int]:
        """
        Reconcile positions table with broker holdings to detect manual sells.

        Edge Case #14, #15, #17 fix: Detects when manual trades affect system holdings
        and updates positions table accordingly.

        Logic:
        - If broker_qty < positions_qty: Manual sell detected → Update positions table
        - If broker_qty = 0: Manual full sell → Mark position as closed
        - If broker_qty > positions_qty: Manual buy → IGNORE (don't update)

        Returns:
            Dict with reconciliation stats: {
                'checked': int,
                'updated': int,
                'closed': int,
                'ignored': int
            }
        """
        if not self.positions_repo or not self.user_id:
            logger.debug("PositionsRepository or user_id not available, skipping reconciliation")
            return {"checked": 0, "updated": 0, "closed": 0, "ignored": 0}

        stats = {"checked": 0, "updated": 0, "closed": 0, "ignored": 0}

        try:
            # Fetch broker holdings
            holdings_response = self.portfolio.get_holdings()
            if not holdings_response or not isinstance(holdings_response, dict):
                logger.debug("Could not fetch broker holdings for reconciliation")
                return stats

            holdings_data = holdings_response.get("data", [])
            # Note: Empty holdings_data is valid - means all positions were sold
            # We still need to check positions to detect manual full sells

            # Create broker holdings map: {symbol: quantity}
            broker_holdings_map = {}
            for holding in holdings_data:
                # Extract symbol (handle various field names)
                symbol = (
                    holding.get("tradingSymbol")
                    or holding.get("symbol")
                    or holding.get("securitySymbol")
                    or ""
                )
                if not symbol:
                    continue

                # Extract base symbol (remove -EQ suffix)
                base_symbol = extract_base_symbol(symbol).upper()

                # Extract quantity (handle various field names)
                qty = int(
                    holding.get("quantity")
                    or holding.get("qty")
                    or holding.get("netQuantity")
                    or holding.get("holdingsQuantity")
                    or 0
                )

                if base_symbol and qty > 0:
                    broker_holdings_map[base_symbol] = qty

            # Get all open positions from database
            open_positions = self.positions_repo.list(self.user_id)
            open_positions = [pos for pos in open_positions if pos.closed_at is None]

            logger.info(
                f"Reconciling {len(open_positions)} open positions with broker holdings..."
            )

            for pos in open_positions:
                stats["checked"] += 1
                symbol = pos.symbol.upper()
                positions_qty = int(pos.quantity)

                # Get broker quantity (0 if not in holdings)
                broker_qty = broker_holdings_map.get(symbol, 0)

                # Case 1: Manual full sell detected (broker_qty = 0, positions_qty > 0)
                if broker_qty == 0 and positions_qty > 0:
                    logger.warning(
                        f"Manual full sell detected for {symbol}: "
                        f"positions table shows {positions_qty} shares, "
                        f"but broker has 0 shares. Marking position as closed."
                    )
                    try:
                        from src.infrastructure.db.timezone_utils import ist_now

                        self.positions_repo.mark_closed(
                            user_id=self.user_id,
                            symbol=symbol,
                            closed_at=ist_now(),
                            exit_price=None,  # Manual sell, price unknown
                        )
                        stats["closed"] += 1
                        logger.info(f"Position {symbol} marked as closed due to manual full sell")
                    except Exception as e:
                        logger.error(f"Error marking position {symbol} as closed: {e}")

                # Case 2: Manual partial sell detected (broker_qty < positions_qty)
                elif broker_qty < positions_qty:
                    sold_qty = positions_qty - broker_qty
                    logger.warning(
                        f"Manual partial sell detected for {symbol}: "
                        f"positions table shows {positions_qty} shares, "
                        f"but broker has {broker_qty} shares. "
                        f"Updating positions table (sold {sold_qty} shares)."
                    )
                    try:
                        # Reduce quantity in positions table
                        self.positions_repo.reduce_quantity(
                            user_id=self.user_id,
                            symbol=symbol,
                            sold_quantity=float(sold_qty),
                        )
                        stats["updated"] += 1
                        logger.info(
                            f"Position {symbol} quantity updated: {positions_qty} -> {broker_qty} "
                            f"(manual sell of {sold_qty} shares detected)"
                        )
                    except Exception as e:
                        logger.error(f"Error updating position {symbol} quantity: {e}")

                # Case 3: Manual buy detected (broker_qty > positions_qty) - IGNORE
                elif broker_qty > positions_qty:
                    stats["ignored"] += 1
                    logger.debug(
                        f"Manual buy detected for {symbol}: "
                        f"broker has {broker_qty} shares, "
                        f"positions table shows {positions_qty} shares. "
                        f"Ignoring (manual holdings not tracked by system)."
                    )

                # Case 4: Perfect match (broker_qty == positions_qty) - No action needed
                else:
                    logger.debug(
                        f"Position {symbol} matches broker holdings: {positions_qty} shares"
                    )

            if stats["updated"] > 0 or stats["closed"] > 0:
                logger.info(
                    f"Reconciliation complete: {stats['checked']} checked, "
                    f"{stats['updated']} updated, {stats['closed']} closed, "
                    f"{stats['ignored']} ignored (manual buys)"
                )

        except Exception as e:
            logger.error(f"Error during positions reconciliation: {e}", exc_info=True)

        return stats

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
                    if result and result.get("status") == "EXECUTED":
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

    def _cancel_pending_reentry_orders(self, base_symbol: str) -> int:
        """
        Cancel pending reentry orders for a closed position.

        Edge Case #12 fix: When a sell order executes and closes a position,
        cancel any pending reentry orders to prevent position from being reopened.

        Args:
            base_symbol: Base symbol (e.g., "RELIANCE") for which to cancel reentry orders

        Returns:
            Number of reentry orders cancelled
        """
        if not self.orders_repo or not self.user_id:
            logger.debug(
                "OrdersRepository or user_id not available, skipping reentry order cancellation"
            )
            return 0

        cancelled_count = 0

        try:
            from src.infrastructure.db.models import OrderStatus as DbOrderStatus

            # Query for pending reentry orders for this symbol
            all_orders = self.orders_repo.list(self.user_id)
            reentry_orders = [
                db_order
                for db_order in all_orders
                if db_order.side.lower() == "buy"
                and db_order.status == DbOrderStatus.PENDING
                and db_order.entry_type == "reentry"
                and extract_base_symbol(db_order.symbol).upper() == base_symbol.upper()
            ]

            if not reentry_orders:
                logger.debug(f"No pending reentry orders found for {base_symbol}")
                return 0

            logger.info(
                f"Found {len(reentry_orders)} pending reentry order(s) for closed position {base_symbol}. "
                f"Cancelling them..."
            )

            for db_order in reentry_orders:
                try:
                    if not db_order.broker_order_id:
                        logger.warning(
                            f"Reentry order {db_order.id} for {base_symbol} has no broker_order_id. "
                            f"Updating DB status only."
                        )
                        # Update DB status even without broker_order_id
                        self.orders_repo.update(
                            db_order,
                            status=DbOrderStatus.CANCELLED,
                            reason="Position closed",
                        )
                        cancelled_count += 1
                        continue

                    # Cancel via broker API
                    cancel_result = self.orders.cancel_order(db_order.broker_order_id)
                    if cancel_result:
                        logger.info(
                            f"Cancelled reentry order {db_order.broker_order_id} "
                            f"for closed position {base_symbol}"
                        )
                        # Update DB order status
                        self.orders_repo.update(
                            db_order,
                            status=DbOrderStatus.CANCELLED,
                            reason="Position closed",
                        )
                        cancelled_count += 1
                    else:
                        logger.warning(
                            f"Failed to cancel reentry order {db_order.broker_order_id} "
                            f"for {base_symbol} via broker API. Order may have already executed."
                        )
                        # Still update DB status to reflect intent
                        self.orders_repo.update(
                            db_order,
                            status=DbOrderStatus.CANCELLED,
                            reason="Position closed (cancellation attempted)",
                        )
                        cancelled_count += 1

                except Exception as e:
                    logger.warning(
                        f"Error cancelling reentry order {db_order.broker_order_id} "
                        f"for {base_symbol}: {e}"
                    )
                    # Continue with next order even if one fails

            if cancelled_count > 0:
                logger.info(
                    f"Cancelled {cancelled_count} pending reentry order(s) for closed position {base_symbol}"
                )

        except Exception as e:
            logger.error(
                f"Error cancelling pending reentry orders for {base_symbol}: {e}",
                exc_info=True,
            )

        return cancelled_count

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

    def _parse_circuit_limits_from_rejection(
        self, rejection_reason: str
    ) -> dict[str, float] | None:
        """
        Parse circuit limits from rejection message.

        Example message: "RMS:Rule: Check circuit limit including square off order exceeds :
        Circuit breach, Order Price :34.65, Low Price Range:30.32 High Price Range:33.51"

        Returns:
            Dict with 'upper' and 'lower' circuit limits, or None if not found
        """
        if not rejection_reason:
            return None

        import re

        # Try to extract High Price Range and Low Price Range
        # Pattern: "High Price Range:33.51" or "High Price Range: 33.51"
        high_match = re.search(r"High Price Range[:\s]+([\d.]+)", rejection_reason, re.IGNORECASE)
        low_match = re.search(r"Low Price Range[:\s]+([\d.]+)", rejection_reason, re.IGNORECASE)

        if high_match and low_match:
            try:
                upper = float(high_match.group(1))
                lower = float(low_match.group(1))
                return {"upper": upper, "lower": lower}
            except (ValueError, AttributeError):
                pass

        return None

    def _remove_rejected_orders(self):
        """
        Remove rejected/cancelled orders from active tracking.
        Also checks for circuit limit rejections and stores them for retry.
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

                    # Check if rejection is due to circuit limit breach
                    from .utils.order_field_extractor import OrderFieldExtractor

                    rejection_reason = OrderFieldExtractor.get_rejection_reason(broker_order) or ""

                    if (
                        "circuit" in rejection_reason.lower()
                        or "circuit limit" in rejection_reason.lower()
                    ):
                        # Parse circuit limits
                        circuit_limits = self._parse_circuit_limits_from_rejection(rejection_reason)
                        ema9_target = order_info.get("target_price", 0)

                        if circuit_limits and ema9_target > circuit_limits.get("upper", 0):
                            # EMA9 exceeds upper circuit - wait for expansion
                            base_symbol = symbol.upper()
                            self.waiting_for_circuit_expansion[base_symbol] = {
                                "upper_circuit": circuit_limits["upper"],
                                "lower_circuit": circuit_limits["lower"],
                                "ema9_target": ema9_target,
                                "trade": {
                                    "symbol": symbol,
                                    "placed_symbol": order_info.get("placed_symbol", symbol),
                                    "ticker": order_info.get("ticker", ""),
                                    "qty": order_info.get("qty", 0),
                                },
                                "rejection_reason": rejection_reason,
                            }
                            logger.info(
                                f"{base_symbol}: Order rejected due to circuit limit breach. "
                                f"EMA9 (Rs {ema9_target:.2f}) > Upper Circuit (Rs {circuit_limits['upper']:.2f}). "
                                f"Waiting for circuit expansion..."
                            )
                            # Remove from active tracking but keep in waiting list
                            self._remove_from_tracking(symbol)
                            continue

                    # Regular rejection (not circuit limit) - remove from tracking
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
                verification_results = self.order_verifier.get_verification_results_for_symbol(
                    symbol
                )

                # Check if any result shows EXECUTED status (completed sell order)
                for result in verification_results:
                    if result.get("status") == "EXECUTED":
                        # Extract price from broker_order if available
                        broker_order = result.get("broker_order")
                        order_price = 0.0
                        if broker_order:
                            order_price = OrderFieldExtractor.get_price(broker_order) or 0.0

                        order_id = result.get("order_id", "")
                        # Try to get filled quantity from broker_order if available
                        filled_qty = 0
                        order_qty = 0
                        if broker_order:
                            filled_qty = OrderFieldExtractor.get_filled_quantity(broker_order)
                            order_qty = OrderFieldExtractor.get_quantity(broker_order)
                        logger.info(
                            f"Found completed sell order for {symbol} from OrderStatusVerifier: "
                            f"Order ID {order_id}, Price: Rs {order_price:.2f}, "
                            f"Filled: {filled_qty}/{order_qty}"
                        )
                        return {
                            "order_id": order_id,
                            "price": order_price,
                            "filled_qty": filled_qty,
                            "order_qty": order_qty,
                        }
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
                    filled_qty = OrderFieldExtractor.get_filled_quantity(order)
                    order_qty = OrderFieldExtractor.get_quantity(order)

                    logger.info(
                        f"Found completed sell order for {base_symbol}: Order ID {order_id}, "
                        f"Price: Rs {order_price:.2f}, Filled: {filled_qty}/{order_qty}"
                    )

                    return {
                        "order_id": order_id,
                        "price": order_price,
                        "filled_qty": filled_qty,
                        "order_qty": order_qty,
                    }

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

        Edge Case #14, #15, #17 fix: Reconciles positions with broker holdings
        before placing orders to detect manual sells.

        Returns:
            Number of orders placed
        """
        logger.info("? Running sell order placement at market open...")

        # Edge Case #14, #15, #17: Reconcile positions with broker holdings
        # Detect and handle manual sells before placing orders
        reconciliation_stats = self._reconcile_positions_with_broker_holdings()
        if reconciliation_stats["updated"] > 0 or reconciliation_stats["closed"] > 0:
            logger.info(
                f"Reconciliation detected {reconciliation_stats['updated']} manual partial sells "
                f"and {reconciliation_stats['closed']} manual full sells. "
                f"Positions table updated accordingly."
            )

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

            # Check for existing order with same symbol (avoid duplicate or update if quantity changed)
            if symbol.upper() in existing_orders:
                existing = existing_orders[symbol.upper()]
                existing_qty = existing["qty"]
                existing_price = existing["price"]

                if existing_qty == qty:
                    # Same quantity - just track the existing order
                    logger.info(
                        f"Skipping {symbol}: Existing sell order found (Order ID: {existing['order_id']}, Qty: {qty}, Price: Rs {existing_price:.2f})"
                    )
                    # Track the existing order for monitoring
                    # IMPORTANT: Must include ticker for monitoring to work
                    self._register_order(
                        symbol=symbol,
                        order_id=existing["order_id"],
                        target_price=existing_price,
                        qty=qty,
                        ticker=ticker,  # From trade history (e.g., GLENMARK.NS)
                        placed_symbol=trade.get("placed_symbol") or f"{symbol}-EQ",
                    )
                    self.lowest_ema9[symbol] = existing_price
                    orders_placed += 1  # Count as placed (existing)
                    logger.debug(
                        f"Tracked {symbol}: ticker={ticker}, order_id={existing['order_id']}"
                    )
                    continue
                elif qty > existing_qty:
                    # Quantity increased (reentry happened) - update existing order
                    logger.info(
                        f"Updating sell order for {symbol}: quantity increased from {existing_qty} to {qty} "
                        f"(reentry detected, Order ID: {existing['order_id']})"
                    )

                    # Update the sell order with new quantity (keep same price)
                    if self.update_sell_order(
                        order_id=existing["order_id"],
                        symbol=symbol,
                        qty=qty,
                        new_price=existing_price,  # Keep same price
                    ):
                        logger.info(
                            f"Successfully updated sell order for {symbol}: {existing_qty} -> {qty} shares "
                            f"@ Rs {existing_price:.2f}"
                        )
                        # Update tracking with new quantity
                        self._register_order(
                            symbol=symbol,
                            order_id=existing["order_id"],
                            target_price=existing_price,
                            qty=qty,  # Updated quantity
                            ticker=ticker,
                            placed_symbol=trade.get("placed_symbol") or f"{symbol}-EQ",
                        )
                        self.lowest_ema9[symbol] = existing_price
                        orders_placed += 1  # Count as updated
                    else:
                        logger.warning(
                            f"Failed to update sell order for {symbol}. "
                            f"Order may need manual update or will be replaced next day."
                        )
                    continue
                else:
                    # Quantity decreased (partial sell or manual adjustment)
                    logger.warning(
                        f"Sell order quantity decreased for {symbol}: {existing_qty} -> {qty}. "
                        f"This might indicate a partial sell execution. Skipping update for safety."
                    )
                    # Still track the existing order with its current quantity
                    self._register_order(
                        symbol=symbol,
                        order_id=existing["order_id"],
                        target_price=existing_price,
                        qty=existing_qty,  # Keep existing quantity
                        ticker=ticker,
                        placed_symbol=trade.get("placed_symbol") or f"{symbol}-EQ",
                    )
                    self.lowest_ema9[symbol] = existing_price
                    orders_placed += 1
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

        # Initialize RSI10 cache for all open positions (previous day's RSI10)
        self._initialize_rsi10_cache(open_positions)

        logger.info(f"Placed {orders_placed} sell orders at market open")
        return orders_placed

    def _initialize_rsi10_cache(self, open_positions: list[dict[str, Any]]) -> None:
        """
        Initialize RSI10 cache with previous day's RSI10 for all open positions.
        Called at market open (9:15 AM).

        Args:
            open_positions: List of open position dictionaries
        """
        if not open_positions:
            return

        logger.info(f"Initializing RSI10 cache for {len(open_positions)} positions...")

        for position in open_positions:
            symbol = position.get("symbol")
            ticker = position.get("ticker")

            if not symbol or not ticker:
                continue

            try:
                # Get previous day's RSI10
                previous_rsi = self._get_previous_day_rsi10(ticker)
                if previous_rsi is not None:
                    self.rsi10_cache[symbol] = previous_rsi
                    logger.debug(f"Cached previous day RSI10 for {symbol}: {previous_rsi:.2f}")
                else:
                    logger.warning(
                        f"Could not get previous day RSI10 for {symbol}, will use real-time when available"
                    )
            except Exception as e:
                logger.warning(f"Error caching RSI10 for {symbol}: {e}")

        logger.info(f"RSI10 cache initialized for {len(self.rsi10_cache)} positions")

    def _get_previous_day_rsi10(self, ticker: str) -> float | None:
        """
        Get previous day's RSI10 value.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Previous day's RSI10 value, or None if unavailable
        """
        try:
            # Get price data (exclude current day to get previous day's data)
            df = self.price_service.get_price(
                ticker, days=200, interval="1d", add_current_day=False
            )

            if df is None or df.empty or len(df) < 2:
                return None

            # Calculate indicators
            df = self.indicator_service.calculate_all_indicators(df)

            if df is None or df.empty or len(df) < 2:
                return None

            # Get second-to-last row (previous day)
            previous_day = df.iloc[-2]
            previous_rsi = previous_day.get("rsi10", None)

            if previous_rsi is not None:
                # Check if NaN - use simple check since pandas may not be imported
                try:
                    import pandas as pd

                    is_na = pd.isna(previous_rsi)
                except (ImportError, AttributeError):
                    # Fallback: check if value is None or NaN-like
                    is_na = previous_rsi is None or (
                        isinstance(previous_rsi, float) and str(previous_rsi).lower() == "nan"
                    )

                if not is_na:
                    return float(previous_rsi)

            return None
        except Exception as e:
            logger.debug(f"Error getting previous day RSI10 for {ticker}: {e}")
            return None

    def _get_current_rsi10(self, symbol: str, ticker: str) -> float | None:
        """
        Get current RSI10 value with real-time calculation and fallback to cache.

        Priority:
        1. Try to calculate real-time RSI10 (update cache if available)
        2. Fallback to cached previous day's RSI10

        Args:
            symbol: Stock symbol (for cache lookup)
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Current RSI10 value, or None if unavailable
        """
        try:
            # Try to get real-time RSI10 (include current day)
            df = self.price_service.get_price(ticker, days=200, interval="1d", add_current_day=True)

            if df is not None and not df.empty:
                # Calculate indicators
                df = self.indicator_service.calculate_all_indicators(df)

                if df is not None and not df.empty:
                    # Get latest row (current day)
                    latest = df.iloc[-1]
                    current_rsi = latest.get("rsi10", None)

                    if current_rsi is not None:
                        # Check if NaN - use simple check since pandas may not be imported
                        try:
                            import pandas as pd

                            is_na = pd.isna(current_rsi)
                        except (ImportError, AttributeError):
                            # Fallback: check if value is None or NaN-like
                            is_na = current_rsi is None or (
                                isinstance(current_rsi, float) and str(current_rsi).lower() == "nan"
                            )

                        if not is_na:
                            # Update cache with real-time value
                            self.rsi10_cache[symbol] = float(current_rsi)
                            logger.debug(
                                f"Updated RSI10 cache for {symbol} with real-time value: {current_rsi:.2f}"
                            )
                            return float(current_rsi)
        except Exception as e:
            logger.debug(f"Error calculating real-time RSI10 for {symbol}: {e}")

        # Fallback to cached previous day's RSI10
        cached_rsi = self.rsi10_cache.get(symbol)
        if cached_rsi is not None:
            logger.debug(f"Using cached RSI10 for {symbol}: {cached_rsi:.2f}")
            return cached_rsi

        logger.debug(f"RSI10 unavailable for {symbol} (no cache, real-time failed)")
        return None

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

    def _check_and_retry_circuit_expansion(self) -> int:
        """
        Check if EMA9 has dropped within circuit limits for waiting symbols and retry placing orders.
        Only retries when EMA9 is within the stored upper circuit limit.

        Returns:
            Number of orders successfully retried
        """
        if not self.waiting_for_circuit_expansion:
            return 0

        retried_count = 0

        for base_symbol, wait_info in list(self.waiting_for_circuit_expansion.items()):
            try:
                trade = wait_info["trade"]
                ticker = trade.get("ticker", "")
                broker_symbol = trade.get("placed_symbol", trade.get("symbol", ""))

                if not ticker and broker_symbol:
                    # Try to extract ticker from symbol
                    ticker = (
                        broker_symbol.replace("-EQ", "")
                        .replace("-BE", "")
                        .replace("-BL", "")
                        .replace("-BZ", "")
                        + ".NS"
                    )

                if not ticker:
                    logger.debug(f"{base_symbol}: No ticker available for circuit check")
                    continue

                # Get current EMA9
                current_ema9 = self.get_current_ema9(ticker, broker_symbol=broker_symbol)
                if not current_ema9:
                    continue

                upper_circuit = wait_info["upper_circuit"]
                ema9_target = wait_info["ema9_target"]

                # Check if current EMA9 is now within the upper circuit limit
                if current_ema9 > upper_circuit:
                    # EMA9 still exceeds circuit - wait
                    logger.debug(
                        f"{base_symbol}: EMA9 (Rs {current_ema9:.2f}) still exceeds upper circuit "
                        f"(Rs {upper_circuit:.2f}). Waiting..."
                    )
                    continue

                # EMA9 is now within circuit limits - retry placing order
                # Use current EMA9 if it's lower than stored target (better price), otherwise use stored target
                target_price = min(current_ema9, ema9_target)

                logger.info(
                    f"{base_symbol}: EMA9 (Rs {current_ema9:.2f}) is now within circuit limit "
                    f"(Rs {upper_circuit:.2f}). Retrying order placement at Rs {target_price:.2f}..."
                )

                # Place order - if it succeeds, remove from waiting list
                # If it fails again with circuit limit, it will be re-added with updated limits
                order_id = self.place_sell_order(trade, target_price)

                if order_id:
                    # Order placed successfully - remove from waiting list
                    logger.info(
                        f"{base_symbol}: Order placed successfully at Rs {target_price:.2f}, "
                        f"Order ID: {order_id}"
                    )
                    del self.waiting_for_circuit_expansion[base_symbol]
                    retried_count += 1

                    # Register the order for tracking
                    qty = trade.get("qty", 0)
                    ticker = trade.get("ticker", "")
                    placed_symbol = trade.get("placed_symbol", trade.get("symbol", base_symbol))
                    self._register_order(
                        symbol=placed_symbol,
                        order_id=order_id,
                        target_price=target_price,
                        qty=qty,
                        ticker=ticker,
                        placed_symbol=placed_symbol,
                    )
                else:
                    logger.debug(
                        f"{base_symbol}: Order placement failed. Will check again on next cycle."
                    )

            except Exception as e:
                logger.error(f"Error checking circuit expansion for {base_symbol}: {e}")
                continue

        return retried_count

    def monitor_and_update(self) -> dict[str, int]:  # noqa: PLR0912, PLR0915
        """
        Monitor EMA9 and update sell orders if lower value found (parallel processing)

        Returns:
            Dict with statistics
        """
        stats = {
            "checked": 0,
            "updated": 0,
            "executed": 0,
            "converted_to_market": 0,
            "circuit_retried": 0,
        }

        # Clean up any rejected/cancelled orders before monitoring
        self._cleanup_rejected_orders()

        # Check for circuit expansion and retry waiting orders
        circuit_retried = self._check_and_retry_circuit_expansion()
        stats["circuit_retried"] = circuit_retried

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

                # Get filled quantity and order quantity to determine if partial or full execution
                filled_qty = completed_order_info.get("filled_qty", 0) or order_info.get("qty", 0)
                order_qty = completed_order_info.get("order_qty", 0) or order_info.get("qty", 0)

                # Update positions table (Edge Case #8 fix)
                if self.positions_repo and self.user_id:
                    try:
                        from src.infrastructure.db.timezone_utils import ist_now

                        base_symbol = extract_base_symbol(symbol).upper()
                        if filled_qty > 0:
                            if filled_qty >= order_qty or filled_qty >= order_info.get("qty", 0):
                                # Full execution - mark position as closed
                                self.positions_repo.mark_closed(
                                    user_id=self.user_id,
                                    symbol=base_symbol,
                                    closed_at=ist_now(),
                                    exit_price=order_price,
                                )
                                logger.info(
                                    f"Position marked as closed in database: {base_symbol} "
                                    f"(sold {filled_qty} shares @ Rs {order_price:.2f})"
                                )

                                # Edge Case #12: Cancel pending reentry orders for closed position
                                self._cancel_pending_reentry_orders(base_symbol)
                            else:
                                # Partial execution - reduce quantity, keep position open
                                self.positions_repo.reduce_quantity(
                                    user_id=self.user_id,
                                    symbol=base_symbol,
                                    sold_quantity=float(filled_qty),
                                )
                                logger.info(
                                    f"Position quantity reduced in database: {base_symbol} "
                                    f"(sold {filled_qty} shares, remaining quantity updated)"
                                )
                    except Exception as e:
                        logger.error(
                            f"Error updating positions table for {symbol} after sell execution: {e}"
                        )

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
                sold_qty = order_info.get("qty", 0)

                # Update positions table (Edge Case #8 fix)
                if self.positions_repo and self.user_id:
                    try:
                        from src.infrastructure.db.timezone_utils import ist_now

                        base_symbol = extract_base_symbol(symbol).upper()
                        # Assume full execution if we don't have filled_qty info
                        self.positions_repo.mark_closed(
                            user_id=self.user_id,
                            symbol=base_symbol,
                            closed_at=ist_now(),
                            exit_price=current_price,
                        )
                        logger.info(
                            f"Position marked as closed in database: {base_symbol} "
                            f"(sold {sold_qty} shares @ Rs {current_price:.2f})"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error updating positions table for {symbol} after sell execution: {e}"
                        )

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

        # Check RSI exit condition FIRST (priority over EMA9 check)
        stats["converted_to_market"] = 0
        symbols_to_skip_ema = []
        for symbol, order_info in list(self.active_sell_orders.items()):
            # Skip if already converted
            if symbol in self.converted_to_market:
                symbols_to_skip_ema.append(symbol)
                continue

            # Check RSI exit condition
            if self._check_rsi_exit_condition(symbol, order_info):
                stats["converted_to_market"] += 1
                symbols_to_skip_ema.append(symbol)
                continue  # Skip EMA9 check (order already converted)

        # Process remaining active stocks in parallel (EMA9 monitoring)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all monitoring tasks (only for non-executed, non-converted orders)
            future_to_symbol = {
                executor.submit(
                    self._check_and_update_single_stock,
                    symbol,
                    order_info,
                    [],  # Empty list - executed orders already removed
                ): symbol
                for symbol, order_info in self.active_sell_orders.items()
                if symbol not in symbols_to_skip_ema
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
            f"Monitor cycle: {stats['checked']} checked, {stats['updated']} updated, "
            f"{stats['executed']} executed, {stats.get('converted_to_market', 0)} converted to market"
        )
        return stats

    def _check_rsi_exit_condition(self, symbol: str, order_info: dict[str, Any]) -> bool:
        """
        Check if RSI10 > 50 and convert limit order to market order.

        Priority:
        1. Check previous day's RSI10 (cached)
        2. Then check real-time RSI10 (update cache if available)
        3. If RSI10 > 50: Convert limit order to market order

        Args:
            symbol: Stock symbol
            order_info: Order information dictionary

        Returns:
            True if order was converted to market, False otherwise
        """
        # Skip if already converted
        if symbol in self.converted_to_market:
            return False

        # Get ticker for RSI calculation
        ticker = order_info.get("ticker")
        if not ticker:
            logger.debug(f"No ticker found for {symbol}, skipping RSI exit check")
            return False

        # Get current RSI10 (previous day first, then real-time)
        rsi10 = self._get_current_rsi10(symbol, ticker)
        if rsi10 is None:
            logger.debug(f"RSI10 unavailable for {symbol}, skipping exit check")
            return False

        # Check exit condition
        if rsi10 > 50:
            logger.info(f"RSI Exit triggered for {symbol}: RSI10={rsi10:.2f} > 50")
            return self._convert_to_market_sell(symbol, order_info, rsi10)

        return False

    def _convert_to_market_sell(
        self, symbol: str, order_info: dict[str, Any], rsi10: float
    ) -> bool:
        """
        Convert existing limit sell order to market sell order.

        Primary: Try to modify existing order (change order_type from LIMIT to MARKET)
        Fallback: If modify fails, cancel existing order and place new market order

        Args:
            symbol: Stock symbol
            order_info: Order information dictionary
            rsi10: Current RSI10 value (for logging)

        Returns:
            True if conversion successful, False otherwise
        """
        order_id = order_info.get("order_id")
        qty = order_info.get("qty")
        placed_symbol = order_info.get("placed_symbol") or f"{symbol}-EQ"

        if not order_id or not qty:
            logger.error(f"Missing order_id or qty for {symbol}, cannot convert to market")
            return False

        try:
            # Primary: Try to modify existing order (LIMIT → MARKET)
            logger.info(f"Attempting to modify order {order_id} for {symbol} (LIMIT → MARKET)")
            modify_result = self.orders.modify_order(
                order_id=order_id,
                quantity=qty,
                order_type="MKT",  # Change to MARKET order
            )

            # Check if modify succeeded
            if modify_result and modify_result.get("stat", "").lower() == "ok":
                logger.info(f"Successfully modified order {order_id} for {symbol} to MARKET order")
                self.converted_to_market.add(symbol)
                self._remove_order(symbol, reason="Converted to market (RSI > 50)")
                return True

            # Modify failed, try fallback: cancel + place
            logger.warning(
                f"Modify order failed for {symbol}, falling back to cancel+place: {modify_result}"
            )

        except Exception as e:
            logger.warning(f"Error modifying order for {symbol}, falling back to cancel+place: {e}")

        # Fallback: Cancel existing order and place new market order
        try:
            # Cancel existing limit order
            logger.info(f"Cancelling limit order {order_id} for {symbol}")
            cancel_result = self.orders.cancel_order(order_id)

            if not cancel_result:
                logger.error(f"Failed to cancel limit order {order_id} for {symbol}")
                # Send notification but don't retry
                self._send_rsi_exit_error_notification(symbol, "cancel_failed", rsi10)
                return False

            # Place new market sell order
            logger.info(f"Placing market sell order for {symbol}: qty={qty}")
            market_order_resp = self.orders.place_market_sell(
                symbol=placed_symbol,
                quantity=qty,
                variety=self._get_order_variety_for_market_hours(),
                exchange=config.DEFAULT_EXCHANGE,
                product=config.DEFAULT_PRODUCT,
            )

            # Verify order placement
            if self._is_valid_order_response(market_order_resp):
                market_order_id = self._extract_order_id(market_order_resp)
                logger.info(f"Placed market sell order for {symbol}: {market_order_id}")

                # Track conversion
                self.converted_to_market.add(symbol)

                # Remove from limit order monitoring
                self._remove_order(symbol, reason="Converted to market (RSI > 50)")

                return True
            else:
                logger.error(f"Failed to place market sell order for {symbol}: {market_order_resp}")
                self._send_rsi_exit_error_notification(symbol, "place_failed", rsi10)
                return False

        except Exception as e:
            logger.error(f"Error converting {symbol} to market sell (fallback): {e}")
            self._send_rsi_exit_error_notification(symbol, "conversion_error", rsi10)
            return False

    def _is_valid_order_response(self, response: Any) -> bool:
        """
        Check if order response is valid (order was placed successfully).

        Args:
            response: Order response from broker API

        Returns:
            True if order was placed successfully
        """
        if not response:
            return False

        if isinstance(response, dict):
            # Check for error indicators
            keys_lower = {str(k).lower() for k in response.keys()}
            if any(k in keys_lower for k in ("error", "errors", "not_ok")):
                return False

            # Check for order ID indicators
            has_order_id = any(
                key in response for key in ["nOrdNo", "orderId", "order_id", "neoOrdNo", "data"]
            )
            return has_order_id

        return False

    def _extract_order_id(self, response: Any) -> str | None:
        """
        Extract order ID from broker response.

        Args:
            response: Order response from broker API

        Returns:
            Order ID string, or None if not found
        """
        if not response or not isinstance(response, dict):
            return None

        # Try various order ID fields
        order_id = (
            response.get("nOrdNo")
            or response.get("orderId")
            or response.get("order_id")
            or response.get("neoOrdNo")
            or response.get("data", {}).get("nOrdNo")
            or response.get("data", {}).get("orderId")
            or response.get("order", {}).get("neoOrdNo")
        )

        return str(order_id) if order_id else None

    def _send_rsi_exit_error_notification(self, symbol: str, error_type: str, rsi10: float) -> None:
        """
        Send Telegram notification for RSI exit conversion errors.

        Args:
            symbol: Stock symbol
            error_type: Type of error (cancel_failed, place_failed, conversion_error)
            rsi10: Current RSI10 value
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_messages = {
                "cancel_failed": "Failed to cancel limit order",
                "place_failed": "Failed to place market order",
                "conversion_error": "Error during order conversion",
            }

            message = (
                f"❌ *RSI Exit Conversion Failed*\n\n"
                f"Symbol: `{symbol}`\n"
                f"RSI10: {rsi10:.2f}\n"
                f"Error: {error_messages.get(error_type, 'Unknown error')}\n\n"
                f"Limit order remains active. Manual intervention may be required.\n\n"
                f"_Time: {timestamp}_"
            )

            # Use TelegramNotifier to respect notification preferences
            try:
                from modules.kotak_neo_auto_trader.telegram_notifier import get_telegram_notifier

                telegram_notifier = get_telegram_notifier(
                    db_session=None,  # SellOrderManager doesn't have db_session
                )
                if telegram_notifier and telegram_notifier.enabled:
                    telegram_notifier.notify_system_alert(
                        alert_type="RSI_EXIT_CONVERSION_FAILED",
                        message_text=message,
                        severity="ERROR",
                        user_id=self.user_id,
                    )
                else:
                    # Fallback to old method if telegram_notifier not available
                    from modules.kotak_neo_auto_trader.telegram_notifier import send_telegram

                    send_telegram(message)
            except Exception as notify_err:
                logger.warning(f"Failed to send RSI exit error notification: {notify_err}")
                # Fallback to old method on error
                try:
                    from modules.kotak_neo_auto_trader.telegram_notifier import send_telegram

                    send_telegram(message)
                except Exception:
                    pass  # Already logged
        except Exception as e:
            logger.warning(f"Failed to send RSI exit error notification: {e}")

    def _get_order_variety_for_market_hours(self) -> str:
        """Get order variety based on market hours."""
        from core.volume_analysis import is_market_hours

        if is_market_hours():
            return "REGULAR"
        return config.DEFAULT_VARIETY
