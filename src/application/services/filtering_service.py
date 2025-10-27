"""
Filtering Service

Filters and validates stock analysis results.
"""

from typing import List, Dict, Any


class FilteringService:
    """
    Service for filtering analysis results
    
    Provides methods to:
    - Filter buyable candidates
    - Apply score thresholds
    - Remove invalid/error results
    """
    
    def __init__(self, min_combined_score: float = 25.0):
        """
        Initialize filtering service
        
        Args:
            min_combined_score: Minimum combined score for filtering
        """
        self.min_combined_score = min_combined_score
    
    def filter_buy_candidates(
        self,
        results: List[Dict[str, Any]],
        enable_backtest_scoring: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Filter for buy/strong_buy candidates
        
        Args:
            results: List of analysis results
            enable_backtest_scoring: Whether backtest scoring is enabled
            
        Returns:
            Filtered list of buyable stocks
        """
        buyable = []
        
        for result in results:
            if result is None:
                continue
            
            # Use final_verdict if backtest scoring enabled
            if enable_backtest_scoring:
                verdict = result.get('final_verdict', result.get('verdict'))
            else:
                verdict = result.get('verdict')
            
            # Check if buyable
            if verdict in ['buy', 'strong_buy']:
                # Check status
                if result.get('status') != 'success':
                    continue
                
                # Apply score threshold if backtest scoring enabled
                if enable_backtest_scoring:
                    combined_score = result.get('combined_score', 0)
                    if combined_score < self.min_combined_score:
                        continue
                
                buyable.append(result)
        
        return buyable
    
    def filter_strong_buy_candidates(
        self,
        results: List[Dict[str, Any]],
        enable_backtest_scoring: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Filter for strong_buy candidates only
        
        Args:
            results: List of analysis results
            enable_backtest_scoring: Whether backtest scoring is enabled
            
        Returns:
            Filtered list of strong buy stocks
        """
        strong_buys = []
        
        for result in results:
            if result is None:
                continue
            
            # Use final_verdict if backtest scoring enabled
            if enable_backtest_scoring:
                verdict = result.get('final_verdict', result.get('verdict'))
            else:
                verdict = result.get('verdict')
            
            # Check if strong buy
            if verdict == 'strong_buy':
                # Check status
                if result.get('status') != 'success':
                    continue
                
                # Apply score threshold if backtest scoring enabled
                if enable_backtest_scoring:
                    combined_score = result.get('combined_score', 0)
                    if combined_score < self.min_combined_score:
                        continue
                
                strong_buys.append(result)
        
        return strong_buys
    
    def remove_invalid_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove None and invalid results
        
        Args:
            results: List of analysis results
            
        Returns:
            Cleaned list without invalid entries
        """
        return [r for r in results if r is not None and isinstance(r, dict)]
    
    def filter_by_score_threshold(
        self,
        results: List[Dict[str, Any]],
        threshold: float,
        score_key: str = 'combined_score'
    ) -> List[Dict[str, Any]]:
        """
        Filter results by score threshold
        
        Args:
            results: List of analysis results
            threshold: Minimum score threshold
            score_key: Score field to use for filtering
            
        Returns:
            Filtered results above threshold
        """
        return [
            r for r in results 
            if r.get(score_key, 0) >= threshold
        ]
    
    def exclude_tickers(
        self,
        results: List[Dict[str, Any]],
        exclude_list: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Exclude specific tickers from results
        
        Args:
            results: List of analysis results
            exclude_list: List of tickers to exclude
            
        Returns:
            Results without excluded tickers
        """
        exclude_set = {t.upper() for t in exclude_list}
        return [
            r for r in results 
            if r.get('ticker', '').upper() not in exclude_set
        ]
    
    def get_error_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Get all results with errors
        
        Args:
            results: List of analysis results
            
        Returns:
            Results that encountered errors
        """
        return [
            r for r in results 
            if r.get('status') != 'success' or r.get('error')
        ]
