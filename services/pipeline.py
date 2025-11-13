"""
Pipeline Pattern for Analysis Workflow

Provides a pluggable pipeline where analysis steps can be added, removed, 
or reordered without modifying the core logic.

Phase 3 Feature - Pipeline Pattern
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime
import logging

from services.event_bus import EventBus, Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """
    Context object passed through pipeline steps
    
    Holds all data needed for analysis and accumulates results from each step.
    
    Attributes:
        ticker: Stock ticker symbol
        data: Raw market data (OHLCV)
        config: Strategy configuration
        results: Accumulated results from steps
        metadata: Additional metadata
        errors: List of errors encountered
    """
    ticker: str
    data: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    
    def has_error(self) -> bool:
        """Check if any errors occurred"""
        return len(self.errors) > 0
    
    def add_error(self, error: str) -> None:
        """Add an error to the context"""
        self.errors.append(error)
        logger.error(f"Pipeline error for {self.ticker}: {error}")
    
    def set_result(self, key: str, value: Any) -> None:
        """Set a result value"""
        self.results[key] = value
    
    def get_result(self, key: str, default: Any = None) -> Any:
        """Get a result value"""
        return self.results.get(key, default)


class PipelineStep(ABC):
    """
    Abstract base class for pipeline steps
    
    Each step processes the context and can:
    - Read data from context
    - Add results to context
    - Add errors to context
    - Skip execution based on conditions
    """
    
    def __init__(self, name: Optional[str] = None):
        """
        Initialize pipeline step
        
        Args:
            name: Optional name for the step (defaults to class name)
        """
        self.name = name or self.__class__.__name__
        self.enabled = True
    
    @abstractmethod
    def execute(self, context: PipelineContext) -> PipelineContext:
        """
        Execute the step
        
        Args:
            context: Pipeline context
            
        Returns:
            Modified context
        """
        pass
    
    def should_skip(self, context: PipelineContext) -> bool:
        """
        Check if step should be skipped
        
        Args:
            context: Pipeline context
            
        Returns:
            True if step should be skipped
        """
        # Only skip if step is disabled
        # Don't skip due to errors - let each step handle errors gracefully
        return not self.enabled
    
    def __call__(self, context: PipelineContext) -> PipelineContext:
        """
        Execute step with skip logic
        
        Args:
            context: Pipeline context
            
        Returns:
            Modified context
        """
        if self.should_skip(context):
            logger.debug(f"Skipping step: {self.name}")
            return context
        
        logger.debug(f"Executing step: {self.name}")
        
        try:
            return self.execute(context)
        except Exception as e:
            error_msg = f"Error in {self.name}: {str(e)}"
            context.add_error(error_msg)
            logger.exception(error_msg)
            return context


class AnalysisPipeline:
    """
    Analysis Pipeline - Orchestrates analysis steps
    
    Features:
    - Pluggable steps (add/remove/reorder)
    - Event publishing for each step
    - Error handling and recovery
    - Step enable/disable
    - Conditional execution
    
    Usage:
        pipeline = AnalysisPipeline()
        pipeline.add_step(FetchDataStep())
        pipeline.add_step(CalculateIndicatorsStep())
        pipeline.add_step(DetectSignalsStep())
        pipeline.add_step(DetermineVerdictStep())
        
        result = pipeline.execute(ticker="RELIANCE.NS")
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Initialize pipeline
        
        Args:
            event_bus: Optional event bus for publishing events
        """
        self.steps: List[PipelineStep] = []
        self.event_bus = event_bus or get_event_bus()
        
        logger.info("AnalysisPipeline initialized")
    
    def add_step(self, step: PipelineStep, position: Optional[int] = None) -> 'AnalysisPipeline':
        """
        Add a step to the pipeline
        
        Args:
            step: Pipeline step to add
            position: Optional position to insert at (None = append to end)
            
        Returns:
            Self for method chaining
        """
        if position is None:
            self.steps.append(step)
        else:
            self.steps.insert(position, step)
        
        logger.info(f"Added step: {step.name} at position {position or len(self.steps) - 1}")
        return self
    
    def remove_step(self, step_name: str) -> bool:
        """
        Remove a step by name
        
        Args:
            step_name: Name of step to remove
            
        Returns:
            True if step was removed
        """
        for i, step in enumerate(self.steps):
            if step.name == step_name:
                self.steps.pop(i)
                logger.info(f"Removed step: {step_name}")
                return True
        
        logger.warning(f"Step not found: {step_name}")
        return False
    
    def get_step(self, step_name: str) -> Optional[PipelineStep]:
        """
        Get a step by name
        
        Args:
            step_name: Name of step to get
            
        Returns:
            Step if found, None otherwise
        """
        for step in self.steps:
            if step.name == step_name:
                return step
        return None
    
    def enable_step(self, step_name: str) -> bool:
        """
        Enable a step
        
        Args:
            step_name: Name of step to enable
            
        Returns:
            True if step was found and enabled
        """
        step = self.get_step(step_name)
        if step:
            step.enabled = True
            logger.info(f"Enabled step: {step_name}")
            return True
        return False
    
    def disable_step(self, step_name: str) -> bool:
        """
        Disable a step
        
        Args:
            step_name: Name of step to disable
            
        Returns:
            True if step was found and disabled
        """
        step = self.get_step(step_name)
        if step:
            step.enabled = False
            logger.info(f"Disabled step: {step_name}")
            return True
        return False
    
    def clear_steps(self) -> None:
        """Clear all steps from pipeline"""
        self.steps = []
        logger.info("Cleared all pipeline steps")
    
    def execute(
        self,
        ticker: str,
        data: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        publish_events: bool = True
    ) -> PipelineContext:
        """
        Execute the pipeline
        
        Args:
            ticker: Stock ticker symbol
            data: Optional initial data
            config: Optional configuration
            publish_events: Whether to publish events
            
        Returns:
            Final pipeline context with results
        """
        # Create initial context
        context = PipelineContext(
            ticker=ticker,
            data=data,
            config=config or {},
            metadata={'start_time': datetime.now()}
        )
        
        # Publish start event
        if publish_events:
            self.event_bus.publish(Event(
                event_type=EventType.ANALYSIS_STARTED,
                data={'ticker': ticker},
                source='AnalysisPipeline'
            ))
        
        logger.info(f"Starting pipeline for {ticker} with {len(self.steps)} steps")
        
        # Execute each step
        for i, step in enumerate(self.steps):
            step_start = datetime.now()
            
            # Execute step
            context = step(context)
            
            # Track timing
            step_duration = (datetime.now() - step_start).total_seconds()
            context.metadata[f'{step.name}_duration'] = step_duration
            
            logger.debug(f"Step {i+1}/{len(self.steps)} ({step.name}) completed in {step_duration:.2f}s")
            
            # Stop if critical error
            if context.has_error() and self._is_critical_error(context):
                logger.error(f"Pipeline stopped due to critical error: {context.errors[-1]}")
                break
        
        # Add timing metadata
        context.metadata['end_time'] = datetime.now()
        context.metadata['total_duration'] = (
            context.metadata['end_time'] - context.metadata['start_time']
        ).total_seconds()
        
        # Publish completion event
        if publish_events:
            event_type = EventType.ANALYSIS_FAILED if context.has_error() else EventType.ANALYSIS_COMPLETED
            self.event_bus.publish(Event(
                event_type=event_type,
                data={
                    'ticker': ticker,
                    'success': not context.has_error(),
                    'duration': context.metadata['total_duration'],
                    'results': context.results
                },
                source='AnalysisPipeline'
            ))
        
        logger.info(
            f"Pipeline completed for {ticker} in {context.metadata['total_duration']:.2f}s. "
            f"Success: {not context.has_error()}"
        )
        
        return context
    
    def _is_critical_error(self, context: PipelineContext) -> bool:
        """
        Check if context has a critical error that should stop pipeline
        
        Args:
            context: Pipeline context
            
        Returns:
            True if has critical error
        """
        # Data fetch errors are critical - can't proceed without data
        # But allow verdict step to run to set a default verdict
        critical_errors = [
            "No data available",
            "Data fetch failed",
            "No data available for verdict determination"
        ]
        
        for error in context.errors:
            if any(critical in error for critical in critical_errors):
                # Still critical, but allow verdict step to handle it
                return False  # Don't stop early - let verdict step set default
        
        # Other errors may be critical
        return len(context.errors) > 0
    
    def get_step_names(self) -> List[str]:
        """
        Get list of step names in order
        
        Returns:
            List of step names
        """
        return [step.name for step in self.steps]
    
    def get_enabled_steps(self) -> List[str]:
        """
        Get list of enabled step names
        
        Returns:
            List of enabled step names
        """
        return [step.name for step in self.steps if step.enabled]


# Convenience function to create a standard analysis pipeline
def create_standard_pipeline() -> AnalysisPipeline:
    """
    Create a standard analysis pipeline with common steps
    
    Note: This is a template - actual step implementations would be in separate files
    
    Returns:
        Configured AnalysisPipeline
    """
    pipeline = AnalysisPipeline()
    
    # Steps would be added here
    # pipeline.add_step(FetchDataStep())
    # pipeline.add_step(CalculateIndicatorsStep())
    # pipeline.add_step(DetectSignalsStep())
    # pipeline.add_step(DetermineVerdictStep())
    
    logger.info("Created standard analysis pipeline")
    return pipeline
