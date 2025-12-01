"""
Concrete Pipeline Steps for Analysis

Wraps existing services (Phase 1 & 2) with pipeline pattern (Phase 3).
Each step is a self-contained unit that can be added/removed from pipeline.

Phase 3 Feature - Pipeline Steps Implementation
"""

from typing import Optional
import logging

from services.pipeline import PipelineStep, PipelineContext
from services.data_service import DataService
from services.indicator_service import IndicatorService
from services.signal_service import SignalService
from services.verdict_service import VerdictService
from services.event_bus import Event, EventType, get_event_bus
import pandas as pd

try:
    from services.ml_verdict_service import MLVerdictService
    from services.ml_logging_service import get_ml_logging_service
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    MLVerdictService = None
    get_ml_logging_service = None

logger = logging.getLogger(__name__)


class FetchDataStep(PipelineStep):
    """
    Pipeline step to fetch market data

    Fetches OHLCV data using DataService and adds to context
    """

    def __init__(self, data_service: Optional[DataService] = None):
        super().__init__("FetchData")
        self.data_service = data_service or DataService()

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Fetch market data for ticker"""
        try:
            # Fetch daily data
            df = self.data_service.fetch_single_timeframe(
                ticker=context.ticker,
                end_date=context.config.get('end_date') if context.config else None,
                add_current_day=context.config.get('add_current_day', True) if context.config else True
            )

            if df is None or df.empty:
                context.add_error(f"No data available for {context.ticker}")
                return context

            # Add to context
            context.data = {'df': df, 'timeframe': 'daily'}
            context.set_result('data_fetched', True)
            context.set_result('data_points', len(df))

            # Publish event
            get_event_bus().publish(Event(
                event_type=EventType.DATA_FETCHED,
                data={'ticker': context.ticker, 'rows': len(df)},
                source='FetchDataStep'
            ))

            logger.info(f"Fetched {len(df)} rows of data for {context.ticker}")

        except Exception as e:
            context.add_error(f"Data fetch failed: {str(e)}")

        return context


class CalculateIndicatorsStep(PipelineStep):
    """
    Pipeline step to calculate technical indicators

    Computes RSI, EMA, volume metrics using IndicatorService
    """

    def __init__(self, indicator_service: Optional[IndicatorService] = None):
        super().__init__("CalculateIndicators")
        self.indicator_service = indicator_service or IndicatorService()

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Calculate technical indicators"""
        try:
            # Get data from context
            if not context.data or 'df' not in context.data:
                context.add_error("No data available for indicator calculation")
                return context

            df = context.data['df']

            # Calculate indicators
            df = self.indicator_service.compute_indicators(df)

            # Update context
            context.data['df'] = df

            # Get latest row using DataService
            data_service = DataService()
            latest_row = data_service.get_latest_row(df)

            # Extract key indicator values
            indicators = {
                'rsi': self.indicator_service.get_rsi_value(latest_row) if latest_row is not None else None,
                'ema200': self.indicator_service.get_ema200_value(latest_row) if latest_row is not None else None,
                'close': float(latest_row.get('close')) if latest_row is not None and pd.notna(latest_row.get('close')) else None,
                'is_above_ema200': self.indicator_service.is_above_ema200(latest_row) if latest_row is not None else False,
            }

            context.set_result('indicators', indicators)
            context.set_result('indicators_calculated', True)

            logger.info(f"Calculated indicators for {context.ticker}: RSI={indicators['rsi']}")

        except Exception as e:
            context.add_error(f"Indicator calculation failed: {str(e)}")

        return context


class DetectSignalsStep(PipelineStep):
    """
    Pipeline step to detect trading signals

    Identifies patterns, RSI oversold, EMA positions using SignalService
    """

    def __init__(self, signal_service: Optional[SignalService] = None):
        super().__init__("DetectSignals")
        self.signal_service = signal_service or SignalService()

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Detect trading signals"""
        try:
            # Get data from context
            if not context.data or 'df' not in context.data:
                context.add_error("No data available for signal detection")
                return context

            df = context.data['df']

            # Get latest and previous rows
            data_service = DataService()
            last = data_service.get_latest_row(df)
            prev = data_service.get_previous_row(df)

            if last is None:
                context.add_error("No data available for signal detection")
                return context

            # Detect signals
            signals = []

            # Pattern signals
            pattern_signals = self.signal_service.detect_pattern_signals(df, last, prev)
            signals.extend(pattern_signals)

            # RSI oversold signal
            if self.signal_service.detect_rsi_oversold_signal(last):
                signals.append("rsi_oversold")

            # Add to context
            context.set_result('signals', signals)
            context.set_result('signal_count', len(signals))

            # Publish event for each signal
            for signal in signals:
                get_event_bus().publish(Event(
                    event_type=EventType.SIGNAL_DETECTED,
                    data={'ticker': context.ticker, 'signal': signal},
                    source='DetectSignalsStep'
                ))

            logger.info(f"Detected {len(signals)} signals for {context.ticker}: {signals}")

        except Exception as e:
            context.add_error(f"Signal detection failed: {str(e)}")

        return context


class DetermineVerdictStep(PipelineStep):
    """
    Pipeline step to determine trading verdict

    Analyzes signals, volume, fundamentals to produce BUY/WATCH/AVOID verdict
    """

    def __init__(self, verdict_service: Optional[VerdictService] = None):
        super().__init__("DetermineVerdict")
        self.verdict_service = verdict_service or VerdictService()

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Determine trading verdict"""
        try:
            # Get data from context
            if not context.data or 'df' not in context.data:
                # Set default verdict when no data available
                context.set_result('verdict', 'avoid')
                context.set_result('justification', ['No data available - cannot determine verdict'])
                context.set_result('verdict_source', 'rule_based')
                context.add_error("No data available for verdict determination")
                logger.warning(f"No data available for {context.ticker} - setting default verdict: avoid")
                return context

            df = context.data['df']
            signals = context.get_result('signals', [])
            indicators = context.get_result('indicators', {})

            # Get latest row
            data_service = DataService()
            last = data_service.get_latest_row(df)

            if last is None:
                context.add_error("No data available for verdict determination")
                return context

            # Get indicator values (needed for RSI-based volume adjustment)
            rsi_value = indicators.get('rsi')
            is_above_ema200 = indicators.get('is_above_ema200', False)

            # Assess volume (with RSI for RSI-based volume threshold adjustment)
            # RELAXED VOLUME REQUIREMENTS (2025-11-09): Pass RSI for RSI-based adjustment
            # For RSI < 30 (oversold), volume requirement is reduced to 0.5x
            volume_data = self.verdict_service.assess_volume(df, last, rsi_value=rsi_value)
            context.set_result('volume_data', volume_data)

            # Get fundamentals if available
            fundamentals = context.get_result('fundamentals', {})
            pe = fundamentals.get('pe') if fundamentals else None
            pb = fundamentals.get('pb') if fundamentals else None

            # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): Assess fundamentals with flexible logic
            # - Keep negative PE filter for "avoid" (loss-making companies)
            # - But allow "watch" verdict for growth stocks (negative PE) if PB ratio is reasonable (< 5.0)
            fundamental_assessment = self.verdict_service.assess_fundamentals(pe, pb)
            fundamental_ok = fundamental_assessment.get('fundamental_ok', not (pe is not None and pe < 0))  # Backward compatibility

            # Get timeframe confirmation if available
            timeframe_confirmation = context.get_result('multi_timeframe')
            news_sentiment = context.get_result('news_sentiment')

            # Determine verdict
            verdict, justification = self.verdict_service.determine_verdict(
                signals=signals,
                rsi_value=rsi_value,
                is_above_ema200=is_above_ema200,
                vol_ok=volume_data.get('vol_ok', False),
                vol_strong=volume_data.get('vol_strong', False),
                fundamental_ok=fundamental_ok,  # Backward compatibility
                timeframe_confirmation=timeframe_confirmation,
                news_sentiment=news_sentiment,
                fundamental_assessment=fundamental_assessment  # New: flexible fundamental assessment
            )

            context.set_result('verdict', verdict)
            context.set_result('justification', justification)
            context.set_result('verdict_source', 'rule_based')  # Default to rule-based for non-ML pipeline

            # Calculate trading parameters if verdict is favorable
            # CRITICAL REQUIREMENT (2025-11-09): RSI10 < 30 is a key requirement
            # Trading parameters are ONLY calculated when RSI < 30 (or RSI < 20 if below EMA200)
            if verdict in ['strong_buy', 'buy']:
                extremes = data_service.get_recent_extremes(df)
                current_price = float(last['close'])

                trading_params = self.verdict_service.calculate_trading_parameters(
                    current_price=current_price,
                    verdict=verdict,
                    recent_low=extremes['low'],
                    recent_high=extremes['high'],
                    timeframe_confirmation=timeframe_confirmation,
                    df=df,
                    rsi_value=rsi_value,  # Pass RSI for validation
                    is_above_ema200=is_above_ema200  # Pass EMA200 position for threshold selection
                )
                context.set_result('trading_params', trading_params)

            logger.info(f"Verdict for {context.ticker}: {verdict}")

        except Exception as e:
            context.add_error(f"Verdict determination failed: {str(e)}")

        return context


class FetchFundamentalsStep(PipelineStep):
    """
    Pipeline step to fetch fundamental data (optional)

    Gets PE, PB ratios and applies fundamental filters
    """

    def __init__(self, verdict_service: Optional[VerdictService] = None):
        super().__init__("FetchFundamentals")
        self.verdict_service = verdict_service or VerdictService()
        # Make this step optional by default
        self.enabled = False

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Fetch fundamental data"""
        try:
            fundamentals = self.verdict_service.fetch_fundamentals(context.ticker)

            context.set_result('fundamentals', fundamentals)
            context.set_result('fundamentals_fetched', True)

            logger.info(f"Fetched fundamentals for {context.ticker}: {fundamentals}")

        except Exception as e:
            # Non-critical error - don't stop pipeline
            logger.warning(f"Fundamental fetch failed for {context.ticker}: {e}")
            context.set_result('fundamentals_fetched', False)

        return context


class MLVerdictStep(PipelineStep):
    """
    Pipeline step for ML-enhanced verdict prediction (optional)

    Uses trained ML model to enhance or replace rule-based verdicts.
    Falls back to rule-based logic if ML unavailable or confidence too low.

    Phase 3 Feature - ML Integration
    """

    def __init__(self, ml_verdict_service: Optional['MLVerdictService'] = None, config=None):
        super().__init__("MLVerdict")
        self.config = config
        self.ml_service = None

        if not ML_AVAILABLE:
            logger.warning("ML services not available. Install ML dependencies.")
            self.enabled = False
            return

        # Use provided service or create new one
        if ml_verdict_service:
            self.ml_service = ml_verdict_service
        elif config and hasattr(config, 'ml_verdict_model_path'):
            # Create ML service with model path from config
            self.ml_service = MLVerdictService(
                model_path=config.ml_verdict_model_path,
                config=config
            )
        else:
            # Try default model path
            self.ml_service = MLVerdictService(
                model_path="models/verdict_model_random_forest.pkl"
            )

        # Make this step optional by default (must be explicitly enabled)
        self.enabled = False

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Apply ML verdict prediction"""
        try:
            if not self.ml_service or not self.ml_service.model_loaded:
                logger.debug("ML model not loaded, skipping ML verdict step")
                return context

            # Get rule-based verdict from previous step
            rule_verdict = context.get_result('verdict')
            rule_justification = context.get_result('justification', [])

            # Get features from context
            signals = context.get_result('signals', [])
            indicators = context.get_result('indicators', {})
            volume_data = context.get_result('volume_data', {})
            fundamentals = context.get_result('fundamentals', {})
            timeframe_confirmation = context.get_result('multi_timeframe')
            news_sentiment = context.get_result('news_sentiment')

            # Extract parameters for ML service
            rsi_value = indicators.get('rsi')
            is_above_ema200 = indicators.get('is_above_ema200', False)
            vol_ok = volume_data.get('vol_ok', False)
            vol_strong = volume_data.get('vol_strong', False)

            pe = fundamentals.get('pe') if fundamentals else None
            fundamental_ok = not (pe is not None and pe < 0)

            # Get DataFrame for feature extraction
            df = context.data.get('df') if context.data else None

            # Get ML prediction with confidence (with full context)
            ml_verdict, ml_confidence = self.ml_service.predict_verdict_with_confidence(
                signals=signals,
                rsi_value=rsi_value,
                is_above_ema200=is_above_ema200,
                vol_ok=vol_ok,
                vol_strong=vol_strong,
                fundamental_ok=fundamental_ok,
                timeframe_confirmation=timeframe_confirmation,
                news_sentiment=news_sentiment,
                indicators=indicators,
                fundamentals=fundamentals,
                df=df
            )

            # Store ML prediction metadata
            context.set_result('ml_verdict', ml_verdict)
            context.set_result('ml_confidence', ml_confidence)
            context.set_result('rule_verdict', rule_verdict)

            # Decide whether to use ML verdict
            if ml_verdict and ml_confidence > 0:
                confidence_threshold = self.config.ml_confidence_threshold if self.config and hasattr(self.config, 'ml_confidence_threshold') else 0.5

                if ml_confidence >= confidence_threshold:
                    # Use ML verdict if confidence is high enough
                    final_verdict = ml_verdict

                    # Update justification
                    ml_justification = [
                        f"ML prediction: {ml_verdict} (confidence: {ml_confidence:.1%})",
                        f"Rule-based verdict: {rule_verdict}"
                    ]

                    # Combine with rule justification if enabled
                    if self.config and hasattr(self.config, 'ml_combine_with_rules') and self.config.ml_combine_with_rules:
                        ml_justification.extend(rule_justification)

                    context.set_result('verdict', final_verdict)
                    context.set_result('justification', ml_justification)
                    context.set_result('verdict_source', 'ml')

                    logger.info(
                        f"ML verdict for {context.ticker}: {final_verdict} "
                        f"(confidence: {ml_confidence:.1%}, rule-based: {rule_verdict})"
                    )
                else:
                    # Keep rule-based verdict if confidence too low
                    context.set_result('verdict_source', 'rule_based')
                    logger.info(
                        f"ML confidence too low ({ml_confidence:.1%}), using rule-based verdict: {rule_verdict}"
                    )
            else:
                # No ML prediction, keep rule-based
                context.set_result('verdict_source', 'rule_based')
                logger.debug("No ML prediction available, using rule-based verdict")

            # Log ML prediction (Phase 4 - Monitoring)
            if get_ml_logging_service:
                try:
                    ml_logging = get_ml_logging_service()
                    ml_logging.log_prediction(
                        ticker=context.ticker,
                        ml_verdict=ml_verdict,
                        ml_confidence=ml_confidence,
                        rule_verdict=rule_verdict,
                        final_verdict=context.get_result('verdict'),
                        verdict_source=context.get_result('verdict_source'),
                        features=None,  # Could extract if needed
                        indicators=indicators
                    )
                except Exception as log_error:
                    logger.debug(f"Failed to log ML prediction: {log_error}")

            # Publish event
            get_event_bus().publish(Event(
                event_type=EventType.ANALYSIS_COMPLETED,
                data={
                    'ticker': context.ticker,
                    'ml_verdict': ml_verdict,
                    'ml_confidence': ml_confidence,
                    'rule_verdict': rule_verdict,
                    'final_verdict': context.get_result('verdict'),
                    'verdict_source': context.get_result('verdict_source')
                },
                source='MLVerdictStep'
            ))

        except Exception as e:
            # Non-critical error - don't stop pipeline
            logger.warning(f"ML verdict step failed for {context.ticker}: {e}")
            context.set_result('verdict_source', 'rule_based')

        return context


class MultiTimeframeStep(PipelineStep):
    """
    Pipeline step for multi-timeframe analysis (optional)

    Analyzes multiple timeframes for confirmation
    """

    def __init__(self, data_service: Optional[DataService] = None, signal_service: Optional[SignalService] = None):
        super().__init__("MultiTimeframe")
        self.data_service = data_service or DataService()
        self.signal_service = signal_service or SignalService()
        # Make this step optional by default
        self.enabled = False

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Perform multi-timeframe analysis"""
        try:
            # Fetch weekly data using multi-timeframe
            multi_data = self.data_service.fetch_multi_timeframe(
                ticker=context.ticker,
                end_date=context.config.get('end_date') if context.config else None,
                add_current_day=context.config.get('add_current_day', True) if context.config else True
            )

            weekly_df = multi_data.get('weekly') if multi_data else None

            if weekly_df is not None and not weekly_df.empty:
                # Get timeframe confirmation
                daily_df = context.data['df']

                mtf_result = self.signal_service.get_timeframe_confirmation(
                    daily_df=daily_df,
                    weekly_df=weekly_df
                )

                context.set_result('multi_timeframe', mtf_result)
                context.set_result('mtf_analyzed', True)

                logger.info(f"Multi-timeframe analysis for {context.ticker}: {mtf_result}")
            else:
                context.set_result('mtf_analyzed', False)

        except Exception as e:
            # Non-critical error
            logger.warning(f"Multi-timeframe analysis failed for {context.ticker}: {e}")
            context.set_result('mtf_analyzed', False)

        return context


def create_analysis_pipeline(
    enable_fundamentals: bool = False,
    enable_multi_timeframe: bool = False,
    enable_ml: bool = False,
    config=None
) -> 'AnalysisPipeline':
    """
    Create a fully configured analysis pipeline

    Args:
        enable_fundamentals: Include fundamental analysis step
        enable_multi_timeframe: Include multi-timeframe analysis step
        enable_ml: Include ML-enhanced verdict prediction
        config: Strategy configuration (for ML settings)

    Returns:
        Configured AnalysisPipeline
    """
    from services.pipeline import AnalysisPipeline

    pipeline = AnalysisPipeline()

    # Core steps (always enabled)
    pipeline.add_step(FetchDataStep())
    pipeline.add_step(CalculateIndicatorsStep())
    pipeline.add_step(DetectSignalsStep())
    pipeline.add_step(DetermineVerdictStep())

    # Optional steps
    if enable_fundamentals:
        fundamentals_step = FetchFundamentalsStep()
        fundamentals_step.enabled = True
        pipeline.add_step(fundamentals_step)

    if enable_multi_timeframe:
        mtf_step = MultiTimeframeStep()
        mtf_step.enabled = True
        pipeline.add_step(mtf_step)

    # ML step (after verdict determination, optional)
    if enable_ml and ML_AVAILABLE:
        ml_step = MLVerdictStep(config=config)
        ml_step.enabled = True
        pipeline.add_step(ml_step)  # Added after DetermineVerdictStep
        logger.info("ML verdict prediction enabled in pipeline")
    elif enable_ml and not ML_AVAILABLE:
        logger.warning("ML requested but not available. Install ML dependencies.")

    logger.info(
        f"Created analysis pipeline with {len(pipeline.get_enabled_steps())} enabled steps: "
        f"{', '.join(pipeline.get_enabled_steps())}"
    )

    return pipeline
