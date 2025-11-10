"""
Event Bus for Event-Driven Architecture

Provides publish-subscribe mechanism for loose coupling between components.
Components can publish events and subscribe to events without direct dependencies.

Phase 3 Feature - Event-Driven Architecture
"""

from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from threading import Lock

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Standard event types in the system"""
    # Analysis events
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"
    
    # Signal events
    SIGNAL_DETECTED = "signal_detected"
    PATTERN_FOUND = "pattern_found"
    
    # Data events
    DATA_FETCHED = "data_fetched"
    DATA_FETCH_FAILED = "data_fetch_failed"
    
    # Trading events
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    
    # Risk events
    STOP_LOSS_HIT = "stop_loss_hit"
    TARGET_REACHED = "target_reached"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    
    # System events
    SYSTEM_ERROR = "system_error"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"


@dataclass
class Event:
    """
    Event object containing event data
    
    Attributes:
        event_type: Type of event
        data: Event payload data
        timestamp: When event occurred
        source: Component that published the event
        metadata: Additional metadata
    """
    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return f"Event({self.event_type.value}, source={self.source})"


# Type alias for event handler functions
EventHandler = Callable[[Event], None]


class EventBus:
    """
    Event Bus for publish-subscribe pattern
    
    Features:
    - Subscribe to specific event types
    - Publish events to all subscribers
    - Thread-safe operations
    - Event history tracking (optional)
    - Error handling for handlers
    
    Usage:
        bus = EventBus()
        
        # Subscribe to events
        def on_analysis_complete(event: Event):
            print(f"Analysis done: {event.data['ticker']}")
        
        bus.subscribe(EventType.ANALYSIS_COMPLETED, on_analysis_complete)
        
        # Publish events
        bus.publish(Event(
            event_type=EventType.ANALYSIS_COMPLETED,
            data={'ticker': 'RELIANCE.NS', 'verdict': 'buy'},
            source='AnalysisService'
        ))
    """
    
    def __init__(self, enable_history: bool = False, history_size: int = 100):
        """
        Initialize event bus
        
        Args:
            enable_history: If True, keep history of recent events
            history_size: Maximum number of events to keep in history
        """
        self._subscribers: Dict[EventType, List[EventHandler]] = {}
        self._lock = Lock()
        self._enable_history = enable_history
        self._history_size = history_size
        self._history: List[Event] = []
        
        logger.info("EventBus initialized")
    
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Subscribe to an event type
        
        Args:
            event_type: Type of event to subscribe to
            handler: Function to call when event occurs
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.debug(f"Subscribed handler to {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Unsubscribe from an event type
        
        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function to remove
        """
        with self._lock:
            if event_type in self._subscribers:
                if handler in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(handler)
                    logger.debug(f"Unsubscribed handler from {event_type.value}")
    
    def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers
        
        Args:
            event: Event to publish
        """
        # Add to history
        if self._enable_history:
            with self._lock:
                self._history.append(event)
                if len(self._history) > self._history_size:
                    self._history.pop(0)
        
        # Get subscribers
        with self._lock:
            handlers = self._subscribers.get(event.event_type, []).copy()
        
        # Call each handler
        logger.debug(f"Publishing {event.event_type.value} to {len(handlers)} subscribers")
        
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event.event_type.value}: {e}")
                # Don't stop other handlers if one fails
    
    def clear_subscribers(self, event_type: Optional[EventType] = None) -> None:
        """
        Clear subscribers
        
        Args:
            event_type: If provided, clear only for this event type. 
                       If None, clear all subscribers.
        """
        with self._lock:
            if event_type:
                self._subscribers[event_type] = []
            else:
                self._subscribers = {}
            
            logger.debug(f"Cleared subscribers for {event_type.value if event_type else 'all events'}")
    
    def get_history(self, event_type: Optional[EventType] = None, limit: int = 10) -> List[Event]:
        """
        Get event history
        
        Args:
            event_type: If provided, filter by event type
            limit: Maximum number of events to return
            
        Returns:
            List of recent events
        """
        if not self._enable_history:
            return []
        
        with self._lock:
            history = self._history.copy()
        
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        
        return history[-limit:]
    
    def get_subscriber_count(self, event_type: EventType) -> int:
        """
        Get number of subscribers for an event type
        
        Args:
            event_type: Event type to check
            
        Returns:
            Number of subscribers
        """
        with self._lock:
            return len(self._subscribers.get(event_type, []))
    
    def has_subscribers(self, event_type: EventType) -> bool:
        """
        Check if event type has any subscribers
        
        Args:
            event_type: Event type to check
            
        Returns:
            True if has subscribers
        """
        return self.get_subscriber_count(event_type) > 0


# Global event bus instance (singleton pattern)
_global_event_bus: Optional[EventBus] = None


def get_event_bus(enable_history: bool = False) -> EventBus:
    """
    Get global event bus instance (singleton)
    
    Args:
        enable_history: Enable event history tracking
        
    Returns:
        Global EventBus instance
    """
    global _global_event_bus
    
    if _global_event_bus is None:
        _global_event_bus = EventBus(enable_history=enable_history)
    
    return _global_event_bus


def reset_event_bus() -> None:
    """
    Reset global event bus (useful for testing)
    """
    global _global_event_bus
    _global_event_bus = None
