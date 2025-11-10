"""
Unit tests for Verdict Service - RSI30 Requirement Enforcement

Tests that trading parameters are only calculated when RSI < 30.
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from services.verdict_service import VerdictService
from config.strategy_config import StrategyConfig


class TestVerdictServiceRSI30:
    """Test RSI30 requirement enforcement in trading parameters calculation"""
    
    @pytest.fixture
    def config(self):
        """Create test configuration"""
        return StrategyConfig.default()
    
    @pytest.fixture
    def verdict_service(self, config):
        """Create VerdictService instance"""
        return VerdictService(config)
    
    @pytest.fixture
    def mock_df(self):
        """Create mock DataFrame"""
        return pd.DataFrame({
            'close': [100.0, 101.0, 99.0],
            'high': [105.0, 106.0, 104.0],
            'low': [95.0, 96.0, 94.0],
            'volume': [1000000, 1100000, 900000]
        })
    
    def test_trading_parameters_not_calculated_rsi_above_30(self, verdict_service, mock_df):
        """Test that trading parameters are NOT calculated when RSI >= 30"""
        result = verdict_service.calculate_trading_parameters(
            current_price=100.0,
            verdict='buy',
            recent_low=95.0,
            recent_high=110.0,
            timeframe_confirmation=None,
            df=mock_df,
            rsi_value=35.0,  # RSI >= 30
            is_above_ema200=True
        )
        
        assert result is None
    
    def test_trading_parameters_calculated_rsi_below_30(self, verdict_service, mock_df):
        """Test that trading parameters ARE calculated when RSI < 30"""
        with patch('services.verdict_service.calculate_smart_buy_range') as mock_buy_range, \
             patch('services.verdict_service.calculate_smart_stop_loss') as mock_stop, \
             patch('services.verdict_service.calculate_smart_target') as mock_target:
            
            mock_buy_range.return_value = (99.0, 101.0)
            mock_stop.return_value = 95.0
            mock_target.return_value = 110.0
            
            result = verdict_service.calculate_trading_parameters(
                current_price=100.0,
                verdict='buy',
                recent_low=95.0,
                recent_high=110.0,
                timeframe_confirmation=None,
                df=mock_df,
                rsi_value=25.0,  # RSI < 30
                is_above_ema200=True
            )
            
            assert result is not None
            assert 'buy_range' in result
            assert 'target' in result
            assert 'stop' in result
    
    def test_trading_parameters_not_calculated_rsi_none(self, verdict_service, mock_df):
        """Test that trading parameters are NOT calculated when RSI is None"""
        result = verdict_service.calculate_trading_parameters(
            current_price=100.0,
            verdict='buy',
            recent_low=95.0,
            recent_high=110.0,
            timeframe_confirmation=None,
            df=mock_df,
            rsi_value=None,  # RSI is None
            is_above_ema200=True
        )
        
        assert result is None
    
    def test_trading_parameters_not_calculated_verdict_not_buy(self, verdict_service, mock_df):
        """Test that trading parameters are NOT calculated when verdict is not buy/strong_buy"""
        result = verdict_service.calculate_trading_parameters(
            current_price=100.0,
            verdict='watch',  # Not buy/strong_buy
            recent_low=95.0,
            recent_high=110.0,
            timeframe_confirmation=None,
            df=mock_df,
            rsi_value=25.0,
            is_above_ema200=True
        )
        
        assert result is None
    
    def test_rsi_threshold_below_ema200(self, verdict_service, mock_df):
        """Test that RSI threshold is 20 when below EMA200"""
        # RSI = 25 (above 20 threshold for below EMA200)
        result = verdict_service.calculate_trading_parameters(
            current_price=100.0,
            verdict='buy',
            recent_low=95.0,
            recent_high=110.0,
            timeframe_confirmation=None,
            df=mock_df,
            rsi_value=25.0,  # RSI >= 20 (threshold for below EMA200)
            is_above_ema200=False  # Below EMA200
        )
        
        assert result is None  # Should not calculate (RSI >= 20)
    
    def test_rsi_threshold_below_ema200_passes(self, verdict_service, mock_df):
        """Test that RSI < 20 passes when below EMA200"""
        with patch('services.verdict_service.calculate_smart_buy_range') as mock_buy_range, \
             patch('services.verdict_service.calculate_smart_stop_loss') as mock_stop, \
             patch('services.verdict_service.calculate_smart_target') as mock_target:
            
            mock_buy_range.return_value = (99.0, 101.0)
            mock_stop.return_value = 95.0
            mock_target.return_value = 110.0
            
            result = verdict_service.calculate_trading_parameters(
                current_price=100.0,
                verdict='buy',
                recent_low=95.0,
                recent_high=110.0,
                timeframe_confirmation=None,
                df=mock_df,
                rsi_value=15.0,  # RSI < 20 (threshold for below EMA200)
                is_above_ema200=False  # Below EMA200
            )
            
            assert result is not None  # Should calculate (RSI < 20)
    
    def test_rsi_threshold_above_ema200(self, verdict_service, mock_df):
        """Test that RSI threshold is 30 when above EMA200"""
        # RSI = 35 (above 30 threshold for above EMA200)
        result = verdict_service.calculate_trading_parameters(
            current_price=100.0,
            verdict='buy',
            recent_low=95.0,
            recent_high=110.0,
            timeframe_confirmation=None,
            df=mock_df,
            rsi_value=35.0,  # RSI >= 30 (threshold for above EMA200)
            is_above_ema200=True  # Above EMA200
        )
        
        assert result is None  # Should not calculate (RSI >= 30)
    
    def test_rsi_threshold_above_ema200_passes(self, verdict_service, mock_df):
        """Test that RSI < 30 passes when above EMA200"""
        with patch('services.verdict_service.calculate_smart_buy_range') as mock_buy_range, \
             patch('services.verdict_service.calculate_smart_stop_loss') as mock_stop, \
             patch('services.verdict_service.calculate_smart_target') as mock_target:
            
            mock_buy_range.return_value = (99.0, 101.0)
            mock_stop.return_value = 95.0
            mock_target.return_value = 110.0
            
            result = verdict_service.calculate_trading_parameters(
                current_price=100.0,
                verdict='buy',
                recent_low=95.0,
                recent_high=110.0,
                timeframe_confirmation=None,
                df=mock_df,
                rsi_value=25.0,  # RSI < 30 (threshold for above EMA200)
                is_above_ema200=True  # Above EMA200
            )
            
            assert result is not None  # Should calculate (RSI < 30)
