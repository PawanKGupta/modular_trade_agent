import pandas as pd
import numpy as np
from utils.logger import logger
from core.indicators import compute_indicators
from config.strategy_config import StrategyConfig
from typing import Optional

class TimeframeAnalysis:
    """
    Multi-timeframe analysis for dip-buying opportunities
    Analyzes daily and weekly conditions for mean reversion setups
    Focuses on oversold conditions, support levels, and exhaustion patterns
    """
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        Initialize TimeframeAnalysis with configurable parameters
        
        Args:
            config: StrategyConfig instance (uses default if None)
        """
        # Get config if not provided
        if config is None:
            config = StrategyConfig.default()
        
        self.config = config
        
        # Use configurable lookback values
        self.support_lookback_daily = config.support_resistance_lookback_daily
        self.support_lookback_weekly = config.support_resistance_lookback_weekly
        self.volume_lookback_daily = config.volume_exhaustion_lookback_daily
        self.volume_lookback_weekly = config.volume_exhaustion_lookback_weekly
        
        # RSI thresholds from config
        self.oversold_threshold = config.rsi_oversold  # Daily RSI threshold
        self.weekly_oversold_threshold = 40  # Weekly RSI threshold (can be made configurable later)
    
    def _get_support_lookback(self, timeframe: str) -> int:
        """Get support/resistance lookback for given timeframe"""
        return self.support_lookback_weekly if timeframe == 'weekly' else self.support_lookback_daily
    
    def _get_volume_lookback(self, timeframe: str) -> int:
        """Get volume exhaustion lookback for given timeframe"""
        return self.volume_lookback_weekly if timeframe == 'weekly' else self.volume_lookback_daily
    
    def _get_adaptive_lookback(self, available_data_days: int, base_lookback: int, timeframe: str) -> int:
        """
        Adaptive lookback based on available data
        Aligned with data fetching strategy: Daily max 5 years, Weekly max 3 years
        Only runs if enable_adaptive_lookback is True (configurable)
        """
        # Check if adaptive logic is enabled
        if not self.config.enable_adaptive_lookback:
            return base_lookback  # Return default if disabled

        if timeframe == 'weekly':
            # Weekly: 3 years fetched (~156 candles), use up to 50 periods (~1 year)
            if available_data_days >= 1095:  # 3 years (weekly fetch max)
                return int(min(base_lookback * 2.5, 50))  # Use up to 50 periods
            elif available_data_days >= 730:  # 2 years
                return int(min(base_lookback * 2, 40))
            else:
                return base_lookback  # Default
        else:  # daily
            # Daily: 5 years fetched (~1,250 days), use up to 50 periods (~2.5 months)
            if available_data_days >= 1825:  # 5 years (daily fetch max)
                return int(min(base_lookback * 2.5, 50))  # Use up to 50 periods
            elif available_data_days >= 1095:  # 3 years
                return int(min(base_lookback * 1.5, 30))
            else:
                return base_lookback  # Default (20 periods)

        return base_lookback  # Default fallback
    
    def analyze_dip_conditions(self, df, timeframe='daily'):
        """
        Analyze dip-buying conditions for a given timeframe
        Returns analysis focused on oversold conditions and support levels
        """
        # Get appropriate lookback for this timeframe
        support_lookback = self._get_support_lookback(timeframe)
        
        # Check if df is valid (not None and not empty)
        if df is None or df.empty:
            return None
        
        # Apply adaptive logic if enabled
        available_data_days = len(df)
        support_lookback = self._get_adaptive_lookback(available_data_days, support_lookback, timeframe)
        
        # For weekly data with limited history, use adaptive lookback
        # For dip-buying strategy, we can work with less weekly data
        if len(df) < support_lookback:
            # For weekly timeframe, try with reduced lookback if we have at least 10 rows
            if timeframe == 'weekly' and len(df) >= 10:
                # Use available data with reduced lookback (50% of requested)
                support_lookback = max(int(support_lookback * 0.5), 10)  # At least 10, or 50% of requested
                logger.debug(f"Weekly data limited ({len(df)} rows), using reduced lookback: {support_lookback} for {timeframe} analysis")
            else:
                # Not enough data even with reduced lookback
                logger.debug(f"Insufficient data for {timeframe} analysis: {len(df)} rows < {support_lookback} lookback")
                return None
            
        try:
            # Ensure indicators are computed with configurable RSI period
            df = compute_indicators(df, rsi_period=self.config.rsi_period, config=self.config)
            if df is None:
                return None
                
            last = df.iloc[-1]
            
            # Support and resistance level analysis
            support_analysis = self._analyze_support_levels(df, timeframe, support_lookback)
            resistance_analysis = self._analyze_resistance_levels(df, timeframe, support_lookback)
            
            # Oversold condition analysis
            oversold_analysis = self._analyze_oversold_conditions(df, timeframe)
            
            # Volume exhaustion analysis  
            volume_exhaustion = self._analyze_volume_exhaustion(df, timeframe)
            
            # Selling pressure analysis
            selling_pressure = self._analyze_selling_pressure(df)
            
            # Mean reversion setup quality
            reversion_setup = self._analyze_reversion_setup(df, timeframe)
            
            # Get RSI column name based on config
            rsi_col = f'rsi{self.config.rsi_period}'
            rsi_value = last[rsi_col] if rsi_col in last.index else last.get('rsi10')
            
            return {
                'timeframe': timeframe,
                'support_analysis': support_analysis,
                'resistance_analysis': resistance_analysis,
                'oversold_analysis': oversold_analysis,
                'volume_exhaustion': volume_exhaustion,
                'selling_pressure': selling_pressure,
                'reversion_setup': reversion_setup,
                'current_price': round(last['close'], 2),
                'rsi': round(rsi_value, 2) if not pd.isna(rsi_value) else None
            }
            
        except Exception as e:
            logger.error(f"Error analyzing {timeframe} trend: {e}")
            return None
    
    def _analyze_support_levels(self, df, timeframe, support_lookback=None):
        """Analyze support levels and price position relative to them"""
        if support_lookback is None:
            support_lookback = self._get_support_lookback(timeframe)
        
        # Ensure support_lookback is an integer
        support_lookback = int(support_lookback)
        
        try:
            recent_data = df.tail(support_lookback)
            current_price = df.iloc[-1]['close']
            
            # Find support levels (recent lows)
            recent_lows = recent_data['low']
            support_level = recent_lows.min()
            
            # Distance from support
            distance_from_support = ((current_price - support_level) / support_level) * 100
            
            # Support strength (how many times tested)
            support_tolerance = 0.02  # 2% tolerance
            support_tests = 0
            for low in recent_lows:
                if abs(low - support_level) / support_level <= support_tolerance:
                    support_tests += 1
            
            # Recent support hold check
            recent_5_days = df.tail(5)
            support_holding = recent_5_days['low'].min() >= support_level * 0.98
            
            # Support quality assessment
            if distance_from_support <= 3 and support_tests >= 2:
                quality = 'strong'  # Near strong support
            elif distance_from_support <= 5:
                quality = 'moderate'  # Near moderate support
            elif distance_from_support <= 10:
                quality = 'weak'  # Somewhat near support
            else:
                quality = 'none'  # Far from support
            
            return {
                'support_level': round(support_level, 2),
                'distance_pct': round(distance_from_support, 2),
                'support_tests': support_tests,
                'support_holding': support_holding,
                'quality': quality
            }
            
        except Exception as e:
            logger.error(f"Error in support analysis: {e}")
            return {'quality': 'unknown', 'distance_pct': 999, 'support_holding': False}
    
    def _analyze_resistance_levels(self, df, timeframe, support_lookback=None):
        """Analyze resistance levels and price position relative to them"""
        if support_lookback is None:
            support_lookback = self._get_support_lookback(timeframe)
        
        # Ensure support_lookback is an integer
        support_lookback = int(support_lookback)
        
        try:
            recent_data = df.tail(support_lookback)
            current_price = df.iloc[-1]['close']
            
            # Find resistance levels (recent highs)
            recent_highs = recent_data['high']
            resistance_level = recent_highs.max()
            
            # Distance to resistance
            distance_to_resistance = ((resistance_level - current_price) / current_price) * 100
            
            # Resistance strength (how many times tested)
            resistance_tolerance = 0.02  # 2% tolerance
            resistance_tests = 0
            for high in recent_highs:
                if abs(high - resistance_level) / resistance_level <= resistance_tolerance:
                    resistance_tests += 1
            
            # Recent resistance hold check
            recent_5_days = df.tail(5)
            resistance_holding = recent_5_days['high'].max() <= resistance_level * 1.02
            
            # Resistance quality assessment
            if distance_to_resistance >= 10 and resistance_tests >= 2:
                quality = 'strong'  # Far from strong resistance - good for targets
            elif distance_to_resistance >= 5:
                quality = 'moderate'  # Some room to resistance
            elif distance_to_resistance >= 2:
                quality = 'weak'  # Close to resistance - limited upside
            else:
                quality = 'immediate'  # Very close to resistance - cap targets
            
            return {
                'resistance_level': round(resistance_level, 2),
                'distance_pct': round(distance_to_resistance, 2),
                'resistance_tests': resistance_tests,
                'resistance_holding': resistance_holding,
                'quality': quality
            }
            
        except Exception as e:
            logger.error(f"Error in resistance analysis: {e}")
            return {'quality': 'unknown', 'distance_pct': 0, 'resistance_holding': True}
    
    def _analyze_oversold_conditions(self, df, timeframe):
        """Analyze oversold conditions for mean reversion opportunities"""
        try:
            last = df.iloc[-1]
            # Get RSI column name based on config
            rsi_col = f'rsi{self.config.rsi_period}'
            current_rsi = last[rsi_col] if rsi_col in last.index else last.get('rsi10')
            
            if pd.isna(current_rsi):
                return {'condition': 'unknown', 'severity': 'none', 'duration': 0}
            
            # Determine oversold threshold based on timeframe
            threshold = self.weekly_oversold_threshold if timeframe == 'weekly' else self.oversold_threshold
            
            # RSI condition assessment
            if current_rsi < 20:
                condition = 'extremely_oversold'
                severity = 'extreme'
            elif current_rsi < threshold:
                condition = 'oversold'
                severity = 'high'
            elif current_rsi < threshold + 10:
                condition = 'approaching_oversold'
                severity = 'moderate'
            else:
                condition = 'not_oversold'
                severity = 'none'
            
            # Duration of oversold condition
            rsi_col = f'rsi{self.config.rsi_period}'
            rsi_series = df[rsi_col].tail(10).dropna() if rsi_col in df.columns else df.get('rsi10', pd.Series()).tail(10).dropna()
            oversold_duration = 0
            if len(rsi_series) > 0:
                # Convert to list for safe iteration
                rsi_values = rsi_series.tolist()
                for rsi_val in reversed(rsi_values):
                    if rsi_val < threshold:
                        oversold_duration += 1
                    else:
                        break
            
            # RSI divergence check (price making new lows while RSI doesn't)
            if len(df) >= 10:
                recent_prices = df['close'].tail(10)
                rsi_col = f'rsi{self.config.rsi_period}'
                recent_rsi = df[rsi_col].tail(10).dropna() if rsi_col in df.columns else df.get('rsi10', pd.Series()).tail(10).dropna()
                
                if len(recent_rsi) >= 5:
                    price_new_low = recent_prices.iloc[-1] <= recent_prices.iloc[-5:].min()
                    rsi_higher_low = recent_rsi.iloc[-1] > recent_rsi.iloc[-5:].min()
                    bullish_divergence = price_new_low and rsi_higher_low and current_rsi < threshold
                else:
                    bullish_divergence = False
            else:
                bullish_divergence = False
            
            return {
                'condition': condition,
                'severity': severity,
                'rsi_value': round(current_rsi, 2),
                'duration': oversold_duration,
                'bullish_divergence': bullish_divergence
            }
            
        except Exception as e:
            logger.error(f"Error in oversold analysis: {e}")
            return {'condition': 'unknown', 'severity': 'none', 'duration': 0, 'bullish_divergence': False}
    
    def _analyze_volume_exhaustion(self, df, timeframe='daily'):
        """Analyze volume patterns for signs of selling exhaustion"""
        try:
            volume_lookback = self._get_volume_lookback(timeframe)
            recent_volume = df['volume'].tail(volume_lookback)
            current_volume = df['volume'].iloc[-1]
            avg_volume = recent_volume.mean()
            
            # Volume trend over recent periods
            volume_trend_periods = min(5, len(recent_volume))
            recent_volume_subset = recent_volume.tail(volume_trend_periods)
            
            if len(recent_volume_subset) >= 3:
                # Linear regression on volume to detect trend
                x = np.arange(len(recent_volume_subset))
                volume_slope = np.polyfit(x, recent_volume_subset.values, 1)[0]
                volume_trend_direction = 'declining' if volume_slope < 0 else 'increasing'
            else:
                volume_trend_direction = 'neutral'
                volume_slope = 0
            
            # Current volume relative to average
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Selling exhaustion indicators
            exhaustion_signals = []
            
            # Low volume on down days (selling drying up)
            recent_data = df.tail(5)
            down_days = recent_data[recent_data['close'] < recent_data['open']]
            if len(down_days) > 0:
                avg_down_volume = down_days['volume'].mean()
                if avg_down_volume < avg_volume * 0.8:  # Lower volume on down days
                    exhaustion_signals.append('low_volume_decline')
            
            # Volume declining over time
            if volume_trend_direction == 'declining' and len(exhaustion_signals) == 0:
                exhaustion_signals.append('declining_volume_trend')
            
            # Very low current volume
            if volume_ratio < 0.6:
                exhaustion_signals.append('very_low_volume')
            
            return {
                'volume_trend': volume_trend_direction,
                'volume_ratio': round(volume_ratio, 2),
                'avg_volume': int(avg_volume),
                'exhaustion_signals': exhaustion_signals,
                'exhaustion_score': len(exhaustion_signals)
            }
            
        except Exception as e:
            logger.error(f"Error in volume exhaustion analysis: {e}")
            return {
                'volume_trend': 'neutral', 
                'volume_ratio': 1.0, 
                'exhaustion_signals': [], 
                'exhaustion_score': 0
            }
    
    def _analyze_selling_pressure(self, df):
        """Analyze selling pressure and price action for exhaustion signs"""
        try:
            recent_data = df.tail(10)
            current_price = df.iloc[-1]['close']
            
            # Consecutive down days
            consecutive_down = 0
            for i in range(len(recent_data) - 1, -1, -1):
                if recent_data.iloc[i]['close'] < recent_data.iloc[i]['open']:
                    consecutive_down += 1
                else:
                    break
            
            # Price decline magnitude over recent period
            if len(recent_data) >= 5:
                high_5_days_ago = recent_data.iloc[-5]['high']
                decline_pct = ((current_price - high_5_days_ago) / high_5_days_ago) * 100
            else:
                decline_pct = 0
            
            # Lower lows pattern (bearish momentum weakening)
            if len(recent_data) >= 3:
                recent_lows = recent_data['low'].tail(3)
                weakening_decline = recent_lows.iloc[-1] > recent_lows.iloc[-2]  # Higher low
            else:
                weakening_decline = False
            
            # Selling pressure assessment
            pressure_signals = []
            if consecutive_down >= 3:
                pressure_signals.append('consecutive_down_days')
            if decline_pct < -10:  # Significant decline
                pressure_signals.append('major_decline')
            if decline_pct < -5:  # Moderate decline
                pressure_signals.append('moderate_decline')
                
            # Exhaustion signs
            exhaustion_signs = []
            if weakening_decline:
                exhaustion_signs.append('higher_low')
            if consecutive_down >= 3 and not recent_data.iloc[-1]['close'] < recent_data.iloc[-2]['low'] * 0.98:
                exhaustion_signs.append('shallow_final_day')  # Last down day not deep
            
            return {
                'consecutive_down_days': consecutive_down,
                'decline_pct': round(decline_pct, 2),
                'pressure_signals': pressure_signals,
                'exhaustion_signs': exhaustion_signs,
                'pressure_score': len(pressure_signals),
                'exhaustion_score': len(exhaustion_signs)
            }
            
        except Exception as e:
            logger.error(f"Error in selling pressure analysis: {e}")
            return {
                'consecutive_down_days': 0,
                'decline_pct': 0,
                'pressure_signals': [],
                'exhaustion_signs': [],
                'pressure_score': 0,
                'exhaustion_score': 0
            }
    
    def _analyze_reversion_setup(self, df, timeframe):
        """Analyze overall mean reversion setup quality"""
        try:
            current_data = df.iloc[-1]
            current_price = current_data['close']
            # Get RSI column name based on config
            rsi_col = f'rsi{self.config.rsi_period}'
            current_rsi = current_data[rsi_col] if rsi_col in current_data.index else current_data.get('rsi10')
            
            if pd.isna(current_rsi):
                return {'quality': 'poor', 'score': 0, 'reasons': []}
            
            setup_reasons = []
            score = 0
            
            # RSI oversold condition (primary signal for your strategy)
            threshold = self.weekly_oversold_threshold if timeframe == 'weekly' else self.oversold_threshold
            if current_rsi < 20:
                setup_reasons.append('extremely_oversold_rsi')
                score += 3
            elif current_rsi < threshold:
                setup_reasons.append('oversold_rsi')
                score += 2
            
            # EMA200 filter (price above EMA200 - buying dips in uptrends)
            if 'ema50' in df.columns and not pd.isna(current_data['ema50']):
                if current_price > current_data['ema50']:  # Using EMA50 as proxy for EMA200
                    setup_reasons.append('above_ema_uptrend')
                    score += 2  # Higher score for uptrend confirmation
            
            # Reversal candlestick patterns
            if len(df) >= 2:
                prev_data = df.iloc[-2]
                
                # Simple hammer pattern
                body = abs(current_data['close'] - current_data['open'])
                lower_wick = current_data['open'] - current_data['low'] if current_data['close'] > current_data['open'] else current_data['close'] - current_data['low']
                upper_wick = current_data['high'] - current_data['close'] if current_data['close'] > current_data['open'] else current_data['high'] - current_data['open']
                
                if lower_wick > body * 2 and upper_wick < body * 0.5:  # Hammer-like
                    setup_reasons.append('hammer_pattern')
                    score += 1
                
                # Bullish engulfing
                if (prev_data['close'] < prev_data['open'] and  # Previous red candle
                    current_data['close'] > current_data['open'] and  # Current green candle
                    current_data['close'] > prev_data['open'] and  # Engulfs previous high
                    current_data['open'] < prev_data['close']):  # Opens below previous close
                    setup_reasons.append('bullish_engulfing')
                    score += 2
            
            # Multi-timeframe context bonus
            if timeframe == 'daily':
                # Daily setup gets bonus points
                score += 1
                setup_reasons.append('daily_timeframe_entry')
            elif timeframe == 'weekly':
                # Weekly setup indicates longer-term opportunity
                if score > 0:  # Only if other conditions met
                    score += 2
                    setup_reasons.append('weekly_timeframe_context')
            
            # Quality assessment
            if score >= 6:
                quality = 'excellent'
            elif score >= 4:
                quality = 'good'
            elif score >= 2:
                quality = 'fair'
            else:
                quality = 'poor'
            
            return {
                'quality': quality,
                'score': score,
                'reasons': setup_reasons
            }
            
        except Exception as e:
            logger.error(f"Error in reversion setup analysis: {e}")
            return {'quality': 'poor', 'score': 0, 'reasons': []}

    def get_dip_buying_alignment_score(self, daily_analysis, weekly_analysis):
        """
        Calculate alignment score for dip-buying opportunities
        Returns score from 0-10 where higher = better dip-buying setup
        """
        if not daily_analysis or not weekly_analysis:
            return 0
            
        try:
            score = 0
            max_score = 10
            
            # Daily oversold condition (3 points max - PRIMARY SIGNAL)
            daily_oversold = daily_analysis['oversold_analysis']
            if daily_oversold['severity'] == 'extreme':
                score += 3  # RSI < 20
            elif daily_oversold['severity'] == 'high':
                score += 2  # RSI < 30
            elif daily_oversold['severity'] == 'moderate':
                score += 1  # RSI approaching oversold
            
            # Weekly uptrend context (2 points max)
            # REFINED LOGIC (2025-11-09): Avoid double-counting pullback and support
            # - Weekly trend up and price near support → +2
            # - Weekly trend up but mid-range (not at support) → +1
            # - Weekly trend flat/down → 0
            weekly_oversold = weekly_analysis['oversold_analysis']
            weekly_support = weekly_analysis['support_analysis']
            weekly_reversion = weekly_analysis['reversion_setup']
            
            # Check if weekly trend is up
            is_weekly_uptrend = 'above_ema_uptrend' in weekly_reversion.get('reasons', [])
            
            if is_weekly_uptrend:
                # Weekly trend is up - check if price is near support
                support_quality = weekly_support.get('quality', 'none')
                support_distance = weekly_support.get('distance_pct', 999)
                
                # Price is "near support" if:
                # - Support quality is strong/moderate AND
                # - Distance to support is <= 5% (close to support level)
                is_near_support = (
                    support_quality in ['strong', 'moderate'] and
                    support_distance <= 5.0
                )
                
                if is_near_support:
                    score += 2  # Weekly trend up and price near support - perfect setup
                else:
                    score += 1  # Weekly trend up but mid-range (not at support) - still good
            # If weekly trend is flat/down, score += 0 (no points)
            
            # Support level confluence (2 points max)
            daily_support = daily_analysis['support_analysis']
            if daily_support['quality'] == 'strong' and daily_support['distance_pct'] <= 3:
                score += 2  # Very close to strong support
            elif daily_support['quality'] in ['strong', 'moderate'] and daily_support['distance_pct'] <= 5:
                score += 1  # Close to good support
            
            # Volume exhaustion signals (2 points max)
            daily_volume = daily_analysis['volume_exhaustion']
            weekly_volume = weekly_analysis['volume_exhaustion']
            
            volume_score = daily_volume['exhaustion_score'] + weekly_volume['exhaustion_score']
            if volume_score >= 3:
                score += 2  # Strong volume exhaustion
            elif volume_score >= 1:
                score += 1  # Some volume exhaustion
            
            # Selling pressure exhaustion (1 point max)
            daily_selling = daily_analysis['selling_pressure']
            if daily_selling['exhaustion_score'] >= 1:
                score += 1
                
            # Reversion setup quality bonus (1 point max)
            daily_reversion = daily_analysis['reversion_setup']
            if daily_reversion['quality'] in ['excellent', 'good']:
                score += 1
                
            return min(score, max_score)
            
        except Exception as e:
            logger.error(f"Error calculating dip-buying alignment score: {e}")
            return 0
            
    def get_dip_buying_confirmation(self, daily_data, weekly_data):
        """
        Complete multi-timeframe analysis for dip-buying opportunities
        """
        daily_analysis = self.analyze_dip_conditions(daily_data, 'daily')
        
        # Handle case where weekly data might be unavailable
        if weekly_data is not None:
            weekly_analysis = self.analyze_dip_conditions(weekly_data, 'weekly')
        else:
            logger.warning("Weekly data unavailable, using daily-only analysis")
            weekly_analysis = None
        
        alignment_score = self.get_dip_buying_alignment_score(daily_analysis, weekly_analysis)
        
        # Overall uptrend dip-buying assessment
        # Adjust thresholds if weekly analysis is missing
        if weekly_analysis is None:
            # Lower thresholds when only daily analysis available
            if alignment_score >= 5:
                confirmation = 'good_uptrend_dip'        # Daily-only good setup
            elif alignment_score >= 3:
                confirmation = 'fair_uptrend_dip'        # Daily-only fair setup
            elif alignment_score >= 1:
                confirmation = 'weak_uptrend_dip'        # Daily-only weak setup
            else:
                confirmation = 'poor_uptrend_dip'        # Poor daily setup
        else:
            # Standard thresholds with full MTF analysis
            if alignment_score >= 8:
                confirmation = 'excellent_uptrend_dip'    # RSI<30 + strong uptrend + support
            elif alignment_score >= 6:
                confirmation = 'good_uptrend_dip'        # RSI<30 + uptrend context
            elif alignment_score >= 4:
                confirmation = 'fair_uptrend_dip'        # RSI<30 + some uptrend signs
            elif alignment_score >= 2:
                confirmation = 'weak_uptrend_dip'        # Marginal uptrend dip
            else:
                confirmation = 'poor_uptrend_dip'        # Avoid - not in uptrend
            
        return {
            'daily_analysis': daily_analysis,
            'weekly_analysis': weekly_analysis,
            'alignment_score': alignment_score,
            'confirmation': confirmation
        }
