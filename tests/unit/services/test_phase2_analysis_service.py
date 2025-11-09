"""
Unit Tests for Phase 2: AnalysisService with Pre-fetched Data

Tests for:
1. AnalysisService accepts pre-fetched data
2. Pre-calculated indicators optimization
3. Data fetching optimization
"""
import sys
from pathlib import Path
import pytest
import pandas as pd
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from services.analysis_service import AnalysisService
from config.strategy_config import StrategyConfig


class TestAnalysisServicePreFetchedData:
    """Test AnalysisService with pre-fetched data optimization"""
    
    def create_test_dataframe(self):
        """Create test DataFrame with OHLCV data"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        
        df = pd.DataFrame({
            'open': range(100, 200),
            'high': range(101, 201),
            'low': range(99, 199),
            'close': range(100, 200),
            'volume': [1000000] * 100
        }, index=dates)
        
        return df
    
    def test_analysis_service_accepts_pre_fetched_daily(self):
        """Test AnalysisService accepts pre-fetched daily data"""
        service = AnalysisService()
        df = self.create_test_dataframe()
        
        # Mock indicator service to avoid actual computation
        with patch.object(service.indicator_service, 'compute_indicators', return_value=df):
            with patch.object(service.signal_service, 'detect_all_signals', return_value={
                'signals': [],
                'timeframe_confirmation': {},
                'news_sentiment': None
            }):
                with patch.object(service.verdict_service, 'assess_volume', return_value={
                    'vol_ok': True,
                    'vol_strong': False,
                    'avg_vol': 1000000,
                    'today_vol': 1000000,
                    'volume_analysis': {},
                    'volume_pattern': {},
                    'volume_description': ''
                }):
                    with patch.object(service.verdict_service, 'fetch_fundamentals', return_value={
                        'pe': 20.0,
                        'pb': 2.0
                    }):
                        with patch.object(service.verdict_service, 'determine_verdict', return_value=('buy', [])):
                            with patch.object(service.verdict_service, 'apply_candle_quality_check', return_value=('buy', {}, None)):
                                with patch.object(service.verdict_service, 'calculate_trading_parameters', return_value={
                                    'buy_range': [100, 105],
                                    'target': 110,
                                    'stop': 95
                                }):
                                    with patch.object(service.data_service, 'get_latest_row', return_value=df.iloc[-1]):
                                        with patch.object(service.data_service, 'get_previous_row', return_value=df.iloc[-2] if len(df) > 1 else None):
                                            with patch.object(service.data_service, 'get_recent_extremes', return_value={'high': 200, 'low': 100}):
                                                result = service.analyze_ticker(
                                                    ticker='TEST.NS',
                                                    enable_multi_timeframe=False,
                                                    pre_fetched_daily=df
                                                )
                                                
                                                assert result is not None
                                                assert result.get('status') == 'success'
    
    def test_analysis_service_accepts_pre_calculated_indicators(self):
        """Test AnalysisService accepts pre-calculated indicators"""
        service = AnalysisService()
        df = self.create_test_dataframe()
        
        pre_calculated = {
            'rsi': 25.0,
            'ema200': 150.0
        }
        
        # Mock indicator service
        with patch.object(service.indicator_service, 'compute_indicators', return_value=df):
            with patch.object(service.signal_service, 'detect_all_signals', return_value={
                'signals': [],
                'timeframe_confirmation': {},
                'news_sentiment': None
            }):
                with patch.object(service.verdict_service, 'assess_volume', return_value={
                    'vol_ok': True,
                    'vol_strong': False,
                    'avg_vol': 1000000,
                    'today_vol': 1000000,
                    'volume_analysis': {},
                    'volume_pattern': {},
                    'volume_description': ''
                }):
                    with patch.object(service.verdict_service, 'fetch_fundamentals', return_value={
                        'pe': 20.0,
                        'pb': 2.0
                    }):
                        with patch.object(service.verdict_service, 'determine_verdict', return_value=('buy', [])):
                            with patch.object(service.verdict_service, 'apply_candle_quality_check', return_value=('buy', {}, None)):
                                with patch.object(service.verdict_service, 'calculate_trading_parameters', return_value={
                                    'buy_range': [100, 105],
                                    'target': 110,
                                    'stop': 95
                                }):
                                    with patch.object(service.data_service, 'get_latest_row', return_value=df.iloc[-1]):
                                        with patch.object(service.data_service, 'get_previous_row', return_value=df.iloc[-2] if len(df) > 1 else None):
                                            with patch.object(service.data_service, 'get_recent_extremes', return_value={'high': 200, 'low': 100}):
                                                result = service.analyze_ticker(
                                                    ticker='TEST.NS',
                                                    enable_multi_timeframe=False,
                                                    pre_fetched_daily=df,
                                                    pre_calculated_indicators=pre_calculated
                                                )
                                                
                                                assert result is not None
    
    def test_analysis_service_uses_config(self):
        """Test AnalysisService uses StrategyConfig"""
        config = StrategyConfig(rsi_period=14)
        service = AnalysisService(config=config)
        
        assert service.config.rsi_period == 14
        assert service.indicator_service.config.rsi_period == 14
        assert service.signal_service.config.rsi_period == 14
        assert service.verdict_service.config.rsi_period == 14


if __name__ == "__main__":
    pytest.main([__file__, '-v'])


