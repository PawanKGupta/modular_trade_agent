"""
ML Logging Service

Service for logging ML predictions, tracking performance metrics,
and monitoring model behavior.

Phase 4 Feature - ML Monitoring and Logging
"""

import os
import json
import csv
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, asdict

from utils.logger import logger


@dataclass
class MLPredictionLog:
    """Data class for ML prediction log entry"""
    timestamp: str
    ticker: str
    ml_verdict: Optional[str]
    ml_confidence: float
    rule_verdict: str
    final_verdict: str
    verdict_source: str  # 'ml' or 'rule_based'
    features: Dict[str, Any]
    indicators: Dict[str, Any]
    agreement: bool  # ML and rule-based agree
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class MLLoggingService:
    """
    Service for logging and monitoring ML predictions
    
    Features:
    - Log every ML prediction with metadata
    - Track agreement/disagreement with rule-based
    - Compute performance metrics
    - Detect model drift
    - Generate monitoring reports
    """
    
    def __init__(self, log_dir: str = "logs/ml_predictions"):
        """
        Initialize ML logging service
        
        Args:
            log_dir: Directory to store prediction logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Daily log file
        today = datetime.now().strftime("%Y-%m-%d")
        self.log_file = self.log_dir / f"predictions_{today}.jsonl"
        self.csv_file = self.log_dir / f"predictions_{today}.csv"
        
        # Metrics tracking
        self.metrics = {
            'total_predictions': 0,
            'ml_predictions_used': 0,
            'rule_predictions_used': 0,
            'agreements': 0,
            'disagreements': 0,
            'confidence_sum': 0.0,
            'verdicts': {'strong_buy': 0, 'buy': 0, 'watch': 0, 'avoid': 0}
        }
        
        logger.info(f"MLLoggingService initialized with log_dir: {self.log_dir}")
    
    def log_prediction(
        self,
        ticker: str,
        ml_verdict: Optional[str],
        ml_confidence: float,
        rule_verdict: str,
        final_verdict: str,
        verdict_source: str,
        features: Optional[Dict[str, Any]] = None,
        indicators: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an ML prediction
        
        Args:
            ticker: Stock ticker
            ml_verdict: ML model's verdict
            ml_confidence: ML confidence score
            rule_verdict: Rule-based verdict
            final_verdict: Final verdict used
            verdict_source: Source of final verdict ('ml' or 'rule_based')
            features: Features used for ML prediction
            indicators: Technical indicators
        """
        try:
            # Create log entry
            log_entry = MLPredictionLog(
                timestamp=datetime.now().isoformat(),
                ticker=ticker,
                ml_verdict=ml_verdict,
                ml_confidence=ml_confidence,
                rule_verdict=rule_verdict,
                final_verdict=final_verdict,
                verdict_source=verdict_source,
                features=features or {},
                indicators=indicators or {},
                agreement=(ml_verdict == rule_verdict) if ml_verdict else False
            )
            
            # Log to JSONL file (one JSON object per line)
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry.to_dict()) + '\n')
            
            # Log to CSV file (for easy analysis)
            self._log_to_csv(log_entry)
            
            # Update metrics
            self._update_metrics(log_entry)
            
            logger.debug(
                f"Logged ML prediction for {ticker}: "
                f"ML={ml_verdict}({ml_confidence:.1%}), Rule={rule_verdict}, "
                f"Final={final_verdict}, Source={verdict_source}"
            )
            
        except Exception as e:
            logger.error(f"Failed to log ML prediction: {e}")
    
    def _log_to_csv(self, log_entry: MLPredictionLog) -> None:
        """Log to CSV file for easy analysis"""
        try:
            # Check if file exists to write header
            file_exists = self.csv_file.exists()
            
            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'timestamp', 'ticker', 'ml_verdict', 'ml_confidence',
                    'rule_verdict', 'final_verdict', 'verdict_source', 'agreement'
                ])
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow({
                    'timestamp': log_entry.timestamp,
                    'ticker': log_entry.ticker,
                    'ml_verdict': log_entry.ml_verdict or 'N/A',
                    'ml_confidence': f"{log_entry.ml_confidence:.4f}",
                    'rule_verdict': log_entry.rule_verdict,
                    'final_verdict': log_entry.final_verdict,
                    'verdict_source': log_entry.verdict_source,
                    'agreement': log_entry.agreement
                })
                
        except Exception as e:
            logger.debug(f"Failed to log to CSV: {e}")
    
    def _update_metrics(self, log_entry: MLPredictionLog) -> None:
        """Update performance metrics"""
        self.metrics['total_predictions'] += 1
        
        if log_entry.verdict_source == 'ml':
            self.metrics['ml_predictions_used'] += 1
        else:
            self.metrics['rule_predictions_used'] += 1
        
        if log_entry.agreement:
            self.metrics['agreements'] += 1
        else:
            self.metrics['disagreements'] += 1
        
        if log_entry.ml_verdict:
            self.metrics['confidence_sum'] += log_entry.ml_confidence
        
        if log_entry.final_verdict in self.metrics['verdicts']:
            self.metrics['verdicts'][log_entry.final_verdict] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics
        
        Returns:
            Dictionary of metrics
        """
        total = self.metrics['total_predictions']
        
        if total == 0:
            return {
                'total_predictions': 0,
                'ml_usage_rate': 0.0,
                'agreement_rate': 0.0,
                'avg_confidence': 0.0,
                'verdict_distribution': {}
            }
        
        ml_predictions = self.metrics['ml_predictions_used']
        
        return {
            'total_predictions': total,
            'ml_predictions_used': ml_predictions,
            'rule_predictions_used': self.metrics['rule_predictions_used'],
            'ml_usage_rate': ml_predictions / total if total > 0 else 0.0,
            'agreement_rate': self.metrics['agreements'] / total if total > 0 else 0.0,
            'disagreement_rate': self.metrics['disagreements'] / total if total > 0 else 0.0,
            'avg_confidence': self.metrics['confidence_sum'] / ml_predictions if ml_predictions > 0 else 0.0,
            'verdict_distribution': self.metrics['verdicts'].copy()
        }
    
    def get_recent_predictions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent predictions from log
        
        Args:
            limit: Number of recent predictions to return
            
        Returns:
            List of recent predictions
        """
        predictions = []
        
        try:
            if not self.log_file.exists():
                return predictions
            
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                
            # Get last N lines
            recent_lines = lines[-limit:] if len(lines) > limit else lines
            
            for line in recent_lines:
                try:
                    predictions.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            
        except Exception as e:
            logger.error(f"Failed to read recent predictions: {e}")
        
        return predictions
    
    def generate_report(self) -> str:
        """
        Generate a summary report of ML performance
        
        Returns:
            Formatted report string
        """
        metrics = self.get_metrics()
        
        report = []
        report.append("=" * 60)
        report.append("ML PREDICTION MONITORING REPORT")
        report.append("=" * 60)
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Log File: {self.log_file}")
        report.append("")
        
        report.append("📊 PREDICTION SUMMARY")
        report.append(f"  Total Predictions: {metrics['total_predictions']}")
        report.append(f"  ML Used: {metrics['ml_predictions_used']} ({metrics['ml_usage_rate']:.1%})")
        report.append(f"  Rule-Based Used: {metrics['rule_predictions_used']}")
        report.append("")
        
        report.append("🎯 AGREEMENT METRICS")
        report.append(f"  Agreement Rate: {metrics['agreement_rate']:.1%}")
        report.append(f"  Disagreement Rate: {metrics['disagreement_rate']:.1%}")
        report.append(f"  Avg ML Confidence: {metrics['avg_confidence']:.1%}")
        report.append("")
        
        report.append("📈 VERDICT DISTRIBUTION")
        for verdict, count in metrics['verdict_distribution'].items():
            pct = (count / metrics['total_predictions'] * 100) if metrics['total_predictions'] > 0 else 0
            report.append(f"  {verdict}: {count} ({pct:.1f}%)")
        
        report.append("=" * 60)
        
        return '\n'.join(report)
    
    def detect_drift(self, baseline_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Detect model drift by comparing current metrics to baseline
        
        Args:
            baseline_metrics: Baseline metrics to compare against
            
        Returns:
            Drift detection results
        """
        current_metrics = self.get_metrics()
        
        if not baseline_metrics:
            return {
                'drift_detected': False,
                'message': 'No baseline metrics provided'
            }
        
        drift_detected = False
        warnings = []
        
        # Check confidence drop
        if 'avg_confidence' in baseline_metrics:
            confidence_drop = baseline_metrics['avg_confidence'] - current_metrics['avg_confidence']
            if confidence_drop > 0.1:  # 10% drop
                drift_detected = True
                warnings.append(f"Confidence dropped by {confidence_drop:.1%}")
        
        # Check agreement rate drop
        if 'agreement_rate' in baseline_metrics:
            agreement_drop = baseline_metrics['agreement_rate'] - current_metrics['agreement_rate']
            if agreement_drop > 0.15:  # 15% drop
                drift_detected = True
                warnings.append(f"Agreement rate dropped by {agreement_drop:.1%}")
        
        # Check ML usage drop
        if 'ml_usage_rate' in baseline_metrics:
            usage_drop = baseline_metrics['ml_usage_rate'] - current_metrics['ml_usage_rate']
            if usage_drop > 0.2:  # 20% drop
                drift_detected = True
                warnings.append(f"ML usage dropped by {usage_drop:.1%}")
        
        return {
            'drift_detected': drift_detected,
            'warnings': warnings,
            'current_metrics': current_metrics,
            'baseline_metrics': baseline_metrics
        }


# Global singleton
_ml_logging_service = None


def get_ml_logging_service() -> MLLoggingService:
    """Get or create the global ML logging service instance"""
    global _ml_logging_service
    if _ml_logging_service is None:
        _ml_logging_service = MLLoggingService()
    return _ml_logging_service


def reset_ml_logging_service() -> None:
    """Reset the global ML logging service instance"""
    global _ml_logging_service
    _ml_logging_service = None
