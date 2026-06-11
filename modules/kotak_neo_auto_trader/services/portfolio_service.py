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
    positions_repo=None,
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
        positions_repo: PositionsRepository instance (optional, for system holdings count)
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
            positions_repo=positions_repo,
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
    if positions_repo is not None:
        _portfolio_service_instance.positions_repo = positions_repo
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
        positions_repo=None,
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
            positions_repo: PositionsRepository instance (optional, for system holdings count)
            user_id: User ID (optional, for database order checks)
            enable_caching: Enable caching (default: True)
            cache_ttl: Cache TTL in seconds (default: 120 / 2 minutes)
        """
        self.portfolio = portfolio
        self.orders = orders
        self.auth = auth
        self.strategy_config = strategy_config
        self.orders_repo = orders_repo
        self.positions_repo = positions_repo
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

    @staticmethod
    def _normalize_base_symbol(sym: str) -> str:
        """Normalize a trading symbol to its base form (no series suffix)."""
        return (
            sym.upper()
            .replace("-EQ", "")
            .replace("-BE", "")
            .replace("-BL", "")
            .replace("-BZ", "")
        )

    @staticmethod
    def _extract_holding_symbol(item: dict) -> str:
        """Extract symbol from a Kotak holdings API row."""
        return str(
            item.get("tradingSymbol")
            or item.get("symbol")
            or item.get("instrumentName")
            or item.get("securitySymbol")
            or item.get("securityname")
            or item.get("stockName")
            or ""
        ).upper().strip()

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

    def _fetch_holdings_symbols(self, *, min_qty: int = 0) -> set[str]:
        """
        Fetch set of symbols from broker holdings API.

        Args:
            min_qty: When > 0, only include rows with quantity at least this value.

        Returns:
            Set of symbol strings (base-normalized when min_qty > 0).
        """
        h = self._fetch_holdings()
        symbols = set()

        for item in h.get("data") or []:
            if min_qty > 0:
                qty_raw = (
                    item.get("quantity") if item.get("quantity") is not None else item.get("qty")
                )
                qty = int(float(str(qty_raw or 0)))
                if qty < min_qty:
                    continue

            sym = self._extract_holding_symbol(item)
            if not sym:
                continue
            if min_qty > 0:
                sym = self._normalize_base_symbol(sym)
            symbols.add(sym)

        return symbols

    def _fetch_system_position_symbols(self) -> set[str]:
        """
        Fetch open system-tracked position symbols (Positions table).

        Manual or pre-existing broker demat holdings are excluded so
        max_portfolio_size applies to Rebound-managed positions only.
        """
        if self.positions_repo and self.user_id:
            symbols: set[str] = set()
            try:
                for pos in self.positions_repo.list(self.user_id):
                    if pos.closed_at is None and int(pos.quantity or 0) > 0:
                        base = self._normalize_base_symbol(pos.symbol)
                        if base:
                            symbols.add(base)
            except Exception as e:
                logger.warning(f"Failed to get system positions from database: {e}")
            return symbols

        if self.portfolio:
            logger.debug(
                "positions_repo not configured; falling back to broker holdings (qty>0) "
                "for portfolio count"
            )
            return self._fetch_holdings_symbols(min_qty=1)

        return set()

    def _add_database_buy_order_symbols(self, symbols: set[str]) -> None:
        """Reserve portfolio slots for active system buy orders not yet in positions."""
        if not self.orders_repo or not self.user_id:
            return

        try:
            from modules.kotak_neo_auto_trader.utils.trading_day_utils import (  # noqa: PLC0415
                get_next_trading_day_close,
            )
        except ImportError:
            from datetime import timedelta  # noqa: PLC0415

            get_next_trading_day_close = None

        from src.infrastructure.db.timezone_utils import IST, ist_now  # noqa: PLC0415

        try:
            db_orders, _ = self.orders_repo.list(self.user_id)
        except Exception as e:
            logger.warning(f"Failed to get orders from database: {e}")
            return

        now = ist_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=IST)
        elif now.tzinfo != IST:
            now = now.astimezone(IST)

        for order in db_orders:
            if order.side == "buy" and order.status in {
                DbOrderStatus.ONGOING,
                DbOrderStatus.CLOSED,
                DbOrderStatus.PENDING,
            }:
                placed_at_val = getattr(order, "placed_at", None)
                has_real_placed_at = placed_at_val is not None and "Mock" not in type(
                    placed_at_val
                ).__name__
                if order.status == DbOrderStatus.CLOSED and has_real_placed_at:
                    continue

                if order.status == DbOrderStatus.PENDING and order.placed_at:
                    is_stale = False
                    placed_at = order.placed_at

                    try:
                        if get_next_trading_day_close:
                            if placed_at.tzinfo is None:
                                placed_at = placed_at.replace(tzinfo=IST)
                            elif placed_at.tzinfo != IST:
                                placed_at = placed_at.astimezone(IST)

                            next_trading_day_close = get_next_trading_day_close(placed_at)
                            is_stale = now > next_trading_day_close

                            if is_stale:
                                age_hours = (now - placed_at).total_seconds() / 3600
                                logger.debug(
                                    f"Excluding stale PENDING order from portfolio count: "
                                    f"{order.symbol} (placed_at: {placed_at.strftime('%Y-%m-%d %H:%M')}, "
                                    f"next trading day close: "
                                    f"{next_trading_day_close.strftime('%Y-%m-%d %H:%M')}, "
                                    f"age: {age_hours:.1f}h)"
                                )
                        else:
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
                                    f"Excluding stale PENDING order from portfolio count "
                                    f"(fallback): {order.symbol} "
                                    f"(placed_at: {placed_at_ist}, age: {age_hours:.1f}h)"
                                )
                    except Exception as e:
                        logger.warning(
                            f"Failed to check if PENDING order is stale for {order.symbol}: {e}. "
                            f"Including order in portfolio count to be safe."
                        )

                    if is_stale:
                        continue

                sym = self._normalize_base_symbol(order.symbol)
                if sym:
                    symbols.add(sym)

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
            sym = str(
                item.get("tradingSymbol")
                or item.get("symbol")
                or item.get("instrumentName")
                or item.get("securitySymbol")
                or item.get("securityname")
                or item.get("stockName")
                or ""
            ).upper().strip()
            if sym in variants:
                return True

        return False

    def get_current_positions(self, include_pending: bool = True) -> list[str]:
        """
        Get list of symbols that count toward max_portfolio_size.

        Replaces: AutoTradeEngine.current_symbols_in_portfolio()

        Includes:
        - Open system positions (Positions table; excludes manual broker holdings)
        - ONGOING/CLOSED/PENDING buy orders from database (reserves slots for in-flight buys)

        Args:
            include_pending: Include pending BUY orders (default: True)

        Returns:
            Sorted list of base symbol strings
        """
        symbols = set(self._fetch_system_position_symbols())

        if include_pending:
            self._add_database_buy_order_symbols(symbols)

        return sorted(symbols)

    def get_portfolio_count(self, include_pending: bool = True) -> int:
        """
        Get current system portfolio size (number of positions toward max_portfolio_size).

        Counts open system positions plus in-flight system buy orders only;
        manual broker demat holdings are excluded.

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
