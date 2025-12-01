"""
Chart Quality Service

Analyzes chart quality to filter out stocks with poor chart patterns:
- Too many gaps (up/down)
- No movement (flat/choppy)
- Extreme candles (big red/green)
- Erratic price action
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, Optional
from utils.logger import logger
from core.candle_analysis import calculate_candle_metrics, calculate_market_context
from config.strategy_config import StrategyConfig


class ChartQualityService:
    """
    Service for analyzing chart quality

    Provides methods to:
    - Analyze gaps in the chart
    - Analyze movement/volatility
    - Analyze extreme candles
    - Calculate overall chart cleanliness score
    - Determine if chart is acceptable for trading
    """

    def __init__(self, config: Optional[StrategyConfig] = None, minimal_mode: bool = False):
        """
        Initialize chart quality service

        Args:
            config: Strategy configuration (uses default if None)
            minimal_mode: If True, only check movement (flat charts). Skip gap and extreme candle checks.
                         Use this for ML training data collection to avoid filtering out valid bounce patterns.
                         Default: False (full chart quality checks)
        """
        self.config = config or StrategyConfig.default()
        self.minimal_mode = minimal_mode

        # Chart quality thresholds (from config or env)
        # RELAXED THRESHOLDS (2025-11-09): Updated defaults to match relaxed thresholds
        self.max_gap_frequency = getattr(self.config, 'chart_quality_max_gap_frequency',
                                        float(os.getenv('CHART_QUALITY_MAX_GAP_FREQUENCY', '25.0')))  # Relaxed from 20.0
        self.min_daily_range_pct = getattr(self.config, 'chart_quality_min_daily_range_pct',
                                          float(os.getenv('CHART_QUALITY_MIN_DAILY_RANGE_PCT', '1.0')))  # Relaxed from 1.5
        self.max_extreme_candle_frequency = getattr(self.config, 'chart_quality_max_extreme_candle_frequency',
                                                   float(os.getenv('CHART_QUALITY_MAX_EXTREME_CANDLE_FREQUENCY', '20.0')))  # Relaxed from 15.0
        self.min_score = getattr(self.config, 'chart_quality_min_score',
                               float(os.getenv('CHART_QUALITY_MIN_SCORE', '50.0')))  # Relaxed from 60.0
        self.enabled = getattr(self.config, 'chart_quality_enabled',
                             os.getenv('CHART_QUALITY_ENABLED', 'true').lower() in ('1', 'true', 'yes', 'on'))

    def _normalize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names to lowercase for consistency.
        Handles both yfinance (Capitalized) and standard (lowercase) formats.
        """
        df = df.copy()
        column_mapping = {
            'Close': 'close', 'Open': 'open', 'High': 'high', 'Low': 'low',
            'Volume': 'volume', 'Adj Close': 'adj_close'
        }
        df.columns = [column_mapping.get(col, col.lower()) for col in df.columns]
        return df

    def analyze_gaps(self, df: pd.DataFrame, lookback_days: int = 60) -> Dict:
        """
        Analyze gaps in the chart

        Args:
            df: DataFrame with OHLC data
            lookback_days: Number of days to analyze

        Returns:
            Dict with gap analysis results
        """
        try:
            # Normalize column names
            df = self._normalize_column_names(df)

            recent_data = df.tail(lookback_days) if len(df) >= lookback_days else df

            if len(recent_data) < 2:
                return {
                    'gap_count': 0,
                    'gap_frequency': 0.0,
                    'avg_gap_size_pct': 0.0,
                    'max_gap_size_pct': 0.0,
                    'has_too_many_gaps': False,
                    'reason': 'Insufficient data'
                }

            gaps = []
            gap_sizes = []

            for i in range(1, len(recent_data)):
                prev_close = recent_data.iloc[i-1]['close']
                curr_open = recent_data.iloc[i]['open']
                curr_high = recent_data.iloc[i]['high']
                curr_low = recent_data.iloc[i]['low']

                # Gap up: current low > previous close
                if curr_low > prev_close:
                    gap_size = ((curr_low - prev_close) / prev_close) * 100
                    gaps.append('up')
                    gap_sizes.append(gap_size)

                # Gap down: current high < previous close
                elif curr_high < prev_close:
                    gap_size = ((prev_close - curr_high) / prev_close) * 100
                    gaps.append('down')
                    gap_sizes.append(gap_size)

            gap_count = len(gaps)
            gap_frequency = (gap_count / len(recent_data)) * 100 if len(recent_data) > 0 else 0
            avg_gap_size = np.mean(gap_sizes) if gap_sizes else 0.0
            max_gap_size = max(gap_sizes) if gap_sizes else 0.0

            # Too many gaps: >threshold% of days have gaps
            has_too_many_gaps = gap_frequency > self.max_gap_frequency

            return {
                'gap_count': gap_count,
                'gap_frequency': round(gap_frequency, 2),
                'avg_gap_size_pct': round(avg_gap_size, 2),
                'max_gap_size_pct': round(max_gap_size, 2),
                'has_too_many_gaps': has_too_many_gaps,
                'reason': f'{gap_count} gaps ({gap_frequency:.1f}% of days)' if gap_count > 0 else 'No significant gaps'
            }
        except Exception as e:
            logger.warning(f"Error analyzing gaps: {e}")
            return {
                'gap_count': 0,
                'gap_frequency': 0.0,
                'avg_gap_size_pct': 0.0,
                'max_gap_size_pct': 0.0,
                'has_too_many_gaps': False,
                'reason': f'Error: {str(e)}'
            }

    def analyze_movement(self, df: pd.DataFrame, lookback_days: int = 60) -> Dict:
        """
        Analyze if chart has movement or is flat/choppy

        Args:
            df: DataFrame with OHLC data
            lookback_days: Number of days to analyze

        Returns:
            Dict with movement analysis results
        """
        try:
            # Normalize column names
            df = self._normalize_column_names(df)

            recent_data = df.tail(lookback_days) if len(df) >= lookback_days else df

            if len(recent_data) < 10:
                return {
                    'has_movement': True,
                    'volatility_pct': 0.0,
                    'avg_daily_range_pct': 0.0,
                    'is_flat': False,
                    'reason': 'Insufficient data'
                }

            # Calculate daily ranges
            daily_ranges = recent_data['high'] - recent_data['low']
            avg_price = recent_data['close'].mean()
            avg_daily_range = daily_ranges.mean()
            avg_daily_range_pct = (avg_daily_range / avg_price) * 100 if avg_price > 0 else 0

            # Calculate volatility (ATR-like)
            volatility = daily_ranges.std()
            volatility_pct = (volatility / avg_price) * 100 if avg_price > 0 else 0

            # Check if price is stuck in tight range
            price_range = recent_data['high'].max() - recent_data['low'].min()
            price_range_pct = (price_range / avg_price) * 100 if avg_price > 0 else 0

            # Flat/choppy: low volatility and small price range
            is_flat = avg_daily_range_pct < self.min_daily_range_pct and price_range_pct < 15.0

            return {
                'has_movement': not is_flat,
                'volatility_pct': round(volatility_pct, 2),
                'avg_daily_range_pct': round(avg_daily_range_pct, 2),
                'price_range_pct': round(price_range_pct, 2),
                'is_flat': is_flat,
                'reason': f'Avg range: {avg_daily_range_pct:.1f}%, Price range: {price_range_pct:.1f}%'
            }
        except Exception as e:
            logger.warning(f"Error analyzing movement: {e}")
            return {
                'has_movement': True,
                'volatility_pct': 0.0,
                'avg_daily_range_pct': 0.0,
                'is_flat': False,
                'reason': f'Error: {str(e)}'
            }

    def analyze_extreme_candles(self, df: pd.DataFrame, lookback_days: int = 30) -> Dict:
        """
        Analyze for extreme candles (big red/green)

        Args:
            df: DataFrame with OHLC data
            lookback_days: Number of days to analyze

        Returns:
            Dict with extreme candle analysis results
        """
        try:
            # Normalize column names
            df = self._normalize_column_names(df)

            recent_data = df.tail(lookback_days) if len(df) >= lookback_days else df

            if len(recent_data) < 5:
                return {
                    'extreme_candle_count': 0,
                    'extreme_candle_frequency': 0.0,
                    'has_extreme_candles': False,
                    'reason': 'Insufficient data'
                }

            # Calculate market context
            market_context = calculate_market_context(recent_data, lookback_days=30)
            avg_daily_range = market_context['avg_daily_range']
            avg_price = market_context['avg_price_level']

            if avg_daily_range == 0 or avg_price == 0:
                return {
                    'extreme_candle_count': 0,
                    'extreme_candle_frequency': 0.0,
                    'has_extreme_candles': False,
                    'reason': 'Cannot calculate - invalid data'
                }

            extreme_candles = []

            for idx, row in recent_data.iterrows():
                metrics = calculate_candle_metrics(row)
                if metrics is None:
                    continue

                # Check if candle is extreme (body > 3x average daily range)
                body_size = metrics['body_size']
                body_vs_avg_range = body_size / avg_daily_range if avg_daily_range > 0 else 0

                # Also check absolute price movement percentage
                price_move_pct = (body_size / metrics['open']) * 100 if metrics['open'] > 0 else 0

                # Extreme candle: body > 3x avg range OR >5% price move
                is_extreme = body_vs_avg_range > 3.0 or price_move_pct > 5.0

                if is_extreme:
                    extreme_candles.append({
                        'date': idx,
                        'body_size': body_size,
                        'body_vs_avg': round(body_vs_avg_range, 2),
                        'price_move_pct': round(price_move_pct, 2),
                        'is_red': metrics['is_red'],
                        'is_green': metrics['is_green']
                    })

            extreme_count = len(extreme_candles)
            extreme_frequency = (extreme_count / len(recent_data)) * 100 if len(recent_data) > 0 else 0

            # Too many extreme candles: >threshold% of days
            has_extreme_candles = extreme_frequency > self.max_extreme_candle_frequency

            return {
                'extreme_candle_count': extreme_count,
                'extreme_candle_frequency': round(extreme_frequency, 2),
                'has_extreme_candles': has_extreme_candles,
                'extreme_candles': extreme_candles[:5],  # Top 5
                'reason': f'{extreme_count} extreme candles ({extreme_frequency:.1f}% of days)' if extreme_count > 0 else 'No extreme candles'
            }
        except Exception as e:
            logger.warning(f"Error analyzing extreme candles: {e}")
            return {
                'extreme_candle_count': 0,
                'extreme_candle_frequency': 0.0,
                'has_extreme_candles': False,
                'reason': f'Error: {str(e)}'
            }

    def calculate_chart_cleanliness_score(self, df: pd.DataFrame) -> Dict:
        """
        Calculate overall chart cleanliness score (0-100)

        Args:
            df: DataFrame with OHLC data

        Returns:
            Dict with chart quality analysis and score
        """
        if not self.enabled:
            return {
                'score': 100.0,
                'status': 'disabled',
                'passed': True,
                'gap_analysis': {},
                'movement_analysis': {},
                'extreme_candle_analysis': {},
                'reason': 'Chart quality analysis disabled'
            }

        try:
            # Normalize column names first
            df = self._normalize_column_names(df)

            # Analyze different aspects
            # In minimal mode: Only check movement (flat charts won't bounce)
            # Skip gap and extreme candle checks (they don't prevent bounces)
            if self.minimal_mode:
                gap_analysis = {'has_too_many_gaps': False, 'gap_frequency': 0.0}
                movement_analysis = self.analyze_movement(df, lookback_days=60)
                extreme_candle_analysis = {'has_extreme_candles': False, 'extreme_candle_frequency': 0.0}
            else:
                gap_analysis = self.analyze_gaps(df, lookback_days=60)
                movement_analysis = self.analyze_movement(df, lookback_days=60)
                extreme_candle_analysis = self.analyze_extreme_candles(df, lookback_days=30)

            # Calculate overall score (0-100, higher is better)
            score = 100.0

            # Penalties
            if not self.minimal_mode:
                # Full mode: Apply all penalties
                if gap_analysis['has_too_many_gaps']:
                    score -= 30.0
                elif gap_analysis['gap_frequency'] > 10.0:
                    score -= 15.0

            # Movement check: Always apply (flat charts won't bounce)
            if movement_analysis['is_flat']:
                score -= 25.0
            elif movement_analysis['avg_daily_range_pct'] < 2.0:
                score -= 10.0

            if not self.minimal_mode:
                # Full mode: Apply extreme candle penalties
                if extreme_candle_analysis['has_extreme_candles']:
                    score -= 25.0
                elif extreme_candle_analysis['extreme_candle_frequency'] > 10.0:
                    score -= 15.0

            # Ensure score is within bounds
            score = max(0.0, min(100.0, score))

            # Determine status
            if score >= 80.0:
                status = 'clean'
            elif score >= 60.0:
                status = 'acceptable'
            else:
                status = 'poor'

            # Check if passed (hard filter)
            passed = score >= self.min_score

            # Build reason
            reasons = []
            if gap_analysis['has_too_many_gaps']:
                reasons.append(f"Too many gaps ({gap_analysis['gap_frequency']:.1f}%)")
            if movement_analysis['is_flat']:
                reasons.append(f"No movement (range: {movement_analysis['avg_daily_range_pct']:.1f}%)")
            if extreme_candle_analysis['has_extreme_candles']:
                reasons.append(f"Extreme candles ({extreme_candle_analysis['extreme_candle_frequency']:.1f}%)")

            if not reasons:
                reasons.append("Clean chart")

            return {
                'score': round(score, 1),
                'status': status,
                'passed': passed,
                'gap_analysis': gap_analysis,
                'movement_analysis': movement_analysis,
                'extreme_candle_analysis': extreme_candle_analysis,
                'reason': ' | '.join(reasons)
            }
        except Exception as e:
            logger.error(f"Error calculating chart cleanliness score: {e}")
            return {
                'score': 0.0,
                'status': 'error',
                'passed': False,
                'gap_analysis': {},
                'movement_analysis': {},
                'extreme_candle_analysis': {},
                'reason': f'Error: {str(e)}'
            }

    def assess_chart_quality(self, df: pd.DataFrame) -> Dict:
        """
        Main entry point for chart quality assessment

        Args:
            df: DataFrame with OHLC data

        Returns:
            Dict with complete chart quality analysis
        """
        return self.calculate_chart_cleanliness_score(df)

    def is_chart_acceptable(self, df: pd.DataFrame) -> bool:
        """
        Check if chart is acceptable for trading (hard filter)

        Args:
            df: DataFrame with OHLC data

        Returns:
            True if chart is acceptable, False otherwise
        """
        if not self.enabled:
            return True

        analysis = self.calculate_chart_cleanliness_score(df)
        return analysis.get('passed', False)
