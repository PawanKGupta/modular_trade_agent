#!/usr/bin/env python3
"""
Unit tests for mean reversion labeling logic

Tests that labels are assigned correctly based on profit thresholds:
- strong_buy: profit >= 5%
- buy: profit 1-5%
- watch: profit 0-1%
- avoid: loss < 0%
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


class TestMeanReversionLabeling:
    """Test labeling logic for mean reversion strategy"""
    
    def test_strong_buy_label_for_high_profit(self):
        """Test that profit >= 5% gets strong_buy label"""
        from scripts.collect_training_data import create_labels_from_backtest_results_with_reentry
        
        backtest_results = {
            'ticker': 'TEST.NS',
            'full_results': {
                'positions': [{
                    'entry_date': '2024-01-15',
                    'entry_price': 1000.0,
                    'exit_date': '2024-01-22',
                    'exit_price': 1080.0,
                    'pnl_pct': 8.0,  # >= 5%
                    'exit_reason': 'Target reached',
                    'fills': [{
                        'date': pd.Timestamp('2024-01-15'),
                        'price': 1000.0,
                        'quantity': 50,
                        'capital': 50000
                    }]
                }]
            }
        }
        
        with patch('scripts.collect_training_data.extract_features_at_date') as mock_extract:
            mock_extract.return_value = {
                'rsi_10': 25.0,
                'price_above_ema200': True,
                'ema9_distance_pct': 5.0
            }
            
            labels = create_labels_from_backtest_results_with_reentry(backtest_results)
            
            assert len(labels) == 1
            assert labels[0]['label'] == 'strong_buy'
            assert labels[0]['actual_pnl_pct'] == 8.0
    
    def test_buy_label_for_good_profit(self):
        """Test that profit 1-5% gets buy label"""
        from scripts.collect_training_data import create_labels_from_backtest_results_with_reentry
        
        backtest_results = {
            'ticker': 'TEST.NS',
            'full_results': {
                'positions': [{
                    'entry_date': '2024-01-15',
                    'entry_price': 1000.0,
                    'exit_date': '2024-01-22',
                    'exit_price': 1030.0,
                    'pnl_pct': 3.0,  # 1-5%
                    'exit_reason': 'Target reached',
                    'fills': [{
                        'date': pd.Timestamp('2024-01-15'),
                        'price': 1000.0,
                        'quantity': 50,
                        'capital': 50000
                    }]
                }]
            }
        }
        
        with patch('scripts.collect_training_data.extract_features_at_date') as mock_extract:
            mock_extract.return_value = {'rsi_10': 28.0, 'ema9_distance_pct': 4.0}
            
            labels = create_labels_from_backtest_results_with_reentry(backtest_results)
            
            assert len(labels) == 1
            assert labels[0]['label'] == 'buy'
            assert labels[0]['actual_pnl_pct'] == 3.0
    
    def test_watch_label_for_marginal_profit(self):
        """Test that profit 0-1% gets watch label"""
        from scripts.collect_training_data import create_labels_from_backtest_results_with_reentry
        
        backtest_results = {
            'ticker': 'TEST.NS',
            'full_results': {
                'positions': [{
                    'entry_date': '2024-01-15',
                    'entry_price': 1000.0,
                    'exit_date': '2024-01-22',
                    'exit_price': 1005.0,
                    'pnl_pct': 0.5,  # 0-1%
                    'exit_reason': 'RSI exit',
                    'fills': [{
                        'date': pd.Timestamp('2024-01-15'),
                        'price': 1000.0,
                        'quantity': 50,
                        'capital': 50000
                    }]
                }]
            }
        }
        
        with patch('scripts.collect_training_data.extract_features_at_date') as mock_extract:
            mock_extract.return_value = {'rsi_10': 29.0, 'ema9_distance_pct': 3.0}
            
            labels = create_labels_from_backtest_results_with_reentry(backtest_results)
            
            assert len(labels) == 1
            assert labels[0]['label'] == 'watch'
            assert labels[0]['actual_pnl_pct'] == 0.5
    
    def test_avoid_label_for_loss(self):
        """Test that loss < 0% gets avoid label"""
        from scripts.collect_training_data import create_labels_from_backtest_results_with_reentry
        
        backtest_results = {
            'ticker': 'TEST.NS',
            'full_results': {
                'positions': [{
                    'entry_date': '2024-01-15',
                    'entry_price': 1000.0,
                    'exit_date': '2024-01-22',
                    'exit_price': 980.0,
                    'pnl_pct': -2.0,  # Loss
                    'exit_reason': 'Target reached',
                    'fills': [{
                        'date': pd.Timestamp('2024-01-15'),
                        'price': 1000.0,
                        'quantity': 50,
                        'capital': 50000
                    }]
                }]
            }
        }
        
        with patch('scripts.collect_training_data.extract_features_at_date') as mock_extract:
            mock_extract.return_value = {'rsi_10': 22.0, 'ema9_distance_pct': 8.0}
            
            labels = create_labels_from_backtest_results_with_reentry(backtest_results)
            
            assert len(labels) == 1
            assert labels[0]['label'] == 'avoid'
            assert labels[0]['actual_pnl_pct'] == -2.0
    
    def test_boundary_conditions(self):
        """Test label assignment at exact boundary values"""
        from scripts.collect_training_data import create_labels_from_backtest_results_with_reentry
        
        test_cases = [
            (5.0, 'strong_buy'),   # Exactly 5%
            (4.99, 'buy'),          # Just below 5%
            (1.0, 'buy'),           # Exactly 1%
            (0.99, 'watch'),        # Just below 1%
            (0.0, 'watch'),         # Exactly 0%
            (-0.01, 'avoid'),       # Just below 0%
        ]
        
        for pnl_pct, expected_label in test_cases:
            backtest_results = {
                'ticker': 'TEST.NS',
                'full_results': {
                    'positions': [{
                        'entry_date': '2024-01-15',
                        'entry_price': 1000.0,
                        'exit_date': '2024-01-22',
                        'exit_price': 1000.0 + (1000.0 * pnl_pct / 100),
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'Target reached',
                        'fills': [{
                            'date': pd.Timestamp('2024-01-15'),
                            'price': 1000.0,
                            'quantity': 50,
                            'capital': 50000
                        }]
                    }]
                }
            }
            
            with patch('scripts.collect_training_data.extract_features_at_date') as mock_extract:
                mock_extract.return_value = {'rsi_10': 25.0, 'ema9_distance_pct': 5.0}
                
                labels = create_labels_from_backtest_results_with_reentry(backtest_results)
                
                assert len(labels) == 1, f"Failed for P&L={pnl_pct}%"
                assert labels[0]['label'] == expected_label, \
                    f"P&L={pnl_pct}% should be '{expected_label}', got '{labels[0]['label']}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

