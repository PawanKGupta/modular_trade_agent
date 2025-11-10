"""
Get Holdings Use Case
Business logic for retrieving portfolio holdings
"""

from dataclasses import dataclass
from ...domain import IBrokerGateway, Money
from ..dto import HoldingsResponse


@dataclass
class GetHoldingsUseCase:
    """
    Use case for retrieving portfolio holdings
    
    Handles broker interaction and portfolio calculations
    """
    
    broker_gateway: IBrokerGateway
    
    def execute(self) -> HoldingsResponse:
        """
        Execute the get holdings use case
        
        Returns:
            HoldingsResponse with holdings and portfolio totals
        """
        # 1. Check broker connection
        if not self.broker_gateway.is_connected():
            if not self.broker_gateway.connect():
                return HoldingsResponse.failure_response(
                    errors=["Failed to connect to broker"]
                )
        
        # 2. Get holdings from broker
        try:
            holdings = self.broker_gateway.get_holdings()
            
            # 3. Calculate portfolio totals
            if not holdings:
                return HoldingsResponse.success_response(
                    holdings=[],
                    total_value=Money.zero(),
                    total_pnl=Money.zero()
                )
            
            total_value = Money.zero()
            total_pnl = Money.zero()
            
            for holding in holdings:
                total_value = total_value + holding.calculate_market_value()
                total_pnl = total_pnl + holding.calculate_pnl()
            
            return HoldingsResponse.success_response(
                holdings=holdings,
                total_value=total_value,
                total_pnl=total_pnl
            )
            
        except ConnectionError as e:
            return HoldingsResponse.failure_response(
                errors=[f"Connection error: {str(e)}"]
            )
        except Exception as e:
            return HoldingsResponse.failure_response(
                errors=[f"Unexpected error: {str(e)}"]
            )
