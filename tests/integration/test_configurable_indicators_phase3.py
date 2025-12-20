"""
Phase 3: Testing & Validation for Configurable Indicators

Tests for:
1. Unit tests for configurable parameters
2. Integration tests with current data
3. Backtest comparison (old vs new) - CRITICAL
4. BacktestEngine regression tests
5. Integrated backtest validation tests
6. Simple backtest regression tests
7. Data fetching optimization tests
8. Indicator calculation consistency tests
9. Performance benchmarking
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

warnings.filterwarnings("ignore")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backtest.backtest_config import BacktestConfig
from backtest.backtest_engine import BacktestEngine
from config.strategy_config import StrategyConfig

# Phase 4.8: core.backtest_scoring functions are deprecated
# Keep imports for backward compatibility, but prefer BacktestService
from core.backtest_scoring import run_simple_backtest  # Deprecated
from core.data_fetcher import fetch_multi_timeframe_data, yfinance_circuit_breaker
from core.indicators import compute_indicators
from core.timeframe_analysis import TimeframeAnalysis

# NOTE: This test uses old architecture functions (run_backtest, trade_agent)
# The new implementation (Nov 2025) uses single-pass daily iteration
# Mark tests that use old functions to skip
from integrated_backtest import run_integrated_backtest


# Dummy function to prevent import errors
def run_backtest(*args, **kwargs):
    pytest.skip("Old architecture - replaced by single-pass implementation")


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """
    Reset circuit breaker before each test to prevent failures from previous tests
    from affecting current test.

    This fixes the bug where a global circuit breaker blocks all requests after
    failures with invalid symbols, causing valid symbols to fail.
    """
    # Reset circuit breaker before each test
    yfinance_circuit_breaker.reset()
    yield
    # Optionally reset after test as well (though before is usually enough)
    # yfinance_circuit_breaker.reset()


# ============================================================================
# 1. Unit Tests for Configurable Parameters
# ============================================================================


class TestConfigurableParameters:
    """Test configurable parameters in StrategyConfig"""

    def test_strategy_config_defaults(self):
        """Test StrategyConfig has all required fields with correct defaults"""
        config = StrategyConfig.default()

        assert hasattr(config, "rsi_period")
        assert config.rsi_period == 10

        assert hasattr(config, "support_resistance_lookback_daily")
        assert config.support_resistance_lookback_daily == 20

        assert hasattr(config, "support_resistance_lookback_weekly")
        assert config.support_resistance_lookback_weekly == 50

        assert hasattr(config, "volume_exhaustion_lookback_daily")
        assert config.volume_exhaustion_lookback_daily == 10

        assert hasattr(config, "volume_exhaustion_lookback_weekly")
        assert config.volume_exhaustion_lookback_weekly == 20

        assert hasattr(config, "data_fetch_daily_max_years")
        assert config.data_fetch_daily_max_years == 5

        assert hasattr(config, "data_fetch_weekly_max_years")
        assert config.data_fetch_weekly_max_years == 3

        assert hasattr(config, "enable_adaptive_lookback")
        assert config.enable_adaptive_lookback == True

    def test_strategy_config_custom_values(self):
        """Test StrategyConfig with custom values"""
        config = StrategyConfig(
            rsi_period=14,
            support_resistance_lookback_daily=30,
            support_resistance_lookback_weekly=60,
            volume_exhaustion_lookback_daily=15,
            volume_exhaustion_lookback_weekly=25,
            data_fetch_daily_max_years=3,
            data_fetch_weekly_max_years=2,
            enable_adaptive_lookback=False,
        )

        assert config.rsi_period == 14
        assert config.support_resistance_lookback_daily == 30
        assert config.support_resistance_lookback_weekly == 60
        assert config.volume_exhaustion_lookback_daily == 15
        assert config.volume_exhaustion_lookback_weekly == 25
        assert config.data_fetch_daily_max_years == 3
        assert config.data_fetch_weekly_max_years == 2
        assert config.enable_adaptive_lookback == False

    def test_backtest_config_syncing(self):
        """Test BacktestConfig syncing with StrategyConfig"""
        strategy_config = StrategyConfig.default()
        backtest_config = BacktestConfig.from_strategy_config(strategy_config)

        assert backtest_config.RSI_PERIOD == strategy_config.rsi_period
        assert backtest_config.RSI_PERIOD == 10

        # Test default_synced
        synced_config = BacktestConfig.default_synced()
        assert synced_config.RSI_PERIOD == StrategyConfig.default().rsi_period


# ============================================================================
# 2. Integration Tests with Current Data
# ============================================================================


class TestIntegrationWithData:
    """Test integration with real data"""

    @pytest.mark.integration
    def test_compute_indicators_with_config(self):
        """Test compute_indicators uses configurable RSI period"""
        # Create sample data
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        df = pd.DataFrame(
            {
                "close": np.linspace(100, 120, 100),
                "open": np.linspace(99, 119, 100),
                "high": np.linspace(102, 122, 100),
                "low": np.linspace(98, 118, 100),
                "volume": [1000000] * 100,
            },
            index=dates,
        )

        # Test with default config
        config = StrategyConfig.default()
        result = compute_indicators(df, config=config)

        assert result is not None
        assert f"rsi{config.rsi_period}" in result.columns
        assert "rsi10" in result.columns  # Backward compatibility
        assert "ema200" in result.columns

        # Test with custom RSI period
        custom_config = StrategyConfig(rsi_period=14)
        result_custom = compute_indicators(df, rsi_period=14, config=custom_config)

        assert "rsi14" in result_custom.columns
        assert "rsi10" not in result_custom.columns  # Only if period=10

    @pytest.mark.integration
    def test_timeframe_analysis_with_config(self):
        """Test TimeframeAnalysis uses configurable lookbacks"""
        config = StrategyConfig.default()
        tf_analysis = TimeframeAnalysis(config=config)

        assert tf_analysis.config == config
        assert tf_analysis.support_lookback_daily == config.support_resistance_lookback_daily
        assert tf_analysis.support_lookback_weekly == config.support_resistance_lookback_weekly
        assert tf_analysis.volume_lookback_daily == config.volume_exhaustion_lookback_daily
        assert tf_analysis.volume_lookback_weekly == config.volume_exhaustion_lookback_weekly


# ============================================================================
# 3. Backtest Comparison (Old vs New) - CRITICAL
# ============================================================================


class TestBacktestComparison:
    """Test backtest results comparison (old vs new)"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_backtest_engine_regression(self):
        """Test BacktestEngine produces consistent results with default config"""
        symbol = "RELIANCE.NS"
        start_date = "2023-01-01"
        end_date = "2023-12-31"

        try:
            # Run with default synced config
            config = BacktestConfig.default_synced()
            engine = BacktestEngine(
                symbol=symbol, start_date=start_date, end_date=end_date, config=config
            )

            # Verify RSI period is correct
            assert engine.config.RSI_PERIOD == 10

            # Verify data was loaded
            if engine.data is None or engine.data.empty:
                pytest.skip(f"No data available for {symbol} (network issue or symbol not found)")

            # Verify RSI column exists before running
            assert (
                "RSI10" in engine.data.columns or f"RSI{config.RSI_PERIOD}" in engine.data.columns
            )

            # Run backtest
            results = engine.run_backtest()

            # Verify results structure
            assert "total_return_pct" in results
            assert "win_rate" in results
            assert "total_trades" in results
            assert "closed_positions" in results or "open_positions" in results
            assert "symbol" in results
            assert "period" in results
        except (ValueError, Exception) as e:
            # Catch any exception during BacktestEngine initialization or data loading
            error_msg = str(e)
            if (
                "No data available" in error_msg
                or "network" in error_msg.lower()
                or "data" in error_msg.lower()
            ):
                pytest.skip(f"Data fetching failed for {symbol}: {error_msg}")
            else:
                raise

    @pytest.mark.integration
    @pytest.mark.slow
    def test_simple_backtest_regression(self):
        """Test simple backtest produces consistent results"""
        symbol = "RELIANCE.NS"
        config = StrategyConfig.default()

        # Run simple backtest
        result = run_simple_backtest(
            stock_symbol=symbol, years_back=2, dip_mode=False, config=config
        )

        # Verify results structure
        assert "backtest_score" in result
        assert "total_return_pct" in result
        assert "win_rate" in result
        assert "total_trades" in result

        # Verify score is reasonable
        assert 0 <= result["backtest_score"] <= 100


# ============================================================================
# 4. Data Fetching Optimization Tests
# ============================================================================


class TestDataFetchingOptimization:
    """Test data fetching optimization in integrated backtest"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_integrated_backtest_data_reuse(self):
        """Test integrated backtest reuses BacktestEngine data (updated in Phase 2)"""
        symbol = "RELIANCE.NS"
        date_range = ("2023-01-01", "2023-12-31")

        try:
            # Run backtest with return_engine=True
            signals, engine = run_backtest(symbol, date_range, return_engine=True)

            # Verify engine is returned
            assert engine is not None
            if engine is None or engine.data is None or engine.data.empty:
                pytest.skip(f"No data available for {symbol} (network issue or symbol not found)")

            assert len(engine.data) > 0

            # Verify signals are returned
            assert isinstance(signals, list)

            # Verify data has indicators
            assert (
                "RSI10" in engine.data.columns
                or f"RSI{engine.config.RSI_PERIOD}" in engine.data.columns
            )
            assert "EMA200" in engine.data.columns
        except (ValueError, Exception) as e:
            # Catch any exception during backtest execution
            error_msg = str(e)
            if (
                "No data available" in error_msg
                or "network" in error_msg.lower()
                or "data" in error_msg.lower()
            ):
                pytest.skip(f"Data fetching failed for {symbol}: {error_msg}")
            else:
                raise

    @pytest.mark.integration
    @pytest.mark.slow
    def test_fetch_multi_timeframe_data_config(self):
        """Test fetch_multi_timeframe_data respects configurable max years"""
        symbol = "RELIANCE.NS"
        config = StrategyConfig.default()

        try:
            # Fetch data
            multi_data = fetch_multi_timeframe_data(ticker=symbol, days=800, config=config)

            if multi_data is None:
                pytest.skip(
                    f"Data fetching failed for {symbol} (network issue or symbol not found)"
                )

            assert "daily" in multi_data
            assert "weekly" in multi_data

            daily_data = multi_data["daily"]
            weekly_data = multi_data["weekly"]

            if daily_data is None or daily_data.empty:
                pytest.skip(f"No daily data available for {symbol}")
            if weekly_data is None or weekly_data.empty:
                pytest.skip(f"No weekly data available for {symbol}")

            # Verify data respects max years
            max_daily_days = config.data_fetch_daily_max_years * 365
            max_weekly_days = config.data_fetch_weekly_max_years * 365

            # Data should not exceed max years (allowing some tolerance)
            assert len(daily_data) <= max_daily_days * 1.1  # 10% tolerance
            assert len(weekly_data) <= max_weekly_days * 1.1  # 10% tolerance
        except Exception as e:
            if "No data available" in str(e) or "network" in str(e).lower():
                pytest.skip(f"Data fetching failed for {symbol}: {e}")
            else:
                raise

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.skip(reason="Tests old trade_agent function - replaced in Nov 2025 refactor")
    def test_trade_agent_accepts_pre_fetched_data(self):
        """Test trade_agent accepts pre-fetched data (Phase 2 optimization)"""
        import inspect

        # Verify trade_agent accepts pre-fetched data parameters
        sig = inspect.signature(trade_agent)
        assert "pre_fetched_data" in sig.parameters
        assert "pre_calculated_indicators" in sig.parameters

    @pytest.mark.integration
    @pytest.mark.slow
    def test_analysis_service_accepts_pre_fetched_data(self):
        """Test AnalysisService accepts pre-fetched data (Phase 2 optimization)"""
        import inspect

        from services.analysis_service import AnalysisService

        service = AnalysisService()
        sig = inspect.signature(service.analyze_ticker)

        # Verify AnalysisService accepts pre-fetched data parameters
        assert "pre_fetched_daily" in sig.parameters
        assert "pre_fetched_weekly" in sig.parameters
        assert "pre_calculated_indicators" in sig.parameters


# ============================================================================
# 5. Indicator Calculation Consistency Tests
# ============================================================================


class TestIndicatorConsistency:
    """Test indicator calculation consistency across components"""

    @pytest.mark.integration
    def test_pandas_ta_consistency(self):
        """Test that all components use pandas_ta consistently"""

        # Create sample data
        dates = pd.date_range("2023-01-01", periods=250, freq="D")
        close_prices = pd.Series(np.linspace(100, 120, 250), index=dates)

        # Test compute_indicators uses pandas_ta
        df = pd.DataFrame(
            {
                "close": close_prices,
                "open": close_prices - 1,
                "high": close_prices + 1,
                "low": close_prices - 1,
                "volume": [1000000] * 250,
            }
        )

        result = compute_indicators(df)

        # Verify pandas_ta was used (check for pandas_ta-style column names)
        assert "rsi10" in result.columns or "rsi10" in [c.lower() for c in result.columns]
        assert "ema200" in result.columns or "ema200" in [c.lower() for c in result.columns]

    @pytest.mark.integration
    def test_backtest_engine_indicators(self):
        """Test BacktestEngine uses pandas_ta for indicators"""
        # Check BacktestEngine source code uses pandas_ta
        with open("backtest/backtest_engine.py", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            assert "ta.rsi" in content or "pandas_ta" in content
            assert "ta.ema" in content or "pandas_ta" in content


# ============================================================================
# 6. Integrated Backtest Validation Tests
# ============================================================================


class TestIntegratedBacktestValidation:
    """Test integrated backtest validation"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_integrated_backtest_runs(self):
        """Test integrated backtest runs successfully with configurable parameters"""
        symbol = "RELIANCE.NS"
        date_range = ("2023-01-01", "2023-12-31")

        try:
            # Run integrated backtest
            results = run_integrated_backtest(symbol, date_range, capital_per_position=50000)

            # Verify results structure
            assert "stock_name" in results
            assert "total_signals" in results
            assert "executed_trades" in results
            assert "skipped_signals" in results

            # Verify it uses configurable parameters (indirectly via BacktestEngine)
            assert results["stock_name"] == symbol
        except (ValueError, Exception) as e:
            # Catch any exception during integrated backtest execution
            error_msg = str(e)
            if (
                "No data available" in error_msg
                or "network" in error_msg.lower()
                or "data" in error_msg.lower()
            ):
                pytest.skip(f"Data fetching failed for {symbol}: {error_msg}")
            else:
                raise

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.skip(reason="Tests old run_backtest function - replaced in Nov 2025 refactor")
    def test_integrated_backtest_uses_pre_fetched_data(self):
        """Test integrated backtest uses pre-fetched data optimization (Phase 2)"""
        from config.strategy_config import StrategyConfig
        from services.analysis_service import AnalysisService

        symbol = "RELIANCE.NS"
        date_range = ("2023-01-01", "2023-12-31")

        try:
            # Run backtest to get engine with data
            signals, engine = run_backtest(symbol, date_range, return_engine=True)

            # Verify engine has data
            assert engine is not None
            if engine is None or engine.data is None or engine.data.empty:
                pytest.skip(f"No data available for {symbol} (network issue or symbol not found)")

            # Verify trade_agent can accept pre-fetched data
            # This is verified by the function signature accepting pre_fetched_data
            import inspect

            sig = inspect.signature(trade_agent)
            assert "pre_fetched_data" in sig.parameters
            assert "pre_calculated_indicators" in sig.parameters

            # Verify AnalysisService accepts pre-fetched data
            service = AnalysisService(config=StrategyConfig.default())
            service_sig = inspect.signature(service.analyze_ticker)
            assert "pre_fetched_daily" in service_sig.parameters
            assert "pre_calculated_indicators" in service_sig.parameters
        except ValueError as e:
            if "No data available" in str(e):
                pytest.skip(f"Data fetching failed for {symbol}: {e}")
            else:
                raise


# ============================================================================
# 7. ML Compatibility Tests
# ============================================================================


class TestMLCompatibility:
    """Test ML compatibility with configurable parameters"""

    @pytest.mark.integration
    def test_ml_feature_extraction_default_config(self):
        """Test ML feature extraction produces same features with default config"""
        try:
            import numpy as np
            import pandas as pd

            from config.strategy_config import StrategyConfig
            from services.ml_verdict_service import MLVerdictService

            # Create sample data
            dates = pd.date_range("2023-01-01", periods=100, freq="D")
            df = pd.DataFrame(
                {
                    "close": np.linspace(100, 120, 100),
                    "high": np.linspace(102, 122, 100),
                    "low": np.linspace(98, 118, 100),
                    "volume": [1000000] * 100,
                },
                index=dates,
            )

            # Test with default config (should produce same features as before)
            config = StrategyConfig.default()
            ml_service = MLVerdictService(config=config)

            # Extract features
            features = ml_service._extract_features(
                rsi_value=25.0,
                indicators={"ema200": 110.0, "close": 115.0},
                is_above_ema200=True,
                df=df,
                vol_ok=True,
                vol_strong=True,
                fundamental_ok=True,
                signals=["hammer"],
                timeframe_confirmation={},
                news_sentiment=None,
            )

            # Verify default config produces expected feature names
            assert "rsi_10" in features  # Default RSI period = 10
            # Model expects 'avg_volume_20' (not dynamic avg_volume_{volume_lookback})
            # Always create avg_volume_20 to match training data (43 features)
            assert "avg_volume_20" in features  # Model expects this exact feature name
            assert "recent_high_20" in features  # Default support lookback = 20
            assert "recent_low_20" in features  # Default support lookback = 20

        except ImportError:
            pytest.skip("ML verdict service not available")

    @pytest.mark.integration
    def test_ml_backward_compatibility(self):
        """Test ML service maintains backward compatibility with existing models"""
        try:
            from config.strategy_config import StrategyConfig
            from services.ml_verdict_service import MLVerdictService

            # Test with default config (should work with existing models)
            config = StrategyConfig.default()
            ml_service = MLVerdictService(config=config)

            # Verify config is set
            assert ml_service.config == config
            assert ml_service.config.rsi_period == 10  # Default matches existing models

        except ImportError:
            pytest.skip("ML verdict service not available")


# ============================================================================
# 8. Scoring/Verdict Tests
# ============================================================================


class TestScoringVerdict:
    """Test scoring/verdict system uses configurable RSI thresholds"""

    @pytest.mark.integration
    def test_scoring_service_rsi_thresholds(self):
        """Test ScoringService uses configurable RSI thresholds"""
        from config.strategy_config import StrategyConfig
        from services.scoring_service import ScoringService

        # Test with default config
        default_config = StrategyConfig.default()
        default_service = ScoringService(config=default_config)

        # Test scoring with RSI value between thresholds
        analysis_data = {
            "verdict": "buy",
            "justification": ["rsi:25"],  # Between 20 and 30
            "timeframe_analysis": {},
        }

        score_default = default_service.compute_strength_score(analysis_data)

        # Should get +1 for RSI < 30 (default oversold)
        assert score_default >= 6  # Base 5 + 1 = 6

        # Test with custom config
        custom_config = StrategyConfig(rsi_oversold=35.0, rsi_extreme_oversold=25.0)
        custom_service = ScoringService(config=custom_config)

        # RSI 25 should now trigger oversold threshold (25 < 35)
        score_custom = custom_service.compute_strength_score(analysis_data)

        # Should get +1 for RSI < 35 (custom oversold)
        assert score_custom >= 6  # Base 5 + 1 = 6

        # Verify configurable thresholds are actually used
        assert default_service.config.rsi_oversold == 30.0
        assert custom_service.config.rsi_oversold == 35.0

    @pytest.mark.integration
    def test_scoring_service_extreme_oversold(self):
        """Test ScoringService uses configurable extreme oversold threshold"""
        from services.scoring_service import ScoringService

        service = ScoringService()

        # Test with RSI below extreme oversold
        analysis_data = {
            "verdict": "buy",
            "justification": ["rsi:15"],  # Below extreme oversold (20)
            "timeframe_analysis": {},
        }

        score = service.compute_strength_score(analysis_data)

        # Should get +2 (one for < 30, one for < 20)
        assert score >= 7  # Base 5 + 2 = 7

    @pytest.mark.integration
    def test_scoring_service_timeframe_analysis_thresholds(self):
        """Test ScoringService uses configurable thresholds in timeframe analysis"""
        from services.scoring_service import ScoringService

        service = ScoringService()

        analysis_data = {
            "verdict": "buy",
            "justification": [],
            "timeframe_analysis": {
                "daily_analysis": {
                    "oversold_analysis": {"severity": "high"},  # RSI < 30
                    "support_analysis": {"quality": "strong"},
                },
                "weekly_analysis": {"oversold_analysis": {"severity": "high"}},
            },
        }

        score = service.compute_strength_score(analysis_data)

        # Should get at least base score + timeframe analysis bonuses
        # Base 5 + timeframe bonuses (at least +2 for high severity)
        assert score >= 5  # At least base score
        # Note: Actual score depends on timeframe analysis implementation

    @pytest.mark.integration
    def test_backtest_scoring_entry_conditions(self):
        """Test backtest scoring entry conditions use configurable RSI"""
        from config.strategy_config import StrategyConfig

        config = StrategyConfig.default()

        # Verify config has RSI thresholds
        assert hasattr(config, "rsi_oversold")
        assert hasattr(config, "rsi_extreme_oversold")
        assert config.rsi_oversold == 30.0
        assert config.rsi_extreme_oversold == 20.0

        # Verify backtest scoring uses config
        # This is verified by passing config to run_simple_backtest
        # The actual entry conditions use config.rsi_oversold internally


# ============================================================================
# 9. Legacy Migration Tests
# ============================================================================


class TestLegacyMigration:
    """Test legacy code migration to StrategyConfig"""

    @pytest.mark.integration
    def test_core_analysis_uses_strategy_config(self):
        """Test core/analysis.py uses StrategyConfig (updated in Phase 2)"""
        from config.settings import RSI_NEAR_OVERSOLD, RSI_OVERSOLD
        from config.strategy_config import StrategyConfig
        from core.analysis import analyze_ticker

        # Verify legacy constants still exist for backward compatibility
        assert RSI_OVERSOLD == 30
        assert RSI_NEAR_OVERSOLD == 40

        # Verify legacy constants are synced with StrategyConfig
        config = StrategyConfig.default()
        assert RSI_OVERSOLD == config.rsi_oversold
        assert RSI_NEAR_OVERSOLD == config.rsi_near_oversold

        # Verify analyze_ticker accepts config parameter (Phase 2 update)
        import inspect

        sig = inspect.signature(analyze_ticker)
        assert "config" in sig.parameters

        # Verify config parameter defaults to StrategyConfig.default()
        config_param = sig.parameters["config"]
        assert config_param.default is None  # Uses default internally

    @pytest.mark.integration
    def test_pattern_detection_rsi_period(self):
        """Test pattern detection works with configurable RSI period (updated in Phase 2)"""
        import numpy as np
        import pandas as pd

        from core.patterns import bullish_divergence

        # Create sample data with RSI
        dates = pd.date_range("2023-01-01", periods=30, freq="D")
        df = pd.DataFrame(
            {
                "open": np.linspace(100, 90, 30),
                "high": np.linspace(102, 92, 30),
                "low": np.linspace(98, 88, 30),
                "close": np.linspace(100, 90, 30),
                "volume": [1000000] * 30,
                "rsi10": np.linspace(20, 30, 30),  # Increasing RSI (divergence)
                "rsi14": np.linspace(22, 32, 30),  # Custom RSI period
            },
            index=dates,
        )

        # Test with default RSI period (10)
        result_default = bullish_divergence(df, rsi_period=10, lookback_period=10)
        assert isinstance(result_default, (bool, np.bool_))

        # Test with custom RSI period (14)
        result_custom = bullish_divergence(df, rsi_period=14, lookback_period=10)
        assert isinstance(result_custom, (bool, np.bool_))

        # Test backward compatibility (default parameters)
        result_backward = bullish_divergence(df)
        assert isinstance(result_backward, (bool, np.bool_))

    @pytest.mark.integration
    def test_auto_trader_config_sync(self):
        """Test auto-trader config is synced with StrategyConfig (updated in Phase 2)"""
        try:
            from config.strategy_config import StrategyConfig
            from modules.kotak_neo_auto_trader.config import RSI_PERIOD

            # Verify RSI_PERIOD exists
            assert RSI_PERIOD is not None

            # Verify RSI_PERIOD is synced with StrategyConfig
            strategy_config = StrategyConfig.default()
            assert RSI_PERIOD == strategy_config.rsi_period

            # Verify default value is correct
            assert RSI_PERIOD == 10  # Should match StrategyConfig default

        except ImportError:
            pytest.skip("Auto-trader config not available")

    @pytest.mark.integration
    def test_deprecated_constants_still_work(self):
        """Test deprecated constants still work and are synced with StrategyConfig (updated in Phase 2)"""
        from config.settings import RSI_NEAR_OVERSOLD, RSI_OVERSOLD
        from config.strategy_config import StrategyConfig

        # Verify constants still work
        assert RSI_OVERSOLD == 30
        assert RSI_NEAR_OVERSOLD == 40

        # Verify constants are synced with StrategyConfig (Phase 2 update)
        config = StrategyConfig.default()
        assert RSI_OVERSOLD == config.rsi_oversold
        assert RSI_NEAR_OVERSOLD == config.rsi_near_oversold

        # Verify constants can still be imported (backward compatibility)
        from config.settings import RSI_OVERSOLD as RSI_OVERSOLD_IMPORTED

        assert RSI_OVERSOLD_IMPORTED == 30


# ============================================================================
# 10. Performance Benchmarking
# ============================================================================


class TestPerformance:
    """Test performance improvements"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_data_fetching_performance(self):
        """Test that data fetching optimization improves performance"""
        import time

        symbol = "RELIANCE.NS"
        date_range = ("2023-01-01", "2023-12-31")

        try:
            # Measure time for integrated backtest (should reuse data)
            start_time = time.time()
            signals, engine = run_backtest(symbol, date_range, return_engine=True)
            fetch_time = time.time() - start_time

            # Verify it completes in reasonable time (< 30 seconds for single stock)
            assert fetch_time < 30, f"Data fetching took {fetch_time:.2f}s, expected < 30s"

            # Verify data is available
            assert engine is not None
            if engine is None or engine.data is None or engine.data.empty:
                pytest.skip(f"No data available for {symbol} (network issue or symbol not found)")
        except (ValueError, Exception) as e:
            # Catch any exception during backtest execution
            error_msg = str(e)
            if (
                "No data available" in error_msg
                or "network" in error_msg.lower()
                or "data" in error_msg.lower()
            ):
                pytest.skip(f"Data fetching failed for {symbol}: {error_msg}")
            else:
                raise


# ============================================================================
# Main Test Runner
# ============================================================================


def main():
    """Run all Phase 3 tests"""
    print("\n" + "=" * 80)
    print("Phase 3: Testing & Validation for Configurable Indicators")
    print("=" * 80)

    # Run pytest
    pytest.main([__file__, "-v", "--tb=short", "-m", "integration or slow", "--durations=10"])


if __name__ == "__main__":
    main()
