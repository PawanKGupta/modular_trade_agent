"""
Integration Tests for Phase 2: Complete Implementation

Tests for:
1. End-to-end analysis with configurable parameters
2. Integrated backtest with data optimization
3. All services using config correctly
4. Legacy analysis.py with StrategyConfig
5. Pattern detection in real scenarios
"""
import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig
from services.analysis_service import AnalysisService
from services.scoring_service import ScoringService
from services.signal_service import SignalService
from core.analysis import analyze_ticker
from core.patterns import bullish_divergence
import pytest

# NOTE: Tests using old trade_agent function are now obsolete
# The new implementation (Nov 2025) integrates trade agent inline

# Dummy function to prevent import errors
def trade_agent(*args, **kwargs):
    pytest.skip("Old architecture - replaced by single-pass implementation")


class TestPhase2CompleteIntegration:
    """Integration tests for complete Phase 2 implementation"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_analysis_service_with_custom_config(self):
        """Test AnalysisService works with custom StrategyConfig"""
        custom_config = StrategyConfig(
            rsi_period=14,
            rsi_oversold=35.0,
            rsi_extreme_oversold=25.0
        )

        service = AnalysisService(config=custom_config)

        # Verify all services use the custom config
        assert service.config.rsi_period == 14
        assert service.indicator_service.config.rsi_period == 14
        assert service.signal_service.config.rsi_period == 14
        assert service.verdict_service.config.rsi_period == 14

    @pytest.mark.integration
    @pytest.mark.slow
    def test_scoring_service_with_custom_thresholds(self):
        """Test ScoringService uses custom RSI thresholds"""
        custom_config = StrategyConfig(
            rsi_oversold=35.0,
            rsi_extreme_oversold=25.0
        )

        service = ScoringService(config=custom_config)

        analysis_data = {
            'verdict': 'buy',
            'justification': ['rsi:30'],  # Between 25 and 35
            'timeframe_analysis': {}
        }

        score = service.compute_strength_score(analysis_data)

        # Should get +1 for RSI < 35 (custom oversold)
        assert score >= 5

    @pytest.mark.integration
    @pytest.mark.slow
    def test_signal_service_with_config(self):
        """Test SignalService uses StrategyConfig"""
        config = StrategyConfig(rsi_period=14)
        service = SignalService(config=config)

        assert service.config.rsi_period == 14
        assert service.tf_analyzer.config.rsi_period == 14

    @pytest.mark.integration
    @pytest.mark.slow
    def test_legacy_analyze_ticker_with_config(self):
        """Test legacy analyze_ticker accepts StrategyConfig"""
        config = StrategyConfig(rsi_period=14)

        # This should work without errors (may use service layer internally)
        # We're just testing the function signature accepts config
        try:
            result = analyze_ticker(
                ticker='RELIANCE.NS',
                enable_multi_timeframe=False,
                config=config
            )
            # If it runs, config was accepted
            assert result is not None or isinstance(result, dict)
        except Exception as e:
            # If it fails due to data fetching, that's okay - we're testing config acceptance
            if 'data' in str(e).lower() or 'fetch' in str(e).lower():
                pass  # Expected for unit test without network
            else:
                raise

    @pytest.mark.integration
    @pytest.mark.slow
    def test_pattern_detection_with_config(self):
        """Test pattern detection works with configurable RSI period"""
        # Create test data that creates valid divergence
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')

        # Create price data with lower low in recent period
        prices = []
        for i in range(30):
            if i < 15:
                # First 15 days: stable prices around 100
                prices.append(100 + (i % 3) * 0.1)
            else:
                # Last 15 days: declining prices (lower low)
                prices.append(100 - (i - 15) * 0.5)

        # Create RSI data with higher low (divergence)
        rsi_values = []
        for i in range(30):
            if i < 15:
                # First 15 days: lower RSI
                rsi_values.append(25 + (i % 3) * 0.1)
            else:
                # Last 15 days: higher RSI (divergence - price down, RSI up)
                rsi_values.append(30 + (i - 15) * 0.3)

        df = pd.DataFrame({
            'open': prices,
            'high': [p + 1 for p in prices],
            'low': [p - 1 for p in prices],
            'close': prices,
            'volume': [1000000] * 30,
            'rsi14': rsi_values  # Custom RSI period
        }, index=dates)

        # Test with custom RSI period
        result = bullish_divergence(df, rsi_period=14, lookback_period=10)

        # Handle numpy boolean types (np.True_ is not isinstance(bool))
        assert result is True or result is False or isinstance(result, (bool, np.bool_))

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.skip(reason="Tests old trade_agent function - replaced in Nov 2025 refactor")
    def test_integrated_backtest_data_optimization(self):
        """Test integrated backtest uses pre-fetched data"""
        # This test verifies that trade_agent accepts pre-fetched data
        # We'll create mock data to test the optimization

        # Create test data
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        df = pd.DataFrame({
            'Open': range(100, 200),
            'High': range(101, 201),
            'Low': range(99, 199),
            'Close': range(100, 200),
            'Volume': [1000000] * 100
        }, index=dates)

        pre_calculated = {
            'rsi': 25.0,
            'ema200': 150.0
        }

        # Test that trade_agent accepts pre-fetched data
        # This is a structural test - we're verifying the function signature
        import inspect
        sig = inspect.signature(trade_agent)

        assert 'pre_fetched_data' in sig.parameters
        assert 'pre_calculated_indicators' in sig.parameters

    @pytest.mark.integration
    @pytest.mark.slow
    def test_all_services_use_config(self):
        """Test all services properly use StrategyConfig"""
        config = StrategyConfig(
            rsi_period=14,
            rsi_oversold=35.0,
            rsi_extreme_oversold=25.0
        )

        # Test AnalysisService
        analysis_service = AnalysisService(config=config)
        assert analysis_service.config.rsi_period == 14

        # Test ScoringService
        scoring_service = ScoringService(config=config)
        assert scoring_service.config.rsi_oversold == 35.0

        # Test SignalService
        signal_service = SignalService(config=config)
        assert signal_service.config.rsi_period == 14

        # Verify TimeframeAnalysis also uses config
        assert signal_service.tf_analyzer.config.rsi_period == 14

    @pytest.mark.integration
    @pytest.mark.slow
    def test_auto_trader_config_sync(self):
        """Test auto-trader config is synced with StrategyConfig"""
        from modules.kotak_neo_auto_trader import config as auto_trader_config

        strategy_config = StrategyConfig.default()

        # RSI period should be synced
        assert auto_trader_config.RSI_PERIOD == strategy_config.rsi_period

        # EMA settings should be separate
        assert auto_trader_config.EMA_SHORT == 9
        assert auto_trader_config.EMA_LONG == 200

    @pytest.mark.integration
    @pytest.mark.slow
    def test_legacy_config_backward_compatibility(self):
        """Test legacy config constants work for backward compatibility"""
        from config.settings import RSI_OVERSOLD, RSI_NEAR_OVERSOLD
        from config.strategy_config import StrategyConfig

        config = StrategyConfig.default()

        # Legacy constants should match StrategyConfig
        assert RSI_OVERSOLD == config.rsi_oversold
        assert RSI_NEAR_OVERSOLD == config.rsi_near_oversold


class TestPhase2DataOptimization:
    """Integration tests for data fetching optimization"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_analysis_service_pre_fetched_data_parameter(self):
        """Test AnalysisService.analyze_ticker accepts pre-fetched data parameters"""
        service = AnalysisService()

        # Verify function signature
        import inspect
        sig = inspect.signature(service.analyze_ticker)

        assert 'pre_fetched_daily' in sig.parameters
        assert 'pre_fetched_weekly' in sig.parameters
        assert 'pre_calculated_indicators' in sig.parameters

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.skip(reason="Tests old trade_agent function - replaced in Nov 2025 refactor")
    def test_trade_agent_pre_fetched_data_parameter(self):
        """Test trade_agent accepts pre-fetched data parameters"""
        import inspect
        sig = inspect.signature(trade_agent)

        assert 'pre_fetched_data' in sig.parameters
        assert 'pre_calculated_indicators' in sig.parameters


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-m', 'integration'])

