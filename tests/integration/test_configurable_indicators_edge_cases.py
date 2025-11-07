"""
Edge Case Tests for Configurable Indicators

Tests for:
1. Empty data handling
2. Missing columns handling
3. Invalid configuration values
4. Boundary conditions
5. Error handling
"""

import sys
import os
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig
from backtest.backtest_config import BacktestConfig
from core.indicators import compute_indicators
from core.timeframe_analysis import TimeframeAnalysis
from core.data_fetcher import fetch_multi_timeframe_data, yfinance_circuit_breaker


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset circuit breaker before each test"""
    yfinance_circuit_breaker.reset()
    yield


# ============================================================================
# 1. Empty Data Handling Tests
# ============================================================================

class TestEmptyDataHandling:
    """Test handling of empty data"""
    
    def test_compute_indicators_empty_dataframe(self):
        """Test compute_indicators handles empty DataFrame"""
        empty_df = pd.DataFrame()
        result = compute_indicators(empty_df)
        assert result is None
    
    def test_compute_indicators_none_input(self):
        """Test compute_indicators handles None input"""
        result = compute_indicators(None)
        assert result is None
    
    def test_timeframe_analysis_empty_data(self):
        """Test TimeframeAnalysis handles empty data"""
        config = StrategyConfig.default()
        tf_analyzer = TimeframeAnalysis(config=config)
        
        empty_daily = pd.DataFrame()
        empty_weekly = pd.DataFrame()
        
        # analyze_dip_conditions only takes one DataFrame, not two
        # Use get_dip_buying_confirmation for multi-timeframe analysis
        result = tf_analyzer.get_dip_buying_confirmation(empty_daily, empty_weekly)
        assert result is not None
        assert 'daily_analysis' in result
        assert 'weekly_analysis' in result


# ============================================================================
# 2. Missing Columns Handling Tests
# ============================================================================

class TestMissingColumnsHandling:
    """Test handling of missing columns"""
    
    def test_compute_indicators_missing_close_column(self):
        """Test compute_indicators handles missing Close column"""
        df = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [95, 96, 97],
            'volume': [1000000, 1100000, 1200000]
        })
        result = compute_indicators(df)
        assert result is None
    
    def test_compute_indicators_missing_volume_column(self):
        """Test compute_indicators handles missing Volume column"""
        df = pd.DataFrame({
            'close': [100, 101, 102],
            'open': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [95, 96, 97]
        })
        # Should still work (volume not required for RSI/EMA)
        result = compute_indicators(df)
        assert result is not None
        assert 'rsi10' in result.columns or 'rsi10' in [c.lower() for c in result.columns]
    
    def test_timeframe_analysis_missing_columns(self):
        """Test TimeframeAnalysis handles missing columns"""
        config = StrategyConfig.default()
        tf_analyzer = TimeframeAnalysis(config=config)
        
        incomplete_df = pd.DataFrame({
            'close': [100, 101, 102]
        })
        
        # analyze_dip_conditions only takes one DataFrame
        result = tf_analyzer.analyze_dip_conditions(incomplete_df, 'daily')
        # Should return None or handle gracefully due to missing columns
        # The method will try to compute indicators which may fail
        assert result is None or isinstance(result, dict)


# ============================================================================
# 3. Invalid Configuration Values Tests
# ============================================================================

class TestInvalidConfigurationValues:
    """Test handling of invalid configuration values"""
    
    def test_strategy_config_invalid_rsi_period(self):
        """Test StrategyConfig handles invalid RSI period"""
        # Very low RSI period
        config = StrategyConfig(rsi_period=3)
        assert config.rsi_period == 3  # Should accept but may cause issues
        
        # Very high RSI period
        config = StrategyConfig(rsi_period=50)
        assert config.rsi_period == 50  # Should accept but may cause issues
    
    def test_strategy_config_invalid_lookback(self):
        """Test StrategyConfig handles invalid lookback values"""
        # Zero lookback
        config = StrategyConfig(support_resistance_lookback_daily=0)
        assert config.support_resistance_lookback_daily == 0  # Should accept but may cause issues
        
        # Negative lookback
        config = StrategyConfig(support_resistance_lookback_daily=-10)
        assert config.support_resistance_lookback_daily == -10  # Should accept but may cause issues
    
    def test_strategy_config_invalid_data_fetch_years(self):
        """Test StrategyConfig handles invalid data fetch years"""
        # Zero years
        config = StrategyConfig(data_fetch_daily_max_years=0)
        assert config.data_fetch_daily_max_years == 0  # Should accept but may cause issues
        
        # Very high years
        config = StrategyConfig(data_fetch_daily_max_years=20)
        assert config.data_fetch_daily_max_years == 20  # Should accept but may cause issues


# ============================================================================
# 4. Boundary Conditions Tests
# ============================================================================

class TestBoundaryConditions:
    """Test boundary conditions"""
    
    def test_compute_indicators_minimum_data(self):
        """Test compute_indicators with minimum required data"""
        # Minimum data for RSI (need at least period+1 rows)
        dates = pd.date_range('2023-01-01', periods=11, freq='D')
        df = pd.DataFrame({
            'close': np.linspace(100, 110, 11),
            'open': np.linspace(99, 109, 11),
            'high': np.linspace(105, 115, 11),
            'low': np.linspace(95, 105, 11),
            'volume': [1000000] * 11
        }, index=dates)
        
        result = compute_indicators(df)
        assert result is not None
        assert len(result) == 11
    
    def test_compute_indicators_single_row(self):
        """Test compute_indicators with single row"""
        df = pd.DataFrame({
            'close': [100],
            'open': [99],
            'high': [105],
            'low': [95],
            'volume': [1000000]
        })
        
        result = compute_indicators(df)
        # Should handle gracefully (RSI needs more data)
        assert result is not None
    
    def test_timeframe_analysis_minimum_data(self):
        """Test TimeframeAnalysis with minimum data"""
        config = StrategyConfig.default()
        tf_analyzer = TimeframeAnalysis(config=config)
        
        # Minimum data for analysis
        dates = pd.date_range('2023-01-01', periods=20, freq='D')
        df = pd.DataFrame({
            'close': np.linspace(100, 120, 20),
            'open': np.linspace(99, 119, 20),
            'high': np.linspace(105, 125, 20),
            'low': np.linspace(95, 115, 20),
            'volume': [1000000] * 20
        }, index=dates)
        
        result = tf_analyzer.analyze_dip_conditions(df, 'daily')
        assert result is not None


# ============================================================================
# 5. Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling"""
    
    def test_compute_indicators_nan_values(self):
        """Test compute_indicators handles NaN values"""
        dates = pd.date_range('2023-01-01', periods=50, freq='D')
        df = pd.DataFrame({
            'close': np.linspace(100, 150, 50),
            'open': np.linspace(99, 149, 50),
            'high': np.linspace(105, 155, 50),
            'low': np.linspace(95, 145, 50),
            'volume': [1000000] * 50
        }, index=dates)
        
        # Add some NaN values
        df.loc[df.index[10], 'close'] = np.nan
        df.loc[df.index[20], 'volume'] = np.nan
        
        result = compute_indicators(df)
        assert result is not None
        # Should handle NaN gracefully
    
    def test_compute_indicators_inf_values(self):
        """Test compute_indicators handles Inf values"""
        dates = pd.date_range('2023-01-01', periods=50, freq='D')
        df = pd.DataFrame({
            'close': np.linspace(100, 150, 50),
            'open': np.linspace(99, 149, 50),
            'high': np.linspace(105, 155, 50),
            'low': np.linspace(95, 145, 50),
            'volume': [1000000] * 50
        }, index=dates)
        
        # Add some Inf values
        df.loc[df.index[10], 'close'] = np.inf
        df.loc[df.index[20], 'volume'] = np.inf
        
        result = compute_indicators(df)
        assert result is not None
        # Should handle Inf gracefully
    
    def test_timeframe_analysis_invalid_data_types(self):
        """Test TimeframeAnalysis handles invalid data types"""
        config = StrategyConfig.default()
        tf_analyzer = TimeframeAnalysis(config=config)
        
        # Invalid data types
        invalid_df = pd.DataFrame({
            'close': ['a', 'b', 'c'],  # String instead of numeric
            'open': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [95, 96, 97],
            'volume': [1000000, 1100000, 1200000]
        })
        
        result = tf_analyzer.analyze_dip_conditions(invalid_df, 'daily')
        # Should handle gracefully or return None/error due to invalid data types
        assert result is None or isinstance(result, dict)


# ============================================================================
# 6. Configuration Edge Cases Tests
# ============================================================================

class TestConfigurationEdgeCases:
    """Test configuration edge cases"""
    
    def test_strategy_config_extreme_values(self):
        """Test StrategyConfig with extreme values"""
        # All minimum values
        config = StrategyConfig(
            rsi_period=5,
            support_resistance_lookback_daily=10,
            support_resistance_lookback_weekly=20,
            volume_exhaustion_lookback_daily=5,
            volume_exhaustion_lookback_weekly=10,
            data_fetch_daily_max_years=1,
            data_fetch_weekly_max_years=1,
            enable_adaptive_lookback=False
        )
        assert config.rsi_period == 5
        assert config.support_resistance_lookback_daily == 10
        
        # All maximum values
        config = StrategyConfig(
            rsi_period=30,
            support_resistance_lookback_daily=100,
            support_resistance_lookback_weekly=200,
            volume_exhaustion_lookback_daily=30,
            volume_exhaustion_lookback_weekly=50,
            data_fetch_daily_max_years=10,
            data_fetch_weekly_max_years=5,
            enable_adaptive_lookback=True
        )
        assert config.rsi_period == 30
        assert config.support_resistance_lookback_daily == 100
    
    def test_backtest_config_syncing_edge_cases(self):
        """Test BacktestConfig syncing with edge case configs"""
        # Extreme RSI period
        config = StrategyConfig(rsi_period=50)
        backtest_config = BacktestConfig.from_strategy_config(config)
        assert backtest_config.RSI_PERIOD == 50
        
        # Very low RSI period
        config = StrategyConfig(rsi_period=3)
        backtest_config = BacktestConfig.from_strategy_config(config)
        assert backtest_config.RSI_PERIOD == 3


# ============================================================================
# 7. Data Fetching Edge Cases Tests
# ============================================================================

class TestDataFetchingEdgeCases:
    """Test data fetching edge cases"""
    
    @pytest.mark.integration
    def test_fetch_multi_timeframe_data_invalid_symbol(self):
        """Test fetch_multi_timeframe_data with invalid symbol"""
        result = fetch_multi_timeframe_data("INVALID.SYMBOL.123", days=100)
        assert result is None
    
    @pytest.mark.integration
    def test_fetch_multi_timeframe_data_zero_days(self):
        """Test fetch_multi_timeframe_data with zero days"""
        config = StrategyConfig.default()
        result = fetch_multi_timeframe_data("RELIANCE.NS", days=0, config=config)
        # Should use minimum required days from config
        if result is not None:
            assert 'daily' in result
            assert 'weekly' in result
    
    @pytest.mark.integration
    def test_fetch_multi_timeframe_data_very_large_days(self):
        """Test fetch_multi_timeframe_data with very large days"""
        config = StrategyConfig.default()
        result = fetch_multi_timeframe_data("RELIANCE.NS", days=10000, config=config)
        # Should respect max_years from config
        if result is not None:
            assert 'daily' in result
            daily_data = result['daily']
            if daily_data is not None and not daily_data.empty:
                max_days = config.data_fetch_daily_max_years * 365
                assert len(daily_data) <= max_days * 1.1  # 10% tolerance


# ============================================================================
# 8. Adaptive Lookback Edge Cases Tests
# ============================================================================

class TestAdaptiveLookbackEdgeCases:
    """Test adaptive lookback edge cases"""
    
    def test_adaptive_lookback_insufficient_data(self):
        """Test adaptive lookback with insufficient data"""
        config = StrategyConfig.default()
        tf_analyzer = TimeframeAnalysis(config=config)
        
        # Very little data
        available_days = 100
        base_lookback = 20
        result = tf_analyzer._get_adaptive_lookback(available_days, base_lookback, 'daily')
        assert result == base_lookback  # Should return base if insufficient data
    
    def test_adaptive_lookback_disabled(self):
        """Test adaptive lookback when disabled"""
        config = StrategyConfig(enable_adaptive_lookback=False)
        tf_analyzer = TimeframeAnalysis(config=config)
        
        available_days = 2000
        base_lookback = 20
        result = tf_analyzer._get_adaptive_lookback(available_days, base_lookback, 'daily')
        assert result == base_lookback  # Should return base if disabled
    
    def test_adaptive_lookback_maximum_data(self):
        """Test adaptive lookback with maximum data"""
        config = StrategyConfig.default()
        tf_analyzer = TimeframeAnalysis(config=config)
        
        # Maximum data
        available_days = 3000
        base_lookback = 20
        result = tf_analyzer._get_adaptive_lookback(available_days, base_lookback, 'daily')
        assert result >= base_lookback  # Should increase with more data
        assert result <= 50  # Should not exceed maximum


# ============================================================================
# Main Test Runner
# ============================================================================

def main():
    """Run all edge case tests"""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    main()

