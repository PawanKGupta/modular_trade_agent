"""
Backtest Configuration Module

This module contains all configuration settings for the backtesting system.
"""

from typing import Optional

class BacktestConfig:
    """Configuration class for backtesting parameters"""
    
    # Capital Settings
    INITIAL_CAPITAL = 100000  # Capital for each buy signal
    POSITION_SIZE = 100000    # Amount to invest per position
    
    # Technical Indicator Settings
    EMA_PERIOD = 200          # EMA period for uptrend confirmation
    RSI_PERIOD = 10           # RSI period for oversold detection
    
    # Entry Conditions
    RSI_OVERSOLD_LEVEL_1 = 30  # First RSI threshold for entry
    RSI_OVERSOLD_LEVEL_2 = 20  # Second RSI threshold for pyramiding
    RSI_OVERSOLD_LEVEL_3 = 10  # Third RSI threshold for pyramiding
    
    # Pyramiding Settings
    MAX_POSITIONS = 10        # Maximum number of positions in a single stock
    ENABLE_PYRAMIDING = True  # Enable/disable pyramiding
    
    # Risk Management (placeholders for future implementation)
    STOP_LOSS_PCT = None      # Stop loss percentage (to be implemented)
    TAKE_PROFIT_PCT = None    # Take profit percentage (to be implemented)
    
    # Data Settings
    MIN_DATA_POINTS = 70      # Minimum data points required for backtest
    
    # Reporting Settings
    DETAILED_LOGGING = True   # Enable detailed logging of trades
    EXPORT_TRADES = True      # Export individual trades to CSV
    
    @classmethod
    def from_strategy_config(cls, strategy_config) -> 'BacktestConfig':
        """
        Create BacktestConfig from StrategyConfig to sync RSI period
        
        Args:
            strategy_config: StrategyConfig instance
        
        Returns:
            BacktestConfig instance with synced RSI period
        """
        config = cls()
        # Sync RSI period from StrategyConfig
        config.RSI_PERIOD = strategy_config.rsi_period
        # Sync RSI thresholds if available
        if hasattr(strategy_config, 'rsi_oversold'):
            config.RSI_OVERSOLD_LEVEL_1 = int(strategy_config.rsi_oversold)
        if hasattr(strategy_config, 'rsi_extreme_oversold'):
            config.RSI_OVERSOLD_LEVEL_2 = int(strategy_config.rsi_extreme_oversold)
            # Level 3 can be half of extreme oversold
            config.RSI_OVERSOLD_LEVEL_3 = int(strategy_config.rsi_extreme_oversold / 2)
        return config
    
    @classmethod
    def default_synced(cls) -> 'BacktestConfig':
        """
        Create BacktestConfig synced with default StrategyConfig
        
        Returns:
            BacktestConfig instance synced with StrategyConfig.default()
        """
        from config.strategy_config import StrategyConfig
        return cls.from_strategy_config(StrategyConfig.default())
    
    @classmethod
    def get_config_dict(cls):
        """Return configuration as dictionary"""
        return {
            'initial_capital': cls.INITIAL_CAPITAL,
            'position_size': cls.POSITION_SIZE,
            'ema_period': cls.EMA_PERIOD,
            'rsi_period': cls.RSI_PERIOD,
            'rsi_levels': [cls.RSI_OVERSOLD_LEVEL_1, cls.RSI_OVERSOLD_LEVEL_2, cls.RSI_OVERSOLD_LEVEL_3],
            'max_positions': cls.MAX_POSITIONS,
            'enable_pyramiding': cls.ENABLE_PYRAMIDING,
            'min_data_points': cls.MIN_DATA_POINTS
        }
