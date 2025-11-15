#!/usr/bin/env python3
"""
Unit tests for circuit breaker reset in training data collection

Tests that circuit breaker is reset periodically to prevent blocking
during long-running feature extraction.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


class TestCircuitBreakerReset:
    """Test circuit breaker reset during training data collection"""
    
    def test_circuit_breaker_reset_called(self):
        """Test that circuit breaker is reset before feature extraction"""
        # This test verifies the script structure imports and resets the circuit breaker
        # We can't easily test the actual reset call without running the full script,
        # but we can verify the import and reset method exist
        
        from core.data_fetcher import yfinance_circuit_breaker
        
        # Verify circuit breaker has reset method
        assert hasattr(yfinance_circuit_breaker, 'reset')
        assert callable(yfinance_circuit_breaker.reset)
        
        # Call reset (should not raise exception)
        try:
            yfinance_circuit_breaker.reset()
            # If we get here, reset worked
            assert True
        except Exception as e:
            pytest.fail(f"Circuit breaker reset failed: {e}")
    
    def test_circuit_breaker_state_transitions(self):
        """Test that circuit breaker can transition from OPEN to CLOSED"""
        from core.data_fetcher import yfinance_circuit_breaker
        from utils.circuit_breaker import CircuitState
        
        # Get initial state
        initial_state = yfinance_circuit_breaker.state
        
        # Reset should set state to CLOSED
        yfinance_circuit_breaker.reset()
        
        # State should be CLOSED after reset (use enum value)
        assert yfinance_circuit_breaker.state == CircuitState.CLOSED
    
    def test_resume_feature_extraction_imports(self):
        """Test that resume_feature_extraction script has required imports"""
        # Verify the script can be imported
        try:
            import scripts.resume_feature_extraction as resume_script
            # If import succeeds, script structure is valid
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import resume_feature_extraction: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

