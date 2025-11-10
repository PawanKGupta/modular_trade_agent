#!/usr/bin/env python3
"""
Phase 3 Test Runner for Configurable Indicators

Runs comprehensive tests for Phase 3: Testing & Validation
"""
import sys
import os
from pathlib import Path
import subprocess
import time

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_tests():
    """Run all Phase 3 tests"""
    print("=" * 80)
    print("PHASE 3: Testing & Validation for Configurable Indicators")
    print("=" * 80)
    
    test_file = "tests/integration/test_configurable_indicators_phase3.py"
    
    # Test categories
    test_categories = {
        "1. Unit Tests for Configurable Parameters": [
            "TestConfigurableParameters"
        ],
        "2. Integration Tests with Current Data": [
            "TestIntegrationWithData"
        ],
        "3. Backtest Comparison (Old vs New)": [
            "TestBacktestComparison"
        ],
        "4. Data Fetching Optimization": [
            "TestDataFetchingOptimization"
        ],
        "5. Indicator Calculation Consistency": [
            "TestIndicatorConsistency"
        ],
        "6. Performance Benchmarking": [
            "TestPerformance"
        ]
    }
    
    results = {}
    total_tests = 0
    passed_tests = 0
    
    for category, test_classes in test_categories.items():
        print(f"\n{'='*80}")
        print(f"{category}")
        print(f"{'='*80}")
        
        for test_class in test_classes:
            print(f"\nRunning {test_class}...")
            start_time = time.time()
            
            try:
                # Run pytest for this test class
                result = subprocess.run(
                    [
                        sys.executable, "-m", "pytest",
                        f"{test_file}::{test_class}",
                        "-v",
                        "--tb=short",
                        "--durations=5"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout per test class
                )
                
                elapsed = time.time() - start_time
                
                # Parse results
                if result.returncode == 0:
                    # Count passed tests
                    output_lines = result.stdout.split('\n')
                    passed = sum(1 for line in output_lines if 'PASSED' in line)
                    failed = sum(1 for line in output_lines if 'FAILED' in line)
                    
                    total_tests += (passed + failed)
                    passed_tests += passed
                    
                    results[test_class] = {
                        'status': 'PASSED',
                        'passed': passed,
                        'failed': failed,
                        'time': elapsed
                    }
                    
                    print(f"✅ {test_class}: {passed} passed, {failed} failed ({elapsed:.2f}s)")
                else:
                    results[test_class] = {
                        'status': 'FAILED',
                        'error': result.stderr,
                        'time': elapsed
                    }
                    print(f"❌ {test_class}: Failed ({elapsed:.2f}s)")
                    print(result.stderr[:500])  # Print first 500 chars of error
                    
            except subprocess.TimeoutExpired:
                results[test_class] = {
                    'status': 'TIMEOUT',
                    'time': 300
                }
                print(f"⏱️  {test_class}: Timeout (>5 minutes)")
            except Exception as e:
                results[test_class] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
                print(f"❌ {test_class}: Error - {e}")
    
    # Summary
    print(f"\n{'='*80}")
    print("PHASE 3 TEST SUMMARY")
    print(f"{'='*80}")
    
    for test_class, result in results.items():
        status = result['status']
        if status == 'PASSED':
            print(f"✅ {test_class}: {result['passed']} passed, {result['failed']} failed ({result['time']:.2f}s)")
        elif status == 'FAILED':
            print(f"❌ {test_class}: Failed ({result.get('time', 0):.2f}s)")
        elif status == 'TIMEOUT':
            print(f"⏱️  {test_class}: Timeout")
        else:
            print(f"❌ {test_class}: Error")
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests and total_tests > 0:
        print("\n🎉 All Phase 3 tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())




