"""
Integration test for Phase 3 - Pipeline Pattern and Event-Driven Architecture
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_event_bus():
    """Test Event Bus functionality"""
    print("\n" + "=" * 60)
    print("Testing Phase 3 - Event Bus")
    print("=" * 60)

    try:
        from services.event_bus import EventBus, Event, EventType, get_event_bus, reset_event_bus

        print("? Event Bus imports successful")

        # Test basic pub/sub
        bus = EventBus(enable_history=True)

        events_received = []

        def handler(event):
            events_received.append(event)

        bus.subscribe(EventType.ANALYSIS_COMPLETED, handler)

        bus.publish(
            Event(
                event_type=EventType.ANALYSIS_COMPLETED,
                data={"ticker": "TEST.NS", "verdict": "buy"},
                source="TestService",
            )
        )

        assert len(events_received) == 1
        assert events_received[0].data["ticker"] == "TEST.NS"
        print("? Basic pub/sub works")

        # Test event history
        history = bus.get_history()
        assert len(history) > 0
        print("? Event history tracking works")

        # Test subscriber count
        count = bus.get_subscriber_count(EventType.ANALYSIS_COMPLETED)
        assert count == 1
        print("? Subscriber count works")

        # Test global singleton
        reset_event_bus()
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2
        print("? Global event bus singleton works")

        return True

    except Exception as e:
        print(f"? Event Bus test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_pipeline():
    """Test Pipeline Pattern functionality"""
    print("\n" + "=" * 60)
    print("Testing Phase 3 - Pipeline Pattern")
    print("=" * 60)

    try:
        from services.pipeline import AnalysisPipeline, PipelineStep, PipelineContext

        print("? Pipeline imports successful")

        # Create mock step
        class TestStep(PipelineStep):
            def __init__(self, name):
                super().__init__(name)
                self.executed = False

            def execute(self, context):
                self.executed = True
                context.set_result(f"{self.name}_result", "success")
                return context

        # Test pipeline creation
        pipeline = AnalysisPipeline()
        assert len(pipeline.steps) == 0
        print("? Pipeline creation works")

        # Test adding steps
        step1 = TestStep("Step1")
        step2 = TestStep("Step2")

        pipeline.add_step(step1)
        pipeline.add_step(step2)
        assert len(pipeline.steps) == 2
        print("? Adding steps works")

        # Test execution
        context = pipeline.execute("TEST.NS", publish_events=False)

        assert step1.executed == True
        assert step2.executed == True
        assert context.get_result("Step1_result") == "success"
        assert context.get_result("Step2_result") == "success"
        print("? Pipeline execution works")

        # Test step control
        assert len(pipeline.get_step_names()) == 2
        pipeline.disable_step("Step2")
        assert "Step2" not in pipeline.get_enabled_steps()
        print("? Step enable/disable works")

        # Test removal
        pipeline.remove_step("Step1")
        assert len(pipeline.steps) == 1
        print("? Step removal works")

        return True

    except Exception as e:
        print(f"? Pipeline test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_pipeline_steps():
    """Test concrete pipeline steps"""
    print("\n" + "=" * 60)
    print("Testing Phase 3 - Concrete Pipeline Steps")
    print("=" * 60)

    try:
        from services.pipeline_steps import (
            FetchDataStep,
            CalculateIndicatorsStep,
            DetectSignalsStep,
            DetermineVerdictStep,
            create_analysis_pipeline,
        )

        print("? Pipeline steps imports successful")

        # Test factory function
        pipeline = create_analysis_pipeline(enable_fundamentals=False, enable_multi_timeframe=False)

        assert len(pipeline.steps) == 4  # 4 core steps
        print(f"? Pipeline factory creates {len(pipeline.steps)} core steps")

        step_names = pipeline.get_step_names()
        expected = ["FetchData", "CalculateIndicators", "DetectSignals", "DetermineVerdict"]
        assert step_names == expected
        print(f"? Step names correct: {step_names}")

        # Test with optional steps
        pipeline_full = create_analysis_pipeline(
            enable_fundamentals=True, enable_multi_timeframe=True
        )

        assert len(pipeline_full.steps) > 4
        print(f"? Pipeline with optional steps has {len(pipeline_full.steps)} steps")

        return True

    except Exception as e:
        print(f"? Pipeline steps test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_integration():
    """Test integration between pipeline and event bus"""
    print("\n" + "=" * 60)
    print("Testing Phase 3 - Pipeline + Event Bus Integration")
    print("=" * 60)

    try:
        from services.pipeline import AnalysisPipeline, PipelineStep, PipelineContext
        from services.event_bus import EventType, reset_event_bus, get_event_bus

        # Reset event bus
        reset_event_bus()
        bus = get_event_bus()

        # Track events
        events = []

        def event_handler(event):
            events.append(event)

        bus.subscribe(EventType.ANALYSIS_STARTED, event_handler)
        bus.subscribe(EventType.ANALYSIS_COMPLETED, event_handler)

        # Create simple step
        class SimpleStep(PipelineStep):
            def execute(self, context):
                context.set_result("test", "done")
                return context

        # Create and execute pipeline
        pipeline = AnalysisPipeline()
        pipeline.add_step(SimpleStep("TestStep"))

        context = pipeline.execute("TEST.NS", publish_events=True)

        # Check events were published
        assert len(events) >= 2
        assert any(e.event_type == EventType.ANALYSIS_STARTED for e in events)
        assert any(e.event_type == EventType.ANALYSIS_COMPLETED for e in events)

        print("? Pipeline publishes events correctly")
        print(f"? Received {len(events)} events")

        return True

    except Exception as e:
        print(f"? Integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all Phase 3 tests"""
    print("\n" + "=" * 60)
    print("Phase 3 Integration Test Suite")
    print("Pipeline Pattern + Event-Driven Architecture")
    print("=" * 60)

    results = {
        "Event Bus": test_event_bus(),
        "Pipeline Pattern": test_pipeline(),
        "Concrete Pipeline Steps": test_pipeline_steps(),
        "Pipeline + Event Bus Integration": test_integration(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "? PASSED" if passed else "? FAILED"
        print(f"{test_name}: {status}")

    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n? All Phase 3 tests passed!")
        print("? Event-Driven Architecture working")
        print("? Pipeline Pattern working")
        print("? Integration successful")
        return 0
    else:
        print(f"\n[WARN]?  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
