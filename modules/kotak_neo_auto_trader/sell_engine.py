#!/usr/bin/env python3
"""
Sell Order Management Engine for Kotak Neo Auto Trader

Manages profit-taking sell orders with EMA9 target tracking:
1. Places limit sell orders at market open (9:15 AM) with daily EMA9 as target
2. Monitors and updates orders every minute with lowest EMA9 value
3. Tracks order execution and updates trade history
"""

import re
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

# Conditional imports for optional dependencies
try:
    from core.volume_analysis import is_market_hours
except ImportError:
    is_market_hours = None

try:
    from modules.kotak_neo_auto_trader.telegram_notifier import (
        get_telegram_notifier,
        send_telegram,
    )
except ImportError:
    get_telegram_notifier = None
    send_telegram = None

try:
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus
    from src.infrastructure.db.timezone_utils import ist_now
    from src.infrastructure.db.transaction import transaction
except ImportError:
    DbOrderStatus = None
    ist_now = None
    transaction = None

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
    from .utils.symbol_utils import (
        extract_base_symbol,
        extract_ticker_base,
        get_ticker_from_full_symbol,
    )
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
        strategy_config=None,  # Optional: StrategyConfig for user-specific settings (exchange, etc.)
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
        self.strategy_config = strategy_config  # User-specific trading config (for exchange, etc.)

        # Phase 0.4: Initialize targets repository if db session available
        self.targets_repo = None
        if self.positions_repo and hasattr(self.positions_repo, "db"):
            try:
                from src.infrastructure.persistence.targets_repository import TargetsRepository

                self.targets_repo = TargetsRepository(self.positions_repo.db)
                logger.debug("TargetsRepository initialized for sell order manager")
            except Exception as e:
                logger.debug(f"TargetsRepository not available: {e}")

        # Holdings cache removed - we now fetch holdings when needed and reuse data
        # from monitoring cycles instead of maintaining a separate cache

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
            full_symbol = symbol.upper()  # Already has suffix from scrip master
            self.active_sell_orders[full_symbol] = {
                "order_id": order_id,
                "target_price": target_price,
                "qty": qty,
                "ticker": ticker,
                **kwargs,
            }
        else:
            # Legacy mode
            full_symbol = symbol.upper()  # Already has suffix from scrip master
            self.active_sell_orders[full_symbol] = {
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
        result = False
        if self.state_manager:
            result = self.state_manager.update_sell_order_price(symbol, new_price)
            if result:
                # Sync active_sell_orders for backward compatibility
                full_symbol = symbol.upper()
                if full_symbol in self.active_sell_orders:
                    self.active_sell_orders[full_symbol]["target_price"] = new_price
        else:
            # Legacy mode
            full_symbol = symbol.upper()
            if full_symbol in self.active_sell_orders:
                self.active_sell_orders[full_symbol]["target_price"] = new_price
                result = True

        # Phase 0.4: Update target record in database
        if self.targets_repo and self.user_id:
            try:
                target = self.targets_repo.get_by_symbol(self.user_id, symbol, active_only=True)
                if target:
                    self.targets_repo.update_target_price(target.id, new_price)
                    logger.debug(f"Updated target price for {symbol} to {new_price:.2f}")
            except Exception as e:
                logger.debug(f"Failed to update target price for {symbol}: {e}")

        return result

    def _remove_order(self, symbol: str, reason: str | None = None) -> bool:
        """
        Helper method to remove order using OrderStateManager if available.

        Args:
            symbol: Trading symbol
            reason: Optional reason for removal

        Returns:
            True if removed, False otherwise
        """
        full_symbol = symbol.upper()

        full_symbol = symbol.upper() if symbol else ""  # symbol is already full symbol

        if self.state_manager:
            # Always sync from OrderStateManager first to ensure consistency
            state_orders = self.state_manager.get_active_sell_orders()
            self.active_sell_orders.update(state_orders)

            # Try to remove from OrderStateManager (may or may not be there)
            result = self.state_manager.remove_from_tracking(symbol, reason=reason)

            # Always remove from self.active_sell_orders if present (for backward compatibility)
            # This ensures removal even if OrderStateManager didn't have it
            removed = False
            if full_symbol in self.active_sell_orders:
                del self.active_sell_orders[full_symbol]
                removed = True

            # Return True if either OrderStateManager had it or we removed from local dict
            return result or removed
        else:
            # Legacy mode
            if full_symbol in self.active_sell_orders:
                del self.active_sell_orders[full_symbol]
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

    def _normalize_order_strict(self, o: dict[str, Any]) -> dict[str, Any]:
        """
        Strict normalization of a Kotak order payload without price fallbacks.

        Rules:
        - Status: derive from primary fields and map to one of
          {complete, cancelled, rejected, open, unknown}
        - Execution price: ONLY `avgPrc` is used for completed orders.
          No fallback to `prc`/`price`/`executedPrice`.
        - For non-completed orders, execution price is None.
        - Executed quantity must be > 0 for a completed order.
        """
        status_raw = (o.get("ordSt") or o.get("stat") or o.get("orderStatus") or "").strip().lower()
        if "cancel" in status_raw:
            status = "cancelled"
        elif "reject" in status_raw:
            status = "rejected"
        elif status_raw == "complete" or status_raw == "executed" or status_raw == "filled":
            status = "complete"
        elif status_raw in ("open", "pending", "trigger pending"):
            status = "open"
        else:
            status = status_raw or "unknown"

        side = (o.get("trnsTp") or "").upper()  # B/S
        order_type = o.get("prcTp")  # MKT/L
        from .utils.order_field_extractor import OrderFieldExtractor

        filled_qty = int(OrderFieldExtractor.get_filled_quantity(o))
        cancelled_qty = int(o.get("cnlQty") or 0)
        remaining_qty = int(o.get("unFldSz") or 0)
        original_qty = int(OrderFieldExtractor.get_quantity(o))

        # Strict execution price: only avgPrc for completed orders
        try:
            avg_prc = float(o.get("avgPrc") or 0)
        except (ValueError, TypeError):
            avg_prc = 0.0
        execution_price = avg_prc if status == "complete" else None

        # If broker reports ongoing/open but we have fills and avg price, treat as completed
        if status != "complete" and filled_qty > 0 and avg_prc > 0:
            status = "complete"
            execution_price = avg_prc

        # Validate completed order strictly: must have fill qty
        # Do NOT demote completed status due to missing/zero avgPrc; keep execution_price=None
        if status == "complete" and filled_qty <= 0:
            status = "open" if remaining_qty > 0 else "cancelled"
            execution_price = None

        return {
            "broker_order_id": o.get("nOrdNo")
            or o.get("neoOrdNo")
            or o.get("orderId")
            or o.get("ordId")
            or o.get("id"),
            "exchange_order_id": o.get("exOrdId"),
            "status": status,
            "side": side,
            "order_type": order_type,
            "symbol": o.get("trdSym") or o.get("tradingSymbol") or o.get("sym"),
            "segment": o.get("exSeg"),
            "price": None if order_type == "MKT" else o.get("prc"),  # informational only for limit
            "execution_price": execution_price,
            "qty": original_qty,
            "filled_qty": filled_qty,
            "cancelled_qty": cancelled_qty,
            "remaining_qty": remaining_qty,
            "entered_at": o.get("ordEntTm") or o.get("orderEntryTime"),
            "executed_at": o.get("exCfmTm") if status == "complete" else None,
            "reject_reason": o.get("rejRsn") if status == "rejected" else None,
            "raw": o,
        }

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
                full_symbol = symbol.upper()
                if full_symbol in self.active_sell_orders:
                    del self.active_sell_orders[full_symbol]
            return result
        else:
            # Legacy mode - just remove from tracking
            full_symbol = symbol.upper()
            if full_symbol in self.active_sell_orders:
                del self.active_sell_orders[full_symbol]
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
            # Fetch holdings directly (no cache - fetch when needed)
            holdings_response = None
            if self.portfolio:
                try:
                    holdings_response = self.portfolio.get_holdings()
                except Exception as e:
                    logger.debug(f"Failed to fetch holdings for validation: {e}")

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

                    full_symbol = symbol.upper()  # Keep full symbol from broker
                    qty = int(
                        holding.get("quantity")
                        or holding.get("qty")
                        or holding.get("netQuantity")
                        or holding.get("holdingsQuantity")
                        or 0
                    )

                    # Issue #2 Fix: Track all holdings including zero quantity
                    # This ensures we detect when broker has 0 shares (user sold all manually)
                    if full_symbol:
                        broker_holdings_map[full_symbol] = qty
        except Exception as e:
            logger.debug(f"Could not fetch broker holdings for validation: {e}")

        open_positions = []
        positions = self.positions_repo.list(self.user_id)

        for pos in positions:
            if pos.closed_at is None:  # Open position
                # Get ticker and placed_symbol from matching ONGOING order if available
                # Extract base symbol for ticker creation (yfinance needs base symbol)
                ticker = get_ticker_from_full_symbol(pos.symbol)
                placed_symbol = pos.symbol  # Use full symbol as placed_symbol

                # Try to get ticker and placed_symbol from most recent ONGOING order
                if self.orders_repo and DbOrderStatus:
                    try:
                        ongoing_orders = self.orders_repo.list(
                            self.user_id, status=DbOrderStatus.ONGOING
                        )
                        for order in ongoing_orders:
                            if (
                                order.side.lower() == "buy"
                                and order.symbol.upper() == pos.symbol.upper()  # Exact match
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

                # Issue #2 Fix: Filter zero quantity positions before adding to list
                # Prevents positions from being added when sell_qty becomes 0 after validation
                if sell_qty <= 0:
                    logger.warning(
                        f"Skipping {pos.symbol}: sell quantity is {sell_qty} "
                        f"(positions table: {positions_qty}, broker: {broker_qty}). "
                        f"Position should be closed or reconciled."
                    )
                    continue

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

    def _check_positions_without_sell_orders(self) -> int:
        """
        Issue #5 Fix: Check how many open positions don't have active sell orders.

        Returns:
            Number of positions without sell orders
        """
        if not self.positions_repo or not self.user_id:
            return 0

        try:
            open_positions = self.get_open_positions()
            if not open_positions:
                return 0

            # Get existing sell orders (from broker API)
            existing_orders = self.get_existing_sell_orders()
            existing_symbols = set(existing_orders.keys())

            # Count positions without sell orders
            positions_without_orders = 0
            for position in open_positions:
                symbol = position.get("symbol", "").upper()
                if symbol not in existing_symbols:
                    positions_without_orders += 1

            return positions_without_orders
        except Exception as e:
            logger.debug(f"Failed to check positions without sell orders: {e}")
            return 0

    def _place_sell_orders_for_missing_positions(self) -> tuple[int, list[dict[str, Any]]]:
        """
        Issue #5 Fix: Attempt to place sell orders for positions that don't have them.

        This handles cases where sell orders failed to place at market open due to:
        - Issue #3: EMA9 calculation failure
        - Issue #2: Zero quantity after validation
        - Other transient failures

        Returns:
            Tuple of (orders_placed_count, failed_positions_list)
            failed_positions_list contains dicts with: symbol, reason, entry_price, quantity
        """
        if not self.positions_repo or not self.user_id:
            return 0, []

        failed_positions = []
        try:
            open_positions = self.get_open_positions()
            if not open_positions:
                return 0, []

            # Get existing sell orders to avoid duplicates
            existing_orders = self.get_existing_sell_orders()
            existing_symbols = set(existing_orders.keys())

            orders_placed = 0
            for position in open_positions:
                symbol = position.get("symbol", "").upper()
                if symbol in existing_symbols:
                    continue  # Already has sell order

                # Attempt to place sell order for this position
                try:
                    # Extract base symbol for ticker creation (yfinance needs base symbol)
                    ticker = position.get("ticker") or get_ticker_from_full_symbol(symbol)
                    broker_sym = position.get("placed_symbol", symbol)  # Use full symbol
                    entry_price = position.get("entry_price", 0)
                    qty = position.get("qty", 0)

                    # Issue #3 Fix: Get EMA9 with retry and fallback
                    ema9 = self._get_ema9_with_retry(
                        ticker, broker_symbol=broker_sym, symbol=symbol
                    )
                    if not ema9:
                        logger.warning(
                            f"Issue #5: Cannot place sell order for {symbol}: "
                            f"EMA9 calculation failed (Issue #3)"
                        )
                        failed_positions.append(
                            {
                                "symbol": symbol,
                                "reason": "EMA9 calculation failed (Issue #3)",
                                "entry_price": entry_price,
                                "quantity": qty,
                            }
                        )
                        continue

                    # Place sell order
                    order_id = self.place_sell_order(position, ema9)
                    if order_id:
                        # Register the order
                        self._register_order(
                            symbol=symbol,
                            order_id=order_id,
                            target_price=ema9,
                            qty=qty,
                            ticker=ticker,
                            placed_symbol=broker_sym,
                        )
                        self.lowest_ema9[symbol] = ema9
                        orders_placed += 1
                        logger.info(
                            f"Issue #5: Successfully placed sell order for {symbol}: "
                            f"Order ID: {order_id}, Target: Rs {ema9:.2f}"
                        )
                    else:
                        logger.warning(
                            f"Issue #5: Failed to place sell order for {symbol}: "
                            f"place_sell_order() returned None"
                        )
                        failed_positions.append(
                            {
                                "symbol": symbol,
                                "reason": "Order placement failed (broker API returned None)",
                                "entry_price": entry_price,
                                "quantity": qty,
                            }
                        )
                except Exception as e:
                    logger.warning(
                        f"Issue #5: Error placing sell order for {symbol}: {e}",
                        exc_info=True,
                    )
                    failed_positions.append(
                        {
                            "symbol": symbol,
                            "reason": f"Exception: {str(e)}",
                            "entry_price": position.get("entry_price", 0),
                            "quantity": position.get("qty", 0),
                        }
                    )

            return orders_placed, failed_positions
        except Exception as e:
            logger.error(f"Issue #5: Failed to place sell orders for missing positions: {e}")
            return 0, []

    def get_positions_without_sell_orders(
        self, use_broker_api: bool = False, skip_ema9_check: bool = True
    ) -> list[dict[str, Any]]:
        """
        Issue #5: Get detailed list of positions without sell orders.

        Returns list of positions with reasons why sell orders weren't placed.
        Useful for dashboard/API visibility.

        Args:
            use_broker_api: If True, validates against broker holdings and pending orders.
                          If False (default), uses database-only queries (faster, no API calls).
            skip_ema9_check: If True (default), skips expensive EMA9 calculation for faster response.
                           If False, calculates EMA9 to determine exact reason (slower).

        Returns:
            List of dicts with: symbol, entry_price, quantity, reason, ticker
        """
        if not self.positions_repo or not self.user_id:
            return []

        try:
            # Option 1: Use database-only queries (no broker API calls)
            if not use_broker_api:
                return self._get_positions_without_sell_orders_db_only(
                    skip_ema9_check=skip_ema9_check
                )

            # Option 2: Use broker API for validation (slower, but more accurate)
            open_positions = self.get_open_positions()
            if not open_positions:
                return []

            # Get existing sell orders from broker API
            existing_orders = self.get_existing_sell_orders()
            existing_symbols = set(existing_orders.keys())

            positions_without_orders = []
            for position in open_positions:
                symbol = position.get("symbol", "").upper()
                if symbol in existing_symbols:
                    continue  # Has sell order, skip

                # Determine reason why sell order wasn't placed
                reason = "Not attempted yet"
                # Extract base symbol for ticker creation (yfinance needs base symbol)
                ticker = position.get("ticker") or get_ticker_from_full_symbol(symbol)
                broker_sym = position.get("placed_symbol", symbol)  # Use full symbol

                # Check common reasons without actually placing orders
                try:
                    # Check if EMA9 can be calculated
                    ema9 = self._get_ema9_with_retry(
                        ticker, broker_symbol=broker_sym, symbol=symbol
                    )
                    if not ema9:
                        reason = "EMA9 calculation failed (Issue #3)"
                    else:
                        # EMA9 is available - order should be placeable
                        # Check if quantity is valid
                        qty = position.get("qty", 0)
                        if qty <= 0:
                            reason = "Zero or invalid quantity (Issue #2)"
                        else:
                            # All checks pass - order should be placeable
                            reason = "Order placement not attempted (may be pending retry)"
                except Exception as e:
                    reason = f"Error during analysis: {str(e)}"

                positions_without_orders.append(
                    {
                        "symbol": symbol,
                        "entry_price": position.get("entry_price", 0),
                        "quantity": position.get("qty", 0),
                        "reason": reason,
                        "ticker": ticker,
                        "broker_symbol": broker_sym,
                    }
                )

            return positions_without_orders
        except Exception as e:
            logger.error(f"Failed to get positions without sell orders: {e}")
            return []

    def _get_positions_without_sell_orders_db_only(
        self, skip_ema9_check: bool = True
    ) -> list[dict[str, Any]]:
        """
        Issue #5: Get positions without sell orders using database-only queries.

        This avoids broker API calls and is suitable for dashboard/API queries.
        Uses database orders table to check for existing sell orders.

        Args:
            skip_ema9_check: If True (default), skips expensive EMA9 calculation for faster response.
                           If False, calculates EMA9 to determine exact reason (slower, ~1-2s per position).

        Returns:
            List of dicts with: symbol, entry_price, quantity, reason, ticker
        """
        try:
            # Get open positions from database (no broker API call)
            positions = self.positions_repo.list(self.user_id)
            open_positions = [pos for pos in positions if pos.closed_at is None]

            if not open_positions:
                return []

            # Get existing sell orders from database (no broker API call)
            existing_sell_symbols = set()
            if self.orders_repo:
                try:
                    from src.infrastructure.db.models import OrderStatus as DbOrderStatus

                    # Get all pending/ongoing sell orders from database
                    all_orders = self.orders_repo.list(self.user_id)
                    for order in all_orders:
                        if order.side.lower() == "sell" and order.status in {
                            DbOrderStatus.PENDING,
                            DbOrderStatus.ONGOING,
                        }:
                            # Use full symbol (orders already have full symbols)
                            full_symbol = order.symbol.upper()
                            if full_symbol:
                                existing_sell_symbols.add(full_symbol)
                except Exception as e:
                    logger.debug(f"Failed to get sell orders from database: {e}")

            positions_without_orders = []
            for pos in open_positions:
                symbol = pos.symbol.upper()  # Full symbol (e.g., "RELIANCE-EQ")
                if symbol in existing_sell_symbols:
                    continue  # Has sell order in database, skip

                # Get ticker and broker_symbol from order metadata if available
                # Extract base symbol for ticker creation (yfinance needs base symbol)
                base_symbol = extract_base_symbol(symbol).upper()
                ticker = f"{base_symbol}.NS"
                broker_sym = symbol  # Use full symbol as broker_symbol

                if self.orders_repo:
                    try:
                        from src.infrastructure.db.models import OrderStatus as DbOrderStatus

                        # Try to get ticker from most recent buy order
                        ongoing_orders = self.orders_repo.list(
                            self.user_id, status=DbOrderStatus.ONGOING
                        )
                        for order in ongoing_orders:
                            if (
                                order.side.lower() == "buy"
                                and extract_base_symbol(order.symbol).upper() == base_symbol
                            ):
                                if order.order_metadata and isinstance(order.order_metadata, dict):
                                    ticker = order.order_metadata.get("ticker", ticker)
                                broker_sym = order.symbol
                                break
                    except Exception as e:
                        logger.debug(f"Failed to enrich position metadata: {e}")

                # Determine reason (lightweight check without broker API)
                reason = "Not attempted yet"
                qty = int(pos.quantity)

                # Skip expensive EMA9 calculation for dashboard queries (default)
                if skip_ema9_check:
                    # Quick check: quantity validation only
                    if qty <= 0:
                        reason = "Zero or invalid quantity (Issue #2)"
                    else:
                        reason = "Order placement not attempted (may be pending retry or EMA9 calculation failed)"
                else:
                    # Full analysis with EMA9 calculation (slower, ~1-2s per position)
                    try:
                        ema9 = self._get_ema9_with_retry(
                            ticker, broker_symbol=broker_sym, symbol=symbol
                        )
                        if not ema9:
                            reason = "EMA9 calculation failed (Issue #3)"
                        elif qty <= 0:
                            reason = "Zero or invalid quantity (Issue #2)"
                        else:
                            reason = "Order placement not attempted (may be pending retry)"
                    except Exception as e:
                        reason = f"Error during analysis: {str(e)}"

                positions_without_orders.append(
                    {
                        "symbol": symbol,
                        "entry_price": float(pos.avg_price),
                        "quantity": int(pos.quantity),
                        "reason": reason,
                        "ticker": ticker,
                        "broker_symbol": broker_sym,
                    }
                )

            return positions_without_orders
        except Exception as e:
            logger.error(f"Failed to get positions without sell orders (DB-only): {e}")
            return []

    def _detect_manual_sells_from_orders(
        self, all_orders_response: dict[str, Any] | None = None
    ) -> dict[str, int]:
        """
        Detect manual sells using get_orders() data (optimized approach).

        This method detects manual sells immediately by checking for executed SELL orders
        that are not in our tracked sell orders list. This is more efficient than using
        Holdings API which only updates T+1 (next day after settlement).

        Args:
            all_orders_response: Optional orders response from get_orders() API call.
                                If provided, uses this data instead of making a new API call.
                                This allows reusing data from frequent monitoring calls.

        Returns:
            Dictionary with stats: {"checked": int, "detected": int, "closed": int, "updated": int}
        """
        stats = {"checked": 0, "detected": 0, "closed": 0, "updated": 0}

        if not self.positions_repo or not self.user_id:
            return stats

        # Get orders data if not provided
        if not all_orders_response:
            if not self.orders:
                return stats
            try:
                all_orders_response = self.orders.get_orders()
            except Exception as e:
                logger.debug(f"Failed to fetch orders for manual sell detection: {e}")
                return stats

        if not all_orders_response or "data" not in all_orders_response:
            return stats

        # Get our tracked sell order IDs
        tracked_sell_order_ids = set()
        for order_info in self.active_sell_orders.values():
            order_id = order_info.get("order_id")
            if order_id:
                tracked_sell_order_ids.add(str(order_id))

        # Get all open positions
        try:
            open_positions = self.get_open_positions()
            if not open_positions:
                return stats

            # Build symbol to position mapping
            symbol_to_position = {}
            for position in open_positions:
                symbol = position.get("symbol", "").upper()
                if symbol:
                    symbol_to_position[symbol] = position

            stats["checked"] = len(symbol_to_position)

            # Check each order in broker response
            for order in all_orders_response.get("data", []):
                # Only check SELL orders
                if not OrderFieldExtractor.is_sell_order(order):
                    continue

                # Strict normalization: process only fully executed orders with avgPrc
                norm = self._normalize_order_strict(order)
                if norm.get("status") != "complete":
                    continue
                executed_qty = int(norm.get("filled_qty") or 0)
                if executed_qty <= 0:
                    continue

                order_id = norm.get("broker_order_id") or OrderFieldExtractor.get_order_id(order)
                if not order_id:
                    continue
                order_id = str(order_id).strip()

                # Skip if this is our tracked sell order
                if order_id in tracked_sell_order_ids:
                    continue

                # Extract symbol and quantity
                trading_symbol = OrderFieldExtractor.get_symbol(order)
                if not trading_symbol:
                    continue

                full_symbol = trading_symbol.upper()  # Already full symbol from broker
                if not full_symbol or full_symbol not in symbol_to_position:
                    logger.debug(
                        f"Skipping manual sell order {order_id} for {full_symbol}: "
                        f"Not in tracked positions (likely manual buy or never traded by system)"
                    )
                    continue  # Not one of our tracked positions

                # Edge Case Fix #2 & #3: Re-check position status before processing
                # Handles race conditions where position was closed by our system's sell order
                # or by a previous manual sell order in the same batch
                try:
                    position_obj = self.positions_repo.get_by_symbol(self.user_id, full_symbol)
                    if not position_obj or position_obj.closed_at is not None:
                        logger.debug(
                            f"Position {full_symbol} already closed, skipping manual sell order {order_id}"
                        )
                        continue
                except Exception as e:
                    logger.debug(f"Error checking position status for {full_symbol}: {e}")
                    continue

                # NEW FIX: Only apply timestamp check for positions created from SYSTEM buy orders
                # Reason: If system was down/failed and couldn't place/execute sell order, OR user manually
                # closed the position, we still want to detect and update the position table.
                # But we need to prevent false positives from old manual sell orders that happened
                # BEFORE the system bought the stock.
                is_system_position = False
                if self.orders_repo and position_obj.opened_at:
                    try:
                        # Check if there's a system buy order (orig_source != 'manual') for this symbol
                        # that was executed around the time the position was opened
                        # Get all buy orders for this symbol (no status filter)
                        buy_orders = self.orders_repo.list(self.user_id)

                        # Filter for buy orders matching this symbol
                        for buy_order in buy_orders:
                            if buy_order.side.lower() != "buy":
                                continue

                            # Compare full symbols (orders already have full symbols)
                            if buy_order.symbol.upper() != full_symbol:
                                continue

                            # Check if this is a system order (not manual)
                            # System orders have orig_source != 'manual' (could be 'signal', None, etc.)
                            if (
                                not buy_order.orig_source
                                or buy_order.orig_source.lower() != "manual"
                            ):
                                # Treat as system position based on presence of matching non-manual buy
                                is_system_position = True
                                logger.debug(
                                    f"Position {full_symbol} identified as system position via buy order {getattr(buy_order, 'id', 'N/A')}"
                                )
                                break

                    except Exception as e:
                        logger.debug(
                            f"Error checking if position {full_symbol} is from system order: {e}. "
                            f"Will skip timestamp check to avoid false negatives."
                        )
                        # If we can't determine, assume it's NOT a system position (skip timestamp check)
                        is_system_position = False

                # Skip positions created from manual buys - system does not track manual buys
                # If position is not from system order, skip manual sell detection
                if not is_system_position:
                    logger.debug(
                        f"Skipping manual sell detection for {full_symbol}: "
                        f"Position is not from system buy order (manual buy or unknown source). "
                        f"System does not track manual positions."
                    )
                    continue

                # Conservative timestamp gating: skip if sell time is earlier than position
                # open time on the same calendar day (prevents truly old sells from before system buy).
                # Note: We only skip on the same day to avoid false positives from historical data
                # that might have incorrect timestamps or be from previous trading sessions.
                try:
                    from datetime import datetime

                    from src.infrastructure.db.timezone_utils import IST

                    sell_order_time = None
                    time_str = (
                        OrderFieldExtractor.get_order_time(order)
                        if isinstance(order, dict)
                        else None
                    )
                    exec_time_obj = order.get("execution_time") if isinstance(order, dict) else None
                    filled_at_obj = order.get("filled_at") if isinstance(order, dict) else None

                    if isinstance(exec_time_obj, datetime):
                        sell_order_time = exec_time_obj
                    elif isinstance(filled_at_obj, datetime):
                        sell_order_time = filled_at_obj
                    elif isinstance(time_str, str):
                        try:
                            sell_order_time = datetime.fromisoformat(
                                time_str.replace("Z", "+00:00")
                            )
                        except Exception:
                            sell_order_time = None

                    if sell_order_time and position_obj.opened_at:
                        # Normalize to IST
                        if sell_order_time.tzinfo is None:
                            sell_order_time = sell_order_time.replace(tzinfo=IST)
                        else:
                            sell_order_time = sell_order_time.astimezone(IST)

                        opened_at = position_obj.opened_at
                        if opened_at.tzinfo is None:
                            opened_at = opened_at.replace(tzinfo=IST)
                        else:
                            opened_at = opened_at.astimezone(IST)

                        # Skip if same day and sell time < opened_at
                        # This prevents false positives from old sells on the same trading day
                        # while allowing historical data from previous days to be processed
                        if (
                            sell_order_time.date() == opened_at.date()
                            and sell_order_time < opened_at
                        ):
                            logger.debug(
                                f"Skipping manual sell order {order_id} for {full_symbol}: "
                                f"executed before position open on same day ({sell_order_time} < {opened_at})."
                            )
                            continue
                except Exception:
                    # Do not block detection on any parsing error
                    pass

                # Manual sell detected!
                # Use the refreshed position_obj from database (not the stale symbol_to_position)
                # This ensures we see the updated quantity after previous orders in the same batch
                if position_obj and hasattr(position_obj, "quantity"):
                    position_qty = int(position_obj.quantity or 0)
                else:
                    # Fallback to symbol_to_position if position_obj is not available
                    position = symbol_to_position.get(full_symbol, {})
                    position_qty = int(position.get("qty", 0) or 0)

                # Edge Case Fix #6: Validate position quantity
                if position_qty <= 0:
                    logger.warning(
                        f"Invalid position quantity for {full_symbol}: {position_qty}, skipping"
                    )
                    continue

                stats["detected"] += 1

                # Edge Case Fix #7: Validate executed_qty vs position_qty
                if executed_qty > position_qty:
                    logger.warning(
                        f"Manual sell executed quantity ({executed_qty}) exceeds position quantity "
                        f"({position_qty}) for {full_symbol}. This might indicate position was already "
                        f"partially sold or data inconsistency. Marking position as closed."
                    )

                # Strict exit price: use only avgPrc captured via normalization
                # Do NOT fallback to prc/price. If missing/invalid, proceed with exit_price=None.
                exit_price = norm.get("execution_price")
                if exit_price is not None:
                    try:
                        exit_price = float(exit_price)
                    except (ValueError, TypeError):
                        exit_price = None
                if exit_price is not None and exit_price <= 0:
                    # Treat non-positive avgPrc as unavailable
                    exit_price = None

                # Track manual sell order in active_sell_orders to prevent duplicate placement
                # This ensures system doesn't place another sell order for the same symbol
                try:
                    # Get sell order details for tracking
                    sell_order_price = exit_price
                    sell_order_qty = executed_qty
                    trading_symbol_full = trading_symbol  # Keep full symbol with suffix

                    # Register manual sell order in active_sell_orders
                    self._register_order(
                        symbol=trading_symbol_full,
                        order_id=order_id,
                        target_price=sell_order_price,
                        qty=int(sell_order_qty),
                        ticker=None,  # Will be constructed if needed
                        is_manual=True,  # Mark as manual sell order
                    )
                    logger.info(
                        f"Tracked manual sell order {order_id} for {full_symbol}: "
                        f"qty={sell_order_qty}, price=Rs {sell_order_price:.2f}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to track manual sell order {order_id} for {full_symbol}: {e}. "
                        f"Will still close position."
                    )

                # Case 1: Full sell (executed_qty >= position_qty)
                if executed_qty >= position_qty:
                    price_str = f"{exit_price:.2f}" if exit_price is not None else "unknown"
                    logger.warning(
                        f"Manual full sell detected for {full_symbol} via get_orders(): "
                        f"Order ID {order_id}, executed {executed_qty} shares @ Rs {price_str}. "
                        f"Position had {position_qty} shares. Marking position as closed."
                    )
                    try:
                        # Get execution time from normalized/extracted fields
                        execution_time = None
                        from datetime import datetime

                        from src.infrastructure.db.timezone_utils import IST

                        # Prefer normalized executed_at (exCfmTm) if available
                        if "norm" in locals() and norm.get("executed_at"):
                            try:
                                execution_time = datetime.fromisoformat(
                                    str(norm["executed_at"]).replace("Z", "+00:00")
                                )
                            except Exception:
                                execution_time = None

                        # Fallback to broker's executionTime field if present
                        if not execution_time and isinstance(order, dict):
                            exec_time_str = order.get("executionTime")
                            if exec_time_str:
                                try:
                                    execution_time = datetime.fromisoformat(
                                        str(exec_time_str).replace("Z", "+00:00")
                                    )
                                except Exception:
                                    execution_time = None

                        # Last resort: use OrderFieldExtractor known time fields
                        if not execution_time and isinstance(order, dict):
                            order_time_str = OrderFieldExtractor.get_order_time(order)
                            if order_time_str:
                                try:
                                    execution_time = datetime.fromisoformat(
                                        order_time_str.replace("Z", "+00:00")
                                    )
                                except Exception:
                                    execution_time = None

                        # Normalize to IST if parsed
                        if execution_time:
                            if execution_time.tzinfo is None:
                                execution_time = execution_time.replace(tzinfo=IST)
                            else:
                                execution_time = execution_time.astimezone(IST)

                        closed_at_time = (
                            execution_time if execution_time else (ist_now() if ist_now else None)
                        )

                        if closed_at_time:
                            # Phase 0.2: Determine exit_reason dynamically from sell order metadata
                            exit_reason = "MANUAL"  # Default: user manual sell

                            # Try to find the sell order and extract exit_reason from metadata
                            if order_id and self.orders_repo:
                                try:
                                    sell_order = self.orders_repo.get_by_broker_order_id(
                                        self.user_id, order_id
                                    )
                                    if sell_order and sell_order.order_metadata:
                                        exit_reason = sell_order.order_metadata.get(
                                            "exit_reason", "MANUAL"
                                        )
                                except Exception as e:
                                    logger.debug(
                                        f"Could not retrieve exit_reason from order {order_id}: {e}. "
                                        f"Using default 'MANUAL'"
                                    )

                            self.positions_repo.mark_closed(
                                user_id=self.user_id,
                                symbol=full_symbol,
                                closed_at=closed_at_time,
                                exit_price=exit_price,
                                exit_reason=exit_reason,
                            )
                            # Close corresponding ONGOING buy orders
                            try:
                                base_symbol = extract_base_symbol(full_symbol).upper()
                                self._close_buy_orders_for_symbol(base_symbol)
                            except Exception as close_error:
                                # Log error but don't fail - position is already closed
                                logger.warning(
                                    f"Failed to close buy orders for {full_symbol} after marking position closed: {close_error}"
                                )
                        stats["closed"] += 1
                        price_str = f"{exit_price:.2f}" if exit_price is not None else "unknown"
                        logger.info(
                            f"Position {full_symbol} marked as closed due to manual full sell "
                            f"(detected via get_orders()): exit_price=Rs {price_str}, "
                            f"closed_at={closed_at_time}"
                        )
                    except Exception as e:
                        # Edge Case Fix #8: Check if it's a database constraint violation or concurrent modification
                        error_str = str(e).lower()
                        if (
                            "closed" in error_str
                            or "does not exist" in error_str
                            or "not found" in error_str
                        ):
                            logger.debug(
                                f"Position {full_symbol} was already closed/updated by another process: {e}"
                            )
                        else:
                            logger.error(f"Error marking position {full_symbol} as closed: {e}")

                # Case 2: Partial sell (executed_qty < position_qty)
                else:
                    logger.warning(
                        f"Manual partial sell detected for {full_symbol} via get_orders(): "
                        f"Order ID {order_id}, executed {executed_qty} shares. "
                        f"Position had {position_qty} shares. Updating position quantity."
                    )
                    try:
                        self.positions_repo.reduce_quantity(
                            user_id=self.user_id,
                            symbol=full_symbol,
                            sold_quantity=float(executed_qty),
                        )
                        stats["updated"] += 1
                        logger.info(
                            f"Position {full_symbol} quantity updated: {position_qty} -> "
                            f"{position_qty - executed_qty} (manual sell of {executed_qty} shares "
                            f"detected via get_orders())"
                        )
                    except Exception as e:
                        # Edge Case Fix #8: Check if it's a database constraint violation or concurrent modification
                        error_str = str(e).lower()
                        if (
                            "closed" in error_str
                            or "does not exist" in error_str
                            or "not found" in error_str
                        ):
                            logger.debug(
                                f"Position {full_symbol} was already closed/updated by another process: {e}"
                            )
                        else:
                            logger.error(f"Error updating position {full_symbol} quantity: {e}")

            if stats["detected"] > 0:
                logger.info(
                    f"Manual sell detection via get_orders(): {stats['checked']} positions checked, "
                    f"{stats['detected']} manual sells detected, "
                    f"{stats['closed']} positions closed, {stats['updated']} positions updated"
                )

        except Exception as e:
            logger.error(f"Error during manual sell detection from orders: {e}", exc_info=True)

        return stats

    def _detect_and_track_pending_manual_sell_orders(
        self,
    ) -> dict[str, int]:
        """
        Detect and track pending manual sell orders for system positions.

        This ensures that if user manually places a sell order for a system position,
        it is tracked in active_sell_orders to prevent duplicate sell order placement.

        Returns:
            Dictionary with stats: {"checked": int, "tracked": int}
        """
        stats = {"checked": 0, "tracked": 0}

        if not self.positions_repo or not self.user_id or not self.orders:
            return stats

        try:
            # Get all open system positions
            open_positions = self.get_open_positions()
            if not open_positions:
                return stats

            # Build symbol to position mapping (only system positions)
            symbol_to_position = {}
            for position in open_positions:
                symbol = position.get("symbol", "").upper()
                if symbol:
                    symbol_to_position[symbol] = position

            stats["checked"] = len(symbol_to_position)

            # Get pending orders from broker (includes manual pending sell orders)
            try:
                pending_orders = self.orders.get_pending_orders()
            except Exception as e:
                logger.debug(f"Failed to fetch pending orders for manual sell tracking: {e}")
                return stats

            if not pending_orders:
                return stats

            # Get our tracked sell order IDs
            tracked_sell_order_ids = set()
            for order_info in self.active_sell_orders.values():
                order_id = order_info.get("order_id")
                if order_id:
                    tracked_sell_order_ids.add(str(order_id))

            # Check each pending order
            for order in pending_orders:
                try:
                    # Only check SELL orders
                    if not OrderFieldExtractor.is_sell_order(order):
                        continue

                    order_id = OrderFieldExtractor.get_order_id(order)
                    if not order_id:
                        continue

                    # Normalize order ID for consistent comparison
                    order_id = str(order_id).strip()

                    # Skip if this is our tracked sell order
                    if order_id in tracked_sell_order_ids:
                        continue

                    # Extract symbol
                    trading_symbol = OrderFieldExtractor.get_symbol(order)
                    if not trading_symbol:
                        continue

                    full_symbol = trading_symbol.upper()  # Already full symbol from broker
                    if not full_symbol or full_symbol not in symbol_to_position:
                        logger.debug(
                            f"Skipping pending manual sell order {order_id} for {full_symbol}: "
                            f"Not in tracked positions (likely manual buy or never traded by system)"
                        )
                        continue  # Not one of our tracked positions

                    # Check if this is a system position (not manual buy)
                    position_obj = None
                    try:
                        position_obj = self.positions_repo.get_by_symbol(self.user_id, full_symbol)
                        if not position_obj or position_obj.closed_at is not None:
                            continue
                    except Exception as e:
                        logger.debug(f"Error checking position for {full_symbol}: {e}")
                        continue

                    # Check if position is from system buy order
                    is_system_position = False
                    if self.orders_repo and position_obj.opened_at:
                        try:
                            if DbOrderStatus:
                                buy_orders = self.orders_repo.list(
                                    self.user_id,
                                    status=DbOrderStatus.ONGOING,
                                )

                                for buy_order in buy_orders:
                                    if buy_order.side.lower() != "buy":
                                        continue

                                    # Compare full symbols (orders already have full symbols)
                                    if buy_order.symbol.upper() != full_symbol:
                                        continue

                                    # Check if this is a system order (not manual)
                                    if (
                                        buy_order.orig_source
                                        and buy_order.orig_source.lower() == "manual"
                                    ):
                                        continue

                                    # Check if order execution time matches position opened_at
                                    order_execution_time = None
                                    if (
                                        hasattr(buy_order, "execution_time")
                                        and buy_order.execution_time
                                    ):
                                        order_execution_time = buy_order.execution_time
                                    elif hasattr(buy_order, "filled_at") and buy_order.filled_at:
                                        order_execution_time = buy_order.filled_at

                                    if order_execution_time:
                                        from src.infrastructure.db.timezone_utils import IST

                                        if order_execution_time.tzinfo is None:
                                            order_execution_time = order_execution_time.replace(
                                                tzinfo=IST
                                            )
                                        else:
                                            order_execution_time = order_execution_time.astimezone(
                                                IST
                                            )

                                        position_opened_at = position_obj.opened_at
                                        if position_opened_at.tzinfo is None:
                                            position_opened_at = position_opened_at.replace(
                                                tzinfo=IST
                                            )
                                        else:
                                            position_opened_at = position_opened_at.astimezone(IST)

                                        time_diff = abs(
                                            (
                                                order_execution_time - position_opened_at
                                            ).total_seconds()
                                        )
                                        if time_diff <= 3600:  # 1 hour window
                                            is_system_position = True
                                            break
                        except Exception as e:
                            logger.debug(
                                f"Error checking if position {full_symbol} is from system order: {e}"
                            )

                    # Only track pending manual sell orders for system positions
                    if not is_system_position:
                        continue

                    # Extract order details
                    order_qty = OrderFieldExtractor.get_quantity(order)
                    order_price = OrderFieldExtractor.get_price(order) or 0.0

                    if order_qty > 0:
                        # Track pending manual sell order
                        try:
                            self._register_order(
                                symbol=trading_symbol,
                                order_id=order_id,
                                target_price=order_price,
                                qty=int(order_qty),
                                ticker=None,
                                is_manual=True,  # Mark as manual sell order
                            )
                            stats["tracked"] += 1
                            logger.info(
                                f"Tracked pending manual sell order {order_id} for {full_symbol}: "
                                f"qty={order_qty}, price=Rs {order_price:.2f}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to track pending manual sell order {order_id} for {full_symbol}: {e}"
                            )

                except Exception as e:
                    logger.debug(f"Error processing pending order for manual sell tracking: {e}")
                    continue

            if stats["tracked"] > 0:
                logger.info(
                    f"Pending manual sell order tracking: {stats['checked']} positions checked, "
                    f"{stats['tracked']} pending manual sell orders tracked"
                )

        except Exception as e:
            logger.error(f"Error during pending manual sell order tracking: {e}", exc_info=True)

        return stats

    def _reconcile_positions_with_broker_holdings(
        self, holdings_response: dict[str, Any] | None = None
    ) -> dict[str, int]:
        """
        Reconcile positions table with broker holdings to detect manual sells.

        Edge Case #14, #15, #17 fix: Detects when manual trades affect system holdings
        and updates positions table accordingly.

        NOTE: Holdings API only updates T+1 (next day after settlement), so this method
        is primarily useful at market open to catch yesterday's manual trades. For immediate
        detection during market hours, use _detect_manual_sells_from_orders() instead.

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
            # Use provided holdings response if available (from monitoring cycle), otherwise fetch
            if not holdings_response or not isinstance(holdings_response, dict):
                # Fallback: Fetch if not provided (for backward compatibility)
                if self.portfolio:
                    try:
                        holdings_response = self.portfolio.get_holdings()
                    except Exception as e:
                        logger.debug(f"Failed to fetch holdings for reconciliation: {e}")
                        return stats
                else:
                    logger.debug(
                        "Portfolio not available, cannot fetch holdings for reconciliation"
                    )
                    return stats

            if not isinstance(holdings_response, dict):
                logger.debug("Invalid holdings response for reconciliation")
                return stats

            holdings_data = holdings_response.get("data", [])
            # Note: Empty holdings_data is valid - means all positions were sold
            # We still need to check positions to detect manual full sells

            # Create broker holdings map: {symbol or base_symbol: quantity}
            broker_holdings_map = {}
            for holding in holdings_data:
                # Extract symbol (handle various field names)
                symbol = (
                    holding.get("tradingSymbol")
                    or holding.get("displaySymbol")
                    or holding.get("symbol")
                    or holding.get("securitySymbol")
                    or ""
                )
                if not symbol:
                    continue

                # Keep full symbol from broker (may be base like ASTERDM or full like EMKAY-BE)
                full_symbol = symbol.upper()

                # Extract quantity (handle various field names)
                qty = int(
                    holding.get("quantity")
                    or holding.get("qty")
                    or holding.get("netQuantity")
                    or holding.get("holdingsQuantity")
                    or 0
                )

                if not full_symbol or qty <= 0:
                    continue

                # Map full symbol
                broker_holdings_map[full_symbol] = qty

                # Also map base symbol so positions like ASTERDM-EQ or EMKAY-BE can match
                base_symbol = extract_base_symbol(full_symbol)
                if base_symbol and base_symbol != full_symbol:
                    broker_holdings_map[base_symbol] = qty

            # Get all open positions from database
            open_positions = self.positions_repo.list(self.user_id)
            open_positions = [pos for pos in open_positions if pos.closed_at is None]

            logger.info(f"Reconciling {len(open_positions)} open positions with broker holdings...")

            for pos in open_positions:
                stats["checked"] += 1
                symbol = pos.symbol.upper()
                positions_qty = int(pos.quantity)

                # Get broker quantity, trying both full symbol and base symbol
                base_symbol = extract_base_symbol(symbol)
                broker_qty = broker_holdings_map.get(symbol)
                if broker_qty is None and base_symbol:
                    broker_qty = broker_holdings_map.get(base_symbol, 0)
                else:
                    broker_qty = broker_qty or 0

                # Case 1: Manual full sell detected (broker_qty = 0, positions_qty > 0)
                if broker_qty == 0 and positions_qty > 0:
                    # BUG FIX: Check for recent executed buy orders before marking as closed
                    # This prevents incorrectly closing positions when broker holdings haven't
                    # been updated yet after order execution (race condition fix)
                    # Uses 5-minute window for executed orders, but also checks if position
                    # was created within last 2 minutes (more precise)
                    if self._has_recent_executed_buy_order(symbol, minutes=5):
                        logger.info(
                            f"Skipping reconciliation for {symbol}: "
                            f"Recent executed buy order detected (within last 10 minutes). "
                            f"Broker holdings may not be updated yet. "
                            f"Will reconcile on next cycle."
                        )
                        stats["ignored"] += 1
                        continue

                    logger.warning(
                        f"Manual full sell detected for {symbol}: "
                        f"positions table shows {positions_qty} shares, "
                        f"but broker has 0 shares. Marking position as closed."
                    )
                    try:
                        if ist_now:
                            self.positions_repo.mark_closed(
                                user_id=self.user_id,
                                symbol=symbol,
                                closed_at=ist_now(),
                                exit_price=None,  # Manual sell, price unknown
                                exit_reason="MANUAL",  # Phase 0.2: Manual sell
                            )
                            # Close corresponding ONGOING buy orders
                            try:
                                base_symbol = extract_base_symbol(symbol).upper()
                                self._close_buy_orders_for_symbol(base_symbol)
                            except Exception as close_error:
                                # Log error but don't fail - position is already closed
                                logger.warning(
                                    f"Failed to close buy orders for {symbol} after marking position closed: {close_error}"
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

    def _has_recent_executed_buy_order(self, symbol: str, minutes: int = 5) -> bool:
        """
        Check if there's a recently executed buy order for this symbol.

        This prevents reconciliation from incorrectly closing positions when:
        - Broker holdings API hasn't updated yet after order execution
        - Order executed recently but holdings fetch happened before execution

        Strategy:
        1. First check if position was created very recently (within 2 minutes) - most precise
        2. Fallback to checking executed orders within time window

        Args:
            symbol: Base symbol to check (e.g., 'ASTERDM')
            minutes: Time window in minutes to check executed orders (default: 5 minutes)
                     Note: Position creation check uses 2 minutes (broker API typically updates within 1-2 min)

        Returns:
            True if there's a recent executed buy order or recently created position, False otherwise
        """
        if not self.positions_repo or not self.user_id:
            return False

        try:
            from datetime import timedelta

            if not ist_now:
                return False

            now = ist_now()

            # Strategy 1: Check if position was created very recently (most precise)
            # Broker APIs typically update within 1-2 minutes, so 2 minutes is sufficient
            position = self.positions_repo.get_by_symbol(self.user_id, symbol)
            if position and position.opened_at:
                position_age = (now - position.opened_at).total_seconds() / 60  # minutes
                if position_age <= 2:  # Position created within last 2 minutes
                    logger.debug(
                        f"Position {symbol} was created {position_age:.1f} minutes ago. "
                        f"Skipping reconciliation (broker holdings may not be updated yet)."
                    )
                    return True

            # Strategy 2: Check for executed buy orders within time window
            # Use shorter window (5 minutes) since broker APIs usually update within 1-2 minutes
            # 5 minutes provides safety margin without being too conservative
            if not self.orders_repo:
                return False

            cutoff_time = now - timedelta(minutes=minutes)

            # Get all buy orders for this user
            orders = self.orders_repo.list(self.user_id)

            # Filter for buy orders matching this symbol
            for order in orders:
                # Check if this is a buy order for the symbol
                if order.side.lower() != "buy":
                    continue

                # Compare full symbols (orders already have full symbols, symbol is full after migration)
                if order.symbol.upper() != symbol.upper():
                    continue

                # Check if order was executed recently
                # Executed orders have status='ongoing' and execution_time or filled_at set
                if order.status == DbOrderStatus.ONGOING:
                    # Check execution_time first (more accurate)
                    if hasattr(order, "execution_time") and order.execution_time:
                        if order.execution_time >= cutoff_time:
                            logger.debug(
                                f"Found recent executed buy order for {symbol}: "
                                f"order_id={order.id}, execution_time={order.execution_time}"
                            )
                            return True

                    # Fallback to filled_at if execution_time not available
                    if hasattr(order, "filled_at") and order.filled_at:
                        if order.filled_at >= cutoff_time:
                            logger.debug(
                                f"Found recent executed buy order for {symbol}: "
                                f"order_id={order.id}, filled_at={order.filled_at}"
                            )
                            return True

            return False

        except Exception as e:
            logger.debug(f"Error checking recent executed orders for {symbol}: {e}")
            return False

    def _cancel_orphaned_sell_orders(self) -> dict[str, int]:
        """
        Cancel sell orders that have no corresponding open positions.

        Safety checks:
        - Only cancels PENDING orders (not ONGOING/executing orders)
        - Skips orders for positions closed within last 5 minutes (race condition protection)
        - Only cancels system-created orders (not manual orders)
        - Handles broker API failures gracefully

        Returns:
            Dict with stats: {'checked': int, 'cancelled': int, 'skipped': int, 'errors': int}
        """
        if not self.orders_repo or not self.positions_repo or not self.user_id:
            logger.debug(
                "Repositories or user_id not available, skipping orphaned sell order cleanup"
            )
            return {"checked": 0, "cancelled": 0, "skipped": 0, "errors": 0}

        stats = {"checked": 0, "cancelled": 0, "skipped": 0, "errors": 0}

        try:
            if not ist_now:
                return stats

            now = ist_now()

            # Get all PENDING sell orders (not ONGOING - those might be executing)
            sell_orders = self.orders_repo.list(self.user_id)
            sell_orders = [
                o
                for o in sell_orders
                if o.side.lower() == "sell"
                and o.status == DbOrderStatus.PENDING  # Only PENDING, not ONGOING
            ]

            if not sell_orders:
                logger.debug("No pending sell orders found for orphaned order cleanup")
                return stats

            # Get all positions (open and recently closed)
            all_positions = self.positions_repo.list(self.user_id)
            open_position_symbols = {
                pos.symbol.upper() for pos in all_positions if pos.closed_at is None
            }

            # Track recently closed positions (within last 5 minutes) for race condition protection
            recently_closed = {}
            for pos in all_positions:
                if pos.closed_at:
                    # Handle timezone mismatch: ensure both datetimes are timezone-aware
                    closed_at = pos.closed_at
                    if closed_at.tzinfo is None:
                        # Naive datetime: assume it's in IST (database convention)
                        from src.infrastructure.db.timezone_utils import IST
                        closed_at = closed_at.replace(tzinfo=IST)
                    elif closed_at.tzinfo != now.tzinfo:
                        # Different timezone: convert to IST
                        closed_at = closed_at.astimezone(now.tzinfo)
                    
                    closed_age = (now - closed_at).total_seconds() / 60
                    if closed_age < 5:  # Closed within last 5 minutes
                        recently_closed[pos.symbol.upper()] = closed_age

            logger.info(
                f"Checking {len(sell_orders)} pending sell orders against "
                f"{len(open_position_symbols)} open positions..."
            )

            cancelled_orders = []

            for order in sell_orders:
                stats["checked"] += 1
                order_symbol = order.symbol.upper()
                base_symbol = extract_base_symbol(order_symbol).upper()

                # Safety check 1: Skip manual orders
                if order.order_metadata and isinstance(order.order_metadata, dict):
                    source = order.order_metadata.get("source", "")
                    if "manual" in source.lower():
                        logger.debug(f"Skipping {order_symbol}: Manual sell order")
                        stats["skipped"] += 1
                        continue

                # Safety check 2: Check if position exists (open or recently closed)
                has_open_position = (
                    order_symbol in open_position_symbols or base_symbol in open_position_symbols
                )

                # Check if position was recently closed (race condition protection)
                recently_closed_age = recently_closed.get(order_symbol) or recently_closed.get(
                    base_symbol
                )

                if has_open_position:
                    # Position exists - order is valid
                    continue
                elif recently_closed_age is not None:
                    # Position was closed recently - might be race condition
                    logger.debug(
                        f"Skipping {order_symbol}: Position closed {recently_closed_age:.1f} minutes ago. "
                        f"Order may still be valid. Will check on next cycle."
                    )
                    stats["skipped"] += 1
                    continue
                else:
                    # Orphaned sell order - no corresponding position
                    logger.warning(
                        f"Found orphaned sell order: {order_symbol} "
                        f"(Order ID: {order.broker_order_id}, DB ID: {order.id}). "
                        f"No open position found. Cancelling..."
                    )

                    try:
                        # Cancel via broker API if broker_order_id exists
                        if order.broker_order_id and self.orders:
                            try:
                                cancel_result = self.orders.cancel_order(order.broker_order_id)
                                if cancel_result:
                                    logger.info(
                                        f"Cancelled orphaned sell order {order.broker_order_id} for {order_symbol}"
                                    )
                                else:
                                    logger.warning(
                                        f"Failed to cancel orphaned sell order {order.broker_order_id} "
                                        f"via broker API. Will still mark as cancelled in DB."
                                    )
                            except Exception as cancel_error:
                                logger.warning(
                                    f"Error cancelling orphaned sell order {order.broker_order_id} "
                                    f"via broker API: {cancel_error}. Will still mark as cancelled in DB."
                                )

                        # Update database order status (even if broker cancellation failed)
                        self.orders_repo.cancel(
                            order,
                            reason="Orphaned sell order: No corresponding open position found",
                        )

                        stats["cancelled"] += 1
                        cancelled_orders.append(order_symbol)

                    except Exception as e:
                        logger.error(
                            f"Error cancelling orphaned sell order {order.id} for {order_symbol}: {e}"
                        )
                        stats["errors"] += 1

            if stats["cancelled"] > 0:
                logger.info(
                    f"Orphaned sell order cleanup complete: {stats['checked']} checked, "
                    f"{stats['cancelled']} cancelled, {stats['skipped']} skipped, "
                    f"{stats['errors']} errors. Cancelled symbols: {', '.join(cancelled_orders)}"
                )

        except Exception as e:
            logger.error(f"Error during orphaned sell order cleanup: {e}", exc_info=True)

        return stats

    def _reconcile_single_symbol(
        self, symbol: str, holdings_response: dict[str, Any] | None = None
    ) -> bool:
        """
        Lightweight reconciliation for a single symbol.

        Used before critical operations (e.g., updating sell orders) to ensure
        we have the latest position quantity even if manual trade happened.

        Args:
            symbol: Base symbol to reconcile

        Returns:
            True if reconciliation was performed, False otherwise
        """
        if not self.positions_repo or not self.user_id:
            return False

        try:
            # Get position from database with lock (consistent with other critical reads)
            position = self.positions_repo.get_by_symbol_for_update(self.user_id, symbol)
            if not position or position.closed_at is not None:
                return False  # Position doesn't exist or is closed

            # Use provided holdings response if available, otherwise fetch fresh
            if not holdings_response or not isinstance(holdings_response, dict):
                # Fetch fresh for critical operations
                if self.portfolio:
                    try:
                        holdings_response = self.portfolio.get_holdings()
                    except Exception as e:
                        logger.debug(
                            f"Failed to fetch holdings for single symbol reconciliation: {e}"
                        )
                        return False
                else:
                    return False

            if not isinstance(holdings_response, dict):
                return False

            holdings_data = holdings_response.get("data", [])

            # Find broker quantity for this symbol
            broker_qty = 0
            for holding in holdings_data:
                holding_symbol = (
                    holding.get("tradingSymbol")
                    or holding.get("symbol")
                    or holding.get("securitySymbol")
                    or ""
                )
                if not holding_symbol:
                    continue

                full_symbol = holding_symbol.upper()  # Keep full symbol from broker
                if full_symbol == symbol.upper():  # ✅ Exact match
                    broker_qty = int(
                        holding.get("quantity")
                        or holding.get("qty")
                        or holding.get("netQuantity")
                        or holding.get("holdingsQuantity")
                        or 0
                    )
                    break

            positions_qty = int(position.quantity)

            # Manual full sell detected
            if broker_qty == 0 and positions_qty > 0:
                # BUG FIX: Check for recent executed buy orders before marking as closed
                # Uses 5-minute window for executed orders, but also checks if position
                # was created within last 2 minutes (more precise)
                if self._has_recent_executed_buy_order(symbol, minutes=5):
                    logger.info(
                        f"Skipping single symbol reconciliation for {symbol}: "
                        f"Recent executed buy order detected. "
                        f"Broker holdings may not be updated yet."
                    )
                    return False

                logger.warning(
                    f"Manual full sell detected for {symbol} during sell order update. "
                    f"Marking position as closed."
                )
                if ist_now:
                    self.positions_repo.mark_closed(
                        user_id=self.user_id,
                        symbol=symbol,
                        closed_at=ist_now(),
                        exit_price=None,
                    )
                    # Close corresponding ONGOING buy orders
                    try:
                        base_symbol = extract_base_symbol(symbol).upper()
                        self._close_buy_orders_for_symbol(base_symbol)
                    except Exception as close_error:
                        # Log error but don't fail - position is already closed
                        logger.warning(
                            f"Failed to close buy orders for {symbol} after marking position closed: {close_error}"
                        )
                return True

            # Manual partial sell detected
            elif broker_qty < positions_qty:
                sold_qty = positions_qty - broker_qty
                logger.warning(
                    f"Manual partial sell detected for {symbol} during sell order update: "
                    f"{sold_qty} shares sold. Updating position."
                )
                self.positions_repo.reduce_quantity(
                    user_id=self.user_id,
                    symbol=symbol,
                    sold_quantity=float(sold_qty),
                )
                return True

            return False  # No reconciliation needed

        except Exception as e:
            logger.debug(f"Error in lightweight reconciliation for {symbol}: {e}")
            return False

    def _get_holdings(self) -> dict | None:
        """
        Get holdings from broker API.

        Simplified: No cache mechanism - fetch when needed.
        Holdings data is reused from monitoring cycles where possible.

        Returns:
            Holdings dictionary or None
        """
        if not self.portfolio:
            return None

        try:
            holdings_response = self.portfolio.get_holdings()
            if holdings_response and isinstance(holdings_response, dict):
                logger.debug("Fetched holdings from broker API")
            return holdings_response
        except Exception as e:
            logger.warning(f"Failed to fetch holdings from broker API: {e}")
            return None

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

    def _get_ema9_with_retry(
        self, ticker: str, broker_symbol: str = None, symbol: str = None, max_retries: int = 2
    ) -> float | None:
        """
        Issue #3 Fix: Get EMA9 with retry mechanism and fallback to yesterday's EMA9.

        Attempts to calculate current EMA9 with retries. If all attempts fail,
        falls back to yesterday's EMA9 value.

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')
            broker_symbol: Broker symbol for LTP fetch (e.g., 'RELIANCE-EQ')
            symbol: Base symbol for logging (e.g., 'RELIANCE')
            max_retries: Maximum number of retry attempts (default: 2)

        Returns:
            EMA9 value (current or yesterday's fallback) or None if all attempts fail
        """
        import time

        # Try calculating EMA9 with retries
        for attempt in range(max_retries + 1):
            try:
                ema9 = self.get_current_ema9(ticker, broker_symbol=broker_symbol)
                if ema9 and ema9 > 0:
                    if attempt > 0:
                        logger.info(
                            f"EMA9 calculation succeeded for {symbol or ticker} "
                            f"on attempt {attempt + 1}"
                        )
                    return ema9
            except Exception as e:
                logger.debug(
                    f"EMA9 calculation attempt {attempt + 1} failed for {symbol or ticker}: {e}"
                )

            # Wait before retry (except on last attempt)
            if attempt < max_retries:
                time.sleep(0.5)  # Small delay before retry

        # All retries failed - try to get yesterday's EMA9 as fallback
        logger.warning(
            f"Issue #3: EMA9 calculation failed for {symbol or ticker} after {max_retries + 1} attempts. "
            f"Attempting fallback to yesterday's EMA9..."
        )

        try:
            # Try to get historical EMA9 (yesterday's value) as fallback
            # This uses the same logic but without current LTP
            if self.indicator_service and self.indicator_service.price_service:
                # Get historical data and calculate yesterday's EMA9
                df = self.indicator_service.price_service.get_price(
                    ticker, days=200, interval="1d", add_current_day=False
                )
                if df is not None and not df.empty and len(df) >= 9:
                    ema_series = df["close"].ewm(span=9, adjust=False).mean()
                    yesterday_ema9 = float(ema_series.iloc[-1])
                    if yesterday_ema9 and yesterday_ema9 > 0:
                        logger.info(
                            f"Issue #3: Using yesterday's EMA9 ({yesterday_ema9:.2f}) as fallback "
                            f"for {symbol or ticker}"
                        )
                        return yesterday_ema9
        except Exception as e:
            logger.debug(f"Failed to get yesterday's EMA9 fallback for {symbol or ticker}: {e}")

        # All attempts including fallback failed
        return None

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
            ticker = trade.get("ticker")
            if not symbol:
                logger.error("No symbol found in trade entry")
                return None

            # Ensure symbol has exchange suffix
            if not symbol.endswith(("-EQ", "-BE", "-BL", "-BZ")):
                symbol = f"{symbol}-EQ"

            # Try to get correct trading symbol from scrip master
            # Use user's trading config preference for exchange (from database UserTradingConfig)
            # Falls back to config.DEFAULT_EXCHANGE if strategy_config not available
            exchange = (
                self.strategy_config.default_exchange
                if self.strategy_config
                else config.DEFAULT_EXCHANGE
            )
            if self.scrip_master and self.scrip_master.symbol_map:
                correct_symbol = self.scrip_master.get_trading_symbol(symbol, exchange=exchange)
                if correct_symbol:
                    logger.debug(
                        f"Resolved {symbol} -> {correct_symbol} via scrip master ({exchange})"
                    )
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
                order_id_str = str(order_id)
                logger.info(
                    f"Sell order placed: {symbol} @ Rs {rounded_price:.2f}, Order ID: {order_id_str}"
                )

                # Phase 7: Persist sell order to database (dual-write JSON + DB)
                # This ensures unified tracking in Orders table for monitoring and reporting.
                if self.orders_repo and self.user_id:
                    try:
                        # Build metadata consistent with buy-side orders
                        base_symbol = extract_base_symbol(symbol)
                        order_metadata = {
                            "ticker": ticker,
                            "exchange": exchange,
                            "base_symbol": base_symbol,
                            "full_symbol": symbol,
                            "variety": "REGULAR",
                            "source": "sell_engine_run_at_market_open",
                            "exit_reason": "TARGET_HIT",
                        }

                        # Create DB order with side='sell'
                        self.orders_repo.create_amo(
                            user_id=self.user_id,
                            symbol=symbol,
                            side="sell",
                            order_type="limit",
                            quantity=float(qty),
                            price=float(rounded_price),
                            broker_order_id=order_id_str,
                            entry_type="exit",
                            order_metadata=order_metadata,
                            reason="Sell order placed by SellOrderManager at market open",
                        )
                        logger.debug(
                            f"Persisted sell order to DB for {symbol} "
                            f"(user_id={self.user_id}, broker_order_id={order_id_str})"
                        )
                    except Exception as e:  # pragma: no cover - defensive logging
                        logger.warning(
                            f"Failed to persist sell order {order_id_str} for {symbol} to DB: {e}"
                        )

                # Phase 0.4: Create target record in database
                if self.targets_repo and self.user_id:
                    try:
                        # Get position for linking
                        position = None
                        position_id = None
                        entry_price = trade.get("entry_price", 0.0)
                        if self.positions_repo:
                            position = self.positions_repo.get_by_symbol(self.user_id, symbol)
                            if position:
                                position_id = position.id
                                entry_price = position.avg_price

                        # Get trade_mode from user settings
                        trade_mode = None
                        if self.positions_repo and hasattr(self.positions_repo, "db"):
                            try:
                                from src.infrastructure.persistence.settings_repository import (
                                    SettingsRepository,
                                )

                                settings_repo = SettingsRepository(self.positions_repo.db)
                                user_settings = settings_repo.get_by_user_id(self.user_id)
                                if user_settings:
                                    trade_mode = user_settings.trade_mode
                            except Exception as e:
                                logger.debug(f"Could not get trade_mode: {e}")

                        # Default to BROKER if not found (sell_engine is for broker trading)
                        if not trade_mode:
                            from src.infrastructure.db.models import TradeMode

                            trade_mode = TradeMode.BROKER

                        # Calculate distance to target
                        current_price = trade.get("current_price") or trade.get("close")
                        distance_to_target = None
                        distance_to_target_absolute = None
                        if current_price and target_price:
                            distance_to_target = (
                                (target_price - current_price) / current_price
                            ) * 100
                            distance_to_target_absolute = target_price - current_price

                        # Create or update target
                        target_data = {
                            "position_id": position_id,
                            "target_price": rounded_price,  # Use rounded price
                            "entry_price": entry_price,
                            "current_price": current_price,
                            "quantity": float(qty),
                            "distance_to_target": distance_to_target,
                            "distance_to_target_absolute": distance_to_target_absolute,
                            "target_type": "ema9",
                        }

                        target = self.targets_repo.upsert_by_symbol(
                            user_id=self.user_id,
                            symbol=symbol,
                            target_data=target_data,
                            trade_mode=trade_mode,
                        )
                        logger.debug(
                            f"Created/updated target record for {symbol} "
                            f"(target_id={target.id}, target_price={rounded_price:.2f})"
                        )
                    except Exception as e:  # pragma: no cover - defensive logging
                        logger.warning(f"Failed to create target record for {symbol}: {e}")

                return order_id_str
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

    def check_order_execution(self, all_orders_response: dict[str, Any] | None = None) -> list[str]:
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

        # Fallback: Use provided orders response if available, otherwise use direct API call
        try:
            # Use provided orders response if available (from monitoring cycle)
            if all_orders_response and isinstance(all_orders_response, dict):
                orders_data = all_orders_response.get("data", [])
                # Filter for executed/completed SELL orders matching our tracked orders
                for order in orders_data:
                    # Check if it's a sell order
                    if not OrderFieldExtractor.is_sell_order(order):
                        continue

                    # Check if order is completed/executed
                    if not OrderStatusParser.is_completed(order):
                        continue

                    order_id = OrderFieldExtractor.get_order_id(order)
                    if order_id and any(
                        info.get("order_id") == str(order_id)
                        for info in self.active_sell_orders.values()
                    ):
                        executed_ids.append(str(order_id))
                        logger.info(f"Sell order executed: Order ID {order_id}")

                if executed_ids:
                    return executed_ids
            else:
                # Fallback: Use direct API call if orders response not provided
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
            if not DbOrderStatus:
                logger.warning("DbOrderStatus not available, skipping reentry order cancellation")
                return 0

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

            # Group database updates in transaction, but broker API calls happen outside
            # This ensures all DB updates succeed or fail together
            db_updates = []  # Track orders that need DB updates

            for db_order in reentry_orders:
                try:
                    if not db_order.broker_order_id:
                        logger.warning(
                            f"Reentry order {db_order.id} for {base_symbol} has no broker_order_id. "
                            f"Updating DB status only."
                        )
                        # Queue for DB update
                        db_updates.append((db_order, "Position closed"))
                        cancelled_count += 1
                        continue

                    # Cancel via broker API (outside transaction)
                    cancel_result = self.orders.cancel_order(db_order.broker_order_id)
                    if cancel_result:
                        logger.info(
                            f"Cancelled reentry order {db_order.broker_order_id} "
                            f"for closed position {base_symbol}"
                        )
                        # Queue for DB update
                        db_updates.append((db_order, "Position closed"))
                        cancelled_count += 1
                    else:
                        logger.warning(
                            f"Failed to cancel reentry order {db_order.broker_order_id} "
                            f"for {base_symbol} via broker API. Order may have already executed."
                        )
                        # Still update DB status to reflect intent
                        db_updates.append((db_order, "Position closed (cancellation attempted)"))
                        cancelled_count += 1

                except Exception as e:
                    logger.warning(
                        f"Error cancelling reentry order {db_order.broker_order_id} "
                        f"for {base_symbol}: {e}"
                    )
                    # Continue with next order even if one fails

            # Apply all DB updates in a single transaction
            if db_updates and transaction:
                with transaction(self.orders_repo.db):
                    for db_order, reason in db_updates:
                        try:
                            self.orders_repo.update(
                                db_order,
                                status=DbOrderStatus.CANCELLED,
                                reason=reason,
                                auto_commit=False,  # Transaction handles commit
                            )
                        except Exception as e:
                            logger.warning(
                                f"Error updating DB status for reentry order {db_order.id}: {e}"
                            )
                            # Transaction will rollback if exception propagates

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

    def _close_buy_orders_for_symbol(self, base_symbol: str) -> int:
        """
        Close ONGOING buy orders for a symbol when sell order executes.

        When a sell order executes and closes a position, mark all corresponding
        ONGOING buy orders as CLOSED with closed_at timestamp.

        Args:
            base_symbol: Base symbol (e.g., "RELIANCE") for which to close buy orders

        Returns:
            Number of buy orders closed
        """
        if not self.orders_repo or not self.user_id:
            logger.debug("OrdersRepository or user_id not available, skipping buy order closure")
            return 0

        closed_count = 0

        try:
            if not DbOrderStatus or not ist_now:
                logger.warning("DbOrderStatus or ist_now not available, skipping buy order closure")
                return 0

            # Query for ONGOING buy orders for this symbol
            all_orders = self.orders_repo.list(self.user_id)
            ongoing_buy_orders = [
                db_order
                for db_order in all_orders
                if db_order.side.lower() == "buy"
                and db_order.status == DbOrderStatus.ONGOING
                and extract_base_symbol(db_order.symbol).upper() == base_symbol.upper()
            ]

            if not ongoing_buy_orders:
                logger.debug(f"No ONGOING buy orders found for {base_symbol}")
                return 0

            logger.info(
                f"Found {len(ongoing_buy_orders)} ONGOING buy order(s) for {base_symbol}. "
                f"Closing them as sell order executed..."
            )

            # Wrap all order closures in a single transaction
            if transaction:
                with transaction(self.orders_repo.db):
                    for db_order in ongoing_buy_orders:
                        try:
                            # Mark buy order as CLOSED
                            self.orders_repo.update(
                                db_order,
                                status=DbOrderStatus.CLOSED,
                                closed_at=ist_now(),
                                reason="Position closed - sell order executed",
                                auto_commit=False,  # Transaction handles commit
                            )
                            closed_count += 1
                            logger.info(
                                f"Closed buy order {db_order.id} ({db_order.broker_order_id}) "
                                f"for {base_symbol} - sell order executed"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Error closing buy order {db_order.id} for {base_symbol}: {e}"
                            )
                            # Continue with next order even if one fails
                            # Transaction will rollback if exception propagates

            if closed_count > 0:
                logger.info(
                    f"Closed {closed_count} buy order(s) for {base_symbol} after sell execution"
                )

        except Exception as e:
            logger.error(
                f"Error closing buy orders for {base_symbol}: {e}",
                exc_info=True,
            )

        return closed_count

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
        For cancelled orders, checks if position still exists and re-places sell order.
        """
        all_orders = self.orders.get_orders()
        if not all_orders or "data" not in all_orders:
            return

        rejected_symbols = []
        cancelled_symbols_with_positions = []  # Track cancelled orders where position still exists

        for symbol, order_info in list(self.active_sell_orders.items()):
            order_id = order_info.get("order_id")
            if not order_id:
                continue

            # Find this order in broker orders
            broker_order = self._find_order_in_broker_orders(order_id, all_orders["data"])
            if broker_order:
                # Check if order is rejected or cancelled
                is_rejected = OrderStatusParser.is_rejected(broker_order)
                is_cancelled = OrderStatusParser.is_cancelled(broker_order)

                if is_rejected or is_cancelled:
                    status = OrderStatusParser.parse_status(broker_order)

                    # For cancelled orders, check if position still exists
                    if is_cancelled and self.positions_repo and self.user_id:
                        try:
                            full_symbol = symbol.upper()
                            position = self.positions_repo.get_by_symbol(self.user_id, full_symbol)
                            if position and position.closed_at is None:
                                # Position still open - need to re-place sell order
                                cancelled_symbols_with_positions.append((symbol, order_info))
                                logger.info(
                                    f"Order {order_id} for {symbol} was cancelled but position still exists. "
                                    f"Will re-place sell order."
                                )
                                continue
                        except Exception as e:
                            logger.debug(
                                f"Error checking position for cancelled order {symbol}: {e}"
                            )

                    # Check if rejection is due to circuit limit breach (only for rejected, not cancelled)
                    if is_rejected:
                        rejection_reason = (
                            OrderFieldExtractor.get_rejection_reason(broker_order) or ""
                        )

                        if (
                            "circuit" in rejection_reason.lower()
                            or "circuit limit" in rejection_reason.lower()
                        ):
                            # Parse circuit limits
                            circuit_limits = self._parse_circuit_limits_from_rejection(
                                rejection_reason
                            )
                            ema9_target = order_info.get("target_price", 0)

                            if circuit_limits and ema9_target > circuit_limits.get("upper", 0):
                                # EMA9 exceeds upper circuit - wait for expansion
                                full_symbol = (
                                    symbol.upper()
                                )  # symbol is already full symbol from active_sell_orders
                                self.waiting_for_circuit_expansion[full_symbol] = {
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
                                    f"{full_symbol}: Order rejected due to circuit limit breach. "
                                    f"EMA9 (Rs {ema9_target:.2f}) > Upper Circuit (Rs {circuit_limits['upper']:.2f}). "
                                    f"Waiting for circuit expansion..."
                                )
                                # Remove from active tracking but keep in waiting list
                                self._remove_from_tracking(symbol)
                                continue

                    # Regular rejection or cancellation (without open position) - remove from tracking
                    rejected_symbols.append(symbol)
                    logger.info(
                        f"Removing {symbol} from tracking: order {order_id} is {status.value}"
                    )

        # Clean up rejected/cancelled orders (without open positions)
        for symbol in rejected_symbols:
            self._remove_from_tracking(symbol)

        # Re-place sell orders for cancelled orders with open positions
        for symbol, order_info in cancelled_symbols_with_positions:
            try:
                # Remove old cancelled order from tracking first
                self._remove_from_tracking(symbol)

                # Get current EMA9 for new order
                ticker = order_info.get("ticker")
                placed_symbol = order_info.get("placed_symbol", symbol)

                if ticker:
                    ema9 = self._get_ema9_with_retry(
                        ticker, broker_symbol=placed_symbol, symbol=symbol
                    )
                    if ema9:
                        # Re-create trade dict
                        trade = {
                            "symbol": symbol,
                            "ticker": ticker,
                            "qty": order_info.get("qty", 0),
                            "placed_symbol": placed_symbol,
                        }

                        # Place new sell order
                        new_order_id = self.place_sell_order(trade, ema9)
                        if new_order_id:
                            logger.info(
                                f"Successfully re-placed sell order for {symbol} after cancellation: {new_order_id}"
                            )
                        else:
                            logger.warning(
                                f"Failed to re-place sell order for {symbol} after cancellation"
                            )
                    else:
                        logger.warning(
                            f"Failed to get EMA9 for {symbol} to re-place cancelled order"
                        )
                else:
                    logger.warning(f"No ticker available for {symbol} to re-place cancelled order")
            except Exception as e:
                logger.error(f"Error re-placing sell order for {symbol} after cancellation: {e}")

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

    def has_completed_sell_order(
        self, symbol: str, all_orders_response: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
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

        # Fallback: Use provided orders response if available, otherwise use direct API call
        try:
            # Use provided orders response if available (from monitoring cycle)
            if all_orders_response and isinstance(all_orders_response, dict):
                all_orders = all_orders_response
            else:
                # Fallback: Use direct API call if orders response not provided
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

        # Cleanup orphaned sell orders (no corresponding open positions)
        orphaned_stats = self._cancel_orphaned_sell_orders()
        if orphaned_stats["cancelled"] > 0:
            logger.info(
                f"Cleaned up {orphaned_stats['cancelled']} orphaned sell orders "
                f"({orphaned_stats['skipped']} skipped due to safety checks)"
            )

        open_positions = self.get_open_positions()
        if not open_positions:
            logger.info("No open positions to place sell orders")
            return 0

        # Check for existing sell orders to avoid duplicates
        existing_orders = self.get_existing_sell_orders()

        # Optimization: Fetch orders once and reuse for has_completed_sell_order checks
        all_orders_response = None
        try:
            all_orders_response = self.orders.get_orders()
        except Exception as e:
            logger.debug(f"Failed to fetch orders for run_at_market_open: {e}")

        orders_placed = 0

        for trade in open_positions:
            symbol = trade.get("symbol")
            ticker = trade.get("ticker")
            qty = trade.get("qty", 0)

            if not symbol or not ticker:
                logger.warning(f"Skipping trade with missing symbol/ticker: {trade}")
                continue

            # Check if position already has a completed sell order (already sold)
            # Reuse orders data to avoid duplicate API calls
            completed_order_info = self.has_completed_sell_order(symbol, all_orders_response)
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
                    # Race Condition Fix: Re-read position quantity just before updating
                    # to ensure we have the latest value (in case reentry executed during processing)
                    current_position = None
                    if self.positions_repo and self.user_id:
                        try:
                            current_position = self.positions_repo.get_by_symbol_for_update(
                                self.user_id, symbol
                            )
                            if current_position:
                                # Use the latest quantity from database
                                qty = current_position.quantity
                                logger.debug(
                                    f"Re-read position {symbol}: quantity = {qty} "
                                    f"(was {trade.get('qty', 0)} in initial read)"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Failed to re-read position {symbol} before sell order update: {e}. "
                                f"Using quantity from initial read."
                            )

                    logger.info(
                        f"Updating sell order for {symbol}: quantity increased from {existing_qty} to {qty} "
                        f"(reentry detected, Order ID: {existing['order_id']})"
                    )

                    # Manual Trade Detection Timing Fix: Lightweight reconciliation for this symbol
                    # before updating sell order to ensure we have latest quantity
                    # Note: holdings_response not available here, so it will fetch fresh if needed
                    try:
                        # Quick check: reconcile this specific symbol
                        self._reconcile_single_symbol(symbol, holdings_response=None)
                    except Exception as e:
                        logger.debug(
                            f"Lightweight reconciliation for {symbol} failed: {e}. Continuing..."
                        )

                    # Update the sell order with new quantity (keep same price)
                    if self.update_sell_order(
                        order_id=existing["order_id"],
                        symbol=symbol,
                        qty=int(qty),  # Ensure integer for order quantity
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

            # Issue #3 Fix: Get current EMA9 with retry and fallback
            broker_sym = trade.get("placed_symbol") or f"{symbol}-EQ"
            ema9 = self._get_ema9_with_retry(ticker, broker_symbol=broker_sym, symbol=symbol)
            if not ema9:
                logger.error(
                    f"Issue #3: Skipping {symbol}: Failed to calculate EMA9 after retries and fallback. "
                    f"Position exists but sell order cannot be placed."
                )
                # Issue #3: Send alert if telegram notifier available
                if hasattr(self, "telegram_notifier") and self.telegram_notifier:
                    try:
                        self.telegram_notifier.notify_system_alert(
                            alert_type="EMA9_CALCULATION_FAILED",
                            message_text=(
                                f"Failed to calculate EMA9 for {symbol}. "
                                f"Sell order not placed. Position exists but cannot determine target price."
                            ),
                            severity="WARNING",
                            user_id=self.user_id if hasattr(self, "user_id") else None,
                        )
                    except Exception as e:
                        logger.debug(f"Failed to send EMA9 failure alert: {e}")
                continue

            # Issue #4: EMA9 validation check removed - all positions will get sell orders
            # This enables RSI 50 exit mechanism to work for all positions
            # Note: Positions may be sold at loss if EMA9 is below entry price

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

            # Check if position is still open before monitoring
            # Skip stocks that are no longer in trade (position closed manually or by other process)
            if self.positions_repo and self.user_id:
                try:
                    full_symbol = (
                        symbol.upper()
                    )  # symbol is already full symbol from active_sell_orders
                    position = self.positions_repo.get_by_symbol(self.user_id, full_symbol)
                    if not position or position.closed_at is not None:
                        logger.debug(
                            f"Skipping {symbol}: Position is closed or doesn't exist "
                            f"(closed_at={position.closed_at if position else 'N/A'})"
                        )
                        result["action"] = "skipped"
                        result["success"] = True
                        # Mark for removal from active_sell_orders
                        result["remove_from_tracking"] = True
                        return result
                except Exception as e:
                    logger.debug(f"Error checking position status for {symbol}: {e}")
                    # Continue monitoring if position check fails (fail-safe)

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

    def _check_and_fix_sell_order_mismatches(
        self, all_orders_response: dict[str, Any] | None = None
    ) -> int:
        """
        Check for sell order quantity mismatches with position quantities and fix them.

        Flaw #7 Fix: Detects and fixes mismatches caused by failed sell order updates
        (e.g., after reentry execution when update_sell_order() fails).

        Args:
            all_orders_response: Optional orders response from get_orders() API call.
                                 If provided, uses this data instead of making a new API call.
                                 This allows reusing data from frequent monitoring calls.

        Returns:
            Number of mismatches fixed
        """
        if not self.active_sell_orders or not self.positions_repo or not self.user_id:
            return 0

        fixed_count = 0

        # Extract pending sell orders from the provided orders response (if available)
        # Otherwise, fall back to get_existing_sell_orders() for backward compatibility
        if all_orders_response and isinstance(all_orders_response, dict):
            existing_orders = {}
            orders_data = all_orders_response.get("data", [])

            for order in orders_data:
                try:
                    if not OrderFieldExtractor.is_sell_order(order):
                        continue

                    # Extract symbol (remove -EQ suffix)
                    symbol = extract_base_symbol(OrderFieldExtractor.get_symbol(order))

                    # Extract order details
                    qty = OrderFieldExtractor.get_quantity(order)
                    price = OrderFieldExtractor.get_price(order)
                    order_id = OrderFieldExtractor.get_order_id(order)

                    # Only include pending/open orders (not completed ones)
                    if not OrderStatusParser.is_completed(order) and symbol and qty > 0:
                        existing_orders[symbol.upper()] = {
                            "order_id": order_id,
                            "qty": qty,
                            "price": price,
                        }
                except Exception as e:
                    logger.debug(f"Error parsing order for mismatch check: {e}")
                    continue
        else:
            # Fallback: Make separate API call if orders data not provided
            existing_orders = self.get_existing_sell_orders()

        for symbol, order_info in list(self.active_sell_orders.items()):
            try:
                full_symbol = (
                    symbol.upper()
                )  # symbol is already full symbol from active_sell_orders
                base_symbol_for_lookup = extract_base_symbol(
                    symbol
                ).upper()  # For existing_orders lookup

                # Get position quantity from database (positions now use full symbols)
                position = self.positions_repo.get_by_symbol(self.user_id, full_symbol)
                if not position or position.closed_at:
                    # Position doesn't exist or is closed - skip
                    continue

                position_qty = position.quantity

                # Get sell order quantity from broker (existing_orders uses base symbols)
                if base_symbol_for_lookup not in existing_orders:
                    # Sell order doesn't exist in broker (might have been executed/cancelled)
                    continue

                sell_order = existing_orders[base_symbol_for_lookup]
                sell_order_qty = sell_order.get("qty", 0)
                sell_order_id = sell_order.get("order_id")
                sell_order_price = sell_order.get("price", 0)

                # Check for mismatch
                if sell_order_id and position_qty != sell_order_qty:
                    logger.info(
                        f"Detected sell order quantity mismatch for {full_symbol}: "
                        f"Position={position_qty}, Sell order={sell_order_qty}. "
                        f"Attempting to fix..."
                    )

                    # Update sell order to match position quantity
                    if self.update_sell_order(
                        order_id=str(sell_order_id),
                        symbol=full_symbol,
                        qty=int(position_qty),
                        new_price=sell_order_price,
                    ):
                        logger.info(
                            f"Fixed sell order quantity mismatch for {full_symbol}: "
                            f"{sell_order_qty} -> {position_qty} shares"
                        )
                        # Update tracking with new quantity
                        self._register_order(
                            symbol=symbol,
                            order_id=sell_order_id,
                            target_price=sell_order_price,
                            qty=position_qty,
                            ticker=order_info.get("ticker"),
                            placed_symbol=order_info.get("placed_symbol") or full_symbol,
                        )
                        fixed_count += 1
                    else:
                        logger.warning(
                            f"Failed to fix sell order quantity mismatch for {full_symbol}. "
                            f"Will retry in next check cycle."
                        )

            except Exception as e:
                logger.debug(f"Error checking sell order mismatch for {symbol}: {e}")
                continue

        if fixed_count > 0:
            logger.info(f"Fixed {fixed_count} sell order quantity mismatch(es)")

        return fixed_count

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

        for full_symbol, wait_info in list(self.waiting_for_circuit_expansion.items()):
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
                    logger.debug(f"{full_symbol}: No ticker available for circuit check")
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
                        f"{full_symbol}: EMA9 (Rs {current_ema9:.2f}) still exceeds upper circuit "
                        f"(Rs {upper_circuit:.2f}). Waiting..."
                    )
                    continue

                # EMA9 is now within circuit limits - retry placing order
                # Use current EMA9 if it's lower than stored target (better price), otherwise use stored target
                target_price = min(current_ema9, ema9_target)

                logger.info(
                    f"{full_symbol}: EMA9 (Rs {current_ema9:.2f}) is now within circuit limit "
                    f"(Rs {upper_circuit:.2f}). Retrying order placement at Rs {target_price:.2f}..."
                )

                # Place order - if it succeeds, remove from waiting list
                # If it fails again with circuit limit, it will be re-added with updated limits
                order_id = self.place_sell_order(trade, target_price)

                if order_id:
                    # Order placed successfully - remove from waiting list
                    logger.info(
                        f"{full_symbol}: Order placed successfully at Rs {target_price:.2f}, "
                        f"Order ID: {order_id}"
                    )
                    del self.waiting_for_circuit_expansion[full_symbol]
                    retried_count += 1

                    # Register the order for tracking
                    qty = trade.get("qty", 0)
                    ticker = trade.get("ticker", "")
                    placed_symbol = trade.get("placed_symbol", trade.get("symbol", full_symbol))
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
                        f"{full_symbol}: Order placement failed. Will check again on next cycle."
                    )

            except Exception as e:
                logger.error(f"Error checking circuit expansion for {full_symbol}: {e}")
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
            "missing_orders_placed": 0,  # Issue #5: Track orders placed for missing positions
        }

        # Optimized Manual Sell Detection: Use get_orders() for immediate detection
        # Holdings API only updates T+1 (next day after settlement), so running it every 30 minutes
        # during market hours is wasteful. Instead, we detect manual sells immediately using
        # get_orders() data which is already fetched every minute in monitor_all_orders().
        now = datetime.now()

        # Detect and track pending manual sell orders for system positions
        # This ensures manual sell orders are tracked to prevent duplicate placement
        pending_manual_sell_stats = self._detect_and_track_pending_manual_sell_orders()
        if pending_manual_sell_stats.get("tracked", 0) > 0:
            logger.info(
                f"Tracked {pending_manual_sell_stats['tracked']} pending manual sell orders "
                f"for system positions"
            )

        # Clean up any rejected/cancelled orders before monitoring
        self._cleanup_rejected_orders()

        # Check for circuit expansion and retry waiting orders
        circuit_retried = self._check_and_retry_circuit_expansion()
        stats["circuit_retried"] = circuit_retried

        # Issue #5 Fix: Check for positions without sell orders even when active_sell_orders is empty
        if not self.active_sell_orders:
            logger.debug(
                "No active sell orders to monitor - checking for positions without sell orders"
            )
            positions_without_orders = self._check_positions_without_sell_orders()
            if positions_without_orders > 0:
                logger.info(
                    f"Issue #5: Found {positions_without_orders} positions without sell orders. "
                    f"Attempting to place sell orders..."
                )
                # Attempt to place sell orders for positions that don't have them
                # This handles cases where orders failed to place at market open
                orders_placed, failed_positions = self._place_sell_orders_for_missing_positions()
                if orders_placed > 0:
                    logger.info(
                        f"Issue #5: Successfully placed {orders_placed} sell orders for missing positions"
                    )
                    stats["missing_orders_placed"] = orders_placed
                    # Send success alert if some orders were placed but not all
                    if orders_placed < positions_without_orders:
                        remaining = positions_without_orders - orders_placed
                        if hasattr(self, "telegram_notifier") and self.telegram_notifier:
                            try:
                                # Build detailed message with failed symbols
                                failed_symbols = [
                                    fp["symbol"] for fp in failed_positions[:10]
                                ]  # Limit to 10
                                symbols_text = ", ".join(failed_symbols)
                                if len(failed_positions) > 10:
                                    symbols_text += f" (+{len(failed_positions) - 10} more)"

                                message_lines = [
                                    f"Partially placed sell orders: {orders_placed}/{positions_without_orders} successful.",
                                    f"{remaining} positions still without sell orders.",
                                    "",
                                    "Failed symbols:",
                                    symbols_text,
                                ]

                                # Add reasons summary
                                reason_counts = {}
                                for fp in failed_positions:
                                    reason = fp["reason"]
                                    reason_counts[reason] = reason_counts.get(reason, 0) + 1

                                if reason_counts:
                                    message_lines.append("")
                                    message_lines.append("Reasons:")
                                    for reason, count in list(reason_counts.items())[
                                        :5
                                    ]:  # Top 5 reasons
                                        message_lines.append(f"  - {reason}: {count}")

                                self.telegram_notifier.notify_system_alert(
                                    alert_type="SELL_ORDERS_PARTIALLY_PLACED",
                                    message_text="\n".join(message_lines),
                                    severity="WARNING",
                                    user_id=self.user_id if hasattr(self, "user_id") else None,
                                )
                            except Exception as e:
                                logger.debug(f"Failed to send Issue #5 partial success alert: {e}")
                else:
                    logger.warning(
                        f"Issue #5: Could not place sell orders for {positions_without_orders} positions. "
                        f"Check logs for reasons (EMA9 calculation failure, etc.)"
                    )
                    # Issue #5: Send alert when no orders could be placed with detailed symbol list
                    if hasattr(self, "telegram_notifier") and self.telegram_notifier:
                        try:
                            # Build detailed message with failed symbols and reasons
                            failed_symbols = [
                                fp["symbol"] for fp in failed_positions[:10]
                            ]  # Limit to 10
                            symbols_text = ", ".join(failed_symbols)
                            if len(failed_positions) > 10:
                                symbols_text += f" (+{len(failed_positions) - 10} more)"

                            message_lines = [
                                f"Found {positions_without_orders} positions without sell orders.",
                                "Could not place any sell orders.",
                                "",
                                "Affected symbols:",
                                symbols_text,
                            ]

                            # Add reasons summary
                            reason_counts = {}
                            for fp in failed_positions:
                                reason = fp["reason"]
                                reason_counts[reason] = reason_counts.get(reason, 0) + 1

                            if reason_counts:
                                message_lines.append("")
                                message_lines.append("Reasons:")
                                for reason, count in list(reason_counts.items())[
                                    :5
                                ]:  # Top 5 reasons
                                    message_lines.append(f"  - {reason}: {count}")

                            message_lines.append("")
                            message_lines.append("Check dashboard or logs for full details.")

                            self.telegram_notifier.notify_system_alert(
                                alert_type="SELL_ORDERS_MISSING",
                                message_text="\n".join(message_lines),
                                severity="WARNING",
                                user_id=self.user_id if hasattr(self, "user_id") else None,
                            )
                        except Exception as e:
                            logger.debug(f"Failed to send Issue #5 alert: {e}")
            else:
                logger.debug("No positions found without sell orders")
            # Still return early if no active orders (normal monitoring requires active orders)
            # But we've now attempted to fix missing orders
            return stats

        logger.debug(f"Monitoring {len(self.active_sell_orders)} active sell orders in parallel...")

        # Flaw #7 Fix: Get all orders once and use for both execution check and mismatch detection
        # This avoids duplicate API calls - we use the same data for multiple purposes
        all_orders_response = None
        try:
            all_orders_response = self.orders.get_orders()
        except Exception as e:
            logger.debug(f"Failed to fetch orders for monitoring: {e}")

        # Optimized: Detect manual sells immediately using get_orders() data (every minute)
        # This is more efficient than Holdings API which only updates T+1
        if all_orders_response:
            try:
                manual_sell_stats = self._detect_manual_sells_from_orders(all_orders_response)
                if manual_sell_stats.get("detected", 0) > 0:
                    logger.info(
                        f"Manual sell detection via get_orders(): "
                        f"{manual_sell_stats.get('detected', 0)} detected, "
                        f"{manual_sell_stats.get('closed', 0)} closed, "
                        f"{manual_sell_stats.get('updated', 0)} updated"
                    )
            except Exception as e:
                logger.debug(f"Manual sell detection from orders failed (non-critical): {e}")

        # Check for executed orders first (using the orders data we just fetched)
        executed_ids = self.check_order_execution(all_orders_response)

        # Flaw #7 Fix: Check for sell order quantity mismatches using the same orders data
        # Detects and fixes mismatches caused by failed sell order updates (e.g., after reentry)
        # Runs every 15 minutes (:00, :15, :30, :45) to catch failures quickly
        if all_orders_response and now.minute % 15 == 0 and now.second < 10:
            try:
                self._check_and_fix_sell_order_mismatches(all_orders_response)
            except Exception as e:
                logger.debug(f"Failed to check sell order mismatches (non-critical): {e}")

        # Remove executed orders BEFORE monitoring (don't waste API calls on executed orders)
        symbols_executed = []
        for symbol, order_info in list(self.active_sell_orders.items()):
            order_id = order_info.get("order_id")

            # Check if sell order has been completed (using orders data from monitoring cycle)
            completed_order_info = self.has_completed_sell_order(symbol, all_orders_response)
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
                        full_symbol = (
                            symbol.upper()
                        )  # symbol is already full symbol from active_sell_orders
                        if filled_qty > 0:
                            if filled_qty >= order_qty or filled_qty >= order_info.get("qty", 0):
                                # Full execution - mark position as closed
                                # Wrap position and order updates in transaction for atomicity
                                if transaction and ist_now:
                                    # Phase 0.2: Get exit details from sell order
                                    exit_reason = "EMA9_TARGET"  # Default
                                    exit_rsi = None
                                    sell_order_db_id = None

                                    # Try to get sell order from database to extract exit details
                                    if self.orders_repo and completed_order_id:
                                        try:
                                            sell_order = self.orders_repo.get_by_broker_order_id(
                                                self.user_id, completed_order_id
                                            )
                                            if sell_order:
                                                sell_order_db_id = sell_order.id
                                                if sell_order.order_metadata and isinstance(
                                                    sell_order.order_metadata, dict
                                                ):
                                                    exit_reason = sell_order.order_metadata.get(
                                                        "exit_note", "EMA9_TARGET"
                                                    )
                                                    exit_rsi = sell_order.order_metadata.get(
                                                        "exit_rsi"
                                                    )
                                        except Exception as e:
                                            logger.debug(
                                                f"Could not get sell order for exit details: {e}"
                                            )

                                    with transaction(self.positions_repo.db):
                                        self.positions_repo.mark_closed(
                                            user_id=self.user_id,
                                            symbol=full_symbol,
                                            closed_at=ist_now(),
                                            exit_price=order_price,
                                            exit_reason=exit_reason,
                                            exit_rsi=exit_rsi,
                                            sell_order_id=sell_order_db_id,
                                            auto_commit=False,  # Transaction handles commit
                                        )
                                        logger.info(
                                            f"Position marked as closed in database: {full_symbol} "
                                            f"(sold {filled_qty} shares @ Rs {order_price:.2f})"
                                        )

                                        # Phase 0.4: Mark target as achieved
                                        if self.targets_repo and self.user_id:
                                            try:
                                                target = self.targets_repo.get_by_symbol(
                                                    self.user_id, full_symbol, active_only=True
                                                )
                                                if target:
                                                    self.targets_repo.mark_achieved(
                                                        target.id, achieved_at=ist_now()
                                                    )
                                                    logger.debug(
                                                        f"Marked target as achieved for {full_symbol}"
                                                    )
                                            except Exception as e:
                                                logger.debug(
                                                    f"Failed to mark target as achieved for {full_symbol}: {e}"
                                                )

                                        # Close corresponding ONGOING buy orders (within same transaction)
                                        # Extract base symbol for _close_buy_orders_for_symbol which uses base symbols
                                        base_symbol_for_buy_orders = extract_base_symbol(
                                            symbol
                                        ).upper()
                                        self._close_buy_orders_for_symbol(
                                            base_symbol_for_buy_orders
                                        )

                                # Edge Case #12: Cancel pending reentry orders for closed position
                                # Note: This includes broker API calls, so it's outside the transaction
                                # Extract base symbol for _cancel_pending_reentry_orders which uses base symbols
                                base_symbol_for_reentry = extract_base_symbol(symbol).upper()
                                self._cancel_pending_reentry_orders(base_symbol_for_reentry)

                                # Cache removed - holdings fetched when needed
                            else:
                                # Partial execution - reduce quantity, keep position open
                                self.positions_repo.reduce_quantity(
                                    user_id=self.user_id,
                                    symbol=full_symbol,
                                    sold_quantity=float(filled_qty),
                                )
                                # Cache removed - holdings fetched when needed
                                logger.info(
                                    f"Position quantity reduced in database: {full_symbol} "
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
                        full_symbol = (
                            symbol.upper()
                        )  # symbol is already full symbol from active_sell_orders
                        # Assume full execution if we don't have filled_qty info
                        # Wrap position and order updates in transaction for atomicity
                        if transaction and ist_now:
                            # Phase 0.2: Get exit details from sell order
                            exit_reason = "EMA9_TARGET"  # Default
                            exit_rsi = None
                            sell_order_db_id = None

                            # Try to get sell order from database to extract exit details
                            if self.orders_repo and order_id:
                                try:
                                    sell_order = self.orders_repo.get_by_broker_order_id(
                                        self.user_id, order_id
                                    )
                                    if sell_order:
                                        sell_order_db_id = sell_order.id
                                        if sell_order.order_metadata and isinstance(
                                            sell_order.order_metadata, dict
                                        ):
                                            exit_reason = sell_order.order_metadata.get(
                                                "exit_note", "EMA9_TARGET"
                                            )
                                            exit_rsi = sell_order.order_metadata.get("exit_rsi")
                                except Exception as e:
                                    logger.debug(f"Could not get sell order for exit details: {e}")

                            with transaction(self.positions_repo.db):
                                self.positions_repo.mark_closed(
                                    user_id=self.user_id,
                                    symbol=full_symbol,
                                    closed_at=ist_now(),
                                    exit_price=current_price,
                                    exit_reason=exit_reason,
                                    exit_rsi=exit_rsi,
                                    sell_order_id=sell_order_db_id,
                                    auto_commit=False,  # Transaction handles commit
                                )
                                logger.info(
                                    f"Position marked as closed in database: {full_symbol} "
                                    f"(sold {sold_qty} shares @ Rs {current_price:.2f})"
                                )

                                # Phase 0.4: Mark target as achieved
                                if self.targets_repo and self.user_id:
                                    try:
                                        target = self.targets_repo.get_by_symbol(
                                            self.user_id, full_symbol, active_only=True
                                        )
                                        if target:
                                            self.targets_repo.mark_achieved(
                                                target.id, achieved_at=ist_now()
                                            )
                                            logger.debug(
                                                f"Marked target as achieved for {full_symbol}"
                                            )
                                    except Exception as e:
                                        logger.debug(
                                            f"Failed to mark target as achieved for {full_symbol}: {e}"
                                        )

                                # Close corresponding ONGOING buy orders (within same transaction)
                                # Extract base symbol for _close_buy_orders_for_symbol which uses base symbols
                                base_symbol_for_buy_orders = extract_base_symbol(symbol).upper()
                                self._close_buy_orders_for_symbol(base_symbol_for_buy_orders)

                        # Invalidate cache since position was closed (broker holdings changed)
                        self._invalidate_holdings_cache()
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
            symbols_to_remove = []  # Track symbols to remove due to closed positions

            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]

                try:
                    result = future.result()
                    action = result.get("action")

                    # Remove closed positions from tracking
                    if result.get("remove_from_tracking"):
                        symbols_to_remove.append(symbol)
                        logger.info(
                            f"Removing {symbol} from sell order tracking: position is closed"
                        )
                        continue

                    if action == "updated":
                        symbols_to_update_ema[symbol] = result.get("ema9")
                        stats["updated"] += 1
                    elif action in ["checked", "error", "skipped"]:
                        stats["checked"] += 1

                except Exception as e:
                    logger.error(f"Error processing result for {symbol}: {e}")
                    stats["checked"] += 1

            # Remove closed positions from active_sell_orders
            for symbol in symbols_to_remove:
                self._remove_order(symbol, reason="Position closed")
                if symbol in self.lowest_ema9:
                    del self.lowest_ema9[symbol]

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
                if get_telegram_notifier:
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
                    elif send_telegram:
                        # Fallback to old method if telegram_notifier not available
                        send_telegram(message)
                elif send_telegram:
                    send_telegram(message)
            except Exception as notify_err:
                logger.warning(f"Failed to send RSI exit error notification: {notify_err}")
                # Fallback to old method on error
                if send_telegram:
                    try:
                        send_telegram(message)
                    except Exception:
                        pass  # Already logged
        except Exception as e:
            logger.warning(f"Failed to send RSI exit error notification: {e}")

    def _get_order_variety_for_market_hours(self) -> str:
        """Get order variety based on market hours."""
        if is_market_hours and is_market_hours():
            return "REGULAR"
        return config.DEFAULT_VARIETY
