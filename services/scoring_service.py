"""
Scoring Service

Calculates signal strength scores for stock analysis results.
Migrated from core/scoring.py to service layer (Phase 4).

This service can be used independently or as part of the analysis pipeline.
"""

from typing import Dict, Any, Optional
import logging

from utils.logger import logger
from config.strategy_config import StrategyConfig


class ScoringService:
    """
    Service for calculating signal strength scores
    
    Provides methods to calculate:
    - Strength scores based on signals and justifications
    - Trading priority scores for ranking
    - Combined scores (current + historical)
    
    This is a service layer wrapper around the core scoring logic,
    providing dependency injection and better testability.
    """
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        Initialize scoring service
        
        Args:
            config: StrategyConfig instance (uses default if None)
        """
        self.config = config if config is not None else StrategyConfig.default()
    
    def compute_strength_score(self, analysis_data: Dict[str, Any]) -> float:
        """
        Compute signal strength score based on verdict, patterns, and timeframe analysis.
        
        This method migrates the logic from core.scoring.compute_strength_score().
        
        Args:
            analysis_data: Analysis result dictionary containing:
                - verdict: str (strong_buy/buy/watch/avoid)
                - justification: List[str]
                - timeframe_analysis: Dict (optional)
                - chart_quality: Dict (optional) - chart quality analysis with score and status
            
        Returns:
            Strength score (0-25), or -1 for non-buy verdicts
        """
        score = 0
        verdict = analysis_data.get('verdict')
        
        # Base score based on verdict type
        if verdict == 'strong_buy':
            score = 10  # Strong baseline for strong buys
        elif verdict == 'buy':
            score = 5   # Standard baseline for buys
        else:
            return -1   # No scoring for non-buy verdicts

        justifications = analysis_data.get('justification', [])
        timeframe_analysis = analysis_data.get('timeframe_analysis')

        # Pattern-based scoring
        for j in justifications:
            if j.startswith('pattern:'):
                patterns = j.replace('pattern:', '').split(',')
                score += len(patterns) * 2
            elif j == 'volume_strong':
                score += 1
            elif j.startswith('rsi:'):
                try:
                    rsi_val = float(j.split(':')[1])
                    # Use configurable RSI thresholds
                    if rsi_val < self.config.rsi_oversold:  # Default: 30
                        score += 1
                    if rsi_val < self.config.rsi_extreme_oversold:  # Default: 20
                        score += 1
                except Exception:
                    pass
            elif j == 'excellent_uptrend_dip_confirmation':
                score += 8  # Highest bonus for excellent uptrend dip (RSI<30 + strong uptrend)
            elif j == 'good_uptrend_dip_confirmation':
                score += 5  # Strong bonus for good uptrend dip
            elif j == 'fair_uptrend_dip_confirmation':
                score += 3  # Moderate bonus for fair uptrend dip

        # Additional dip-buying timeframe analysis scoring
        if timeframe_analysis:
            alignment_score = timeframe_analysis.get('alignment_score', 0)
            confirmation = timeframe_analysis.get('confirmation', 'poor_dip')
            
            # Bonus points for dip-buying alignment score
            if alignment_score >= 8:
                score += 4  # Excellent dip bonus
            elif alignment_score >= 6:
                score += 3  # Good dip bonus
            elif alignment_score >= 4:
                score += 2  # Fair dip bonus
            elif alignment_score >= 2:
                score += 1  # Weak dip bonus
            
            # Analyze dip-buying specific components
            daily_analysis = timeframe_analysis.get('daily_analysis', {})
            weekly_analysis = timeframe_analysis.get('weekly_analysis', {})
            
            if daily_analysis and weekly_analysis:
                # Daily oversold condition (primary signal)
                # Uses configurable thresholds: extreme = rsi_extreme_oversold, high = rsi_oversold
                daily_oversold = daily_analysis.get('oversold_analysis', {})
                if daily_oversold.get('severity') == 'extreme':
                    score += 3  # RSI < config.rsi_extreme_oversold (default: 20)
                elif daily_oversold.get('severity') == 'high':
                    score += 2  # RSI < config.rsi_oversold (default: 30)
                
                # Support level confluence
                daily_support = daily_analysis.get('support_analysis', {})
                if daily_support.get('quality') == 'strong':
                    score += 2
                elif daily_support.get('quality') == 'moderate':
                    score += 1
                    
                # Volume exhaustion signals
                daily_volume = daily_analysis.get('volume_exhaustion', {})
                volume_exhaustion_score = daily_volume.get('exhaustion_score', 0)
                if volume_exhaustion_score >= 2:
                    score += 2
                elif volume_exhaustion_score >= 1:
                    score += 1
        
        # Chart quality bonus (cleaner charts = higher score)
        chart_quality = analysis_data.get('chart_quality', {})
        if chart_quality and isinstance(chart_quality, dict):
            chart_score = chart_quality.get('score', 0)
            chart_status = chart_quality.get('status', 'poor')
            
            # Bonus for clean charts (only if passed hard filter)
            if chart_status == 'clean' and chart_score >= 80:
                score += 3  # Excellent chart quality bonus
            elif chart_status == 'acceptable' and chart_score >= 70:
                score += 2  # Good chart quality bonus
            elif chart_status == 'acceptable' and chart_score >= 60:
                score += 1  # Acceptable chart quality bonus
            # Poor charts (score < 60) should already be filtered by hard filter

        return min(score, 25)  # Cap maximum score at 25
    
    def compute_trading_priority_score(self, stock_data: Dict[str, Any]) -> float:
        """
        Compute trading priority score for ranking buy candidates.
        
        Higher score = higher priority for trading.
        
        Args:
            stock_data: Stock analysis data containing:
                - risk_reward_ratio: float
                - rsi: float
                - volume_multiplier: float
                - timeframe_analysis: Dict
                - pe: float (optional)
                - backtest_score: float (optional)
                - chart_quality: Dict (optional) - chart quality analysis with score and status
        
        Returns:
            Priority score (0-100+)
        """
        try:
            if stock_data is None or not isinstance(stock_data, dict):
                return 0
            
            priority_score = 0
            
            # 1. Risk-Reward Ratio (most important for profitability)
            risk_reward = stock_data.get('risk_reward_ratio')
            if risk_reward is not None and risk_reward >= 4.0:
                priority_score += 40
            elif risk_reward is not None and risk_reward >= 3.0:
                priority_score += 30
            elif risk_reward is not None and risk_reward >= 2.0:
                priority_score += 20
            elif risk_reward is not None and risk_reward >= 1.5:
                priority_score += 10
            
            # 2. RSI Oversold Level (lower = better for dip buying)
            rsi = stock_data.get('rsi')
            if rsi is not None:
                if rsi <= 15:
                    priority_score += 25  # Extremely oversold
                elif rsi <= 20:
                    priority_score += 20  # Very oversold
                elif rsi <= 25:
                    priority_score += 15  # Oversold
                elif rsi <= 30:
                    priority_score += 10  # Near oversold
            
            # 3. Volume Strength (higher = more conviction)
            volume_multiplier = stock_data.get('volume_multiplier')
            if volume_multiplier is not None:
                if volume_multiplier >= 4.0:
                    priority_score += 20
                elif volume_multiplier >= 2.0:
                    priority_score += 15
                elif volume_multiplier >= 1.5:
                    priority_score += 10
                elif volume_multiplier >= 1.2:
                    priority_score += 5
            
            # 4. MTF Alignment Score
            timeframe_analysis = stock_data.get('timeframe_analysis', {}) or {}
            alignment_score = timeframe_analysis.get('alignment_score') if isinstance(timeframe_analysis, dict) else None
            if alignment_score is not None:
                priority_score += min(alignment_score, 10)  # Cap at 10 points
            
            # 5. PE Ratio (lower = better value, but cap the bonus)
            pe = stock_data.get('pe')
            if pe is not None and pe > 0:
                if pe <= 15:
                    priority_score += 10
                elif pe <= 25:
                    priority_score += 5
                elif pe <= 35:
                    priority_score += 2
                elif pe >= 50:
                    priority_score -= 5  # Penalty for expensive stocks
            
            # 6. Backtest Performance (if available)
            backtest_score = stock_data.get('backtest_score')
            if backtest_score is not None and backtest_score >= 40:
                priority_score += 15
            elif backtest_score is not None and backtest_score >= 30:
                priority_score += 10
            elif backtest_score is not None and backtest_score >= 20:
                priority_score += 5
            
            # 7. Chart Quality (cleaner charts = higher priority)
            chart_quality = stock_data.get('chart_quality', {})
            if chart_quality and isinstance(chart_quality, dict):
                chart_score = chart_quality.get('score')
                chart_status = chart_quality.get('status', 'poor')
                
                # Ensure chart_score is a number (handle None case)
                if chart_score is None:
                    chart_score = 0
                
                # Prioritize cleaner charts (only if passed hard filter)
                if chart_status == 'clean' and chart_score >= 80:
                    priority_score += 10  # Excellent chart quality
                elif chart_status == 'acceptable' and chart_score >= 70:
                    priority_score += 7   # Good chart quality
                elif chart_status == 'acceptable' and chart_score >= 60:
                    priority_score += 5   # Acceptable chart quality
                # Poor charts (score < 60) should already be filtered by hard filter
            
            return priority_score
            
        except Exception as e:
            logger.warning(f"Error computing priority score: {e}")
            # Fallback to combined/strength score
            if stock_data is None:
                return 0
            return stock_data.get('combined_score', stock_data.get('strength_score', 0))
    
    def compute_combined_score(
        self,
        current_score: float,
        backtest_score: float,
        current_weight: float = 0.5,
        backtest_weight: float = 0.5
    ) -> float:
        """
        Compute combined score from current and historical analysis
        
        Args:
            current_score: Current analysis score
            backtest_score: Historical backtest score
            current_weight: Weight for current score (0-1)
            backtest_weight: Weight for backtest score (0-1)
            
        Returns:
            Combined score
        """
        return (current_score * current_weight) + (backtest_score * backtest_weight)


# Backward compatibility function
def compute_strength_score(entry: Dict[str, Any]) -> float:
    """
    Backward compatibility wrapper for core.scoring.compute_strength_score()
    
    This function maintains compatibility with existing code while delegating
    to the new ScoringService.
    
    Args:
        entry: Analysis result dictionary
        
    Returns:
        Strength score (0-25), or -1 for non-buy verdicts
    """
    service = ScoringService()
    return service.compute_strength_score(entry)

