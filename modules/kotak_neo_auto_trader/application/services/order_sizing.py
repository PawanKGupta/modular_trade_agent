"""
Order Sizing Service
Calculate order quantity based on capital and price
"""

import logging
from dataclasses import dataclass

from ...domain import Money
from ...utils.order_sizing_helper import apply_max_order_value_cap

logger = logging.getLogger(__name__)


@dataclass
class TradingConfig:
    """Trading configuration for order sizing"""

    capital_per_trade: Money = Money.from_int(100000)  # Rs 1 lakh per trade
    min_quantity: int = 1
    max_quantity: int = 100000
    max_order_value: Money = Money.from_int(500000)  # Rs 5 lakh max per order


@dataclass
class OrderSizingService:
    """
    Service for calculating order quantities

    Determines how many shares to buy based on available capital and price
    """

    config: TradingConfig

    def calculate_quantity(self, symbol: str, price: Money, available_balance: Money = None) -> int:
        """
        Calculate order quantity based on capital and price

        Args:
            symbol: Stock symbol
            price: Current price per share
            available_balance: Available cash balance (optional, uses config if not provided)

        Returns:
            Quantity to order (0 if insufficient funds or invalid price)
        """
        # Validate price
        if price.amount <= 0:
            return 0

        # Use available balance or default capital
        capital = available_balance if available_balance else self.config.capital_per_trade

        if capital.amount <= 0:
            return 0

        # Calculate affordable quantity
        quantity = int(capital.amount / price.amount)

        # Apply min/max constraints
        if quantity < self.config.min_quantity:
            return 0

        quantity = min(quantity, self.config.max_quantity)

        # Apply max order value cap using shared helper
        quantity = apply_max_order_value_cap(
            qty=quantity,
            price=price.amount,
            min_qty=self.config.min_quantity,
            symbol=symbol,
            max_order_val=self.config.max_order_value.amount,
        )

        return max(quantity, 0)

    def can_afford(self, quantity: int, price: Money, available_balance: Money) -> bool:
        """
        Check if can afford the order

        Args:
            quantity: Number of shares
            price: Price per share
            available_balance: Available cash

        Returns:
            True if can afford, False otherwise
        """
        order_value = price * quantity
        return available_balance >= order_value

    def get_order_value(self, quantity: int, price: Money) -> Money:
        """
        Calculate total order value

        Args:
            quantity: Number of shares
            price: Price per share

        Returns:
            Total value of the order
        """
        return price * quantity
