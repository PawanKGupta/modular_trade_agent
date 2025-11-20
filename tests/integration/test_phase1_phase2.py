"""
Integration test for Phase 1 and Phase 2 implementations
Tests service layer, caching, async processing, and typed models
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_phase1_service_layer():
    """Test Phase 1 - Service Layer"""
    print("\n" + "=" * 60)
    print("Testing Phase 1 - Service Layer")
    print("=" * 60)

    try:
        from services.analysis_service import AnalysisService
        from services.data_service import DataService
        from services.indicator_service import IndicatorService
        from services.signal_service import SignalService
        from services.verdict_service import VerdictService

        print("? All Phase 1 services imported successfully")

        # Test service initialization
        service = AnalysisService()
        print("? AnalysisService initialized successfully")

        # Test configuration
        from config.strategy_config import StrategyConfig

        config = StrategyConfig.from_env()
        print(f"? Configuration loaded: RSI oversold={config.rsi_oversold}")

        return True
    except Exception as e:
        print(f"? Phase 1 test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_phase2_typed_models():
    """Test Phase 2 - Typed Models"""
    print("\n" + "=" * 60)
    print("Testing Phase 2 - Typed Models")
    print("=" * 60)

    try:
        from services.models import AnalysisResult, Verdict, TradingParameters

        print("? Models imported successfully")

        # Test model creation
        result = AnalysisResult(
            ticker="TEST.NS",
            verdict=Verdict.BUY,
            last_close=100.0,
            signals=["test_signal"],
            strength_score=75.0,
        )
        print(f"? AnalysisResult created: {result.ticker} - {result.verdict.value}")

        # Test methods
        assert result.is_buyable() == True
        assert result.is_success() == True
        print("? Model methods work correctly")

        # Test dict conversion
        result_dict = result.to_dict()
        result2 = AnalysisResult.from_dict(result_dict)
        assert result2.ticker == result.ticker
        print("? Dict conversion works")

        return True
    except Exception as e:
        print(f"? Phase 2 models test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_phase2_caching():
    """Test Phase 2 - Caching Layer"""
    print("\n" + "=" * 60)
    print("Testing Phase 2 - Caching Layer")
    print("=" * 60)

    try:
        from services.cache_service import CacheService
        import tempfile

        print("? CacheService imported successfully")

        # Test cache initialization
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheService(cache_dir=tmpdir, default_ttl_seconds=60, enable_file_cache=True)
            print("? CacheService initialized")

            # Test cache operations
            cache.set("test_key", {"data": "test_value"}, ttl_seconds=60)
            value = cache.get("test_key")
            assert value == {"data": "test_value"}
            print("? Cache set/get works")

            # Test cache miss
            miss = cache.get("non_existent_key")
            assert miss is None
            print("? Cache miss handling works")

        return True
    except Exception as e:
        print(f"? Phase 2 caching test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_phase2_async():
    """Test Phase 2 - Async Processing"""
    print("\n" + "=" * 60)
    print("Testing Phase 2 - Async Processing")
    print("=" * 60)

    try:
        from services.async_analysis_service import AsyncAnalysisService
        from services.async_data_service import AsyncDataService

        print("? Async services imported successfully")

        # Test async service initialization
        async_service = AsyncAnalysisService(max_concurrent=5)
        print("? AsyncAnalysisService initialized")

        return True
    except Exception as e:
        print(f"? Phase 2 async test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_backward_compatibility():
    """Test backward compatibility with legacy code"""
    print("\n" + "=" * 60)
    print("Testing Backward Compatibility")
    print("=" * 60)

    try:
        from core.analysis import analyze_ticker

        print("? Legacy analyze_ticker function still accessible")

        return True
    except Exception as e:
        print(f"? Backward compatibility test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Phase 1 & Phase 2 Integration Test Suite")
    print("=" * 60)

    results = {
        "Phase 1 - Service Layer": test_phase1_service_layer(),
        "Phase 2 - Typed Models": test_phase2_typed_models(),
        "Phase 2 - Caching": test_phase2_caching(),
        "Phase 2 - Async": test_phase2_async(),
        "Backward Compatibility": test_backward_compatibility(),
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
        print("\n? All tests passed! Phase 1 & Phase 2 are working correctly!")
        return 0
    else:
        print(f"\n[WARN]?  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
