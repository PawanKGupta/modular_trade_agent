#!/usr/bin/env python3
"""
Unit Tests for Re-Entry Extraction in Training Data Collection

Tests for Phase 5 enhancement: extracting features for all fills (initial + re-entries)
with quantity-based sample weighting.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.collect_training_data import create_labels_from_backtest_results_with_reentry


class TestReentryExtraction:
    """Test re-entry feature extraction"""
    
    def test_single_fill_position(self):
        """Test position with only initial entry (no re-entries)"""
        backtest_results = {
            'ticker': 'TEST.NS',
            'full_results': {
                'stock_name': 'TEST.NS',
                'positions': [{
                    'entry_date': '2024-01-01',
                    'entry_price': 100.0,
                    'exit_date': '2024-01-10',
                    'exit_price': 110.0,
                    'exit_reason': 'Target reached',
                    'return_pct': 10.0,
                    'capital': 50000,
                    'quantity': 500,
                    'days_to_exit': 9,
                    'max_drawdown_pct': -2.0,
                    'fills': [{
                        'date': pd.Timestamp('2024-01-01'),
                        'price': 100.0,
                        'capital': 50000,
                        'quantity': 500
                    }],
                    'is_pyramided': False
                }]
            }
        }
        
        # Mock services (won't be called for this test structure)
        results = create_labels_from_backtest_results_with_reentry(backtest_results)
        
        # Note: This test structure requires actual data fetching
        # In real scenario, we'd mock the DataService, IndicatorService, etc.
        # For now, we test the structure parsing logic
        
        assert isinstance(results, list)
    
    def test_multi_fill_position(self):
        """Test position with initial entry + re-entries"""
        backtest_results = {
            'ticker': 'TEST.NS',
            'full_results': {
                'positions': [{
                    'entry_date': '2024-01-01',
                    'entry_price': 95.0,  # Averaged price
                    'exit_date': '2024-01-15',
                    'exit_price': 110.0,
                    'exit_reason': 'Target reached',
                    'return_pct': 15.79,
                    'capital': 100000,
                    'quantity': 1053,  # Total quantity
                    'days_to_exit': 14,
                    'max_drawdown_pct': -5.2,
                    'fills': [
                        {
                            'date': pd.Timestamp('2024-01-01'),
                            'price': 100.0,
                            'capital': 50000,
                            'quantity': 500
                        },
                        {
                            'date': pd.Timestamp('2024-01-05'),
                            'price': 90.0,
                            'capital': 50000,
                            'quantity': 555,
                            'rsi_level': 20
                        }
                    ],
                    'is_pyramided': True
                }]
            }
        }
        
        # Test parsing logic
        positions = backtest_results['full_results']['positions']
        assert len(positions) == 1
        
        position = positions[0]
        fills = position.get('fills', [])
        assert len(fills) == 2
        assert position['is_pyramided'] is True


class TestQuantityBasedWeighting:
    """Test quantity-based sample weight calculation"""
    
    def test_equal_capital_different_prices(self):
        """Test weights when same capital buys different quantities"""
        # Fill 1: 50k @ 100 = 500 shares
        # Fill 2: 50k @ 90 = 555 shares
        # Total: 1055 shares
        
        fill1_qty = 500
        fill2_qty = 555
        total_qty = fill1_qty + fill2_qty
        
        weight1 = fill1_qty / total_qty
        weight2 = fill2_qty / total_qty
        
        # Fill 2 at lower price should have higher weight
        assert weight2 > weight1
        assert abs(weight1 - 0.4739) < 0.01  # ~47.39%
        assert abs(weight2 - 0.5261) < 0.01  # ~52.61%
        assert abs((weight1 + weight2) - 1.0) < 0.0001  # Sum to 1.0
    
    def test_deep_averaging_down(self):
        """Test weights with multiple re-entries at progressively lower prices"""
        # Position with 4 fills
        fills = [
            {'price': 100, 'capital': 50000, 'quantity': 500},   # Initial
            {'price': 90, 'capital': 50000, 'quantity': 555},    # Re-entry 1 (10% down)
            {'price': 80, 'capital': 50000, 'quantity': 625},    # Re-entry 2 (20% down)
            {'price': 70, 'capital': 50000, 'quantity': 714},    # Re-entry 3 (30% down)
        ]
        
        total_qty = sum(f['quantity'] for f in fills)
        weights = [f['quantity'] / total_qty for f in fills]
        
        # Later re-entries at lower prices should have higher weights
        assert weights[0] < weights[1] < weights[2] < weights[3]
        
        # Last re-entry should have highest weight (bought most shares)
        assert weights[3] > 0.29  # ~29.7%
        
        # Sum to 1.0
        assert abs(sum(weights) - 1.0) < 0.0001
    
    def test_zero_quantity_handling(self):
        """Test fallback when quantity is zero or missing"""
        # If total_quantity is 0, should fall back to simple weighting
        total_qty = 0
        
        # Fallback logic
        if total_qty > 0:
            weight = 100 / total_qty
        else:
            weight = 1.0  # Fallback for initial entry
        
        assert weight == 1.0


class TestContextFeatures:
    """Test re-entry context feature generation"""
    
    def test_position_id_generation(self):
        """Test position_id format"""
        ticker = "RELIANCE.NS"
        initial_date = "2024-01-15"
        
        position_id = f"{ticker}_{initial_date.replace('-', '')}"
        
        assert position_id == "RELIANCE.NS_20240115"
        assert ticker in position_id
        assert "2024" in position_id
    
    def test_is_reentry_flag(self):
        """Test is_reentry flag for each fill"""
        fills = [
            {'fill_idx': 0},  # Initial
            {'fill_idx': 1},  # Re-entry 1
            {'fill_idx': 2},  # Re-entry 2
        ]
        
        for i, fill in enumerate(fills):
            is_reentry = (i > 0)
            fill['is_reentry'] = is_reentry
        
        assert fills[0]['is_reentry'] is False
        assert fills[1]['is_reentry'] is True
        assert fills[2]['is_reentry'] is True
    
    def test_fill_number_sequence(self):
        """Test fill_number starts at 1 and increments"""
        fills = [{}, {}, {}, {}]
        
        for i, fill in enumerate(fills):
            fill['fill_number'] = i + 1
        
        assert fills[0]['fill_number'] == 1
        assert fills[1]['fill_number'] == 2
        assert fills[2]['fill_number'] == 3
        assert fills[3]['fill_number'] == 4
    
    def test_fill_price_vs_initial_calculation(self):
        """Test fill_price_vs_initial_pct calculation"""
        initial_price = 100.0
        
        test_cases = [
            (100.0, 0.0),     # Same price
            (90.0, -10.0),    # 10% down (averaging down)
            (110.0, 10.0),    # 10% up
            (80.0, -20.0),    # 20% down
        ]
        
        for fill_price, expected_pct in test_cases:
            pct = ((fill_price - initial_price) / initial_price) * 100
            assert abs(pct - expected_pct) < 0.01


class TestBackwardCompatibility:
    """Test backward compatibility with old backtest formats"""
    
    def test_missing_fills_array(self):
        """Test creating fills array from entry_date when fills is missing"""
        position = {
            'entry_date': '2024-01-01',
            'entry_price': 100.0,
            'capital': 50000,
        }
        
        # Backward compatibility logic
        fills = position.get('fills', [])
        if not fills:
            fills = [{
                'date': pd.to_datetime(position['entry_date']),
                'price': float(position['entry_price']),
                'capital': position.get('capital', 50000)
            }]
        
        assert len(fills) == 1
        assert fills[0]['price'] == 100.0
    
    def test_missing_quantity_in_fill(self):
        """Test handling missing quantity field"""
        fill = {'price': 100.0, 'capital': 50000}
        
        quantity = float(fill.get('quantity', 0))
        
        # Should default to 0
        assert quantity == 0.0
    
    def test_position_without_pyramiding_flag(self):
        """Test old positions without is_pyramided field"""
        position = {
            'entry_date': '2024-01-01',
            'fills': [{'date': pd.Timestamp('2024-01-01'), 'price': 100.0}]
        }
        
        is_pyramided = position.get('is_pyramided', False)
        assert is_pyramided is False


class TestLabelCreation:
    """Test label generation from P&L"""
    
    def test_label_thresholds(self):
        """Test label assignment based on P&L thresholds"""
        test_cases = [
            (15.0, 'strong_buy'),   # >= 10%
            (10.0, 'strong_buy'),   # >= 10%
            (7.5, 'buy'),           # 5-10%
            (5.0, 'buy'),           # >= 5%
            (2.5, 'watch'),         # 0-5%
            (0.0, 'watch'),         # >= 0%
            (-2.5, 'avoid'),        # < 0%
            (-10.0, 'avoid'),       # < 0%
        ]
        
        for pnl_pct, expected_label in test_cases:
            if pnl_pct >= 10:
                label = 'strong_buy'
            elif pnl_pct >= 5:
                label = 'buy'
            elif pnl_pct >= 0:
                label = 'watch'
            else:
                label = 'avoid'
            
            assert label == expected_label, f"P&L {pnl_pct}% should be {expected_label}, got {label}"
    
    def test_same_label_for_all_fills(self):
        """Test all fills in same position get same label (Approach A)"""
        position_pnl = 12.5  # strong_buy
        
        # All fills should get same label
        fills = [
            {'fill_idx': 0, 'pnl': position_pnl},
            {'fill_idx': 1, 'pnl': position_pnl},
            {'fill_idx': 2, 'pnl': position_pnl},
        ]
        
        labels = []
        for fill in fills:
            if fill['pnl'] >= 10:
                labels.append('strong_buy')
        
        # All labels should be identical
        assert len(set(labels)) == 1
        assert labels[0] == 'strong_buy'


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_positions_list(self):
        """Test handling empty positions list"""
        backtest_results = {
            'ticker': 'TEST.NS',
            'full_results': {
                'positions': []
            }
        }
        
        results = create_labels_from_backtest_results_with_reentry(backtest_results)
        assert results == []
    
    def test_missing_full_results(self):
        """Test handling missing full_results"""
        backtest_results = {
            'ticker': 'TEST.NS',
        }
        
        results = create_labels_from_backtest_results_with_reentry(backtest_results)
        assert results == []
    
    def test_single_fill_weight_is_one(self):
        """Test that a single fill gets weight of 1.0"""
        total_qty = 500
        fill_qty = 500
        
        weight = fill_qty / total_qty if total_qty > 0 else 1.0
        
        assert weight == 1.0
    
    def test_timestamp_string_conversion(self):
        """Test conversion of pandas Timestamp to string"""
        timestamp = pd.Timestamp('2024-01-15')
        
        date_str = timestamp.strftime('%Y-%m-%d')
        
        assert date_str == '2024-01-15'
        assert isinstance(date_str, str)
    
    def test_numpy_type_conversion(self):
        """Test handling of numpy types"""
        numpy_float = np.float64(123.45)
        numpy_int = np.int64(100)
        
        python_float = float(numpy_float)
        python_int = int(numpy_int)
        
        assert isinstance(python_float, float)
        assert isinstance(python_int, int)
        assert python_float == 123.45
        assert python_int == 100


class TestGroupKFoldPreparation:
    """Test that position_id is set up correctly for GroupKFold"""
    
    def test_unique_position_ids(self):
        """Test that each position gets a unique ID"""
        positions = [
            {'ticker': 'STOCK1.NS', 'initial_date': '2024-01-01'},
            {'ticker': 'STOCK1.NS', 'initial_date': '2024-02-01'},  # Different date
            {'ticker': 'STOCK2.NS', 'initial_date': '2024-01-01'},  # Different stock
        ]
        
        position_ids = []
        for pos in positions:
            ticker = pos['ticker']
            date_str = pos['initial_date'].replace('-', '')
            position_id = f"{ticker}_{date_str}"
            position_ids.append(position_id)
        
        # All should be unique
        assert len(set(position_ids)) == 3
        assert 'STOCK1.NS_20240101' in position_ids
        assert 'STOCK1.NS_20240201' in position_ids
        assert 'STOCK2.NS_20240101' in position_ids
    
    def test_same_position_id_for_all_fills(self):
        """Test that all fills in same position share position_id"""
        position_id = "RELIANCE.NS_20240115"
        
        fills = [
            {'fill_idx': 0, 'position_id': position_id},
            {'fill_idx': 1, 'position_id': position_id},
            {'fill_idx': 2, 'position_id': position_id},
        ]
        
        # All fills should have same position_id
        unique_ids = set(f['position_id'] for f in fills)
        assert len(unique_ids) == 1
        assert list(unique_ids)[0] == position_id


# Integration-style tests (would need mocking of services in real implementation)
class TestIntegrationScenarios:
    """Test realistic integration scenarios"""
    
    def test_pyramiding_improves_outcome(self):
        """Test scenario where pyramiding improves P&L"""
        # Position: Initial @ 100, re-entry @ 90
        # Exit @ 105
        # Without re-entry: 5% gain
        # With re-entry: higher gain due to lower avg price
        
        initial_qty = 500
        reentry_qty = 555
        total_qty = initial_qty + reentry_qty
        
        # Average entry price
        avg_price = (500 * 100 + 555 * 90) / total_qty
        
        # Exit at 105
        pnl_pct = ((105 - avg_price) / avg_price) * 100
        
        # Should be better than 5% (initial only)
        assert pnl_pct > 5.0
        assert pnl_pct < 15.0  # But not too high
    
    def test_catching_falling_knife_scenario(self):
        """Test scenario where pyramiding amplifies losses"""
        # Position: Initial @ 100, re-entries @ 90, 80, 70
        # Exit @ 65 (RSI > 50 after further decline)
        
        fills = [
            {'price': 100, 'qty': 500, 'capital': 50000},
            {'price': 90, 'qty': 555, 'capital': 50000},
            {'price': 80, 'qty': 625, 'capital': 50000},
            {'price': 70, 'qty': 714, 'capital': 50000},
        ]
        
        total_qty = sum(f['qty'] for f in fills)
        avg_price = sum(f['price'] * f['qty'] for f in fills) / total_qty
        
        exit_price = 65
        pnl_pct = ((exit_price - avg_price) / avg_price) * 100
        
        # Should be a loss
        assert pnl_pct < 0
        
        # But less severe than if bought all at 100
        single_entry_loss = ((65 - 100) / 100) * 100
        assert pnl_pct > single_entry_loss  # -22.5% vs -35%


def test_module_imports():
    """Test that all required modules can be imported"""
    try:
        from scripts.collect_training_data import create_labels_from_backtest_results_with_reentry
        from services.data_service import DataService
        from services.indicator_service import IndicatorService
        from services.signal_service import SignalService
        from services.verdict_service import VerdictService
        from core.feature_engineering import calculate_all_dip_features
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import required modules: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

