"""
Unit tests for Pipeline Pattern (Phase 3)

Tests the pluggable pipeline architecture
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import Mock, MagicMock
from services.pipeline import (
    AnalysisPipeline,
    PipelineStep,
    PipelineContext
)
from services.event_bus import EventType, Event, reset_event_bus


class MockStep(PipelineStep):
    """Mock pipeline step for testing"""
    
    def __init__(self, name: str = "MockStep", should_fail: bool = False):
        super().__init__(name)
        self.execute_count = 0
        self.should_fail = should_fail
    
    def execute(self, context: PipelineContext) -> PipelineContext:
        self.execute_count += 1
        
        if self.should_fail:
            raise ValueError(f"{self.name} failed")
        
        context.set_result(f'{self.name}_executed', True)
        return context


class TestPipelineContext:
    """Tests for PipelineContext"""
    
    def test_context_creation(self):
        """Test creating a pipeline context"""
        context = PipelineContext(
            ticker="TEST.NS",
            data={'df': 'test_data'},
            config={'param': 'value'}
        )
        
        assert context.ticker == "TEST.NS"
        assert context.data['df'] == 'test_data'
        assert context.config['param'] == 'value'
        assert context.results == {}
        assert context.errors == []
    
    def test_context_set_get_result(self):
        """Test setting and getting results"""
        context = PipelineContext(ticker="TEST.NS")
        
        context.set_result('key1', 'value1')
        context.set_result('key2', 123)
        
        assert context.get_result('key1') == 'value1'
        assert context.get_result('key2') == 123
        assert context.get_result('nonexistent') is None
        assert context.get_result('nonexistent', 'default') == 'default'
    
    def test_context_error_handling(self):
        """Test error handling in context"""
        context = PipelineContext(ticker="TEST.NS")
        
        assert not context.has_error()
        
        context.add_error("Test error 1")
        assert context.has_error()
        assert len(context.errors) == 1
        
        context.add_error("Test error 2")
        assert len(context.errors) == 2


class TestPipelineStep:
    """Tests for PipelineStep"""
    
    def test_step_execution(self):
        """Test basic step execution"""
        step = MockStep("TestStep")
        context = PipelineContext(ticker="TEST.NS")
        
        result = step(context)
        
        assert step.execute_count == 1
        assert result.get_result('TestStep_executed') == True
    
    def test_step_skip_when_disabled(self):
        """Test that disabled step is skipped"""
        step = MockStep("TestStep")
        step.enabled = False
        context = PipelineContext(ticker="TEST.NS")
        
        result = step(context)
        
        assert step.execute_count == 0
        assert result.get_result('TestStep_executed') is None
    
    def test_step_skip_on_context_error(self):
        """Test that step is NOT skipped if context has error (steps handle errors gracefully)"""
        step = MockStep("TestStep")
        context = PipelineContext(ticker="TEST.NS")
        context.add_error("Previous error")
        
        result = step(context)
        
        # Steps should execute even with errors - they handle errors gracefully
        # This was changed in a previous fix to allow verdict step to run even if data fetch fails
        assert step.execute_count == 1
    
    def test_step_error_handling(self):
        """Test that step errors are caught and added to context"""
        step = MockStep("FailingStep", should_fail=True)
        context = PipelineContext(ticker="TEST.NS")
        
        result = step(context)
        
        assert result.has_error()
        assert 'FailingStep failed' in result.errors[0]


class TestAnalysisPipeline:
    """Tests for AnalysisPipeline"""
    
    def setup_method(self):
        """Reset event bus before each test"""
        reset_event_bus()
    
    def test_pipeline_creation(self):
        """Test creating a pipeline"""
        pipeline = AnalysisPipeline()
        
        assert len(pipeline.steps) == 0
        assert pipeline.event_bus is not None
    
    def test_add_step(self):
        """Test adding steps to pipeline"""
        pipeline = AnalysisPipeline()
        
        step1 = MockStep("Step1")
        step2 = MockStep("Step2")
        
        pipeline.add_step(step1)
        pipeline.add_step(step2)
        
        assert len(pipeline.steps) == 2
        assert pipeline.steps[0].name == "Step1"
        assert pipeline.steps[1].name == "Step2"
    
    def test_add_step_at_position(self):
        """Test adding step at specific position"""
        pipeline = AnalysisPipeline()
        
        step1 = MockStep("Step1")
        step2 = MockStep("Step2")
        step3 = MockStep("Step3")
        
        pipeline.add_step(step1)
        pipeline.add_step(step3)
        pipeline.add_step(step2, position=1)  # Insert in middle
        
        assert pipeline.get_step_names() == ["Step1", "Step2", "Step3"]
    
    def test_remove_step(self):
        """Test removing a step"""
        pipeline = AnalysisPipeline()
        
        step1 = MockStep("Step1")
        step2 = MockStep("Step2")
        
        pipeline.add_step(step1)
        pipeline.add_step(step2)
        
        removed = pipeline.remove_step("Step1")
        
        assert removed == True
        assert len(pipeline.steps) == 1
        assert pipeline.steps[0].name == "Step2"
    
    def test_remove_nonexistent_step(self):
        """Test removing a step that doesn't exist"""
        pipeline = AnalysisPipeline()
        
        removed = pipeline.remove_step("NonExistent")
        
        assert removed == False
    
    def test_get_step(self):
        """Test getting a step by name"""
        pipeline = AnalysisPipeline()
        
        step1 = MockStep("Step1")
        pipeline.add_step(step1)
        
        retrieved = pipeline.get_step("Step1")
        
        assert retrieved is step1
        assert pipeline.get_step("NonExistent") is None
    
    def test_enable_disable_step(self):
        """Test enabling and disabling steps"""
        pipeline = AnalysisPipeline()
        
        step = MockStep("TestStep")
        pipeline.add_step(step)
        
        assert step.enabled == True
        
        pipeline.disable_step("TestStep")
        assert step.enabled == False
        
        pipeline.enable_step("TestStep")
        assert step.enabled == True
    
    def test_clear_steps(self):
        """Test clearing all steps"""
        pipeline = AnalysisPipeline()
        
        pipeline.add_step(MockStep("Step1"))
        pipeline.add_step(MockStep("Step2"))
        
        pipeline.clear_steps()
        
        assert len(pipeline.steps) == 0
    
    def test_pipeline_execution(self):
        """Test executing a pipeline"""
        pipeline = AnalysisPipeline()
        
        step1 = MockStep("Step1")
        step2 = MockStep("Step2")
        step3 = MockStep("Step3")
        
        pipeline.add_step(step1)
        pipeline.add_step(step2)
        pipeline.add_step(step3)
        
        context = pipeline.execute("TEST.NS", publish_events=False)
        
        # All steps should have executed
        assert step1.execute_count == 1
        assert step2.execute_count == 1
        assert step3.execute_count == 1
        
        # Results should be in context
        assert context.get_result('Step1_executed') == True
        assert context.get_result('Step2_executed') == True
        assert context.get_result('Step3_executed') == True
        
        # Metadata should be present
        assert 'start_time' in context.metadata
        assert 'end_time' in context.metadata
        assert 'total_duration' in context.metadata
    
    def test_pipeline_stops_on_error(self):
        """Test that pipeline stops when error occurs"""
        pipeline = AnalysisPipeline()
        
        step1 = MockStep("Step1")
        step2 = MockStep("Step2", should_fail=True)
        step3 = MockStep("Step3")
        
        pipeline.add_step(step1)
        pipeline.add_step(step2)
        pipeline.add_step(step3)
        
        context = pipeline.execute("TEST.NS", publish_events=False)
        
        # Step 1 executed
        assert step1.execute_count == 1
        # Step 2 executed and failed
        assert step2.execute_count == 1
        # Step 3 should be skipped
        assert step3.execute_count == 0
        
        assert context.has_error()
    
    def test_pipeline_events(self):
        """Test that pipeline publishes events"""
        pipeline = AnalysisPipeline()
        
        events_received = []
        
        def event_handler(event: Event):
            events_received.append(event)
        
        pipeline.event_bus.subscribe(EventType.ANALYSIS_STARTED, event_handler)
        pipeline.event_bus.subscribe(EventType.ANALYSIS_COMPLETED, event_handler)
        
        pipeline.add_step(MockStep("TestStep"))
        
        pipeline.execute("TEST.NS", publish_events=True)
        
        # Should have received start and completion events
        assert len(events_received) >= 2
        assert any(e.event_type == EventType.ANALYSIS_STARTED for e in events_received)
        assert any(e.event_type == EventType.ANALYSIS_COMPLETED for e in events_received)
    
    def test_get_step_names(self):
        """Test getting list of step names"""
        pipeline = AnalysisPipeline()
        
        pipeline.add_step(MockStep("Step1"))
        pipeline.add_step(MockStep("Step2"))
        pipeline.add_step(MockStep("Step3"))
        
        names = pipeline.get_step_names()
        
        assert names == ["Step1", "Step2", "Step3"]
    
    def test_get_enabled_steps(self):
        """Test getting list of enabled step names"""
        pipeline = AnalysisPipeline()
        
        step1 = MockStep("Step1")
        step2 = MockStep("Step2")
        step3 = MockStep("Step3")
        
        pipeline.add_step(step1)
        pipeline.add_step(step2)
        pipeline.add_step(step3)
        
        step2.enabled = False
        
        enabled = pipeline.get_enabled_steps()
        
        assert enabled == ["Step1", "Step3"]
    
    def test_pipeline_with_data_and_config(self):
        """Test pipeline execution with initial data and config"""
        pipeline = AnalysisPipeline()
        
        initial_data = {'test': 'data'}
        initial_config = {'param': 'value'}
        
        pipeline.add_step(MockStep("TestStep"))
        
        context = pipeline.execute(
            "TEST.NS",
            data=initial_data,
            config=initial_config,
            publish_events=False
        )
        
        assert context.data == initial_data
        assert context.config == initial_config


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
