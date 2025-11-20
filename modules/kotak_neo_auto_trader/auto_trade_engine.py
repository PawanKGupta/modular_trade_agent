#!/usr/bin/env python3
"""
Auto Trade Engine for Kotak Neo
- Reads recommendations (from analysis_results CSV)
- Places AMO buy orders within portfolio constraints
- Tracks positions and executes re-entry and exit based on RSI/EMA
"""

import glob
import os
import time

# Project logger
import sys
from dataclasses import dataclass
from datetime import date, datetime
from math import floor
from pathlib import Path
from typing import Any

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
# Core market data
from core.data_fetcher import fetch_ohlcv_yf
from core.indicators import compute_indicators
from core.telegram import send_telegram
from utils.logger import logger

# Kotak Neo modules
try:
    from . import config
    from .auth import KotakNeoAuth
    from .eod_cleanup import get_eod_cleanup, schedule_eod_cleanup
    from .manual_order_matcher import get_manual_order_matcher

    # Phase 2 modules
    from .order_status_verifier import get_order_status_verifier
    from .order_tracker import add_pending_order, extract_order_id, search_order_in_broker_orderbook
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
except ImportError:
    from modules.kotak_neo_auto_trader import config
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.eod_cleanup import get_eod_cleanup
    from modules.kotak_neo_auto_trader.manual_order_matcher import get_manual_order_matcher

    # Phase 2 modules
    from modules.kotak_neo_auto_trader.order_status_verifier import get_order_status_verifier
    from modules.kotak_neo_auto_trader.order_tracker import (
        add_pending_order,
        extract_order_id,
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


@dataclass
class Recommendation:
    ticker: str  # e.g. RELIANCE.NS
    verdict: str  # strong_buy|buy|watch
    last_close: float
    execution_capital: float | None = None  # Phase 11: Dynamic capital based on liquidity


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
            all_orders = self.orders_repo.list(self.user_id)
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

    def _save_trades_history(self, data: dict[str, Any]) -> None:
        """
        Save trades history to repository or file-based storage.
        """
        if self.orders_repo and self.positions_repo and self.user_id:
            # Use repository-based storage
            trades = data.get("trades", [])

            for trade in trades:
                symbol = trade.get("symbol", "").upper()
                status = trade.get("status", "open")
                qty = trade.get("qty", 0)
                entry_price = trade.get("entry_price")

                if not symbol or not entry_price:
                    continue

                # Prepare metadata
                metadata = {
                    "placed_symbol": trade.get("placed_symbol"),
                    "ticker": trade.get("ticker"),
                    "rsi10": trade.get("rsi10"),
                    "ema9": trade.get("ema9"),
                    "ema200": trade.get("ema200"),
                    "capital": trade.get("capital"),
                    "rsi_entry_level": trade.get("rsi_entry_level"),
                    "levels_taken": trade.get("levels_taken"),
                    "reset_ready": trade.get("reset_ready", False),
                    "order_response": trade.get("order_response"),
                    "entry_type": trade.get("entry_type"),
                    "reentries": trade.get("reentries", []),
                    "exit_price": trade.get("exit_price"),
                    "exit_rsi10": trade.get("exit_rsi10"),
                    "exit_reason": trade.get("exit_reason"),
                }

                if status == "open":
                    # Upsert open position
                    try:
                        entry_time = datetime.fromisoformat(
                            trade.get("entry_time", datetime.now().isoformat())
                        )
                    except:
                        entry_time = datetime.now()

                    self.positions_repo.upsert(
                        user_id=self.user_id,
                        symbol=symbol,
                        quantity=qty,
                        avg_price=entry_price,
                        opened_at=entry_time,
                    )
                elif status == "closed":
                    # Close position
                    pos = self.positions_repo.get_by_symbol(self.user_id, symbol)
                    if pos:
                        try:
                            exit_time = datetime.fromisoformat(
                                trade.get("exit_time", datetime.now().isoformat())
                            )
                        except:
                            exit_time = datetime.now()
                        pos.closed_at = exit_time
                        self.positions_repo.db.commit()

            # Save failed orders metadata in Orders (if any)
            failed_orders = data.get("failed_orders", [])
            # Note: Failed orders are handled separately in add_failed_order/remove_failed_order
        # Fallback to file-based storage
        elif self.history_path:
            save_history(self.history_path, data)

    def _append_trade(self, trade: dict[str, Any]) -> None:
        """
        Append a trade to history (repository or file-based).
        """
        if self.orders_repo and self.user_id:
            # Use repository-based storage
            data = self._load_trades_history()
            data.setdefault("trades", [])
            data["trades"].append(trade)
            self._save_trades_history(data)
        # Fallback to file-based storage
        elif self.history_path:
            append_trade(self.history_path, trade)

    def _get_failed_orders(
        self, include_previous_day_before_market: bool = False
    ) -> list[dict[str, Any]]:
        """
        Get failed orders from repository or file-based storage.
        """
        if self.orders_repo and self.user_id:
            # Use repository-based storage
            # Failed orders are stored in Orders with special metadata
            all_orders = self.orders_repo.list(self.user_id)
            failed_orders = []
            for order in all_orders:
                metadata = order.order_metadata or {}
                if metadata.get("failed_order"):
                    failed_data = metadata.get("failed_order_data", {})
                    if failed_data:
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

        This method is wrapped in try-except to prevent exceptions from
        crashing the entire buy order task. Failed order tracking is
        non-critical - if it fails, we log and continue.
        """
        try:
            if self.orders_repo and self.user_id:
                # Use repository-based storage
                # Store failed order metadata in a special Orders entry or Activity entry
                # For now, we'll store it in Orders with a special flag
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

                # Check if there's an existing FAILED ORDER for this symbol
                # Only update existing failed orders, don't create duplicates
                existing_orders = self.orders_repo.list(self.user_id)
                existing_failed_orders = [
                    o
                    for o in existing_orders
                    if (o.order_metadata or {}).get("failed_order") is True
                    and normalize_symbol(o.symbol) == normalized_symbol
                ]

                # Log for debugging
                if existing_failed_orders:
                    logger.debug(
                        f"Found {len(existing_failed_orders)} existing failed order(s) for {symbol} (normalized: {normalized_symbol})"
                    )
                else:
                    logger.debug(
                        f"No existing failed order found for {symbol} (normalized: {normalized_symbol}), will create new"
                    )

                if existing_failed_orders:
                    # Update existing failed order's metadata
                    order = existing_failed_orders[0]
                    metadata = order.order_metadata or {}
                    metadata.update(
                        {
                            "failed_order": True,
                            "failed_order_data": failed_order,
                            "last_retry_attempt": datetime.now().isoformat(),
                        }
                    )
                    try:
                        self.orders_repo.update(order, order_metadata=metadata)
                        logger.debug(f"Updated existing failed order for {symbol}")
                    except Exception as update_error:
                        # If update fails, log and continue - failed order tracking is non-critical
                        logger.warning(
                            f"Failed to update order metadata for failed order {symbol}: {update_error}",
                            exc_info=update_error,
                        )
                        # Rollback to clear any session errors
                        if hasattr(self.orders_repo, "db"):
                            try:
                                self.orders_repo.db.rollback()
                            except Exception:
                                pass
                else:
                    # Create a placeholder order to store failed order data
                    new_order = self.orders_repo.create_amo(
                        user_id=self.user_id,
                        symbol=symbol,
                        side="buy",
                        order_type="market",
                        quantity=0,
                        price=None,
                        order_id=None,
                        broker_order_id=None,
                    )
                    # Update metadata
                    metadata = {"failed_order": True, "failed_order_data": failed_order}
                    try:
                        self.orders_repo.update(new_order, order_metadata=metadata)
                    except Exception as update_error:
                        logger.warning(
                            f"Failed to update metadata for new failed order {symbol}: {update_error}",
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
        """
        if self.orders_repo and self.user_id:
            # Use repository-based storage
            all_orders = self.orders_repo.list(self.user_id)
            for order in all_orders:
                metadata = order.order_metadata or {}
                if metadata.get("failed_order"):
                    failed_data = metadata.get("failed_order_data", {})
                    if failed_data.get("symbol", "").upper() == symbol.upper():
                        # Remove failed order flag
                        new_metadata = metadata.copy()
                        new_metadata.pop("failed_order", None)
                        new_metadata.pop("failed_order_data", None)
                        # Get fresh order from database to ensure it's attached to session
                        fresh_order = self.orders_repo.get(order.id)
                        if fresh_order:
                            self.orders_repo.update(fresh_order, order_metadata=new_metadata)
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

    @staticmethod
    def market_was_open_today() -> bool:
        # Try NIFTY 50 index to detect trading day
        try:
            df = fetch_ohlcv_yf("^NSEI", days=5, interval="1d", add_current_day=True)
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
                recs.append(
                    Recommendation(
                        ticker=ticker,
                        verdict=row[verdict_col],
                        last_close=last_close,
                        execution_capital=execution_capital,
                    )
                )
            logger.info(f"Loaded {len(recs)} BUY recommendations from {csv_path}")
            return recs
        # Otherwise, DO NOT recompute; trust the CSV that trade_agent produced
        if "verdict" in df.columns:
            df_buy = df[df["verdict"].astype(str).str.lower().isin(["buy", "strong_buy"])]
            recs = []
            for _, row in df_buy.iterrows():
                ticker = str(row.get("ticker", "")).strip().upper()
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
                recs.append(
                    Recommendation(
                        ticker=ticker,
                        verdict=str(row.get("verdict", "")).lower(),
                        last_close=last_close,
                        execution_capital=execution_capital,
                    )
                )
            logger.info(f"Loaded {len(recs)} BUY recommendations from {csv_path} (raw verdicts)")
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
                from src.infrastructure.db.timezone_utils import ist_now
                from src.infrastructure.persistence.signals_repository import SignalsRepository

                signals_repo = SignalsRepository(self.db)

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

                    # Convert Signals to Recommendation objects
                    recommendations = []
                    for signal in signals:
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
                        if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
                            ticker = f"{ticker}.NS"

                        # Get last_close price
                        last_close = signal.last_close or 0.0
                        if last_close <= 0:
                            logger.warning(f"Skipping {ticker}: invalid last_close ({last_close})")
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

                        # Create Recommendation object
                        rec = Recommendation(
                            ticker=ticker,
                            verdict=verdict,
                            last_close=last_close,
                            execution_capital=execution_capital,
                        )
                        recommendations.append(rec)

                    logger.info(
                        f"Converted {len(recommendations)} buy/strong_buy recommendations from database"
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
        try:
            from pathlib import Path
            from sys import path as sys_path

            project_root = Path(__file__).parent.parent.parent
            if str(project_root) not in sys_path:
                sys_path.insert(0, str(project_root))
            from config.settings import VOLUME_LOOKBACK_DAYS

            df = fetch_ohlcv_yf(ticker, days=800, interval="1d", add_current_day=False)
            # Use configurable RSI period from StrategyConfig
            from config.strategy_config import StrategyConfig

            strategy_config = StrategyConfig.default()
            df = compute_indicators(df, rsi_period=strategy_config.rsi_period)
            if df is None or df.empty:
                return None
            last = df.iloc[-1]
            # Calculate average volume over configurable period (default: 50 days)
            avg_vol = (
                df["volume"].tail(VOLUME_LOOKBACK_DAYS).mean() if "volume" in df.columns else 0
            )

            # Use configurable RSI column name
            rsi_col = f"rsi{strategy_config.rsi_period}"
            # Fallback to 'rsi10' for backward compatibility
            if rsi_col not in last.index and "rsi10" in last.index:
                rsi_col = "rsi10"

            return {
                "close": float(last["close"]),
                "rsi10": (
                    float(last[rsi_col]) if rsi_col in last.index else 0.0
                ),  # Keep 'rsi10' key for backward compatibility
                "ema9": (
                    float(df["close"].ewm(span=config.EMA_SHORT).mean().iloc[-1])
                    if "ema9" not in df.columns
                    else float(last.get("ema9", 0))
                ),
                "ema200": (
                    float(last["ema200"])
                    if "ema200" in df.columns
                    else float(df["close"].ewm(span=config.EMA_LONG).mean().iloc[-1])
                ),
                "avg_volume": float(avg_vol),
            }
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
                                        message = (
                                            f"MANUAL BUY DETECTED\n\n"
                                            f"Symbol: {symbol}\n"
                                            f"Quantity: +{qty_diff} shares\n"
                                            f"New Total: {broker_qty} shares\n"
                                            f"Detected: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                            f"Tracking updated automatically"
                                        )
                                        self.telegram_notifier.send_message(message)

                                    elif disc.get("trade_type") == "MANUAL_SELL":
                                        message = (
                                            f"MANUAL SELL DETECTED\n\n"
                                            f"Symbol: {symbol}\n"
                                            f"Quantity: {qty_diff} shares\n"
                                            f"Remaining: {broker_qty} shares\n"
                                            f"Detected: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                            f"Tracking updated automatically"
                                        )
                                        self.telegram_notifier.send_message(message)

                        # Notify about position closures
                        closed_positions = reconciliation.get("closed_positions", [])
                        if closed_positions and self.telegram_notifier:
                            for symbol in closed_positions:
                                self.telegram_notifier.notify_tracking_stopped(
                                    symbol, "Position fully closed (manual sell detected)"
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
                ind = self.get_daily_indicators(ticker) or {}
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

            # Initialize scrip master for symbol resolution
            try:
                self.scrip_master = KotakNeoScripMaster(
                    auth_client=self.auth.client if hasattr(self.auth, "client") else None
                )
                self.scrip_master.load_scrip_master(force_download=False)
                logger.info("Scrip master loaded for buy order symbol resolution")
            except Exception as e:
                logger.warning(f"Failed to load scrip master: {e}. Will use symbol fallback.")
                self.scrip_master = None

            # Phase 2: Initialize modules
            self._initialize_phase2_modules()
            return True

        ok = self.auth.login()
        if ok:
            self.orders = KotakNeoOrders(self.auth)
            self.portfolio = KotakNeoPortfolio(self.auth)

            # Initialize scrip master for symbol resolution
            try:
                self.scrip_master = KotakNeoScripMaster(
                    auth_client=self.auth.client if hasattr(self.auth, "client") else None
                )
                self.scrip_master.load_scrip_master(force_download=False)
                logger.info("Scrip master loaded for buy order symbol resolution")
            except Exception as e:
                logger.warning(f"Failed to load scrip master: {e}. Will use symbol fallback.")
                self.scrip_master = None

            # Phase 2: Initialize modules
            self._initialize_phase2_modules()
        return ok

    def _initialize_phase2_modules(self) -> None:
        """Initialize Phase 2 modules (verifier, telegram, etc.)."""
        try:
            # 1. Initialize Telegram Notifier
            if self._enable_telegram:
                self.telegram_notifier = get_telegram_notifier()
                logger.info(
                    f"Telegram notifier initialized (enabled: {self.telegram_notifier.enabled})"
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
                        from .order_tracker import get_order_tracker

                        tracker = get_order_tracker()
                        pending_order = tracker.get_order_by_id(order_id)
                        qty = pending_order.get("qty", 0) if pending_order else 0
                        self.telegram_notifier.notify_order_rejection(symbol, order_id, qty, reason)

                def on_execution(symbol: str, order_id: str, qty: int):
                    """Callback when order is executed."""
                    logger.info(f"Order executed: {symbol} ({order_id}) - {qty} shares")
                    if self.telegram_notifier and self.telegram_notifier.enabled:
                        self.telegram_notifier.notify_order_execution(symbol, order_id, qty)

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
                )
                logger.info("EOD cleanup initialized")

            logger.info("[OK] Phase 2 modules initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Phase 2 modules: {e}", exc_info=True)
            logger.warning("Continuing without Phase 2 features")

    def monitor_positions(self, live_price_manager=None) -> dict[str, Any]:
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
        symbols = set(self._fetch_holdings_symbols())
        # Include pending BUY orders too
        pend = self.orders.get_pending_orders() if self.orders else []
        for o in pend or []:
            if str(o.get("transactionType", "")).upper().startswith("B"):
                sym = str(o.get("tradingSymbol") or "").upper()
                if sym:
                    symbols.add(sym)
        return sorted(symbols)

    def portfolio_size(self) -> int:
        return len(self.current_symbols_in_portfolio())

    def get_affordable_qty(self, price: float) -> int:
        """Return maximum whole quantity affordable from available cash/margin."""
        if not self.portfolio or not price or price <= 0:
            return 0
        lim = self.portfolio.get_limits() or {}
        data = lim.get("data") if isinstance(lim, dict) else None
        avail = 0.0
        used_key = None
        if isinstance(data, dict):
            # Prefer explicit cash-like fields first (CNC), then margin keys, then Net
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
            for k in candidates:
                try:
                    v = data.get(k)
                    if v is None or v == "":
                        continue
                    fv = float(v)
                    if fv > 0:
                        avail = fv
                        used_key = k
                        break
                except Exception:
                    continue
            # Absolute fallback: pick the max numeric value in the payload
            if avail <= 0:
                try:
                    nums = []
                    for v in data.values():
                        try:
                            nums.append(float(v))
                        except Exception:
                            pass
                    if nums:
                        avail = max(nums)
                        used_key = used_key or "max_numeric_field"
                except Exception:
                    pass
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
        data = lim.get("data") if isinstance(lim, dict) else None
        avail = 0.0
        used_key = None
        if isinstance(data, dict):
            try:
                # Prefer cash-like fields first, then margin, then Net
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
                for k in candidates:
                    v = data.get(k)
                    if v is None or v == "":
                        continue
                    try:
                        fv = float(v)
                    except Exception:
                        continue
                    if fv > 0:
                        avail = fv
                        used_key = k
                        break
                # Absolute fallback: use the max numeric value in payload
                if avail <= 0:
                    nums = []
                    for v in data.values():
                        try:
                            nums.append(float(v))
                        except Exception:
                            pass
                    if nums:
                        avail = max(nums)
                        used_key = used_key or "max_numeric_field"
                logger.debug(
                    f"Available cash from limits API: Rs {avail:.2f} (key={used_key or 'n/a'})"
                )
                return float(avail)
            except Exception as e:
                logger.warning(f"Error parsing available cash: {e}")
                return 0.0
        logger.debug("Limits API returned no usable 'data' object; assuming Rs 0.00 available")
        return 0.0

    # ---------------------- De-dup helpers ----------------------
    @staticmethod
    def _symbol_variants(base: str) -> list[str]:
        base = base.upper()
        return [base, f"{base}-EQ", f"{base}-BE", f"{base}-BL", f"{base}-BZ"]

    def has_holding(self, base_symbol: str) -> bool:
        if not self.portfolio:
            return False
        variants = set(self._symbol_variants(base_symbol))
        h = self.portfolio.get_holdings() or {}

        # Check for 2FA gate - if detected, force re-login and retry once
        if self._response_requires_2fa(h) and hasattr(self.auth, "force_relogin"):
            logger.info("2FA gate detected in holdings check, attempting re-login...")
            try:
                if self.auth.force_relogin():
                    h = self.portfolio.get_holdings() or {}
                    logger.debug("Holdings re-fetched after re-login")
            except Exception as e:
                logger.warning(f"Re-login failed during holdings check: {e}")

        for item in h.get("data") or []:
            sym = str(item.get("tradingSymbol") or "").upper()
            if sym in variants:
                return True
        return False

    def has_active_buy_order(self, base_symbol: str) -> bool:
        if not self.orders:
            return False
        variants = set(self._symbol_variants(base_symbol))
        pend = self.orders.get_pending_orders() or []
        for o in pend:
            txn = str(o.get("transactionType") or "").upper()
            sym = str(o.get("tradingSymbol") or "").upper()
            if txn.startswith("B") and sym in variants:
                return True
        return False

    def reentries_today(self, base_symbol: str) -> int:
        """Count successful re-entries recorded today for this symbol (base symbol)."""
        try:
            hist = self._load_trades_history()
            trades = hist.get("trades") or []
            today = datetime.now().date()
            cnt = 0
            for t in trades:
                if t.get("entry_type") != "reentry":
                    continue
                sym = str(t.get("symbol") or "").upper()
                if sym != base_symbol.upper():
                    continue
                ts = t.get("entry_time")
                if not ts:
                    continue
                try:
                    d = datetime.fromisoformat(ts).date()
                except Exception:
                    try:
                        d = datetime.strptime(ts.split("T")[0], "%Y-%m-%d").date()
                    except Exception:
                        continue
                if d == today:
                    cnt += 1
            return cnt
        except Exception:
            return 0

    def _attempt_place_order(
        self,
        broker_symbol: str,
        ticker: str,
        qty: int,
        close: float,
        ind: dict[str, Any],
        recommendation_source: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        Helper method to attempt placing an order with symbol resolution.

        Args:
            broker_symbol: Trading symbol
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

        # Determine if this is a BE/BL/BZ segment stock (trade-to-trade)
        # These segments require LIMIT orders, not MARKET orders
        is_t2t_segment = any(broker_symbol.upper().endswith(suf) for suf in ["-BE", "-BL", "-BZ"])

        # For T2T segments, use limit order at current price + 1% buffer
        use_limit_order = is_t2t_segment
        limit_price = close * 1.01 if use_limit_order else 0.0

        if use_limit_order:
            logger.info(
                f"Using LIMIT order for {broker_symbol} (T2T segment) @ Rs {limit_price:.2f}"
            )

        # Try to resolve symbol using scrip master first
        resolved_symbol = None
        if self.scrip_master and self.scrip_master.symbol_map:
            # Try base symbol first
            instrument = self.scrip_master.get_instrument(broker_symbol)
            if instrument:
                resolved_symbol = instrument["symbol"]
                logger.debug(f"Resolved {broker_symbol} -> {resolved_symbol} via scrip master")

        # If scrip master resolved the symbol, use it directly
        if resolved_symbol:
            place_symbol = resolved_symbol
            if use_limit_order:
                trial = self.orders.place_limit_buy(
                    symbol=place_symbol,
                    quantity=qty,
                    price=limit_price,
                    variety=config.DEFAULT_VARIETY,
                    exchange=config.DEFAULT_EXCHANGE,
                    product=config.DEFAULT_PRODUCT,
                )
            else:
                trial = self.orders.place_market_buy(
                    symbol=place_symbol,
                    quantity=qty,
                    variety=config.DEFAULT_VARIETY,
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

        # Fallback: Try common series suffixes if scrip master didn't work
        if not resp:
            series_suffixes = ["-EQ", "-BE", "-BL", "-BZ"]
            resp = None
            placed_symbol = None
            for suf in series_suffixes:
                place_symbol = (
                    broker_symbol if broker_symbol.endswith(suf) else f"{broker_symbol}{suf}"
                )

                # Check if this suffix requires limit order
                is_t2t_suf = suf in ["-BE", "-BL", "-BZ"]

                if is_t2t_suf:
                    limit_price = close * 1.01
                    logger.debug(f"Trying {place_symbol} with LIMIT @ Rs {limit_price:.2f}")
                    trial = self.orders.place_limit_buy(
                        symbol=place_symbol,
                        quantity=qty,
                        price=limit_price,
                        variety=config.DEFAULT_VARIETY,
                        exchange=config.DEFAULT_EXCHANGE,
                        product=config.DEFAULT_PRODUCT,
                    )
                else:
                    trial = self.orders.place_market_buy(
                        symbol=place_symbol,
                        quantity=qty,
                        variety=config.DEFAULT_VARIETY,
                        exchange=config.DEFAULT_EXCHANGE,
                        product=config.DEFAULT_PRODUCT,
                    )
                # Check for successful response - Kotak Neo returns stat='Ok' with nOrdNo
                if isinstance(trial, dict) and "error" not in trial:
                    stat = trial.get("stat", "").lower()
                    trial_str = str(trial).lower()
                    if (
                        stat == "ok"
                        or "data" in trial
                        or "order" in trial
                        or "raw" in trial
                        or "nordno" in trial_str
                    ) and "not_ok" not in trial_str:
                        resp = trial
                        placed_symbol = place_symbol
                        break

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

        if not order_id:
            # Fallback: Search order book after a shorter wait (reduced from 60s to 10s for performance)
            logger.warning(
                f"No order ID in response for {broker_symbol}. "
                f"Will search order book after 10 seconds..."
            )
            order_id = search_order_in_broker_orderbook(
                self.orders,
                placed_symbol or broker_symbol,
                qty,
                placement_time,
                max_wait_seconds=10,  # Reduced from 60s to 10s for faster execution
            )

            if not order_id:
                # Still no order ID - uncertain placement
                logger.error(
                    f"Order placement uncertain for {broker_symbol}: "
                    f"No order ID and not found in order book"
                )
                # Send notification about uncertain order
                from core.telegram import send_telegram

                send_telegram(
                    f"Order placement uncertain\n"
                    f"Symbol: {broker_symbol}\n"
                    f"Qty: {qty}\n"
                    f"Order ID not received and not found in order book.\n"
                    f"Please check broker app manually."
                )
                return (False, None)

        # Order successfully placed with order_id
        logger.info(
            f"Order placed successfully: {placed_symbol or broker_symbol} "
            f"(order_id: {order_id}, qty: {qty})"
        )

        # Get pre-existing quantity (if any)
        pre_existing_qty = 0
        try:
            holdings = self.portfolio.get_holdings() or {}
            for item in holdings.get("data") or []:
                sym = str(item.get("tradingSymbol", "")).upper()
                if broker_symbol.upper() in sym:
                    pre_existing_qty = int(item.get("quantity", 0))
                    break
        except Exception as e:
            logger.debug(f"Could not get pre-existing qty: {e}")

        # Register in tracking scope (system-recommended)
        try:
            tracking_id = add_tracked_symbol(
                symbol=broker_symbol,
                ticker=ticker,
                initial_order_id=order_id,
                initial_qty=qty,
                pre_existing_qty=pre_existing_qty,
                recommendation_source=recommendation_source,
                recommendation_verdict=getattr(ind, "verdict", None),
            )
            logger.debug(f"Added to tracking scope: {broker_symbol} (tracking_id: {tracking_id})")
        except Exception as e:
            logger.error(f"Failed to add to tracking scope: {e}")

        # Add to pending orders for status monitoring
        try:
            add_pending_order(
                order_id=order_id,
                symbol=placed_symbol or broker_symbol,
                ticker=ticker,
                qty=qty,
                order_type="MARKET",
                variety=config.DEFAULT_VARIETY,
            )
            logger.debug(f"Added to pending orders: {order_id}")
        except Exception as e:
            logger.error(f"Failed to add to pending orders: {e}")

        return (True, order_id)

    # ---------------------- New entries ----------------------
    def place_new_entries(self, recommendations: list[Recommendation]) -> dict[str, int | list]:
        summary = {
            "attempted": 0,
            "placed": 0,
            "retried": 0,
            "failed_balance": 0,
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
            if self.db and self.user_id and hasattr(self, "orders_repo"):
                from sqlalchemy import text

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
                    AND status IN ('amo', 'ongoing')
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

        # OPTIMIZATION: Cache portfolio snapshot and pre-fetch indicators for all recommendations
        # This reduces API calls from O(n) to O(1) for portfolio checks and batches indicator fetches
        cached_portfolio_count = None
        cached_holdings_symbols = set()
        try:
            cached_portfolio_count = len(self.current_symbols_in_portfolio())
            cached_holdings = self.portfolio.get_holdings() or {}
            if isinstance(cached_holdings, dict) and "data" in cached_holdings:
                for item in cached_holdings["data"]:
                    sym = (
                        str(item.get("tradingSymbol", ""))
                        .upper()
                        .replace("-EQ", "")
                        .replace("-BE", "")
                        .replace("-BL", "")
                        .replace("-BZ", "")
                    )
                    if sym:
                        cached_holdings_symbols.add(sym)
            logger.info(
                f"Cached portfolio snapshot: {cached_portfolio_count} positions, {len(cached_holdings_symbols)} symbols"
            )
        except Exception as e:
            logger.warning(f"Failed to cache portfolio snapshot: {e}, will fetch per-ticker")

        # Pre-fetch indicators for all recommendation tickers (batch operation with parallelization)
        cached_indicators: dict[str, dict[str, Any] | None] = {}
        if recommendations:
            # Try parallel execution first, fallback to sequential if it fails
            try:
                logger.info(
                    f"Pre-fetching indicators for {len(recommendations)} recommendations in parallel..."
                )
                from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: PLC0415

                def fetch_indicator(rec_ticker: str) -> tuple[str, dict[str, Any] | None]:
                    """Fetch indicator for a single ticker"""
                    try:
                        # get_daily_indicators is a static method, call it correctly
                        ind = AutoTradeEngine.get_daily_indicators(rec_ticker)
                        return (rec_ticker, ind)
                    except Exception as e:
                        logger.warning(
                            f"Failed to pre-fetch indicators for {rec_ticker}: {e}",
                            exc_info=e,
                        )
                        return (rec_ticker, None)

                # Use ThreadPoolExecutor to fetch indicators in parallel
                # Limit to 5 concurrent requests to avoid overwhelming the API
                with ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_ticker = {
                        executor.submit(fetch_indicator, rec.ticker): rec.ticker
                        for rec in recommendations
                    }
                    for future in as_completed(future_to_ticker):
                        try:
                            ticker, ind = future.result()
                            cached_indicators[ticker] = ind
                        except Exception as e:
                            ticker = future_to_ticker.get(future, "unknown")
                            logger.error(
                                f"Error getting indicator result for {ticker}: {e}",
                                exc_info=e,
                            )
                            cached_indicators[ticker] = None

                successful_prefetches = sum(1 for v in cached_indicators.values() if v is not None)
                logger.info(
                    f"Pre-fetched {successful_prefetches}/{len(recommendations)} indicators (parallel)"
                )
            except Exception as parallel_error:
                # Fallback to sequential execution if parallel fails
                logger.warning(
                    f"Parallel indicator fetching failed: {parallel_error}. Falling back to sequential...",
                    exc_info=parallel_error,
                )
                logger.info(
                    f"Pre-fetching indicators for {len(recommendations)} recommendations sequentially..."
                )
                for rec in recommendations:
                    try:
                        ind = AutoTradeEngine.get_daily_indicators(rec.ticker)
                        cached_indicators[rec.ticker] = ind
                    except Exception as e:
                        logger.warning(f"Failed to pre-fetch indicators for {rec.ticker}: {e}")
                        cached_indicators[rec.ticker] = None
                successful_prefetches = sum(1 for v in cached_indicators.values() if v is not None)
                logger.info(
                    f"Pre-fetched {successful_prefetches}/{len(recommendations)} indicators (sequential)"
                )

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

        # STEP 1: Retry previously failed orders due to insufficient balance
        # (includes yesterday's orders if before 9:15 AM market open)
        failed_orders = self._get_failed_orders(include_previous_day_before_market=True)
        if failed_orders:
            logger.info(f"Found {len(failed_orders)} previously failed orders to retry")
            for failed_order in failed_orders[:]:
                # Skip non-retryable orders (e.g., broker API errors)
                if failed_order.get("non_retryable", False):
                    logger.info(
                        f"Skipping non-retryable failed order for {failed_order.get('symbol')} "
                        f"(reason: {failed_order.get('reason', 'unknown')})"
                    )
                    continue

                # Check portfolio limit
                try:
                    current_count = len(self.current_symbols_in_portfolio())
                except Exception:
                    current_count = self.portfolio_size()
                if current_count >= self.strategy_config.max_portfolio_size:
                    logger.info(
                        f"Portfolio limit reached ({current_count}/{self.strategy_config.max_portfolio_size}); skipping failed order retries"
                    )
                    break

                symbol = failed_order.get("symbol")
                ticker = failed_order.get("ticker")

                # Skip if already in holdings
                if self.has_holding(symbol):
                    logger.info(f"Removing {symbol} from retry queue: already in holdings")
                    self._remove_failed_order(symbol)
                    continue

                # Skip if already has active buy order
                if self.has_active_buy_order(symbol):
                    logger.info(f"Skipping retry for {symbol}: already has pending buy order")
                    continue

                summary["retried"] += 1
                logger.info(f"Retrying failed order for {symbol}...")

                # Get fresh indicators
                ind = self.get_daily_indicators(ticker)
                if not ind or any(k not in ind for k in ("close", "rsi10", "ema9", "ema200")):
                    logger.warning(f"Skipping retry {symbol}: missing indicators")
                    continue

                close = ind["close"]
                if close <= 0:
                    logger.warning(f"Skipping retry {symbol}: invalid close price {close}")
                    continue

                # Phase 11: Always recalculate execution_capital during retry to respect current user config
                # This ensures that if user changes capital config, retries use the new value
                avg_vol = ind.get("avg_volume", 0)
                old_execution_capital = failed_order.get("execution_capital")
                execution_capital = self._calculate_execution_capital(ticker, close, avg_vol)

                # Log if capital changed from stored value
                if (
                    old_execution_capital
                    and old_execution_capital > 0
                    and old_execution_capital != execution_capital
                ):
                    logger.info(
                        f"Retry {symbol}: Execution capital updated from Rs {old_execution_capital:,.0f} "
                        f"to Rs {execution_capital:,.0f} (current user_capital: Rs {self.strategy_config.user_capital:,.0f})"
                    )
                else:
                    logger.debug(
                        f"Calculated execution_capital for retry {symbol}: Rs {execution_capital:,.0f} "
                        f"(using user_capital: Rs {self.strategy_config.user_capital:,.0f})"
                    )

                qty = max(config.MIN_QTY, floor(execution_capital / close))

                # Check position-to-volume ratio (liquidity filter)
                avg_vol = ind.get("avg_volume", 0)
                if not self.check_position_volume_ratio(qty, avg_vol, symbol, close):
                    logger.info(
                        f"Skipping retry {symbol}: position size too large relative to volume"
                    )
                    summary["skipped_invalid_qty"] += 1
                    # Remove from failed orders queue since it's not a temporary issue
                    self._remove_failed_order(symbol)
                    continue

                # Check balance again
                affordable = self.get_affordable_qty(close)
                if affordable < config.MIN_QTY or qty > affordable:
                    avail_cash = self.get_available_cash()
                    required_cash = qty * close
                    shortfall = max(0.0, required_cash - (avail_cash or 0.0))
                    logger.warning(
                        f"Retry failed for {symbol}: still insufficient balance (need Rs {required_cash:,.0f}, have Rs {(avail_cash or 0.0):,.0f})"
                    )
                    # Update the failed order with new attempt timestamp
                    failed_order["retry_count"] = failed_order.get("retry_count", 0) + 1
                    failed_order["last_retry_attempt"] = datetime.now().isoformat()
                    self._add_failed_order(failed_order)
                    continue

                # Try placing the order
                success, order_id = self._attempt_place_order(symbol, ticker, qty, close, ind)
                if success:
                    summary["placed"] += 1
                    self._remove_failed_order(symbol)
                    logger.info(
                        f"Successfully placed retry order for {symbol} (order_id: {order_id})"
                    )
                else:
                    # Broker/API error during retry - log and continue with other orders
                    # Don't stop the entire run for one failed retry
                    error_msg = (
                        f"Broker/API error while retrying order for {symbol}. "
                        "Skipping this retry and continuing with other orders."
                    )
                    logger.error(error_msg)
                    # Continue with next failed order instead of raising exception
                    continue

        # STEP 2: Process new recommendations
        for rec in recommendations:
            broker_symbol = self.parse_symbol_for_broker(rec.ticker)
            ticker_attempt = {
                "ticker": rec.ticker,
                "symbol": broker_symbol,
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
                try:
                    current_count = len(self.current_symbols_in_portfolio())
                except Exception:
                    current_count = self.portfolio_size()
            if current_count >= self.strategy_config.max_portfolio_size:
                logger.info(
                    f"Portfolio limit reached ({current_count}/{self.strategy_config.max_portfolio_size}); skipping further entries"
                )
                summary["skipped_portfolio_limit"] += 1
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = "portfolio_limit_reached"
                summary["ticker_attempts"].append(ticker_attempt)
                break
            summary["attempted"] += 1
            # 1) Holding check (use cached holdings if available)
            broker_symbol_base = (
                broker_symbol.upper()
                .replace("-EQ", "")
                .replace("-BE", "")
                .replace("-BL", "")
                .replace("-BZ", "")
            )
            if cached_holdings_symbols and broker_symbol_base in cached_holdings_symbols:
                logger.info(f"Skipping {broker_symbol}: already in holdings (cached)")
                summary["skipped_duplicates"] += 1
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = "already_in_holdings"
                summary["ticker_attempts"].append(ticker_attempt)
                continue
            elif self.has_holding(broker_symbol):  # Fallback to live check if cache miss
                logger.info(f"Skipping {broker_symbol}: already in holdings")
                summary["skipped_duplicates"] += 1
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = "already_in_holdings"
                summary["ticker_attempts"].append(ticker_attempt)
                continue
            # 2) Active pending buy order check -> cancel and replace
            if self.has_active_buy_order(broker_symbol):
                variants = self._symbol_variants(broker_symbol)
                try:
                    cancelled = self.orders.cancel_pending_buys_for_symbol(variants)
                    logger.info(f"Cancelled {cancelled} pending BUY order(s) for {broker_symbol}")
                except Exception as e:
                    logger.warning(f"Could not cancel pending order(s) for {broker_symbol}: {e}")

            # Use cached indicators if available, otherwise fetch
            ind = cached_indicators.get(rec.ticker)
            if ind is None:
                ind = self.get_daily_indicators(rec.ticker)
            if not ind or any(k not in ind for k in ("close", "rsi10", "ema9", "ema200")):
                logger.warning(f"Skipping {rec.ticker}: missing indicators")
                summary["skipped_missing_data"] += 1
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = "missing_indicators"
                summary["ticker_attempts"].append(ticker_attempt)
                continue
            close = ind["close"]
            if close <= 0:
                logger.warning(f"Skipping {rec.ticker}: invalid close price {close}")
                summary["skipped_invalid_qty"] += 1
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

            # Check position-to-volume ratio (liquidity filter)
            avg_vol = ind.get("avg_volume", 0)
            if not self.check_position_volume_ratio(qty, avg_vol, broker_symbol, close):
                logger.info(f"Skipping {broker_symbol}: position size too large relative to volume")
                summary["skipped_invalid_qty"] += 1
                ticker_attempt["status"] = "skipped"
                ticker_attempt["reason"] = "position_too_large_for_volume"
                ticker_attempt["qty"] = qty
                ticker_attempt["execution_capital"] = execution_capital
                summary["ticker_attempts"].append(ticker_attempt)
                continue

            # Balance check (CNC needs cash) -> notify on insufficiency and save for retry
            affordable = self.get_affordable_qty(close)
            if affordable < config.MIN_QTY or qty > affordable:
                avail_cash = self.get_available_cash()
                required_cash = qty * close
                shortfall = max(0.0, required_cash - (avail_cash or 0.0))
                # Telegram message with emojis
                telegram_msg = (
                    f"Insufficient balance for {broker_symbol} AMO BUY.\n"
                    f"Needed: Rs {required_cash:,.0f} for {qty} @ Rs {close:.2f}.\n"
                    f"Available: Rs {(avail_cash or 0.0):,.0f}. Shortfall: Rs {shortfall:,.0f}.\n\n"
                    f"Order saved for retry until 9:15 AM tomorrow (before market opens).\n"
                    f"Add balance & run script, or wait for 8 AM scheduled retry."
                )
                send_telegram(telegram_msg)

                # Logger message without emojis
                logger.warning(
                    f"Insufficient balance for {broker_symbol} AMO BUY. "
                    f"Needed: Rs.{required_cash:,.0f} for {qty} @ Rs.{close:.2f}. "
                    f"Available: Rs.{(avail_cash or 0.0):,.0f}. Shortfall: Rs.{shortfall:,.0f}. "
                    f"Order saved for retry until 9:15 AM tomorrow."
                )

                # Save failed order for retry
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
                broker_symbol, rec.ticker, qty, close, ind, recommendation_source=rec_source
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
        from collections import defaultdict

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
                        variety=self.strategy_config.default_variety,
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
                                        variety=self.strategy_config.default_variety,
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
                                        telegram_msg = (
                                            f"SELL ORDER RETRY FAILED\n\n"
                                            f"Symbol: *{symbol}*\n"
                                            f"Expected Qty: {total_qty}\n"
                                            f"Available Qty: {actual_qty}\n"
                                            f"Price: Rs {price:.2f}\n"
                                            f"RSI10: {rsi:.1f}\n"
                                            f"EMA9: Rs {ema9:.2f}\n\n"
                                            f"Both initial and retry sell orders failed.\n"
                                            f"Manual intervention may be required.\n\n"
                                            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                        )
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
                                    telegram_msg = (
                                        f"SELL ORDER RETRY FAILED\n\n"
                                        f"Symbol: *{symbol}*\n"
                                        f"Expected Qty: {total_qty}\n"
                                        f"Available Qty: 0 (not found in holdings)\n"
                                        f"Price: Rs {price:.2f}\n\n"
                                        f"Cannot retry - symbol not found in holdings.\n"
                                        f"Manual check required.\n\n"
                                        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                    )
                                    send_telegram(telegram_msg)
                                    logger.error(
                                        f"No holdings found for {symbol} - cannot retry sell order - Telegram alert sent"
                                    )
                            else:
                                # Send Telegram notification when holdings fetch fails
                                telegram_msg = (
                                    f"SELL ORDER RETRY FAILED\n\n"
                                    f"Symbol: *{symbol}*\n"
                                    f"Expected Qty: {total_qty}\n"
                                    f"Price: Rs {price:.2f}\n\n"
                                    f"Failed to fetch holdings from broker.\n"
                                    f"Cannot determine actual available quantity.\n"
                                    f"Manual intervention required.\n\n"
                                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                                send_telegram(telegram_msg)
                                logger.error(
                                    f"Failed to fetch holdings for retry - cannot determine actual quantity for {symbol} - Telegram alert sent"
                                )
                        except Exception as e:
                            # Send Telegram notification for exception during retry
                            telegram_msg = (
                                f"SELL ORDER RETRY EXCEPTION\n\n"
                                f"Symbol: *{symbol}*\n"
                                f"Expected Qty: {total_qty}\n"
                                f"Price: Rs {price:.2f}\n\n"
                                f"Error: {str(e)[:100]}\n"
                                f"Manual intervention required.\n\n"
                                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            )
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
                    # Re-entry duplicate protection: holdings and active order
                    if self.has_holding(symbol) or self.has_active_buy_order(symbol):
                        logger.info(
                            f"Re-entry skip {symbol}: already in holdings or pending order exists"
                        )
                        continue
                    place_symbol = symbol if symbol.endswith("-EQ") else f"{symbol}-EQ"
                    resp = self.orders.place_market_buy(
                        symbol=place_symbol,
                        quantity=qty,
                        variety=self.strategy_config.default_variety,
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
                                new_total_qty = old_qty + qty
                                e["qty"] = new_total_qty
                                logger.info(
                                    f"Trade history updated: {symbol} qty {old_qty} -> {new_total_qty}"
                                )
                                # Also add reentry metadata for tracking
                                if "reentries" not in e:
                                    e["reentries"] = []
                                e["reentries"].append(
                                    {
                                        "qty": qty,
                                        "level": next_level,
                                        "rsi": rsi,
                                        "price": price,
                                        "time": datetime.now().isoformat(),
                                    }
                                )
                        except Exception as e:
                            logger.error(f"Error updating trade history after reentry: {e}")
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
