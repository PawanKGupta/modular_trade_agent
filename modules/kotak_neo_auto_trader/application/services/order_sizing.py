"""
Order Sizing Service
Calculate order quantity based on capital and price
"""

from dataclasses import dataclass
from decimal import Decimal
from ...domain import Money


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

        # Check if order value exceeds max
        order_value = price * quantity
        if order_value > self.config.max_order_value:
            # Recalculate based on max order value
            quantity = int(self.config.max_order_value.amount / price.amount)

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
