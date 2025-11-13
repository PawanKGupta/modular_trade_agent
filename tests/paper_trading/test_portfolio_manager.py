"""
Test Portfolio Manager
"""

import pytest
from modules.kotak_neo_auto_trader.infrastructure.simulation import PortfolioManager
from modules.kotak_neo_auto_trader.domain import Money, Exchange


class TestPortfolioManager:
    """Test portfolio management"""

    @pytest.fixture
    def portfolio(self):
        """Create portfolio manager"""
        return PortfolioManager()

    def test_empty_portfolio(self, portfolio):
        """Test empty portfolio initialization"""
        holdings = portfolio.get_all_holdings()
        assert len(holdings) == 0
        assert portfolio.calculate_portfolio_value() == Money.zero()

    def test_add_holding(self, portfolio):
        """Test adding a holding"""
        portfolio.add_holding("INFY", 10, Money(1450.00))

        holdings = portfolio.get_all_holdings()
        assert len(holdings) == 1

        holding = portfolio.get_holding("INFY")
        assert holding.symbol == "INFY"
        assert holding.quantity == 10
        assert holding.average_price.amount == 1450.00

    def test_add_holding_averaging(self, portfolio):
        """Test adding to existing holding (averaging)"""
        portfolio.add_holding("INFY", 10, Money(1450.00))
        portfolio.add_holding("INFY", 10, Money(1350.00))

        holding = portfolio.get_holding("INFY")
        assert holding.quantity == 20
        assert holding.average_price.amount == 1400.00  # Average

    def test_reduce_holding(self, portfolio):
        """Test reducing holding quantity"""
        portfolio.add_holding("TCS", 10, Money(3500.00))

        remaining, realized_pnl = portfolio.reduce_holding("TCS", 5, Money(3600.00))

        assert remaining.quantity == 5
        assert realized_pnl.amount == 500.00  # (3600 - 3500) * 5

    def test_reduce_holding_complete(self, portfolio):
        """Test reducing holding to zero"""
        portfolio.add_holding("RELIANCE", 10, Money(2500.00))

        remaining, realized_pnl = portfolio.reduce_holding("RELIANCE", 10, Money(2600.00))

        assert remaining is None
        assert not portfolio.has_holding("RELIANCE")
        assert realized_pnl.amount == 1000.00

    def test_reduce_holding_insufficient_quantity(self, portfolio):
        """Test reducing more than held"""
        portfolio.add_holding("INFY", 5, Money(1450.00))

        with pytest.raises(ValueError, match="Insufficient quantity"):
            portfolio.reduce_holding("INFY", 10, Money(1500.00))

    def test_reduce_holding_not_found(self, portfolio):
        """Test reducing non-existent holding"""
        with pytest.raises(ValueError, match="No holding found"):
            portfolio.reduce_holding("INVALID", 5, Money(1000.00))

    def test_update_prices(self, portfolio):
        """Test updating prices for holdings"""
        portfolio.add_holding("INFY", 10, Money(1450.00))
        portfolio.add_holding("TCS", 5, Money(3500.00))

        portfolio.update_prices({
            "INFY": 1500.00,
            "TCS": 3600.00
        })

        infy = portfolio.get_holding("INFY")
        assert infy.current_price.amount == 1500.00

    def test_calculate_unrealized_pnl(self, portfolio):
        """Test unrealized P&L calculation"""
        portfolio.add_holding("INFY", 10, Money(1450.00))
        portfolio.update_price("INFY", Money(1500.00))

        unrealized_pnl = portfolio.calculate_unrealized_pnl()
        assert unrealized_pnl.amount == 500.00  # (1500 - 1450) * 10

    def test_calculate_realized_pnl(self, portfolio):
        """Test realized P&L tracking"""
        portfolio.add_holding("TCS", 10, Money(3500.00))
        portfolio.reduce_holding("TCS", 5, Money(3600.00))

        realized_pnl = portfolio.get_realized_pnl()
        assert realized_pnl.amount == 500.00

    def test_calculate_total_pnl(self, portfolio):
        """Test total P&L calculation"""
        # Add holding
        portfolio.add_holding("INFY", 10, Money(1450.00))

        # Sell some (realized)
        portfolio.reduce_holding("INFY", 5, Money(1500.00))

        # Update price (unrealized)
        portfolio.update_price("INFY", Money(1550.00))

        total_pnl = portfolio.get_total_pnl()
        # Realized: (1500-1450)*5 = 250
        # Unrealized: (1550-1450)*5 = 500
        # Total: 750
        assert total_pnl.amount == 750.00

    def test_calculate_portfolio_value(self, portfolio):
        """Test portfolio value calculation"""
        portfolio.add_holding("INFY", 10, Money(1450.00))
        portfolio.add_holding("TCS", 5, Money(3500.00))

        portfolio.update_prices({
            "INFY": 1500.00,
            "TCS": 3600.00
        })

        value = portfolio.calculate_portfolio_value()
        # (1500 * 10) + (3600 * 5) = 33000
        assert value.amount == 33000.00

    def test_calculate_cost_basis(self, portfolio):
        """Test cost basis calculation"""
        portfolio.add_holding("INFY", 10, Money(1450.00))
        portfolio.add_holding("TCS", 5, Money(3500.00))

        cost_basis = portfolio.calculate_cost_basis()
        # (1450 * 10) + (3500 * 5) = 32000
        assert cost_basis.amount == 32000.00

    def test_can_sell_valid(self, portfolio):
        """Test can_sell validation for valid case"""
        portfolio.add_holding("INFY", 10, Money(1450.00))

        can_sell, error = portfolio.can_sell("INFY", 5)
        assert can_sell is True
        assert error == ""

    def test_can_sell_insufficient(self, portfolio):
        """Test can_sell validation for insufficient quantity"""
        portfolio.add_holding("INFY", 5, Money(1450.00))

        can_sell, error = portfolio.can_sell("INFY", 10)
        assert can_sell is False
        assert "Insufficient quantity" in error

    def test_can_sell_not_found(self, portfolio):
        """Test can_sell validation for non-existent holding"""
        can_sell, error = portfolio.can_sell("INVALID", 5)
        assert can_sell is False
        assert "No holding found" in error

    def test_get_summary(self, portfolio):
        """Test portfolio summary"""
        portfolio.add_holding("INFY", 10, Money(1450.00))
        portfolio.update_price("INFY", Money(1500.00))

        summary = portfolio.get_summary()

        assert summary["total_holdings"] == 1
        assert summary["portfolio_value"] == 15000.00
        assert summary["cost_basis"] == 14500.00
        assert summary["unrealized_pnl"] == 500.00
        assert len(summary["holdings"]) == 1

    def test_reset(self, portfolio):
        """Test portfolio reset"""
        portfolio.add_holding("INFY", 10, Money(1450.00))
        portfolio.reset()

        holdings = portfolio.get_all_holdings()
        assert len(holdings) == 0
        assert portfolio.get_realized_pnl() == Money.zero()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

