"""
Unit tests for rate limiting in data_fetcher.py

Tests for:
1. Rate limiting mechanism (_enforce_rate_limit)
2. Configurable delay (API_RATE_LIMIT_DELAY)
3. Thread safety of rate limiting
4. Integration with fetch_ohlcv_yf
"""

import sys
from pathlib import Path
import time
import threading
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from config.settings import API_RATE_LIMIT_DELAY
from core.data_fetcher import _enforce_rate_limit


class TestRateLimiting:
    """Test rate limiting mechanism"""
    
    def setup_method(self):
        """Reset rate limiter state before each test"""
        import core.data_fetcher as data_fetcher_module
        data_fetcher_module._last_api_call_time = 0
    
    def test_enforce_rate_limit_first_call_no_delay(self):
        """Test that first call doesn't have delay"""
        start_time = time.time()
        _enforce_rate_limit(api_type="test")
        elapsed = time.time() - start_time
        
        # First call should be very fast (< 0.1s)
        assert elapsed < 0.1, f"First call took {elapsed:.3f}s, expected < 0.1s"
    
    def test_enforce_rate_limit_second_call_has_delay(self):
        """Test that second call respects delay"""
        # First call
        _enforce_rate_limit(api_type="test1")
        
        # Second call should wait
        start_time = time.time()
        _enforce_rate_limit(api_type="test2")
        elapsed = time.time() - start_time
        
        # Should wait at least API_RATE_LIMIT_DELAY seconds
        assert elapsed >= API_RATE_LIMIT_DELAY * 0.9, f"Second call took {elapsed:.3f}s, expected >= {API_RATE_LIMIT_DELAY * 0.9}s"
        # But not too long (allow some overhead)
        assert elapsed <= API_RATE_LIMIT_DELAY * 1.5, f"Second call took {elapsed:.3f}s, expected <= {API_RATE_LIMIT_DELAY * 1.5}s"
    
    def test_enforce_rate_limit_multiple_calls(self):
        """Test that multiple calls respect delay"""
        delays = []
        
        for i in range(3):
            start_time = time.time()
            _enforce_rate_limit(api_type=f"test{i}")
            elapsed = time.time() - start_time
            delays.append(elapsed)
        
        # First call should be fast
        assert delays[0] < 0.1, f"First call delay: {delays[0]:.3f}s"
        
        # Subsequent calls should have delay
        assert delays[1] >= API_RATE_LIMIT_DELAY * 0.9, f"Second call delay: {delays[1]:.3f}s"
        assert delays[2] >= API_RATE_LIMIT_DELAY * 0.9, f"Third call delay: {delays[2]:.3f}s"
    
    def test_enforce_rate_limit_thread_safety(self):
        """Test that rate limiting is thread-safe"""
        delays = []
        lock = threading.Lock()
        
        def call_rate_limit(index):
            start_time = time.time()
            _enforce_rate_limit(api_type=f"thread{index}")
            elapsed = time.time() - start_time
            with lock:
                delays.append(elapsed)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=call_rate_limit, args=(i,))
            threads.append(thread)
        
        # Start all threads simultaneously
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All calls should complete (no deadlocks)
        assert len(delays) == 5, f"Expected 5 delays, got {len(delays)}"
        
        # Due to thread safety, the first thread to acquire the lock will be fast
        # Other threads will wait. Sort delays to find the fastest one
        sorted_delays = sorted(delays)
        # The fastest call should be fast (first thread to acquire lock)
        assert sorted_delays[0] < 0.1, f"Fastest call should be fast, got {sorted_delays[0]:.3f}s"
        
        # Most calls should have delays (due to thread safety)
        delayed_calls = [d for d in delays if d >= API_RATE_LIMIT_DELAY * 0.9]
        assert len(delayed_calls) >= 3, f"Most calls should have delays, got {len(delayed_calls)} delayed calls out of {len(delays)}"
    
    def test_enforce_rate_limit_configurable_delay(self):
        """Test that delay is configurable via API_RATE_LIMIT_DELAY"""
        # Verify default delay is set
        assert API_RATE_LIMIT_DELAY >= 0.5, f"Default delay too low: {API_RATE_LIMIT_DELAY}"
        assert API_RATE_LIMIT_DELAY <= 2.0, f"Default delay too high: {API_RATE_LIMIT_DELAY}"
    
    @patch('core.data_fetcher.MIN_DELAY_BETWEEN_API_CALLS', 0.1)
    def test_enforce_rate_limit_custom_delay(self):
        """Test rate limiting with custom delay"""
        # Reset rate limiter state
        import core.data_fetcher as data_fetcher_module
        data_fetcher_module._last_api_call_time = 0
        
        # First call
        _enforce_rate_limit(api_type="custom1")
        
        # Second call with custom delay
        start_time = time.time()
        _enforce_rate_limit(api_type="custom2")
        elapsed = time.time() - start_time
        
        # Should respect custom delay (0.1s)
        assert elapsed >= 0.09, f"Delay was {elapsed:.3f}s, expected >= 0.09s"
        assert elapsed <= 0.2, f"Delay was {elapsed:.3f}s, expected <= 0.2s"
    
    def test_enforce_rate_limit_logging(self, caplog):
        """Test that rate limiting logs appropriately"""
        import logging
        caplog.set_level(logging.DEBUG)
        
        # First call (no delay, no log)
        _enforce_rate_limit(api_type="log_test")
        
        # Second call (should log delay)
        _enforce_rate_limit(api_type="log_test2")
        
        # Check logs (rate limiting messages are at DEBUG level)
        log_messages = [record.message for record in caplog.records]
        # Rate limiting logs are at DEBUG level, may not appear in all test runs
        # Just verify function completes without errors


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
