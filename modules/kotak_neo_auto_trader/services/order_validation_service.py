"""
Order Validation Service

Centralized service for order placement validation.
Eliminates duplicate validation logic across services.

Phase 3.1: Order Validation & Verification
"""

import sys
from dataclasses import dataclass
from math import floor
from pathlib import Path
from threading import Lock
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import logger  # noqa: E402

try:
    from config.settings import POSITION_VOLUME_RATIO_TIERS
except ImportError:
    from config.settings import POSITION_VOLUME_RATIO_TIERS  # noqa: E402


@dataclass
class ValidationResult:
    """Result of order validation"""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    data: dict[str, Any] | None = None

    def __post_init__(self):
        """Ensure lists are initialized"""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.data is None:
            self.data = {}

    def add_error(self, error: str) -> None:
        """Add an error message"""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning message"""
        self.warnings.append(warning)

    def get_error_summary(self) -> str:
        """Get formatted error summary"""
        if not self.errors:
            return ""
        return "; ".join(self.errors)

    def get_warning_summary(self) -> str:
        """Get formatted warning summary"""
        if not self.warnings:
            return ""
        return "; ".join(self.warnings)


# Singleton instance
_order_validation_service_instance: "OrderValidationService | None" = None
_order_validation_service_lock = Lock()


def get_order_validation_service(
    portfolio_service=None,
    portfolio=None,
    orders=None,
    orders_repo=None,
    user_id=None,
) -> "OrderValidationService":
    """
    Get or create OrderValidationService singleton instance

    Args:
        portfolio_service: PortfolioService instance (optional)
        portfolio: KotakNeoPortfolio instance (optional)
        orders: KotakNeoOrders instance (optional)

    Returns:
        OrderValidationService instance
    """
    global _order_validation_service_instance  # noqa: PLW0603

    with _order_validation_service_lock:
        if _order_validation_service_instance is None:
            _order_validation_service_instance = OrderValidationService(
                portfolio_service=portfolio_service,
                portfolio=portfolio,
                orders=orders,
                orders_repo=orders_repo,
                user_id=user_id,
            )

        # Update dependencies if provided
        if portfolio_service and (
            _order_validation_service_instance.portfolio_service != portfolio_service
        ):
            _order_validation_service_instance.portfolio_service = portfolio_service
        if portfolio and (
            _order_validation_service_instance.portfolio != portfolio
        ):
            _order_validation_service_instance.portfolio = portfolio
        if orders and (
            _order_validation_service_instance.orders != orders
        ):
            _order_validation_service_instance.orders = orders
        if orders_repo and (
            _order_validation_service_instance.orders_repo != orders_repo
        ):
            _order_validation_service_instance.orders_repo = orders_repo
        if user_id is not None and (
            _order_validation_service_instance.user_id != user_id
        ):
            _order_validation_service_instance.user_id = user_id

        return _order_validation_service_instance


class OrderValidationService:
    """
    Centralized service for order placement validation

    Provides unified interface for:
    - Balance checks
    - Portfolio capacity checks
    - Duplicate order checks
    - Volume ratio checks
    - Comprehensive validation
    """

    def __init__(
        self,
        portfolio_service=None,
        portfolio=None,
        orders=None,
        orders_repo=None,
        user_id=None,
    ):
        """
        Initialize OrderValidationService

        Args:
            portfolio_service: PortfolioService instance (optional)
            portfolio: KotakNeoPortfolio instance (optional, for direct balance checks)
            orders: KotakNeoOrders instance (optional, for duplicate checks)
            orders_repo: OrdersRepository instance (optional, for database duplicate checks)
            user_id: User ID (optional, for database duplicate checks)
        """
        self.portfolio_service = portfolio_service
        self.portfolio = portfolio
        self.orders = orders
        self.orders_repo = orders_repo
        self.user_id = user_id

    def check_balance(
        self, price: float, required_qty: int | None = None
    ) -> tuple[bool, float, int]:
        """
        Check if sufficient balance is available for order

        Args:
            price: Price per share
            required_qty: Required quantity (optional, if None returns affordable qty)

        Returns:
            Tuple of (has_sufficient_balance, available_cash, affordable_qty)
        """
        available_cash = self.get_available_cash()
        affordable_qty = self.get_affordable_qty(price) if price > 0 else 0

        if required_qty is None:
            # Just return balance info
            return (True, available_cash, affordable_qty)

        # Check if required quantity is affordable
        has_sufficient = affordable_qty >= required_qty
        return (has_sufficient, available_cash, affordable_qty)

    def get_available_cash(self) -> float:
        """
        Get available cash from portfolio limits

        Returns:
            Available cash amount
        """
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
            except Exception as e:
                logger.warning(f"Error parsing available cash: {e}")

        logger.debug(
            f"Available balance: Rs {avail:.2f} "
            f"(from limits API; key={used_key or 'n/a'})"
        )
        return avail

    def get_affordable_qty(self, price: float) -> int:
        """
        Get maximum affordable quantity for given price

        Args:
            price: Price per share

        Returns:
            Maximum affordable quantity
        """
        if not self.portfolio or not price or price <= 0:
            return 0

        available_cash = self.get_available_cash()
        try:
            return max(0, floor(available_cash / float(price)))
        except Exception:
            return 0

    def check_portfolio_capacity(
        self, include_pending: bool = True
    ) -> tuple[bool, int, int]:
        """
        Check portfolio capacity

        Delegates to PortfolioService if available, otherwise returns (True, 0, 999)

        Args:
            include_pending: Include pending orders in count

        Returns:
            Tuple of (has_capacity, current_count, max_size)
        """
        if self.portfolio_service:
            return self.portfolio_service.check_portfolio_capacity(
                include_pending=include_pending
            )

        # Fallback: assume capacity available if PortfolioService not available
        logger.warning(
            "PortfolioService not available for capacity check - assuming capacity available"
        )
        return (True, 0, 999)

    def check_duplicate_order(
        self,
        symbol: str,
        check_active_buy_order: bool = True,
        check_holdings: bool = True,
        allow_reentry: bool = False,
    ) -> tuple[bool, str | None]:
        """
        Check if order would be duplicate

        Args:
            symbol: Symbol to check
            check_active_buy_order: Check for active buy orders (broker API + database)
            check_holdings: Check if already in holdings
            allow_reentry: If True, skip holdings check (allows buying more of existing position)

        Returns:
            Tuple of (is_duplicate, reason)
        """
        variants = set(self._symbol_variants(symbol))

        # Check for active buy orders (broker API first)
        if check_active_buy_order and self.orders:
            try:
                pend = self.orders.get_pending_orders() or []
                for o in pend:
                    txn = str(o.get("transactionType") or "").upper()
                    sym = str(o.get("tradingSymbol") or "").upper()
                    if txn.startswith("B") and sym in variants:
                        return (True, f"Active buy order exists for {symbol} (broker API)")
            except Exception as e:
                logger.warning(f"Error checking pending orders for duplicates: {e}")

        # Database fallback: Check for PENDING/ONGOING buy orders
        if (
            check_active_buy_order
            and self.orders_repo
            and self.user_id
        ):
            try:
                from src.infrastructure.db.models import OrderStatus as DbOrderStatus

                existing_orders = self.orders_repo.list(self.user_id)
                symbol_base = symbol.upper().replace("-EQ", "").replace("-BE", "").replace("-BL", "").replace("-BZ", "")

                for existing_order in existing_orders:
                    order_symbol_base = (
                        existing_order.symbol.upper()
                        .replace("-EQ", "")
                        .replace("-BE", "")
                        .replace("-BL", "")
                        .replace("-BZ", "")
                    )

                    if (
                        existing_order.side == "buy"
                        and existing_order.status
                        in [DbOrderStatus.PENDING, DbOrderStatus.ONGOING]
                        and order_symbol_base == symbol_base
                    ):
                        return (
                            True,
                            f"Active buy order exists for {symbol} (database: {existing_order.status})",
                        )
            except Exception as e:
                logger.warning(f"Error checking database for duplicate orders: {e}")

        # Check if already in holdings (broker API)
        # Skip holdings check if allow_reentry=True (reentries should allow buying more)
        if check_holdings and not allow_reentry and self.portfolio_service:
            try:
                if self.portfolio_service.has_position(symbol):
                    return (True, f"Already in holdings: {symbol}")
            except Exception as e:
                logger.warning(f"Error checking holdings for duplicates: {e}")

        # Also check positions table (includes pre-existing holdings)
        # Skip positions check if allow_reentry=True (reentries should allow buying more)
        if check_holdings and not allow_reentry and self.orders_repo and self.user_id:
            try:
                from src.infrastructure.persistence.positions_repository import (
                    PositionsRepository,
                )

                # Get positions repository from orders_repo's db session
                if hasattr(self.orders_repo, "db"):
                    positions_repo = PositionsRepository(self.orders_repo.db)
                    symbol_base = (
                        symbol.upper()
                        .replace("-EQ", "")
                        .replace("-BE", "")
                        .replace("-BL", "")
                        .replace("-BZ", "")
                    )
                    existing_position = positions_repo.get_by_symbol(
                        self.user_id, symbol_base
                    )
                    if existing_position and existing_position.closed_at is None:
                        return (
                            True,
                            f"Already in positions table: {symbol} (qty: {existing_position.quantity})",
                        )
            except Exception as e:
                logger.warning(f"Error checking positions table for duplicates: {e}")

        return (False, None)

    def check_volume_ratio(
        self, qty: int, avg_volume: float, symbol: str, price: float = 0
    ) -> tuple[bool, float | None, str | None]:
        """
        Check if position size is within acceptable range of daily volume

        Args:
            qty: Quantity to check
            avg_volume: Average daily volume
            symbol: Symbol name
            price: Price per share (optional, for tier determination)

        Returns:
            Tuple of (is_valid, ratio, tier_info)
        """
        if avg_volume <= 0:
            logger.warning(f"{symbol}: No volume data available")
            return (False, None, None)

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

        ratio = qty / avg_volume if avg_volume > 0 else float("inf")
        if ratio > max_ratio:
            logger.warning(
                f"{symbol}: Position too large relative to volume "
                f"(price=Rs {price:.2f}, qty={qty}, avg_vol={int(avg_volume)}, "
                f"ratio={ratio:.1%} > {max_ratio:.1%} for tier {tier_used})"
            )
            return (False, ratio, tier_used)

        logger.debug(
            f"{symbol}: Volume check passed "
            f"(ratio={ratio:.2%} of daily volume, tier={tier_used})"
        )
        return (True, ratio, tier_used)

    def validate_order_placement(
        self,
        symbol: str,
        price: float,
        qty: int,
        avg_volume: float | None = None,
        check_balance: bool = True,
        check_capacity: bool = True,
        check_duplicate: bool = True,
        check_volume: bool = True,
        include_pending: bool = True,
    ) -> ValidationResult:
        """
        Comprehensive order placement validation

        Args:
            symbol: Symbol to validate
            price: Price per share
            qty: Quantity to validate
            avg_volume: Average daily volume (for volume ratio check)
            check_balance: Check balance availability
            check_capacity: Check portfolio capacity
            check_duplicate: Check for duplicate orders/holdings
            check_volume: Check volume ratio
            include_pending: Include pending orders in capacity check

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Check balance
        if check_balance:
            has_sufficient, available_cash, affordable_qty = self.check_balance(
                price, qty
            )
            result.data["available_cash"] = available_cash
            result.data["affordable_qty"] = affordable_qty
            result.data["required_cash"] = qty * price

            if not has_sufficient:
                shortfall = max(0.0, (qty * price) - available_cash)
                result.add_error(
                    f"Insufficient balance: need Rs {qty * price:,.0f}, "
                    f"available Rs {available_cash:,.0f} (shortfall: Rs {shortfall:,.0f})"
                )

        # Check portfolio capacity
        if check_capacity:
            has_capacity, current_count, max_size = self.check_portfolio_capacity(
                include_pending=include_pending
            )
            result.data["current_portfolio_count"] = current_count
            result.data["max_portfolio_size"] = max_size

            if not has_capacity:
                result.add_error(
                    f"Portfolio at capacity: {current_count}/{max_size} positions"
                )

        # Check duplicate order
        if check_duplicate:
            is_duplicate, reason = self.check_duplicate_order(symbol)
            if is_duplicate:
                result.add_error(f"Duplicate order: {reason}")

        # Check volume ratio
        if check_volume and avg_volume is not None and avg_volume > 0:
            is_valid_volume, ratio, tier_info = self.check_volume_ratio(
                qty, avg_volume, symbol, price
            )
            result.data["volume_ratio"] = ratio
            result.data["volume_tier"] = tier_info

            if not is_valid_volume:
                result.add_error(
                    f"Position too large for volume: "
                    f"ratio {ratio:.1%} exceeds limit for tier {tier_info}"
                )

        return result

    @staticmethod
    def _symbol_variants(base: str) -> list[str]:
        """Generate symbol variants for matching"""
        base = base.upper()
        return [base, f"{base}-EQ", f"{base}-BE", f"{base}-BL", f"{base}-BZ"]

