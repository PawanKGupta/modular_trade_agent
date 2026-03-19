#!/usr/bin/env python3
"""
Auto Trade Engine for Kotak Neo
- Reads recommendations (from analysis_results CSV)
- Places AMO buy orders within portfolio constraints
- Tracks positions and executes re-entry and exit based on RSI/EMA
"""

import glob
import os

# Project logger
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from math import floor, isfinite
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
# Core market data
from core.telegram import send_telegram
from modules.kotak_neo_auto_trader.services import (
    get_indicator_service,
    get_price_service,
)
from utils.logger import logger

# Database models
try:
    from sqlalchemy import text

    from src.infrastructure.db.models import OrderStatus as DbOrderStatus
except ImportError:
    DbOrderStatus = None
    text = None

# Kotak Neo modules
try:
    from . import config
    from .auth import KotakNeoAuth
    from .eod_cleanup import get_eod_cleanup, schedule_eod_cleanup
    from .manual_order_matcher import get_manual_order_matcher

    # Phase 2 modules
    from .order_status_verifier import get_order_status_verifier
    from .order_tracker import (
        add_pending_order,
        configure_order_tracker,
        extract_order_id,
        get_order_tracker,
        search_order_in_broker_orderbook,
    )
    from .orders import KotakNeoOrders
    from .portfolio import KotakNeoPortfolio
    from .scrip_master import KotakNeoScripMaster
    from .storage import (
        add_failed_order,
        append_trade,
        check_manual_buys_of_failed_orders,
        cleanup_expired_failed_orders,
        get_failed_orders,
        load_history,
        remove_failed_order,
        save_history,
    )
    from .telegram_notifier import get_telegram_notifier
    from .tracking_scope import (
        add_tracked_symbol,
        get_tracked_symbols,
        is_tracked,
        update_tracked_qty,
    )
    from .trader import KotakNeoTrader
    from .utils.order_field_extractor import OrderFieldExtractor
except ImportError:
    from modules.kotak_neo_auto_trader import config
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.eod_cleanup import get_eod_cleanup
    from modules.kotak_neo_auto_trader.manual_order_matcher import get_manual_order_matcher

    # Phase 2 modules
    from modules.kotak_neo_auto_trader.order_status_verifier import get_order_status_verifier
    from modules.kotak_neo_auto_trader.order_tracker import (
        add_pending_order,
        configure_order_tracker,
        extract_order_id,
        get_order_tracker,
        search_order_in_broker_orderbook,
    )
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
    from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
    from modules.kotak_neo_auto_trader.scrip_master import KotakNeoScripMaster
    from modules.kotak_neo_auto_trader.storage import (
        add_failed_order,
        append_trade,
        check_manual_buys_of_failed_orders,
        cleanup_expired_failed_orders,
        get_failed_orders,
        load_history,
        remove_failed_order,
        save_history,
    )
    from modules.kotak_neo_auto_trader.telegram_notifier import get_telegram_notifier
    from modules.kotak_neo_auto_trader.tracking_scope import (
        add_tracked_symbol,
        get_tracked_symbols,
        is_tracked,
    )
    from modules.kotak_neo_auto_trader.utils.order_field_extractor import (
        OrderFieldExtractor,
    )


@dataclass
class Recommendation:
    ticker: str  # e.g. RELIANCE.NS
    verdict: str  # strong_buy|buy|watch
    last_close: float
    execution_capital: float | None = None  # Phase 11: Dynamic capital based on liquidity
    priority_score: float | None = None  # Priority score for sorting (higher = higher priority)


class OrderPlacementError(RuntimeError):
    """Raised when a broker/API error occurs while placing buy orders."""

    def __init__(self, message: str, symbol: str | None = None):
        super().__init__(message)
        self.symbol = symbol


class AutoTradeEngine:
    def __init__(
        self,
        env_file: str = "kotak_neo.env",
        auth: KotakNeoAuth | None = None,
        enable_verifier: bool = True,
        enable_telegram: bool = True,
        enable_eod_cleanup: bool = True,
        verifier_interval: int = 1800,
        # Phase 2.3: User context parameters
        user_id: int | None = None,
        db_session=None,
        strategy_config=None,  # StrategyConfig instance
    ):
        self.env_file = env_file
        # IMPORTANT: When used by run_trading_service, auth MUST be provided
        # Only create new auth for standalone usage (backward compatibility)
        if auth is None:
            logger.warning(
                "AutoTradeEngine: No auth provided - creating new session. "
                "For run_trading_service, always pass the shared auth session."
            )
            self.auth = KotakNeoAuth(env_file)
        else:
            self.auth = auth

        # Phase 2.3: User context
        self.user_id = user_id
        self.db = db_session

        # Phase 2.3: User-specific configuration
        if strategy_config is None:
            # Fallback to default config for backward compatibility
            from config.strategy_config import StrategyConfig

            self.strategy_config = StrategyConfig.default()
            logger.warning(
                "AutoTradeEngine: No strategy_config provided - using default. "
                "For multi-user support, always pass user-specific config."
            )
        else:
            self.strategy_config = strategy_config

        self.orders: KotakNeoOrders | None = None
        self.portfolio: KotakNeoPortfolio | None = None

        # Phase 2.3: Use repository instead of file-based storage
        if self.db:
            # Use database repositories
            self.history_path = None  # No longer using file-based storage
            from src.infrastructure.persistence.orders_repository import OrdersRepository
            from src.infrastructure.persistence.positions_repository import PositionsRepository

            self.orders_repo = OrdersRepository(self.db)
            self.positions_repo = PositionsRepository(self.db)

            # Ensure global OrderTracker writes pending orders to the database
            try:
                configure_order_tracker(
                    data_dir="data",
                    db_session=self.db,
                    user_id=self.user_id,
                    use_db=True,
                )
                logger.info(
                    "OrderTracker configured with DB session (DB-only mode enabled by default)"
                )
            except Exception as tracker_error:
                logger.warning(f"Failed to configure OrderTracker with DB session: {tracker_error}")
        else:
            # Backward compatibility: file-based storage
            self.history_path = config.TRADES_HISTORY_PATH
            self.orders_repo = None
            self.positions_repo = None

        # Initialize scrip master for symbol resolution
        self.scrip_master: KotakNeoScripMaster | None = None

        # Phase 2 modules configuration
        self._enable_verifier = enable_verifier
        self._enable_telegram = enable_telegram
        self._enable_eod_cleanup = enable_eod_cleanup
        self._verifier_interval = verifier_interval

        # Phase 2 module instances (initialized in login)
        self.telegram_notifier = None
        self.order_verifier = None
        self.manual_matcher = None
        self.eod_cleanup = None

        # Initialize unified services (Phase 1.3: Duplicate steps consolidation)
        # Services initialized without price_manager initially (can be updated later if needed)
        self.price_service = get_price_service(enable_caching=True)
        self.indicator_service = get_indicator_service(
            price_service=self.price_service, enable_caching=True
        )

        # Initialize PortfolioService (Phase 2.1: Portfolio & Position Services)
        # Portfolio and orders will be set after login
        from modules.kotak_neo_auto_trader.services import get_portfolio_service

        self.portfolio_service = get_portfolio_service(
            portfolio=None,  # Will be set after login
            orders=None,  # Will be set after login
            auth=self.auth,
            strategy_config=self.strategy_config,
            orders_repo=self.orders_repo if hasattr(self, "orders_repo") else None,
            user_id=self.user_id,
            enable_caching=True,
        )

        # Initialize OrderValidationService (Phase 3.1: Order Validation & Verification)
        # Portfolio, orders, and orders_repo will be set after login
        from modules.kotak_neo_auto_trader.services import get_order_validation_service

        self.order_validation_service = get_order_validation_service(
            portfolio_service=self.portfolio_service,
            portfolio=None,  # Will be set after login
            orders=None,  # Will be set after login
            orders_repo=self.orders_repo if hasattr(self, "orders_repo") else None,
            user_id=self.user_id,
        )

    # ---------------------- Telegram Notifier Helper (Phase 3) ----------------------
    def _get_telegram_notifier(self):
        """
        Get Telegram notifier instance with user-specific credentials.

        Creates a new TelegramNotifier instance (not singleton) with user-specific
        bot_token and chat_id from notification preferences. Falls back to singleton
        pattern if user_id or db_session is not available (backward compatibility).

        Returns:
            TelegramNotifier instance or None if not available
        """
        try:
            # Backward compatibility: If no user_id or db, use singleton pattern
            if not self.user_id or not self.db:
                logger.debug(
                    "AutoTradeEngine: No user_id or db_session - using singleton TelegramNotifier"
                )
                return get_telegram_notifier(db_session=self.db)

            # Check if telegram notifier module is available
            try:
                from services.notification_preference_service import (
                    NotificationPreferenceService,
                )
            except ImportError:
                logger.debug("NotificationPreferenceService not available - using singleton")
                return get_telegram_notifier(db_session=self.db)

            # Get user's notification preferences to get Telegram chat ID and bot token
            pref_service = NotificationPreferenceService(self.db)
            preferences = pref_service.get_preferences(self.user_id)

            # Check if Telegram is enabled for this user
            if not preferences or not preferences.telegram_enabled:
                logger.debug(f"Telegram not enabled for user {self.user_id}")
                return None

            # Get bot token from user preferences first, then fall back to environment
            bot_token = preferences.telegram_bot_token if preferences else None
            if not bot_token:
                import os

                bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

            chat_id = preferences.telegram_chat_id if preferences else None

            # Only create notifier if both bot token and chat ID are available
            if not bot_token:
                logger.debug(f"Telegram bot token not available for user {self.user_id}")
                return None
            if not chat_id:
                logger.debug(f"Telegram chat ID not configured for user {self.user_id}")
                return None

            # Create a new TelegramNotifier instance (not singleton) for this user
            # This is necessary because each user has a different chat_id
            from .telegram_notifier import TelegramNotifier

            return TelegramNotifier(
                bot_token=bot_token,
                chat_id=chat_id,
                enabled=True,
                db_session=self.db,
            )
        except Exception as e:
            logger.warning(
                f"Failed to get user-specific Telegram notifier: {e}. Falling back to singleton."
            )
            # Fallback to singleton pattern on error
            return get_telegram_notifier(db_session=self.db)

    # ---------------------- Storage Abstraction (Phase 2.3) ----------------------
    def _load_trades_history(self) -> dict[str, Any]:
        """
        Load trades history from repository or file-based storage.
        Returns dict with 'trades' list and 'failed_orders' list.
        """
        if self.orders_repo and self.user_id:
            # Use repository-based storage

            # Get open positions
            open_positions = self.positions_repo.list(self.user_id)
            open_positions = [p for p in open_positions if p.closed_at is None]

            # Get buy orders for these positions to reconstruct trade metadata
            all_orders, _ = self.orders_repo.list(self.user_id)
            buy_orders = [o for o in all_orders if o.side.lower() == "buy"]

            # Convert positions to trades format
            trades = []
            for pos in open_positions:
                # Find related buy orders for this position
                symbol_orders = [
                    o for o in buy_orders if o.symbol.upper().split("-")[0] == pos.symbol.upper()
                ]
                if symbol_orders:
                    # Use the first buy order's metadata
                    first_order = symbol_orders[0]
                    metadata = first_order.order_metadata or {}
                else:
                    metadata = {}

                trade = {
                    "symbol": pos.symbol,
                    "placed_symbol": metadata.get("placed_symbol", pos.symbol),
                    "ticker": metadata.get("ticker", f"{pos.symbol}.NS"),
                    "entry_price": pos.avg_price,
                    "entry_time": (
                        pos.opened_at.isoformat() if pos.opened_at else datetime.now().isoformat()
                    ),
                    "rsi10": metadata.get("rsi10"),
                    "ema9": metadata.get("ema9"),
                    "ema200": metadata.get("ema200"),
                    "capital": metadata.get("capital"),
                    "qty": pos.quantity,
                    "rsi_entry_level": metadata.get("rsi_entry_level"),
                    "levels_taken": metadata.get(
                        "levels_taken", {"30": True, "20": False, "10": False}
                    ),
                    "reset_ready": metadata.get("reset_ready", False),
                    "order_response": metadata.get("order_response"),
                    "status": "open",
                    "entry_type": metadata.get("entry_type", "system_recommended"),
                    "reentries": metadata.get("reentries", []),
                }
                trades.append(trade)

            # Get closed positions (for historical reference)
            closed_positions = [
                p for p in self.positions_repo.list(self.user_id) if p.closed_at is not None
            ]
            for pos in closed_positions:
                # Find related orders
                symbol_orders = [
                    o for o in all_orders if o.symbol.upper().split("-")[0] == pos.symbol.upper()
                ]
                if symbol_orders:
                    first_order = symbol_orders[0]
                    metadata = first_order.order_metadata or {}
                else:
                    metadata = {}

                trade = {
                    "symbol": pos.symbol,
                    "placed_symbol": metadata.get("placed_symbol", pos.symbol),
                    "ticker": metadata.get("ticker", f"{pos.symbol}.NS"),
                    "entry_price": pos.avg_price,
                    "entry_time": (
                        pos.opened_at.isoformat() if pos.opened_at else datetime.now().isoformat()
                    ),
                    "exit_price": metadata.get("exit_price"),
                    "exit_time": pos.closed_at.isoformat() if pos.closed_at else None,
                    "exit_rsi10": metadata.get("exit_rsi10"),
                    "exit_reason": metadata.get("exit_reason"),
                    "qty": pos.quantity,
                    "status": "closed",
                    "entry_type": metadata.get("entry_type", "system_recommended"),
                }
                trades.append(trade)

            # Failed orders: stored in Orders with special metadata flag
            failed_orders = []
            for order in all_orders:
                metadata = order.order_metadata or {}
                if metadata.get("failed_order"):
                    failed_orders.append(metadata.get("failed_order_data", {}))

            return {
                "trades": trades,
                "failed_orders": failed_orders,
                "last_run": datetime.now().isoformat(),
            }
        # Fallback to file-based storage
        elif self.history_path:
            return load_history(self.history_path)
        else:
            # No storage available - return empty structure
            return {
                "trades": [],
                "failed_orders": [],
                "last_run": None,
            }

    def _update_position_from_trade(self, trade: dict[str, Any]) -> None:
        """
        Update positions table directly from a single trade entry.
        This is called when a trade is added/updated to avoid syncing all trades.
        Syncs reentry data from trade history.
        """
        if not self.positions_repo or not self.user_id:
            return

        symbol = trade.get("symbol", "").upper()
        status = trade.get("status", "open")
        qty = trade.get("qty", 0)
        entry_price = trade.get("entry_price")

        if not symbol or not entry_price:
            return

        if status == "open":
            # Upsert open position
            try:
                entry_time = datetime.fromisoformat(
                    trade.get("entry_time", datetime.now().isoformat())
                )
            except:
                entry_time = datetime.now()

            # Get reentry data from trade history
            reentries = trade.get("reentries", [])
            reentry_count = len(reentries) if isinstance(reentries, list) else 0

            # Calculate initial_entry_price (first entry price, before any reentries)
            initial_entry_price = entry_price
            last_reentry_price = None

            # If there are reentries, get the initial entry price from the first trade entry
            # For now, we'll use entry_price as initial_entry_price
            # This will be updated when we sync from trade history properly

            # Find last reentry price
            if reentries and isinstance(reentries, list) and len(reentries) > 0:
                last_reentry = reentries[-1]
                if isinstance(last_reentry, dict):
                    last_reentry_price = last_reentry.get("price")

            # Check if position already exists to preserve initial_entry_price
            existing_pos = self.positions_repo.get_by_symbol(self.user_id, symbol)
            if existing_pos and existing_pos.initial_entry_price:
                initial_entry_price = existing_pos.initial_entry_price

            # Extract entry RSI from trade metadata or order metadata
            entry_rsi = None
            if trade.get("entry_rsi") is not None:
                entry_rsi = trade.get("entry_rsi")
            elif trade.get("rsi_entry_level") is not None:
                entry_rsi = trade.get("rsi_entry_level")
            elif trade.get("rsi10") is not None:
                entry_rsi = trade.get("rsi10")

            # Only set entry_rsi for new positions (preserve original entry RSI)
            # If position exists and already has entry_rsi, don't overwrite it
            if existing_pos and existing_pos.entry_rsi is not None:
                entry_rsi = None  # Don't update existing entry_rsi

            self.positions_repo.upsert(
                user_id=self.user_id,
                symbol=symbol,
                quantity=qty,
                avg_price=entry_price,
                opened_at=entry_time,
                reentry_count=reentry_count,
                reentries=reentries if reentries else None,
                initial_entry_price=(
                    initial_entry_price if not existing_pos else None
                ),  # Only set for new positions
                last_reentry_price=last_reentry_price,
                entry_rsi=entry_rsi,  # Set entry RSI for new positions
            )
        elif status == "closed":
            # Close position using mark_closed() to ensure exit details are populated
            pos = self.positions_repo.get_by_symbol(self.user_id, symbol)
            if pos:
                try:
                    exit_time = datetime.fromisoformat(
                        trade.get("exit_time", datetime.now().isoformat())
                    )
                except:
                    exit_time = datetime.now()

                # Extract exit details from trade dictionary if available
                exit_price = trade.get("exit_price")
                exit_reason = trade.get("exit_reason", "HISTORY_IMPORT")
                exit_rsi = trade.get("exit_rsi10")  # May be "exit_rsi10" in trade dict
                realized_pnl = trade.get("pnl")  # May be "pnl" in trade dict
                sell_order_id_str = trade.get("sell_order_id")

                # Try to find sell_order_id if provided (may be string or int)
                sell_order_id = None
                if sell_order_id_str and self.orders_repo:
                    try:
                        # If it's already an int, use it directly (assume it's a DB ID)
                        if isinstance(sell_order_id_str, int):
                            sell_order_id = sell_order_id_str
                        else:
                            # Try to find order by broker_order_id or order_id (string match)
                            all_orders, _ = self.orders_repo.list(self.user_id)
                            for order in all_orders:
                                if str(getattr(order, "broker_order_id", None) or "") == str(
                                    sell_order_id_str
                                ) or str(getattr(order, "order_id", None) or "") == str(
                                    sell_order_id_str
                                ):
                                    sell_order_id = order.id
                                    break
                    except Exception as e:
                        logger.debug(f"Could not find sell_order_id {sell_order_id_str}: {e}")

                # Use mark_closed() to properly set all exit details
                self.positions_repo.mark_closed(
                    user_id=self.user_id,
                    symbol=pos.symbol,
                    closed_at=exit_time,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    exit_rsi=exit_rsi,
                    realized_pnl=realized_pnl,
                    sell_order_id=sell_order_id,
                    auto_commit=True,
                )

    def _save_trades_history(self, data: dict[str, Any]) -> None:
        """
        Save trades history to repository or file-based storage.
        Note: For bulk sync operations, this still syncs all trades to positions.
        For individual trade updates, use _update_position_from_trade() instead.

        DB-only mode: When DB is available, skip JSON writes for consistency with sell orders.
        """
        if self.orders_repo and self.user_id:
            # DB-only mode: Bulk sync all trades to positions (no JSON write)
            # This aligns with sell order tracking which is DB-only
            if self.positions_repo:
                trades = data.get("trades", [])
                for trade in trades:
                    self._update_position_from_trade(trade)

            # Save failed orders metadata in Orders (if any)
            failed_orders = data.get("failed_orders", [])
            # Note: Failed orders are handled separately in add_failed_order/remove_failed_order
            # Skip JSON writes when DB is available (DB-only mode)
        # Fallback to file-based storage only if DB is not available
        elif self.history_path:
            save_history(self.history_path, data)

    def _append_trade(self, trade: dict[str, Any]) -> None:
        """
        Append a trade to history (repository or file-based).
        Directly updates positions table when trade is added/updated.

        DB-only mode: When DB is available, skip JSON writes for consistency with sell orders.
        """
        if self.orders_repo and self.user_id:
            # DB-only mode: Update positions table directly (no JSON write)
            # This aligns with sell order tracking which is DB-only
            if self.positions_repo:
                self._update_position_from_trade(trade)
            # Skip JSON writes when DB is available (DB-only mode)
            # Fallback to file-based storage only if DB is not available
        elif self.history_path:
            # Fallback: file-based storage when DB is not available
            append_trade(self.history_path, trade)

    def _get_failed_orders(
        self, include_previous_day_before_market: bool = False
    ) -> list[dict[str, Any]]:
        """
        Get failed orders from repository or file-based storage.

        Phase 6: Updated to use first-class failure statuses (FAILED)
        instead of metadata flags. RETRY_PENDING merged into FAILED.
        """
        if self.orders_repo and self.user_id:
            # Phase 6: Use repository's get_failed_orders() method or check status
            try:
                failed_orders_db = self.orders_repo.get_failed_orders(self.user_id)
                # Convert DB orders to dict format for backward compatibility
                failed_orders = []
                for order in failed_orders_db:
                    failed_data = {
                        "symbol": order.symbol,
                        "ticker": getattr(order, "ticker", None),
                        "close": order.price,
                        "qty": order.quantity,
                        "reason": getattr(order, "reason", None)
                        or "unknown",  # Use unified reason field
                        "first_failed_at": (
                            order.first_failed_at.isoformat() if order.first_failed_at else None
                        ),
                        "retry_count": order.retry_count or 0,
                        "status": order.status.value if order.status else "failed",
                    }
                    failed_orders.append(failed_data)
                return failed_orders
            except Exception as e:
                logger.warning(f"Error getting failed orders from repository: {e}")
                # Fallback: Check status manually

                all_orders, _ = self.orders_repo.list(self.user_id)
                failed_orders = []
                for order in all_orders:
                    if order.status == DbOrderStatus.FAILED:  # Merged: FAILED + RETRY_PENDING
                        failed_data = {
                            "symbol": order.symbol,
                            "ticker": getattr(order, "ticker", None),
                            "close": order.price,
                            "qty": order.quantity,
                            "reason": getattr(order, "reason", None) or "unknown",
                            "first_failed_at": (
                                order.first_failed_at.isoformat() if order.first_failed_at else None
                            ),
                            "retry_count": order.retry_count or 0,
                            "status": order.status.value if order.status else "failed",
                        }
                        failed_orders.append(failed_data)
                return failed_orders
        # Fallback to file-based storage
        elif self.history_path:
            return get_failed_orders(self.history_path, include_previous_day_before_market)
        else:
            return []

    def _add_failed_order(self, failed_order: dict[str, Any]) -> None:
        """
        Add a failed order to retry queue (repository or file-based).

        Phase 6: Updated to use first-class failure statuses (FAILED)
        and store failure metadata in dedicated columns instead of JSON metadata.
        RETRY_PENDING merged into FAILED.

        This method is wrapped in try-except to prevent exceptions from
        crashing the entire buy order task. Failed order tracking is
        non-critical - if it fails, we log and continue.
        """
        try:
            if self.orders_repo and self.user_id:
                # Phase 6: Use repository-based storage with first-class failure statuses
                symbol = failed_order.get("symbol", "")
                if not symbol:
                    return

                # Normalize symbol for comparison (remove segment suffixes like -EQ, -BE, etc.)
                def normalize_symbol(sym: str) -> str:
                    """Normalize symbol by removing segment suffixes"""
                    if not sym:
                        return ""
                    # Remove common segment suffixes and normalize
                    normalized = sym.upper().strip()
                    # Split by "-" and take first part, or use whole symbol if no "-"
                    if "-" in normalized:
                        normalized = normalized.split("-")[0].strip()
                    return normalized

                normalized_symbol = normalize_symbol(symbol)

                # Phase 6: Check for existing failed orders using status instead of metadata

                existing_orders, _ = self.orders_repo.list(self.user_id)
                existing_failed_orders = [
                    o
                    for o in existing_orders
                    if o.status == DbOrderStatus.FAILED  # Merged: FAILED + RETRY_PENDING
                    and normalize_symbol(o.symbol) == normalized_symbol
                ]

                # Determine failure reason and retry status
                failure_reason = failed_order.get("reason", "unknown")
                is_retryable = failure_reason == "insufficient_balance" and not failed_order.get(
                    "non_retryable", False
                )
                retry_pending = is_retryable

                # Build failure reason string
                reason_parts = [failure_reason]
                if failed_order.get("shortfall"):
                    reason_parts.append(f"shortfall: Rs {failed_order['shortfall']:,.0f}")
                failure_reason_str = " - ".join(reason_parts)

                if existing_failed_orders:
                    # Phase 6: Update existing failed order using mark_failed()
                    order = existing_failed_orders[0]
                    try:
                        retry_count = order.retry_count or 0
                        self.orders_repo.mark_failed(
                            order=order,
                            failure_reason=failure_reason_str,
                            retry_pending=retry_pending,
                        )
                        logger.debug(
                            f"Updated existing failed order for {symbol} "
                            f"(status: FAILED)"  # All failures are FAILED now
                        )
                        # Phase 9: Send notification for retry queue update (if retryable)
                        if (
                            self.telegram_notifier
                            and self.telegram_notifier.enabled
                            and retry_pending
                        ):
                            try:
                                self.telegram_notifier.notify_retry_queue_updated(
                                    symbol=symbol,
                                    action="updated",
                                    retry_count=retry_count + 1,
                                    additional_info={"reason": failure_reason_str},
                                    user_id=self.user_id,
                                )
                            except Exception as notify_error:
                                logger.warning(
                                    f"Failed to send retry queue update notification: {notify_error}"
                                )
                    except Exception as update_error:
                        logger.warning(
                            f"Failed to update failed order {symbol}: {update_error}",
                            exc_info=update_error,
                        )
                        if hasattr(self.orders_repo, "db"):
                            try:
                                self.orders_repo.db.rollback()
                            except Exception:
                                pass
                else:
                    # Phase 6: Create new failed order with proper status
                    # Create order first, then mark as failed
                    try:
                        # Build order_metadata with ticker for retry logic
                        order_metadata = {}
                        if failed_order.get("ticker"):
                            order_metadata["ticker"] = failed_order["ticker"]
                        if failed_order.get("rsi10") is not None:
                            order_metadata["rsi10"] = failed_order["rsi10"]
                        if failed_order.get("ema9") is not None:
                            order_metadata["ema9"] = failed_order["ema9"]
                        if failed_order.get("ema200") is not None:
                            order_metadata["ema200"] = failed_order["ema200"]

                        new_order = self.orders_repo.create_amo(
                            user_id=self.user_id,
                            symbol=symbol,
                            side="buy",
                            order_type="market",
                            quantity=failed_order.get("qty", 0),
                            price=failed_order.get("close"),
                            order_id=None,
                            broker_order_id=None,
                            order_metadata=order_metadata if order_metadata else None,
                        )
                    except Exception as create_error:
                        # Handle database schema errors (e.g., missing column)
                        from sqlalchemy.exc import OperationalError

                        if isinstance(create_error, OperationalError) or (
                            hasattr(create_error, "orig")
                            and isinstance(create_error.orig, Exception)
                            and "no column named" in str(create_error).lower()
                        ):
                            logger.warning(
                                f"Database schema error when creating failed order for {symbol}: "
                                f"{create_error}. Migration may not have been applied. "
                                "Failed order won't be saved to database.",
                                exc_info=create_error,
                            )
                        else:
                            logger.warning(
                                f"Failed to create failed order for {symbol}: {create_error}",
                                exc_info=create_error,
                            )
                        # Rollback session to allow subsequent operations
                        if hasattr(self.orders_repo, "db"):
                            try:
                                self.orders_repo.db.rollback()
                            except Exception:
                                pass
                        return  # Exit early if order creation failed
                    # Phase 6: Mark as failed with proper status and metadata in columns
                    try:
                        self.orders_repo.mark_failed(
                            order=new_order,
                            failure_reason=failure_reason_str,
                            retry_pending=retry_pending,
                        )
                        logger.debug(
                            f"Created new failed order for {symbol} "
                            f"(status: FAILED)"  # All failures are FAILED now
                        )
                        # Phase 9: Send notification for retry queue update
                        if (
                            self.telegram_notifier
                            and self.telegram_notifier.enabled
                            and retry_pending
                        ):
                            try:
                                self.telegram_notifier.notify_retry_queue_updated(
                                    symbol=symbol,
                                    action="added",
                                    retry_count=0,
                                    additional_info={"reason": failure_reason_str},
                                    user_id=self.user_id,
                                )
                            except Exception as notify_error:
                                logger.warning(
                                    f"Failed to send retry queue notification: {notify_error}"
                                )
                    except Exception as update_error:
                        logger.warning(
                            f"Failed to mark new order as failed {symbol}: {update_error}",
                            exc_info=update_error,
                        )
                        if hasattr(self.orders_repo, "db"):
                            try:
                                self.orders_repo.db.rollback()
                            except Exception:
                                pass
            # Fallback to file-based storage
            elif self.history_path:
                add_failed_order(self.history_path, failed_order)
        except Exception as e:
            # Log error but don't crash the task - failed order tracking is non-critical
            logger.warning(
                f"Failed to save failed order to retry queue: {e}. "
                "Task will continue, but failed order won't be retried automatically.",
                exc_info=e,
            )

    def _remove_failed_order(self, symbol: str) -> None:
        """
        Remove a failed order from retry queue (repository or file-based).

        Phase 6: Updated to work with first-class failure statuses (FAILED, RETRY_PENDING)
        instead of metadata flags.
        """
        if self.orders_repo and self.user_id:
            # Phase 6: Use repository-based storage with status-based lookup

            all_orders, _ = self.orders_repo.list(self.user_id)
            for order in all_orders:
                # Phase 6: Check status instead of metadata
                if order.status == DbOrderStatus.FAILED:  # Merged: FAILED + RETRY_PENDING
                    # Normalize symbol for comparison
                    order_symbol = order.symbol.upper().strip()
                    if "-" in order_symbol:
                        order_symbol = order_symbol.split("-")[0].strip()
                    symbol_normalized = symbol.upper().strip()
                    if "-" in symbol_normalized:
                        symbol_normalized = symbol_normalized.split("-")[0].strip()

                    if order_symbol == symbol_normalized:
                        # Phase 6: Mark as closed instead of removing (keep record)
                        try:
                            retry_count = order.retry_count or 0
                            self.orders_repo.mark_cancelled(
                                order=order, cancelled_reason="Removed from retry queue"
                            )
                            logger.debug(f"Removed failed order for {symbol} from retry queue")
                            # Phase 9: Send notification for retry queue removal
                            if self.telegram_notifier and self.telegram_notifier.enabled:
                                try:
                                    self.telegram_notifier.notify_retry_queue_updated(
                                        symbol=symbol,
                                        action="removed",
                                        retry_count=retry_count,
                                        user_id=self.user_id,
                                    )
                                except Exception as notify_error:
                                    logger.warning(
                                        f"Failed to send retry queue removal notification: {notify_error}"
                                    )
                        except Exception as e:
                            logger.warning(f"Failed to remove failed order {symbol}: {e}")
                        break
        # Fallback to file-based storage
        elif self.history_path:
            remove_failed_order(self.history_path, symbol)

    # ---------------------- Utilities ----------------------
    @staticmethod
    def parse_symbol_for_broker(ticker: str) -> str:
        # Convert 'RELIANCE.NS' -> 'RELIANCE'
        return ticker.replace(".NS", "").upper()

    @staticmethod
    def is_trading_weekday(d: date | None = None) -> bool:
        d = d or datetime.now().date()
        return d.weekday() in config.MARKET_DAYS

    def _get_order_variety_for_market_hours(self) -> str:
        """
        Determine order variety based on market hours.

        Returns:
            "REGULAR" if market is open, otherwise uses configured default (typically "AMO")
        """
        from core.volume_analysis import is_market_hours

        if is_market_hours():
            return "REGULAR"
        else:
            # Use configured default (typically AMO for after-market orders)
            return (
                self.strategy_config.default_variety
                if hasattr(self, "strategy_config")
                else config.DEFAULT_VARIETY
            )

    def market_was_open_today() -> bool:
        # Try NIFTY 50 index to detect trading day
        try:
            # Use PriceService for fetching NIFTY data
            price_service = get_price_service(enable_caching=True)
            df = price_service.get_price("^NSEI", days=5, interval="1d", add_current_day=True)
            if df is None or df.empty:
                return False
            latest = df["date"].iloc[-1].date()
            return latest == datetime.now().date()
        except Exception:
            # If detection fails, fallback to weekday check only
            return AutoTradeEngine.is_trading_weekday()

    @staticmethod
    def load_latest_recommendations_from_csv(csv_path: str) -> list[Recommendation]:
        import pandas as pd

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"Failed to read recommendations CSV {csv_path}: {e}")
            return []
        # If CSV already has post-scored fields, use them
        if "final_verdict" in df.columns:
            from . import config as _cfg

            verdict_col = "final_verdict"
            # Apply combined_score threshold if present (default from config)
            if "combined_score" in df.columns:
                th = getattr(_cfg, "MIN_COMBINED_SCORE", 25)
                df_buy = df[
                    df[verdict_col].astype(str).str.lower().isin(["buy", "strong_buy"])
                    & (df["combined_score"].fillna(0) >= th)
                    & (df.get("status", "success") == "success")
                ]
            else:
                df_buy = df[df[verdict_col].astype(str).str.lower().isin(["buy", "strong_buy"])]
            recs = []
            for _, row in df_buy.iterrows():
                ticker = str(row.get("ticker", "")).strip().upper()

                # Exclude ETFs (Exchange Traded Funds) - they behave differently from stocks
                # and may not be suitable for mean reversion strategies
                if "ETF" in ticker:
                    logger.debug(
                        f"Skipping {ticker}: ETF excluded from trading (mean reversion strategy)"
                    )
                    continue

                last_close = float(row.get("last_close", 0) or 0)
                # Phase 11: Load execution_capital from CSV if available
                execution_capital = row.get("execution_capital")
                if execution_capital is not None:
                    try:
                        execution_capital = (
                            float(execution_capital) if execution_capital != "" else None
                        )
                    except (ValueError, TypeError):
                        execution_capital = None
                # Load priority_score from CSV if available (for sorting)
                priority_score = row.get("priority_score")
                if priority_score is not None:
                    try:
                        priority_score = float(priority_score) if priority_score != "" else None
                    except (ValueError, TypeError):
                        priority_score = None
                    else:
                        # Fallback to combined_score if priority_score not available
                        combined_score = row.get("combined_score")
                        if combined_score is not None:
                            try:
                                priority_score = (
                                    float(combined_score) if combined_score != "" else None
                                )
                            except (ValueError, TypeError):
                                priority_score = None
                        else:
                            priority_score = None

                # ML Confidence Boost: When ML is enabled, boost priority_score based on ML confidence
                # This ensures high-confidence ML predictions get prioritized even if technical scores are lower
                ml_confidence = row.get("ml_confidence")
                if ml_confidence is not None and priority_score is not None:
                    try:
                        ml_confidence = float(ml_confidence) if ml_confidence != "" else None
                        if ml_confidence is not None and ml_confidence > 0:
                            # Boost priority based on ML confidence bands:
                            # - High confidence (>=70%): +20 points (strong ML conviction)
                            # - Medium confidence (60-70%): +10 points (good ML conviction)
                            # - Low confidence (50-60%): +5 points (moderate ML conviction)
                            if ml_confidence >= 0.70:
                                priority_score += 20  # High ML confidence boost
                            elif ml_confidence >= 0.60:
                                priority_score += 10  # Medium ML confidence boost
                            elif ml_confidence >= 0.50:
                                priority_score += 5  # Low ML confidence boost
                            # ML confidence < 50%: No boost (below threshold)
                    except (ValueError, TypeError):
                        pass  # Ignore ML confidence if invalid

                recs.append(
                    Recommendation(
                        ticker=ticker,
                        verdict=row[verdict_col],
                        last_close=last_close,
                        execution_capital=execution_capital,
                        priority_score=priority_score,
                    )
                )
            # Sort by priority_score (descending) - higher priority stocks placed first
            recs.sort(key=lambda r: r.priority_score or 0.0, reverse=True)
            logger.info(
                f"Loaded {len(recs)} BUY recommendations from {csv_path} (sorted by priority_score)"
            )
            return recs
        # Otherwise, DO NOT recompute; trust the CSV that trade_agent produced
        if "verdict" in df.columns:
            df_buy = df[df["verdict"].astype(str).str.lower().isin(["buy", "strong_buy"])]
            recs = []
            for _, row in df_buy.iterrows():
                ticker = str(row.get("ticker", "")).strip().upper()

                # Exclude ETFs (Exchange Traded Funds) - they behave differently from stocks
                # and may not be suitable for mean reversion strategies
                if "ETF" in ticker:
                    logger.debug(
                        f"Skipping {ticker}: ETF excluded from trading (mean reversion strategy)"
                    )
                    continue

                last_close = float(row.get("last_close", 0) or 0)
                # Phase 11: Load execution_capital from CSV if available
                execution_capital = row.get("execution_capital")
                if execution_capital is not None:
                    try:
                        execution_capital = (
                            float(execution_capital) if execution_capital != "" else None
                        )
                    except (ValueError, TypeError):
                        execution_capital = None
                # Load priority_score from CSV if available (for sorting)
                priority_score = row.get("priority_score")
                if priority_score is not None:
                    try:
                        priority_score = float(priority_score) if priority_score != "" else None
                    except (ValueError, TypeError):
                        priority_score = None
                else:
                    # Fallback to combined_score if priority_score not available
                    combined_score = row.get("combined_score")
                    if combined_score is not None:
                        try:
                            priority_score = float(combined_score) if combined_score != "" else None
                        except (ValueError, TypeError):
                            priority_score = None
                    else:
                        priority_score = None

                # ML Confidence Boost: When ML is enabled, boost priority_score based on ML confidence
                # This ensures high-confidence ML predictions get prioritized even if technical scores are lower
                ml_confidence = row.get("ml_confidence")
                if ml_confidence is not None and priority_score is not None:
                    try:
                        ml_confidence = float(ml_confidence) if ml_confidence != "" else None
                        if ml_confidence is not None and ml_confidence > 0:
                            # Boost priority based on ML confidence bands:
                            # - High confidence (>=70%): +20 points (strong ML conviction)
                            # - Medium confidence (60-70%): +10 points (good ML conviction)
                            # - Low confidence (50-60%): +5 points (moderate ML conviction)
                            if ml_confidence >= 0.70:
                                priority_score += 20  # High ML confidence boost
                            elif ml_confidence >= 0.60:
                                priority_score += 10  # Medium ML confidence boost
                            elif ml_confidence >= 0.50:
                                priority_score += 5  # Low ML confidence boost
                            # ML confidence < 50%: No boost (below threshold)
                    except (ValueError, TypeError):
                        pass  # Ignore ML confidence if invalid

                recs.append(
                    Recommendation(
                        ticker=ticker,
                        verdict=str(row.get("verdict", "")).lower(),
                        last_close=last_close,
                        execution_capital=execution_capital,
                        priority_score=priority_score,
                    )
                )
            # Sort by priority_score (descending) - higher priority stocks placed first
            recs.sort(key=lambda r: r.priority_score or 0.0, reverse=True)
            logger.info(
                f"Loaded {len(recs)} BUY recommendations from {csv_path} (raw verdicts, sorted by priority_score)"
            )
            return recs
        logger.warning(
            f"CSV {csv_path} missing 'final_verdict' and 'verdict' columns; no recommendations loaded"
        )
        return []

    def load_latest_recommendations(self) -> list[Recommendation]:
        # Priority 1: If a custom CSV path is set (from runner), use it (for backward compatibility)
        if hasattr(self, "_custom_csv_path") and self._custom_csv_path:
            return self.load_latest_recommendations_from_csv(self._custom_csv_path)

        # Priority 2: If database session is available, load from Signals table (unified source)
        if self.db and self.user_id:
            try:
                from src.infrastructure.db.models import SignalStatus  # noqa: PLC0415
                from src.infrastructure.db.timezone_utils import ist_now  # noqa: PLC0415
                from src.infrastructure.persistence.signals_repository import (  # noqa: PLC0415
                    SignalsRepository,
                )

                signals_repo = SignalsRepository(self.db, user_id=self.user_id)

                # Mark time-expired signals before loading to ensure database consistency
                # This prevents trading on expired signals
                signals_repo.mark_time_expired_signals()

                # Get latest signals (today's or most recent)
                today = ist_now().date()
                signals = signals_repo.by_date(today, limit=500)

                # If no signals for today, get recent ones
                if not signals:
                    signals = signals_repo.recent(limit=500)

                if not signals:
                    logger.warning("No signals found in database, falling back to CSV")
                    # Fall through to CSV fallback
                else:
                    logger.info(f"Loaded {len(signals)} signals from database (Signals table)")

                    # PERFORMANCE FIX: Batch load user signal statuses to avoid N+1 query problem
                    # Load all user signal statuses in a single query instead of one per signal
                    signal_ids = [signal.id for signal in signals]
                    user_statuses_dict = {}
                    if signal_ids:
                        from sqlalchemy import select

                        from src.infrastructure.db.models import UserSignalStatus

                        user_statuses = self.db.execute(
                            select(UserSignalStatus.signal_id, UserSignalStatus.status).where(
                                UserSignalStatus.user_id == self.user_id,
                                UserSignalStatus.signal_id.in_(signal_ids),
                            )
                        ).all()
                        user_statuses_dict = {
                            signal_id: status for signal_id, status in user_statuses
                        }

                    # Filter signals by effective status (considering per-user status)
                    # Only include ACTIVE signals - skip TRADED, REJECTED, and EXPIRED
                    active_signals = []
                    for signal in signals:
                        # Get effective status (user-specific if exists, otherwise base status)
                        # IMPORTANT: EXPIRED base status cannot be overridden by user status
                        # However, TRADED/REJECTED user status takes precedence over EXPIRED base status
                        # (from our recent fix - user actions are preserved even when base expires)
                        user_status = user_statuses_dict.get(signal.id)

                        # Determine effective status:
                        # 1. If user has TRADED, REJECTED, or FAILED override, use that (completed actions take precedence)
                        # 2. If base signal is EXPIRED and no user override, effective_status is EXPIRED
                        # 3. Otherwise, use user status if exists, otherwise use base signal status
                        if user_status in [
                            SignalStatus.TRADED,
                            SignalStatus.REJECTED,
                            SignalStatus.FAILED,
                        ]:
                            # User has completed an action (TRADED/REJECTED/FAILED) - this takes precedence
                            effective_status = user_status
                        elif signal.status == SignalStatus.EXPIRED:
                            # Base signal is EXPIRED and no user action - cannot be overridden with ACTIVE
                            effective_status = SignalStatus.EXPIRED
                        else:
                            # Use user status if exists, otherwise use base signal status
                            effective_status = (
                                user_status if user_status is not None else signal.status
                            )

                        # Only include ACTIVE signals
                        if effective_status != SignalStatus.ACTIVE:
                            user_status_str = user_status.value if user_status else "none"
                            logger.debug(
                                f"Skipping signal {signal.symbol}: "
                                f"status={effective_status.value} "
                                f"(base={signal.status.value}, user={user_status_str})"
                            )
                            continue

                        active_signals.append(signal)

                    logger.info(
                        f"Filtered to {len(active_signals)} ACTIVE signals "
                        f"(user {self.user_id}, skipped {len(signals) - len(active_signals)} non-ACTIVE)"
                    )

                    if not active_signals:
                        logger.warning(
                            "No ACTIVE signals found after filtering, falling back to CSV"
                        )
                        # Fall through to CSV fallback
                    else:
                        # Convert Signals to Recommendation objects
                        recommendations = []
                        for signal in active_signals:
                            # Determine verdict (prioritize final_verdict, then verdict, then ml_verdict)
                            verdict = None
                            if signal.final_verdict and signal.final_verdict.lower() in [
                                "buy",
                                "strong_buy",
                            ]:
                                verdict = signal.final_verdict.lower()
                            elif signal.verdict and signal.verdict.lower() in ["buy", "strong_buy"]:
                                verdict = signal.verdict.lower()
                            elif signal.ml_verdict and signal.ml_verdict.lower() in [
                                "buy",
                                "strong_buy",
                            ]:
                                verdict = signal.ml_verdict.lower()

                            # Only include buy/strong_buy signals
                            if not verdict:
                                continue

                            # Convert symbol to ticker format (add .NS if not present)
                            ticker = signal.symbol.upper()

                            # Exclude ETFs (Exchange Traded Funds) - they behave differently from stocks
                            # and may not be suitable for mean reversion strategies
                            if "ETF" in ticker:
                                logger.debug(
                                    f"Skipping {ticker}: ETF excluded from trading (mean reversion strategy)"
                                )
                                continue

                            if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
                                ticker = f"{ticker}.NS"

                            # Get last_close price
                            last_close = signal.last_close or 0.0
                            if last_close <= 0:
                                logger.warning(
                                    f"Skipping {ticker}: invalid last_close ({last_close})"
                                )
                                continue

                            # Extract execution_capital from liquidity_recommendation or trading_params
                            execution_capital = None
                            if signal.liquidity_recommendation and isinstance(
                                signal.liquidity_recommendation, dict
                            ):
                                execution_capital = signal.liquidity_recommendation.get(
                                    "execution_capital"
                                )
                            elif signal.trading_params and isinstance(signal.trading_params, dict):
                                execution_capital = signal.trading_params.get("execution_capital")

                            # Extract priority_score from signal (for sorting)
                            priority_score = signal.priority_score
                            if priority_score is None:
                                # Fallback to combined_score if priority_score not available
                                priority_score = signal.combined_score or 0.0

                            # ML Confidence Boost: When ML is enabled, boost priority_score based on ML confidence
                            # This ensures high-confidence ML predictions get prioritized even if technical scores are lower
                            ml_confidence = signal.ml_confidence
                            if ml_confidence is not None and ml_confidence > 0:
                                # Boost priority based on ML confidence bands:
                                # - High confidence (>=70%): +20 points (strong ML conviction)
                                # - Medium confidence (60-70%): +10 points (good ML conviction)
                                # - Low confidence (50-60%): +5 points (moderate ML conviction)
                                if ml_confidence >= 0.70:
                                    priority_score += 20  # High ML confidence boost
                                elif ml_confidence >= 0.60:
                                    priority_score += 10  # Medium ML confidence boost
                                elif ml_confidence >= 0.50:
                                    priority_score += 5  # Low ML confidence boost
                                # ML confidence < 50%: No boost (below threshold)

                            # Create Recommendation object
                            rec = Recommendation(
                                ticker=ticker,
                                verdict=verdict,
                                last_close=last_close,
                                execution_capital=execution_capital,
                                priority_score=priority_score,
                            )
                            recommendations.append(rec)

                    # Sort by priority_score (descending) - higher priority stocks placed first
                    recommendations.sort(key=lambda r: r.priority_score or 0.0, reverse=True)

                    logger.info(
                        f"Converted {len(recommendations)} buy/strong_buy recommendations from database "
                        f"(sorted by priority_score)"
                    )
                    return recommendations

            except Exception as e:
                logger.warning(
                    f"Failed to load recommendations from database: {e}, falling back to CSV"
                )
                # Fall through to CSV fallback

        # Priority 3: Fallback to CSV files (backward compatibility for standalone usage)
        path = config.ANALYSIS_DIR
        # Prefer post-scored CSV; fallback to base if not present
        patterns = [
            os.path.join(
                path, getattr(config, "RECOMMENDED_CSV_GLOB", "bulk_analysis_final_*.csv")
            ),
            os.path.join(path, "bulk_analysis_*.csv"),
        ]
        files = []
        for pat in patterns:
            files = sorted(glob.glob(pat), key=os.path.getmtime, reverse=True)
            if files:
                break
        if not files:
            logger.warning(f"No recommendation CSV found in {path}")
            return []
        latest = files[0]
        logger.info(f"Loading recommendations from CSV: {latest}")
        return self.load_latest_recommendations_from_csv(latest)

    def _calculate_execution_capital(self, ticker: str, close: float, avg_volume: float) -> float:
        """
        Phase 11: Calculate execution capital based on liquidity using instance's strategy_config.

        Args:
            ticker: Stock ticker (e.g., RELIANCE.NS)
            close: Current close price
            avg_volume: Average daily volume

        Returns:
            Execution capital to use for this trade
        """
        try:
            from services.liquidity_capital_service import LiquidityCapitalService

            liquidity_service = LiquidityCapitalService(config=self.strategy_config)

            capital_data = liquidity_service.calculate_execution_capital(
                avg_volume=avg_volume, stock_price=close
            )
            execution_capital = capital_data.get(
                "execution_capital", self.strategy_config.user_capital
            )

            # Fallback to strategy_config if calculation failed
            if execution_capital <= 0:
                execution_capital = self.strategy_config.user_capital

            return execution_capital
        except Exception as e:
            logger.warning(
                f"Failed to calculate execution capital for {ticker}: {e}, using user_capital from config"
            )
            return self.strategy_config.user_capital

    @staticmethod
    def calculate_execution_capital(ticker: str, close: float, avg_volume: float) -> float:
        """
        Phase 11: Calculate execution capital based on liquidity (static method for backward compatibility).

        Args:
            ticker: Stock ticker (e.g., RELIANCE.NS)
            close: Current close price
            avg_volume: Average daily volume

        Returns:
            Execution capital to use for this trade
        """
        try:
            from config.strategy_config import StrategyConfig
            from services.liquidity_capital_service import LiquidityCapitalService

            # Phase 2.3: Static method uses default config for backward compatibility
            # Instance methods should use _calculate_execution_capital() instead
            strategy_config = StrategyConfig.default()

            liquidity_service = LiquidityCapitalService(config=strategy_config)

            capital_data = liquidity_service.calculate_execution_capital(
                avg_volume=avg_volume, stock_price=close
            )
            execution_capital = capital_data.get("execution_capital", strategy_config.user_capital)

            # Fallback to strategy_config if calculation failed
            if execution_capital <= 0:
                execution_capital = strategy_config.user_capital

            return execution_capital
        except Exception as e:
            logger.warning(
                f"Failed to calculate execution capital for {ticker}: {e}, using default"
            )
            from modules.kotak_neo_auto_trader import config as kotak_config

            return kotak_config.CAPITAL_PER_TRADE

    @staticmethod
    def get_daily_indicators(ticker: str) -> dict[str, Any] | None:
        """
        Static method for backward compatibility.

        Uses IndicatorService directly for calculation.
        For new code, prefer instance method: engine.get_daily_indicators(ticker)

        Args:
            ticker: Stock ticker (e.g., 'RELIANCE.NS')

        Returns:
            Dict with keys: close, rsi10, ema9, ema200, avg_volume
        """
        # Use IndicatorService directly for static calls (backward compatibility)
        try:
            price_service = get_price_service(enable_caching=True)
            indicator_service = get_indicator_service(
                price_service=price_service, enable_caching=True
            )
            from config.strategy_config import StrategyConfig

            strategy_config = StrategyConfig.default()
            return indicator_service.get_daily_indicators_dict(
                ticker=ticker,
                rsi_period=None,
                config=strategy_config,
            )
        except Exception as e:
            logger.warning(f"Failed to get indicators for {ticker}: {e}")
            return None

    @staticmethod
    def check_position_volume_ratio(
        qty: int, avg_volume: float, symbol: str, price: float = 0
    ) -> bool:
        """Check if position size is within acceptable range of daily volume based on stock price."""
        from pathlib import Path
        from sys import path as sys_path

        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys_path:
            sys_path.insert(0, str(project_root))
        from config.settings import POSITION_VOLUME_RATIO_TIERS

        if avg_volume <= 0:
            logger.warning(f"{symbol}: No volume data available")
            return False

        # Determine max ratio based on stock price tier
        max_ratio = 0.20  # Default: 20% for unknown price
        tier_used = "default (20%)"

        if price > 0:
            # Find applicable tier (sorted descending by price threshold)
            for price_threshold, ratio_limit in POSITION_VOLUME_RATIO_TIERS:
                if price >= price_threshold:
                    max_ratio = ratio_limit
                    if price_threshold > 0:
                        tier_used = f"Rs {price_threshold}+ ({ratio_limit:.1%})"
                    else:
                        tier_used = f"<Rs 500 ({ratio_limit:.1%})"
                    break

        ratio = qty / avg_volume
        if ratio > max_ratio:
            logger.warning(
                f"{symbol}: Position too large relative to volume "
                f"(price=Rs {price:.2f}, qty={qty}, avg_vol={int(avg_volume)}, "
                f"ratio={ratio:.1%} > {max_ratio:.1%} for tier {tier_used})"
            )
            return False

        logger.debug(
            f"{symbol}: Volume check passed (ratio={ratio:.2%} of daily volume, tier={tier_used})"
        )
        return True

    def reconcile_holdings_to_history(self) -> None:
        """
        Add holdings to history - ONLY for system-recommended (tracked) symbols.
        Non-tracked symbols are completely ignored.
        Also performs manual trade reconciliation if enabled.
        """
        try:
            if not self.portfolio:
                return

            # Phase 2: Manual trade reconciliation
            if self.manual_matcher and self._enable_telegram:
                try:
                    holdings_response = self.portfolio.get_holdings()
                    if holdings_response and isinstance(holdings_response, dict):
                        holdings = holdings_response.get("data", [])
                        reconciliation = self.manual_matcher.reconcile_holdings_with_tracking(
                            holdings
                        )

                        # Log any discrepancies
                        if reconciliation.get("discrepancies"):
                            summary = self.manual_matcher.get_reconciliation_summary(reconciliation)
                            logger.info(f"\n{summary}")

                            # Send Telegram notifications for manual trades
                            if self.telegram_notifier:
                                for disc in reconciliation.get("discrepancies", []):
                                    symbol = disc.get("symbol")
                                    qty_diff = disc.get("qty_diff", 0)
                                    broker_qty = disc.get("broker_qty", 0)

                                    if disc.get("trade_type") == "MANUAL_BUY":
                                        message_text = (
                                            f"🛒 *Manual Buy Detected*\n\n"
                                            f"Symbol: `{symbol}`\n"
                                            f"Quantity: +{qty_diff} shares\n"
                                            f"New Total: {broker_qty} shares\n\n"
                                            f"Tracking updated automatically"
                                        )
                                        self.telegram_notifier.notify_system_alert(
                                            alert_type="MANUAL_TRADE",
                                            message_text=message_text,
                                            severity="INFO",
                                            user_id=self.user_id,
                                        )

                                    elif disc.get("trade_type") == "MANUAL_SELL":
                                        message_text = (
                                            f"💰 *Manual Sell Detected*\n\n"
                                            f"Symbol: `{symbol}`\n"
                                            f"Quantity: {qty_diff} shares\n"
                                            f"Remaining: {broker_qty} shares\n\n"
                                            f"Tracking updated automatically"
                                        )
                                        self.telegram_notifier.notify_system_alert(
                                            alert_type="MANUAL_TRADE",
                                            message_text=message_text,
                                            severity="INFO",
                                            user_id=self.user_id,
                                        )

                        # Notify about position closures
                        closed_positions = reconciliation.get("closed_positions", [])
                        if closed_positions and self.telegram_notifier:
                            for symbol in closed_positions:
                                self.telegram_notifier.notify_tracking_stopped(
                                    symbol,
                                    "Position fully closed (manual sell detected)",
                                    user_id=self.user_id,
                                )
                except Exception as e:
                    logger.error(f"Manual trade reconciliation error: {e}")

            # Get list of symbols actively tracked by system
            tracked_symbols = get_tracked_symbols(status="active")
            if not tracked_symbols:
                logger.debug("No tracked symbols - skipping reconciliation")
                return

            logger.info(f"Reconciling holdings for {len(tracked_symbols)} tracked symbols")

            hist = self._load_trades_history()
            existing = {
                t.get("symbol") for t in hist.get("trades", []) if t.get("status") == "open"
            }
            h = self.portfolio.get_holdings() or {}

            added = 0
            skipped_not_tracked = 0

            for item in h.get("data") or []:
                sym = str(item.get("tradingSymbol") or "").upper().strip()
                if not sym or sym == "N/A":
                    continue

                base = sym.split("-")[0].strip()
                if not base or not base.isalnum():
                    continue

                # CRITICAL: Only process if this symbol is tracked
                if not is_tracked(base):
                    skipped_not_tracked += 1
                    logger.debug(f"Skipping {base} - not system-recommended")
                    continue

                # Already in history
                if base in (s.split("-")[0] for s in existing if s):
                    continue

                # Add tracked holding to history
                ticker = f"{base}.NS"
                ind = AutoTradeEngine.get_daily_indicators(ticker) or {}
                qty = int(item.get("quantity") or 0)
                entry_price = (
                    item.get("avgPrice") or item.get("price") or item.get("ltp") or ind.get("close")
                )

                trade = {
                    "symbol": base,
                    "placed_symbol": sym,
                    "ticker": ticker,
                    "entry_price": float(entry_price) if entry_price else None,
                    "entry_time": datetime.now().isoformat(),
                    "rsi10": ind.get("rsi10"),
                    "ema9": ind.get("ema9"),
                    "ema200": ind.get("ema200"),
                    "capital": None,
                    "qty": qty,
                    "rsi_entry_level": None,
                    "levels_taken": None,
                    "reset_ready": False,
                    "order_response": None,
                    "status": "open",
                    "entry_type": "system_recommended",
                }
                self._append_trade(trade)
                added += 1
                logger.debug(f"Added tracked holding to history: {base}")

            if added:
                logger.info(
                    f"Reconciled {added} system-recommended holding(s) into history "
                    f"(skipped {skipped_not_tracked} non-tracked holdings)"
                )
            elif skipped_not_tracked > 0:
                logger.info(
                    f"Reconciliation complete: {skipped_not_tracked} non-tracked holdings ignored"
                )

        except Exception as e:
            logger.warning(f"Reconcile holdings failed: {e}")

    # ---------------------- Session ----------------------
    def login(self) -> bool:
        # If already authenticated, skip login but still initialize components
        if self.auth.is_authenticated():
            self.orders = KotakNeoOrders(self.auth)
            self.portfolio = KotakNeoPortfolio(self.auth)

            # Update PortfolioService with portfolio and orders (Phase 2.1)
            self.portfolio_service.portfolio = self.portfolio
            self.portfolio_service.orders = self.orders

            # Update OrderValidationService with portfolio and orders (Phase 3.1)
            self.order_validation_service.portfolio = self.portfolio
            self.order_validation_service.orders = self.orders
            if self.orders_repo:
                self.order_validation_service.orders_repo = self.orders_repo
            if self.user_id:
                self.order_validation_service.user_id = self.user_id

            # Initialize scrip master for symbol resolution
            try:
                rest_client = self.auth.get_rest_client() if hasattr(self.auth, "get_rest_client") else None
                self.scrip_master = KotakNeoScripMaster(auth_client=rest_client)
                if not self.scrip_master.load_scrip_master(force_download=False):
                    raise RuntimeError("Scrip master load failed")
                logger.info("Scrip master loaded for buy order symbol resolution")
            except Exception as e:
                logger.error(
                    f"Failed to load scrip master: {e}. "
                    f"Order placement will fail without scrip master. "
                    f"Please check network connection and try again."
                )
                self.scrip_master = None

            # Phase 2: Initialize modules
            self._initialize_phase2_modules()
            return True

        ok = self.auth.login()
        if ok:
            self.orders = KotakNeoOrders(self.auth)
            self.portfolio = KotakNeoPortfolio(self.auth)

            # Update PortfolioService with portfolio and orders (Phase 2.1)
            self.portfolio_service.portfolio = self.portfolio
            self.portfolio_service.orders = self.orders

            # Update OrderValidationService with portfolio and orders (Phase 3.1)
            self.order_validation_service.portfolio = self.portfolio
            self.order_validation_service.orders = self.orders
            if self.orders_repo:
                self.order_validation_service.orders_repo = self.orders_repo
            if self.user_id:
                self.order_validation_service.user_id = self.user_id

            # Initialize scrip master for symbol resolution
            try:
                rest_client = self.auth.get_rest_client() if hasattr(self.auth, "get_rest_client") else None
                self.scrip_master = KotakNeoScripMaster(auth_client=rest_client)
                if not self.scrip_master.load_scrip_master(force_download=False):
                    raise RuntimeError("Scrip master load failed")
                logger.info("Scrip master loaded for buy order symbol resolution")
            except Exception as e:
                logger.error(
                    f"Failed to load scrip master: {e}. "
                    f"Order placement will fail without scrip master. "
                    f"Please check network connection and try again."
                )
                self.scrip_master = None

            # Phase 2: Initialize modules
            self._initialize_phase2_modules()
        return ok

    def _initialize_phase2_modules(self) -> None:
        """Initialize Phase 2 modules (verifier, telegram, etc.)."""
        try:
            # 1. Initialize Telegram Notifier
            if self._enable_telegram:
                # Phase 3: Create user-specific TelegramNotifier with user credentials
                self.telegram_notifier = self._get_telegram_notifier()
                if self.telegram_notifier:
                    logger.info(
                        f"Telegram notifier initialized (enabled: {self.telegram_notifier.enabled})"
                    )
                else:
                    logger.info(
                        "Telegram notifier not available (user preferences or credentials missing)"
                    )

            # 2. Initialize Manual Order Matcher
            self.manual_matcher = get_manual_order_matcher()
            logger.info("Manual order matcher initialized")

            # 3. Initialize Order Status Verifier with callbacks
            if self._enable_verifier:

                def on_rejection(symbol: str, order_id: str, reason: str):
                    """Callback when order is rejected."""
                    logger.warning(f"Order rejected: {symbol} ({order_id}) - {reason}")
                    if self.telegram_notifier and self.telegram_notifier.enabled:
                        # Get quantity from pending orders
                        tracker = get_order_tracker()
                        pending_order = tracker.get_order_by_id(order_id)
                        qty = pending_order.get("qty", 0) if pending_order else 0
                        # Phase 3: Pass user_id for preference checking
                        self.telegram_notifier.notify_order_rejection(
                            symbol, order_id, qty, reason, user_id=self.user_id
                        )

                def on_execution(symbol: str, order_id: str, qty: int):
                    """Callback when order is executed."""
                    logger.info(f"Order executed: {symbol} ({order_id}) - {qty} shares")
                    if self.telegram_notifier and self.telegram_notifier.enabled:
                        # Phase 3: Pass user_id for preference checking
                        self.telegram_notifier.notify_order_execution(
                            symbol, order_id, qty, user_id=self.user_id
                        )

                self.order_verifier = get_order_status_verifier(
                    broker_client=self.orders,
                    check_interval_seconds=self._verifier_interval,
                    on_rejection_callback=on_rejection,
                    on_execution_callback=on_execution,
                )

                # Start verifier in background
                self.order_verifier.start()
                logger.info(
                    f"Order status verifier started (check interval: {self._verifier_interval}s)"
                )

            # 4. Initialize EOD Cleanup (but don't schedule yet - done in run())
            if self._enable_eod_cleanup:
                self.eod_cleanup = get_eod_cleanup(
                    broker_client=self.portfolio,  # Use portfolio for holdings access
                    order_verifier=self.order_verifier,
                    manual_matcher=self.manual_matcher,
                    telegram_notifier=self.telegram_notifier,
                    user_id=self.user_id,
                )
                logger.info("EOD cleanup initialized")

            logger.info("[OK] Phase 2 modules initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Phase 2 modules: {e}", exc_info=True)
            logger.warning("Continuing without Phase 2 features")

    def monitor_positions(
        self, live_price_manager=None
    ) -> dict[
        str, Any
    ]:  # Deprecated: Position monitoring removed, exit in sell monitor, re-entry in buy order service
        """
        Monitor all open positions for reentry/exit signals.

        Args:
            live_price_manager: Optional shared LivePriceCache/LivePriceManager instance
                               to avoid duplicate auth sessions and WebSocket connections

        Returns:
            Dict with monitoring results
        """
        try:
            from .position_monitor import PositionMonitor, get_telegram_notifier

            # Use direct instantiation to pass shared live_price_manager
            # This avoids creating duplicate auth sessions and WebSocket connections
            telegram = get_telegram_notifier() if self._enable_telegram else None

            monitor = PositionMonitor(
                history_path=self.history_path,
                telegram_notifier=telegram,
                enable_alerts=self._enable_telegram,
                live_price_manager=live_price_manager,  # Pass shared instance
                enable_realtime_prices=True,
            )

            # Run monitoring
            results = monitor.monitor_all_positions()

            return results

        except Exception as e:
            logger.error(f"Position monitoring failed: {e}")
            import traceback

            traceback.print_exc()
            return {
                "monitored": 0,
                "alerts_sent": 0,
                "exit_imminent": 0,
                "averaging_opportunities": 0,
            }

    def logout(self):
        # Phase 2: Stop verifier before logout
        if self.order_verifier and self.order_verifier.is_running():
            logger.info("Stopping order status verifier...")
            self.order_verifier.stop()

        self.auth.logout()

    # ---------------------- Portfolio helpers ----------------------
    def _response_requires_2fa(self, resp) -> bool:
        try:
            s = str(resp)
            return "2fa" in s.lower() or "complete the 2fa" in s.lower()
        except Exception:
            return False

    def _fetch_holdings_symbols(self) -> list[str]:
        symbols = set()
        if not self.portfolio:
            return []
        # First attempt
        h = self.portfolio.get_holdings()
        # If 2FA gating detected, force re-login and retry once
        if self._response_requires_2fa(h) and hasattr(self.auth, "force_relogin"):
            try:
                if self.auth.force_relogin():
                    h = self.portfolio.get_holdings()
            except Exception:
                pass
        data = (h or {}).get("data") if isinstance(h, dict) else None
        for item in data or []:
            sym = str(item.get("tradingSymbol") or "").upper()
            if sym:
                symbols.add(sym)
        return sorted(symbols)

    def current_symbols_in_portfolio(self) -> list[str]:
        """
        Get list of symbols currently in portfolio.

        .. deprecated:: Phase 2.1
           Use :meth:`portfolio_service.get_current_positions` instead.
           This method is kept for backward compatibility and delegates to PortfolioService.
           Will be removed in a future version.

        Returns:
            List of symbols currently in portfolio (includes pending buy orders by default)
        """
        import warnings

        warnings.warn(
            "current_symbols_in_portfolio() is deprecated. "
            "Use portfolio_service.get_current_positions() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Update portfolio_service with current portfolio/orders if available
        if self.portfolio and self.portfolio_service.portfolio != self.portfolio:
            self.portfolio_service.portfolio = self.portfolio
        if self.orders and self.portfolio_service.orders != self.orders:
            self.portfolio_service.orders = self.orders

        return self.portfolio_service.get_current_positions(include_pending=True)

    def portfolio_size(self) -> int:
        """
        Get current portfolio size.

        .. deprecated:: Phase 2.1
           Use :meth:`portfolio_service.get_portfolio_count` instead.
           This method is kept for backward compatibility and delegates to PortfolioService.
           Will be removed in a future version.

        Returns:
            Current portfolio size (includes pending buy orders by default)
        """
        import warnings

        warnings.warn(
            "portfolio_size() is deprecated. Use portfolio_service.get_portfolio_count() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Update portfolio_service with current portfolio/orders if available
        if self.portfolio and self.portfolio_service.portfolio != self.portfolio:
            self.portfolio_service.portfolio = self.portfolio
        if self.orders and self.portfolio_service.orders != self.orders:
            self.portfolio_service.orders = self.orders

        return self.portfolio_service.get_portfolio_count(include_pending=True)

    def get_affordable_qty(self, price: float) -> int:
        """Return maximum whole quantity affordable from available cash/margin."""
        if not self.portfolio or not price or price <= 0:
            return 0
        lim = self.portfolio.get_limits() or {}
        avail, used_key = self._extract_available_cash_from_limits(lim)
        logger.debug(
            f"Available balance: Rs {avail:.2f} (from limits API; key={used_key or 'n/a'})"
        )
        try:
            from math import floor

            return max(0, floor(avail / float(price)))
        except Exception:
            return 0

    def get_available_cash(self) -> float:
        """Return available funds from limits with robust field fallbacks."""
        if not self.portfolio:
            return 0.0
        lim = self.portfolio.get_limits() or {}
        avail, used_key = self._extract_available_cash_from_limits(lim)
        logger.debug(f"Available cash from limits API: Rs {avail:.2f} (key={used_key or 'n/a'})")
        return float(avail)

    def _check_order_margin(
        self, symbol: str, price: float, qty: int, transaction_type: str = "B", product: str = "CNC"
    ) -> tuple[bool, float, float, float, bool]:
        """
        Validate order funds using Kotak check-margin API.

        Returns:
            (has_sufficient, available_cash, required_margin, shortfall, margin_api_ok)
        """
        required_cash = max(0.0, float(price) * float(qty))

        try:
            if not self.auth or not hasattr(self.auth, "get_rest_client"):
                raise RuntimeError("REST client unavailable")
            rest = self.auth.get_rest_client()
            if not rest:
                raise RuntimeError("REST client unavailable")

            token = None
            if self.scrip_master:
                # Prefer exact symbol first (e.g., RELIANCE-EQ), then base symbol.
                token = self.scrip_master.get_token(symbol, exchange="NSE")
                if not token and "-" in symbol:
                    token = self.scrip_master.get_token(symbol.split("-")[0], exchange="NSE")
            if not token:
                raise RuntimeError(f"instrument token unavailable for {symbol}")

            ex_seg = "nse_cm"
            prc_tp = "MKT" if float(price) <= 0 else "L"
            jdata = {
                "brkName": "KOTAK",
                "brnchId": "ONLINE",
                "exSeg": ex_seg,
                "prc": str(0 if prc_tp == "MKT" else float(price)),
                "prcTp": prc_tp,
                "prod": product,
                "qty": str(int(qty)),
                "tok": str(token),
                "trnsTp": "B" if str(transaction_type).upper().startswith("B") else "S",
            }

            resp = rest.check_margin(jdata) or {}
            if not isinstance(resp, dict):
                raise RuntimeError(f"invalid check-margin response type: {type(resp)}")

            def _to_num(v: Any, default: float = 0.0) -> float:
                try:
                    if v is None:
                        return default
                    return float(str(v).replace(",", "").strip())
                except Exception:
                    return default

            # Kotak payloads can be either flat or wrapped under `data`
            # (dict/list). Parse both envelope and data-body fields.
            body: dict[str, Any] = resp
            data_node = resp.get("data")
            if isinstance(data_node, dict):
                body = data_node
            elif isinstance(data_node, list) and data_node and isinstance(data_node[0], dict):
                body = data_node[0]

            def _first(*keys: str, source: dict[str, Any]) -> Any:
                for key in keys:
                    if key in source and source.get(key) is not None:
                        return source.get(key)
                return None

            avl_raw = _first(
                "avlCash",
                "availableCash",
                "cash",
                "netCash",
                source=body,
            )
            if avl_raw is None:
                avl_raw = _first(
                    "avlCash",
                    "availableCash",
                    "cash",
                    "netCash",
                    source=resp,
                )

            req_raw = _first(
                "reqdMrgn",
                "requiredMargin",
                "reqMargin",
                "ordMrgn",
                source=body,
            )
            if req_raw is None:
                req_raw = _first(
                    "reqdMrgn",
                    "requiredMargin",
                    "reqMargin",
                    "ordMrgn",
                    source=resp,
                )

            insuf_raw = _first(
                "insufFund",
                "insufficientFund",
                "shortfall",
                source=body,
            )
            if insuf_raw is None:
                insuf_raw = _first(
                    "insufFund",
                    "insufficientFund",
                    "shortfall",
                    source=resp,
                )

            rms_raw = _first("rmsVldtd", "rmsValidated", source=body)
            if rms_raw is None:
                rms_raw = _first("rmsVldtd", "rmsValidated", source=resp)

            stat_raw = _first("stat", "status", source=resp)
            if stat_raw is None:
                stat_raw = _first("stat", "status", source=body)

            stcode_raw = _first("stCode", "statusCode", "code", source=resp)
            if stcode_raw is None:
                stcode_raw = _first("stCode", "statusCode", "code", source=body)

            avl_cash = _to_num(avl_raw, 0.0)
            req_margin = _to_num(req_raw, required_cash)
            insuf_fund = _to_num(insuf_raw, max(0.0, req_margin - avl_cash))
            rms_valid = str(rms_raw or "").upper().strip()
            stat_ok = str(stat_raw or "").lower().strip() in {"ok", "success", "true"}
            stcode = str(stcode_raw or "").strip()
            has_sufficient = bool(
                stat_ok
                and stcode in {"200", "0", ""}
                and (rms_valid == "OK" or insuf_fund <= 0.0 or avl_cash >= req_margin)
            )
            margin_api_ok = bool(stat_ok and stcode in {"200", "0", ""})
            shortfall = max(0.0, insuf_fund if insuf_fund > 0 else (req_margin - avl_cash))
            logger.debug(
                f"check-margin {symbol}: sufficient={has_sufficient}, avlCash={avl_cash:.2f}, "
                f"reqdMrgn={req_margin:.2f}, insufFund={shortfall:.2f}, rmsVldtd={rms_valid or 'n/a'}"
            )
            return has_sufficient, avl_cash, req_margin, shortfall, margin_api_ok
        except Exception as e:
            # Hard-fail policy: if check-margin is unavailable/invalid, do not place order.
            logger.error(f"check-margin failed for {symbol}: {e}")
            return False, 0.0, required_cash, required_cash, False

    def _extract_available_cash_from_limits(self, limits_payload: Any) -> tuple[float, str | None]:
        """Parse available cash from nested/flat limits payloads."""
        if not isinstance(limits_payload, dict):
            return 0.0, None

        candidates = [
            "cash",
            "availableCash",
            "available_cash",
            "availableBalance",
            "available_balance",
            "available_bal",
            "fundsAvailable",
            "funds_available",
            "fundAvailable",
            "marginAvailable",
            "margin_available",
            "availableMargin",
            "Net",
            "net",
        ]

        def _to_num(raw: Any) -> float | None:
            try:
                if raw is None:
                    return None
                # Support Money-like objects
                if hasattr(raw, "amount"):
                    raw = getattr(raw, "amount")
                if isinstance(raw, str):
                    s = raw.replace(",", "").strip()
                    if s.lower().startswith("rs"):
                        s = s[2:].strip(" .:")
                    if not s:
                        return None
                    return float(s)
                return float(raw)
            except Exception:
                return None

        payloads: list[tuple[str, dict[str, Any]]] = []
        data = limits_payload.get("data")
        if isinstance(data, dict):
            payloads.append(("data.", data))
        payloads.append(("", limits_payload))

        for prefix, payload in payloads:
            for key in candidates:
                value = _to_num(payload.get(key))
                if value is not None and value > 0:
                    return value, f"{prefix}{key}"

            nums: list[float] = []
            for value in payload.values():
                num = _to_num(value)
                if num is not None:
                    nums.append(num)
            if nums:
                return max(nums), f"{prefix}max_numeric_field"

        return 0.0, None

    # ---------------------- De-dup helpers ----------------------
    @staticmethod
    def _symbol_variants(base: str) -> list[str]:
        base = base.upper()
        return [base, f"{base}-EQ", f"{base}-BE", f"{base}-BL", f"{base}-BZ"]

    def has_holding(self, base_symbol: str) -> bool:
        """
        Check if symbol is in holdings.

        .. deprecated:: Phase 2.1
           Use :meth:`portfolio_service.has_position` instead.
           This method is kept for backward compatibility and delegates to PortfolioService.
           Will be removed in a future version.

        Args:
            base_symbol: Base symbol to check (e.g., 'RELIANCE')

        Returns:
            True if symbol is in holdings, False otherwise
        """
        import warnings

        warnings.warn(
            f"has_holding() is deprecated. "
            f"Use portfolio_service.has_position('{base_symbol}') instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Update portfolio_service with current portfolio/orders if available
        if self.portfolio and self.portfolio_service.portfolio != self.portfolio:
            self.portfolio_service.portfolio = self.portfolio
        if self.orders and self.portfolio_service.orders != self.orders:
            self.portfolio_service.orders = self.orders

        return self.portfolio_service.has_position(base_symbol)

    def has_active_buy_order(self, base_symbol: str) -> bool:
        """
        Check if there's an active buy order for the given symbol.
        First checks broker API, then falls back to database check.
        This prevents duplicate orders when broker API doesn't return pending orders.
        """
        variants = set(self._symbol_variants(base_symbol))

        # 1) Check broker API first (primary source)
        if self.orders:
            try:
                pend = self.orders.get_pending_orders() or []
                for o in pend:
                    txn = str(o.get("transactionType") or "").upper()
                    sym = str(o.get("tradingSymbol") or "").upper()
                    if txn.startswith("B") and sym in variants:
                        return True
            except Exception as e:
                logger.warning(
                    f"Broker API check for active buy order failed for {base_symbol}: {e}. "
                    "Falling back to database check."
                )

        # 2) Database fallback: Check for PENDING/ONGOING/CLOSED buy orders (AMO/PENDING_EXECUTION merged into PENDING)
        # This prevents duplicates when broker API doesn't return pending orders or is unavailable
        if self.orders_repo and self.user_id:
            try:
                existing_orders, _ = self.orders_repo.list(self.user_id)
                for existing_order in existing_orders:
                    # Check if symbol matches (including variants)
                    order_symbol_base = (
                        existing_order.symbol.upper()
                        .replace("-EQ", "")
                        .replace("-BE", "")
                        .replace("-BL", "")
                        .replace("-BZ", "")
                    )
                    base_symbol_clean = (
                        base_symbol.upper()
                        .replace("-EQ", "")
                        .replace("-BE", "")
                        .replace("-BL", "")
                        .replace("-BZ", "")
                    )

                    if (
                        existing_order.side == "buy"
                        and existing_order.status
                        in {
                            DbOrderStatus.PENDING,  # Merged: AMO + PENDING_EXECUTION
                            DbOrderStatus.ONGOING,  # Legacy executed
                            DbOrderStatus.CLOSED,  # Filled (position open; don't block re-entry if filled)
                        }
                        and order_symbol_base == base_symbol_clean
                    ):
                        # Only block re-entry for UNFILLED orders (execution_qty is None)
                        # Filled orders (ONGOING legacy or CLOSED) shouldn't block re-entry
                        if existing_order.execution_qty is None:
                            logger.debug(
                                f"Database check: {base_symbol} already has unfilled buy order "
                                f"(status: {existing_order.status}, order_id: {existing_order.id})"
                            )
                            return True
                        else:
                            logger.debug(
                                f"Database check: {base_symbol} has filled buy order (execution_qty={existing_order.execution_qty}), "
                                f"not blocking re-entry (status: {existing_order.status}, order_id: {existing_order.id})"
                            )
            except Exception as e:
                logger.warning(f"Database check for active buy order failed for {base_symbol}: {e}")

        return False

    def reentries_today(self, base_symbol: str) -> int:
        """
        Count successful re-entries recorded today for this symbol (base symbol).

        Edge Case #11 Fix: Checks the 'reentries' array within trade entries
        instead of looking for separate entries with entry_type == 'reentry'.
        Reentries are stored in the reentries array of existing trade entries.

        Updated: Queries directly from database (Positions table) as the single
        source of truth. JSON file is kept as backup only (write-only for archival).
        """
        try:
            # Database is the single source of truth
            if not self.positions_repo or not self.user_id:
                logger.warning(
                    "Cannot query reentries: positions_repo or user_id not available. "
                    "Returning 0 to prevent incorrect reentry cap checks."
                )
                return 0

            position = self.positions_repo.get_by_symbol(self.user_id, base_symbol)
            if not position or not position.reentries:
                return 0

            # Count reentries from today
            # Fix: Check placed_at date (order placement date) instead of time (execution date)
            # This ensures daily cap is based on when order was placed, not when it executed
            # Example: Order placed Day 1, executes Day 2 → Should count for Day 1, not Day 2
            reentries_raw = position.reentries

            # Handle both old format (list) and new format (dict with metadata)
            if isinstance(reentries_raw, dict):
                # New format: extract reentries array
                reentries = reentries_raw.get("reentries", [])
            elif isinstance(reentries_raw, list):
                # Old format: directly a list
                reentries = reentries_raw
            else:
                # Invalid format
                return 0

            if not isinstance(reentries, list):
                return 0

            today = datetime.now().date()
            cnt = 0
            for reentry in reentries:
                if not isinstance(reentry, dict):
                    continue

                # Priority: Check placed_at first (correct date for daily cap)
                placed_at_str = reentry.get("placed_at")
                placed_at_checked = False
                if placed_at_str:
                    try:
                        # placed_at is stored as ISO date string (YYYY-MM-DD)
                        d = datetime.fromisoformat(placed_at_str).date()
                        placed_at_checked = True  # Successfully parsed placed_at
                        if d == today:
                            cnt += 1
                            continue  # Found match, skip time field check
                        # If placed_at exists and doesn't match today, skip time field (don't fallback)
                        continue
                    except Exception:
                        # If parsing fails, fall through to time field fallback
                        pass

                # Fallback: Use time field (backward compatibility for old re-entries)
                # Only use this if placed_at is missing or parsing failed
                # Old re-entries may not have placed_at field
                if not placed_at_checked:
                    reentry_time = reentry.get("time")
                    if reentry_time:
                        try:
                            # Parse ISO format timestamp
                            d = datetime.fromisoformat(reentry_time).date()
                        except Exception:
                            try:
                                # Fallback: try parsing just the date part
                                d = datetime.strptime(reentry_time.split("T")[0], "%Y-%m-%d").date()
                            except Exception:
                                continue
                        if d == today:
                            cnt += 1
            return cnt
        except Exception as e:
            logger.error(f"Error counting reentries for {base_symbol}: {e}")
            return 0

    def _get_position_cycle_metadata(self, position: Any) -> dict[str, Any]:
        """
        Get cycle metadata from position.

        Returns a dict with:
        - current_cycle: int (default 0)
        - last_rsi_above_30: str | None (ISO timestamp)
        - last_rsi_value: float | None

        Args:
            position: Position object from database

        Returns:
            Dict with cycle metadata
        """
        metadata = {
            "current_cycle": 0,
            "last_rsi_above_30": None,
            "last_rsi_value": None,
        }

        if not position or not position.reentries:
            return metadata

        # Check if reentries is a dict with _cycle_metadata key (new format)
        if isinstance(position.reentries, dict):
            cycle_meta = position.reentries.get("_cycle_metadata")
            if isinstance(cycle_meta, dict):
                metadata["current_cycle"] = cycle_meta.get("current_cycle", 0)
                metadata["last_rsi_above_30"] = cycle_meta.get("last_rsi_above_30")
                metadata["last_rsi_value"] = cycle_meta.get("last_rsi_value")
            return metadata

        # If reentries is a list, metadata might be stored separately
        # For now, we'll extract from the structure
        # In the new format, we'll store metadata in a wrapper dict
        return metadata

    def _set_position_cycle_metadata(
        self,
        position: Any,
        current_cycle: int | None = None,
        last_rsi_above_30: str | None = None,
        last_rsi_value: float | None = None,
    ) -> dict:
        """
        Set cycle metadata in position's reentries structure.

        This creates/updates a wrapper structure:
        {
            "_cycle_metadata": {
                "current_cycle": int,
                "last_rsi_above_30": str | None,
                "last_rsi_value": float | None
            },
            "reentries": [...]
        }

        Args:
            position: Position object from database
            current_cycle: Current cycle number (None to keep existing)
            last_rsi_above_30: ISO timestamp when RSI was last above 30 (None to keep existing)
            last_rsi_value: Last known RSI value (None to keep existing)

        Returns:
            Updated reentries structure (dict with _cycle_metadata and reentries keys)
        """
        # Get existing metadata
        existing_meta = self._get_position_cycle_metadata(position)

        # Get existing reentries array
        existing_reentries = []
        if position.reentries:
            if isinstance(position.reentries, dict):
                # New format: extract reentries array
                existing_reentries = position.reentries.get("reentries", [])
                if not isinstance(existing_reentries, list):
                    existing_reentries = []
            elif isinstance(position.reentries, list):
                # Old format: reentries is directly a list
                existing_reentries = position.reentries

        # Update metadata
        if current_cycle is not None:
            existing_meta["current_cycle"] = current_cycle
        if last_rsi_above_30 is not None:
            existing_meta["last_rsi_above_30"] = last_rsi_above_30
        if last_rsi_value is not None:
            existing_meta["last_rsi_value"] = last_rsi_value

        # Return wrapper structure
        return {"_cycle_metadata": existing_meta, "reentries": existing_reentries}

    def has_reentry_at_level(self, base_symbol: str, level: int, allow_reset: bool = False) -> bool:
        """
        Check if a re-entry at the specified level already exists in the current cycle.

        Enhanced Hybrid Approach: Now checks by cycle number, not just level.
        This allows re-entries at the same level after a reset (new cycle).

        This includes checking:
        1. Initial entry RSI - if initial entry was at this level, block re-entry at same level
           (Exception: If allow_reset=True, allow it after reset for any level)
        2. Existing re-entries in current cycle - if a re-entry at this level exists in current cycle, block duplicate

        Args:
            base_symbol: Symbol to check
            level: Re-entry level (30, 20, or 10)
            allow_reset: If True, allow re-entry at this level even if initial entry was at this level
                        (This handles the reset case where RSI > 30 then < 30, allowing re-entry at any level)

        Returns:
            True if re-entry at this level already exists in current cycle (including initial entry), False otherwise
        """
        try:
            if not self.positions_repo or not self.user_id:
                return False

            position = self.positions_repo.get_by_symbol(self.user_id, base_symbol)
            if not position:
                return False

            # Get current cycle from metadata
            cycle_meta = self._get_position_cycle_metadata(position)
            current_cycle = cycle_meta.get("current_cycle", 0)

            # Check if initial entry was at this level
            # Exception: If allow_reset=True, skip this check (reset allows re-entry at any level again)
            entry_rsi = position.entry_rsi
            if entry_rsi is not None and not allow_reset:
                # Determine which level the initial entry was at
                if level == 30 and entry_rsi < 30:
                    return True  # Initial entry was at RSI < 30, block re-entry at level 30
                elif level == 20 and entry_rsi < 20:
                    return True  # Initial entry was at RSI < 20, block re-entry at level 20
                elif level == 10 and entry_rsi < 10:
                    return True  # Initial entry was at RSI < 10, block re-entry at level 10

            # Check existing re-entries in current cycle
            if not position.reentries:
                return False

            # Extract reentries array (handle both old and new format)
            reentries = position.reentries
            if isinstance(reentries, dict):
                # New format: extract reentries array
                reentries = reentries.get("reentries", [])
            if not isinstance(reentries, list):
                return False

            for reentry in reentries:
                if not isinstance(reentry, dict):
                    continue

                # Check if level matches
                reentry_level = reentry.get("level")
                if reentry_level is None:
                    continue

                try:
                    # Handle both int and string representations
                    reentry_level_int = int(reentry_level) if reentry_level is not None else None
                    if reentry_level_int == level:
                        # Check cycle number (if stored)
                        reentry_cycle = reentry.get("cycle")
                        if reentry_cycle is not None:
                            # Only block if it's in the same cycle
                            if int(reentry_cycle) == current_cycle:
                                return True
                        # Backward compatibility: if cycle not stored, assume cycle 0
                        # Only block if current_cycle is also 0 (initial cycle)
                        elif current_cycle == 0:
                            return True
                except (ValueError, TypeError):
                    continue

            return False
        except Exception as e:
            logger.error(f"Error checking reentry level for {base_symbol}: {e}")
            return False

    def _resolve_broker_symbol(self, base_symbol: str) -> str:
        """
        Resolve base symbol to actual broker trading symbol using scrip master.

        Scrip master is the SINGLE SOURCE OF TRUTH for symbol resolution.
        If scrip master is not available or symbol is not found, raises an error.

        IMPORTANT: Only resolves to -EQ segment symbols. T2T segments (-BE, -BL, -BZ)
        are rejected as they are not supported for trading.

        Args:
            base_symbol: Base symbol (e.g., "SALSTEEL") or already resolved symbol (e.g., "SALSTEEL-EQ")

        Returns:
            Resolved broker symbol (e.g., "SALSTEEL-EQ") - ONLY -EQ symbols

        Raises:
            ValueError: If scrip master is not available, symbol cannot be resolved,
                       or only T2T segment available (no -EQ variant)
        """
        # Get exchange from user's trading config (from database UserTradingConfig)
        # This is the user's preference stored in their trading configuration
        # Falls back to config.DEFAULT_EXCHANGE only if strategy_config not available (standalone usage)
        exchange = (
            self.strategy_config.default_exchange
            if self.strategy_config
            else config.DEFAULT_EXCHANGE
        )

        # If symbol already has suffix, validate it exists in scrip master
        if any(base_symbol.upper().endswith(suf) for suf in ["-EQ", "-BE", "-BL", "-BZ"]):
            # Reject T2T segments - only -EQ is allowed
            if any(base_symbol.upper().endswith(suf) for suf in ["-BE", "-BL", "-BZ"]):
                raise ValueError(
                    f"Symbol {base_symbol} is a T2T segment stock (-BE/-BL/-BZ) which is not supported. "
                    f"Only -EQ segment stocks are allowed for trading."
                )

            # Validate that -EQ symbol exists in scrip master
            if self.scrip_master and self.scrip_master.symbol_map:
                instrument = self.scrip_master.get_instrument(base_symbol, exchange=exchange)
                if instrument and instrument.get("symbol"):
                    # Symbol exists in scrip master, use as-is
                    logger.debug(
                        f"Symbol {base_symbol} already has -EQ suffix and exists in scrip master ({exchange})"
                    )
                    return base_symbol
                else:
                    # Symbol has suffix but not in scrip master - this is an error
                    raise ValueError(
                        f"Symbol {base_symbol} not found in scrip master ({exchange}). "
                        f"Please verify the symbol is correct."
                    )
            else:
                # Scrip master not available, but symbol has -EQ suffix - assume it's valid
                logger.warning(
                    f"Scrip master not available, but symbol {base_symbol} has -EQ suffix. "
                    f"Using as-is (not validated)."
                )
                return base_symbol

        # Scrip master is REQUIRED for symbol resolution
        if not self.scrip_master or not self.scrip_master.symbol_map:
            raise ValueError(
                f"Scrip master is not available. Cannot resolve symbol {base_symbol}. "
                f"Please ensure scrip master is loaded before placing orders."
            )

        try:
            # First, try to get -EQ variant explicitly
            eq_symbol = f"{base_symbol}-EQ"
            instrument = self.scrip_master.get_instrument(eq_symbol, exchange=exchange)

            if instrument and instrument.get("symbol"):
                resolved = instrument["symbol"]
                # Double-check it's -EQ (safety check)
                if resolved.upper().endswith("-EQ"):
                    logger.info(
                        f"Resolved {base_symbol} -> {resolved} via scrip master ({exchange}) - EQ variant"
                    )
                    return resolved
                else:
                    logger.warning(f"Expected -EQ variant but got {resolved} for {base_symbol}")

            # If -EQ not found, try base symbol (might resolve to something else)
            instrument = self.scrip_master.get_instrument(base_symbol, exchange=exchange)
            if instrument and instrument.get("symbol"):
                resolved = instrument["symbol"]

                # Check if resolved symbol is T2T segment - reject it
                if any(resolved.upper().endswith(suf) for suf in ["-BE", "-BL", "-BZ"]):
                    raise ValueError(
                        f"Symbol {base_symbol} resolves to T2T segment {resolved} which is not supported. "
                        f"Only -EQ segment stocks are allowed for trading. "
                        f"The stock may only be available in T2T segment on {exchange}."
                    )

                # Check if it's -EQ
                if resolved.upper().endswith("-EQ"):
                    logger.info(
                        f"Resolved {base_symbol} -> {resolved} via scrip master ({exchange})"
                    )
                    return resolved
                else:
                    # Resolved to something unexpected
                    raise ValueError(
                        f"Symbol {base_symbol} resolved to unexpected format: {resolved}. "
                        f"Expected -EQ segment symbol."
                    )
            else:
                # Symbol not found in scrip master
                raise ValueError(
                    f"Symbol {base_symbol} not found in scrip master ({exchange}). "
                    f"Please verify the symbol is correct or check if it's listed on {exchange}."
                )
        except ValueError:
            # Re-raise ValueError (our custom errors)
            raise
        except Exception as e:
            # Wrap other exceptions
            raise ValueError(
                f"Failed to resolve symbol {base_symbol} via scrip master: {e}. "
                f"Scrip master is the single source of truth for symbol resolution."
            ) from e

    def _attempt_place_order(
        self,
        broker_symbol: str,
        ticker: str,
        qty: int,
        close: float,
        ind: dict[str, Any],
        recommendation_source: str | None = None,
        entry_type: str | None = None,
        order_metadata: dict | None = None,
    ) -> tuple[bool, str | None]:
        """
        Helper method to attempt placing an order with symbol resolution.

        Args:
            broker_symbol: Trading symbol (should already be resolved, but will resolve if needed)
            ticker: Full ticker (e.g., RELIANCE.NS)
            qty: Order quantity
            close: Current close price
            ind: Market indicators dict
            recommendation_source: Source of recommendation (e.g., CSV file)

        Returns:
            Tuple of (success: bool, order_id: Optional[str])
        """
        resp = None
        placed_symbol = None
        placement_time = datetime.now().isoformat()

        # Determine order variety based on market hours
        # AMO orders should only be used when market is closed
        # During market hours, use REGULAR orders
        from core.volume_analysis import is_market_hours

        if is_market_hours():
            order_variety = "REGULAR"
            logger.debug(f"Market is open - using REGULAR order variety for {broker_symbol}")
        else:
            order_variety = config.DEFAULT_VARIETY  # Default to AMO when market is closed
            logger.debug(
                f"Market is closed - using {order_variety} order variety for {broker_symbol}"
            )

        # Symbol should already be resolved from place_new_entries() via scrip master
        # Scrip master is the SINGLE SOURCE OF TRUTH - use the resolved symbol directly
        # If symbol doesn't have suffix, it means resolution failed earlier - this is an error
        place_symbol = broker_symbol

        # Validate that symbol has suffix (means it was resolved by scrip master)
        # T2T segment stocks (-BE, -BL, -BZ) are filtered out earlier in analysis phase
        has_suffix = place_symbol.upper().endswith("-EQ")
        if not has_suffix:
            logger.error(
                f"Symbol {place_symbol} does not have -EQ suffix. "
                f"This indicates scrip master resolution failed earlier. "
                f"Cannot place order without proper symbol resolution."
            )
            return (False, None)

        # Place order with scrip master resolved symbol (all MARKET orders - T2T support removed)
        trial = self.orders.place_market_buy(
            symbol=place_symbol,
            quantity=qty,
            variety=order_variety,
            exchange=config.DEFAULT_EXCHANGE,
            product=config.DEFAULT_PRODUCT,
        )

        # Check for successful response - Kotak Neo returns stat='Ok' with nOrdNo
        if isinstance(trial, dict) and "error" not in trial:
            stat = trial.get("stat", "").lower()
            if (
                stat == "ok"
                or "data" in trial
                or "order" in trial
                or "raw" in trial
                or "nordno" in str(trial).lower()
            ):
                resp = trial
                placed_symbol = place_symbol

        # Check if order was successful
        # Accept responses with nOrdNo (direct order ID) or data/order/raw structures
        resp_valid = (
            isinstance(resp, dict)
            and (
                "data" in resp
                or "order" in resp
                or "raw" in resp
                or "nOrdNo" in resp
                or "nordno" in str(resp).lower()
            )
            and "error" not in resp
            and "not_ok" not in str(resp).lower()
        )

        if not resp_valid:
            logger.error(f"Order placement failed for {broker_symbol}")
            return (False, None)

        # Extract order ID from response
        order_id = extract_order_id(resp)

        # Use resolved symbol (placed_symbol) everywhere - this is the actual broker format
        # Define early so it can be used throughout
        actual_symbol = placed_symbol or broker_symbol  # Prefer placed_symbol (resolved format)

        if not order_id:
            # Fallback: Search order book after a shorter wait (reduced from 60s to 10s for performance)
            logger.warning(
                f"No order ID in response for {actual_symbol}. "
                f"Will search order book after 10 seconds..."
            )
            order_id = search_order_in_broker_orderbook(
                self.orders,
                actual_symbol,
                qty,
                placement_time,
                max_wait_seconds=10,  # Reduced from 60s to 10s for faster execution
            )

            if not order_id:
                # Still no order ID - uncertain placement
                logger.error(
                    f"Order placement uncertain for {actual_symbol}: "
                    f"No order ID and not found in order book"
                )
                # Send notification about uncertain order
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                telegram_msg = (
                    f"⚠️ *Order Placement Uncertain*\n\n"
                    f"Symbol: `{actual_symbol}`\n"
                    f"Qty: {qty}\n"
                    f"Order ID not received and not found in order book.\n"
                    f"Please check broker app manually.\n\n"
                    f"_Time: {timestamp}_"
                )
                # Use TelegramNotifier to respect notification preferences
                if self.telegram_notifier and self.telegram_notifier.enabled:
                    try:
                        self.telegram_notifier.notify_system_alert(
                            alert_type="ORDER_PLACEMENT_UNCERTAIN",
                            message_text=telegram_msg,
                            severity="WARNING",
                            user_id=self.user_id,
                        )
                    except Exception as notify_err:
                        logger.warning(
                            f"Failed to send order placement uncertain notification: {notify_err}"
                        )
                else:
                    # Fallback to old method if telegram_notifier not available
                    send_telegram(telegram_msg)
                return (False, None)

        # Order successfully placed with order_id
        logger.info(
            f"Order placed successfully: {actual_symbol} (order_id: {order_id}, qty: {qty})"
        )

        # Mark signal as TRADED (Phase 2.3: Database integration)
        if self.db:
            try:
                from src.infrastructure.persistence.signals_repository import (  # noqa: PLC0415
                    SignalsRepository,
                )

                signals_repo = SignalsRepository(self.db, user_id=self.user_id)
                # Try multiple symbol variants to handle stored symbols with/without suffixes (.NS, -EQ)
                base_symbol = actual_symbol.split("-")[0] if "-" in actual_symbol else actual_symbol
                candidates = [base_symbol]
                upper_actual = actual_symbol.upper()
                if upper_actual not in candidates:
                    candidates.append(upper_actual)
                # Add NSE-style ticker if missing
                ticker_variant = (
                    f"{base_symbol}.NS" if not base_symbol.endswith(".NS") else base_symbol
                )
                if ticker_variant not in candidates:
                    candidates.append(ticker_variant)

                marked = False
                for candidate in candidates:
                    try:
                        if signals_repo.mark_as_traded(candidate, user_id=self.user_id):
                            logger.info(
                                f"Marked signal for {candidate} as TRADED (user {self.user_id})"
                            )
                            marked = True
                            break
                    except Exception as inner_mark_error:
                        logger.debug(
                            f"Mark-as-traded attempt failed for {candidate}: {inner_mark_error}"
                        )

                if not marked:
                    logger.warning(f"Could not mark signal as TRADED for any variant: {candidates}")
            except Exception as mark_error:
                # Don't fail order placement if marking fails
                logger.warning(f"Failed to mark signal as traded for {actual_symbol}: {mark_error}")

        order_type = "MARKET"  # All buy orders are MARKET orders (T2T support removed)

        # Phase 9: Send notification for order placed successfully
        if self.telegram_notifier and self.telegram_notifier.enabled:
            try:
                self.telegram_notifier.notify_order_placed(
                    symbol=actual_symbol,  # Use actual resolved symbol format
                    order_id=order_id,
                    quantity=qty,
                    order_type=order_type,
                    price=None,  # MARKET orders don't have prices
                    user_id=self.user_id,
                )
            except Exception as e:
                logger.warning(f"Failed to send order placed notification: {e}")

        # Get pre-existing quantity (if any)
        pre_existing_qty = 0
        try:
            holdings = self.portfolio.get_holdings() or {}
            for item in holdings.get("data") or []:
                sym = str(item.get("tradingSymbol", "")).upper()
                # Check if actual_symbol matches holdings symbol (both should be in broker format)
                if actual_symbol.upper() in sym or sym in actual_symbol.upper():
                    pre_existing_qty = int(item.get("quantity", 0))
                    break
        except Exception as e:
            logger.debug(f"Could not get pre-existing qty: {e}")

        # Register in tracking scope (system-recommended)
        try:
            tracking_id = add_tracked_symbol(
                symbol=actual_symbol,  # Use actual resolved symbol format
                ticker=ticker,
                initial_order_id=order_id,
                initial_qty=qty,
                pre_existing_qty=pre_existing_qty,
                recommendation_source=recommendation_source,
                recommendation_verdict=getattr(ind, "verdict", None),
            )
            logger.debug(f"Added to tracking scope: {actual_symbol} (tracking_id: {tracking_id})")
        except Exception as e:
            logger.error(f"Failed to add to tracking scope: {e}")

        # Add to pending orders for status monitoring
        try:
            add_pending_order(
                order_id=order_id,
                symbol=actual_symbol,  # Use actual resolved symbol format
                ticker=ticker,
                qty=qty,
                order_type=order_type,
                variety=config.DEFAULT_VARIETY,
                price=0.0,  # MARKET orders use price=0
                entry_type=entry_type,
                order_metadata=order_metadata,
            )
            logger.debug(f"Added to pending orders: {order_id}")
        except Exception as e:
            logger.error(f"Failed to add to pending orders: {e}")

        # Immediately fetch order status from broker and sync DB state
        self._sync_order_status_snapshot(
            order_id=str(order_id),
            symbol=actual_symbol,  # Use actual resolved symbol format
            quantity=qty,
        )

        # Phase 5: Immediately verify order placement (non-blocking)
        # This checks if the order was immediately rejected by the broker
        try:
            is_valid, rejection_reason = self._verify_order_placement(
                order_id=order_id, symbol=actual_symbol, wait_seconds=15
            )
            if not is_valid:
                logger.error(
                    f"Order {order_id} was immediately rejected: {rejection_reason}. "
                    f"Order status has been updated in database."
                )
                # Note: Order is still considered "placed" from broker's perspective,
                # but we've detected and logged the rejection
        except Exception as e:
            logger.warning(f"Order verification failed (non-critical): {e}")
            # Don't fail order placement if verification fails

        return (True, order_id)

    def _sync_order_status_snapshot(
        self, order_id: str, symbol: str | None = None, quantity: int | None = None
    ) -> None:
        """
        Immediately fetch the current broker status for a newly placed order and
        mirror it in the orders table.
        """
        if not (self.orders and self.orders_repo and self.user_id):
            return

        try:
            orders_response = self.orders.get_orders() or {}
            broker_orders = (
                orders_response.get("data", []) if isinstance(orders_response, dict) else []
            )
            target = None
            for broker_order in broker_orders:
                if OrderFieldExtractor.get_order_id(broker_order) == str(order_id):
                    target = broker_order
                    break

            if not target:
                return

            db_order = self.orders_repo.get_by_broker_order_id(
                self.user_id, str(order_id)
            ) or self.orders_repo.get_by_order_id(self.user_id, str(order_id))
            if not db_order:
                return

            status = OrderFieldExtractor.get_status(target)
            status_lower = status.lower()
            if not status_lower:
                return

            self.orders_repo.update_status_check(db_order)

            if status_lower in {"rejected", "reject"}:
                rejection_reason = (
                    OrderFieldExtractor.get_rejection_reason(target) or "Rejected by broker"
                )
                self.orders_repo.mark_rejected(db_order, rejection_reason)
            elif status_lower in {"cancelled", "cancel"}:
                cancelled_reason = OrderFieldExtractor.get_rejection_reason(target) or "Cancelled"
                self.orders_repo.mark_cancelled(db_order, cancelled_reason)
            elif status_lower in {"executed", "filled", "complete"}:
                execution_price = OrderFieldExtractor.get_price(target)
                execution_qty = (
                    OrderFieldExtractor.get_quantity(target) or quantity or db_order.quantity
                )
                self.orders_repo.mark_executed(
                    db_order,
                    execution_price=execution_price,
                    execution_qty=execution_qty,
                )
            elif status_lower in {
                "pending",
                "open",
                "trigger_pending",
                "partially_filled",
                "partially filled",
            }:
                if db_order.status != DbOrderStatus.PENDING:
                    self.orders_repo.update(db_order, status=DbOrderStatus.PENDING)
        except Exception as e:
            logger.debug(
                f"Immediate order status sync failed for {symbol or order_id}: {e}",
                exc_info=False,
            )

    def _verify_order_placement(
        self, order_id: str, symbol: str, wait_seconds: int = 15
    ) -> tuple[bool, str | None]:
        """
        Phase 5: Immediately verify order placement by polling broker once.

        After placing an AMO order, wait briefly then check broker to see if
        the order was immediately rejected. This catches rejections that happen
        within seconds of placement (e.g., insufficient balance, invalid symbol).

        Args:
            order_id: Order ID from broker
            symbol: Trading symbol
            wait_seconds: Seconds to wait before checking (default: 15, range: 10-30)

        Returns:
            Tuple of (is_valid: bool, rejection_reason: Optional[str])
            - is_valid=True: Order is valid (pending, executed, or not found yet)
            - is_valid=False: Order was rejected, rejection_reason contains the reason
        """
        if not order_id:
            logger.warning("Cannot verify order placement: order_id is None")
            return (True, None)  # Assume valid if no order_id

        # Clamp wait time between 10-30 seconds
        wait_seconds = max(10, min(30, wait_seconds))

        logger.info(
            f"Verifying order placement: {symbol} (order_id: {order_id}) - "
            f"waiting {wait_seconds} seconds before checking broker..."
        )

        # Wait for broker to process the order
        time.sleep(wait_seconds)

        try:
            # Query broker for order status
            orders_response = self.orders.get_orders() if self.orders else None
            if not orders_response:
                logger.warning("Could not fetch orders from broker for verification")
                return (True, None)  # Assume valid if we can't check

            broker_orders = orders_response.get("data", [])

            # Find our order in broker's order list
            from .domain.value_objects.order_enums import OrderStatus
            from .utils.order_field_extractor import OrderFieldExtractor
            from .utils.order_status_parser import OrderStatusParser

            for broker_order in broker_orders:
                broker_order_id = OrderFieldExtractor.get_order_id(broker_order)
                if broker_order_id == order_id:
                    # Found our order - check status
                    status = OrderStatusParser.parse_status(broker_order)

                    if status == OrderStatus.REJECTED:
                        # Order was rejected - extract reason
                        rejection_reason = (
                            OrderFieldExtractor.get_rejection_reason(broker_order)
                            or "Unknown rejection reason"
                        )

                        logger.error(
                            f"Order immediately rejected: {symbol} (order_id: {order_id}) - "
                            f"Reason: {rejection_reason}"
                        )

                        # Phase 5: Update database if orders_repo is available
                        if self.orders_repo and self.user_id:
                            try:
                                # Find the order in database
                                all_orders, _ = self.orders_repo.list(self.user_id)
                                db_order = None
                                for order in all_orders:
                                    if (
                                        order.broker_order_id == order_id
                                        or order.order_id == order_id
                                    ):
                                        db_order = order
                                        break

                                if db_order:
                                    # Update order status to rejected

                                    self.orders_repo.mark_rejected(
                                        db_order,
                                        rejection_reason,
                                    )
                                    logger.info(
                                        f"Updated order {order_id} status to REJECTED in database"
                                    )
                            except Exception as e:
                                logger.warning(f"Failed to update order status in database: {e}")

                        # Phase 5: Send notification
                        try:
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            telegram_msg = (
                                f"⚠️ *AMO Order Immediately Rejected*\n\n"
                                f"Symbol: `{symbol}`\n"
                                f"Order ID: `{order_id}`\n"
                                f"Reason: {rejection_reason}\n\n"
                                f"Order was rejected within {wait_seconds} seconds of placement. "
                                f"Please check broker app.\n\n"
                                f"_Time: {timestamp}_"
                            )
                            # Use TelegramNotifier to respect notification preferences
                            if self.telegram_notifier and self.telegram_notifier.enabled:
                                try:
                                    # Use notify_order_rejection for order rejections
                                    self.telegram_notifier.notify_order_rejection(
                                        symbol=symbol,
                                        order_id=order_id,
                                        quantity=0,  # Quantity not available in this context
                                        rejection_reason=rejection_reason,
                                        user_id=self.user_id,
                                    )
                                except Exception as notify_err:
                                    logger.warning(
                                        f"Failed to send rejection notification: {notify_err}"
                                    )
                            else:
                                # Fallback to old method if telegram_notifier not available
                                from core.telegram import send_telegram

                                send_telegram(telegram_msg)
                        except Exception as e:
                            logger.warning(f"Failed to send rejection notification: {e}")

                        return (False, rejection_reason)

                    elif status in {OrderStatus.COMPLETE, OrderStatus.EXECUTED}:
                        # Order executed immediately (unlikely for AMO, but possible)
                        logger.info(f"Order immediately executed: {symbol} (order_id: {order_id})")
                        return (True, None)

                    else:
                        # Order is pending/open - this is expected for AMO orders
                        logger.debug(
                            f"Order status: {status.value if hasattr(status, 'value') else status} "
                            f"for {symbol} (order_id: {order_id}) - order is pending (expected for AMO)"
                        )
                        return (True, None)

            # Order not found in broker's list yet - this is normal for AMO orders
            # Broker may not show AMO orders immediately
            logger.debug(
                f"Order {order_id} not found in broker order list yet (normal for AMO orders)"
            )
            return (True, None)

        except Exception as e:
            logger.error(f"Error verifying order placement: {e}")
            # On error, assume order is valid (don't block on verification failures)
            return (True, None)

    def _check_for_manual_orders(
        self, symbol: str, cached_pending_orders: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """
        Check for manual orders (orders not in our database) for a given symbol.

        Args:
            symbol: Symbol to check
            cached_pending_orders: Optional cached pending orders to avoid redundant API calls

        Returns:
            {
                'has_manual_order': bool,
                'has_system_order': bool,
                'manual_orders': list[dict],  # List of manual orders found
                'system_orders': list[dict],  # List of system orders found
            }
        """
        result = {
            "has_manual_order": False,
            "has_system_order": False,
            "manual_orders": [],
            "system_orders": [],
        }

        if not self.orders or not self.orders_repo or not self.user_id:
            return result

        try:
            # Use cached orders if provided, otherwise fetch
            if cached_pending_orders is not None:
                pending_orders = cached_pending_orders
            else:
                pending_orders = self.orders.get_pending_orders() or []
            variants = set(self._symbol_variants(symbol))

            from .utils.order_field_extractor import OrderFieldExtractor

            for order in pending_orders:
                order_symbol = OrderFieldExtractor.get_symbol(order).upper()
                transaction_type = OrderFieldExtractor.get_transaction_type(order)

                # Check if this is a BUY order for our symbol
                if not transaction_type.startswith("B"):
                    continue

                if order_symbol not in variants:
                    continue

                # Extract order details
                order_id = OrderFieldExtractor.get_order_id(order)
                if not order_id:
                    continue

                quantity = OrderFieldExtractor.get_quantity(order)
                price = OrderFieldExtractor.get_price(order)

                order_info = {
                    "order_id": order_id,
                    "symbol": order_symbol,
                    "quantity": quantity,
                    "price": price,
                    "broker_order": order,
                }

                # Check if order exists in our database
                db_order = self.orders_repo.get_by_broker_order_id(self.user_id, order_id)

                if db_order:
                    # This is a system order
                    result["has_system_order"] = True
                    result["system_orders"].append(order_info)
                else:
                    # This is a manual order (not in our DB)
                    result["has_manual_order"] = True
                    result["manual_orders"].append(order_info)

        except Exception as e:
            logger.warning(f"Error checking for manual orders for {symbol}: {e}")

        return result

    def _should_skip_retry_due_to_manual_order(
        self, symbol: str, retry_qty: int, manual_order_info: dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Determine if retry should be skipped due to existing manual order.

        Args:
            symbol: Trading symbol
            retry_qty: Quantity that retry wants to place
            manual_order_info: Result from _check_for_manual_orders()

        Returns:
            (should_skip: bool, reason: str)
        """
        if not manual_order_info.get("has_manual_order"):
            return (False, "No manual orders found")

        manual_orders = manual_order_info.get("manual_orders", [])
        if not manual_orders:
            return (False, "No manual orders in list")

        # Use the first manual order (most common case: single manual order)
        manual_order = manual_orders[0]
        manual_qty = manual_order.get("quantity", 0)

        # If manual order quantity is >= retry quantity, skip retry
        if manual_qty >= retry_qty:
            return (
                True,
                f"Manual order exists with {manual_qty} shares (>= retry qty {retry_qty})",
            )

        # If manual order quantity is significantly larger, skip retry
        if manual_qty > retry_qty * 1.5:  # 50% more
            return (
                True,
                f"Manual order exists with {manual_qty} shares (much larger than retry qty {retry_qty})",
            )

        # If manual order quantity is close to retry quantity, skip retry
        if abs(manual_qty - retry_qty) <= 2:  # Within 2 shares
            return (
                True,
                f"Manual order exists with {manual_qty} shares (similar to retry qty {retry_qty})",
            )

        # Otherwise, proceed with retry (will cancel and replace)
        return (
            False,
            f"Manual order has {manual_qty} shares, retry wants {retry_qty} shares - will cancel and replace",
        )

    # ---------------------- Retry pending orders from DB ----------------------
    def retry_pending_orders_from_db(self) -> dict[str, int]:
        """
        Retry FAILED orders that haven't expired from database.
        Called by premarket retry task at scheduled time.

        Returns:
            Summary dict with retry statistics
        """
        summary = {
            "retried": 0,
            "placed": 0,
            "failed": 0,
            "skipped": 0,
        }

        if not self.orders_repo or not self.user_id:
            logger.debug("Cannot retry orders: DB not available or user_id not set")
            return summary

        try:
            # Get retriable FAILED orders (expiry filter applied)
            retriable_orders = self.orders_repo.get_retriable_failed_orders(self.user_id)

            if not retriable_orders:
                logger.info("No retriable FAILED orders to retry")
                return summary

            logger.info(f"Found {len(retriable_orders)} retriable FAILED orders to retry")

            # Safety guard: never retry a buy for symbols that already have an open position.
            # Re-entry logic is handled by dedicated re-entry task, not premarket retry.
            open_position_base_symbols: set[str] = set()
            if self.positions_repo and self.user_id:
                try:
                    for pos in self.positions_repo.list(self.user_id):
                        if getattr(pos, "closed_at", None) is not None:
                            continue
                        qty = float(getattr(pos, "quantity", 0) or 0)
                        if qty <= 0:
                            continue
                        sym = str(getattr(pos, "symbol", "") or "").upper()
                        if not sym:
                            continue
                        open_position_base_symbols.add(sym.split("-")[0])
                except Exception as open_pos_err:
                    logger.warning(
                        f"Open-position guard unavailable during retry: {open_pos_err}. "
                        "Continuing without position guard."
                    )

            # Check portfolio limit using OrderValidationService (Phase 3.1)
            # Update portfolio_service with current portfolio/orders if available
            if self.portfolio and hasattr(self.portfolio_service, "portfolio"):
                if self.portfolio_service.portfolio != self.portfolio:
                    self.portfolio_service.portfolio = self.portfolio
            if self.orders and hasattr(self.portfolio_service, "orders"):
                if self.portfolio_service.orders != self.orders:
                    self.portfolio_service.orders = self.orders

            # Update OrderValidationService with portfolio/orders if available
            if self.portfolio and hasattr(self.order_validation_service, "portfolio"):
                if self.order_validation_service.portfolio != self.portfolio:
                    self.order_validation_service.portfolio = self.portfolio
            if self.orders and hasattr(self.order_validation_service, "orders"):
                if self.order_validation_service.orders != self.orders:
                    self.order_validation_service.orders = self.orders

            has_capacity, current_count, max_size = (
                self.order_validation_service.check_portfolio_capacity(include_pending=True)
            )

            for db_order in retriable_orders:
                summary["retried"] += 1
                symbol = db_order.symbol
                base_symbol = str(symbol or "").upper().split("-")[0]

                # Guard against unintended duplicate buys: skip retry if open position exists.
                if base_symbol and base_symbol in open_position_base_symbols:
                    logger.info(
                        f"Skipping retry for {symbol}: open position already exists for base symbol "
                        f"{base_symbol}. Marking failed retry row as cancelled."
                    )
                    try:
                        self.orders_repo.mark_cancelled(
                            db_order,
                            f"Open position exists for {base_symbol} - retry not needed",
                        )
                    except Exception as cancel_err:
                        logger.warning(
                            f"Failed to cancel stale retry row for {symbol}: {cancel_err}"
                        )
                    summary["skipped"] += 1
                    continue

                # Validate symbol exists in scrip master (single source of truth)
                # Symbol in DB should already be resolved, but validate it exists
                # Use user's trading config preference for exchange
                exchange = (
                    self.strategy_config.default_exchange
                    if self.strategy_config
                    else config.DEFAULT_EXCHANGE
                )
                # Validate symbol exists in scrip master (single source of truth)
                # Only check if scrip_master is available and has symbol_map
                # If scrip_master is not available or symbol_map is empty, skip validation
                if (
                    self.scrip_master
                    and hasattr(self.scrip_master, "symbol_map")
                    and self.scrip_master.symbol_map
                ):
                    try:
                        instrument = self.scrip_master.get_instrument(symbol, exchange=exchange)
                        if not instrument or not instrument.get("symbol"):
                            logger.warning(
                                f"Symbol {symbol} from DB not found in scrip master ({exchange}). "
                                f"Skipping retry (symbol may have been delisted or changed)."
                            )
                            summary["skipped"] += 1
                            continue
                    except Exception as scrip_error:
                        # If scrip_master check fails, log warning but continue (don't block retry)
                        logger.warning(
                            f"Scrip master validation failed for {symbol}: {scrip_error}. "
                            "Continuing with retry."
                        )

                # Check portfolio limit
                if not has_capacity:
                    logger.info(
                        f"Portfolio limit reached ({current_count}/{self.strategy_config.max_portfolio_size}); "
                        "skipping remaining retries"
                    )
                    summary["skipped"] += len(retriable_orders) - summary["retried"] + 1
                    break

                # Duplicate prevention: Check if already in holdings
                # Phase 3.1: Use OrderValidationService for duplicate check (includes holdings + active buy orders)
                is_duplicate, duplicate_reason = (
                    self.order_validation_service.check_duplicate_order(
                        symbol, check_active_buy_order=True, check_holdings=True
                    )
                )

                if is_duplicate:
                    logger.info(
                        f"Skipping retry for {symbol}: {duplicate_reason}. "
                        "Order no longer needed - marking as cancelled."
                    )
                    # Mark as cancelled since order is no longer needed (already in holdings or active order)
                    self.orders_repo.mark_cancelled(
                        db_order, f"{duplicate_reason} - order not needed"
                    )
                    summary["skipped"] += 1
                    continue

                # Get ticker from order_metadata or try to construct it
                ticker = None
                if db_order.order_metadata:
                    ticker = db_order.order_metadata.get("ticker")

                # If not in metadata, try to construct from symbol
                # Remove segment suffix (e.g., -EQ, -BE) before adding .NS
                if not ticker:
                    base_symbol = symbol.split("-")[0] if "-" in symbol else symbol
                    ticker = f"{base_symbol}.NS"

                # Get fresh indicators using IndicatorService
                ind = self.indicator_service.get_daily_indicators_dict(
                    ticker=ticker, rsi_period=None, config=self.strategy_config
                )
                if not ind or any(k not in ind for k in ("close", "rsi10", "ema9", "ema200")):
                    logger.warning(f"Skipping retry {symbol}: missing indicators")
                    summary["skipped"] += 1
                    continue

                raw_close = ind["close"]
                try:
                    close = float(raw_close)
                except (TypeError, ValueError):
                    close = 0.0
                if not isfinite(close) or close <= 0:
                    logger.warning(f"Skipping retry {symbol}: invalid close price {close}")
                    summary["skipped"] += 1
                    continue

                # Recalculate execution capital and quantity based on current strategy config
                # This adapts to changes in user_capital config
                avg_vol = ind.get("avg_volume", 0)
                execution_capital = self._calculate_execution_capital(ticker, close, avg_vol)
                qty = max(config.MIN_QTY, floor(execution_capital / close))

                # Check for manual orders before proceeding
                manual_order_info = self._check_for_manual_orders(symbol)

                # If manual order exists, link it to DB record and update status
                if manual_order_info.get("has_manual_order"):
                    manual_orders = manual_order_info.get("manual_orders", [])
                    if manual_orders:
                        manual_order = manual_orders[0]  # Use first manual order found
                        manual_order_id = manual_order.get("order_id")
                        manual_qty = manual_order.get("quantity", 0)
                        manual_price = manual_order.get("price", 0.0)

                        logger.info(
                            f"Manual AMO order detected for {symbol}: order_id={manual_order_id}, "
                            f"qty={manual_qty}, price={manual_price}. "
                            "Linking to DB record and updating status to PENDING."
                        )

                        # Update DB order with manual order details

                        self.orders_repo.update(
                            db_order,
                            broker_order_id=manual_order_id,
                            quantity=manual_qty,  # Use actual manual order quantity
                            price=manual_price if manual_price > 0 else None,
                            status=DbOrderStatus.PENDING,  # Changed from PENDING_EXECUTION
                        )

                        logger.info(
                            f"Updated DB order {db_order.id} for {symbol}: "
                            f"status=PENDING, broker_order_id={manual_order_id}, "
                            f"qty={manual_qty}, price={manual_price}"
                        )

                        summary["skipped"] += 1

                        # Send notification about manual order linking
                        if self.telegram_notifier and self.telegram_notifier.enabled:
                            try:
                                self.telegram_notifier.notify_retry_queue_updated(
                                    symbol=symbol,
                                    action="linked_manual_order",
                                    retry_count=db_order.retry_count or 0,
                                    user_id=self.user_id,
                                    additional_info={
                                        "manual_order_id": manual_order_id,
                                        "manual_qty": manual_qty,
                                        "manual_price": manual_price,
                                        "retry_qty": qty,
                                        "message": "Manual order linked to DB record, status updated to PENDING",
                                    },
                                )
                            except Exception as notify_error:
                                logger.warning(
                                    f"Failed to send manual order notification: {notify_error}"
                                )
                        continue

                # Duplicate prevention: Check for active buy orders (system orders)
                # Cancel and replace (consistent with place_new_entries behavior)
                has_active_order = False
                try:
                    has_active_order = self.has_active_buy_order(symbol)
                except Exception as active_order_error:
                    logger.warning(
                        f"Active order check failed for {symbol} during retry: {active_order_error}. "
                        "Falling back to database check."
                    )
                    # Database fallback: Check for pending/ongoing buy orders
                    if self.orders_repo and self.user_id:
                        existing_orders, _ = self.orders_repo.list(self.user_id)
                        for existing_order in existing_orders:
                            if (
                                existing_order.symbol == symbol
                                and existing_order.side == "buy"
                                and existing_order.status
                                in {
                                    DbOrderStatus.PENDING,  # Merged: AMO + PENDING_EXECUTION
                                    DbOrderStatus.ONGOING,
                                }
                                and existing_order.id != db_order.id  # Exclude current retry order
                            ):
                                has_active_order = True
                                logger.info(
                                    f"Database check: {symbol} already has pending/ongoing buy order"
                                )
                                break

                if has_active_order:
                    # Cancel existing pending buy order and replace (consistent with place_new_entries)
                    variants = self._symbol_variants(symbol)
                    try:
                        cancelled = self.orders.cancel_pending_buys_for_symbol(variants)
                        logger.info(
                            f"Cancelled {cancelled} pending BUY order(s) for {symbol} before retry"
                        )
                    except Exception as cancel_error:
                        logger.warning(
                            f"Could not cancel pending order(s) for {symbol} before retry: {cancel_error}"
                        )
                        # If cancel fails, skip to prevent duplicates
                        summary["skipped"] += 1
                        continue

                # Check position-to-volume ratio - Phase 3.1: Use OrderValidationService
                is_valid_volume, volume_ratio, tier_info = (
                    self.order_validation_service.check_volume_ratio(qty, avg_vol, symbol, close)
                )
                if not is_valid_volume:
                    logger.info(
                        f"Skipping retry {symbol}: position size too large relative to volume"
                    )
                    # Mark as FAILED (not retryable) since it's a permanent issue
                    self.orders_repo.mark_failed(
                        order=db_order,
                        failure_reason="Position too large for volume - not retryable",
                        retry_pending=False,
                    )
                    summary["skipped"] += 1
                    continue

                # Check balance via check-margin (fallback: limits-based).
                margin_result = self._check_order_margin(
                    symbol=symbol,
                    price=close,
                    qty=qty,
                    transaction_type="B",
                    product="CNC",
                )
                if len(margin_result) == 4:
                    has_sufficient, avail_cash, required_cash, shortfall = margin_result
                    margin_api_ok = True
                else:
                    has_sufficient, avail_cash, required_cash, shortfall, margin_api_ok = margin_result

                if not margin_api_ok:
                    logger.error(
                        f"Retry margin check failed for {symbol}; "
                        "skipping this retry attempt (not a balance-shortfall decision)."
                    )
                    from src.infrastructure.db.timezone_utils import ist_now

                    db_order.retry_count = (db_order.retry_count or 0) + 1
                    db_order.last_retry_attempt = ist_now()
                    db_order.reason = "margin_check_failed"
                    self.orders_repo.update(db_order)
                    summary["failed"] += 1
                    continue

                affordable = int((avail_cash or 0.0) // close) if close > 0 else 0
                if not has_sufficient or affordable < config.MIN_QTY or qty > affordable:
                    logger.warning(
                        f"Retry failed for {symbol}: still insufficient balance "
                        f"(need Rs {required_cash:,.0f}, have Rs {(avail_cash or 0.0):,.0f})"
                    )
                    # Update retry count but keep as FAILED for next scheduled retry
                    from src.infrastructure.db.timezone_utils import ist_now

                    db_order.retry_count = (db_order.retry_count or 0) + 1
                    db_order.last_retry_attempt = ist_now()
                    db_order.reason = (
                        f"insufficient_balance - shortfall: Rs {shortfall:,.0f}"
                    )
                    self.orders_repo.update(db_order)
                    summary["failed"] += 1
                    continue

                # Try placing the order
                success, order_id = self._attempt_place_order(symbol, ticker, qty, close, ind)
                if success:
                    summary["placed"] += 1
                    # Update order status to PENDING and set broker_order_id
                    # Also update quantity in case it changed due to config changes
                    try:
                        self.orders_repo.update(
                            db_order,
                            broker_order_id=order_id,
                            quantity=qty,  # Update with recalculated quantity
                            status=DbOrderStatus.PENDING,
                        )
                    except Exception as update_err:
                        # Some deployments may still have unique index
                        # uq_orders_user_base_symbol_active applying to active BUY rows.
                        # If a stale active row exists for same base_symbol, cancel it and retry once.
                        err_text = str(update_err).lower()
                        if "uq_orders_user_base_symbol_active" in err_text or "duplicate key value" in err_text:
                            try:
                                from src.infrastructure.db.timezone_utils import ist_now

                                # Clear failed transaction before further DB work.
                                self.db.rollback()
                                base_symbol = (
                                    (symbol or "").upper().split("-")[0].strip()
                                )
                                existing_orders, _ = self.orders_repo.list(self.user_id)
                                cancelled_conflicts = 0
                                for existing_order in existing_orders:
                                    existing_base = (
                                        (getattr(existing_order, "base_symbol", None) or "")
                                        .upper()
                                        .split("-")[0]
                                        .strip()
                                    )
                                    if not existing_base:
                                        existing_base = (
                                            (getattr(existing_order, "symbol", "") or "")
                                            .upper()
                                            .split("-")[0]
                                            .strip()
                                        )
                                    if (
                                        existing_order.id != db_order.id
                                        and existing_order.user_id == self.user_id
                                        and existing_order.side == "buy"
                                        and existing_base == base_symbol
                                        and existing_order.status
                                        in {DbOrderStatus.PENDING, DbOrderStatus.ONGOING}
                                    ):
                                        self.orders_repo.update(
                                            existing_order,
                                            status=DbOrderStatus.CANCELLED,
                                            reason=(
                                                "Cancelled stale active order during retry "
                                                "to satisfy unique active-symbol constraint"
                                            ),
                                            closed_at=ist_now(),
                                            last_status_check=ist_now(),
                                        )
                                        cancelled_conflicts += 1
                                if cancelled_conflicts:
                                    logger.warning(
                                        f"Retry DB conflict for {symbol}: cancelled "
                                        f"{cancelled_conflicts} conflicting active buy row(s), retrying update."
                                    )
                                # Retry once after conflict cleanup.
                                self.orders_repo.update(
                                    db_order,
                                    broker_order_id=order_id,
                                    quantity=qty,
                                    status=DbOrderStatus.PENDING,
                                )
                            except Exception as retry_update_err:
                                logger.error(
                                    f"Retry order DB update failed for {symbol} after conflict cleanup: {retry_update_err}",
                                    exc_info=retry_update_err,
                                )
                                summary["failed"] += 1
                                continue
                        else:
                            logger.error(
                                f"Retry order DB update failed for {symbol}: {update_err}",
                                exc_info=update_err,
                            )
                            summary["failed"] += 1
                            continue
                    logger.info(
                        f"Successfully placed retry order for {symbol} (order_id: {order_id}, qty: {qty}). "
                        f"DB updated with new quantity based on current config."
                    )

                    # Send notification
                    if self.telegram_notifier and self.telegram_notifier.enabled:
                        try:
                            retry_count = db_order.retry_count or 0
                            self.telegram_notifier.notify_retry_queue_updated(
                                symbol=symbol,
                                action="retried_successfully",
                                retry_count=retry_count,
                                user_id=self.user_id,
                                additional_info={"order_id": order_id},
                            )
                        except Exception as notify_error:
                            logger.warning(
                                f"Failed to send retry success notification: {notify_error}"
                            )
                else:
                    # Broker/API error - mark as FAILED (not retryable)
                    self.orders_repo.mark_failed(
                        order=db_order,
                        failure_reason="Broker API error during retry - not retryable",
                        retry_pending=False,
                    )
                    summary["failed"] += 1
                    logger.error(f"Broker/API error while retrying order for {symbol}")

            logger.info(
                f"Retry summary: {summary['placed']} placed, {summary['failed']} failed, "
                f"{summary['skipped']} skipped"
            )
            return summary

        except Exception as e:
            logger.error(f"Error retrying pending orders from DB: {e}", exc_info=e)
            return summary

    # ---------------------- Pre-Market AMO Adjustment ----------------------

    def adjust_amo_quantities_premarket(self) -> dict[str, int]:
        """
        Pre-market AMO quantity adjuster (runs at 9:05 AM)

        Adjusts AMO order quantities based on pre-market prices
        to keep capital constant (user_capital per trade).

        Handles gaps up (reduce qty) and gaps down (increase qty)
        to prevent order rejections due to insufficient funds.

        Returns:
            Summary dict with adjustment statistics
        """
        summary = {
            "total_orders": 0,
            "adjusted": 0,
            "no_adjustment_needed": 0,
            "price_unavailable": 0,
            "modification_failed": 0,
            "skipped_not_enabled": 0,
            "cancelled_above_ema9": 0,
        }

        # Check if feature is enabled
        if not self.strategy_config.enable_premarket_amo_adjustment:
            logger.info("Pre-market AMO adjustment is disabled in config - skipping")
            summary["skipped_not_enabled"] = 1
            return summary

        logger.info("🔄 Starting pre-market AMO quantity adjustment...")

        # Check authentication
        if not self.auth or not self.auth.is_authenticated():
            logger.warning("Session expired - attempting re-authentication...")
            if not self.login():
                logger.error("Re-authentication failed - cannot adjust AMO orders")
                return summary

        if not self.orders or not self.portfolio:
            logger.error("Orders or portfolio not initialized - attempting login...")
            if not self.login():
                logger.error("Login failed - cannot adjust AMO orders")
                return summary

        try:
            # 1. Get all pending orders from broker
            logger.info("Fetching pending AMO orders from broker...")
            pending_orders = self.orders.get_pending_orders() or []

            # Filter only AMO/pending orders (including re-entry orders)
            amo_orders = [
                order
                for order in pending_orders
                if order.get("orderValidity", "").upper() == "DAY"  # AMO orders
                and order.get("orderStatus", "").upper() in ["PENDING", "OPEN", "TRIGGER_PENDING"]
                and order.get("transactionType", "").upper() == "BUY"
            ]

            # Also get re-entry orders from database (if available)
            reentry_orders_from_db = []
            if self.orders_repo and self.user_id:
                try:
                    # Import here to ensure it's available
                    from src.infrastructure.db.models import OrderStatus as DbOrderStatus

                    all_orders, _ = self.orders_repo.list(self.user_id)
                    reentry_orders_from_db = [
                        db_order
                        for db_order in all_orders
                        if db_order.side == "buy"
                        and db_order.status == DbOrderStatus.PENDING
                        and db_order.entry_type == "reentry"
                    ]

                    if reentry_orders_from_db:
                        logger.info(
                            f"Found {len(reentry_orders_from_db)} re-entry orders in database"
                        )
                except Exception as e:
                    logger.warning(f"Error fetching re-entry orders from database: {e}")

            # Build set of broker order IDs for quick lookup
            broker_order_ids = set()
            if pending_orders:
                broker_order_ids = {
                    order.get("nOrdNo", order.get("orderId", ""))
                    for order in pending_orders
                    if order.get("nOrdNo") or order.get("orderId")
                }

            # Track which re-entry orders we've already cancelled (to skip them in next loop)
            cancelled_reentry_order_ids = set()

            # Check re-entry orders from database for closed positions FIRST
            # This must happen even if there are no broker orders, to handle cases where
            # re-entry orders exist in DB but position was closed
            for db_order in reentry_orders_from_db:
                # Check if position is closed - cancel re-entry order if closed
                if self.positions_repo:
                    # Use get_by_symbol_any to check for closed positions
                    position = self.positions_repo.get_by_symbol_any(
                        self.user_id, db_order.symbol, include_closed=True
                    )
                    if position and position.closed_at is not None:
                        logger.info(
                            f"Position {db_order.symbol} is closed - cancelling re-entry order {db_order.broker_order_id}"
                        )
                        try:
                            if db_order.broker_order_id:
                                cancel_result = self.orders.cancel_order(db_order.broker_order_id)
                                if cancel_result:
                                    logger.info(
                                        f"Cancelled re-entry order {db_order.broker_order_id} for closed position"
                                    )
                                    # Update DB order status
                                    from src.infrastructure.db.models import (
                                        OrderStatus as DbOrderStatus,
                                    )

                                    self.orders_repo.update(
                                        db_order,
                                        status=DbOrderStatus.CANCELLED,
                                        reason="Position closed",
                                    )
                                    summary["cancelled"] = summary.get("cancelled", 0) + 1
                                    cancelled_reentry_order_ids.add(db_order.broker_order_id)
                        except Exception as e:
                            logger.warning(
                                f"Error cancelling re-entry order {db_order.broker_order_id}: {e}"
                            )
                        continue

            # Check for re-entry orders not found at broker (EOD cancellation handling)
            # This must happen even if broker returns empty, to mark stale orders as CANCELLED
            for db_order in reentry_orders_from_db:
                # Skip if already cancelled for closed position
                if db_order.broker_order_id in cancelled_reentry_order_ids:
                    continue

                # Check if order is found in broker's order list
                order_found_at_broker = (
                    db_order.broker_order_id and db_order.broker_order_id in broker_order_ids
                )

                if order_found_at_broker:
                    # Order found at broker - add to processing list
                    matching_broker_order = None
                    if pending_orders:
                        for broker_order in pending_orders:
                            broker_order_id = broker_order.get(
                                "nOrdNo", broker_order.get("orderId", "")
                            )
                            if broker_order_id == db_order.broker_order_id:
                                matching_broker_order = broker_order
                                break
                    if matching_broker_order:
                        # Only add if not already in amo_orders (avoid duplicates)
                        # Re-entry orders might already be in amo_orders from initial broker filter
                        already_in_list = any(
                            order.get("nOrdNo", order.get("orderId", ""))
                            == db_order.broker_order_id
                            for order in amo_orders
                        )
                        if not already_in_list:
                            amo_orders.append(matching_broker_order)
                else:
                    # Order not found at broker - likely cancelled by broker at EOD
                    # Order not found at broker - likely cancelled by broker at EOD
                    # Mark PENDING orders as CANCELLED in database, but only if:
                    # 1. Order is still PENDING (re-check to avoid race conditions)
                    # 2. Order is old enough (placed before previous day's market close)
                    #    to avoid marking newly placed orders as CANCELLED
                    from src.infrastructure.db.models import (
                        OrderStatus as DbOrderStatus,
                    )

                    if db_order.status == DbOrderStatus.PENDING and self.orders_repo:
                        try:
                            # Re-check order status to avoid race conditions
                            # (e.g., UnifiedOrderMonitor might have updated it)
                            # Fetch fresh order from DB using broker_order_id
                            fresh_order = self.orders_repo.get_by_broker_order_id(
                                self.user_id, db_order.broker_order_id
                            )
                            if not fresh_order or fresh_order.status != DbOrderStatus.PENDING:
                                logger.debug(
                                    f"Re-entry order {db_order.broker_order_id} status changed "
                                    f"(now {fresh_order.status if fresh_order else 'deleted'}) - skipping cancellation"
                                )
                                continue

                            # Check if order is old enough (placed before previous day's market close)
                            # This prevents marking newly placed orders as CANCELLED if broker API
                            # hasn't synced yet
                            from src.infrastructure.db.timezone_utils import IST, ist_now

                            now = ist_now()
                            if now.tzinfo is None:
                                now = now.replace(tzinfo=IST)
                            elif now.tzinfo != IST:
                                now = now.astimezone(IST)

                            # Only mark as CANCELLED if order is at least 1 hour old
                            # (gives broker API time to sync)
                            if db_order.placed_at:
                                placed_at = db_order.placed_at
                                if placed_at.tzinfo is None:
                                    placed_at = placed_at.replace(tzinfo=IST)
                                elif placed_at.tzinfo != IST:
                                    placed_at = placed_at.astimezone(IST)

                                age_hours = (now - placed_at).total_seconds() / 3600
                                if age_hours < 1:
                                    logger.debug(
                                        f"Re-entry order {db_order.broker_order_id} is too recent "
                                        f"({age_hours:.1f} hours old) - skipping cancellation "
                                        f"(broker API may not have synced yet)"
                                    )
                                    continue

                            logger.info(
                                f"Re-entry order {db_order.broker_order_id} not found at broker "
                                f"(likely cancelled at EOD) - marking as CANCELLED in database"
                            )
                            self.orders_repo.update(
                                fresh_order,
                                status=DbOrderStatus.CANCELLED,
                                reason="Order not found at broker (likely cancelled at EOD)",
                            )
                            summary["cancelled"] = summary.get("cancelled", 0) + 1
                        except Exception as e:
                            logger.warning(
                                f"Error updating order status for {db_order.broker_order_id}: {e}"
                            )
                    else:
                        logger.warning(
                            f"Re-entry order {db_order.broker_order_id} not found in broker orders - "
                            f"may have been executed or cancelled (status: {db_order.status})"
                        )

            summary["total_orders"] = len(amo_orders)

            # PERFORMANCE FIX: Pre-fetch prices and calculate EMA9 for all orders in parallel
            # This reduces total time from N*3-4s to ~3-4s for all orders
            from concurrent.futures import ThreadPoolExecutor, as_completed

            from .market_data import KotakNeoMarketData

            market_data = KotakNeoMarketData(self.auth)

            # Prepare order data for parallel processing
            order_data = []
            for order in amo_orders:
                symbol = order.get("symbol", order.get("tradingSymbol", ""))
                original_qty = int(order.get("quantity", 0))
                order_id = order.get("nOrdNo", order.get("orderId", ""))

                if not symbol or not original_qty or not order_id:
                    logger.warning(f"Incomplete order data - skipping: {order}")
                    continue

                # Extract base symbol (remove -EQ suffix if present)
                base_symbol = symbol.replace("-EQ", "")

                # Get ticker from order metadata or construct from symbol
                ticker = None
                if self.orders_repo and self.user_id:
                    try:
                        db_order = self.orders_repo.get_by_broker_order_id(self.user_id, order_id)
                        if db_order and db_order.order_metadata:
                            ticker = db_order.order_metadata.get(
                                "ticker"
                            ) or db_order.order_metadata.get("original_ticker")
                    except Exception:
                        pass  # Ignore errors - will construct ticker below

                # Construct ticker if not found in metadata
                if not ticker:
                    ticker = f"{base_symbol}.NS"

                order_data.append(
                    {
                        "order": order,
                        "symbol": symbol,
                        "base_symbol": base_symbol,
                        "ticker": ticker,
                        "order_id": order_id,
                        "original_qty": original_qty,
                    }
                )

            # Fetch prices and calculate EMA9 for all orders in parallel
            price_results = {}
            ema9_results = {}
            if order_data:
                logger.info(
                    f"Pre-fetching prices and calculating EMA9 for {len(order_data)} orders in parallel..."
                )

                def fetch_price_and_ema9(order_info):
                    """Fetch price and calculate EMA9 for a single order"""
                    symbol = order_info["symbol"]
                    base_symbol = order_info["base_symbol"]
                    ticker = order_info["ticker"]
                    order_id = order_info["order_id"]
                    result = {
                        "order_id": order_id,
                        "price": None,
                        "ema9": None,
                    }
                    try:
                        # Fetch pre-market price
                        price = market_data.get_ltp(symbol, exchange="NSE")
                        if price and price > 0:
                            result["price"] = price

                            # Calculate EMA9 using fetched price
                            try:
                                ema9 = self.indicator_service.calculate_ema9_realtime(
                                    ticker=ticker,
                                    broker_symbol=symbol,
                                    current_ltp=price,
                                )
                                if ema9 and ema9 > 0:
                                    result["ema9"] = ema9
                            except Exception as e:
                                logger.debug(f"{base_symbol}: Failed to calculate EMA9: {e}")
                    except Exception as e:
                        logger.debug(f"{base_symbol}: Failed to fetch pre-market price: {e}")

                    return order_id, result

                with ThreadPoolExecutor(max_workers=min(10, len(order_data))) as executor:
                    future_to_order = {
                        executor.submit(fetch_price_and_ema9, o): o for o in order_data
                    }
                    for future in as_completed(future_to_order):
                        order_id, result = future.result()
                        price_results[order_id] = result["price"]
                        ema9_results[order_id] = result["ema9"]

                logger.info(
                    f"Pre-fetch complete: {len([p for p in price_results.values() if p is not None])}/{len(order_data)} prices, "
                    f"{len([e for e in ema9_results.values() if e is not None])}/{len(order_data)} EMA9 values"
                )

            # Process each AMO order using pre-fetched prices and EMA9 values
            for order_info in order_data:
                order = order_info["order"]
                symbol = order_info["symbol"]
                base_symbol = order_info["base_symbol"]
                order_id = order_info["order_id"]
                original_qty = order_info["original_qty"]

                logger.info(f"Processing {base_symbol}: current qty={original_qty}")

                # Use pre-fetched pre-market price
                premarket_price = price_results.get(order_id)

                if not premarket_price or premarket_price <= 0:
                    logger.warning(f"{base_symbol}: Pre-market price not available, skipping")
                    summary["price_unavailable"] += 1
                    continue

                logger.info(f"{base_symbol}: Pre-market price = Rs {premarket_price:.2f}")

                # Use pre-calculated EMA9
                ema9 = ema9_results.get(order_id)

                # Check if pre-market price > EMA9 - 1%
                if ema9 and ema9 > 0:
                    ema9_threshold = ema9 * 0.99  # EMA9 - 1%
                    if premarket_price > ema9_threshold:
                        logger.warning(
                            f"{base_symbol}: Pre-market price (Rs {premarket_price:.2f}) > EMA9-1% "
                            f"(Rs {ema9_threshold:.2f}, EMA9: Rs {ema9:.2f}) - Cancelling order"
                        )
                        try:
                            cancel_result = self.orders.cancel_order(order_id)
                            if cancel_result:
                                logger.info(
                                    f"✅ {base_symbol}: Order cancelled due to gap-up above EMA9-1%"
                                )
                                summary["cancelled_above_ema9"] += 1

                                # Update database order status
                                if self.db and self.orders_repo:
                                    try:
                                        db_order = self.orders_repo.get_by_broker_order_id(
                                            self.user_id, order_id
                                        )
                                        if db_order:
                                            from src.infrastructure.db.models import (
                                                OrderStatus as DbOrderStatus,
                                            )

                                            self.orders_repo.update(
                                                db_order,
                                                status=DbOrderStatus.CANCELLED,
                                                reason=f"Pre-market price (Rs {premarket_price:.2f}) > EMA9-1% (Rs {ema9_threshold:.2f})",
                                            )
                                            logger.info(
                                                f"{base_symbol}: DB order record updated - cancelled due to EMA9 validation"
                                            )
                                    except Exception as db_err:
                                        logger.warning(
                                            f"{base_symbol}: Failed to update DB record: {db_err}"
                                        )

                                # Send Telegram notification
                                if self.telegram_notifier and self.telegram_notifier.enabled:
                                    try:
                                        message_text = (
                                            f"🚫 *Order Cancelled - Gap Up Above EMA9*\n\n"
                                            f"Symbol: `{base_symbol}`\n"
                                            f"Pre-market: Rs {premarket_price:.2f}\n"
                                            f"EMA9: Rs {ema9:.2f}\n"
                                            f"Threshold: Rs {ema9_threshold:.2f} (EMA9 - 1%)\n"
                                            f"Reason: Price gap-up above entry target"
                                        )
                                        self.telegram_notifier.notify_system_alert(
                                            alert_type="ORDER_CANCELLED_EMA9",
                                            message_text=message_text,
                                            severity="WARNING",
                                            user_id=self.user_id,
                                        )
                                    except Exception as notify_err:
                                        logger.warning(
                                            f"Failed to send Telegram notification: {notify_err}"
                                        )

                                continue  # Skip quantity adjustment for cancelled order
                            else:
                                logger.error(f"{base_symbol}: Failed to cancel order above EMA9-1%")
                                summary["modification_failed"] += 1
                        except Exception as cancel_err:
                            logger.error(
                                f"{base_symbol}: Error cancelling order above EMA9-1%: {cancel_err}",
                                exc_info=True,
                            )
                            summary["modification_failed"] += 1
                elif ema9 is None:
                    logger.warning(
                        f"{base_symbol}: EMA9 calculation failed - proceeding with quantity adjustment"
                    )

                # 4. Recalculate quantity to keep capital constant
                target_capital = self.strategy_config.user_capital
                new_qty = max(config.MIN_QTY, floor(target_capital / premarket_price))

                # 5. Check if quantity adjustment is needed
                if new_qty == original_qty:
                    logger.info(f"{base_symbol}: No adjustment needed (qty={original_qty})")
                    summary["no_adjustment_needed"] += 1
                    continue

                # Calculate gap percentage
                original_value = original_qty * premarket_price
                gap_pct = (
                    (premarket_price - (target_capital / original_qty))
                    / (target_capital / original_qty)
                ) * 100

                # 6. Modify the AMO order
                # For MARKET orders, only quantity needs to be updated
                # Price is logged for tracking but not passed to modify_order (not needed for MARKET)
                original_price = float(
                    order.get("price", order.get("prc", order.get("orderPrice", 0))) or 0
                )
                logger.info(
                    f"{base_symbol}: Adjusting AMO order: "
                    f"qty {original_qty} → {new_qty}, "
                    f"price Rs {original_price:.2f} → Rs {premarket_price:.2f} "
                    f"(gap: {gap_pct:+.2f}%, capital: Rs {self.strategy_config.user_capital:,.0f})"
                )

                try:
                    result = self.orders.modify_order(
                        order_id=order_id,
                        quantity=new_qty,
                        # Note: price parameter not needed for MARKET orders (executes at market price)
                        order_type="MKT",  # Keep as MARKET order
                    )

                    if result and result.get("stat", "").lower() == "ok":
                        logger.info(
                            f"✅ {base_symbol}: AMO order modified successfully (#{order_id})"
                        )
                        summary["adjusted"] += 1

                        # Update database record if exists
                        if self.db and self.orders_repo:
                            try:
                                db_order = self.orders_repo.get_by_broker_order_id(
                                    self.user_id, order_id
                                )
                                if db_order:
                                    self.orders_repo.update(db_order, quantity=new_qty)
                                    logger.info(
                                        f"{base_symbol}: DB order record updated with new qty={new_qty}"
                                    )
                            except Exception as db_err:
                                logger.warning(
                                    f"{base_symbol}: Failed to update DB record: {db_err}"
                                )

                        # Send Telegram notification
                        if self.telegram_notifier and self.telegram_notifier.enabled:
                            try:
                                message_text = (
                                    f"📊 *Pre-Market Adjustment*\n\n"
                                    f"Symbol: `{base_symbol}`\n"
                                    f"Qty: {original_qty} → {new_qty} ({new_qty - original_qty:+d})\n"
                                    f"Gap: {gap_pct:+.2f}%\n"
                                    f"Pre-market: Rs {premarket_price:.2f}"
                                )
                                self.telegram_notifier.notify_system_alert(
                                    alert_type="PRE_MARKET_ADJUSTMENT",
                                    message_text=message_text,
                                    severity="INFO",
                                    user_id=self.user_id,
                                )
                            except Exception as notify_err:
                                logger.warning(
                                    f"Failed to send Telegram notification: {notify_err}"
                                )
                    else:
                        logger.error(f"❌ {base_symbol}: AMO modification failed: {result}")
                        summary["modification_failed"] += 1

                except Exception as e:
                    logger.error(f"❌ {base_symbol}: Error modifying AMO: {e}", exc_info=True)
                    summary["modification_failed"] += 1

            # Summary
            logger.info(
                f"✅ Pre-market adjustment complete: "
                f"{summary['adjusted']} adjusted, "
                f"{summary['no_adjustment_needed']} unchanged, "
                f"{summary['price_unavailable']} price N/A, "
                f"{summary['modification_failed']} failed, "
                f"{summary['cancelled_above_ema9']} cancelled (above EMA9-1%)"
            )

            return summary

        except Exception as e:
            logger.error(f"Error during pre-market AMO adjustment: {e}", exc_info=True)
            return summary

    # ---------------------- New entries ----------------------
    def place_new_entries(self, recommendations: list[Recommendation]) -> dict[str, int | list]:
        summary = {
            "attempted": 0,
            "placed": 0,
            "failed_balance": 0,
            "skipped": 0,  # Total skipped (for backward compatibility with tests)
            "skipped_portfolio_limit": 0,
            "skipped_duplicates": 0,
            "skipped_missing_data": 0,
            "skipped_invalid_qty": 0,
            "ticker_attempts": [],  # Per-ticker telemetry: list of dicts with ticker, status, reason, qty, capital, etc.
        }

        # Check if authenticated - if not, try to re-authenticate
        if not self.auth or not self.auth.is_authenticated():
            logger.warning("Session expired - attempting re-authentication...")
            if not self.login():
                logger.error("Re-authentication failed - cannot proceed")
                return summary
            logger.info("Re-authentication successful - proceeding with order placement")

        if not self.orders or not self.portfolio:
            logger.error("Orders or portfolio not initialized - attempting login...")
            if not self.login():
                logger.error("Login failed - cannot proceed")
                return summary

        # Pre-flight check: Verify we can fetch holdings before proceeding
        # This prevents duplicate orders if holdings API is down
        # NOTE: Broker API may restrict balance checks between 12 AM - 6 AM IST, but we still attempt it
        # Retry up to 3 times for transient API errors
        logger.info("Pre-flight check: Fetching holdings to verify API health...")
        test_holdings = None
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            test_holdings = self.portfolio.get_holdings()
            if test_holdings is not None:
                break
            if attempt < max_retries:
                logger.warning(
                    f"Holdings API failed (attempt {attempt}/{max_retries}) - retrying in 2 seconds..."
                )
                time.sleep(2)
            else:
                logger.error(
                    f"Holdings API failed after {max_retries} attempts - broker API may be temporarily unavailable. "
                    "Aborting order placement to prevent duplicate orders."
                )

        # Handle None response (API error after retries)
        if test_holdings is None:
            logger.warning(
                "Holdings API unavailable after retries - using database fallback to check for existing orders"
            )
            # Fallback: Check database for existing orders to prevent duplicates
            if self.db and self.user_id and hasattr(self, "orders_repo") and text:
                # Check if we have any pending/ongoing buy orders for the recommended symbols
                symbols_to_check = [
                    self.parse_symbol_for_broker(rec.ticker) for rec in recommendations
                ]
                existing_orders = []
                query = text(
                    """
                    SELECT COUNT(*) as count
                    FROM orders
                    WHERE user_id = :user_id
                    AND symbol = :symbol
                    AND side = 'buy'
                    AND status IN ('pending', 'ongoing')
                """
                )
                for symbol in symbols_to_check:
                    result = self.db.execute(
                        query, {"user_id": self.user_id, "symbol": symbol}
                    ).fetchone()
                    if result and result[0] > 0:
                        existing_orders.append(symbol)

                if existing_orders:
                    logger.error(
                        f"Cannot fetch holdings and found existing orders for: {existing_orders}. "
                        "Aborting to prevent duplicate orders. Please check broker API status."
                    )
                    return summary
                else:
                    logger.warning(
                        "Holdings API unavailable but no existing orders found in database. "
                        "Proceeding with order placement (risk: may duplicate if holdings exist but not in DB)."
                    )
                    # Proceed without holdings check - we'll rely on broker-side duplicate detection
                    # Set test_holdings to empty dict to bypass validation
                    test_holdings = {"data": []}
                    # Cache the empty holdings to avoid redundant API calls
                    if (
                        self.portfolio_service
                        and self.portfolio_service.enable_caching
                        and self.portfolio_service._cache
                    ):
                        self.portfolio_service._cache.set("holdings", test_holdings)
                        logger.debug(
                            "Populated PortfolioService cache with empty holdings (fallback)"
                        )
            else:
                logger.error(
                    "Cannot fetch holdings (API returned None after retries) and no database fallback available. "
                    "Aborting order placement to prevent duplicates. Please check broker API status or try again later."
                )
                return summary

        # Check for 2FA gate
        if self._response_requires_2fa(test_holdings):
            logger.warning("Holdings API requires 2FA - attempting re-login...")
            if hasattr(self.auth, "force_relogin") and self.auth.force_relogin():
                test_holdings = self.portfolio.get_holdings()
                if test_holdings is None:
                    logger.error(
                        "Holdings still unavailable after re-login - aborting order placement"
                    )
                    return summary
                # Update cache with fresh holdings after 2FA re-login
                if (
                    self.portfolio_service
                    and self.portfolio_service.enable_caching
                    and self.portfolio_service._cache
                ):
                    self.portfolio_service._cache.set("holdings", test_holdings)
                    logger.debug("Updated PortfolioService cache with holdings after 2FA re-login")

        # Verify holdings has 'data' field (successful response structure)
        if not isinstance(test_holdings, dict) or "data" not in test_holdings:
            logger.error(
                "Holdings API returned invalid response - aborting order placement to prevent duplicates"
            )
            logger.error(
                f"Holdings response type: {type(test_holdings)}, keys: {list(test_holdings.keys()) if isinstance(test_holdings, dict) else 'N/A'}"
            )
            return summary

        logger.info("Holdings API healthy - proceeding with order placement")

        # Note: Stale PENDING orders are excluded from portfolio count in PortfolioService
        # EOD cleanup handles marking stale orders as CANCELLED/FAILED at end of day
        # The exclusion in portfolio count prevents stale orders from blocking new orders during the day

        # OPTIMIZATION: Populate PortfolioService cache with holdings from pre-flight check
        # This prevents redundant API calls when PortfolioService methods are called later
        # Same pattern as pending_orders cache - fetch once, reuse throughout
        if (
            self.portfolio_service
            and self.portfolio_service.enable_caching
            and self.portfolio_service._cache
            and test_holdings is not None
        ):
            self.portfolio_service._cache.set("holdings", test_holdings)
            logger.debug("Populated PortfolioService cache with holdings from pre-flight check")

        # OPTIMIZATION: Cache portfolio snapshot and pre-fetch indicators
        # Reduces API calls from O(n) to O(1) for portfolio checks
        # Update portfolio_service with current portfolio/orders if available
        if self.portfolio and self.portfolio_service.portfolio != self.portfolio:
            self.portfolio_service.portfolio = self.portfolio
        if self.orders and self.portfolio_service.orders != self.orders:
            self.portfolio_service.orders = self.orders

        cached_portfolio_count = None
        cached_holdings_symbols = set()
        try:
            cached_portfolio_count = self.portfolio_service.get_portfolio_count(
                include_pending=True
            )
            # Get holdings symbols from PortfolioService (base symbols only)
            cached_positions = self.portfolio_service.get_current_positions(
                include_pending=False
            )  # Only actual holdings, not pending
            # Extract base symbols (remove -EQ, -BE, etc. suffixes)
            for sym in cached_positions:
                base_sym = (
                    sym.replace("-EQ", "").replace("-BE", "").replace("-BL", "").replace("-BZ", "")
                )
                if base_sym:
                    cached_holdings_symbols.add(base_sym)
            logger.info(
                f"Cached portfolio snapshot: {cached_portfolio_count} positions, "
                f"{len(cached_holdings_symbols)} symbols"
            )
        except Exception as e:
            logger.warning(f"Failed to cache portfolio snapshot: {e}, will fetch per-ticker")

        # Pre-fetch indicators for all recommendation tickers (batch operation with parallelization)
        cached_indicators: dict[str, dict[str, Any] | None] = {}
        if recommendations:
            # Pre-fetch all indicators in parallel (thread-safe cache, no fallback to sequential)
            logger.info(
                f"Pre-fetching indicators for {len(recommendations)} recommendations in parallel..."
            )
            from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: PLC0415

            def fetch_indicator(rec_ticker: str) -> tuple[str, dict[str, Any] | None]:
                """Fetch indicator for a single ticker (thread-safe)"""
                try:
                    logger.debug(f"[Parallel Fetch] Starting fetch for {rec_ticker}")
                    # Use instance method so tests/mocks can override data source.
                    ind = self.get_daily_indicators(rec_ticker)
                    if ind:
                        logger.debug(
                            f"[Parallel Fetch] Fetched {rec_ticker}: "
                            f"close={ind.get('close', 'N/A')}"
                        )
                    return (rec_ticker, ind)
                except Exception as e:
                    logger.error(
                        f"Failed to fetch indicators for {rec_ticker}: {e}",
                        exc_info=False,
                    )
                    return (rec_ticker, None)

            # ThreadPoolExecutor: 5 max workers for concurrent requests
            # Separate locks in PriceCache prevent deadlocks
            max_workers = min(5, len(recommendations))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_ticker = {
                    executor.submit(fetch_indicator, rec.ticker): rec.ticker
                    for rec in recommendations
                }

                for future in as_completed(future_to_ticker, timeout=60):  # 60s overall timeout
                    try:
                        ticker, ind = future.result(timeout=30)  # 30s per future

                        # Validate ticker match
                        expected_ticker = future_to_ticker.get(future)
                        if ticker != expected_ticker:
                            logger.error(
                                f"Ticker mismatch! Expected {expected_ticker}, got {ticker}"
                            )
                            ticker = expected_ticker

                        cached_indicators[ticker] = ind
                        if ind:
                            logger.debug(
                                f"Cached indicators for {ticker}: close={ind.get('close', 'N/A')}"
                            )
                    except TimeoutError:
                        ticker = future_to_ticker.get(future, "unknown")
                        logger.error(f"Timeout fetching indicators for {ticker}")
                        cached_indicators[ticker] = None
                    except Exception as e:
                        ticker = future_to_ticker.get(future, "unknown")
                        logger.error(f"Error fetching {ticker}: {e}", exc_info=False)
                        cached_indicators[ticker] = None

            successful_prefetches = sum(1 for v in cached_indicators.values() if v is not None)
            logger.info(f"Pre-fetched {successful_prefetches}/{len(recommendations)} indicators")

        # OPTIMIZATION: Fetch orders once and cache for reuse throughout placement
        # This prevents multiple API calls (5-6x) during buy order placement
        cached_pending_orders = None
        if self.orders:
            try:
                cached_pending_orders = self.orders.get_pending_orders() or []
                logger.debug(f"Cached {len(cached_pending_orders)} pending orders for reuse")
            except Exception as e:
                logger.warning(f"Failed to cache pending orders: {e}, will fetch per-check")
                cached_pending_orders = None

        # Log summary of what we have before proceeding
        logger.info(
            f"Starting order placement: {len(recommendations)} recommendations, "
            f"{len(cached_indicators)} cached indicators, "
            f"{cached_portfolio_count} current positions"
        )

        # Clean up expired failed orders (past market open time)
        # Note: cleanup_expired_failed_orders still uses file-based storage for backward compatibility
        if self.history_path:
            cleanup_expired_failed_orders(self.history_path)

        # Pre-step: If user bought manually (same day or prev day before open), update history and remove from failed queue
        # Note: check_manual_buys_of_failed_orders still uses file-based storage for backward compatibility
        try:
            if self.history_path:
                detected = check_manual_buys_of_failed_orders(
                    self.history_path, self.orders, include_previous_day_before_market=True
                )
            else:
                detected = []
            if detected:
                logger.info(f"Manual buys detected and recorded: {', '.join(detected)}")
        except Exception as e:
            logger.warning(f"Manual buy check failed: {e}")

        # Process new recommendations (retries handled separately at scheduled time)
        open_position_base_symbols: set[str] = set()
        if self.positions_repo and self.user_id:
            try:
                for pos in self.positions_repo.list(self.user_id):
                    if getattr(pos, "closed_at", None) is not None:
                        continue
                    qty = float(getattr(pos, "quantity", 0) or 0)
                    if qty <= 0:
                        continue
                    sym = str(getattr(pos, "symbol", "") or "").upper()
                    if sym:
                        open_position_base_symbols.add(sym.split("-")[0])
            except Exception as open_pos_err:
                logger.warning(
                    f"Open-position guard unavailable in place_new_entries: {open_pos_err}. "
                    "Continuing without DB open-position guard."
                )

        for rec in recommendations:
            base_symbol = self.parse_symbol_for_broker(rec.ticker)  # "SALSTEEL"

            # Resolve symbol to actual broker format early (e.g., "SALSTEEL" -> "SALSTEEL-BE")
            # Scrip master is the SINGLE SOURCE OF TRUTH for symbol resolution
            try:
                broker_symbol = self._resolve_broker_symbol(base_symbol)  # "SALSTEEL-BE"
            except ValueError as e:
                # Scrip master resolution failed - skip this recommendation
                logger.error(f"Failed to resolve symbol {base_symbol} via scrip master: {e}")
                summary["skipped"] += 1
                summary["skipped_missing_data"] += 1  # Also increment specific counter
                ticker_attempt = {
                    "ticker": rec.ticker,
                    "symbol": base_symbol,
                    "verdict": rec.verdict,
                    "status": "skipped",
                    "reason": f"scrip_master_resolution_failed: {str(e)}",
                    "qty": None,
                    "execution_capital": None,
                    "price": None,
                    "order_id": None,
                }
                summary["ticker_attempts"].append(ticker_attempt)
                continue

            if base_symbol.upper() in open_position_base_symbols:
                logger.info(
                    f"Skipping {broker_symbol}: open position already exists for base symbol "
                    f"{base_symbol.upper()} (DB guard)."
                )
                summary["skipped_duplicates"] += 1
                summary["skipped"] += 1
                ticker_attempt = {
                    "ticker": rec.ticker,
                    "symbol": broker_symbol,
                    "verdict": rec.verdict,
                    "status": "skipped",
                    "reason": "open_position_exists",
                    "qty": None,
                    "execution_capital": None,
                    "price": None,
                    "order_id": None,
                }
                summary["ticker_attempts"].append(ticker_attempt)
                continue

            ticker_attempt = {
                "ticker": rec.ticker,
                "symbol": broker_symbol,  # Use resolved symbol
                "verdict": rec.verdict,
                "status": "pending",
                "reason": None,
                "qty": None,
                "execution_capital": None,
                "price": None,
                "order_id": None,
            }

            # Enforce hard portfolio cap before any balance checks (use cached value if available)
            if cached_portfolio_count is not None:
                current_count = cached_portfolio_count
            else:
                # Use PortfolioService for portfolio count
                current_count = self.portfolio_service.get_portfolio_count(include_pending=True)

            # Use OrderValidationService for capacity check (Phase 3.1)
            # OrderValidationService delegates to PortfolioService
            # Note: PortfolioService excludes stale PENDING orders (past next trading day market close) from count
            has_capacity, current_count, max_size = (
                self.order_validation_service.check_portfolio_capacity(include_pending=True)
            )
            if not has_capacity:
                logger.warning(
                    f"Portfolio limit reached ({current_count}/{max_size}); skipping further entries. "
                    f"Note: Stale PENDING orders (past next trading day market close) are excluded from count."
                )
                summary["skipped_portfolio_limit"] += 1
                summary["skipped"] += 1  # Increment general counter
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = "portfolio_limit_reached"
                summary["ticker_attempts"].append(ticker_attempt)
                break
            summary["attempted"] += 1
            # 1) Holding check (use cached holdings if available) - Phase 3.1: Use OrderValidationService for duplicate check
            # Check cached holdings first for performance
            broker_symbol_base = (
                broker_symbol.upper()
                .replace("-EQ", "")
                .replace("-BE", "")
                .replace("-BL", "")
                .replace("-BZ", "")
            )
            if cached_holdings_symbols and broker_symbol_base in cached_holdings_symbols:
                logger.info(
                    f"Skipping {broker_symbol}: already in holdings (cached). "
                    "System does not track existing holdings - keeping portfolios separate."
                )
                summary["skipped_duplicates"] += 1
                summary["skipped"] += 1  # Increment general counter
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = "already_in_holdings"
                summary["ticker_attempts"].append(ticker_attempt)
                # Send notification for skipped order
                if self.telegram_notifier and self.telegram_notifier.enabled:
                    try:
                        self.telegram_notifier.notify_order_skipped(
                            symbol=broker_symbol,
                            reason="already_in_holdings",
                            additional_info={"base_symbol": broker_symbol_base},
                            user_id=self.user_id,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send skipped order notification: {e}")
                continue

            # Use OrderValidationService for duplicate check (includes holdings + active buy orders)
            # Pass cached orders to avoid redundant API calls
            is_duplicate, duplicate_reason = self.order_validation_service.check_duplicate_order(
                broker_symbol,
                check_active_buy_order=False,
                check_holdings=True,
                cached_pending_orders=cached_pending_orders,
            )
            if is_duplicate:
                logger.info(
                    f"Skipping {broker_symbol}: {duplicate_reason}. "
                    "System does not track existing holdings - keeping portfolios separate."
                )
                summary["skipped_duplicates"] += 1
                summary["skipped"] += 1  # Increment general counter
                skip_reason = (
                    "already_in_holdings"
                    if "holdings" in duplicate_reason.lower()
                    else "duplicate_order"
                )
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = skip_reason
                summary["ticker_attempts"].append(ticker_attempt)
                # Send notification for skipped order
                if self.telegram_notifier and self.telegram_notifier.enabled:
                    try:
                        self.telegram_notifier.notify_order_skipped(
                            symbol=broker_symbol,
                            reason=skip_reason,
                            additional_info={
                                "base_symbol": broker_symbol_base,
                                "details": duplicate_reason,
                            },
                            user_id=self.user_id,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send skipped order notification: {e}")
                continue
            # 2) Check for manual AMO orders -> link to DB and skip placing
            # Pass cached orders to avoid redundant API calls
            # Note: _check_for_manual_orders checks by base symbol, but we use resolved symbol for DB
            manual_order_info = self._check_for_manual_orders(
                base_symbol, cached_pending_orders=cached_pending_orders
            )
            if manual_order_info.get("has_manual_order"):
                manual_orders = manual_order_info.get("manual_orders", [])
                if manual_orders:
                    manual_order = manual_orders[0]  # Use first manual order found
                    manual_order_id = manual_order.get("order_id")
                    manual_qty = manual_order.get("quantity", 0)
                    manual_price = manual_order.get("price", 0.0)
                    # Extract actual symbol from manual order (broker format)
                    # order_info dict uses "symbol" key (from OrderFieldExtractor.get_symbol())
                    manual_symbol = manual_order.get("symbol") or broker_symbol

                    logger.info(
                        f"Manual AMO order detected for {broker_symbol}: order_id={manual_order_id}, "
                        f"qty={manual_qty}, price={manual_price}. "
                        "Skipping new order placement and updating DB with existing order details."
                    )

                    # Create/update DB order with manual order details
                    if self.orders_repo and self.user_id:
                        # Check if order already exists in DB
                        existing_order = self.orders_repo.get_by_broker_order_id(
                            self.user_id, manual_order_id
                        )

                        if existing_order:
                            # Update existing order
                            self.orders_repo.update(
                                existing_order,
                                quantity=manual_qty,
                                price=manual_price if manual_price > 0 else None,
                                status=DbOrderStatus.PENDING,
                            )
                            logger.info(
                                f"Updated existing DB order {existing_order.id} for {manual_symbol} "
                                f"with manual order details"
                            )
                        else:
                            # Create new order record for manual order
                            # Use actual symbol from broker order (manual_symbol) or resolved symbol
                            db_order = self.orders_repo.create_amo(
                                user_id=self.user_id,
                                symbol=manual_symbol,  # Use actual symbol from broker order
                                side="buy",
                                order_type="market",  # AMO orders are typically market
                                quantity=manual_qty,
                                price=manual_price if manual_price > 0 else None,
                                order_id=manual_order_id,
                                broker_order_id=manual_order_id,
                            )
                            db_order.status = DbOrderStatus.PENDING
                            self.orders_repo.update(db_order)
                            logger.info(
                                f"Created new DB order {db_order.id} for {manual_symbol} "
                                f"with manual order details"
                            )

                    summary["skipped_duplicates"] += 1
                    summary["skipped"] += 1  # Increment general counter
                    ticker_attempt["status"] = "skipped"
                    ticker_attempt["reason"] = "manual_order_exists"
                    ticker_attempt["qty"] = manual_qty
                    ticker_attempt["order_id"] = manual_order_id
                    summary["ticker_attempts"].append(ticker_attempt)
                    continue

            # 3) Active pending buy order check (system orders)
            # Phase 3.1: Use OrderValidationService for duplicate check (broker API + database)
            # This prevents duplicates when service runs multiple times before broker syncs
            # Pass cached orders to avoid redundant API calls
            is_duplicate_order, duplicate_order_reason = (
                self.order_validation_service.check_duplicate_order(
                    broker_symbol,
                    check_active_buy_order=True,
                    check_holdings=False,  # Already checked holdings above
                    cached_pending_orders=cached_pending_orders,
                )
            )

            variants = set(self._symbol_variants(broker_symbol))
            broker_symbol_base = (
                broker_symbol.upper()
                .replace("-EQ", "")
                .replace("-BE", "")
                .replace("-BL", "")
                .replace("-BZ", "")
            )

            # Check database for existing buy orders
            # This prevents duplicates when service runs multiple times before broker syncs
            # Status handling:
            # - PENDING, FAILED: Can be updated/cancelled if params change (merged statuses)
            # - ONGOING: Already executed, skip (position exists)
            # - CLOSED: Completed trade, allow new buy opportunity (don't block)
            # - CANCELLED: Cancelled order, allow new buy opportunity (don't block)
            # - SELL: Only for sell orders (side="sell"), excluded by side filter
            has_db_order = False
            existing_db_order = None
            if self.orders_repo and self.user_id:
                try:
                    existing_orders, _ = self.orders_repo.list(self.user_id)
                    for existing_order in existing_orders:
                        order_symbol_base = (
                            existing_order.symbol.upper()
                            .replace("-EQ", "")
                            .replace("-BE", "")
                            .replace("-BL", "")
                            .replace("-BZ", "")
                        )
                        if (
                            existing_order.side == "buy"  # Only check buy orders
                            and existing_order.status
                            in {
                                DbOrderStatus.PENDING,  # Merged: AMO + PENDING_EXECUTION
                                DbOrderStatus.ONGOING,
                                DbOrderStatus.FAILED,  # Merged: FAILED + RETRY_PENDING + REJECTED
                                # Note: CLOSED and CANCELLED orders are NOT included here
                                # because they represent completed/cancelled trades and should
                                # NOT block new buy opportunities for the same stock
                                # Note: SELL status removed - use side='sell' to identify sell orders
                            }
                            and order_symbol_base == broker_symbol_base
                        ):
                            has_db_order = True
                            existing_db_order = existing_order
                            break
                except Exception as e:
                    logger.warning(
                        f"Database check for active buy order failed for {broker_symbol}: {e}. "
                        "Falling back to broker API check."
                    )

            # If database has an order, we'll check if quantity needs to be updated after calculating new quantity
            # Skip if database has executed order (ONGOING legacy or CLOSED = filled, cannot update)
            if has_db_order and existing_db_order:
                if existing_db_order.status in (DbOrderStatus.ONGOING, DbOrderStatus.CLOSED):
                    logger.info(
                        f"Skipping {broker_symbol}: already has executed buy order in database "
                        f"(status: {existing_db_order.status}, order_id: {existing_db_order.id}). "
                        "Order already executed, cannot update quantity."
                    )
                    summary["skipped_duplicates"] += 1
                    summary["skipped"] += 1  # Increment general counter
                    ticker_attempt["status"] = "skipped"
                    ticker_attempt["reason"] = "active_order_in_db"
                    ticker_attempt["existing_order_id"] = existing_db_order.id
                    summary["ticker_attempts"].append(ticker_attempt)
                    continue

            # Check broker API for pending orders (only if database doesn't have order or order is not executed)
            # If broker has pending order, cancel and replace
            # OPTIMIZATION: Use cached orders if available to avoid redundant API calls
            if self.orders:
                try:
                    # Use cached orders if provided, otherwise fetch
                    if cached_pending_orders is not None:
                        pend = cached_pending_orders
                    else:
                        pend = self.orders.get_pending_orders() or []
                    has_broker_order = False
                    for o in pend:
                        txn = str(o.get("transactionType") or "").upper()
                        sym = str(o.get("tradingSymbol") or "").upper()
                        if txn.startswith("B") and sym in variants:
                            has_broker_order = True
                            break

                    if has_broker_order:
                        try:
                            cancelled = self.orders.cancel_pending_buys_for_symbol(list(variants))
                            logger.info(
                                f"Cancelled {cancelled} pending BUY order(s) for {broker_symbol}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Could not cancel pending order(s) for {broker_symbol}: {e}"
                            )
                            # If cancel fails, skip to prevent duplicates
                            summary["skipped_duplicates"] += 1
                            summary["skipped"] += 1  # Increment general counter
                            ticker_attempt["status"] = "skipped"
                            ticker_attempt["reason"] = "cancel_failed"
                            summary["ticker_attempts"].append(ticker_attempt)
                            continue
                except Exception as e:
                    logger.warning(
                        f"Broker API check for active buy order failed for {broker_symbol}: {e}. "
                        "Proceeding with order placement (database check already passed)."
                    )

            # If OrderValidationService detected duplicate order from broker API, handle it
            # (Note: Database orders are already handled above for update/cancel logic)
            if is_duplicate_order and not has_db_order:
                # Duplicate detected by OrderValidationService (broker API or database)
                logger.info(
                    f"Skipping {broker_symbol}: {duplicate_order_reason}. "
                    "Will not place duplicate order."
                )
                summary["skipped_duplicates"] += 1
                summary["skipped"] += 1  # Increment general counter
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = "duplicate_order"
                summary["ticker_attempts"].append(ticker_attempt)
                continue

            # Use cached indicators if available, otherwise fetch
            ind = cached_indicators.get(rec.ticker)
            if ind is None:
                logger.debug(f"Cache miss for {rec.ticker}, fetching fresh indicators")
                ind = self.get_daily_indicators(rec.ticker)
            else:
                logger.debug(f"Cache hit for {rec.ticker}, close={ind.get('close', 'N/A')}")

            if not ind or any(k not in ind for k in ("close", "rsi10", "ema9", "ema200")):
                logger.warning(f"Skipping {rec.ticker}: missing indicators")
                summary["skipped_missing_data"] += 1
                summary["skipped"] += 1  # Increment general counter
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = "missing_indicators"
                summary["ticker_attempts"].append(ticker_attempt)
                continue
            raw_close = ind["close"]
            try:
                close = float(raw_close)
            except (TypeError, ValueError):
                close = 0.0
            logger.info(f"{rec.ticker}: Using close price = Rs {close:.2f} from indicators")
            if not isfinite(close) or close <= 0:
                logger.warning(f"Skipping {rec.ticker}: invalid close price {close}")
                summary["skipped_invalid_qty"] += 1
                summary["skipped"] += 1  # Increment general counter
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = "invalid_price"
                ticker_attempt["price"] = close
                summary["ticker_attempts"].append(ticker_attempt)
                continue
            ticker_attempt["price"] = close

            # Phase 11: Always recalculate execution_capital to respect current user config
            # This ensures that if user changes capital config, new orders use the new value
            # even if the recommendation has a stored execution_capital from previous analysis
            avg_vol = ind.get("avg_volume", 0)
            stored_execution_capital = rec.execution_capital
            execution_capital = self._calculate_execution_capital(rec.ticker, close, avg_vol)

            # Log if capital changed from stored value
            if (
                stored_execution_capital
                and stored_execution_capital > 0
                and stored_execution_capital != execution_capital
            ):
                logger.info(
                    f"{rec.ticker}: Execution capital updated from stored Rs {stored_execution_capital:,.0f} "
                    f"to Rs {execution_capital:,.0f} (current user_capital: Rs {self.strategy_config.user_capital:,.0f})"
                )
            else:
                logger.debug(
                    f"Calculated execution_capital for {rec.ticker}: Rs {execution_capital:,.0f} "
                    f"(using user_capital: Rs {self.strategy_config.user_capital:,.0f})"
                )

            # Phase 11: Log if capital was adjusted from user_capital
            if execution_capital < self.strategy_config.user_capital:
                logger.info(
                    f"{broker_symbol}: Capital adjusted due to liquidity: "
                    f"Rs {execution_capital:,.0f} (requested: Rs {self.strategy_config.user_capital:,.0f})"
                )

            qty = max(config.MIN_QTY, floor(execution_capital / close))

            # If database has an existing PENDING order, check if quantity or price needs to be updated
            # due to capital change (e.g., user updated capital per trade config) or price change
            if has_db_order and existing_db_order:
                # Update quantity/price for orders that can still be modified
                # Skip ONGOING orders (already executed, cannot update)
                # Skip CLOSED/CANCELLED orders (already finalized)
                # Handle PENDING/FAILED orders (merged statuses)
                if existing_db_order.status in {
                    DbOrderStatus.PENDING,  # Merged: AMO + PENDING_EXECUTION
                    DbOrderStatus.FAILED,  # Merged: FAILED + RETRY_PENDING + REJECTED
                }:
                    existing_qty = existing_db_order.quantity or 0
                    existing_price = existing_db_order.price or 0.0

                    # Check if quantity or price has changed (any change triggers update)
                    qty_changed = existing_qty > 0 and qty != existing_qty
                    price_changed = (
                        existing_price > 0 and abs(close - existing_price) > 0.01
                    )  # 1 paisa tolerance for float comparison

                    if qty_changed or price_changed:
                        # Any change in quantity or price triggers order update
                        changes = []
                        if qty_changed:
                            changes.append(f"qty: {existing_qty} -> {qty}")
                        if price_changed:
                            changes.append(f"price: Rs {existing_price:.2f} -> Rs {close:.2f}")

                        logger.info(
                            f"Order parameters updated for {broker_symbol}: {', '.join(changes)}. "
                            f"Cancelling existing order and placing new order with updated parameters."
                        )

                        # Cancel existing order from broker (if still pending)
                        variants = set(self._symbol_variants(broker_symbol))
                        try:
                            if self.orders:
                                cancelled = self.orders.cancel_pending_buys_for_symbol(
                                    list(variants)
                                )
                                logger.info(
                                    f"Cancelled {cancelled} existing order(s) for {broker_symbol}"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Could not cancel existing order for {broker_symbol}: {e}"
                            )
                            # Continue anyway - will place new order

                        # Update existing DB order status to CANCELLED (replaced due to parameter change)
                        try:
                            self.orders_repo.update(
                                existing_db_order,
                                status=DbOrderStatus.CANCELLED,
                                cancelled_reason="Order cancelled due to parameter update (qty/price changed)",
                            )
                            logger.info(
                                f"Marked existing DB order {existing_db_order.id} as CANCELLED "
                                f"(replaced with new order due to parameter update)"
                            )
                        except Exception as e:
                            logger.warning(f"Could not update existing DB order status: {e}")

                        # Continue to place new order with updated quantity/price
                        # (has_db_order will be ignored, we've already cancelled the old one)
                    else:
                        # Quantity and price unchanged, skip placing new order
                        logger.info(
                            f"Skipping {broker_symbol}: already has active buy order in database "
                            f"(status: {existing_db_order.status}, order_id: {existing_db_order.id}). "
                            f"Quantity and price unchanged (qty={existing_qty}, price=Rs {existing_price:.2f})."
                        )
                        summary["skipped_duplicates"] += 1
                        summary["skipped"] += 1  # Increment general counter
                        ticker_attempt["status"] = "skipped"
                        ticker_attempt["reason"] = "active_order_in_db"
                        ticker_attempt["existing_order_id"] = existing_db_order.id
                        summary["ticker_attempts"].append(ticker_attempt)
                        continue
                elif existing_db_order.status in (DbOrderStatus.ONGOING, DbOrderStatus.CLOSED):
                    # Order is executed (ONGOING legacy or CLOSED = filled), skip
                    logger.info(
                        f"Skipping {broker_symbol}: already has executed buy order in database "
                        f"(status: {existing_db_order.status}, order_id: {existing_db_order.id}). "
                        "Order already executed, cannot update quantity/price."
                    )
                    summary["skipped_duplicates"] += 1
                    summary["skipped"] += 1  # Increment general counter
                    ticker_attempt["status"] = "skipped"
                    ticker_attempt["reason"] = "active_order_in_db"
                    ticker_attempt["existing_order_id"] = existing_db_order.id
                    summary["ticker_attempts"].append(ticker_attempt)
                    continue
                # else: CLOSED/CANCELLED orders - allow new order placement (don't block)
                # These represent completed/cancelled trades and should not prevent new opportunities

            # Check position-to-volume ratio (liquidity filter) - Phase 3.1: Use OrderValidationService
            avg_vol = ind.get("avg_volume", 0)
            is_valid_volume, volume_ratio, tier_info = (
                self.order_validation_service.check_volume_ratio(qty, avg_vol, broker_symbol, close)
            )
            if not is_valid_volume:
                logger.info(f"Skipping {broker_symbol}: position size too large relative to volume")
                summary["skipped_invalid_qty"] += 1
                summary["skipped"] += 1  # Increment general counter
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = "position_too_large_for_volume"
                ticker_attempt["qty"] = qty
                ticker_attempt["execution_capital"] = execution_capital
                summary["ticker_attempts"].append(ticker_attempt)
                continue

            # Balance check (CNC needs cash) via check-margin API.
            margin_result = self._check_order_margin(
                symbol=broker_symbol,
                price=close,
                qty=qty,
                transaction_type="B",
                product="CNC",
            )
            if len(margin_result) == 4:
                has_sufficient_balance, avail_cash, required_cash, shortfall = margin_result
                margin_api_ok = True
            else:
                (
                    has_sufficient_balance,
                    avail_cash,
                    required_cash,
                    shortfall,
                    margin_api_ok,
                ) = margin_result
            affordable = int((avail_cash or 0.0) // close) if close > 0 else 0
            if not margin_api_ok:
                logger.error(
                    f"Margin check failed for {broker_symbol}; skipping order "
                    "(not an insufficient-balance verdict)."
                )
                ticker_attempt["status"] = "failed"
                ticker_attempt["reason"] = "margin_check_failed"
                ticker_attempt["qty"] = qty
                ticker_attempt["execution_capital"] = execution_capital
                summary["ticker_attempts"].append(ticker_attempt)

                failed_order_info = {
                    "symbol": broker_symbol,
                    "ticker": rec.ticker,
                    "close": close,
                    "qty": qty,
                    "required_cash": qty * close,
                    "shortfall": 0.0,
                    "reason": "margin_check_failed",
                    "verdict": rec.verdict,
                    "rsi10": ind.get("rsi10"),
                    "ema9": ind.get("ema9"),
                    "ema200": ind.get("ema200"),
                    "execution_capital": execution_capital,
                    "non_retryable": True,
                }
                try:
                    self._add_failed_order(failed_order_info)
                except Exception as db_err:
                    logger.warning(f"Failed to persist margin_check_failed order: {db_err}")
                summary["skipped"] += 1
                continue

            if not has_sufficient_balance:
                # Telegram message with emojis
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                telegram_msg = (
                    f"💰 *Insufficient Balance - AMO BUY*\n\n"
                    f"Symbol: `{broker_symbol}`\n"
                    f"Needed: Rs {required_cash:,.0f} for {qty} @ Rs {close:.2f}\n"
                    f"Available: Rs {(avail_cash or 0.0):,.0f}\n"
                    f"Shortfall: Rs {shortfall:,.0f}\n\n"
                    f"Order status updated in database. Will be retried at scheduled time (8:00 AM) or manually.\n\n"
                    f"_Time: {timestamp}_"
                )
                # Use TelegramNotifier to respect notification preferences
                if self.telegram_notifier and self.telegram_notifier.enabled:
                    try:
                        self.telegram_notifier.notify_system_alert(
                            alert_type="BALANCE_SHORTFALL",
                            message_text=telegram_msg,
                            severity="WARNING",
                            user_id=self.user_id,
                        )
                    except Exception as notify_err:
                        logger.warning(
                            f"Failed to send balance shortfall notification: {notify_err}"
                        )
                else:
                    # Fallback to old method if telegram_notifier not available (backward compatibility)
                    send_telegram(telegram_msg)

                # Logger message without emojis
                logger.warning(
                    f"Insufficient balance for {broker_symbol} AMO BUY. "
                    f"Needed: Rs.{required_cash:,.0f} for {qty} @ Rs.{close:.2f}. "
                    f"Available: Rs.{(avail_cash or 0.0):,.0f}. Shortfall: Rs.{shortfall:,.0f}. "
                    f"Order status updated in database. Will be retried at scheduled time or manually."
                )

                # Create order in DB with FAILED status for scheduled retry
                failed_order_info = {
                    "symbol": broker_symbol,
                    "ticker": rec.ticker,
                    "close": close,
                    "qty": qty,
                    "required_cash": required_cash,
                    "shortfall": shortfall,
                    "reason": "insufficient_balance",
                    "verdict": rec.verdict,
                    "rsi10": ind.get("rsi10"),
                    "ema9": ind.get("ema9"),
                    "ema200": ind.get("ema200"),
                    "execution_capital": execution_capital,  # Phase 11: Save execution_capital for retry
                }
                self._add_failed_order(failed_order_info)
                summary["failed_balance"] += 1
                summary["skipped_invalid_qty"] += 1
                summary["skipped"] += 1  # Increment general counter
                ticker_attempt["status"] = "failed"
                ticker_attempt["reason"] = "insufficient_balance"
                ticker_attempt["qty"] = qty
                ticker_attempt["execution_capital"] = execution_capital
                ticker_attempt["required_cash"] = required_cash
                ticker_attempt["available_cash"] = avail_cash
                ticker_attempt["shortfall"] = shortfall
                summary["ticker_attempts"].append(ticker_attempt)
                continue

            # Try placing order (get recommendation source if available)
            rec_source = getattr(self, "_custom_csv_path", None) or "system_recommendation"
            success, order_id = self._attempt_place_order(
                broker_symbol,
                rec.ticker,
                qty,
                close,
                ind,
                recommendation_source=rec_source,
                entry_type="initial",
                order_metadata={
                    "placed_symbol": broker_symbol,
                    "ticker": rec.ticker,
                    "rsi10": ind.get("rsi10"),
                    "ema9": ind.get("ema9"),
                    "ema200": ind.get("ema200"),
                    "capital": ind.get("capital"),
                    "rsi_entry_level": ind.get("rsi_entry_level"),
                    "entry_type": "initial",
                    "verdict": getattr(rec, "verdict", None),
                },
            )
            if success:
                summary["placed"] += 1
                logger.info(f"Order placed: {broker_symbol} (order_id: {order_id})")
                ticker_attempt["status"] = "placed"
                ticker_attempt["qty"] = qty
                ticker_attempt["execution_capital"] = execution_capital
                ticker_attempt["order_id"] = order_id
                summary["ticker_attempts"].append(ticker_attempt)
            else:
                # Broker/API error - log and continue with other recommendations
                # Don't stop the entire run for one failed order
                error_msg = (
                    f"Broker/API error while placing order for {broker_symbol}. "
                    "Skipping this order and continuing with other recommendations."
                )
                logger.error(error_msg)
                ticker_attempt["status"] = "failed"
                ticker_attempt["reason"] = "broker_api_error"
                ticker_attempt["qty"] = qty
                ticker_attempt["execution_capital"] = execution_capital
                summary["ticker_attempts"].append(ticker_attempt)

                # Save failed order to database for tracking (but mark as non-retryable)
                failed_order_info = {
                    "symbol": broker_symbol,
                    "ticker": rec.ticker,
                    "close": close,
                    "qty": qty,
                    "required_cash": qty * close,
                    "shortfall": 0.0,  # Not a balance issue
                    "reason": "broker_api_error",
                    "verdict": rec.verdict,
                    "rsi10": ind.get("rsi10"),
                    "ema9": ind.get("ema9"),
                    "ema200": ind.get("ema200"),
                    "execution_capital": execution_capital,
                    "non_retryable": True,  # Mark as non-retryable since it's a broker API issue
                }
                try:
                    self._add_failed_order(failed_order_info)
                except Exception as e:
                    logger.warning(f"Failed to save broker API error to database: {e}")

                # Continue with next recommendation instead of raising exception
                continue
        return summary

    # ---------------------- Re-entry and exit ----------------------
    def place_reentry_orders(self) -> dict[str, int]:
        """
        Check re-entry conditions and place AMO orders for re-entries.

        Called at 4:05 PM (with buy orders).

        Re-entry logic based on entry RSI level:
        - Entry at RSI < 30 → Re-entry at RSI < 20 → RSI < 10 → Reset
        - Entry at RSI < 20 → Re-entry at RSI < 10 → Reset
        - Entry at RSI < 10 → Only Reset

        Reset mechanism:
        - When RSI > 30: Set reset_ready = True
        - When RSI drops < 30 after reset_ready: Reset all levels

        Returns:
            Summary dict with re-entry statistics
        """
        summary = {
            "attempted": 0,
            "placed": 0,
            "failed_balance": 0,
            "skipped_no_position": 0,
            "skipped_duplicates": 0,
            "skipped_duplicate_level": 0,  # Re-entry at same level already placed today
            "skipped_invalid_rsi": 0,
            "skipped_missing_data": 0,
            "skipped_invalid_qty": 0,
        }

        # Check if authenticated
        if not self.auth or not self.auth.is_authenticated():
            logger.warning("Session expired - attempting re-authentication...")
            if not self.login():
                logger.error("Re-authentication failed - cannot proceed")
                return summary
            logger.info("Re-authentication successful - proceeding with re-entry check")

        if not self.orders or not self.portfolio:
            logger.error("Orders or portfolio not initialized - attempting login...")
            if not self.login():
                logger.error("Login failed - cannot proceed")
                return summary

        # Load all open positions from database
        if not self.positions_repo or not self.user_id:
            logger.warning(
                "Positions repository or user_id not available - skipping re-entry check"
            )
            return summary

        # Manual Trade Detection Timing Fix: Reconcile positions before placing reentry orders
        # This ensures we detect manual trades that happened during market hours
        if hasattr(self, "sell_manager") and self.sell_manager:
            try:
                reconciliation_stats = self.sell_manager._reconcile_positions_with_broker_holdings()
                if (
                    reconciliation_stats.get("updated", 0) > 0
                    or reconciliation_stats.get("closed", 0) > 0
                ):
                    logger.info(
                        f"Reconciliation before reentry placement: "
                        f"{reconciliation_stats.get('updated', 0)} positions updated, "
                        f"{reconciliation_stats.get('closed', 0)} positions closed"
                    )
            except Exception as e:
                logger.warning(
                    f"Reconciliation before reentry placement failed: {e}. Continuing..."
                )

        open_positions = self.positions_repo.list(self.user_id)
        open_positions = [pos for pos in open_positions if pos.closed_at is None]

        if not open_positions:
            logger.info("No open positions for re-entry check")
            return summary

        logger.info(f"Checking re-entry conditions for {len(open_positions)} open positions...")
        from datetime import time as dt_time

        from core.volume_analysis import is_market_hours

        # Re-entry RSI source policy:
        # - At/after market close on trading days, use current day close-inclusive RSI.
        # - During next-day market hours, keep using previous closed-day RSI snapshot
        #   until the next post-close evaluation window.
        now_time = datetime.now().time()
        market_close = dt_time(15, 30)
        use_latest_rsi_after_close = (
            self.is_trading_weekday()
            and (not is_market_hours())
            and now_time >= market_close
        )

        # Get portfolio snapshot for capacity checks
        if self.portfolio_service:
            if self.portfolio and self.portfolio_service.portfolio != self.portfolio:
                self.portfolio_service.portfolio = self.portfolio
            if self.orders and self.portfolio_service.orders != self.orders:
                self.portfolio_service.orders = self.orders

        for position in open_positions:
            symbol = position.symbol
            entry_rsi = position.entry_rsi

            if entry_rsi is None:
                logger.warning(
                    f"Skipping {symbol}: missing entry_rsi on open position. "
                    "Re-entry requires actual entry RSI; no synthetic default applied."
                )
                summary["skipped_missing_data"] += 1
                continue

            summary["attempted"] += 1

            try:
                # Construct market-data ticker from position symbol.
                # Positions store full trading symbols like "INDIAGLYCO-EQ", but indicator services
                # expect exchange tickers like "INDIAGLYCO.NS".
                base_symbol = (
                    symbol.replace(".NS", "")
                    .replace(".BO", "")
                    .replace("-EQ", "")
                    .replace("-BE", "")
                    .replace("-BL", "")
                    .replace("-BZ", "")
                )
                ticker = (
                    base_symbol if base_symbol.endswith((".NS", ".BO")) else f"{base_symbol}.NS"
                )

                # Get current indicators
                uses_default_get_daily_indicators = (
                    self.get_daily_indicators is AutoTradeEngine.get_daily_indicators
                )
                if self.indicator_service and uses_default_get_daily_indicators:
                    ind = self.indicator_service.get_daily_indicators_dict(
                        ticker=ticker,
                        rsi_period=None,
                        config=self.strategy_config,
                        add_current_day=use_latest_rsi_after_close,
                    )
                else:
                    ind = self.get_daily_indicators(ticker)
                if not ind:
                    logger.warning(f"Skipping {symbol}: missing indicators for re-entry evaluation")
                    summary["skipped_missing_data"] += 1
                    continue

                current_rsi = ind.get("rsi10")
                current_price = ind.get("close")
                avg_volume = ind.get("avg_volume", 0)

                if current_rsi is None or current_price is None:
                    logger.warning(f"Skipping {symbol}: invalid indicators (RSI or price missing)")
                    summary["skipped_missing_data"] += 1
                    continue

                # Re-entry safety guard:
                # Reject clearly anomalous prices when at least one stable reference exists.
                # This protects sizing from stale/cross-symbol indicator payloads.
                try:
                    current_price = float(current_price)
                except (TypeError, ValueError):
                    logger.warning(
                        f"Skipping {symbol}: current_price is not numeric ({current_price!r})"
                    )
                    summary["skipped_missing_data"] += 1
                    continue

                if not isfinite(current_price) or current_price <= 0:
                    logger.warning(f"Skipping {symbol}: invalid current_price ({current_price})")
                    summary["skipped_missing_data"] += 1
                    continue

                reference_prices: list[float] = []
                for candidate in (
                    getattr(position, "avg_price", None),
                    getattr(position, "entry_price", None),
                    ind.get("ema200"),
                ):
                    try:
                        value = float(candidate)
                    except (TypeError, ValueError):
                        continue
                    if isfinite(value) and value > 0:
                        reference_prices.append(value)

                # Keep the guard broad to avoid false positives:
                # allow 65% drawdown to 3x from any available reference.
                # Apply only when at least one reference is available.
                if reference_prices and not any(
                    (ref * 0.35) <= current_price <= (ref * 3.0) for ref in reference_prices
                ):
                    logger.warning(
                        f"Skipping {symbol}: current_price looks anomalous for re-entry sizing "
                        f"(current_price={current_price}, references={reference_prices})"
                    )
                    summary["skipped_missing_data"] += 1
                    continue

                # Determine next re-entry level based on entry RSI
                # Enhanced Hybrid Approach: Returns (next_level, metadata_updates)
                # Get cycle before to detect if reset happened
                cycle_meta_before = self._get_position_cycle_metadata(position)
                cycle_before = cycle_meta_before.get("current_cycle", 0)

                next_level, metadata_updates = self._determine_reentry_level(
                    entry_rsi, current_rsi, position
                )

                # Detect if reset happened (cycle was incremented)
                is_reset = (
                    metadata_updates.get("current_cycle") is not None
                    and metadata_updates.get("current_cycle") > cycle_before
                )

                # Update position metadata if needed (cycle tracking, reset detection)
                if any(v is not None for v in metadata_updates.values()):
                    try:
                        # Get current cycle metadata
                        cycle_meta = self._get_position_cycle_metadata(position)
                        current_cycle = cycle_meta.get("current_cycle", 0)

                        # Apply metadata updates
                        updated_reentries = self._set_position_cycle_metadata(
                            position,
                            current_cycle=metadata_updates.get("current_cycle") or current_cycle,
                            last_rsi_above_30=metadata_updates.get("last_rsi_above_30"),
                            last_rsi_value=metadata_updates.get("last_rsi_value"),
                        )

                        # Update position in database
                        self.positions_repo.upsert(
                            user_id=self.user_id,
                            symbol=symbol,
                            quantity=position.quantity,
                            avg_price=position.avg_price,
                            reentries=updated_reentries,
                            auto_commit=True,
                        )

                        # Refresh position object to get updated metadata
                        position = self.positions_repo.get_by_symbol(self.user_id, symbol)
                        if not position:
                            logger.warning(f"Position {symbol} not found after metadata update")
                            summary["skipped_missing_data"] += 1
                            continue

                        if metadata_updates.get("current_cycle") is not None:
                            logger.info(
                                f"Updated cycle metadata for {symbol}: "
                                f"current_cycle={updated_reentries['_cycle_metadata']['current_cycle']}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Failed to update cycle metadata for {symbol}: {e}. "
                            f"Continuing with re-entry check..."
                        )

                if next_level is None:
                    logger.debug(
                        f"No re-entry opportunity for {symbol} "
                        f"(entry_rsi={entry_rsi:.2f}, current_rsi={current_rsi:.2f})"
                    )
                    summary["skipped_invalid_rsi"] += 1
                    continue

                # Get current cycle for logging and order metadata
                # Use refreshed position object if metadata was updated
                cycle_meta = self._get_position_cycle_metadata(position)
                current_cycle = cycle_meta.get("current_cycle", 0)

                logger.info(
                    f"Re-entry opportunity for {symbol}: entry_rsi={entry_rsi:.2f}, "
                    f"current_rsi={current_rsi:.2f}, next_level={next_level}, "
                    f"cycle={current_cycle}, is_reset={is_reset}"
                )

                # Check if re-entry at this level already exists in current cycle
                # Enhanced Hybrid Approach: Checks by cycle number, allowing same level after reset
                # Fix Issue 1: Pass allow_reset=True when reset is detected, regardless of level
                if self.has_reentry_at_level(symbol, next_level, allow_reset=is_reset):
                    logger.info(
                        f"Skipping {symbol}: Re-entry at level {next_level} (RSI < {next_level}) "
                        f"already exists in cycle {current_cycle}. "
                        f"Next re-entry should be at a different level or after reset."
                    )
                    summary["skipped_duplicate_level"] = (
                        summary.get("skipped_duplicate_level", 0) + 1
                    )
                    continue

                # Check for duplicates (only active buy orders, NOT holdings)
                # Reentries allow buying more of existing position
                base_symbol = self.parse_symbol_for_broker(ticker)
                if not base_symbol:
                    logger.warning(f"Could not parse broker symbol for {symbol}")
                    summary["skipped_missing_data"] += 1
                    continue

                # Resolve symbol via scrip master (single source of truth)
                try:
                    broker_symbol = self._resolve_broker_symbol(base_symbol)
                except ValueError as e:
                    logger.error(
                        f"Failed to resolve symbol {base_symbol} via scrip master for re-entry: {e}"
                    )
                    summary["skipped_missing_data"] += 1
                    continue

                # Check for active BUY orders only (not SELL orders)
                # Re-entry should be allowed even if there's an open SELL order
                # Use has_active_buy_order which correctly filters by side='buy'
                if self.has_active_buy_order(broker_symbol):
                    logger.info(
                        f"Skipping {symbol}: Active BUY order exists for {broker_symbol} "
                        "(re-entry blocked to prevent duplicate buy orders)"
                    )
                    summary["skipped_duplicates"] += 1
                    continue

                # Calculate execution capital and quantity
                execution_capital = self._calculate_execution_capital(
                    ticker, current_price, avg_volume
                )
                qty = int(execution_capital / current_price)

                logger.info(
                    f"Re-entry quantity calculation for {symbol}: "
                    f"execution_capital={execution_capital}, current_price={current_price}, "
                    f"avg_volume={avg_volume}, calculated_qty={qty}"
                )

                if qty <= 0:
                    logger.warning(f"Skipping {symbol}: invalid quantity ({qty})")
                    summary["skipped_invalid_qty"] += 1
                    continue

                # Check balance and adjust quantity if needed
                affordable_qty = self.get_affordable_qty(current_price)
                if affordable_qty < qty:
                    logger.warning(
                        f"Insufficient balance for {symbol}: "
                        f"requested={qty}, affordable={affordable_qty}"
                    )
                    qty = affordable_qty
                    if qty <= 0:
                        # Save as failed order for retry
                        failed_order_info = {
                            "symbol": broker_symbol,
                            "ticker": ticker,
                            "close": current_price,
                            "qty": qty,
                            "required_cash": execution_capital,
                            "shortfall": execution_capital - (affordable_qty * current_price),
                            "reason": "insufficient_balance",
                            "rsi10": current_rsi,
                            "ema9": ind.get("ema9"),
                            "ema200": ind.get("ema200"),
                            "execution_capital": execution_capital,
                            "entry_type": "reentry",
                            "entry_rsi": entry_rsi,
                            "reentry_level": next_level,
                        }
                        try:
                            self._add_failed_order(failed_order_info)
                            summary["failed_balance"] += 1
                        except Exception as e:
                            logger.warning(f"Failed to save re-entry order to failed orders: {e}")
                        continue

                # Place re-entry order (AMO-like)
                # Enhanced Hybrid Approach: Include cycle number in order metadata
                rec_source = "reentry"
                cycle_meta = self._get_position_cycle_metadata(position)
                current_cycle = cycle_meta.get("current_cycle", 0)

                success, order_id = self._attempt_place_order(
                    broker_symbol,
                    ticker,
                    qty,
                    current_price,
                    ind,
                    recommendation_source=rec_source,
                    entry_type="reentry",
                    order_metadata={
                        "placed_symbol": broker_symbol,
                        "ticker": ticker,
                        "rsi10": current_rsi,
                        "ema9": ind.get("ema9"),
                        "ema200": ind.get("ema200"),
                        "capital": execution_capital,
                        "entry_type": "reentry",
                        "entry_rsi": entry_rsi,
                        "reentry_level": next_level,
                        "cycle": current_cycle,  # Store cycle number for tracking
                    },
                )

                if success:
                    summary["placed"] += 1
                    logger.info(
                        f"Re-entry order placed: {symbol} (order_id: {order_id}, "
                        f"qty: {qty}, level: {next_level})"
                    )
                else:
                    logger.warning(f"Failed to place re-entry order for {symbol}")

            except Exception as e:
                logger.error(f"Error checking re-entry for {symbol}: {e}", exc_info=True)
                continue

        skipped_total = (
            summary["skipped_no_position"]
            + summary["skipped_duplicates"]
            + summary["skipped_invalid_rsi"]
            + summary["skipped_missing_data"]
            + summary["skipped_invalid_qty"]
        )
        logger.info(
            f"Re-entry check complete: attempted={summary['attempted']}, "
            f"placed={summary['placed']}, failed_balance={summary['failed_balance']}, "
            f"skipped={skipped_total}"
        )

        return summary

    def _determine_reentry_level(
        self, entry_rsi: float, current_rsi: float, position: Any
    ) -> tuple[int | None, dict[str, Any]]:
        """
        Determine next re-entry level based on entry RSI and current RSI.

        Enhanced Hybrid Approach: Implements cycle tracking with reset detection on startup.

        Logic:
        - Entry at RSI < 30 → Re-entry at RSI < 20 → RSI < 10 → Reset
        - Entry at RSI < 20 → Re-entry at RSI < 10 → Reset
        - Entry at RSI < 10 → Only Reset

        Reset mechanism:
        - When RSI > 30: Store last_rsi_above_30 timestamp in position metadata
        - When RSI drops < 30 after last_rsi_above_30 exists: Increment current_cycle, reset all levels
        - On startup: Check if current RSI < 30 and last_rsi_above_30 exists → Reset detected

        Args:
            entry_rsi: RSI10 value at initial entry
            current_rsi: Current RSI10 value
            position: Position object (for tracking reset state)

        Returns:
            Tuple of (next_level, metadata_updates):
            - next_level: Next re-entry level (30, 20, or 10), or None if no re-entry opportunity
            - metadata_updates: Dict with cycle metadata updates to apply:
              {
                  "current_cycle": int | None,  # None = no change
                  "last_rsi_above_30": str | None,  # ISO timestamp or None to clear
                  "last_rsi_value": float | None,  # None = no change
              }
        """
        from src.infrastructure.db.timezone_utils import ist_now

        # Get current cycle metadata
        cycle_meta = self._get_position_cycle_metadata(position)
        current_cycle = cycle_meta.get("current_cycle", 0)
        last_rsi_above_30 = cycle_meta.get("last_rsi_above_30")
        last_rsi_value = cycle_meta.get("last_rsi_value")

        # Initialize metadata updates (None = no change)
        metadata_updates = {
            "current_cycle": None,
            "last_rsi_above_30": None,
            "last_rsi_value": None,
        }

        levels_taken = {"30": False, "20": False, "10": False}

        # Determine initial levels_taken based on entry_rsi
        if entry_rsi < 10:
            # Entry at RSI < 10: All levels taken
            levels_taken = {"30": True, "20": True, "10": True}
        elif entry_rsi < 20:
            # Entry at RSI < 20: 30 and 20 taken
            levels_taken = {"30": True, "20": True, "10": False}
        elif entry_rsi < 30:
            # Entry at RSI < 30: Only 30 taken
            levels_taken = {"30": True, "20": False, "10": False}
        else:
            # Entry at RSI >= 30: No levels taken (shouldn't happen, but handle it)
            levels_taken = {"30": False, "20": False, "10": False}

        # Fix Issue 1: Update levels_taken based on executed re-entries in current cycle
        # Check reentries array to see which levels have been taken in the current cycle
        if position and position.reentries:
            reentries = position.reentries
            if isinstance(reentries, dict):
                # New format: extract reentries array
                reentries = reentries.get("reentries", [])
            if isinstance(reentries, list):
                for reentry in reentries:
                    if not isinstance(reentry, dict):
                        continue
                    # Check if this re-entry is in the current cycle
                    reentry_cycle = reentry.get("cycle")
                    if reentry_cycle is not None:
                        # Only consider re-entries in the current cycle
                        if int(reentry_cycle) == current_cycle:
                            reentry_level = reentry.get("level")
                            if reentry_level is not None:
                                try:
                                    level_int = int(reentry_level)
                                    if level_int == 30:
                                        levels_taken["30"] = True
                                    elif level_int == 20:
                                        levels_taken["20"] = True
                                    elif level_int == 10:
                                        levels_taken["10"] = True
                                except (ValueError, TypeError):
                                    pass
                    # Backward compatibility: if cycle not stored, assume cycle 0
                    elif current_cycle == 0:
                        reentry_level = reentry.get("level")
                        if reentry_level is not None:
                            try:
                                level_int = int(reentry_level)
                                if level_int == 30:
                                    levels_taken["30"] = True
                                elif level_int == 20:
                                    levels_taken["20"] = True
                                elif level_int == 10:
                                    levels_taken["10"] = True
                            except (ValueError, TypeError):
                                pass

        # Fix: Mark intermediate levels as taken to prevent backtracking
        # Rule: When a re-entry at level X is taken, mark all higher levels (between entry level and X) as taken
        # This prevents backtracking: e.g., if level 10 is taken, level 20 should also be marked as taken
        # Examples:
        #   - If level 10 is taken → Mark levels 20 and 30 as taken (can't backtrack to 20 or 30)
        #   - If level 20 is taken → Mark level 30 as taken (can't backtrack to 30)
        #   - If level 30 is taken → No intermediate levels
        if levels_taken.get("10"):
            # If level 10 is taken, mark level 20 and 30 as taken (can't backtrack)
            levels_taken["20"] = True
            levels_taken["30"] = True
            logger.debug(
                "Level 10 is taken - marking levels 20 and 30 as taken to prevent backtracking"
            )
        elif levels_taken.get("20"):
            # If level 20 is taken, mark level 30 as taken (can't backtrack)
            levels_taken["30"] = True
            logger.debug("Level 20 is taken - marking level 30 as taken to prevent backtracking")

        # Enhanced reset detection with startup support
        # Step 1: If RSI > 30, store last_rsi_above_30 timestamp
        if current_rsi > 30:
            # Store timestamp when RSI goes above 30
            now = ist_now()
            metadata_updates["last_rsi_above_30"] = now.isoformat()
            metadata_updates["last_rsi_value"] = current_rsi
            logger.debug(
                f"RSI > 30 detected: {current_rsi:.2f}. Storing last_rsi_above_30 timestamp."
            )
            # Don't return yet - continue to check if we should trigger reset immediately

        # Step 2: Check for reset condition (RSI < 30 AND last_rsi_above_30 exists)
        # This works both during runtime and on startup
        reset_detected = False
        if current_rsi < 30 and last_rsi_above_30:
            # Reset detected! Increment cycle and reset all levels
            new_cycle = current_cycle + 1
            metadata_updates["current_cycle"] = new_cycle
            metadata_updates["last_rsi_above_30"] = None  # Clear reset flag
            metadata_updates["last_rsi_value"] = current_rsi  # Update last RSI value
            reset_detected = True

            logger.info(
                f"Reset detected: RSI dropped to {current_rsi:.2f} after being above 30. "
                f"Incrementing cycle from {current_cycle} to {new_cycle}."
            )

            # Reset all levels, treat as new cycle
            levels_taken = {"30": False, "20": False, "10": False}

            # Fix Issue 2: Reset should check current RSI level and trigger appropriate level
            # Don't always return level 30 - check what level the current RSI satisfies
            if current_rsi < 10:
                # RSI < 10: Trigger level 10 (highest priority)
                logger.info(f"Reset triggers re-entry at level 10 (RSI {current_rsi:.2f} < 10)")
                return (10, metadata_updates)
            elif current_rsi < 20:
                # RSI < 20: Trigger level 20
                logger.info(f"Reset triggers re-entry at level 20 (RSI {current_rsi:.2f} < 20)")
                return (20, metadata_updates)
            elif current_rsi < 30:
                # RSI < 30: Trigger level 30
                logger.info(f"Reset triggers re-entry at level 30 (RSI {current_rsi:.2f} < 30)")
                return (30, metadata_updates)
            else:
                # Shouldn't happen (we're in reset condition with RSI < 30)
                logger.warning(
                    f"Reset detected but RSI {current_rsi:.2f} is not < 30. This shouldn't happen."
                )
                return (None, metadata_updates)

        # Step 3: Update last_rsi_value if RSI changed (for tracking)
        if last_rsi_value != current_rsi:
            metadata_updates["last_rsi_value"] = current_rsi

        # Normal progression through levels
        # Fix Issue 3: Allow skipping levels if RSI drops directly to a lower level
        # Check levels in priority order (10 > 20 > 30) - allows skipping levels
        next_level = None

        if current_rsi < 10:
            # RSI < 10: Check if level 10 is available
            if not levels_taken.get("10"):
                next_level = 10
                logger.debug(
                    f"RSI {current_rsi:.2f} < 10, level 10 available (allows skipping level 20)"
                )
        elif current_rsi < 20:
            # RSI < 20: Check if level 20 is available
            if not levels_taken.get("20"):
                next_level = 20
                logger.debug(f"RSI {current_rsi:.2f} < 20, level 20 available")
        elif current_rsi < 30:
            # RSI < 30: Check if level 30 is available
            if not levels_taken.get("30"):
                next_level = 30
                logger.debug(f"RSI {current_rsi:.2f} < 30, level 30 available")

        return (next_level, metadata_updates)

    def evaluate_reentries_and_exits(self) -> dict[str, int]:
        summary = {"symbols_evaluated": 0, "exits": 0, "reentries": 0}

        # Check if authenticated - if not, try to re-authenticate
        if not self.auth or not self.auth.is_authenticated():
            logger.warning("Session expired - attempting re-authentication...")
            if not self.login():
                logger.error("Re-authentication failed - cannot proceed")
                return summary
            logger.info("Re-authentication successful - proceeding with evaluation")

        if not self.orders:
            logger.error("Orders not initialized - attempting login...")
            if not self.login():
                logger.error("Login failed - cannot proceed")
                return summary
        data = self._load_trades_history()
        trades = data.get("trades", [])
        # Group open trades by symbol
        open_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for t in trades:
            if t.get("status") == "open":
                open_by_symbol[t["symbol"]].append(t)

        for symbol, entries in open_by_symbol.items():
            summary["symbols_evaluated"] += 1
            # Fix: Ensure symbol is valid before constructing ticker
            ticker = entries[0].get("ticker")
            if not ticker or ticker == ".NS":
                # Reconstruct ticker from symbol if missing or invalid
                if symbol and symbol.strip():
                    ticker = f"{symbol}.NS"
                else:
                    logger.warning("Skip invalid empty symbol in trade history")
                    continue
            ind = self.get_daily_indicators(ticker)
            if not ind:
                logger.warning(f"Skip {symbol}: missing indicators for re-entry/exit evaluation")
                continue
            rsi = ind["rsi10"]
            price = ind["close"]
            ema9 = ind["ema9"]

            # Exit conditions
            if self.strategy_config.exit_on_ema9_or_rsi50 and (price >= ema9 or rsi > 50):
                total_qty = sum(e.get("qty", 0) for e in entries)
                if total_qty > 0:
                    resp = self.orders.place_market_sell(
                        symbol=symbol,
                        quantity=total_qty,
                        variety=self._get_order_variety_for_market_hours(),
                        exchange=self.strategy_config.default_exchange,
                        product=self.strategy_config.default_product,
                    )

                    # Check if order was rejected due to insufficient quantity
                    order_rejected = False
                    if resp is None:
                        order_rejected = True
                    elif isinstance(resp, dict):
                        # Check for error indicators in response
                        keys_lower = {str(k).lower() for k in resp.keys()}
                        if any(k in keys_lower for k in ("error", "errors")):
                            error_msg = str(resp).lower()
                            # Check if error is related to insufficient quantity
                            if any(
                                phrase in error_msg
                                for phrase in [
                                    "insufficient",
                                    "quantity",
                                    "qty",
                                    "not enough",
                                    "exceed",
                                ]
                            ):
                                order_rejected = True
                                logger.warning(
                                    f"Sell order rejected for {symbol} (likely insufficient qty): {resp}"
                                )

                    # Retry with actual available quantity from broker
                    if order_rejected:
                        logger.info(
                            f"Retrying sell order for {symbol} with broker available quantity..."
                        )
                        try:
                            # Fetch holdings to get actual available quantity
                            holdings_response = self.portfolio.get_holdings()
                            if (
                                holdings_response
                                and isinstance(holdings_response, dict)
                                and "data" in holdings_response
                            ):
                                holdings_data = holdings_response["data"]
                                actual_qty = 0

                                # Find the symbol in holdings
                                for holding in holdings_data:
                                    holding_symbol = (
                                        (
                                            holding.get("tradingSymbol")
                                            or holding.get("symbol")
                                            or holding.get("instrumentName")
                                            or ""
                                        )
                                        .replace("-EQ", "")
                                        .upper()
                                    )

                                    if holding_symbol == symbol.upper():
                                        actual_qty = int(
                                            holding.get("quantity")
                                            or holding.get("qty")
                                            or holding.get("netQuantity")
                                            or holding.get("holdingsQuantity")
                                            or 0
                                        )
                                        break

                                if actual_qty > 0:
                                    logger.info(
                                        f"Found {actual_qty} shares available in holdings for {symbol} (expected {total_qty})"
                                    )
                                    # Retry sell with actual quantity
                                    resp = self.orders.place_market_sell(
                                        symbol=symbol,
                                        quantity=actual_qty,
                                        variety=self._get_order_variety_for_market_hours(),
                                        exchange=self.strategy_config.default_exchange,
                                        product=self.strategy_config.default_product,
                                    )

                                    # Check if retry also failed
                                    retry_failed = False
                                    if resp is None:
                                        retry_failed = True
                                    elif isinstance(resp, dict):
                                        keys_lower = {str(k).lower() for k in resp.keys()}
                                        if any(k in keys_lower for k in ("error", "errors")):
                                            retry_failed = True

                                    if retry_failed:
                                        # Send Telegram notification for failed retry
                                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        telegram_msg = (
                                            f"❌ *Sell Order Retry Failed*\n\n"
                                            f"Symbol: `{symbol}`\n"
                                            f"Expected Qty: {total_qty}\n"
                                            f"Available Qty: {actual_qty}\n"
                                            f"Price: Rs {price:.2f}\n"
                                            f"RSI10: {rsi:.1f}\n"
                                            f"EMA9: Rs {ema9:.2f}\n\n"
                                            f"Both initial and retry sell orders failed.\n"
                                            f"Manual intervention may be required.\n\n"
                                            f"_Time: {timestamp}_"
                                        )
                                        # Use TelegramNotifier to respect notification preferences
                                        if (
                                            self.telegram_notifier
                                            and self.telegram_notifier.enabled
                                        ):
                                            try:
                                                self.telegram_notifier.notify_system_alert(
                                                    alert_type="SELL_ORDER_RETRY_FAILED",
                                                    message_text=telegram_msg,
                                                    severity="ERROR",
                                                    user_id=self.user_id,
                                                )
                                            except Exception as notify_err:
                                                logger.warning(
                                                    f"Failed to send sell order retry failed notification: {notify_err}"
                                                )
                                        else:
                                            # Fallback to old method if telegram_notifier not available
                                            send_telegram(telegram_msg)
                                        logger.error(
                                            f"Sell order retry FAILED for {symbol} - Telegram alert sent"
                                        )
                                    else:
                                        logger.info(
                                            f"Retry sell order placed for {symbol}: {actual_qty} shares"
                                        )
                                        # Update total_qty to reflect actual sold quantity
                                        total_qty = actual_qty
                                else:
                                    # Send Telegram notification when no holdings found
                                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    telegram_msg = (
                                        f"❌ *Sell Order Retry Failed*\n\n"
                                        f"Symbol: `{symbol}`\n"
                                        f"Expected Qty: {total_qty}\n"
                                        f"Available Qty: 0 (not found in holdings)\n"
                                        f"Price: Rs {price:.2f}\n\n"
                                        f"Cannot retry - symbol not found in holdings.\n"
                                        f"Manual check required.\n\n"
                                        f"_Time: {timestamp}_"
                                    )
                                    # Use TelegramNotifier to respect notification preferences
                                    if self.telegram_notifier and self.telegram_notifier.enabled:
                                        try:
                                            self.telegram_notifier.notify_system_alert(
                                                alert_type="SELL_ORDER_NO_HOLDINGS",
                                                message_text=telegram_msg,
                                                severity="ERROR",
                                                user_id=self.user_id,
                                            )
                                        except Exception as notify_err:
                                            logger.warning(
                                                f"Failed to send no holdings notification: {notify_err}"
                                            )
                                    else:
                                        # Fallback to old method if telegram_notifier not available
                                        send_telegram(telegram_msg)
                                    logger.error(
                                        f"No holdings found for {symbol} - cannot retry sell order - Telegram alert sent"
                                    )
                            else:
                                # Send Telegram notification when holdings fetch fails
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                telegram_msg = (
                                    f"❌ *Sell Order Retry Failed*\n\n"
                                    f"Symbol: `{symbol}`\n"
                                    f"Expected Qty: {total_qty}\n"
                                    f"Price: Rs {price:.2f}\n\n"
                                    f"Failed to fetch holdings from broker.\n"
                                    f"Cannot determine actual available quantity.\n"
                                    f"Manual intervention required.\n\n"
                                    f"_Time: {timestamp}_"
                                )
                                # Use TelegramNotifier to respect notification preferences
                                if self.telegram_notifier and self.telegram_notifier.enabled:
                                    try:
                                        self.telegram_notifier.notify_system_alert(
                                            alert_type="SELL_ORDER_HOLDINGS_FETCH_FAILED",
                                            message_text=telegram_msg,
                                            severity="ERROR",
                                            user_id=self.user_id,
                                        )
                                    except Exception as notify_err:
                                        logger.warning(
                                            f"Failed to send holdings fetch failed notification: {notify_err}"
                                        )
                                else:
                                    # Fallback to old method if telegram_notifier not available
                                    send_telegram(telegram_msg)
                                logger.error(
                                    f"Failed to fetch holdings for retry - cannot determine actual quantity for {symbol} - Telegram alert sent"
                                )
                        except Exception as e:
                            # Send Telegram notification for exception during retry
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            telegram_msg = (
                                f"❌ *Sell Order Retry Exception*\n\n"
                                f"Symbol: `{symbol}`\n"
                                f"Expected Qty: {total_qty}\n"
                                f"Price: Rs {price:.2f}\n\n"
                                f"Error: {str(e)[:100]}\n"
                                f"Manual intervention required.\n\n"
                                f"_Time: {timestamp}_"
                            )
                            # Use TelegramNotifier to respect notification preferences
                            if self.telegram_notifier and self.telegram_notifier.enabled:
                                try:
                                    self.telegram_notifier.notify_system_alert(
                                        alert_type="SELL_ORDER_RETRY_EXCEPTION",
                                        message_text=telegram_msg,
                                        severity="ERROR",
                                        user_id=self.user_id,
                                    )
                                except Exception as notify_err:
                                    logger.warning(
                                        f"Failed to send sell order retry exception notification: {notify_err}"
                                    )
                            else:
                                # Fallback to old method if telegram_notifier not available
                                from core.telegram import send_telegram

                                send_telegram(telegram_msg)
                            logger.error(
                                f"Error during sell order retry for {symbol}: {e} - Telegram alert sent"
                            )

                    # Mark all entries as closed
                    exit_time = datetime.now().isoformat()
                    for e in entries:
                        e["status"] = "closed"
                        e["exit_price"] = price
                        e["exit_time"] = exit_time
                        e["exit_rsi10"] = rsi
                        e["exit_reason"] = "EMA9 or RSI50"
                        e["sell_order_response"] = resp
                    logger.info(f"Exit {symbol}: qty={total_qty} at ref={price} RSI={rsi:.2f}")
                    summary["exits"] += 1
                    continue  # no re-entries if exited

            # Re-entry conditions
            # Determine next level available based on levels_taken and reset logic
            levels = entries[0].get("levels_taken", {"30": True, "20": False, "10": False})
            # Reset handling: if RSI>30, allow future cycles (but do not auto-clear past entries; apply for next re-entries)
            if rsi > 30:
                for e in entries:
                    e["reset_ready"] = True
            # If reset_ready and rsi drops below 30 again, trigger NEW CYCLE reentry at RSI<30
            if rsi < 30 and any(e.get("reset_ready") for e in entries):
                # This is a NEW CYCLE - treat RSI<30 as a fresh reentry opportunity
                for e in entries:
                    e["levels_taken"] = {"30": False, "20": False, "10": False}  # Reset all levels
                    e["reset_ready"] = False
                levels = entries[0]["levels_taken"]
                # Immediately trigger reentry at this RSI<30 level
                next_level = 30
            else:
                # Normal progression through levels
                next_level = None
                if levels.get("30") and not levels.get("20") and rsi < 20:
                    next_level = 20
                if levels.get("20") and not levels.get("10") and rsi < 10:
                    next_level = 10

            if next_level is not None:
                # Daily cap: allow max 1 re-entry per symbol per day
                if self.reentries_today(symbol) >= 1:
                    logger.info(f"Re-entry daily cap reached for {symbol}; skipping today")
                    continue

                # Phase 11: Calculate execution_capital for re-entry based on current liquidity
                avg_vol = ind.get("avg_volume", 0)
                execution_capital = AutoTradeEngine.calculate_execution_capital(
                    ticker, price, avg_vol
                )
                logger.debug(
                    f"Calculated execution_capital for re-entry {symbol}: Rs {execution_capital:,.0f}"
                )

                qty = max(config.MIN_QTY, floor(execution_capital / price))
                # Balance check for re-entry
                affordable = self.get_affordable_qty(price)
                if affordable < 1:
                    logger.warning(
                        f"Re-entry skip {symbol}: insufficient funds for 1 share at {price}"
                    )
                    continue
                if qty > affordable:
                    logger.info(f"Re-entry reducing qty from {qty} to {affordable} based on funds")
                    qty = affordable
                if qty > 0:
                    # Re-entry duplicate protection: only check for active buy orders
                    # Note: Having holdings is OK for reentry - reentry is meant to add more shares (averaging down)
                    if self.has_active_buy_order(symbol):
                        logger.info(
                            f"Re-entry skip {symbol}: pending buy order exists (prevent duplicate orders)"
                        )
                        continue
                    place_symbol = symbol if symbol.endswith("-EQ") else f"{symbol}-EQ"
                    resp = self.orders.place_market_buy(
                        symbol=place_symbol,
                        quantity=qty,
                        variety=self._get_order_variety_for_market_hours(),
                        exchange=self.strategy_config.default_exchange,
                        product=self.strategy_config.default_product,
                    )
                    # Record new averaging entry only if order succeeded
                    # Accept responses with nOrdNo (direct order ID) or data/order/raw structures
                    resp_valid = (
                        isinstance(resp, dict)
                        and (
                            "data" in resp
                            or "order" in resp
                            or "raw" in resp
                            or "nOrdNo" in resp
                            or "nordno" in str(resp).lower()
                        )
                        and "error" not in resp
                        and "not_ok" not in str(resp).lower()
                    )
                    if resp_valid:
                        # Extract order ID from response
                        reentry_order_id = extract_order_id(resp)

                        # Add reentry order to tracking with entry_type="reentry"
                        if reentry_order_id:
                            try:
                                add_pending_order(
                                    order_id=reentry_order_id,
                                    symbol=place_symbol,
                                    ticker=ticker,
                                    qty=qty,
                                    order_type="MARKET",
                                    variety=self.strategy_config.default_variety,
                                    price=0.0,
                                    entry_type="reentry",
                                    order_metadata={
                                        "rsi_level": next_level,
                                        "rsi": rsi,
                                        "price": price,
                                        "reentry_index": (
                                            len(e.get("reentries", [])) + 1
                                            if e.get("reentries")
                                            else 1
                                        ),
                                    },
                                )
                                logger.debug(f"Added reentry order {reentry_order_id} to tracking")
                            except Exception as e:
                                logger.warning(f"Failed to add reentry order to tracking: {e}")

                        # Mark this level as taken
                        for e in entries:
                            e["levels_taken"][str(next_level)] = True
                        logger.info(
                            f"Re-entry order placed for {symbol} at RSI<{next_level} level; will record once visible in holdings"
                        )
                        summary["reentries"] += 1

                        # Update existing sell order with new total quantity
                        try:
                            logger.info(
                                f"Checking for existing sell order to update after reentry for {symbol}..."
                            )
                            all_orders = self.orders.get_orders()
                            if all_orders and isinstance(all_orders, dict) and "data" in all_orders:
                                for order in all_orders.get("data", []):
                                    order_symbol = (
                                        (order.get("tradingSymbol") or "").split("-")[0].upper()
                                    )
                                    order_type = (
                                        order.get("transactionType") or order.get("trnsTp") or ""
                                    ).upper()
                                    order_status = (
                                        order.get("status")
                                        or order.get("orderStatus")
                                        or order.get("ordSt")
                                        or ""
                                    ).lower()

                                    # Find active sell order for this symbol
                                    if (
                                        order_symbol == symbol.upper()
                                        and order_type in ["S", "SELL"]
                                        and order_status in ["open", "pending"]
                                    ):
                                        old_order_id = (
                                            order.get("neoOrdNo")
                                            or order.get("nOrdNo")
                                            or order.get("orderId")
                                        )
                                        old_qty = int(
                                            order.get("quantity") or order.get("qty") or 0
                                        )
                                        old_price = float(
                                            order.get("price") or order.get("prc") or 0
                                        )

                                        if old_order_id and old_qty > 0:
                                            # Calculate new total quantity
                                            new_total_qty = old_qty + qty
                                            logger.info(
                                                f"Found existing sell order for {symbol}: {old_qty} shares @ Rs {old_price:.2f}"
                                            )
                                            logger.info(
                                                f"Updating to new total: {old_qty} + {qty} (reentry) = {new_total_qty} shares"
                                            )

                                            # Modify order with new quantity
                                            modify_resp = self.orders.modify_order(
                                                order_id=str(old_order_id),
                                                quantity=new_total_qty,
                                                price=old_price,
                                            )

                                            if modify_resp:
                                                logger.info(
                                                    f"Sell order updated: {symbol} x{new_total_qty} @ Rs {old_price:.2f}"
                                                )
                                            else:
                                                logger.warning(
                                                    f"Failed to modify sell order {old_order_id} - order may need manual update"
                                                )
                                            break  # Only update the first matching sell order
                                else:
                                    logger.debug(
                                        f"No active sell order found for {symbol} (will be placed at next sell order run)"
                                    )
                        except Exception as e:
                            logger.error(f"Error updating sell order after reentry: {e}")
                            # Continue execution even if sell order update fails

                        # Update trade history with new total quantity
                        try:
                            logger.info(
                                f"Updating trade history quantity after reentry for {symbol}..."
                            )
                            for e in entries:
                                old_qty = e.get("qty", 0)
                                old_entry_price = e.get("entry_price", 0)
                                new_total_qty = old_qty + qty

                                # Recalculate weighted average entry price
                                # Formula: (prev_avg * prev_qty + new_price * new_qty) / total_qty
                                if old_qty > 0 and old_entry_price > 0:
                                    new_avg_price = (
                                        (old_entry_price * old_qty) + (price * qty)
                                    ) / new_total_qty
                                    e["entry_price"] = new_avg_price
                                    logger.info(
                                        f"Trade history avg price updated: {symbol} "
                                        f"{old_entry_price:.2f} -> {new_avg_price:.2f} "
                                        f"(qty: {old_qty} -> {new_total_qty})"
                                    )
                                else:
                                    # First entry or invalid data - use reentry price
                                    e["entry_price"] = price

                                e["qty"] = new_total_qty
                                logger.info(
                                    f"Trade history updated: {symbol} qty {old_qty} -> {new_total_qty}"
                                )
                                # Also add reentry metadata for tracking (backup to JSON only)
                                # Note: Database is the source of truth. JSON is kept as backup/archival.
                                # When reentry executes, database is updated via unified_order_monitor.
                                if "reentries" not in e:
                                    e["reentries"] = []
                                # Construct reentry data matching database structure
                                # This structure must match what unified_order_monitor writes to DB.
                                # Since this is a market order placed immediately, placed_at = today
                                current_time = datetime.now()
                                reentry_data = {
                                    "qty": int(qty),
                                    "level": int(next_level) if next_level is not None else None,
                                    "rsi": float(rsi) if rsi is not None else None,
                                    "price": float(price),
                                    "time": current_time.isoformat(),  # Execution time (for historical tracking)
                                    "placed_at": current_time.date().isoformat(),  # Placement date (for daily cap check)
                                    "order_id": (
                                        reentry_order_id if reentry_order_id else None
                                    ),  # Track order_id if available
                                }

                                # Improvement: Validate reentry data before writing to JSON
                                # Validate required fields
                                if (
                                    not isinstance(reentry_data.get("qty"), int)
                                    or reentry_data["qty"] <= 0
                                ):
                                    logger.error(
                                        f"Invalid qty in reentry data for {symbol}: {reentry_data.get('qty')}"
                                    )
                                    continue

                                if (
                                    not isinstance(reentry_data.get("price"), (int, float))
                                    or reentry_data["price"] <= 0
                                ):
                                    logger.error(
                                        f"Invalid price in reentry data for {symbol}: {reentry_data.get('price')}"
                                    )
                                    continue

                                if not isinstance(reentry_data.get("time"), str):
                                    logger.error(
                                        f"Invalid time in reentry data for {symbol}: {reentry_data.get('time')}"
                                    )
                                    continue

                                # Validate time format
                                try:
                                    datetime.fromisoformat(reentry_data["time"])
                                except (ValueError, TypeError) as time_err:
                                    logger.error(
                                        f"Invalid time format in reentry data for {symbol}: "
                                        f"{reentry_data.get('time')} - {time_err}"
                                    )
                                    continue

                                e["reentries"].append(reentry_data)
                        except ValueError as e:
                            logger.error(
                                f"Invalid data when updating trade history after reentry for {symbol}: {e}",
                                exc_info=True,
                            )
                        except KeyError as e:
                            logger.error(
                                f"Missing required field when updating trade history after reentry for {symbol}: {e}",
                                exc_info=True,
                            )
                        except Exception as e:
                            logger.error(
                                f"Unexpected error updating trade history after reentry for {symbol}: {e}",
                                exc_info=True,
                            )
                    else:
                        logger.error(f"Re-entry order placement failed for {symbol}")

        # Save any in-memory modifications (exits/reset flags)
        self._save_trades_history(data)
        return summary

    # ---------------------- Orchestrator ----------------------
    def run(self, keep_session: bool = True):
        # TEMPORARY: Skip weekend check for testing
        # if not self.is_trading_weekday():
        #     logger.info("Non-trading weekday; skipping auto trade run")
        #     return
        # if not self.market_was_open_today():
        #     logger.info("Detected market holiday/closed day; skipping run")
        #     return
        logger.warning(
            "WARNING: Weekend check disabled for testing - this will attempt live trading!"
        )
        if not self.login():
            logger.error("Login failed; aborting auto trade")
            return
        try:
            # Reconcile existing holdings into history (captures filled AMOs)
            self.reconcile_holdings_to_history()
            recs = self.load_latest_recommendations()
            new_summary = self.place_new_entries(recs)
            re_summary = self.evaluate_reentries_and_exits()
            # Reconcile again post-actions
            self.reconcile_holdings_to_history()
            logger.info(
                f"Run Summary: NewEntries placed={new_summary['placed']}/attempted={new_summary['attempted']}, "
                f"retried={new_summary.get('retried', 0)}, failed_balance={new_summary.get('failed_balance', 0)}, "
                f"skipped_dup={new_summary['skipped_duplicates']}, skipped_limit={new_summary['skipped_portfolio_limit']}; "
                f"Re/Exits: reentries={re_summary['reentries']}, exits={re_summary['exits']}, symbols={re_summary['symbols_evaluated']}"
            )
        finally:
            if not keep_session:
                self.logout()
            else:
                logger.info("Keeping session active (no logout)")
