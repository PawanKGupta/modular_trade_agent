#!/usr/bin/env python3
"""
Test concurrent re-authentication handling

Tests that multiple threads detecting JWT expiry simultaneously
will coordinate re-authentication properly
"""

import sys
import time
import threading
from pathlib import Path
from unittest.mock import Mock, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from modules.kotak_neo_auto_trader.auth_handler import (
        is_auth_error,
        _attempt_reauth_thread_safe
    )
    from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


def test_concurrent_reauth():
    """Test concurrent re-authentication with multiple threads"""
    print("="*80)
    print("TESTING CONCURRENT RE-AUTHENTICATION")
    print("="*80)
    
    # Create mock auth object
    mock_auth = Mock(spec=KotakNeoAuth)
    mock_auth.force_relogin = Mock()
    
    # Simulate successful re-auth (with delay to simulate API call)
    def mock_relogin():
        time.sleep(0.1)  # Simulate re-auth taking 100ms
        return True
    
    mock_auth.force_relogin.side_effect = mock_relogin
    
    # Track re-auth attempts
    reauth_attempts = []
    reauth_lock = threading.Lock()
    
    def concurrent_call(thread_id: int):
        """Simulate concurrent API calls that detect auth error"""
        start_time = time.time()
        
        # Simulate detecting auth error
        result = _attempt_reauth_thread_safe(mock_auth, f"method_{thread_id}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        with reauth_lock:
            reauth_attempts.append({
                'thread_id': thread_id,
                'success': result,
                'duration': duration,
                'timestamp': start_time
            })
        
        return result
    
    # Test with 5 concurrent threads
    num_threads = 5
    print(f"\n[TEST] Running {num_threads} concurrent re-auth attempts...")
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {
            executor.submit(concurrent_call, i): i
            for i in range(num_threads)
        }
        
        results = []
        for future in as_completed(futures):
            thread_id = futures[future]
            try:
                result = future.result()
                results.append((thread_id, result))
            except Exception as e:
                print(f"[FAIL] Thread {thread_id} failed: {e}")
                results.append((thread_id, False))
    
    # Analyze results
    print("\n" + "="*80)
    print("TEST RESULTS")
    print("="*80)
    
    successful = [r for _, r in results if r]
    failed = [r for _, r in results if not r]
    
    print(f"\n[OK] Successful re-auth: {len(successful)}/{num_threads}")
    print(f"[FAIL] Failed re-auth: {len(failed)}/{num_threads}")
    
    # Check how many times force_relogin was called
    actual_reauth_calls = mock_auth.force_relogin.call_count
    print(f"\n[INFO] force_relogin() called {actual_reauth_calls} time(s)")
    
    # Sort by timestamp to see order
    reauth_attempts.sort(key=lambda x: x['timestamp'])
    
    print("\n[INFO] Re-auth attempt timeline:")
    for attempt in reauth_attempts:
        status = "[OK]" if attempt['success'] else "[FAIL]"
        print(f"  {status} Thread {attempt['thread_id']}: "
              f"{attempt['duration']:.3f}s, "
              f"success={attempt['success']}")
    
    # Verify only one re-auth was performed
    if actual_reauth_calls == 1:
        print("\n[OK] ✅ CORRECT: Only 1 re-auth call for 5 concurrent threads")
        print("[OK] Thread-safe re-authentication working correctly!")
        
        # Verify all threads got success
        if len(successful) == num_threads:
            print(f"[OK] ✅ All {num_threads} threads detected successful re-auth")
            return True
        else:
            print(f"[WARN] ⚠️  Only {len(successful)}/{num_threads} threads got success")
            return False
    else:
        print(f"\n[FAIL] ❌ INCORRECT: {actual_reauth_calls} re-auth calls for {num_threads} threads")
        print("[FAIL] Expected only 1 re-auth call (concurrent re-auth not thread-safe)")
        return False


def test_sequential_reauth():
    """Test that sequential re-auth works correctly"""
    print("\n" + "="*80)
    print("TESTING SEQUENTIAL RE-AUTHENTICATION")
    print("="*80)
    
    mock_auth = Mock(spec=KotakNeoAuth)
    call_count = [0]
    
    def mock_relogin():
        call_count[0] += 1
        return True
    
    mock_auth.force_relogin.side_effect = mock_relogin
    
    # First re-auth
    result1 = _attempt_reauth_thread_safe(mock_auth, "method1")
    print(f"\n[TEST] First re-auth: {result1}")
    
    # Wait a bit
    time.sleep(0.1)
    
    # Second re-auth (should work independently)
    result2 = _attempt_reauth_thread_safe(mock_auth, "method2")
    print(f"[TEST] Second re-auth: {result2}")
    
    print(f"\n[INFO] force_relogin() called {call_count[0]} time(s)")
    
    if result1 and result2 and call_count[0] == 2:
        print("[OK] ✅ Sequential re-auth works correctly")
        return True
    else:
        print("[FAIL] ❌ Sequential re-auth failed")
        return False


def main():
    """Run all concurrent re-auth tests"""
    print("="*80)
    print("CONCURRENT RE-AUTHENTICATION TEST SUITE")
    print("="*80)
    
    # Test 1: Concurrent re-auth
    test1_passed = test_concurrent_reauth()
    
    # Test 2: Sequential re-auth
    test2_passed = test_sequential_reauth()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    if test1_passed and test2_passed:
        print("\n[OK] ✅ ALL TESTS PASSED")
        print("[OK] Thread-safe re-authentication is working correctly")
        print("[OK] Concurrent threads coordinate properly - only one re-auth performed")
        return 0
    else:
        print("\n[FAIL] ❌ SOME TESTS FAILED")
        if not test1_passed:
            print("[FAIL] Concurrent re-auth test failed")
        if not test2_passed:
            print("[FAIL] Sequential re-auth test failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())

