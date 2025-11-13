"""
ML Feedback Service

Collects actual trade outcomes and feeds back into training pipeline.

Phase 4 Feature - Feedback Loop
"""

import csv
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from utils.logger import logger


class MLFeedbackService:
    """
    Service for collecting feedback on ML predictions
    
    Tracks actual trade outcomes and feeds back to training pipeline.
    """
    
    def __init__(self, feedback_file: str = "data/ml_feedback.csv"):
        """
        Initialize feedback service
        
        Args:
            feedback_file: Path to feedback CSV file
        """
        self.feedback_file = Path(feedback_file)
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"MLFeedbackService initialized: {self.feedback_file}")
    
    def record_outcome(
        self,
        ticker: str,
        prediction_date: str,
        ml_verdict: str,
        rule_verdict: str,
        final_verdict: str,
        actual_outcome: str,  # 'profit', 'loss', 'neutral'
        pnl_pct: Optional[float] = None,
        holding_days: Optional[int] = None,
        notes: str = ""
    ) -> None:
        """
        Record actual trade outcome for a prediction
        
        Args:
            ticker: Stock ticker
            prediction_date: Date of prediction
            ml_verdict: ML prediction
            rule_verdict: Rule-based verdict
            final_verdict: Final verdict used
            actual_outcome: Actual result ('profit', 'loss', 'neutral')
            pnl_pct: Profit/loss percentage
            holding_days: Days held
            notes: Additional notes
        """
        try:
            # Check if file exists for header
            file_exists = self.feedback_file.exists()
            
            with open(self.feedback_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'timestamp', 'ticker', 'prediction_date', 'ml_verdict',
                    'rule_verdict', 'final_verdict', 'actual_outcome',
                    'pnl_pct', 'holding_days', 'notes'
                ])
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow({
                    'timestamp': datetime.now().isoformat(),
                    'ticker': ticker,
                    'prediction_date': prediction_date,
                    'ml_verdict': ml_verdict,
                    'rule_verdict': rule_verdict,
                    'final_verdict': final_verdict,
                    'actual_outcome': actual_outcome,
                    'pnl_pct': f"{pnl_pct:.2f}" if pnl_pct is not None else '',
                    'holding_days': holding_days or '',
                    'notes': notes
                })
            
            logger.info(
                f"Recorded feedback for {ticker}: {ml_verdict} -> {actual_outcome} "
                f"({pnl_pct:.1f}%)" if pnl_pct else ""
            )
            
        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
    
    def get_feedback_summary(self) -> Dict[str, Any]:
        """
        Get summary of feedback collected
        
        Returns:
            Dictionary with feedback statistics
        """
        if not self.feedback_file.exists():
            return {
                'total_feedback': 0,
                'ml_accuracy': 0.0,
                'rule_accuracy': 0.0
            }
        
        try:
            with open(self.feedback_file, 'r') as f:
                reader = csv.DictReader(f)
                feedback_list = list(reader)
            
            total = len(feedback_list)
            
            if total == 0:
                return {
                    'total_feedback': 0,
                    'ml_accuracy': 0.0,
                    'rule_accuracy': 0.0
                }
            
            # Calculate accuracies (simplified)
            ml_correct = sum(1 for row in feedback_list 
                           if self._is_correct(row['ml_verdict'], row['actual_outcome']))
            rule_correct = sum(1 for row in feedback_list
                             if self._is_correct(row['rule_verdict'], row['actual_outcome']))
            
            return {
                'total_feedback': total,
                'ml_accuracy': ml_correct / total if total > 0 else 0.0,
                'rule_accuracy': rule_correct / total if total > 0 else 0.0,
                'ml_better': ml_correct > rule_correct
            }
            
        except Exception as e:
            logger.error(f"Failed to get feedback summary: {e}")
            return {'total_feedback': 0, 'ml_accuracy': 0.0, 'rule_accuracy': 0.0}
    
    def _is_correct(self, verdict: str, outcome: str) -> bool:
        """
        Check if verdict was correct based on outcome
        
        Simplified logic:
        - strong_buy/buy correct if profit
        - avoid correct if loss or neutral
        - watch is neutral
        """
        if outcome == 'profit':
            return verdict in ['strong_buy', 'buy']
        elif outcome == 'loss':
            return verdict == 'avoid'
        else:  # neutral
            return verdict in ['watch', 'avoid']


# Global singleton
_ml_feedback_service = None


def get_ml_feedback_service() -> MLFeedbackService:
    """Get or create the global feedback service instance"""
    global _ml_feedback_service
    if _ml_feedback_service is None:
        _ml_feedback_service = MLFeedbackService()
    return _ml_feedback_service
