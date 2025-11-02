"""
Regression Tests

This directory contains regression tests to ensure stability and prevent regressions
of previously fixed bugs and implemented features.

Test Categories:
- Bug fix regression tests (test_bug_fixes_*.py)
- Feature regression tests (test_*_v*.py)
- Stability tests

Run all regression tests:
    pytest tests/regression/ -v

Run specific regression test file:
    pytest tests/regression/test_bug_fixes_oct31.py -v
    pytest tests/regression/test_continuous_service_v2_1.py -v
"""
