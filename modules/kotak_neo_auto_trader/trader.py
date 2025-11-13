#!/usr/bin/env python3
"""
Main Trader Coordinator for Kotak Neo API
Combines all modules into a unified interface
"""

from typing import Optional, Dict, Any
# Use existing project logger
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from utils.logger import logger

try:
    # Try relative imports first (when used as module)
    from .auth import KotakNeoAuth
    from .portfolio import KotakNeoPortfolio
    from .orders import KotakNeoOrders
except ImportError:
    # Fall back to absolute imports (when run directly)
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
    from modules.kotak_neo_auto_trader.portfolio import KotakNeoPortfolio
    from modules.kotak_neo_auto_trader.orders import KotakNeoOrders


class KotakNeoTrader:
    """
    Main coordinator class that combines all trading modules
    """
    
    def __init__(self, config_file: str = "modules/kotak_neo_auto_trader/kotak_neo.env"):
        """
        Initialize the complete trader system
        
        Args:
            config_file (str): Path to environment configuration file
        """
        self.config_file = config_file
        
        # Initialize authentication
        self.auth = KotakNeoAuth(config_file)
        
        # Initialize other modules (will be available after login)
        self.portfolio = None
        self.orders = None
        
        logger.info("KotakNeoTrader initialized - ready for login")
    
    def login(self) -> bool:
        """
        Perform login and initialize all modules
        
        Returns:
            bool: True if login successful, False otherwise
        """
        success = self.auth.login()
        
        if success:
            # Initialize modules after successful login
            self.portfolio = KotakNeoPortfolio(self.auth)
            self.orders = KotakNeoOrders(self.auth)
            logger.info(" All trading modules initialized successfully!")
        
        return success
    
    def logout(self) -> bool:
        """
        Logout and cleanup
        
        Returns:
            bool: True if logout successful, False otherwise
        """
        success = self.auth.logout()
        
        if success:
            # Reset modules
            self.portfolio = None
            self.orders = None
            logger.info(" All modules logged out and cleaned up")
        
        return success
    
    def is_logged_in(self) -> bool:
        """
        Check if currently logged in
        
        Returns:
            bool: True if logged in, False otherwise
        """
        return self.auth.is_authenticated()
    
    # Portfolio Methods (delegation)
    def get_portfolio_stocks(self) -> Optional[Dict]:
        """Get portfolio holdings"""
        if not self.portfolio:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.portfolio.get_holdings()
    
    def get_positions(self) -> Optional[Dict]:
        """Get current positions"""
        if not self.portfolio:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.portfolio.get_positions()
    
    def get_limits(self) -> Optional[Dict]:
        """Get account limits"""
        if not self.portfolio:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.portfolio.get_limits()
    
    def get_portfolio_summary(self) -> Optional[Dict]:
        """Get complete portfolio summary"""
        if not self.portfolio:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.portfolio.get_portfolio_summary()
    
    def calculate_portfolio_value(self) -> Optional[float]:
        """Calculate total portfolio value"""
        if not self.portfolio:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.portfolio.calculate_portfolio_value()
    
    def get_stock_details(self, symbol: str) -> Optional[Dict]:
        """Get details for specific stock"""
        if not self.portfolio:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.portfolio.get_stock_details(symbol)
    
    # Orders Methods (delegation)
    def get_existing_orders(self) -> Optional[Dict]:
        """Get all existing orders"""
        if not self.orders:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.orders.get_orders()
    
    def get_gtt_orders(self) -> Optional[Dict]:
        """Get GTT orders"""
        if not self.orders:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.orders.get_gtt_orders()
    
    def get_pending_orders(self) -> Optional[Dict]:
        """Get pending orders"""
        if not self.orders:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.orders.get_pending_orders()
    
    def get_executed_orders(self) -> Optional[Dict]:
        """Get executed orders"""
        if not self.orders:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.orders.get_executed_orders()
    
    def get_order_history(self, order_id: str = None) -> Optional[Dict]:
        """Get order history"""
        if not self.orders:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.orders.get_order_history(order_id)
    
    def get_orders_summary(self) -> Optional[Dict]:
        """Get complete orders summary"""
        if not self.orders:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.orders.get_orders_summary()
    
    def search_orders_by_symbol(self, symbol: str) -> Optional[Dict]:
        """Search orders by symbol"""
        if not self.orders:
            logger.error(" Not logged in. Please login first.")
            return None
        return self.orders.search_orders_by_symbol(symbol)
    
    # Combined Methods
    def get_complete_summary(self) -> Dict[str, Any]:
        """
        Get complete trading summary including portfolio and orders
        
        Returns:
            Dict: Complete trading data
        """
        if not self.is_logged_in():
            logger.error(" Not logged in. Please login first.")
            return {}
        
        print("\n" + "="*60)
        logger.info("COMPLETE TRADING SUMMARY")
        print("="*60)
        
        summary = {}
        
        # Get portfolio data
        if self.portfolio:
            logger.info("\nPortfolio Data:")
            summary['portfolio'] = {
                'holdings': self.portfolio.get_holdings(),
                'positions': self.portfolio.get_positions(),
                'limits': self.portfolio.get_limits()
            }
        
        # Get orders data
        if self.orders:
            logger.info("\nOrders Data:")
            summary['orders'] = {
                'all_orders': self.orders.get_orders(),
                'pending_orders': self.orders.get_pending_orders(),
                'executed_orders': self.orders.get_executed_orders(),
                'gtt_orders': self.orders.get_gtt_orders()
            }
        
        print("\n" + "="*60)
        logger.info(" Complete summary generated successfully!")
        print("="*60)
        
        return summary
    
    def quick_status(self) -> Dict[str, Any]:
        """
        Get quick status overview
        
        Returns:
            Dict: Quick status summary
        """
        if not self.is_logged_in():
            return {"status": "Not logged in"}
        
        logger.info("Quick Status Check...")
        
        # Quick checks without detailed output
        portfolio_value = self.calculate_portfolio_value()
        
        # Count orders
        all_orders = self.get_existing_orders()
        order_count = len(all_orders.get('data', [])) if all_orders else 0
        
        # Count holdings
        holdings = self.get_portfolio_stocks()
        holdings_count = len(holdings.get('data', [])) if holdings else 0
        
        # Count positions
        positions = self.get_positions()
        positions_count = 0
        if positions and positions.get('data'):
            positions_count = sum(1 for pos in positions['data'] if pos.get('netQuantity', 0) != 0)
        
        status = {
            "status": "Logged in",
            "portfolio_value": portfolio_value,
            "holdings_count": holdings_count,
            "positions_count": positions_count,
            "orders_count": order_count
        }
        
        logger.info(" Portfolio Value: ₹{portfolio_value or 'N/A'}")
        logger.info(f"Holdings: {holdings_count}")
        logger.info(" Active Positions: {positions_count}")
        logger.info(" Total Orders: {order_count}")
        
        return status
    
    def __enter__(self):
        """Context manager entry"""
        if self.login():
            return self
        else:
            raise Exception("Login failed")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.logout()


def main():
    """
    Demo function showing the modular trader usage
    """
    logger.info("Modular Kotak Neo Trader Demo")
    print("=" * 50)
    
    # Method 1: Manual login/logout
    trader = KotakNeoTrader()
    
    if trader.login():
        # Test individual functions
        logger.info("\n1. Portfolio stocks:")
        trader.get_portfolio_stocks()
        
        logger.info("\n2. Existing orders:")
        trader.get_existing_orders()
        
        logger.info("\n3. GTT orders:")
        trader.get_gtt_orders()
        
        logger.info("\nQuick status:")
        trader.quick_status()
        
        trader.logout()
    
    print("\n" + "=" * 50)
    logger.info("Demo completed!")
    
    # Method 2: Context manager (automatic login/logout)
    logger.info("\nTesting context manager...")
    try:
        with KotakNeoTrader() as trader:
            trader.quick_status()
    except Exception as e:
        logger.info(f"Context manager failed: {e}")


if __name__ == "__main__":
    main()