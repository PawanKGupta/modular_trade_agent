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
            enable_caching: Enable caching (default: True)
            cache_ttl: Cache TTL in seconds (default: 120 / 2 minutes)
        """
        self.portfolio = portfolio
        self.orders = orders
        self.auth = auth
        self.strategy_config = strategy_config
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

        Args:
            include_pending: Include pending BUY orders (default: True)

        Returns:
            Sorted list of symbol strings
        """
        symbols = set(self._fetch_holdings_symbols())

        # Include pending BUY orders if requested
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
                logger.warning(f"Failed to get pending orders: {e}")

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
