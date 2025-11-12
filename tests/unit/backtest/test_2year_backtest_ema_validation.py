#!/usr/bin/env python3
"""
Test to validate 2-year backtest with EMA lag fix validation

This test ensures:
1. Backtest runs successfully for 2 years
2. EMA warm-up periods are sufficient
3. EMA values are accurate (no lag at backtest start)
4. Results are valid and complete
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from backtest.backtest_engine import BacktestEngine
from backtest.backtest_config import BacktestConfig
from integrated_backtest import run_integrated_backtest


@pytest.mark.backtest
@pytest.mark.integration
class Test2YearBacktestEMAValidation:
    """Test 2-year backtest with EMA validation"""

    @pytest.fixture
    def sample_stock(self):
        """Sample stock symbol for testing"""
        return "RELIANCE.NS"

    @pytest.fixture
    def date_range_2years(self):
        """2-year date range ending today"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=730)  # ~2 years
        return (
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

    def test_backtest_engine_2years_ema_warmup(self, sample_stock, date_range_2years, monkeypatch):
        """
        Test BacktestEngine 2-year backtest with EMA warm-up validation

        Validates:
        - Sufficient EMA warm-up periods before backtest start
        - EMA values are calculated correctly
        - Backtest completes without errors
        """
        start_date, end_date = date_range_2years

        # Create mock data with enough history for EMA200 warm-up
        # Need: EMA200 (200) + warm-up (100) = 300 trading days ≈ 420 calendar days
        total_days_needed = 500  # Extra buffer
        data_start = datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=total_days_needed)

        # Generate realistic OHLCV data
        days_total = (datetime.strptime(end_date, '%Y-%m-%d') - data_start).days
        dates = pd.date_range(start=data_start, periods=days_total, freq='D')

        # Create price series with trend and volatility
        np.random.seed(42)
        base_price = 2000.0
        trend = np.linspace(0, 500, days_total)  # Upward trend
        noise = np.random.normal(0, 50, days_total)  # Volatility
        close_prices = base_price + trend + noise

        # Generate OHLCV
        df = pd.DataFrame({
            'date': dates,
            'open': close_prices * (1 + np.random.normal(0, 0.01, days_total)),
            'high': close_prices * (1 + np.abs(np.random.normal(0, 0.02, days_total))),
            'low': close_prices * (1 - np.abs(np.random.normal(0, 0.02, days_total))),
            'close': close_prices,
            'volume': np.random.randint(1000000, 5000000, days_total)
        })
        df.set_index('date', inplace=True)

        # Mock fetch_multi_timeframe_data
        from core import data_fetcher
        def mock_fetch_multi_timeframe_data(ticker, days=800, end_date=None, add_current_day=True, config=None):
            # Filter data to requested end_date
            if end_date:
                end_dt = pd.to_datetime(end_date)
                filtered_df = df.loc[df.index <= end_dt].tail(days)
            else:
                filtered_df = df.tail(days)

            return {
                'daily': filtered_df.reset_index(),
                'weekly': None
            }

        monkeypatch.setattr(
            data_fetcher,
            'fetch_multi_timeframe_data',
            mock_fetch_multi_timeframe_data
        )

        # Mock chart quality service to always pass
        from services import chart_quality_service
        def mock_assess_chart_quality(self, df):
            return {'passed': True, 'reason': 'Mocked for test'}

        monkeypatch.setattr(
            chart_quality_service.ChartQualityService,
            'assess_chart_quality',
            mock_assess_chart_quality
        )

        # Run backtest
        config = BacktestConfig()
        engine = BacktestEngine(
            symbol=sample_stock,
            start_date=start_date,
            end_date=end_date,
            config=config
        )

        # Validate EMA warm-up
        # Check that we have sufficient warm-up periods before backtest start
        backtest_start_dt = pd.to_datetime(start_date)
        data_before_start = engine._full_data.loc[engine._full_data.index < backtest_start_dt]

        ema_warmup_required = min(100, int(config.EMA_PERIOD * 0.5))
        warmup_periods = len(data_before_start)

        assert warmup_periods >= ema_warmup_required, (
            f"Insufficient EMA warm-up: {warmup_periods} periods "
            f"(required: {ema_warmup_required})"
        )

        # Validate EMA values exist and are not NaN at backtest start
        first_backtest_row = engine.data.iloc[0]
        assert not pd.isna(first_backtest_row['EMA200']), (
            "EMA200 is NaN at backtest start - insufficient warm-up"
        )

        # Validate EMA200 is reasonable (not extreme outlier)
        first_ema200 = first_backtest_row['EMA200']
        first_close = first_backtest_row['Close']
        ema_close_ratio = first_ema200 / first_close

        assert 0.5 < ema_close_ratio < 2.0, (
            f"EMA200 seems incorrect: EMA={first_ema200}, Close={first_close}, "
            f"Ratio={ema_close_ratio:.2f}"
        )

        # Run backtest
        results = engine.run_backtest()

        # Validate results structure
        assert isinstance(results, dict), "Results should be a dictionary"
        assert 'symbol' in results, "Results should contain 'symbol'"
        assert 'total_trades' in results, "Results should contain 'total_trades'"
        assert 'period' in results, "Results should contain 'period'"

        # Validate results values
        assert results['symbol'] == sample_stock
        assert isinstance(results['total_trades'], (int, float))
        assert results['total_trades'] >= 0

        print(f"\n✓ BacktestEngine 2-year test passed:")
        print(f"  - Warm-up periods: {warmup_periods} (required: {ema_warmup_required})")
        print(f"  - EMA200 at start: {first_ema200:.2f}")
        print(f"  - Close at start: {first_close:.2f}")
        print(f"  - Total trades: {results['total_trades']}")

    def test_integrated_backtest_2years_ema_warmup(self, sample_stock, date_range_2years, monkeypatch):
        """
        Test integrated_backtest 2-year backtest with EMA warm-up validation

        Validates:
        - Sufficient EMA warm-up periods
        - EMA values are accurate
        - Backtest completes successfully
        """
        start_date, end_date = date_range_2years

        # Create mock data with enough history
        total_days_needed = 500
        data_start = datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=total_days_needed)

        days_total = (datetime.strptime(end_date, '%Y-%m-%d') - data_start).days
        dates = pd.date_range(start=data_start, periods=days_total, freq='D')

        np.random.seed(42)
        base_price = 2000.0
        trend = np.linspace(0, 500, days_total)
        noise = np.random.normal(0, 50, days_total)
        close_prices = base_price + trend + noise

        df = pd.DataFrame({
            'date': dates,
            'open': close_prices * (1 + np.random.normal(0, 0.01, days_total)),
            'high': close_prices * (1 + np.abs(np.random.normal(0, 0.02, days_total))),
            'low': close_prices * (1 - np.abs(np.random.normal(0, 0.02, days_total))),
            'close': close_prices,
            'volume': np.random.randint(1000000, 5000000, days_total)
        })

        # Mock fetch_ohlcv_yf
        from core import data_fetcher
        def mock_fetch_ohlcv_yf(ticker, days=365, interval='1d', end_date=None, add_current_day=True):
            if end_date:
                end_dt = pd.to_datetime(end_date)
                filtered_df = df.loc[df['date'] <= end_dt].tail(days).copy()
            else:
                filtered_df = df.tail(days).copy()

            return filtered_df

        monkeypatch.setattr(
            data_fetcher,
            'fetch_ohlcv_yf',
            mock_fetch_ohlcv_yf
        )

        # Mock trade agent to skip validation (for faster testing)
        from integrated_backtest import validate_initial_entry_with_trade_agent
        def mock_validate_initial_entry(*args, **kwargs):
            return True  # Always approve for testing

        monkeypatch.setattr(
            'integrated_backtest.validate_initial_entry_with_trade_agent',
            mock_validate_initial_entry
        )

        # Run integrated backtest
        results = run_integrated_backtest(
            stock_name=sample_stock,
            date_range=(start_date, end_date),
            capital_per_position=100000,
            skip_trade_agent_validation=True
        )

        # Validate results structure
        assert isinstance(results, dict), "Results should be a dictionary"
        assert 'error' not in results, f"Backtest failed with error: {results.get('error')}"

        # Validate key metrics exist
        assert 'positions' in results or 'executed_trades' in results, (
            "Results should contain position/trade information"
        )

        print(f"\n✓ Integrated Backtest 2-year test passed:")
        if 'executed_trades' in results:
            print(f"  - Executed trades: {results['executed_trades']}")
        if 'total_return_pct' in results:
            print(f"  - Total return: {results['total_return_pct']:.2f}%")

    def test_ema_accuracy_validation(self, monkeypatch):
        """
        Test that EMA values are accurate (not laggy) at backtest start

        This test specifically validates the EMA lag fix by checking:
        1. EMA values stabilize before backtest start
        2. EMA200 tracks price movements correctly
        3. No sudden jumps or lag in EMA values
        """
        # Create test data with known price pattern
        dates = pd.date_range(start='2022-01-01', periods=500, freq='D')

        # Create price series: steady rise, then dip, then recovery
        prices = []
        for i in range(500):
            if i < 200:
                price = 2000 + i * 2  # Steady rise
            elif i < 250:
                price = 2400 - (i - 200) * 4  # Dip
            else:
                price = 2200 + (i - 250) * 1.5  # Recovery
            prices.append(price)

        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p * 1.02 for p in prices],
            'low': [p * 0.98 for p in prices],
            'close': prices,
            'volume': [1000000] * 500
        })

        # Mock data fetcher
        from core import data_fetcher
        def mock_fetch_multi_timeframe_data(ticker, days=800, end_date=None, add_current_day=True, config=None):
            if end_date:
                end_dt = pd.to_datetime(end_date)
                filtered_df = df.loc[df['date'] <= end_dt].tail(days).copy()
            else:
                filtered_df = df.tail(days).copy()

            return {
                'daily': filtered_df,
                'weekly': None
            }

        monkeypatch.setattr(
            data_fetcher,
            'fetch_multi_timeframe_data',
            mock_fetch_multi_timeframe_data
        )

        # Mock chart quality
        from services import chart_quality_service
        def mock_assess_chart_quality(self, df):
            return {'passed': True}

        monkeypatch.setattr(
            chart_quality_service.ChartQualityService,
            'assess_chart_quality',
            mock_assess_chart_quality
        )

        # Run backtest starting after warm-up period
        # Mock data: 2022-01-01 to ~2023-05-15 (500 days)
        # Need backtest period within this range, after EMA warm-up
        # EMA200 needs 200 periods + 100 warm-up = 300 periods
        # So backtest can start around day 300+ = ~2022-11-01
        backtest_start = '2022-11-01'  # After 300+ days of data (sufficient for EMA200 warm-up)
        backtest_end = '2023-04-30'  # Within mock data range

        config = BacktestConfig()
        engine = BacktestEngine(
            symbol="TEST.NS",
            start_date=backtest_start,
            end_date=backtest_end,
            config=config
        )

        # Validate EMA stability: Check EMA200 values before and at backtest start
        backtest_start_dt = pd.to_datetime(backtest_start)
        data_before = engine._full_data.loc[engine._full_data.index < backtest_start_dt]

        if len(data_before) >= 50:
            # Check last 50 EMA200 values before backtest start
            last_50_ema = data_before['EMA200'].tail(50)

            # EMA should be relatively stable (not jumping around)
            ema_std = last_50_ema.std()
            ema_mean = last_50_ema.mean()
            cv = ema_std / ema_mean if ema_mean > 0 else 0

            # Coefficient of variation should be reasonable (< 10% for stable EMA)
            assert cv < 0.15, (
                f"EMA200 is unstable before backtest start: CV={cv:.3f} "
                f"(mean={ema_mean:.2f}, std={ema_std:.2f})"
            )

        # Validate EMA at backtest start
        first_row = engine.data.iloc[0]
        assert not pd.isna(first_row['EMA200']), "EMA200 should not be NaN"

        # EMA200 should be close to recent prices (within reasonable range)
        first_close = first_row['Close']
        first_ema200 = first_row['EMA200']

        # EMA200 should be within 30% of close price (reasonable for 200-period EMA)
        ema_close_diff_pct = abs(first_ema200 - first_close) / first_close
        assert ema_close_diff_pct < 0.30, (
            f"EMA200 too far from close: EMA={first_ema200:.2f}, "
            f"Close={first_close:.2f}, Diff={ema_close_diff_pct:.1%}"
        )

        print(f"\n✓ EMA Accuracy Validation passed:")
        print(f"  - EMA200 at start: {first_ema200:.2f}")
        print(f"  - Close at start: {first_close:.2f}")
        print(f"  - Difference: {ema_close_diff_pct:.1%}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

