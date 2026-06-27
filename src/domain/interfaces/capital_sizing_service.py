"""
CapitalSizingService Interface - Domain Layer

Abstract interface for checking cash limits, checking margins via check-margin APIs,
and calculating capital size/affordable quantities based on portfolio rules.
"""

from abc import ABC, abstractmethod


class ICapitalSizingService(ABC):
    """Interface for capital sizing, cash limits, and margin checks."""

    @abstractmethod
    def get_affordable_qty(self, price: float) -> int:
        """
        Calculate the maximum quantity of stock affordable based on available cash/margin.

        Args:
            price: Price per share

        Returns:
            Maximum integer quantity affordable
        """
        raise NotImplementedError

    @abstractmethod
    def get_available_cash(self) -> float:
        """
        Get the current available cash from the broker/portfolio limits.

        Returns:
            Available cash balance as float
        """
        raise NotImplementedError

    @abstractmethod
    def check_order_margin(
        self,
        symbol: str,
        price: float,
        qty: int,
        transaction_type: str = "B",
        product: str = "CNC",
    ) -> tuple[bool, float, float, float, bool]:
        """
        Validate whether the portfolio has enough margin/cash to place an order.

        Args:
            symbol: Ticker symbol (e.g. RELIANCE-EQ)
            price: Order price
            qty: Order quantity
            transaction_type: "B" for buy, "S" for sell
            product: Product type (e.g. CNC)

        Returns:
            Tuple of:
            - has_sufficient (bool)
            - available_cash (float)
            - required_margin (float)
            - shortfall (float)
            - margin_api_ok (bool)
        """
        raise NotImplementedError

    @abstractmethod
    def calculate_execution_capital(self, ticker: str, close: float, avg_volume: float) -> float:
        """
        Calculate dynamic execution capital based on stock parameters/liquidity.

        Args:
            ticker: Ticker symbol
            close: Close price
            avg_volume: Average trading volume

        Returns:
            Calculated execution capital as float
        """
        raise NotImplementedError
