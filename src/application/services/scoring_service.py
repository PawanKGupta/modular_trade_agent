"""
Scoring Service

Calculates various scores for stock analysis results.
"""

from typing import Dict, Any, Optional


class ScoringService:
    """
    Service for calculating analysis scores
    
    Provides methods to calculate:
    - Strength scores based on signals and justifications
    - Trading priority scores for ranking
    - Combined scores (current + historical)
    """
    
    def compute_strength_score(self, analysis_data: Dict[str, Any]) -> float:
        """
        Compute signal strength score
        
        Args:
            analysis_data: Analysis result dictionary
            
        Returns:
            Strength score (0-25)
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
                    if rsi_val < 30:
                        score += 1
                    if rsi_val < 20:
                        score += 1
                except Exception:
                    pass
            elif j == 'excellent_uptrend_dip_confirmation':
                score += 8
            elif j == 'good_uptrend_dip_confirmation':
                score += 5
            elif j == 'fair_uptrend_dip_confirmation':
                score += 3

        # Additional dip-buying timeframe analysis scoring
        if timeframe_analysis:
            alignment_score = timeframe_analysis.get('alignment_score', 0)
            
            # Bonus points for dip-buying alignment score
            if alignment_score >= 8:
                score += 4
            elif alignment_score >= 6:
                score += 3
            elif alignment_score >= 4:
                score += 2
            elif alignment_score >= 2:
                score += 1
            
            # Analyze dip-buying specific components
            daily_analysis = timeframe_analysis.get('daily_analysis', {})
            weekly_analysis = timeframe_analysis.get('weekly_analysis', {})
            
            if daily_analysis and weekly_analysis:
                # Daily oversold condition
                daily_oversold = daily_analysis.get('oversold_analysis', {})
                if daily_oversold.get('severity') == 'extreme':
                    score += 3  # RSI < 20
                elif daily_oversold.get('severity') == 'high':
                    score += 2  # RSI < 30
                
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

        return min(score, 25)  # Cap maximum score at 25
    
    def compute_trading_priority_score(self, stock_data: Dict[str, Any]) -> float:
        """
        Compute trading priority score for ranking candidates
        
        Args:
            stock_data: Stock analysis data
            
        Returns:
            Priority score (0-100+)
        """
        try:
            if stock_data is None or not isinstance(stock_data, dict):
                return 0
            
            priority_score = 0
            
            # 1. Risk-Reward Ratio (most important for profitability)
            risk_reward = stock_data.get('risk_reward_ratio', 0)
            if risk_reward >= 4.0:
                priority_score += 40
            elif risk_reward >= 3.0:
                priority_score += 30
            elif risk_reward >= 2.0:
                priority_score += 20
            elif risk_reward >= 1.5:
                priority_score += 10
            
            # 2. RSI Oversold Level (lower = better for dip buying)
            rsi = stock_data.get('rsi', 50)
            if rsi <= 15:
                priority_score += 25  # Extremely oversold
            elif rsi <= 20:
                priority_score += 20  # Very oversold
            elif rsi <= 25:
                priority_score += 15  # Oversold
            elif rsi <= 30:
                priority_score += 10  # Near oversold
            
            # 3. Volume Strength (higher = more conviction)
            volume_multiplier = stock_data.get('volume_multiplier', 1.0)
            if volume_multiplier >= 4.0:
                priority_score += 20
            elif volume_multiplier >= 2.0:
                priority_score += 15
            elif volume_multiplier >= 1.5:
                priority_score += 10
            elif volume_multiplier >= 1.2:
                priority_score += 5
            
            # 4. MTF Alignment Score
            timeframe_analysis = stock_data.get('timeframe_analysis', {})
            alignment_score = timeframe_analysis.get('alignment_score', 0)
            priority_score += min(alignment_score, 10)  # Cap at 10 points
            
            # 5. PE Ratio (lower = better value, but cap the bonus)
            pe = stock_data.get('pe', 100)
            if pe and pe > 0:
                if pe <= 15:
                    priority_score += 10
                elif pe <= 25:
                    priority_score += 5
                elif pe <= 35:
                    priority_score += 2
                elif pe >= 50:
                    priority_score -= 5  # Penalty for expensive stocks
            
            # 6. Backtest Performance (if available)
            backtest_score = stock_data.get('backtest_score', 0)
            if backtest_score >= 40:
                priority_score += 15
            elif backtest_score >= 30:
                priority_score += 10
            elif backtest_score >= 20:
                priority_score += 5
            
            return priority_score
            
        except Exception as e:
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
