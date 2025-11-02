"""
ML Retraining Service

Service for automatic model retraining triggered by events.

Phase 4 Feature - Continuous Learning
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

from services.event_bus import EventBus, Event, EventType, get_event_bus
from services.ml_training_service import MLTrainingService
from utils.logger import logger


class MLRetrainingService:
    """
    Service for automatic ML model retraining
    
    Features:
    - Listen to backtest completion events
    - Trigger automatic retraining
    - Track retraining frequency
    - Manage model versions
    - Prevent excessive retraining
    """
    
    def __init__(
        self,
        training_data_path: str = "data/ml_training_data.csv",
        min_retraining_interval_hours: int = 24,
        min_new_samples: int = 100,
        auto_backup: bool = True
    ):
        """
        Initialize ML retraining service
        
        Args:
            training_data_path: Path to training data
            min_retraining_interval_hours: Minimum hours between retraining
            min_new_samples: Minimum new samples required for retraining
            auto_backup: Whether to backup old models
        """
        self.training_data_path = training_data_path
        self.min_retraining_interval = timedelta(hours=min_retraining_interval_hours)
        self.min_new_samples = min_new_samples
        self.auto_backup = auto_backup
        
        self.last_retraining_time: Optional[datetime] = None
        self.retraining_count = 0
        
        # Track retraining history
        self.history_file = Path("logs/ml_retraining_history.txt")
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("MLRetrainingService initialized")
    
    def setup_listeners(self, event_bus: Optional[EventBus] = None) -> None:
        """
        Setup event listeners for automatic retraining
        
        Args:
            event_bus: Event bus instance (uses global if None)
        """
        bus = event_bus or get_event_bus()
        
        # Listen to backtest completion events
        bus.subscribe(EventType.BACKTEST_COMPLETED, self._on_backtest_complete)
        
        # Listen to analysis batch completion (bulk analysis)
        bus.subscribe(EventType.ANALYSIS_COMPLETED, self._on_analysis_batch_complete)
        
        logger.info("MLRetrainingService event listeners registered")
    
    def _on_backtest_complete(self, event: Event) -> None:
        """
        Handle backtest completion event
        
        Args:
            event: Backtest completion event
        """
        logger.info(f"Backtest completed: {event.data}")
        
        # Check if retraining should be triggered
        if self._should_retrain():
            logger.info("Triggering automatic model retraining...")
            self.retrain_models(reason="Backtest completed")
        else:
            logger.info("Skipping retraining (conditions not met)")
    
    def _on_analysis_batch_complete(self, event: Event) -> None:
        """
        Handle analysis batch completion event
        
        Args:
            event: Analysis completion event
        """
        # Only retrain after large batches
        if event.data and event.data.get('batch_size', 0) >= 50:
            logger.info(f"Large analysis batch completed: {event.data.get('batch_size')} stocks")
            
            if self._should_retrain():
                logger.info("Triggering automatic model retraining...")
                self.retrain_models(reason=f"Analysis batch ({event.data.get('batch_size')} stocks)")
    
    def _should_retrain(self) -> bool:
        """
        Check if model should be retrained
        
        Returns:
            True if retraining should happen
        """
        # Check time since last retraining
        if self.last_retraining_time:
            time_since_last = datetime.now() - self.last_retraining_time
            if time_since_last < self.min_retraining_interval:
                logger.debug(
                    f"Too soon to retrain: {time_since_last} < {self.min_retraining_interval}"
                )
                return False
        
        # Check if training data file exists
        if not Path(self.training_data_path).exists():
            logger.warning(f"Training data not found: {self.training_data_path}")
            return False
        
        # Could add more checks here:
        # - Check file size
        # - Check number of new samples since last training
        # - Check model drift metrics
        
        return True
    
    def retrain_models(
        self,
        reason: str = "Manual trigger",
        model_types: list = ["random_forest"]
    ) -> Dict[str, Any]:
        """
        Retrain ML models
        
        Args:
            reason: Reason for retraining (for logging)
            model_types: List of model types to train
            
        Returns:
            Dictionary with retraining results
        """
        logger.info(f"Starting model retraining: {reason}")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'models_trained': [],
            'errors': []
        }
        
        try:
            # Backup old models if enabled
            if self.auto_backup:
                self._backup_models()
            
            # Initialize training service
            trainer = MLTrainingService()
            
            # Train verdict classifier
            for model_type in model_types:
                try:
                    logger.info(f"Training {model_type} verdict classifier...")
                    
                    model_path = trainer.train_verdict_classifier(
                        training_data_path=self.training_data_path,
                        model_type=model_type,
                        test_size=0.2
                    )
                    
                    results['models_trained'].append({
                        'type': 'verdict_classifier',
                        'model_type': model_type,
                        'path': model_path
                    })
                    
                    logger.info(f"✅ {model_type} model trained: {model_path}")
                    
                except Exception as e:
                    error_msg = f"Failed to train {model_type}: {e}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
            
            # Update retraining metadata
            self.last_retraining_time = datetime.now()
            self.retraining_count += 1
            
            # Log to history
            self._log_retraining(results)
            
            # Publish event
            get_event_bus().publish(Event(
                event_type=EventType.ANALYSIS_COMPLETED,  # Reuse for now
                data={
                    'event_type': 'ml_retraining_completed',
                    'reason': reason,
                    'models_trained': len(results['models_trained']),
                    'errors': len(results['errors'])
                },
                source='MLRetrainingService'
            ))
            
            logger.info(
                f"✅ Model retraining completed: "
                f"{len(results['models_trained'])} trained, {len(results['errors'])} errors"
            )
            
        except Exception as e:
            error_msg = f"Retraining failed: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        return results
    
    def _backup_models(self) -> None:
        """Backup existing models before retraining"""
        try:
            models_dir = Path("models")
            if not models_dir.exists():
                return
            
            # Create backup directory
            backup_dir = Path("models/backups")
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            for model_file in models_dir.glob("*.pkl"):
                backup_path = backup_dir / f"{model_file.stem}_{timestamp}.pkl"
                
                # Copy file
                import shutil
                shutil.copy2(model_file, backup_path)
                
                logger.info(f"Backed up model: {model_file.name} -> {backup_path.name}")
            
        except Exception as e:
            logger.warning(f"Failed to backup models: {e}")
    
    def _log_retraining(self, results: Dict[str, Any]) -> None:
        """Log retraining to history file"""
        try:
            with open(self.history_file, 'a') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Retraining #{self.retraining_count}\n")
                f.write(f"Timestamp: {results['timestamp']}\n")
                f.write(f"Reason: {results['reason']}\n")
                f.write(f"Models trained: {len(results['models_trained'])}\n")
                
                for model in results['models_trained']:
                    f.write(f"  - {model['type']} ({model['model_type']}): {model['path']}\n")
                
                if results['errors']:
                    f.write(f"Errors: {len(results['errors'])}\n")
                    for error in results['errors']:
                        f.write(f"  - {error}\n")
                
                f.write(f"{'='*60}\n")
                
        except Exception as e:
            logger.debug(f"Failed to log retraining history: {e}")
    
    def get_retraining_stats(self) -> Dict[str, Any]:
        """
        Get retraining statistics
        
        Returns:
            Dictionary with retraining stats
        """
        return {
            'total_retrainings': self.retraining_count,
            'last_retraining': self.last_retraining_time.isoformat() if self.last_retraining_time else None,
            'min_interval_hours': self.min_retraining_interval.total_seconds() / 3600,
            'can_retrain_now': self._should_retrain()
        }


# Global singleton
_ml_retraining_service = None


def get_ml_retraining_service() -> MLRetrainingService:
    """Get or create the global ML retraining service instance"""
    global _ml_retraining_service
    if _ml_retraining_service is None:
        _ml_retraining_service = MLRetrainingService()
    return _ml_retraining_service


def setup_ml_retraining() -> None:
    """
    Setup automatic ML retraining
    
    Call this during application initialization to enable
    event-driven model retraining.
    """
    service = get_ml_retraining_service()
    service.setup_listeners()
    logger.info("✅ Automatic ML retraining enabled")
