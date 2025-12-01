"""
Portfolio Manager
Tracks holdings, calculates P&L, manages positions
"""

from typing import Dict, Optional, List
from datetime import datetime
from threading import Lock

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

from ...domain import Holding, Money, Exchange


class PortfolioManager:
    """
    Manages paper trading portfolio

    Responsibilities:
    - Track holdings with average price
    - Update holdings on order execution
    - Calculate P&L (realized and unrealized)
    - Validate sell orders
    - Handle averaging down
    """

    def __init__(self):
        """Initialize portfolio manager"""
        self._holdings: Dict[str, Holding] = {}
        self._lock = Lock()
        self._realized_pnl = Money.zero()

    # ===== HOLDING MANAGEMENT =====

    def add_holding(
        self, symbol: str, quantity: int, price: Money, exchange: Exchange = Exchange.NSE
    ) -> Holding:
        """
        Add or update a holding (for buy orders)

        Args:
            symbol: Stock symbol
            quantity: Quantity to add
            price: Purchase price per share
            exchange: Stock exchange

        Returns:
            Updated holding
        """
        with self._lock:
            if symbol in self._holdings:
                # Update existing holding (averaging)
                holding = self._holdings[symbol]
                holding.add_quantity(quantity, price)
                logger.info(
                    f"? Updated holding {symbol}: "
                    f"{holding.quantity} @ avg Rs {holding.average_price.amount:.2f}"
                )
            else:
                # Create new holding
                holding = Holding(
                    symbol=symbol,
                    exchange=exchange,
                    quantity=quantity,
                    average_price=price,
                    current_price=price,
                    last_updated=datetime.now(),
                )
                self._holdings[symbol] = holding
                logger.info(f"? New holding {symbol}: " f"{quantity} @ Rs {price.amount:.2f}")

            return holding

    def reduce_holding(
        self, symbol: str, quantity: int, sale_price: Money
    ) -> tuple[Optional[Holding], Money]:
        """
        Reduce holding quantity (for sell orders)

        Args:
            symbol: Stock symbol
            quantity: Quantity to reduce
            sale_price: Sale price per share

        Returns:
            Tuple of (updated holding or None, realized P&L)

        Raises:
            ValueError: If insufficient quantity or symbol not found
        """
        with self._lock:
            if symbol not in self._holdings:
                raise ValueError(f"No holding found for {symbol}")

            holding = self._holdings[symbol]

            if holding.quantity < quantity:
                raise ValueError(
                    f"Insufficient quantity for {symbol}: "
                    f"Have {holding.quantity}, trying to sell {quantity}"
                )

            # Calculate realized P&L
            avg_cost = holding.average_price
            realized_pnl = (sale_price - avg_cost) * quantity
            self._realized_pnl += realized_pnl

            # Reduce quantity
            holding.reduce_quantity(quantity)

            logger.info(
                f"? Reduced holding {symbol}: "
                f"{holding.quantity} remaining, "
                f"Realized P&L: Rs {realized_pnl.amount:.2f}"
            )

            # Remove if quantity is zero
            if holding.quantity == 0:
                del self._holdings[symbol]
                logger.info(f"? Removed holding {symbol} (quantity = 0)")
                return None, realized_pnl

            return holding, realized_pnl

    def get_holding(self, symbol: str) -> Optional[Holding]:
        """Get holding by symbol"""
        with self._lock:
            return self._holdings.get(symbol)

    def get_all_holdings(self) -> List[Holding]:
        """Get all holdings"""
        with self._lock:
            return list(self._holdings.values())

    def has_holding(self, symbol: str) -> bool:
        """Check if symbol is in portfolio"""
        with self._lock:
            return symbol in self._holdings

    def get_holding_quantity(self, symbol: str) -> int:
        """Get quantity held for a symbol"""
        with self._lock:
            if symbol in self._holdings:
                return self._holdings[symbol].quantity
            return 0

    # ===== PRICE UPDATES =====

    def update_prices(self, prices: Dict[str, float]) -> None:
        """
        Update current prices for holdings

        Args:
            prices: Dictionary of {symbol: price}
        """
        with self._lock:
            for symbol, price in prices.items():
                if symbol in self._holdings:
                    self._holdings[symbol].update_price(Money(price))

    def update_price(self, symbol: str, price: Money) -> None:
        """Update current price for a single symbol"""
        with self._lock:
            if symbol in self._holdings:
                self._holdings[symbol].update_price(price)

    # ===== P&L CALCULATIONS =====

    def calculate_unrealized_pnl(self) -> Money:
        """Calculate total unrealized P&L across all holdings"""
        with self._lock:
            total_pnl = Money.zero()
            for holding in self._holdings.values():
                total_pnl += holding.calculate_pnl()
            return total_pnl

    def get_realized_pnl(self) -> Money:
        """Get total realized P&L"""
        with self._lock:
            return self._realized_pnl

    def get_total_pnl(self) -> Money:
        """Get total P&L (realized + unrealized)"""
        return self.get_realized_pnl() + self.calculate_unrealized_pnl()

    def calculate_portfolio_value(self) -> Money:
        """Calculate total portfolio market value"""
        with self._lock:
            total_value = Money.zero()
            for holding in self._holdings.values():
                total_value += holding.calculate_market_value()
            return total_value

    def calculate_cost_basis(self) -> Money:
        """Calculate total cost basis (what was paid)"""
        with self._lock:
            total_cost = Money.zero()
            for holding in self._holdings.values():
                total_cost += holding.calculate_cost_basis()
            return total_cost

    # ===== VALIDATION =====

    def can_sell(self, symbol: str, quantity: int) -> tuple[bool, str]:
        """
        Check if a sell order is valid

        Args:
            symbol: Stock symbol
            quantity: Quantity to sell

        Returns:
            Tuple of (is_valid, error_message)
        """
        with self._lock:
            if symbol not in self._holdings:
                return False, f"No holding found for {symbol}"

            holding = self._holdings[symbol]

            if holding.quantity < quantity:
                return False, (
                    f"Insufficient quantity: " f"Have {holding.quantity}, trying to sell {quantity}"
                )

            return True, ""

    # ===== STATISTICS =====

    def get_summary(self) -> Dict:
        """Get portfolio summary"""
        with self._lock:
            holdings_list = []
            for holding in self._holdings.values():
                holdings_list.append(
                    {
                        "symbol": holding.symbol,
                        "quantity": holding.quantity,
                        "average_price": holding.average_price.amount,
                        "current_price": holding.current_price.amount,
                        "cost_basis": holding.calculate_cost_basis().amount,
                        "market_value": holding.calculate_market_value().amount,
                        "pnl": holding.calculate_pnl().amount,
                        "pnl_percentage": holding.calculate_pnl_percentage(),
                    }
                )

            return {
                "total_holdings": len(self._holdings),
                "portfolio_value": self.calculate_portfolio_value().amount,
                "cost_basis": self.calculate_cost_basis().amount,
                "unrealized_pnl": self.calculate_unrealized_pnl().amount,
                "realized_pnl": self.get_realized_pnl().amount,
                "total_pnl": self.get_total_pnl().amount,
                "holdings": holdings_list,
            }

    def to_dict_list(self) -> List[Dict]:
        """Convert holdings to list of dictionaries"""
        with self._lock:
            return [holding.to_dict() for holding in self._holdings.values()]

    def reset(self) -> None:
        """Reset portfolio (clear all holdings)"""
        with self._lock:
            self._holdings.clear()
            self._realized_pnl = Money.zero()
            logger.info("? Portfolio reset")
