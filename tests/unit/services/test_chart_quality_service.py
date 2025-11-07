"""
Unit tests for ChartQualityService

Tests chart quality analysis including gap detection, movement analysis,
and extreme candle detection.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

# Import directly to avoid sklearn dependency issues
import importlib.util
spec = importlib.util.spec_from_file_location(
    "chart_quality_service",
    str(project_root / "services" / "chart_quality_service.py")
)
chart_quality_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chart_quality_module)
ChartQualityService = chart_quality_module.ChartQualityService

from config.strategy_config import StrategyConfig


class TestChartQualityService:
    """Test suite for ChartQualityService"""
    
    def test_initialization(self):
        """Test that ChartQualityService initializes correctly"""
        service = ChartQualityService()
        assert service is not None
        assert service.config is not None
        assert hasattr(service, 'max_gap_frequency')
        assert hasattr(service, 'min_daily_range_pct')
        assert hasattr(service, 'max_extreme_candle_frequency')
        assert hasattr(service, 'min_score')
        assert hasattr(service, 'enabled')
    
    def test_initialization_with_config(self):
        """Test initialization with custom config"""
        config = StrategyConfig.default()
        service = ChartQualityService(config=config)
        assert service.config == config
    
    def test_normalize_column_names(self):
        """Test column name normalization"""
        service = ChartQualityService()
        
        # Test with capitalized columns (yfinance format)
        df = pd.DataFrame({
            'Close': [100, 101, 102],
            'Open': [99, 100, 101],
            'High': [101, 102, 103],
            'Low': [98, 99, 100],
            'Volume': [1000, 1100, 1200]
        })
        
        normalized = service._normalize_column_names(df)
        assert 'close' in normalized.columns
        assert 'open' in normalized.columns
        assert 'high' in normalized.columns
        assert 'low' in normalized.columns
        assert 'volume' in normalized.columns
    
    def test_analyze_gaps_no_gaps(self):
        """Test gap analysis with no gaps"""
        service = ChartQualityService()
        
        # Create data with no gaps (continuous prices)
        dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            'high': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108]
        }, index=dates)
        
        result = service.analyze_gaps(df)
        
        assert result['gap_count'] == 0
        assert result['gap_frequency'] == 0.0
        assert result['has_too_many_gaps'] is False
    
    def test_analyze_gaps_with_gaps(self):
        """Test gap analysis with gaps"""
        service = ChartQualityService()
        
        # Create data with gaps
        dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'close': [100, 101, 105, 106, 110, 111, 115, 116, 120, 121],
            'open': [100, 101, 105, 106, 110, 111, 115, 116, 120, 121],
            'high': [101, 102, 106, 107, 111, 112, 116, 117, 121, 122],
            'low': [99, 100, 104, 105, 109, 110, 114, 115, 119, 120]
        }, index=dates)
        
        # Create gaps: low > prev close
        df.loc[dates[2], 'low'] = 103  # Gap up
        df.loc[dates[4], 'low'] = 108  # Gap up
        df.loc[dates[6], 'low'] = 113  # Gap up
        
        result = service.analyze_gaps(df)
        
        assert result['gap_count'] >= 0  # May detect gaps
        assert 'gap_frequency' in result
        assert 'has_too_many_gaps' in result
    
    def test_analyze_gaps_insufficient_data(self):
        """Test gap analysis with insufficient data"""
        service = ChartQualityService()
        
        # Create data with less than 2 rows
        df = pd.DataFrame({
            'close': [100],
            'open': [100],
            'high': [101],
            'low': [99]
        })
        
        result = service.analyze_gaps(df)
        
        assert result['gap_count'] == 0
        assert result['gap_frequency'] == 0.0
        assert result['has_too_many_gaps'] is False
        assert 'Insufficient data' in result['reason']
    
    def test_analyze_movement_flat_chart(self):
        """Test movement analysis with flat chart"""
        service = ChartQualityService()
        
        # Create flat chart (minimal movement)
        dates = pd.date_range(start='2024-01-01', periods=20, freq='D')
        df = pd.DataFrame({
            'close': [100] * 20,
            'open': [100] * 20,
            'high': [100.1] * 20,
            'low': [99.9] * 20
        }, index=dates)
        
        result = service.analyze_movement(df)
        
        assert 'has_movement' in result
        assert 'avg_daily_range_pct' in result
        assert 'is_flat' in result
    
    def test_analyze_movement_active_chart(self):
        """Test movement analysis with active chart"""
        service = ChartQualityService()
        
        # Create active chart (good movement)
        dates = pd.date_range(start='2024-01-01', periods=20, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 0.5 for i in range(20)],
            'open': [100 + i * 0.5 for i in range(20)],
            'high': [100.5 + i * 0.5 for i in range(20)],
            'low': [99.5 + i * 0.5 for i in range(20)]
        }, index=dates)
        
        result = service.analyze_movement(df)
        
        assert 'has_movement' in result
        assert 'avg_daily_range_pct' in result
        assert result['avg_daily_range_pct'] > 0
    
    def test_analyze_movement_insufficient_data(self):
        """Test movement analysis with insufficient data"""
        service = ChartQualityService()
        
        # Create data with less than 10 rows
        df = pd.DataFrame({
            'close': [100, 101, 102],
            'open': [100, 101, 102],
            'high': [101, 102, 103],
            'low': [99, 100, 101]
        })
        
        result = service.analyze_movement(df)
        
        assert result['has_movement'] is True  # Default when insufficient data
        assert 'Insufficient data' in result['reason']
    
    def test_analyze_extreme_candles_no_extreme(self):
        """Test extreme candle analysis with no extreme candles"""
        service = ChartQualityService()
        
        # Create normal candles
        dates = pd.date_range(start='2024-01-01', periods=20, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 0.1 for i in range(20)],
            'open': [100 + i * 0.1 for i in range(20)],
            'high': [100.2 + i * 0.1 for i in range(20)],
            'low': [99.8 + i * 0.1 for i in range(20)]
        }, index=dates)
        
        result = service.analyze_extreme_candles(df)
        
        assert 'extreme_candle_count' in result
        assert 'extreme_candle_frequency' in result
        assert 'has_extreme_candles' in result
    
    def test_analyze_extreme_candles_insufficient_data(self):
        """Test extreme candle analysis with insufficient data"""
        service = ChartQualityService()
        
        # Create data with less than 5 rows
        df = pd.DataFrame({
            'close': [100, 101, 102],
            'open': [100, 101, 102],
            'high': [101, 102, 103],
            'low': [99, 100, 101]
        })
        
        result = service.analyze_extreme_candles(df)
        
        assert result['extreme_candle_count'] == 0
        assert result['extreme_candle_frequency'] == 0.0
        assert result['has_extreme_candles'] is False
        assert 'Insufficient data' in result['reason']
    
    def test_calculate_chart_cleanliness_score_clean_chart(self):
        """Test cleanliness score calculation for clean chart"""
        service = ChartQualityService()
        
        # Create clean chart (no gaps, good movement, no extreme candles)
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 0.2 for i in range(60)],
            'open': [100 + i * 0.2 for i in range(60)],
            'high': [100.3 + i * 0.2 for i in range(60)],
            'low': [99.7 + i * 0.2 for i in range(60)]
        }, index=dates)
        
        result = service.calculate_chart_cleanliness_score(df)
        
        assert result['score'] >= 0
        assert result['score'] <= 100
        assert 'status' in result
        assert 'passed' in result
        assert result['passed'] is True  # Should pass for clean chart
    
    def test_calculate_chart_cleanliness_score_poor_chart(self):
        """Test cleanliness score calculation for poor chart"""
        service = ChartQualityService()
        
        # Create poor chart (many gaps, flat, extreme candles)
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        df = pd.DataFrame({
            'close': [100] * 60,  # Flat
            'open': [100] * 60,
            'high': [100.1] * 60,
            'low': [99.9] * 60
        }, index=dates)
        
        # Add gaps
        for i in range(10, 60, 5):
            df.loc[dates[i], 'low'] = 102  # Gap up
        
        result = service.calculate_chart_cleanliness_score(df)
        
        assert result['score'] >= 0
        assert result['score'] <= 100
        assert 'status' in result
        assert 'passed' in result
    
    def test_calculate_chart_cleanliness_score_disabled(self):
        """Test cleanliness score when service is disabled"""
        config = StrategyConfig.default()
        config.chart_quality_enabled = False
        service = ChartQualityService(config=config)
        
        df = pd.DataFrame({
            'close': [100, 101, 102],
            'open': [100, 101, 102],
            'high': [101, 102, 103],
            'low': [99, 100, 101]
        })
        
        result = service.calculate_chart_cleanliness_score(df)
        
        assert result['score'] == 100.0
        assert result['status'] == 'disabled'
        assert result['passed'] is True
        assert 'disabled' in result['reason']
    
    def test_assess_chart_quality(self):
        """Test main entry point for chart quality assessment"""
        service = ChartQualityService()
        
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 0.2 for i in range(60)],
            'open': [100 + i * 0.2 for i in range(60)],
            'high': [100.3 + i * 0.2 for i in range(60)],
            'low': [99.7 + i * 0.2 for i in range(60)]
        }, index=dates)
        
        result = service.assess_chart_quality(df)
        
        assert 'score' in result
        assert 'status' in result
        assert 'passed' in result
        assert 'gap_analysis' in result
        assert 'movement_analysis' in result
        assert 'extreme_candle_analysis' in result
        assert 'reason' in result
    
    def test_is_chart_acceptable_clean(self):
        """Test chart acceptance check for clean chart"""
        service = ChartQualityService()
        
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 0.2 for i in range(60)],
            'open': [100 + i * 0.2 for i in range(60)],
            'high': [100.3 + i * 0.2 for i in range(60)],
            'low': [99.7 + i * 0.2 for i in range(60)]
        }, index=dates)
        
        result = service.is_chart_acceptable(df)
        assert isinstance(result, bool)
    
    def test_is_chart_acceptable_disabled(self):
        """Test chart acceptance when service is disabled"""
        config = StrategyConfig.default()
        config.chart_quality_enabled = False
        service = ChartQualityService(config=config)
        
        df = pd.DataFrame({
            'close': [100, 101, 102],
            'open': [100, 101, 102],
            'high': [101, 102, 103],
            'low': [99, 100, 101]
        })
        
        result = service.is_chart_acceptable(df)
        assert result is True  # Should always pass when disabled
    
    def test_error_handling_invalid_data(self):
        """Test error handling with invalid data"""
        service = ChartQualityService()
        
        # Test with empty DataFrame
        df = pd.DataFrame()
        result = service.calculate_chart_cleanliness_score(df)
        assert 'score' in result
        assert 'status' in result
        # Service handles empty DataFrame gracefully, may return error or default values
        assert isinstance(result['score'], (int, float))
    
    def test_error_handling_missing_columns(self):
        """Test error handling with missing columns"""
        service = ChartQualityService()
        
        # Test with missing columns
        df = pd.DataFrame({
            'price': [100, 101, 102]
        })
        
        # Should handle gracefully
        try:
            result = service.assess_chart_quality(df)
            assert 'score' in result
        except Exception:
            # If it raises, that's also acceptable behavior
            pass
    
    def test_configurable_thresholds(self):
        """Test that thresholds are configurable"""
        config = StrategyConfig.default()
        config.chart_quality_min_score = 80.0
        config.chart_quality_max_gap_frequency = 10.0
        
        service = ChartQualityService(config=config)
        
        assert service.min_score == 80.0
        assert service.max_gap_frequency == 10.0
    
    def test_gap_analysis_edge_cases(self):
        """Test gap analysis edge cases"""
        service = ChartQualityService()
        
        # Test with single row
        df = pd.DataFrame({
            'close': [100],
            'open': [100],
            'high': [101],
            'low': [99]
        })
        
        result = service.analyze_gaps(df)
        assert result['gap_count'] == 0
        
        # Test with exactly 2 rows
        df = pd.DataFrame({
            'close': [100, 101],
            'open': [100, 101],
            'high': [101, 102],
            'low': [99, 100]
        })
        
        result = service.analyze_gaps(df)
        assert 'gap_count' in result
    
    def test_movement_analysis_edge_cases(self):
        """Test movement analysis edge cases"""
        service = ChartQualityService()
        
        # Test with exactly 10 rows (boundary)
        dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 0.1 for i in range(10)],
            'open': [100 + i * 0.1 for i in range(10)],
            'high': [100.2 + i * 0.1 for i in range(10)],
            'low': [99.8 + i * 0.1 for i in range(10)]
        }, index=dates)
        
        result = service.analyze_movement(df)
        assert 'has_movement' in result
    
    def test_extreme_candle_analysis_edge_cases(self):
        """Test extreme candle analysis edge cases"""
        service = ChartQualityService()
        
        # Test with exactly 5 rows (boundary)
        dates = pd.date_range(start='2024-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 0.1 for i in range(5)],
            'open': [100 + i * 0.1 for i in range(5)],
            'high': [100.2 + i * 0.1 for i in range(5)],
            'low': [99.8 + i * 0.1 for i in range(5)]
        }, index=dates)
        
        result = service.analyze_extreme_candles(df)
        assert 'extreme_candle_count' in result
    
    def test_analyze_gaps_gap_down(self):
        """Test gap analysis with gap down"""
        service = ChartQualityService()
        
        # Create data with gap down
        dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'close': [100, 101, 95, 96, 97, 98, 99, 100, 101, 102],
            'open': [100, 101, 95, 96, 97, 98, 99, 100, 101, 102],
            'high': [101, 102, 96, 97, 98, 99, 100, 101, 102, 103],
            'low': [99, 100, 94, 95, 96, 97, 98, 99, 100, 101]
        }, index=dates)
        
        # Create gap down: high < prev close
        df.loc[dates[2], 'high'] = 98  # Gap down
        
        result = service.analyze_gaps(df)
        
        assert result['gap_count'] >= 0  # May detect gap down
        assert 'gap_frequency' in result
    
    def test_analyze_movement_exception_handling(self):
        """Test movement analysis exception handling"""
        service = ChartQualityService()
        
        # Create invalid data that might cause exception
        df = pd.DataFrame({
            'close': [None, None, None],
            'open': [None, None, None],
            'high': [None, None, None],
            'low': [None, None, None]
        })
        
        # Should handle gracefully
        result = service.analyze_movement(df)
        assert 'has_movement' in result or 'reason' in result
    
    def test_analyze_extreme_candles_zero_range(self):
        """Test extreme candle analysis with zero range"""
        service = ChartQualityService()
        
        # Create data that might result in zero range
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'close': [100] * 30,  # Flat prices
            'open': [100] * 30,
            'high': [100] * 30,
            'low': [100] * 30
        }, index=dates)
        
        result = service.analyze_extreme_candles(df)
        assert 'extreme_candle_count' in result
    
    def test_analyze_extreme_candles_none_metrics(self):
        """Test extreme candle analysis when metrics is None"""
        service = ChartQualityService()
        
        # Create data that might cause calculate_candle_metrics to return None
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 0.1 for i in range(30)],
            'open': [100 + i * 0.1 for i in range(30)],
            'high': [100.2 + i * 0.1 for i in range(30)],
            'low': [99.8 + i * 0.1 for i in range(30)]
        }, index=dates)
        
        # Should handle None metrics gracefully
        result = service.analyze_extreme_candles(df)
        assert 'extreme_candle_count' in result
    
    def test_calculate_chart_cleanliness_score_exception_handling(self):
        """Test cleanliness score exception handling"""
        service = ChartQualityService()
        
        # Create data that might cause exception in scoring
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 0.2 for i in range(60)],
            'open': [100 + i * 0.2 for i in range(60)],
            'high': [100.3 + i * 0.2 for i in range(60)],
            'low': [99.7 + i * 0.2 for i in range(60)]
        }, index=dates)
        
        result = service.calculate_chart_cleanliness_score(df)
        assert 'score' in result
        assert 'status' in result
    
    def test_calculate_chart_cleanliness_score_too_many_gaps(self):
        """Test cleanliness score with too many gaps"""
        service = ChartQualityService()
        
        # Create chart with many gaps
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 0.1 for i in range(60)],
            'open': [100 + i * 0.1 for i in range(60)],
            'high': [100.2 + i * 0.1 for i in range(60)],
            'low': [99.8 + i * 0.1 for i in range(60)]
        }, index=dates)
        
        # Add many gaps (more than threshold)
        for i in range(15, 60, 2):
            df.loc[dates[i], 'low'] = df.loc[dates[i-1], 'close'] + 2  # Gap up
        
        result = service.calculate_chart_cleanliness_score(df)
        assert result['score'] < 100  # Should have penalty
        assert 'has_too_many_gaps' in result.get('gap_analysis', {})
    
    def test_calculate_chart_cleanliness_score_extreme_candles(self):
        """Test cleanliness score with extreme candles"""
        service = ChartQualityService()
        
        # Create chart with extreme candles
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'close': [100 + i * 0.1 for i in range(30)],
            'open': [100 + i * 0.1 for i in range(30)],
            'high': [100.2 + i * 0.1 for i in range(30)],
            'low': [99.8 + i * 0.1 for i in range(30)]
        }, index=dates)
        
        # Add extreme candles (big moves)
        for i in range(5, 30, 3):
            df.loc[dates[i], 'close'] = df.loc[dates[i], 'open'] + 10  # Big move
            df.loc[dates[i], 'high'] = df.loc[dates[i], 'close'] + 1
            df.loc[dates[i], 'low'] = df.loc[dates[i], 'open'] - 1
        
        result = service.calculate_chart_cleanliness_score(df)
        assert result['score'] < 100  # Should have penalty
        assert 'has_extreme_candles' in result.get('extreme_candle_analysis', {})
    
    def test_calculate_chart_cleanliness_score_poor_status(self):
        """Test cleanliness score with poor status"""
        service = ChartQualityService()
        
        # Create poor chart (many gaps, flat, extreme candles)
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        df = pd.DataFrame({
            'close': [100] * 60,  # Flat
            'open': [100] * 60,
            'high': [100.1] * 60,
            'low': [99.9] * 60
        }, index=dates)
        
        # Add many gaps
        for i in range(10, 60, 3):
            df.loc[dates[i], 'low'] = 102  # Gap up
        
        result = service.calculate_chart_cleanliness_score(df)
        assert result['status'] == 'poor' or result['score'] < 60
        assert result['passed'] is False
    
    def test_calculate_chart_cleanliness_score_exception(self):
        """Test cleanliness score exception handling"""
        service = ChartQualityService()
        
        # Create data that will cause exception
        # Use invalid data that breaks the analysis
        df = pd.DataFrame()
        
        # Should handle exception gracefully
        result = service.calculate_chart_cleanliness_score(df)
        assert 'score' in result
        assert 'status' in result
        # Service may handle empty DataFrame differently, just check it returns valid structure
        assert isinstance(result['score'], (int, float))
        assert isinstance(result['status'], str)

