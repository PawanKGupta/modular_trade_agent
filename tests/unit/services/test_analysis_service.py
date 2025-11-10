"""
Unit tests for AnalysisService (Phase 1 refactoring)

Tests the new service layer extracted from monolithic analyze_ticker() function.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch

from services.analysis_service import AnalysisService
from services.data_service import DataService
from services.indicator_service import IndicatorService
from services.signal_service import SignalService
from services.verdict_service import VerdictService
from config.strategy_config import StrategyConfig


class TestAnalysisService:
    """Test suite for AnalysisService"""
    
    def test_initialization(self):
        """Test that AnalysisService initializes correctly"""
        service = AnalysisService()
        assert service is not None
        assert service.data_service is not None
        assert service.indicator_service is not None
        assert service.signal_service is not None
        assert service.verdict_service is not None
        assert service.config is not None
    
    def test_initialization_with_dependencies(self):
        """Test that AnalysisService accepts dependency injection"""
        mock_data = Mock(spec=DataService)
        mock_indicator = Mock(spec=IndicatorService)
        mock_signal = Mock(spec=SignalService)
        mock_verdict = Mock(spec=VerdictService)
        config = StrategyConfig.default()
        
        service = AnalysisService(
            data_service=mock_data,
            indicator_service=mock_indicator,
            signal_service=mock_signal,
            verdict_service=mock_verdict,
            config=config
        )
        
        assert service.data_service is mock_data
        assert service.indicator_service is mock_indicator
        assert service.signal_service is mock_signal
        assert service.verdict_service is mock_verdict
        assert service.config is config
    
    @patch('services.analysis_service.DataService')
    @patch('services.analysis_service.IndicatorService')
    @patch('services.analysis_service.SignalService')
    @patch('services.analysis_service.VerdictService')
    def test_analyze_ticker_flow(self, mock_verdict_class, mock_signal_class, mock_indicator_class, mock_data_class):
        """Test the analysis flow through the service"""
        # Setup mocks
        mock_data = Mock(spec=DataService)
        mock_indicator = Mock(spec=IndicatorService)
        mock_signal = Mock(spec=SignalService)
        mock_verdict = Mock(spec=VerdictService)
        
        # Create mock DataFrame
        mock_df = pd.DataFrame({
            'close': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [95, 96, 97],
            'volume': [1000, 1100, 1200],
            'rsi10': [25.0, 28.0, 30.0],
            'ema200': [95.0, 96.0, 97.0]
        })
        
        mock_last = mock_df.iloc[-1]
        
        # Configure mocks
        mock_data.fetch_single_timeframe.return_value = mock_df
        mock_data.clip_to_date.return_value = mock_df
        mock_data.get_latest_row.return_value = mock_last
        mock_data.get_previous_row.return_value = mock_df.iloc[-2] if len(mock_df) >= 2 else None
        mock_data.get_recent_extremes.return_value = {'high': 107.0, 'low': 95.0}
        
        mock_indicator.compute_indicators.return_value = mock_df
        mock_indicator.get_rsi_value.return_value = 25.0
        mock_indicator.is_above_ema200.return_value = True
        
        mock_signal.detect_all_signals.return_value = {
            'signals': ['rsi_oversold', 'hammer'],
            'timeframe_confirmation': {'alignment_score': 8, 'confirmation': 'excellent_uptrend_dip'},
            'news_sentiment': None
        }
        
        mock_verdict.assess_volume.return_value = {
            'volume_analysis': {'ratio': 1.2, 'quality': 'good'},
            'vol_ok': True,
            'vol_strong': False,
            'volume_description': 'Adequate volume',
            'volume_pattern': {},
            'avg_vol': 1000,
            'today_vol': 1200
        }
        
        mock_verdict.fetch_fundamentals.return_value = {'pe': 15.0, 'pb': 2.0}
        mock_verdict.determine_verdict.return_value = ('strong_buy', ['rsi:25(above_ema200)', 'pattern:hammer'])
        mock_verdict.apply_candle_quality_check.return_value = ('strong_buy', None, None)
        mock_verdict.calculate_trading_parameters.return_value = {
            'buy_range': (100.0, 102.0),
            'target': 115.0,
            'stop': 95.0
        }
        
        # Create service with mocked dependencies
        service = AnalysisService(
            data_service=mock_data,
            indicator_service=mock_indicator,
            signal_service=mock_signal,
            verdict_service=mock_verdict
        )
        
        # Execute analysis
        result = service.analyze_ticker(
            ticker="RELIANCE.NS",
            enable_multi_timeframe=False,
            export_to_csv=False
        )
        
        # Assertions
        assert result is not None
        assert result['status'] == 'success'
        assert result['ticker'] == 'RELIANCE.NS'
        assert result['verdict'] == 'strong_buy'
        assert 'rsi_oversold' in result['signals']
        assert result['buy_range'] == (100.0, 102.0)
        assert result['target'] == 115.0
        assert result['stop'] == 95.0
        
        # Verify service calls
        mock_data.fetch_single_timeframe.assert_called_once()
        mock_indicator.compute_indicators.assert_called_once()
        mock_signal.detect_all_signals.assert_called_once()
        mock_verdict.assess_volume.assert_called_once()
        mock_verdict.fetch_fundamentals.assert_called_once()
        mock_verdict.determine_verdict.assert_called_once()
        mock_verdict.calculate_trading_parameters.assert_called_once()
    
    def test_analyze_ticker_no_data(self):
        """Test that analyze_ticker handles no data gracefully"""
        service = AnalysisService()
        
        # Mock data service to return None
        service.data_service.fetch_single_timeframe = Mock(return_value=None)
        
        result = service.analyze_ticker("INVALID.NS", enable_multi_timeframe=False)
        
        assert result is not None
        assert result['status'] == 'no_data'
        assert result['ticker'] == 'INVALID.NS'
    
    def test_analyze_ticker_indicator_error(self):
        """Test that analyze_ticker handles indicator calculation errors"""
        service = AnalysisService()
        
        # Create mock DataFrame
        mock_df = pd.DataFrame({'close': [100], 'high': [105], 'low': [95], 'volume': [1000]})
        
        # Mock services
        service.data_service.fetch_single_timeframe = Mock(return_value=mock_df)
        service.indicator_service.compute_indicators = Mock(return_value=None)
        
        result = service.analyze_ticker("TEST.NS", enable_multi_timeframe=False)
        
        assert result is not None
        assert result['status'] == 'indicator_error'
        assert result['ticker'] == 'TEST.NS'
    
    @patch('pathlib.Path')
    @patch('services.ml_verdict_service.MLVerdictService')
    def test_initialization_uses_ml_verdict_service_when_model_exists(self, mock_ml_service_class, mock_path_class):
        """Test that AnalysisService automatically uses MLVerdictService when ML model exists"""
        from services.verdict_service import VerdictService
        
        # Mock Path.exists to return True for ML model
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        
        def path_side_effect(path_str):
            return mock_path
        
        mock_path_class.side_effect = path_side_effect
        
        # Mock MLVerdictService
        mock_ml_service = MagicMock()
        mock_ml_service.model_loaded = True
        mock_ml_service_class.return_value = mock_ml_service
        
        # Create AnalysisService (should use MLVerdictService)
        service = AnalysisService()
        
        # Verify MLVerdictService was called
        mock_ml_service_class.assert_called_once()
        assert service.verdict_service == mock_ml_service
    
    @patch('pathlib.Path')
    def test_initialization_uses_verdict_service_when_model_not_exists(self, mock_path_class):
        """Test that AnalysisService uses VerdictService when ML model doesn't exist"""
        from services.verdict_service import VerdictService
        
        # Mock Path.exists to return False for ML model
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        
        def path_side_effect(path_str):
            return mock_path
        
        mock_path_class.side_effect = path_side_effect
        
        # Create AnalysisService (should use VerdictService)
        service = AnalysisService()
        
        # Verify VerdictService is used (not MLVerdictService)
        assert isinstance(service.verdict_service, VerdictService)
        assert not hasattr(service.verdict_service, 'model_loaded') or not service.verdict_service.model_loaded
    
    @patch('pathlib.Path')
    @patch('services.ml_verdict_service.MLVerdictService')
    def test_initialization_falls_back_to_verdict_service_on_ml_init_error(self, mock_ml_service_class, mock_path_class):
        """Test that AnalysisService falls back to VerdictService when MLVerdictService initialization fails"""
        from services.verdict_service import VerdictService
        
        # Mock Path.exists to return True for ML model
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        
        def path_side_effect(path_str):
            return mock_path
        
        mock_path_class.side_effect = path_side_effect
        
        # Mock MLVerdictService to raise exception
        mock_ml_service_class.side_effect = Exception("ML service initialization failed")
        
        # Create AnalysisService (should fall back to VerdictService)
        service = AnalysisService()
        
        # Verify VerdictService is used (fallback)
        assert isinstance(service.verdict_service, VerdictService)
    
    @patch('pathlib.Path')
    @patch('services.ml_verdict_service.MLVerdictService')
    def test_initialization_falls_back_when_model_fails_to_load(self, mock_ml_service_class, mock_path_class):
        """Test that AnalysisService falls back to VerdictService when ML model fails to load"""
        from services.verdict_service import VerdictService
        
        # Mock Path.exists to return True for ML model
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        
        def path_side_effect(path_str):
            return mock_path
        
        mock_path_class.side_effect = path_side_effect
        
        # Mock MLVerdictService with model_loaded=False
        mock_ml_service = MagicMock()
        mock_ml_service.model_loaded = False  # Model failed to load
        mock_ml_service_class.return_value = mock_ml_service
        
        # Create AnalysisService (should fall back to VerdictService)
        service = AnalysisService()
        
        # Verify VerdictService is used (fallback)
        assert isinstance(service.verdict_service, VerdictService)


class TestDataService:
    """Test suite for DataService"""
    
    def test_initialization(self):
        """Test DataService initialization"""
        service = DataService()
        assert service is not None


class TestIndicatorService:
    """Test suite for IndicatorService"""
    
    def test_initialization(self):
        """Test IndicatorService initialization"""
        service = IndicatorService()
        assert service is not None
        assert service.config is not None
    
    def test_rsi_oversold_check(self):
        """Test RSI oversold detection"""
        service = IndicatorService()
        
        # Create mock row
        row = pd.Series({'rsi10': 25.0})
        
        assert service.is_rsi_oversold(row) is True
        
        row = pd.Series({'rsi10': 35.0})
        assert service.is_rsi_oversold(row) is False


class TestSignalService:
    """Test suite for SignalService"""
    
    def test_initialization(self):
        """Test SignalService initialization"""
        service = SignalService()
        assert service is not None
        assert service.config is not None


class TestVerdictService:
    """Test suite for VerdictService"""
    
    def test_initialization(self):
        """Test VerdictService initialization"""
        service = VerdictService()
        assert service is not None
        assert service.config is not None

