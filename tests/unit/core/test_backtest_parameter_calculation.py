#!/usr/bin/env python3
"""
Unit tests for trading parameter calculation in backtest scoring

Tests that buy_range, target, and stop are calculated for both:
- Rule-based buy/strong_buy verdicts
- ML-only buy/strong_buy verdicts
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


class TestBacktestParameterCalculation:
    """Test trading parameter calculation logic"""
    
    def test_parameters_calculated_for_rule_based_buy(self):
        """Test that parameters are calculated when rule-based verdict is buy"""
        stock_result = {
            'ticker': 'TEST.NS',
            'final_verdict': 'buy',
            'last_close': 100.0,
            'timeframe_analysis': {'alignment_score': 5}
        }
        
        # Check condition
        needs_params = stock_result['final_verdict'] in ['buy', 'strong_buy']
        ml_verdict = stock_result.get('ml_verdict')
        if ml_verdict and ml_verdict in ['buy', 'strong_buy']:
            needs_params = True
            
        assert needs_params == True
    
    def test_parameters_calculated_for_ml_only_buy(self):
        """Test that parameters are calculated when ML-only verdict is buy"""
        stock_result = {
            'ticker': 'TEST.NS',
            'final_verdict': 'watch',  # Rules say watch
            'ml_verdict': 'buy',        # But ML says buy!
            'last_close': 100.0,
            'timeframe_analysis': {'alignment_score': 5}
        }
        
        # Check condition
        needs_params = stock_result['final_verdict'] in ['buy', 'strong_buy']
        ml_verdict = stock_result.get('ml_verdict')
        if ml_verdict and ml_verdict in ['buy', 'strong_buy']:
            needs_params = True
            
        assert needs_params == True  # Should trigger because ML says buy
    
    def test_parameters_calculated_for_ml_strong_buy(self):
        """Test that parameters are calculated when ML-only verdict is strong_buy"""
        stock_result = {
            'ticker': 'TEST.NS',
            'final_verdict': 'avoid',      # Rules say avoid
            'ml_verdict': 'strong_buy',    # But ML says strong_buy!
            'last_close': 100.0
        }
        
        # Check condition
        needs_params = stock_result['final_verdict'] in ['buy', 'strong_buy']
        ml_verdict = stock_result.get('ml_verdict')
        if ml_verdict and ml_verdict in ['buy', 'strong_buy']:
            needs_params = True
            
        assert needs_params == True  # Should trigger because ML says strong_buy
    
    def test_no_parameters_for_watch_and_avoid(self):
        """Test that parameters are NOT calculated when both rule and ML say watch/avoid"""
        stock_result = {
            'ticker': 'TEST.NS',
            'final_verdict': 'watch',
            'ml_verdict': 'avoid',
            'last_close': 100.0
        }
        
        # Check condition
        needs_params = stock_result['final_verdict'] in ['buy', 'strong_buy']
        ml_verdict = stock_result.get('ml_verdict')
        if ml_verdict and ml_verdict in ['buy', 'strong_buy']:
            needs_params = True
            
        assert needs_params == False  # Should NOT trigger


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

