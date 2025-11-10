"""
Liquidity Capital Service

Calculates maximum capital that can be safely allocated to a stock based on liquidity.
Automatically adjusts capital to ensure safe position sizing.
"""

import os
import math
from typing import Dict, Optional
from utils.logger import logger
from config.strategy_config import StrategyConfig
from config.settings import MIN_ABSOLUTE_AVG_VOLUME


class LiquidityCapitalService:
    """
    Service for calculating execution capital based on liquidity
    
    Provides methods to:
    - Calculate maximum capital allowed by liquidity
    - Calculate execution capital (min of user capital and max capital)
    - Check if capital is safe for a stock
    """
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        Initialize liquidity capital service
        
        Args:
            config: Strategy configuration (uses default if None)
        """
        self.config = config or StrategyConfig.default()
        
        # Capital configuration (from config or env)
        self.user_capital = getattr(self.config, 'user_capital',
                                   float(os.getenv('USER_CAPITAL', '200000.0')))
        self.max_position_volume_ratio = getattr(self.config, 'max_position_volume_ratio',
                                                float(os.getenv('MAX_POSITION_VOLUME_RATIO', '0.10')))
        self.min_absolute_avg_volume = getattr(self.config, 'min_absolute_avg_volume',
                                              int(os.getenv('MIN_ABSOLUTE_AVG_VOLUME', '20000')))
        
        # Fallback to MIN_ABSOLUTE_AVG_VOLUME if not in config
        if not hasattr(self.config, 'min_absolute_avg_volume'):
            self.min_absolute_avg_volume = MIN_ABSOLUTE_AVG_VOLUME
    
    def calculate_max_capital(
        self, 
        avg_volume: float, 
        stock_price: float, 
        max_position_volume_ratio: Optional[float] = None
    ) -> float:
        """
        Calculate maximum capital allowed by liquidity
        
        Args:
            avg_volume: Average daily volume (20-day or 50-day)
            stock_price: Current stock price
            max_position_volume_ratio: Maximum position size as % of daily volume (default: 0.10 = 10%)
            
        Returns:
            Maximum capital in rupees that can be safely allocated
        """
        try:
            if avg_volume <= 0 or stock_price <= 0:
                return 0.0
            
            ratio = max_position_volume_ratio or self.max_position_volume_ratio
            
            # Calculate max shares that can be safely traded
            max_shares = avg_volume * ratio
            
            # Calculate max capital
            max_capital = max_shares * stock_price
            
            return max_capital
        except Exception as e:
            logger.warning(f"Error calculating max capital: {e}")
            return 0.0
    
    def calculate_execution_capital(
        self,
        user_capital: Optional[float] = None,
        avg_volume: float = 0.0,
        stock_price: float = 0.0,
        max_position_volume_ratio: Optional[float] = None
    ) -> Dict:
        """
        Calculate execution capital (actual capital to use for trade)
        
        Logic: execution_capital = min(user_capital, max_capital_from_liquidity)
        
        Args:
            user_capital: User's configured capital (default: from config)
            avg_volume: Average daily volume
            stock_price: Current stock price
            max_position_volume_ratio: Maximum position size ratio (default: from config)
            
        Returns:
            Dict with execution capital details:
            {
                'execution_capital': float,
                'max_capital': float,
                'user_capital': float,
                'capital_adjusted': bool,
                'is_safe': bool,
                'reason': str
            }
        """
        try:
            user_cap = user_capital or self.user_capital
            
            # Check absolute minimum volume (safety net)
            if avg_volume < self.min_absolute_avg_volume:
                return {
                    'execution_capital': 0.0,
                    'max_capital': 0.0,
                    'user_capital': user_cap,
                    'capital_adjusted': False,
                    'is_safe': False,
                    'reason': f'Volume too low: {avg_volume:.0f} < {self.min_absolute_avg_volume}'
                }
            
            # Calculate max capital from liquidity
            max_cap = self.calculate_max_capital(
                avg_volume, 
                stock_price, 
                max_position_volume_ratio
            )
            
            if max_cap <= 0:
                return {
                    'execution_capital': 0.0,
                    'max_capital': 0.0,
                    'user_capital': user_cap,
                    'capital_adjusted': False,
                    'is_safe': False,
                    'reason': 'Cannot calculate max capital'
                }
            
            # Execution capital is minimum of user capital and max capital
            execution_capital = min(user_cap, max_cap)
            capital_adjusted = execution_capital < user_cap
            is_safe = execution_capital > 0
            
            # Build reason
            if capital_adjusted:
                reason = f'Capital adjusted: ₹{user_cap/1000:.0f}K → ₹{execution_capital/1000:.0f}K due to liquidity'
            else:
                reason = f'Full capital used: ₹{execution_capital/1000:.0f}K'
            
            return {
                'execution_capital': execution_capital,
                'max_capital': max_cap,
                'user_capital': user_cap,
                'capital_adjusted': capital_adjusted,
                'is_safe': is_safe,
                'reason': reason
            }
        except Exception as e:
            logger.error(f"Error calculating execution capital: {e}")
            return {
                'execution_capital': 0.0,
                'max_capital': 0.0,
                'user_capital': user_capital or self.user_capital,
                'capital_adjusted': False,
                'is_safe': False,
                'reason': f'Error: {str(e)}'
            }
    
    def is_capital_safe(
        self,
        user_capital: Optional[float] = None,
        avg_volume: float = 0.0,
        stock_price: float = 0.0,
        max_position_volume_ratio: Optional[float] = None
    ) -> bool:
        """
        Check if user capital is safe for a stock
        
        Args:
            user_capital: User's configured capital
            avg_volume: Average daily volume
            stock_price: Current stock price
            max_position_volume_ratio: Maximum position size ratio
            
        Returns:
            True if capital is safe, False otherwise
        """
        result = self.calculate_execution_capital(
            user_capital, 
            avg_volume, 
            stock_price, 
            max_position_volume_ratio
        )
        return result.get('is_safe', False)
    
    def calculate_position_size(
        self,
        execution_capital: float,
        stock_price: float
    ) -> Dict:
        """
        Calculate position size (quantity) from execution capital
        
        Args:
            execution_capital: Capital to use for trade
            stock_price: Current stock price
            
        Returns:
            Dict with position size details:
            {
                'quantity': int,
                'actual_capital': float,
                'execution_capital': float
            }
        """
        try:
            if execution_capital <= 0 or stock_price <= 0:
                return {
                    'quantity': 0,
                    'actual_capital': 0.0,
                    'execution_capital': execution_capital
                }
            
            # Calculate quantity (floor to ensure we don't exceed capital)
            quantity = math.floor(execution_capital / stock_price)
            
            # Actual capital used
            actual_capital = quantity * stock_price
            
            return {
                'quantity': quantity,
                'actual_capital': actual_capital,
                'execution_capital': execution_capital
            }
        except Exception as e:
            logger.warning(f"Error calculating position size: {e}")
            return {
                'quantity': 0,
                'actual_capital': 0.0,
                'execution_capital': execution_capital
            }

