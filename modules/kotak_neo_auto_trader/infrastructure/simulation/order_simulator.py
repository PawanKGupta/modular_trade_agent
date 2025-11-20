"""
Order Simulator
Simulates realistic order execution with slippage and fees
"""

import random
import time
from typing import Optional, Tuple
from datetime import datetime, time as dt_time

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

from ...domain import Order, Money, OrderType, OrderStatus
from ...config.paper_trading_config import PaperTradingConfig
from .price_provider import PriceProvider


class OrderSimulator:
    """
    Simulates order execution

    Features:
    - Market order instant execution
    - Limit order conditional execution
    - Realistic slippage
    - Trading fees calculation
    - Market hours enforcement
    - Execution delay simulation
    """

    def __init__(self, config: PaperTradingConfig, price_provider: PriceProvider):
        """
        Initialize order simulator

        Args:
            config: Paper trading configuration
            price_provider: Price provider for fetching prices
        """
        self.config = config
        self.price_provider = price_provider

    def execute_order(self, order: Order) -> Tuple[bool, str, Optional[Money]]:
        """
        Simulate order execution

        Args:
            order: Order to execute

        Returns:
            Tuple of (success, message, execution_price)
        """
        # Check market hours
        if not self._is_market_open(order):
            return False, "Market is closed", None

        # Simulate execution delay
        if not self.config.instant_execution:
            self._simulate_delay()

        # Get current price
        current_price = self.price_provider.get_price(order.symbol)
        if current_price is None:
            return False, f"Price not available for {order.symbol}", None

        current_price_money = Money(current_price)

        # Execute based on order type
        if order.order_type == OrderType.MARKET:
            return self._execute_market_order(order, current_price_money)
        elif order.order_type == OrderType.LIMIT:
            return self._execute_limit_order(order, current_price_money)
        else:
            return False, f"Unsupported order type: {order.order_type}", None

    def _execute_market_order(self, order: Order, current_price: Money) -> Tuple[bool, str, Money]:
        """
        Execute market order with slippage

        Args:
            order: Market order
            current_price: Current market price

        Returns:
            Tuple of (success, message, execution_price)
        """
        # Apply slippage
        execution_price = self._apply_slippage(current_price, order.is_buy_order())

        logger.info(
            f"? Market order executed: {order.symbol} "
            f"@ Rs {execution_price.amount:.2f} "
            f"(Current: Rs {current_price.amount:.2f})"
        )

        return True, "Order executed", execution_price

    def _execute_limit_order(
        self, order: Order, current_price: Money
    ) -> Tuple[bool, str, Optional[Money]]:
        """
        Execute limit order if price condition is met

        Args:
            order: Limit order
            current_price: Current market price

        Returns:
            Tuple of (success, message, execution_price or None)
        """
        if order.price is None:
            return False, "Limit order requires price", None

        # Check if limit price condition is met
        if order.is_buy_order():
            # Buy limit: execute if current price <= limit price
            if current_price.amount <= order.price.amount:
                execution_price = order.price  # Execute at limit price
                logger.info(
                    f"? Limit BUY executed: {order.symbol} "
                    f"@ Rs {execution_price.amount:.2f} "
                    f"(Limit: Rs {order.price.amount:.2f})"
                )
                return True, "Limit order executed", execution_price
            else:
                return False, "Price above limit", None
        else:
            # Sell limit: execute if current price >= limit price
            if current_price.amount >= order.price.amount:
                execution_price = order.price  # Execute at limit price
                logger.info(
                    f"? Limit SELL executed: {order.symbol} "
                    f"@ Rs {execution_price.amount:.2f} "
                    f"(Limit: Rs {order.price.amount:.2f})"
                )
                return True, "Limit order executed", execution_price
            else:
                return False, "Price below limit", None

    def _apply_slippage(self, price: Money, is_buy: bool) -> Money:
        """
        Apply realistic slippage to price

        Args:
            price: Base price
            is_buy: True for buy orders, False for sell orders

        Returns:
            Price with slippage applied
        """
        if not self.config.enable_slippage:
            return price

        # Random slippage within configured range
        min_slip, max_slip = self.config.slippage_range
        slippage_pct = random.uniform(min_slip, max_slip) / 100

        # Buy orders get positive slippage (pay more)
        # Sell orders get negative slippage (receive less)
        if is_buy:
            slipped_price = float(price.amount) * (1 + slippage_pct)
        else:
            slipped_price = float(price.amount) * (1 - slippage_pct)

        return Money(slipped_price)

    def calculate_charges(self, order_value: float, is_buy: bool) -> float:
        """
        Calculate total trading charges

        Args:
            order_value: Total order value in INR
            is_buy: True for buy orders, False for sell orders

        Returns:
            Total charges in INR
        """
        return self.config.calculate_charges(order_value, is_buy)

    def _is_market_open(self, order: Order) -> bool:
        """
        Check if market is open for the order

        Args:
            order: Order to check

        Returns:
            True if market is open or enforcement disabled
        """
        if not self.config.enforce_market_hours:
            return True

        # AMO orders are allowed anytime
        if order.is_amo_order():
            return True

        # Check current time
        now = datetime.now().time()
        market_open = dt_time.fromisoformat(self.config.market_open_time)
        market_close = dt_time.fromisoformat(self.config.market_close_time)

        is_open = market_open <= now <= market_close

        if not is_open:
            logger.warning(
                f"[WARN]? Market closed (Hours: {self.config.market_open_time} - "
                f"{self.config.market_close_time})"
            )

        return is_open

    def _simulate_delay(self) -> None:
        """Simulate network/execution delay"""
        if self.config.execution_delay_ms > 0:
            delay_seconds = self.config.execution_delay_ms / 1000
            time.sleep(delay_seconds)

    def should_execute_amo(self, order: Order) -> bool:
        """
        Check if AMO order should execute now

        Args:
            order: AMO order

        Returns:
            True if it's time to execute AMO
        """
        if not order.is_amo_order():
            return False

        now = datetime.now().time()
        amo_time = dt_time.fromisoformat(self.config.amo_execution_time)

        # Execute if current time >= AMO execution time
        return now >= amo_time

    def validate_order_value(self, order_value: float, available_cash: float) -> Tuple[bool, str]:
        """
        Validate order value against limits

        Args:
            order_value: Total order value
            available_cash: Available cash

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check sufficient funds
        if self.config.check_sufficient_funds:
            total_required = order_value

            # Add charges for buy orders
            charges = self.calculate_charges(order_value, is_buy=True)
            total_required += charges

            if total_required > available_cash:
                return False, (
                    f"Insufficient funds: Need Rs {total_required:.2f}, "
                    f"Available Rs {available_cash:.2f}"
                )

        # Check max position size
        if order_value > self.config.max_position_size:
            return False, (
                f"Order value Rs {order_value:.2f} exceeds "
                f"max position size Rs {self.config.max_position_size:.2f}"
            )

        return True, ""

    def get_execution_summary(self, order: Order, execution_price: Money) -> dict:
        """
        Get detailed execution summary

        Args:
            order: Executed order
            execution_price: Execution price

        Returns:
            Dictionary with execution details
        """
        order_value = float(execution_price.amount) * order.quantity
        charges = self.calculate_charges(order_value, order.is_buy_order())
        net_value = order_value + charges if order.is_buy_order() else order_value - charges

        return {
            "symbol": order.symbol,
            "quantity": order.quantity,
            "execution_price": float(execution_price.amount),
            "order_value": order_value,
            "charges": charges,
            "net_value": net_value,
            "order_type": order.order_type.value,
            "transaction_type": order.transaction_type.value,
            "executed_at": datetime.now().isoformat(),
        }
