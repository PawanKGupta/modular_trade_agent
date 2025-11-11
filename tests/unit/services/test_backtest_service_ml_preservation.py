"""
Unit tests for BacktestService ML prediction preservation.

Tests that initial ML predictions are preserved after backtest scoring.
"""
import pytest
from unittest.mock import Mock, patch
from services.backtest_service import BacktestService


class TestBacktestServiceMLPreservation:
    """Test ML prediction preservation during backtest scoring"""
    
    def test_preserve_initial_ml_predictions(self):
        """Test that initial ML predictions are preserved after backtest"""
        service = BacktestService(default_years_back=2, dip_mode=False)
        
        # Create sample stock result with ML predictions
        stock_results = [{
            'ticker': 'TEST.NS',
            'status': 'success',
            'verdict': 'buy',
            'strength_score': 50,
            'ml_verdict': 'buy',  # Initial ML prediction
            'ml_confidence': 78.5,  # Initial confidence
            'ml_probabilities': {'buy': 0.785, 'watch': 0.15, 'avoid': 0.05, 'strong_buy': 0.015}
        }]
        
        # Mock run_stock_backtest to return data
        with patch.object(service, 'run_stock_backtest', return_value={
            'backtest_score': 45,
            'total_return_pct': 3.5,
            'win_rate': 75.0,
            'total_trades': 8,
            'vs_buy_hold': 2.0,
            'execution_rate': 80.0
        }):
            # Add backtest scores
            results = service.add_backtest_scores_to_results(stock_results)
        
        # Verify ML predictions were preserved
        assert len(results) == 1
        result = results[0]
        
        assert result['ml_verdict'] == 'buy', "Initial ml_verdict should be preserved"
        assert result['ml_confidence'] == 78.5, "Initial ml_confidence should be preserved"
        assert result['ml_probabilities'] is not None, "Initial ml_probabilities should be preserved"
        
        # Verify backtest data was added
        assert 'backtest' in result
        assert result['backtest']['score'] == 45
        assert result['combined_score'] is not None
    
    def test_preserve_ml_when_downgraded(self):
        """Test ML preservation when verdict is downgraded by backtest"""
        service = BacktestService(default_years_back=2, dip_mode=False)
        
        stock_results = [{
            'ticker': 'TEST.NS',
            'status': 'success',
            'verdict': 'buy',
            'strength_score': 48,
            'ml_verdict': 'buy',  # Initial: BUY
            'ml_confidence': 65.0,
            'rsi': 28
        }]
        
        # Mock backtest with poor results (should trigger downgrade)
        with patch.object(service, 'run_stock_backtest', return_value={
            'backtest_score': 15,  # Low score
            'total_return_pct': 0.5,  # Very poor return
            'win_rate': 40.0,
            'total_trades': 5,
            'vs_buy_hold': -1.0,
            'execution_rate': 60.0
        }):
            results = service.add_backtest_scores_to_results(stock_results)
        
        result = results[0]
        
        # Verdict may be downgraded due to poor backtest (or may stay buy with low combined score)
        # The key is ML predictions should be preserved regardless
        
        # ML predictions should still be preserved (initial values)
        assert result['ml_verdict'] == 'buy', "Initial ml_verdict preserved regardless of backtest result"
        assert result['ml_confidence'] == 65.0, "Initial ml_confidence preserved regardless of backtest result"
        
        # Verify backtest data was added
        assert result['combined_score'] < 40, "Combined score should be low due to poor backtest"
    
    def test_preserve_ml_none_values(self):
        """Test preservation when ML predictions are None"""
        service = BacktestService(default_years_back=2, dip_mode=False)
        
        stock_results = [{
            'ticker': 'TEST.NS',
            'status': 'success',
            'verdict': 'watch',
            'strength_score': 30,
            'ml_verdict': None,  # No ML prediction
            'ml_confidence': None
        }]
        
        with patch.object(service, 'run_stock_backtest', return_value={
            'backtest_score': 35,
            'total_return_pct': 2.0,
            'win_rate': 60.0,
            'total_trades': 3,
            'vs_buy_hold': 0.5,
            'execution_rate': 75.0
        }):
            results = service.add_backtest_scores_to_results(stock_results)
        
        result = results[0]
        
        # None values should be preserved
        assert result.get('ml_verdict') is None
        assert result.get('ml_confidence') is None
    
    def test_preserve_ml_without_initial_field(self):
        """Test when stock result doesn't have ml_verdict field at all"""
        service = BacktestService(default_years_back=2, dip_mode=False)
        
        stock_results = [{
            'ticker': 'TEST.NS',
            'status': 'success',
            'verdict': 'buy',
            'strength_score': 45
            # No ml_verdict or ml_confidence fields
        }]
        
        with patch.object(service, 'run_stock_backtest', return_value={
            'backtest_score': 50,
            'total_return_pct': 4.0,
            'win_rate': 70.0,
            'total_trades': 6,
            'vs_buy_hold': 1.5,
            'execution_rate': 85.0
        }):
            results = service.add_backtest_scores_to_results(stock_results)
        
        result = results[0]
        
        # Should not crash, and no ML fields added
        assert result.get('ml_verdict') is None
        assert result.get('ml_confidence') is None
    
    def test_ml_preservation_on_backtest_error(self):
        """Test ML preservation when backtest fails"""
        service = BacktestService(default_years_back=2, dip_mode=False)
        
        stock_results = [{
            'ticker': 'TEST.NS',
            'status': 'success',
            'verdict': 'buy',
            'strength_score': 50,
            'ml_verdict': 'strong_buy',
            'ml_confidence': 88.5
        }]
        
        # Mock backtest to raise an error
        with patch.object(service, 'run_stock_backtest', side_effect=Exception("Backtest failed")):
            results = service.add_backtest_scores_to_results(stock_results)
        
        result = results[0]
        
        # ML should still be preserved even when backtest fails
        assert result['ml_verdict'] == 'strong_buy'
        assert result['ml_confidence'] == 88.5
        assert 'backtest' in result
        assert result['backtest']['score'] == 0
        assert 'error' in result['backtest']

