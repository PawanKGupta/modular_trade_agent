"""
Unit tests for ML-only signal parameter calculation

Tests the fix for issue where ML-only buy/strong_buy signals had missing trading
parameters (showing 0.00 values), causing Telegram API errors.

Key scenarios tested:
1. Parameters calculated when last_close is available
2. Parameters calculated using pre_fetched_df fallback
3. Parameters calculated using stock_info fallback
4. Parameters set to None when no valid price source available
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime


@pytest.fixture
def mock_stock_result_with_last_close():
    """Stock result with valid last_close"""
    return {
        'ticker': 'TEST.NS',
        'ml_verdict': 'buy',
        'ml_confidence': 45.0,
        'final_verdict': 'watch',  # Rules rejected, ML approved
        'last_close': 100.0,
        'timeframe_analysis': {'alignment_score': 6}
    }


@pytest.fixture
def mock_stock_result_with_prefetched_df():
    """Stock result with price in pre_fetched_df"""
    df = pd.DataFrame({
        'close': [95.0, 98.0, 100.0],
        'open': [94.0, 97.0, 99.0],
        'high': [96.0, 99.0, 101.0],
        'low': [93.0, 96.0, 98.0]
    })
    
    return {
        'ticker': 'TEST2.NS',
        'ml_verdict': 'strong_buy',
        'ml_confidence': 55.0,
        'final_verdict': 'avoid',  # Rules rejected, ML approved
        'last_close': None,  # Missing
        'pre_fetched_df': df,
        'timeframe_analysis': {'alignment_score': 8}
    }


@pytest.fixture
def mock_stock_result_with_stock_info():
    """Stock result with price in stock_info"""
    return {
        'ticker': 'TEST3.NS',
        'ml_verdict': 'buy',
        'ml_confidence': 42.0,
        'final_verdict': 'watch',
        'last_close': 0,  # Invalid
        'pre_fetched_df': None,  # Not available
        'stock_info': {
            'currentPrice': 120.0,
            'regularMarketPrice': 120.0
        },
        'timeframe_analysis': {'alignment_score': 5}
    }


@pytest.fixture
def mock_stock_result_no_price():
    """Stock result with no valid price source"""
    return {
        'ticker': 'TEST4.NS',
        'ml_verdict': 'buy',
        'ml_confidence': 40.0,
        'final_verdict': 'avoid',
        'last_close': None,
        'pre_fetched_df': None,
        'stock_info': None,
        'timeframe_analysis': None
    }


class TestMLParameterCalculation:
    """Test ML-only signal parameter calculation"""
    
    @patch('core.backtest_scoring.run_simple_backtest', return_value={})
    @patch('services.backtest_service.calculate_smart_buy_range')
    @patch('services.backtest_service.calculate_smart_stop_loss')
    @patch('services.backtest_service.calculate_smart_target')
    def test_calculates_params_from_last_close(
        self,
        mock_target,
        mock_stop,
        mock_buy_range,
        mock_backtest,
        mock_stock_result_with_last_close
    ):
        """Test parameter calculation using last_close"""
        # Arrange
        mock_buy_range.return_value = (95.0, 100.0)
        mock_stop.return_value = 92.0
        mock_target.return_value = 110.0
        
        from services.backtest_service import BacktestService
        service = BacktestService()
        
        # Act
        results = service.add_backtest_scores([mock_stock_result_with_last_close])
        
        # Assert
        result = results[0]
        assert result['buy_range'] == (95.0, 100.0)
        assert result['target'] == 110.0
        assert result['stop'] == 92.0
        
        # Verify calculation was called with correct price
        mock_buy_range.assert_called_once()
        call_args = mock_buy_range.call_args[0]
        assert call_args[0] == 100.0  # current_price from last_close
    
    @patch('core.backtest_scoring.run_simple_backtest', return_value={})
    @patch('services.backtest_service.calculate_smart_buy_range')
    @patch('services.backtest_service.calculate_smart_stop_loss')
    @patch('services.backtest_service.calculate_smart_target')
    def test_calculates_params_from_prefetched_df(
        self,
        mock_target,
        mock_stop,
        mock_buy_range,
        mock_backtest,
        mock_stock_result_with_prefetched_df
    ):
        """Test parameter calculation using pre_fetched_df fallback"""
        # Arrange
        mock_buy_range.return_value = (98.0, 102.0)
        mock_stop.return_value = 90.0
        mock_target.return_value = 115.0
        
        from services.backtest_service import BacktestService
        service = BacktestService()
        
        # Act
        results = service.add_backtest_scores([mock_stock_result_with_prefetched_df])
        
        # Assert
        result = results[0]
        assert result['buy_range'] == (98.0, 102.0)
        assert result['target'] == 115.0
        assert result['stop'] == 90.0
        
        # Verify calculation was called with price from DataFrame
        mock_buy_range.assert_called_once()
        call_args = mock_buy_range.call_args[0]
        assert call_args[0] == 100.0  # Last close from pre_fetched_df
    
    @patch('core.backtest_scoring.run_simple_backtest', return_value={})
    @patch('services.backtest_service.calculate_smart_buy_range')
    @patch('services.backtest_service.calculate_smart_stop_loss')
    @patch('services.backtest_service.calculate_smart_target')
    def test_calculates_params_from_stock_info(
        self,
        mock_target,
        mock_stop,
        mock_buy_range,
        mock_backtest,
        mock_stock_result_with_stock_info
    ):
        """Test parameter calculation using stock_info fallback"""
        # Arrange
        mock_buy_range.return_value = (118.0, 122.0)
        mock_stop.return_value = 110.0
        mock_target.return_value = 135.0
        
        from services.backtest_service import BacktestService
        service = BacktestService()
        
        # Act
        results = service.add_backtest_scores([mock_stock_result_with_stock_info])
        
        # Assert
        result = results[0]
        assert result['buy_range'] == (118.0, 122.0)
        assert result['target'] == 135.0
        assert result['stop'] == 110.0
        
        # Verify calculation was called with price from stock_info
        mock_buy_range.assert_called_once()
        call_args = mock_buy_range.call_args[0]
        assert call_args[0] == 120.0  # currentPrice from stock_info
    
    @patch('core.backtest_scoring.run_simple_backtest', return_value={})
    def test_sets_none_when_no_price_available(self, mock_backtest, mock_stock_result_no_price):
        """Test that parameters are set to None when no valid price source exists"""
        # Arrange
        from services.backtest_service import BacktestService
        service = BacktestService()
        
        # Act
        results = service.add_backtest_scores([mock_stock_result_no_price])
        
        # Assert
        result = results[0]
        assert result['buy_range'] is None
        assert result['target'] is None
        assert result['stop'] is None
    
    @patch('core.backtest_scoring.run_simple_backtest', return_value={})
    def test_handles_rule_approved_ml_approved_signals(self, mock_backtest):
        """Test that parameters are calculated for signals approved by both rules and ML"""
        # Arrange
        stock_result = {
            'ticker': 'TEST5.NS',
            'ml_verdict': 'buy',
            'final_verdict': 'buy',  # Both approved
            'last_close': 150.0,
            'buy_range': (148.0, 152.0),  # Already set by rules
            'target': 165.0,
            'stop': 140.0,
            'timeframe_analysis': {'alignment_score': 7}
        }
        
        from services.backtest_service import BacktestService
        service = BacktestService()
        
        # Act
        results = service.add_backtest_scores([stock_result])
        
        # Assert - parameters should be preserved (not recalculated)
        result = results[0]
        assert result['buy_range'] == (148.0, 152.0)
        assert result['target'] == 165.0
        assert result['stop'] == 140.0


class TestTelegramFormatFiltering:
    """Test that stocks with invalid parameters are filtered from Telegram messages"""
    
    def test_returns_none_for_missing_parameters(self):
        """Test that get_enhanced_stock_info returns None for missing parameters"""
        # Arrange
        from trade_agent import get_enhanced_stock_info
        
        stock_data = {
            'ticker': 'TEST.NS',
            'buy_range': None,
            'target': None,
            'stop': None,
            'rsi': 25.0,
            'last_close': 100.0
        }
        
        # Act
        result = get_enhanced_stock_info(stock_data, 1)
        
        # Assert
        assert result is None
    
    def test_returns_none_for_zero_parameters(self):
        """Test that get_enhanced_stock_info returns None for zero parameters"""
        # Arrange
        from trade_agent import get_enhanced_stock_info
        
        stock_data = {
            'ticker': 'TEST.NS',
            'buy_range': (0, 0),
            'target': 0,
            'stop': 0,
            'rsi': 25.0,
            'last_close': 100.0
        }
        
        # Act
        result = get_enhanced_stock_info(stock_data, 1)
        
        # Assert
        assert result is None
    
    def test_returns_formatted_string_for_valid_parameters(self):
        """Test that get_enhanced_stock_info returns formatted string for valid parameters"""
        # Arrange
        from trade_agent import get_enhanced_stock_info
        
        stock_data = {
            'ticker': 'TEST.NS',
            'buy_range': (95.0, 100.0),
            'target': 110.0,
            'stop': 92.0,
            'rsi': 25.0,
            'last_close': 100.0,
            'today_vol': 150000,
            'avg_vol': 100000,
            'timeframe_analysis': {'alignment_score': 8}
        }
        
        # Act
        result = get_enhanced_stock_info(stock_data, 1)
        
        # Assert
        assert result is not None
        assert 'TEST.NS' in result
        assert '95.00-100.00' in result
        assert '110.00' in result
        assert '92.00' in result

