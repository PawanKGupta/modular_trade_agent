"""
Portfolio Service

Centralized service for holdings/positions checks across all trading services.
Eliminates duplicate code for portfolio management.

Phase 2.1: Portfolio & Position Services
"""

import sys
from pathlib import Path
from threading import Lock
from time import time
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger  # noqa: E402

# Database models
try:
    from src.infrastructure.db.models import OrderStatus as DbOrderStatus
except ImportError:
    DbOrderStatus = None

try:
    from .. import config
    from ..auth import KotakNeoAuth
    from ..orders import KotakNeoOrders
    from ..portfolio import KotakNeoPortfolio
except ImportError:
    from modules.kotak_neo_auto_trader import config
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders
    from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio


class PortfolioCache:
    """In-memory cache for portfolio holdings data"""

    def __init__(self, ttl_seconds: int = 120):
        """
        Initialize portfolio cache

        Args:
            ttl_seconds: Time-to-live for cache entries (default: 120 seconds / 2 minutes)
        """
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()
        self._ttl = ttl_seconds

    def get(self, key: str) -> Any | None:
        """Get cached value if not expired"""
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time() - timestamp < self._ttl:
                    return value
                # Expired, remove it
                del self._cache[key]
            return None

    def set(self, key: str, value: Any) -> None:
        """Set cached value with current timestamp"""
        with self._lock:
            self._cache[key] = (value, time())

    def clear(self) -> None:
        """Clear all cached values"""
        with self._lock:
            self._cache.clear()

    def invalidate(self, key: str) -> None:
        """Invalidate specific cache entry"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]


# Singleton instance
_portfolio_service_instance: "PortfolioService | None" = None


def get_portfolio_service(  # noqa: PLR0913
    portfolio: KotakNeoPortfolio | None = None,
    orders: KotakNeoOrders | None = None,
    auth: KotakNeoAuth | None = None,
    strategy_config=None,
    orders_repo=None,
    user_id: int | None = None,
    enable_caching: bool = True,
    cache_ttl: int = 120,
) -> "PortfolioService":
    """
    Get or create PortfolioService singleton instance

    Args:
        portfolio: KotakNeoPortfolio instance (optional, can be set later)
        orders: KotakNeoOrders instance (optional, can be set later)
        auth: KotakNeoAuth instance (optional, for 2FA handling)
        strategy_config: StrategyConfig instance (optional, for portfolio limits)
        orders_repo: OrdersRepository instance (optional, for database order checks)
        user_id: User ID (optional, for database order checks)
        enable_caching: Enable caching (default: True)
        cache_ttl: Cache TTL in seconds (default: 120 / 2 minutes)

    Returns:
        PortfolioService instance
    """
    global _portfolio_service_instance  # noqa: PLW0603

    if _portfolio_service_instance is None:
        _portfolio_service_instance = PortfolioService(
            portfolio=portfolio,
            orders=orders,
            auth=auth,
            strategy_config=strategy_config,
            orders_repo=orders_repo,
            user_id=user_id,
            enable_caching=enable_caching,
            cache_ttl=cache_ttl,
        )

    # Update instance if new dependencies provided
    if portfolio is not None:
        _portfolio_service_instance.portfolio = portfolio
    if orders is not None:
        _portfolio_service_instance.orders = orders
    if auth is not None:
        _portfolio_service_instance.auth = auth
    if strategy_config is not None:
        _portfolio_service_instance.strategy_config = strategy_config
    if orders_repo is not None:
        _portfolio_service_instance.orders_repo = orders_repo
    if user_id is not None:
        _portfolio_service_instance.user_id = user_id

    return _portfolio_service_instance


class PortfolioService:
    """
    Centralized service for portfolio/holdings management

    Provides unified interface for:
    - Checking if symbol is in holdings
    - Getting current positions
    - Portfolio count and capacity checks
    - Caching for performance
    """

    def __init__(  # noqa: PLR0913
        self,
        portfolio: KotakNeoPortfolio | None = None,
        orders: KotakNeoOrders | None = None,
        auth: KotakNeoAuth | None = None,
        strategy_config=None,
        orders_repo=None,
        user_id: int | None = None,
        enable_caching: bool = True,
        cache_ttl: int = 120,
    ):
        """
        Initialize PortfolioService

        Args:
            portfolio: KotakNeoPortfolio instance
            orders: KotakNeoOrders instance
            auth: KotakNeoAuth instance (for 2FA handling)
            strategy_config: StrategyConfig instance (for portfolio limits)
            orders_repo: OrdersRepository instance (optional, for database order checks)
            user_id: User ID (optional, for database order checks)
            enable_caching: Enable caching (default: True)
            cache_ttl: Cache TTL in seconds (default: 120 / 2 minutes)
        """
        self.portfolio = portfolio
        self.orders = orders
        self.auth = auth
        self.strategy_config = strategy_config
        self.orders_repo = orders_repo
        self.user_id = user_id
        self.enable_caching = enable_caching
        self._cache = PortfolioCache(ttl_seconds=cache_ttl) if enable_caching else None

    @staticmethod
    def _symbol_variants(base: str) -> list[str]:
        """
        Generate symbol variants for matching

        Args:
            base: Base symbol (e.g., 'RELIANCE')

        Returns:
            List of symbol variants
        """
        base = base.upper()
        return [base, f"{base}-EQ", f"{base}-BE", f"{base}-BL", f"{base}-BZ"]

    def _response_requires_2fa(self, response: dict) -> bool:
        """
        Check if response indicates 2FA gate

        Args:
            response: API response dictionary

        Returns:
            True if 2FA required, False otherwise
        """
        if not isinstance(response, dict):
            return False

        # Check for common 2FA indicators
        error_msg = str(response.get("error", "")).lower()
        error_desc = str(response.get("errorDescription", "")).lower()
        message = str(response.get("message", "")).lower()

        two_fa_indicators = [
            "2fa",
            "two factor",
            "otp",
            "authenticate",
            "verification",
            "login required",
        ]

        return any(
            indicator in error_msg or indicator in error_desc or indicator in message
            for indicator in two_fa_indicators
        )

    def _fetch_holdings(self) -> dict:
        """
        Fetch holdings from broker API with 2FA handling

        Returns:
            Holdings dictionary or empty dict
        """
        if not self.portfolio:
            return {}

        # Check cache first
        if self.enable_caching and self._cache:
            cached = self._cache.get("holdings")
            if cached is not None:
                return cached

        # Fetch from broker
        h = self.portfolio.get_holdings() or {}

        # Check for 2FA gate - if detected, force re-login and retry once
        if self._response_requires_2fa(h) and self.auth and hasattr(self.auth, "force_relogin"):
            logger.info("2FA gate detected in holdings check, attempting re-login...")
            try:
                if self.auth.force_relogin():
                    h = self.portfolio.get_holdings() or {}
                    logger.debug("Holdings re-fetched after re-login")
            except Exception as e:
                logger.warning(f"Re-login failed during holdings check: {e}")

        # Cache the result
        if self.enable_caching and self._cache:
            self._cache.set("holdings", h)

        return h

    def _fetch_holdings_symbols(self) -> set[str]:
        """
        Fetch set of symbols currently in holdings

        Returns:
            Set of symbol strings
        """
        h = self._fetch_holdings()
        symbols = set()

        for item in h.get("data") or []:
            sym = str(item.get("tradingSymbol") or "").upper()
            if sym:
                symbols.add(sym)

        return symbols

    def has_position(self, base_symbol: str) -> bool:
        """
        Check if symbol is in holdings (unified holdings check)

        Replaces: AutoTradeEngine.has_holding()

        Args:
            base_symbol: Base symbol to check (e.g., 'RELIANCE')

        Returns:
            True if symbol is in holdings, False otherwise
        """
        if not self.portfolio:
            return False

        variants = set(self._symbol_variants(base_symbol))
        h = self._fetch_holdings()

        for item in h.get("data") or []:
            sym = str(item.get("tradingSymbol") or "").upper()
            if sym in variants:
                return True

        return False

    def get_current_positions(self, include_pending: bool = True) -> list[str]:
        """
        Get list of symbols currently in portfolio

        Replaces: AutoTradeEngine.current_symbols_in_portfolio()

        Includes:
        - Holdings from broker API
        - Pending orders from broker API
        - ONGOING/CLOSED orders from database (executed orders that may not be in broker holdings yet)
        - PENDING orders from database (if broker API doesn't return them)

        Args:
            include_pending: Include pending BUY orders (default: True)

        Returns:
            Sorted list of symbol strings
        """
        symbols = set(self._fetch_holdings_symbols())

        # Include pending BUY orders from broker API if requested
        if include_pending and self.orders:
            try:
                pend = self.orders.get_pending_orders() or []
                for o in pend:
                    txn = str(o.get("transactionType", "")).upper()
                    if txn.startswith("B"):
                        sym = str(o.get("tradingSymbol") or "").upper()
                        if sym:
                            symbols.add(sym)
            except Exception as e:
                logger.warning(f"Failed to get pending orders from broker API: {e}")

        # CRITICAL FIX: Also include database orders (ONGOING, CLOSED, and PENDING)
        # This ensures we count executed orders that may not appear in broker holdings yet
        # and pending orders that broker API might not return
        if include_pending and self.orders_repo and self.user_id:
            try:
                # Get all buy orders from database with ONGOING, CLOSED (filled), or PENDING status
                # EXCLUDE stale PENDING orders using same logic as EOD cleanup
                # (orders past next trading day market close) to prevent them from blocking new orders
                try:
                    from modules.kotak_neo_auto_trader.utils.trading_day_utils import (  # noqa: PLC0415
                        get_next_trading_day_close,
                    )
                except ImportError:
                    # Fallback to 24-hour check if trading_day_utils not available
                    from datetime import timedelta  # noqa: PLC0415

                    get_next_trading_day_close = None

                from src.infrastructure.db.timezone_utils import IST, ist_now  # noqa: PLC0415

                db_orders, _ = self.orders_repo.list(self.user_id)
                now = ist_now()
                # Normalize to IST for consistent comparison
                if now.tzinfo is None:
                    now = now.replace(tzinfo=IST)
                elif now.tzinfo != IST:
                    now = now.astimezone(IST)

                for order in db_orders:
                    if order.side == "buy" and order.status in {
                        DbOrderStatus.ONGOING,  # Legacy executed orders (may not be in broker yet)
                        DbOrderStatus.CLOSED,  # Filled orders (position open; may not be in broker yet)
                        DbOrderStatus.PENDING,  # Pending orders (if broker API doesn't return them)
                    }:
                        # For PENDING orders, check if they're stale using same logic as EOD cleanup
                        # Stale PENDING orders should not count towards portfolio limit
                        # as they likely failed or were cancelled but status wasn't updated
                        if order.status == DbOrderStatus.PENDING and order.placed_at:
                            is_stale = False
                            placed_at = order.placed_at

                            try:
                                if get_next_trading_day_close:
                                    # Use trading-day-aware logic (same as EOD cleanup)
                                    # Calculate next trading day market close from when order was placed
                                    # Normalize placed_at to IST for comparison
                                    if placed_at.tzinfo is None:
                                        placed_at = placed_at.replace(tzinfo=IST)
                                    elif placed_at.tzinfo != IST:
                                        placed_at = placed_at.astimezone(IST)

                                    next_trading_day_close = get_next_trading_day_close(placed_at)

                                    # If current time is after next trading day market close, order is stale
                                    is_stale = now > next_trading_day_close

                                    if is_stale:
                                        age_hours = (now - placed_at).total_seconds() / 3600
                                        logger.debug(
                                            f"Excluding stale PENDING order from portfolio count: "
                                            f"{order.symbol} (placed_at: {placed_at.strftime('%Y-%m-%d %H:%M')}, "
                                            f"next trading day close: {next_trading_day_close.strftime('%Y-%m-%d %H:%M')}, "
                                            f"age: {age_hours:.1f}h)"
                                        )
                                else:
                                    # Fallback to 24-hour check if trading_day_utils not available
                                    from datetime import timedelta  # noqa: PLC0415

                                    stale_cutoff = now - timedelta(hours=24)
                                    if placed_at.tzinfo is None:
                                        placed_at_naive = placed_at.replace(tzinfo=None)
                                        cutoff_naive = (
                                            stale_cutoff.replace(tzinfo=None)
                                            if stale_cutoff.tzinfo
                                            else stale_cutoff
                                        )
                                        is_stale = placed_at_naive < cutoff_naive
                                    else:
                                        placed_at_ist = (
                                            placed_at.astimezone(IST)
                                            if placed_at.tzinfo != IST
                                            else placed_at
                                        )
                                        is_stale = placed_at_ist < stale_cutoff

                                    if is_stale:
                                        age_hours = (now - placed_at_ist).total_seconds() / 3600
                                        logger.debug(
                                            f"Excluding stale PENDING order from portfolio count (fallback): "
                                            f"{order.symbol} (placed_at: {placed_at_ist}, age: {age_hours:.1f}h)"
                                        )
                            except Exception as e:
                                # If stale check fails (e.g., holiday calendar issue), log and include order
                                # This is safer than excluding valid orders due to a bug
                                logger.warning(
                                    f"Failed to check if PENDING order is stale for {order.symbol}: {e}. "
                                    f"Including order in portfolio count to be safe."
                                )
                                # is_stale remains False, so order will be included

                            if is_stale:
                                continue  # Skip stale PENDING orders

                        # Normalize symbol (remove -EQ, -BE, etc. suffixes)
                        sym = (
                            order.symbol.upper()
                            .replace("-EQ", "")
                            .replace("-BE", "")
                            .replace("-BL", "")
                            .replace("-BZ", "")
                        )
                        if sym:
                            symbols.add(sym)
            except Exception as e:
                logger.warning(f"Failed to get orders from database: {e}")

        return sorted(symbols)

    def get_portfolio_count(self, include_pending: bool = True) -> int:
        """
        Get current portfolio size (number of positions)

        Args:
            include_pending: Include pending BUY orders (default: True)

        Returns:
            Number of positions in portfolio
        """
        return len(self.get_current_positions(include_pending=include_pending))

    def check_portfolio_capacity(
        self, include_pending: bool = True, max_size: int | None = None
    ) -> tuple[bool, int, int]:
        """
        Check if portfolio has capacity for new positions

        Args:
            include_pending: Include pending BUY orders in count (default: True)
            max_size: Maximum portfolio size (uses strategy_config if None)

        Returns:
            Tuple of (has_capacity, current_count, max_size)
        """
        current_count = self.get_portfolio_count(include_pending=include_pending)

        if max_size is None:
            if self.strategy_config and hasattr(self.strategy_config, "max_portfolio_size"):
                max_size = self.strategy_config.max_portfolio_size
            else:
                # Default to config value
                max_size = getattr(config, "MAX_PORTFOLIO_SIZE", 10)

        has_capacity = current_count < max_size
        return (has_capacity, current_count, max_size)

    def clear_cache(self) -> None:
        """Clear all cached portfolio data"""
        if self._cache:
            self._cache.clear()

    def invalidate_holdings_cache(self) -> None:
        """Invalidate holdings cache (force refresh on next fetch)"""
        if self._cache:
            self._cache.invalidate("holdings")
