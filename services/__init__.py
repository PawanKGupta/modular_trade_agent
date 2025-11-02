"""
Service Layer for Analysis

This module provides service classes that encapsulate business logic
extracted from the monolithic analysis.py module.

Phase 1: Basic service layer (Data, Indicator, Signal, Verdict, Analysis)
Phase 2: Async support, caching, typed models
Phase 3: Pipeline pattern, Event-driven architecture
"""

from services.analysis_service import AnalysisService
from services.data_service import DataService
from services.indicator_service import IndicatorService
from services.signal_service import SignalService
from services.verdict_service import VerdictService

# Phase 4: Additional services (Scoring, Backtest)
from services.scoring_service import ScoringService, compute_strength_score
from services.backtest_service import BacktestService

# Phase 2: Async and caching
from services.async_analysis_service import AsyncAnalysisService
from services.async_data_service import AsyncDataService
from services.cache_service import CacheService, CachedDataService

# Phase 2: Typed models
from services.models import (
    AnalysisResult,
    Verdict,
    TradingParameters,
    Indicators,
    Fundamentals
)

# Phase 3: Event bus and pipeline
from services.event_bus import EventBus, Event, EventType, get_event_bus, reset_event_bus
from services.pipeline import AnalysisPipeline, PipelineStep, PipelineContext
from services.pipeline_steps import (
    FetchDataStep,
    CalculateIndicatorsStep,
    DetectSignalsStep,
    DetermineVerdictStep,
    FetchFundamentalsStep,
    MultiTimeframeStep,
    create_analysis_pipeline
)

# Phase 3: ML Integration (optional)
try:
    from services.ml_verdict_service import MLVerdictService
    from services.ml_price_service import MLPriceService
    from services.ml_training_service import MLTrainingService
    from services.pipeline_steps import MLVerdictStep
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    MLVerdictService = None
    MLPriceService = None
    MLTrainingService = None
    MLVerdictStep = None

__all__ = [
    # Phase 1 services
    'AnalysisService',
    'DataService',
    'IndicatorService',
    'SignalService',
    'VerdictService',
    # Phase 4 services
    'ScoringService',
    'compute_strength_score',
    'BacktestService',
    # Phase 2 async services
    'AsyncAnalysisService',
    'AsyncDataService',
    # Phase 2 caching
    'CacheService',
    'CachedDataService',
    # Phase 2 models
    'AnalysisResult',
    'Verdict',
    'TradingParameters',
    'Indicators',
    'Fundamentals',
    # Phase 3 event bus
    'EventBus',
    'Event',
    'EventType',
    'get_event_bus',
    'reset_event_bus',
    # Phase 3 pipeline
    'AnalysisPipeline',
    'PipelineStep',
    'PipelineContext',
    'FetchDataStep',
    'CalculateIndicatorsStep',
    'DetectSignalsStep',
    'DetermineVerdictStep',
    'FetchFundamentalsStep',
    'MultiTimeframeStep',
    'create_analysis_pipeline',
]

# Add ML services if available
if ML_AVAILABLE:
    __all__.extend([
        'MLVerdictService',
        'MLPriceService',
        'MLTrainingService',
        'MLVerdictStep',
        'ML_AVAILABLE',
    ])

