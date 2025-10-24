#!/usr/bin/env python3
"""
Portfolio Management Module for Kotak Neo API
Handles portfolio holdings, positions, and account information
"""

from typing import Optional, Dict, List
# Import existing project logger
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

try:
    from .auth import KotakNeoAuth
except ImportError:
    from auth import KotakNeoAuth


class KotakNeoPortfolio:
    """
    Portfolio management for Kotak Neo API
    """
    
    def __init__(self, auth: KotakNeoAuth):
        """
        Initialize portfolio manager
        
        Args:
            auth (KotakNeoAuth): Authenticated session instance
        """
        self.auth = auth
        logger.info("KotakNeoPortfolio initialized")
    
    def get_holdings(self) -> Optional[Dict]:
        """
        Get portfolio holdings (stocks owned)
        
        Returns:
            Dict: Holdings data or None if failed
        """
        client = self.auth.get_client()
        if not client:
            return None
        
        try:
            logger.info(" Retrieving portfolio holdings...")
            holdings = client.holdings()
            
            if "error" in holdings:
                logger.error(" Failed to get holdings: {holdings['error'][0]['message']}")
                return None
            
            # Process and display holdings
            if 'data' in holdings and holdings['data']:
                holdings_data = holdings['data']
                logger.info(" Found {len(holdings_data)} holdings in portfolio")
                
                # Display summary
                total_value = 0
                for holding in holdings_data:
                    stock_name = holding.get('tradingSymbol', 'N/A')
                    quantity = holding.get('quantity', 0)
                    ltp = holding.get('ltp', 0)
                    market_value = holding.get('marketValue', 0)
                    pnl = holding.get('pnl', 0)
                    
                    logger.info(f"📈 {stock_name}: Qty={quantity}, LTP=₹{ltp}, Value=₹{market_value}, P&L=₹{pnl}")
                    total_value += market_value
                
                logger.info(f"💰 Total Portfolio Value: ₹{total_value}")
            else:
                logger.info(" No holdings found in portfolio")
            
            return holdings
            
        except Exception as e:
            logger.error(" Error getting holdings: {e}")
            return None
    
    def get_positions(self) -> Optional[Dict]:
        """
        Get current positions (open trades for the day)
        
        Returns:
            Dict: Positions data or None if failed
        """
        client = self.auth.get_client()
        if not client:
            return None
        
        try:
            logger.info(" Retrieving current positions...")
            positions = client.positions()
            
            if "error" in positions:
                logger.error(" Failed to get positions: {positions['error'][0]['message']}")
                return None
            
            # Process and display positions
            if 'data' in positions and positions['data']:
                positions_data = positions['data']
                logger.info(" Found {len(positions_data)} positions")
                
                active_positions = 0
                for position in positions_data:
                    symbol = position.get('tradingSymbol', 'N/A')
                    net_quantity = position.get('netQuantity', 0)
                    buy_quantity = position.get('buyQuantity', 0)
                    sell_quantity = position.get('sellQuantity', 0)
                    pnl = position.get('pnl', 0)
                    ltp = position.get('ltp', 0)
                    
                    if net_quantity != 0:  # Only show positions with non-zero quantity
                        logger.info(" {symbol}: Net={net_quantity} (Buy={buy_quantity}, Sell={sell_quantity}), P&L=₹{pnl}, LTP=₹{ltp}")
                        active_positions += 1
                
                if active_positions == 0:
                    logger.info(" No active positions found")
            else:
                logger.info(" No positions found")
            
            return positions
            
        except Exception as e:
            logger.error(" Error getting positions: {e}")
            return None
    
    def get_limits(self) -> Optional[Dict]:
        """
        Get account limits and margins
        
        Returns:
            Dict: Limits data or None if failed
        """
        client = self.auth.get_client()
        if not client:
            return None
        
        try:
            logger.info(" Retrieving account limits...")
            limits = client.limits(segment="ALL", exchange="ALL")
            
            if "error" in limits:
                logger.error(" Failed to get limits: {limits['error'][0]['message']}")
                return None
            
            # Display limits summary
            if 'data' in limits:
                data = limits['data']
                cash = data.get('cash', 0)
                margin_used = data.get('marginUsed', 0)
                margin_available = data.get('marginAvailable', 0)
                
                logger.info(f"💰 Cash: ₹{cash}")
                logger.info(" Margin Used: ₹{margin_used}")
                logger.info(" Margin Available: ₹{margin_available}")
            
            return limits
            
        except Exception as e:
            logger.error(" Error getting limits: {e}")
            return None
    
    def get_portfolio_summary(self) -> Dict:
        """
        Get complete portfolio summary
        
        Returns:
            Dict: Complete portfolio data
        """
        print("\n" + "="*50)
        logger.info(" PORTFOLIO SUMMARY")
        print("="*50)
        
        summary = {
            "holdings": self.get_holdings(),
            "positions": self.get_positions(),
            "limits": self.get_limits()
        }
        
        print("="*50)
        logger.info(" Portfolio summary completed")
        
        return summary
    
    def calculate_portfolio_value(self) -> Optional[float]:
        """
        Calculate total portfolio value
        
        Returns:
            float: Total portfolio value or None if failed
        """
        holdings = self.get_holdings()
        if not holdings or 'data' not in holdings:
            return None
        
        total_value = 0
        for holding in holdings['data']:
            market_value = holding.get('marketValue', 0)
            total_value += market_value
        
        return total_value
    
    def get_stock_details(self, symbol: str) -> Optional[Dict]:
        """
        Get details for a specific stock in portfolio
        
        Args:
            symbol (str): Stock symbol to search for
            
        Returns:
            Dict: Stock details or None if not found
        """
        holdings = self.get_holdings()
        if not holdings or 'data' not in holdings:
            return None
        
        for holding in holdings['data']:
            if holding.get('tradingSymbol', '').upper() == symbol.upper():
                return holding
        
        logger.error(" Stock {symbol} not found in portfolio")
        return None