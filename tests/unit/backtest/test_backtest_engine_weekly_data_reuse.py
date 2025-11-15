"""
Unit tests for weekly data reuse in BacktestEngine

Tests for:
1. Weekly data storage in _weekly_data
2. Weekly data reuse in integrated_backtest
3. Data format conversion (uppercase to lowercase)
"""

import sys
from pathlib import Path
import pandas as pd
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from backtest.backtest_engine import BacktestEngine
from datetime import datetime, timedelta


class TestBacktestEngineWeeklyDataReuse:
    """Test weekly data reuse in BacktestEngine"""

    def test_backtest_engine_stores_weekly_data(self):
        """Test that BacktestEngine stores weekly data in _weekly_data"""
        # Create mock weekly data with lowercase columns (as returned by fetch_multi_timeframe_data)
        # Need at least 20 weeks of data for weekly analysis
        weekly_data = pd.DataFrame({
            'open': [100 + i for i in range(20)],
            'high': [105 + i for i in range(20)],
            'low': [95 + i for i in range(20)],
            'close': [103 + i for i in range(20)],
            'volume': [1000 + i * 100 for i in range(20)],
            'date': pd.date_range('2022-01-01', periods=20, freq='W')
        })

        # Create mock daily data with lowercase columns
        # Need at least 250+ days for EMA200 calculation
        num_days = 300
        daily_data = pd.DataFrame({
            'open': [100 + i * 0.1 for i in range(num_days)],
            'high': [105 + i * 0.1 for i in range(num_days)],
            'low': [95 + i * 0.1 for i in range(num_days)],
            'close': [103 + i * 0.1 for i in range(num_days)],
            'volume': [1000 + i * 10 for i in range(num_days)],
            'date': pd.date_range('2022-01-01', periods=num_days, freq='D')
        })

        # Mock fetch_multi_timeframe_data to return weekly data
        mock_multi_data = {
            'daily': daily_data,
            'weekly': weekly_data
        }

        # Patch at the import location (core.data_fetcher), not the module location
        with patch('core.data_fetcher.fetch_multi_timeframe_data') as mock_fetch:
            mock_fetch.return_value = mock_multi_data

            # Create BacktestEngine with dates that fall within the data range
            start_date = datetime(2022, 6, 1)  # Midway through data
            end_date = datetime(2022, 12, 31)
            engine = BacktestEngine(
                symbol="TEST.NS",  # Use 'symbol' not 'stock_symbol'
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )

            # Verify weekly data is stored
            assert hasattr(engine, '_weekly_data')
            assert engine._weekly_data is not None
            assert len(engine._weekly_data) == 20
            assert 'Close' in engine._weekly_data.columns

    def test_backtest_engine_weekly_data_format(self):
        """Test that weekly data has correct format (uppercase columns)"""
        # Create mock weekly data with lowercase columns (as returned by fetch_multi_timeframe_data)
        # Need at least 20 weeks of data for weekly analysis
        weekly_data = pd.DataFrame({
            'open': [100 + i for i in range(20)],
            'high': [105 + i for i in range(20)],
            'low': [95 + i for i in range(20)],
            'close': [103 + i for i in range(20)],
            'volume': [1000 + i * 100 for i in range(20)],
            'date': pd.date_range('2022-01-01', periods=20, freq='W')
        })

        # Create mock daily data with lowercase columns
        # Need at least 250+ days for EMA200 calculation
        num_days = 300
        daily_data = pd.DataFrame({
            'open': [100 + i * 0.1 for i in range(num_days)],
            'high': [105 + i * 0.1 for i in range(num_days)],
            'low': [95 + i * 0.1 for i in range(num_days)],
            'close': [103 + i * 0.1 for i in range(num_days)],
            'volume': [1000 + i * 10 for i in range(num_days)],
            'date': pd.date_range('2022-01-01', periods=num_days, freq='D')
        })

        mock_multi_data = {
            'daily': daily_data,
            'weekly': weekly_data
        }

        # Patch at the import location (core.data_fetcher), not the module location
        with patch('core.data_fetcher.fetch_multi_timeframe_data') as mock_fetch:
            mock_fetch.return_value = mock_multi_data

            start_date = datetime(2022, 6, 1)  # Midway through data
            end_date = datetime(2022, 12, 31)
            engine = BacktestEngine(
                symbol="TEST.NS",  # Use 'symbol' not 'stock_symbol'
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )

            # Verify weekly data has uppercase columns
            assert 'Open' in engine._weekly_data.columns
            assert 'High' in engine._weekly_data.columns
            assert 'Low' in engine._weekly_data.columns
            assert 'Close' in engine._weekly_data.columns
            assert 'Volume' in engine._weekly_data.columns

    def test_backtest_engine_weekly_data_none_when_not_available(self):
        """Test that _weekly_data is None when weekly data is not available"""
        # Create mock daily data with lowercase columns
        # Need at least 250+ days for EMA200 calculation
        num_days = 300
        daily_data = pd.DataFrame({
            'open': [100 + i * 0.1 for i in range(num_days)],
            'high': [105 + i * 0.1 for i in range(num_days)],
            'low': [95 + i * 0.1 for i in range(num_days)],
            'close': [103 + i * 0.1 for i in range(num_days)],
            'volume': [1000 + i * 10 for i in range(num_days)],
            'date': pd.date_range('2022-01-01', periods=num_days, freq='D')
        })

        mock_multi_data = {
            'daily': daily_data,
            'weekly': None
        }

        # Patch at the import location (core.data_fetcher), not the module location
        with patch('core.data_fetcher.fetch_multi_timeframe_data') as mock_fetch:
            mock_fetch.return_value = mock_multi_data

            start_date = datetime(2022, 6, 1)  # Midway through data
            end_date = datetime(2022, 12, 31)
            engine = BacktestEngine(
                symbol="TEST.NS",  # Use 'symbol' not 'stock_symbol'
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )

            # Verify weekly data is None
            assert engine._weekly_data is None


class TestIntegratedBacktestWeeklyDataReuse:
    """Test weekly data reuse in integrated_backtest"""

    @pytest.mark.skip(reason="Tests old run_backtest function - replaced in Nov 2025 refactor")
    def test_integrated_backtest_passes_weekly_data(self):
        """Test that integrated_backtest passes weekly data to trade_agent"""
        # This is more of an integration test, but we can test the logic
        from integrated_backtest import run_integrated_backtest

        # Mock BacktestEngine with weekly data
        mock_weekly_data = pd.DataFrame({
            'Open': [100, 101],
            'High': [105, 106],
            'Low': [95, 96],
            'Close': [103, 104],
            'Volume': [1000, 1100]
        }, index=pd.date_range('2023-01-01', periods=2, freq='W'))

        # Mock backtest engine
        mock_engine = MagicMock()
        mock_engine._weekly_data = mock_weekly_data
        mock_engine._full_data = pd.DataFrame({
            'Open': [100] * 10,
            'High': [105] * 10,
            'Low': [95] * 10,
            'Close': [103] * 10,
            'Volume': [1000] * 10
        }, index=pd.date_range('2023-01-01', periods=10, freq='D'))
        mock_engine.data = mock_engine._full_data.iloc[:5]  # Backtest period

        # Mock run_backtest to return engine with weekly data
        with patch('integrated_backtest.run_backtest') as mock_run_backtest:
            mock_run_backtest.return_value = ([], mock_engine)

            # Mock trade_agent to capture weekly data
            with patch('integrated_backtest.trade_agent') as mock_trade_agent:
                mock_trade_agent.return_value = MagicMock(verdict='buy')

                # This would normally call run_integrated_backtest
                # But we're just testing that the logic exists
                # In a real test, we'd need to set up more mocks
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
