# Testing Rules & Guidelines

**Version:** 1.0  
**Last Updated:** 2025-11-07  
**Status:** Active

---

## Table of Contents

1. [Overview](#overview)
2. [Test Organization](#test-organization)
3. [Writing Tests](#writing-tests)
4. [Test Patterns](#test-patterns)
5. [Test Data Management](#test-data-management)
6. [Running Tests](#running-tests)
7. [Coverage Requirements](#coverage-requirements)
8. [Test Categories](#test-categories)
9. [Best Practices](#best-practices)
10. [Common Pitfalls](#common-pitfalls)

---

## Overview

### Purpose
This document provides comprehensive rules and guidelines for writing, organizing, and maintaining tests in the Modular Trade Agent project. All developers must follow these rules to ensure code quality, maintainability, and reliability.

### Testing Philosophy
- **Test-Driven Development**: Write tests before or alongside code
- **Comprehensive Coverage**: Aim for 80%+ coverage, 95%+ for critical paths
- **Fast Feedback**: Tests should run quickly and provide clear failure messages
- **Isolation**: Each test must be independent and repeatable
- **Realistic Mocks**: Mock external dependencies, but keep mocks realistic

---

## Test Organization

### Directory Structure

```
tests/
├── conftest.py                    # Root-level fixtures and configuration
├── unit/                          # Unit tests (fast, isolated)
│   ├── services/                  # Service layer tests
│   ├── domain/                    # Domain entity tests
│   ├── infrastructure/            # Infrastructure adapter tests
│   ├── presentation/              # CLI/formatter tests
│   └── kotak/                     # Broker integration unit tests
├── integration/                   # Integration tests (slower)
│   ├── kotak/                     # Broker integration workflows
│   ├── use_cases/                 # Use case integration tests
│   └── test_ml_pipeline.py        # ML pipeline tests
├── regression/                    # Regression tests (bug fixes)
├── e2e/                           # End-to-end tests (full workflows)
├── performance/                   # Performance benchmarks
├── security/                      # Security tests
└── data/                          # Test data files
    └── golden/                    # Golden files for regression tests
```

### File Naming Conventions

- **Test Files**: `test_*.py` (e.g., `test_analysis_service.py`)
- **Test Classes**: `Test*` (optional, prefer functions)
- **Test Functions**: `test_*` (e.g., `test_analyze_ticker_returns_buy_verdict`)
- **Fixtures File**: `conftest.py` (can exist at multiple levels)

### Test File Organization

Each test file should:
- Test one module or class
- Mirror the source structure
- Group related tests together
- Use descriptive names

**Example:**
```python
# tests/unit/services/test_analysis_service.py
"""Tests for AnalysisService."""

import pytest
from services.analysis_service import AnalysisService

def test_analyze_ticker_returns_buy_when_rsi_below_30():
    """Test that BUY verdict is returned when RSI is below 30."""
    # Test implementation

def test_analyze_ticker_returns_strong_buy_when_multiple_signals():
    """Test that STRONG_BUY is returned with multiple bullish signals."""
    # Test implementation
```

---

## Writing Tests

### Test Structure (AAA Pattern)

Follow the **Arrange-Act-Assert** pattern:

```python
def test_analysis_service_returns_buy_verdict():
    """Test that analysis service returns BUY verdict for oversold stock."""
    # Arrange: Set up test data and dependencies
    service = AnalysisService()
    ticker = "RELIANCE.NS"
    mock_data = create_mock_stock_data(rsi=25.0, price_above_ema200=True)
    
    # Act: Execute the code under test
    result = service.analyze_ticker(ticker)
    
    # Assert: Verify the expected outcome
    assert result.verdict == "buy"
    assert result.rsi == 25.0
    assert result.mtf_alignment_score >= 5.0
```

### Test Naming Conventions

**Good Test Names:**
- `test_analysis_service_returns_buy_verdict_when_rsi_below_30`
- `test_scoring_service_computes_combined_score_correctly`
- `test_order_tracker_prevents_duplicate_order_registration`

**Bad Test Names:**
- `test_analysis_service` (too vague)
- `test1` (not descriptive)
- `test_buy` (unclear context)

### Test Function Requirements

1. **One Concept Per Test**: Each test should verify one behavior
2. **Descriptive Docstrings**: Explain what is being tested
3. **Clear Assertions**: Use descriptive assertion messages
4. **No Side Effects**: Tests should not modify global state
5. **Deterministic**: Tests must produce same results every run

### Using Fixtures

**Project-Level Fixtures** (`tests/conftest.py`):
- `sample_stock` - Sample Stock entity
- `sample_analysis_result` - Sample AnalysisResult
- `sample_buy_signal` - Sample BUY signal
- `mock_data_service` - Mock data service
- `mock_scoring_service` - Mock scoring service

**Usage:**
```python
def test_analysis_with_sample_stock(sample_stock, mock_data_service):
    """Test analysis using project fixtures."""
    service = AnalysisService(data_service=mock_data_service)
    result = service.analyze_ticker(sample_stock.ticker)
    assert result.status == "success"
```

**Directory-Level Fixtures** (`tests/unit/services/conftest.py`):
- Create fixtures specific to a test directory
- Use for service-specific test data

---

## Test Patterns

### Unit Test Pattern

```python
import pytest
from unittest.mock import Mock, patch
from services.analysis_service import AnalysisService

@pytest.mark.unit
def test_analyze_ticker_success():
    """Test successful ticker analysis."""
    # Arrange
    mock_data_service = Mock()
    mock_data_service.fetch_stock_data.return_value = {
        'ticker': 'RELIANCE.NS',
        'rsi': 28.5,
        'price': 2450.0,
        'ema200': 2400.0
    }
    
    service = AnalysisService(data_service=mock_data_service)
    
    # Act
    result = service.analyze_ticker("RELIANCE.NS")
    
    # Assert
    assert result.status == "success"
    assert result.verdict == "buy"
```

### Integration Test Pattern

```python
import pytest
from services import AnalysisService

@pytest.mark.integration
def test_analysis_service_integration():
    """Test analysis service with real service dependencies."""
    # Arrange
    service = AnalysisService()  # Uses real dependencies
    
    # Act
    result = service.analyze_ticker("RELIANCE.NS")
    
    # Assert
    assert result.status in ["success", "error"]  # May fail due to external factors
    if result.status == "success":
        assert result.verdict in ["buy", "strong_buy", "watch", "avoid"]
```

### Parametrized Test Pattern

```python
import pytest

@pytest.mark.parametrize("rsi,expected_verdict", [
    (25.0, "buy"),
    (15.0, "strong_buy"),
    (35.0, "watch"),
    (50.0, "avoid"),
])
def test_verdict_based_on_rsi(rsi, expected_verdict):
    """Test verdict determination based on RSI value."""
    # Test implementation
    pass
```

### Async Test Pattern

```python
import pytest
import asyncio
from services import AsyncAnalysisService

@pytest.mark.asyncio
@pytest.mark.unit
async def test_async_batch_analysis():
    """Test async batch analysis."""
    service = AsyncAnalysisService()
    tickers = ["RELIANCE.NS", "INFY.NS", "TCS.NS"]
    
    results = await service.analyze_batch_async(tickers)
    
    assert len(results) == 3
    assert all(r.status == "success" for r in results)
```

### Mock Pattern

```python
from unittest.mock import Mock, patch, MagicMock

def test_with_mocked_api():
    """Test with mocked external API."""
    with patch('services.data_service.yfinance.download') as mock_download:
        mock_download.return_value = create_mock_dataframe()
        
        service = AnalysisService()
        result = service.analyze_ticker("RELIANCE.NS")
        
        mock_download.assert_called_once_with("RELIANCE.NS", period="1y")
        assert result.status == "success"
```

### Exception Testing Pattern

```python
import pytest
from services.exceptions import DataError

def test_raises_data_error_when_no_data():
    """Test that DataError is raised when no data available."""
    mock_data_service = Mock()
    mock_data_service.fetch_stock_data.side_effect = DataError("No data")
    
    service = AnalysisService(data_service=mock_data_service)
    
    with pytest.raises(DataError, match="No data"):
        service.analyze_ticker("INVALID.NS")
```

---

## Test Data Management

### Fixtures for Reusable Data

**Use fixtures from `tests/conftest.py`:**
```python
def test_with_fixtures(sample_stock, sample_analysis_result):
    """Test using project fixtures."""
    assert sample_stock.ticker == "RELIANCE.NS"
    assert sample_analysis_result.verdict == "buy"
```

### Temporary Files

**Use `tmp_path` fixture:**
```python
def test_csv_export(tmp_path):
    """Test CSV export to temporary file."""
    output_file = tmp_path / "test_export.csv"
    
    service = AnalysisService()
    service.export_to_csv("RELIANCE.NS", output_file)
    
    assert output_file.exists()
    # Verify file contents
```

### Mock Data

**Never hit real APIs:**
```python
def test_with_mock_data():
    """Test with mocked API responses."""
    mock_response = {
        'ticker': 'RELIANCE.NS',
        'data': create_mock_ohlcv_data(),
        'indicators': {'rsi': 28.5, 'ema200': 2400.0}
    }
    
    with patch('services.data_service.fetch_data', return_value=mock_response):
        # Test implementation
        pass
```

### Golden Files (Regression Tests)

**Store expected outputs:**
```python
import json
from pathlib import Path

def test_regression_against_golden():
    """Test against golden file for regression detection."""
    golden_file = Path("tests/data/golden/backtest_regression.json")
    expected = json.loads(golden_file.read_text())
    
    # Run analysis
    result = run_analysis("RELIANCE.NS")
    
    # Compare with golden file
    assert result.verdict == expected['verdict']
    assert abs(result.rsi - expected['rsi']) < 0.1
```

### Sensitive Data

**Never commit sensitive data:**
- ❌ API keys, tokens, passwords
- ❌ Real trade data, positions
- ❌ Personal information
- ✅ Use `.env.example` for required variables
- ✅ Use mocks for sensitive operations

---

## Running Tests

### Basic Commands

```bash
# Quick test run (quiet mode)
.\.venv\Scripts\python.exe -m pytest -q

# Verbose output
.\.venv\Scripts\python.exe -m pytest -v

# Run specific test file
.\.venv\Scripts\python.exe -m pytest tests/unit/services/test_analysis_service.py

# Run specific test function
.\.venv\Scripts\python.exe -m pytest tests/unit/services/test_analysis_service.py::test_analyze_ticker

# Run tests matching pattern
.\.venv\Scripts\python.exe -m pytest -k "test_analysis"

# Run with output capture disabled (see print statements)
.\.venv\Scripts\python.exe -m pytest -s
```

### Running by Category

```bash
# Run only unit tests
.\.venv\Scripts\python.exe -m pytest -m unit

# Run only integration tests
.\.venv\Scripts\python.exe -m pytest -m integration

# Run only e2e tests
.\.venv\Scripts\python.exe -m pytest -m e2e

# Exclude slow tests
.\.venv\Scripts\python.exe -m pytest -m "not slow"

# Run multiple markers
.\.venv\Scripts\python.exe -m pytest -m "unit or integration"
```

### Coverage Commands

```bash
# Generate HTML coverage report
.\.venv\Scripts\python.exe -m pytest --cov=. --cov-report=html

# View coverage report
# Open logs/htmlcov/index.html in browser

# Terminal coverage report
.\.venv\Scripts\python.exe -m pytest --cov=. --cov-report=term-missing

# Coverage for specific module
.\.venv\Scripts\python.exe -m pytest --cov=services --cov-report=html
```

### Parallel Execution

```bash
# Run tests in parallel (requires pytest-xdist)
.\.venv\Scripts\python.exe -m pytest -n auto

# Specific number of workers
.\.venv\Scripts\python.exe -m pytest -n 4
```

### Debugging Tests

```bash
# Run with Python debugger
.\.venv\Scripts\python.exe -m pytest --pdb

# Drop into debugger on failure
.\.venv\Scripts\python.exe -m pytest --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb

# Show local variables on failure
.\.venv\Scripts\python.exe -m pytest -l
```

---

## Coverage Requirements

### Coverage Targets

- **Minimum Coverage**: 80% for all new code
- **Critical Paths**: 95%+ coverage required
  - Trading logic (analysis, signals, verdicts)
  - Order execution (buy, sell, modifications)
  - Authentication and session management
  - Error handling and retry logic

### Coverage Configuration

Coverage is configured in `pytest.ini`:
```ini
[coverage:run]
source = src
omit = 
    */tests/*
    */test_*
    */__pycache__/*
    */site-packages/*

[coverage:report]
precision = 2
show_missing = True
skip_covered = False
```

### Coverage Reports

- **HTML Report**: `logs/htmlcov/index.html` (detailed, interactive)
- **Terminal Report**: Shows missing lines (quick feedback)
- **CI Integration**: Coverage reports in CI/CD pipelines

### Improving Coverage

1. **Identify Gaps**: Review coverage report
2. **Add Tests**: Write tests for uncovered code
3. **Edge Cases**: Test boundary conditions
4. **Error Paths**: Test exception handling
5. **Integration**: Test component interactions

---

## Test Categories

### Unit Tests (`@pytest.mark.unit`)

**Purpose**: Test individual functions/methods in isolation

**Characteristics**:
- Fast execution (< 1 second per test)
- No external dependencies
- Mock all external calls
- Test single responsibility

**Example**:
```python
@pytest.mark.unit
def test_rsi_calculation():
    """Test RSI calculation with known values."""
    data = [100, 102, 101, 103, 102, 104, 103, 105]
    rsi = calculate_rsi(data, period=5)
    assert 0 <= rsi <= 100
```

### Integration Tests (`@pytest.mark.integration`)

**Purpose**: Test component interactions

**Characteristics**:
- Slower execution (1-10 seconds)
- Real service dependencies (may be mocked)
- Test workflows and data flow
- May require setup/teardown

**Example**:
```python
@pytest.mark.integration
def test_analysis_pipeline():
    """Test complete analysis pipeline."""
    service = AnalysisService()
    result = service.analyze_ticker("RELIANCE.NS")
    assert result.status == "success"
```

### E2E Tests (`@pytest.mark.e2e`)

**Purpose**: Test complete user workflows

**Characteristics**:
- Slowest execution (10+ seconds)
- Full system integration
- Real dependencies (may be mocked)
- Test user scenarios

**Example**:
```python
@pytest.mark.e2e
def test_complete_trading_workflow():
    """Test complete trading workflow from analysis to order."""
    # Full workflow test
    pass
```

### Regression Tests (`tests/regression/`)

**Purpose**: Prevent bug regressions

**Characteristics**:
- Test bug fixes
- Compare against golden files
- Test historical scenarios
- Ensure fixes don't break existing functionality

### Performance Tests (`@pytest.mark.performance`)

**Purpose**: Benchmark performance

**Characteristics**:
- Measure execution time
- Test throughput
- Memory usage monitoring
- Use `pytest-benchmark`

**Example**:
```python
@pytest.mark.performance
def test_analysis_performance(benchmark):
    """Benchmark analysis service performance."""
    service = AnalysisService()
    result = benchmark(service.analyze_ticker, "RELIANCE.NS")
    assert result.status == "success"
```

### Security Tests (`@pytest.mark.security`)

**Purpose**: Validate security measures

**Characteristics**:
- Test credential handling
- Test input validation
- Test authentication/authorization
- Test data sanitization

---

## Best Practices

### 1. Test Independence

✅ **Good**: Each test is independent
```python
def test_analysis_1():
    service = AnalysisService()
    result1 = service.analyze_ticker("RELIANCE.NS")
    assert result1.status == "success"

def test_analysis_2():
    service = AnalysisService()
    result2 = service.analyze_ticker("INFY.NS")
    assert result2.status == "success"
```

❌ **Bad**: Tests depend on each other
```python
result = None

def test_analysis_1():
    global result
    result = service.analyze_ticker("RELIANCE.NS")

def test_analysis_2():
    assert result.status == "success"  # Depends on test_analysis_1
```

### 2. Descriptive Assertions

✅ **Good**: Clear assertion messages
```python
assert result.verdict == "buy", f"Expected BUY, got {result.verdict}"
assert result.rsi < 30, f"RSI should be below 30, got {result.rsi}"
```

❌ **Bad**: Unclear assertions
```python
assert result.verdict == "buy"
assert result.rsi < 30
```

### 3. Test One Thing

✅ **Good**: One concept per test
```python
def test_rsi_below_30_returns_buy():
    """Test that RSI below 30 returns BUY verdict."""
    pass

def test_rsi_below_20_returns_strong_buy():
    """Test that RSI below 20 returns STRONG_BUY verdict."""
    pass
```

❌ **Bad**: Multiple concepts in one test
```python
def test_analysis():
    """Test everything."""
    # Tests RSI, EMA, volume, patterns, etc.
    pass
```

### 4. Use Fixtures

✅ **Good**: Reuse fixtures
```python
def test_analysis(sample_stock, mock_data_service):
    service = AnalysisService(data_service=mock_data_service)
    result = service.analyze_ticker(sample_stock.ticker)
    assert result.status == "success"
```

❌ **Bad**: Duplicate setup code
```python
def test_analysis_1():
    stock = Stock(ticker="RELIANCE.NS", ...)  # Duplicated
    service = AnalysisService(...)  # Duplicated
    # Test

def test_analysis_2():
    stock = Stock(ticker="RELIANCE.NS", ...)  # Duplicated
    service = AnalysisService(...)  # Duplicated
    # Test
```

### 5. Mock External Dependencies

✅ **Good**: Mock external APIs
```python
@patch('services.data_service.yfinance.download')
def test_analysis(mock_download):
    mock_download.return_value = create_mock_dataframe()
    # Test
```

❌ **Bad**: Hit real APIs
```python
def test_analysis():
    # This hits real yfinance API - BAD!
    service = AnalysisService()
    result = service.analyze_ticker("RELIANCE.NS")
```

---

## Common Pitfalls

### 1. Testing Implementation Details

❌ **Bad**: Testing internal implementation
```python
def test_analysis():
    service = AnalysisService()
    assert service._internal_cache is not None  # Testing private attribute
```

✅ **Good**: Testing public behavior
```python
def test_analysis():
    service = AnalysisService()
    result = service.analyze_ticker("RELIANCE.NS")
    assert result.status == "success"  # Testing public interface
```

### 2. Over-Mocking

❌ **Bad**: Mocking everything
```python
def test_analysis():
    mock_service = Mock()
    mock_service.analyze_ticker.return_value = Mock()
    # No actual testing happening
```

✅ **Good**: Mock only external dependencies
```python
def test_analysis():
    mock_data_service = Mock()  # Mock external API
    service = AnalysisService(data_service=mock_data_service)
    result = service.analyze_ticker("RELIANCE.NS")  # Test real logic
    assert result.status == "success"
```

### 3. Brittle Tests

❌ **Bad**: Testing exact string formats
```python
def test_telegram_message():
    message = format_telegram_message(result)
    assert message == "Exact string with all formatting"  # Brittle
```

✅ **Good**: Testing important content
```python
def test_telegram_message():
    message = format_telegram_message(result)
    assert "RELIANCE.NS" in message
    assert "BUY" in message
    assert "RSI: 28.5" in message
```

### 4. Ignoring Test Failures

❌ **Bad**: Commenting out failing tests
```python
# def test_analysis():
#     # This test is failing, commenting out
#     pass
```

✅ **Good**: Fix the test or the code
```python
def test_analysis():
    # Fixed the test to match new behavior
    result = service.analyze_ticker("RELIANCE.NS")
    assert result.status == "success"
```

### 5. Slow Tests

❌ **Bad**: Unnecessary delays
```python
def test_analysis():
    time.sleep(5)  # Unnecessary delay
    result = service.analyze_ticker("RELIANCE.NS")
```

✅ **Good**: Fast, efficient tests
```python
def test_analysis():
    result = service.analyze_ticker("RELIANCE.NS")  # Fast execution
    assert result.status == "success"
```

---

## References

- [PROJECT_RULES.md](../../PROJECT_RULES.md) - Overall project rules
- [pytest.ini](../../pytest.ini) - Pytest configuration
- [tests/conftest.py](../../tests/conftest.py) - Shared fixtures
- [documents/testing/](../testing/) - Additional testing documentation

---

**Last Updated**: 2025-11-07

