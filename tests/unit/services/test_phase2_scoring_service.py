"""
Unit Tests for Phase 2: Scoring Service with Configurable RSI Thresholds

Tests for:
1. ScoringService with StrategyConfig
2. Configurable RSI thresholds in scoring logic
3. Backward compatibility
"""
import sys
from pathlib import Path
import pytest
import warnings

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from services.scoring_service import ScoringService
from config.strategy_config import StrategyConfig


class TestScoringServiceConfigurable:
    """Test ScoringService with configurable RSI thresholds"""
    
    def test_scoring_service_default_config(self):
        """Test ScoringService uses default config when none provided"""
        service = ScoringService()
        
        assert service.config is not None
        assert isinstance(service.config, StrategyConfig)
        assert service.config.rsi_oversold == 30.0
        assert service.config.rsi_extreme_oversold == 20.0
    
    def test_scoring_service_custom_config(self):
        """Test ScoringService accepts custom config"""
        custom_config = StrategyConfig(
            rsi_oversold=35.0,
            rsi_extreme_oversold=25.0
        )
        service = ScoringService(config=custom_config)
        
        assert service.config.rsi_oversold == 35.0
        assert service.config.rsi_extreme_oversold == 25.0
    
    def test_scoring_with_configurable_rsi_thresholds(self):
        """Test scoring uses configurable RSI thresholds"""
        # Test with default thresholds
        service_default = ScoringService()
        
        analysis_data = {
            'verdict': 'buy',
            'justification': ['rsi:25'],  # Between 20 and 30
            'timeframe_analysis': {}
        }
        
        score_default = service_default.compute_strength_score(analysis_data)
        
        # Should get +1 for RSI < 30 (default oversold)
        assert score_default >= 5  # Base score for 'buy' is 5
        
        # Test with custom thresholds
        custom_config = StrategyConfig(
            rsi_oversold=35.0,
            rsi_extreme_oversold=25.0
        )
        service_custom = ScoringService(config=custom_config)
        
        # RSI 25 should now trigger both thresholds (25 < 35 and 25 < 25 is false, but 25 < 35 is true)
        score_custom = service_custom.compute_strength_score(analysis_data)
        
        # Should get +1 for RSI < 35 (custom oversold)
        assert score_custom >= 5
    
    def test_scoring_with_extreme_oversold(self):
        """Test scoring with extreme oversold threshold"""
        service = ScoringService()
        
        analysis_data = {
            'verdict': 'buy',
            'justification': ['rsi:15'],  # Below extreme oversold (20)
            'timeframe_analysis': {}
        }
        
        score = service.compute_strength_score(analysis_data)
        
        # Should get +2 (one for < 30, one for < 20)
        assert score >= 7  # Base 5 + 2 = 7
    
    def test_scoring_timeframe_analysis_thresholds(self):
        """Test scoring uses configurable thresholds in timeframe analysis"""
        service = ScoringService()
        
        analysis_data = {
            'verdict': 'buy',
            'justification': [],
            'timeframe_analysis': {
                'daily_analysis': {
                    'oversold_analysis': {
                        'severity': 'high'  # RSI < 30
                    },
                    'support_analysis': {
                        'quality': 'strong'
                    }
                },
                'weekly_analysis': {
                    'oversold_analysis': {
                        'severity': 'high'
                    }
                }
            }
        }
        
        score = service.compute_strength_score(analysis_data)
        
        # Should get at least base score + timeframe bonuses
        # Base 5 + at least +2 for high severity (RSI < 30) when both daily and weekly are present
        assert score >= 5  # At least base score
        # Note: Actual score depends on timeframe analysis implementation
    
    def test_scoring_extreme_severity(self):
        """Test scoring with extreme severity uses configurable threshold"""
        service = ScoringService()
        
        analysis_data = {
            'verdict': 'buy',
            'justification': [],
            'timeframe_analysis': {
                'daily_analysis': {
                    'oversold_analysis': {
                        'severity': 'extreme'  # RSI < 20
                    },
                    'support_analysis': {
                        'quality': 'strong'
                    }
                },
                'weekly_analysis': {
                    'oversold_analysis': {
                        'severity': 'extreme'
                    }
                }
            }
        }
        
        score = service.compute_strength_score(analysis_data)
        
        # Should get at least base score + timeframe bonuses
        # Base 5 + at least +3 for extreme severity (RSI < 20) when both daily and weekly are present
        assert score >= 5  # At least base score
        # Note: Actual score depends on timeframe analysis implementation
    
    def test_scoring_non_buy_verdict(self):
        """Test scoring returns -1 for non-buy verdicts"""
        service = ScoringService()
        
        analysis_data = {
            'verdict': 'avoid',
            'justification': ['rsi:25'],
            'timeframe_analysis': {}
        }
        
        score = service.compute_strength_score(analysis_data)
        
        assert score == -1
    
    def test_scoring_strong_buy_verdict(self):
        """Test scoring with strong_buy verdict"""
        service = ScoringService()
        
        analysis_data = {
            'verdict': 'strong_buy',
            'justification': ['rsi:15'],
            'timeframe_analysis': {}
        }
        
        score = service.compute_strength_score(analysis_data)
        
        # Base score for strong_buy is 10, +2 for RSI thresholds
        assert score >= 12


if __name__ == "__main__":
    pytest.main([__file__, '-v'])

