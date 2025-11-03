"""
Unit tests for Event Bus (Phase 3)

Tests the event-driven architecture implementation
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from datetime import datetime
from services.event_bus import (
    EventBus,
    Event,
    EventType,
    get_event_bus,
    reset_event_bus
)


class TestEvent:
    """Tests for Event class"""
    
    def test_event_creation(self):
        """Test creating an event"""
        event = Event(
            event_type=EventType.ANALYSIS_COMPLETED,
            data={'ticker': 'TEST.NS', 'verdict': 'buy'},
            source='TestService'
        )
        
        assert event.event_type == EventType.ANALYSIS_COMPLETED
        assert event.data['ticker'] == 'TEST.NS'
        assert event.source == 'TestService'
        assert isinstance(event.timestamp, datetime)
    
    def test_event_string_representation(self):
        """Test event string representation"""
        event = Event(
            event_type=EventType.SIGNAL_DETECTED,
            data={'signal': 'test'},
            source='TestService'
        )
        
        assert 'signal_detected' in str(event)
        assert 'TestService' in str(event)


class TestEventBus:
    """Tests for EventBus class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.event_bus = EventBus(enable_history=True)
        self.events_received = []
    
    def test_subscribe_and_publish(self):
        """Test basic subscribe and publish"""
        def handler(event: Event):
            self.events_received.append(event)
        
        self.event_bus.subscribe(EventType.ANALYSIS_COMPLETED, handler)
        
        event = Event(
            event_type=EventType.ANALYSIS_COMPLETED,
            data={'ticker': 'TEST.NS'},
            source='Test'
        )
        
        self.event_bus.publish(event)
        
        assert len(self.events_received) == 1
        assert self.events_received[0].data['ticker'] == 'TEST.NS'
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers to same event"""
        received1 = []
        received2 = []
        
        def handler1(event: Event):
            received1.append(event)
        
        def handler2(event: Event):
            received2.append(event)
        
        self.event_bus.subscribe(EventType.SIGNAL_DETECTED, handler1)
        self.event_bus.subscribe(EventType.SIGNAL_DETECTED, handler2)
        
        event = Event(
            event_type=EventType.SIGNAL_DETECTED,
            data={'signal': 'rsi_oversold'}
        )
        
        self.event_bus.publish(event)
        
        assert len(received1) == 1
        assert len(received2) == 1
    
    def test_unsubscribe(self):
        """Test unsubscribing from events"""
        def handler(event: Event):
            self.events_received.append(event)
        
        self.event_bus.subscribe(EventType.ANALYSIS_COMPLETED, handler)
        self.event_bus.unsubscribe(EventType.ANALYSIS_COMPLETED, handler)
        
        event = Event(
            event_type=EventType.ANALYSIS_COMPLETED,
            data={}
        )
        
        self.event_bus.publish(event)
        
        assert len(self.events_received) == 0
    
    def test_handler_error_doesnt_stop_other_handlers(self):
        """Test that error in one handler doesn't stop others"""
        received = []
        
        def failing_handler(event: Event):
            raise ValueError("Test error")
        
        def working_handler(event: Event):
            received.append(event)
        
        self.event_bus.subscribe(EventType.ANALYSIS_COMPLETED, failing_handler)
        self.event_bus.subscribe(EventType.ANALYSIS_COMPLETED, working_handler)
        
        event = Event(event_type=EventType.ANALYSIS_COMPLETED, data={})
        self.event_bus.publish(event)
        
        # Working handler should still receive event
        assert len(received) == 1
    
    def test_event_history(self):
        """Test event history tracking"""
        event_bus = EventBus(enable_history=True, history_size=3)
        
        for i in range(5):
            event = Event(
                event_type=EventType.ANALYSIS_COMPLETED,
                data={'index': i}
            )
            event_bus.publish(event)
        
        history = event_bus.get_history()
        
        # Should only keep last 3 events
        assert len(history) <= 3
        assert history[-1].data['index'] == 4
    
    def test_event_history_filter_by_type(self):
        """Test filtering event history by type"""
        event_bus = EventBus(enable_history=True)
        
        # Publish different types
        event_bus.publish(Event(event_type=EventType.ANALYSIS_COMPLETED, data={}))
        event_bus.publish(Event(event_type=EventType.SIGNAL_DETECTED, data={}))
        event_bus.publish(Event(event_type=EventType.ANALYSIS_COMPLETED, data={}))
        
        # Filter by type
        analysis_events = event_bus.get_history(event_type=EventType.ANALYSIS_COMPLETED)
        
        assert len(analysis_events) == 2
        assert all(e.event_type == EventType.ANALYSIS_COMPLETED for e in analysis_events)
    
    def test_subscriber_count(self):
        """Test getting subscriber count"""
        def handler1(event: Event):
            pass
        
        def handler2(event: Event):
            pass
        
        self.event_bus.subscribe(EventType.ANALYSIS_COMPLETED, handler1)
        self.event_bus.subscribe(EventType.ANALYSIS_COMPLETED, handler2)
        
        count = self.event_bus.get_subscriber_count(EventType.ANALYSIS_COMPLETED)
        assert count == 2
    
    def test_has_subscribers(self):
        """Test checking if event has subscribers"""
        def handler(event: Event):
            pass
        
        assert not self.event_bus.has_subscribers(EventType.ANALYSIS_COMPLETED)
        
        self.event_bus.subscribe(EventType.ANALYSIS_COMPLETED, handler)
        
        assert self.event_bus.has_subscribers(EventType.ANALYSIS_COMPLETED)
    
    def test_clear_subscribers(self):
        """Test clearing subscribers"""
        def handler(event: Event):
            pass
        
        self.event_bus.subscribe(EventType.ANALYSIS_COMPLETED, handler)
        self.event_bus.subscribe(EventType.SIGNAL_DETECTED, handler)
        
        # Clear specific event type
        self.event_bus.clear_subscribers(EventType.ANALYSIS_COMPLETED)
        
        assert not self.event_bus.has_subscribers(EventType.ANALYSIS_COMPLETED)
        assert self.event_bus.has_subscribers(EventType.SIGNAL_DETECTED)
        
        # Clear all
        self.event_bus.clear_subscribers()
        
        assert not self.event_bus.has_subscribers(EventType.SIGNAL_DETECTED)


class TestGlobalEventBus:
    """Tests for global event bus singleton"""
    
    def setup_method(self):
        """Reset global event bus before each test"""
        reset_event_bus()
    
    def test_get_event_bus_returns_singleton(self):
        """Test that get_event_bus returns same instance"""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        
        assert bus1 is bus2
    
    def test_reset_event_bus(self):
        """Test resetting global event bus"""
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()
        
        assert bus1 is not bus2


class TestEventTypes:
    """Test EventType enum"""
    
    def test_event_types_defined(self):
        """Test that all expected event types are defined"""
        expected_types = [
            'ANALYSIS_STARTED',
            'ANALYSIS_COMPLETED',
            'ANALYSIS_FAILED',
            'SIGNAL_DETECTED',
            'PATTERN_FOUND',
            'DATA_FETCHED',
            'ORDER_PLACED',
            'CACHE_HIT',
            'SYSTEM_ERROR'
        ]
        
        for event_type in expected_types:
            assert hasattr(EventType, event_type)
    
    def test_event_type_values(self):
        """Test event type string values"""
        assert EventType.ANALYSIS_COMPLETED.value == 'analysis_completed'
        assert EventType.SIGNAL_DETECTED.value == 'signal_detected'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
