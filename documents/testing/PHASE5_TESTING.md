# Phase 5: Testing - Implementation Guide

## Overview
Comprehensive testing strategy for the modular trading agent with unit tests, integration tests, and end-to-end tests.

## Test Infrastructure ✅

### Setup Complete
- ✅ **pytest.ini** - Pytest configuration with coverage settings
- ✅ **conftest.py** - Shared fixtures and test configuration
- ✅ **Test directory structure** - Organized by test type
- ✅ **Sample unit tests** - Domain entity tests as examples

### Directory Structure
```
tests/
├── __init__.py
├── conftest.py                    # Shared fixtures
├── unit/                          # Unit tests (fast, isolated)
│   ├── __init__.py
│   ├── test_domain_entities.py    ✅ Created
│   ├── test_value_objects.py      # TODO
│   ├── test_services.py           # TODO
│   └── test_use_cases.py          # TODO
├── integration/                   # Integration tests
│   ├── __init__.py
│   └── test_workflows.py          # TODO
└── e2e/                          # End-to-end tests
    ├── __init__.py
    └── test_cli_commands.py       # TODO
```

## Running Tests

### Install Test Dependencies
```bash
pip install pytest pytest-cov pytest-mock
```

### Run All Tests
```bash
pytest
```

### Run Specific Test Types
```bash
# Unit tests only (fast)
pytest -m unit

# Integration tests
pytest -m integration

# End-to-end tests
pytest -m e2e

# Exclude slow tests
pytest -m "not slow"
```

### Run Tests with Coverage
```bash
# Coverage with HTML report
pytest --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html  # Mac/Linux
start htmlcov/index.html  # Windows
```

### Run Specific Test File
```bash
pytest tests/unit/test_domain_entities.py
```

### Run Specific Test
```bash
pytest tests/unit/test_domain_entities.py::TestStock::test_stock_creation
```

## Test Categories

### 1. Unit Tests (✅ Started)
**Purpose**: Test individual components in isolation

**Characteristics**:
- Fast execution (< 1s per test)
- No external dependencies
- Use mocks for dependencies
- High code coverage target (>80%)

**Created Tests**:
- ✅ `test_domain_entities.py` - Stock, Signal, AnalysisResult, TradingParameters

**Remaining**:
- Value objects (Price, Volume)
- Services (ScoringService, FilteringService)
- Use cases (with mocked dependencies)

### 2. Integration Tests
**Purpose**: Test component interactions

**Characteristics**:
- Moderate speed (1-5s per test)
- Real dependencies (no mocks)
- Test full workflows
- Database/API interactions

**To Create**:
- Full analysis workflow
- Backtest integration
- Alert sending flow

### 3. End-to-End Tests
**Purpose**: Test complete user scenarios

**Characteristics**:
- Slower execution (5-30s per test)
- Full system integration
- CLI command execution
- Real data (when safe)

**To Create**:
- CLI analyze command
- CLI backtest command
- CSV export verification

## Test Fixtures

### Available Fixtures (in conftest.py)

#### Domain Entities
```python
sample_stock           # Stock entity
sample_buy_signal      # BUY signal
sample_strong_buy_signal  # STRONG_BUY signal
sample_analysis_result # Analysis result
```

#### Value Objects
```python
sample_price          # Price with currency
sample_volume         # Volume with average
```

#### DTOs
```python
sample_analysis_request      # Single stock request
sample_bulk_analysis_request # Bulk request
sample_analysis_response     # Analysis response
```

#### Mocks
```python
mock_data_service        # Mocked data provider
mock_scoring_service     # Mocked scoring
mock_notification_service # Mocked notifications
```

#### Test Data
```python
sample_legacy_analysis_result # Legacy format dict
```

## Writing Tests

### Example: Unit Test
```python
def test_stock_creation(sample_stock):
    """Test creating a stock"""
    assert sample_stock.ticker == "RELIANCE.NS"
    assert sample_stock.is_valid()
```

### Example: Test with Mock
```python
def test_analyze_use_case(mock_scoring_service):
    """Test analysis use case with mocked scoring"""
    use_case = AnalyzeStockUseCase(scoring_service=mock_scoring_service)
    
    # Mock returns
    mock_scoring_service.compute_strength_score.return_value = 75.0
    
    result = use_case.execute(request)
    
    # Verify mock was called
    mock_scoring_service.compute_strength_score.assert_called_once()
    assert result.strength_score == 75.0
```

### Example: Integration Test
```python
@pytest.mark.integration
def test_full_analysis_workflow():
    """Test complete analysis workflow with real services"""
    container = DIContainer()
    use_case = container.bulk_analyze_use_case
    
    request = BulkAnalysisRequest(tickers=["RELIANCE.NS"])
    response = use_case.execute(request)
    
    assert response.total_analyzed == 1
    assert response.successful > 0
```

### Example: Parametrized Test
```python
@pytest.mark.parametrize("score,expected", [
    (75.0, True),
    (25.0, False),
    (0.0, False),
])
def test_buyable_threshold(score, expected):
    """Test buyable threshold logic"""
    signal = Signal("TEST.NS", SignalType.BUY, datetime.now(), score)
    assert signal.is_buyable() == expected
```

## Coverage Goals

### Minimum Coverage Targets
- **Overall**: 70% (enforced in pytest.ini)
- **Domain Layer**: 90% (critical business logic)
- **Application Layer**: 80% (use cases and services)
- **Infrastructure Layer**: 60% (external dependencies)
- **Presentation Layer**: 70% (CLI commands)

### Current Coverage
Run `pytest --cov` to see current coverage.

```bash
# Generate coverage report
pytest --cov=src --cov-report=term-missing

# View detailed HTML report
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Test Best Practices

### DO ✅
- Write tests before or alongside code (TDD)
- Test one thing per test
- Use descriptive test names
- Use fixtures for common setup
- Mock external dependencies in unit tests
- Test both success and failure cases
- Test edge cases and boundaries
- Keep tests fast and independent

### DON'T ❌
- Test implementation details
- Create test dependencies (test order)
- Use sleep() for timing
- Hardcode paths or credentials
- Skip tests without good reason
- Write overly complex tests
- Test framework code
- Ignore failing tests

## Continuous Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-cov
      - run: pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Next Steps

### Immediate (Phase 5)
1. ✅ Set up test infrastructure
2. ✅ Create sample domain tests
3. ⏳ Complete unit tests for all layers
4. ⏳ Write integration tests
5. ⏳ Add e2e CLI tests
6. ⏳ Achieve 70%+ coverage

### Future Enhancements
- Property-based testing (Hypothesis)
- Performance benchmarks
- Load testing
- Mutation testing
- Contract testing for APIs

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Make sure project root is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or run from project root
cd /path/to/modular_trade_agent
pytest
```

**Coverage Not Working**
```bash
# Ensure pytest-cov is installed
pip install pytest-cov

# Check pytest.ini configuration
cat pytest.ini
```

**Tests Running Slow**
```bash
# Run unit tests only
pytest -m unit

# Run in parallel (requires pytest-xdist)
pip install pytest-xdist
pytest -n auto
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Testing Best Practices](https://docs.pytest.org/en/latest/explanation/goodpractices.html)
- [Mocking Guide](https://docs.python.org/3/library/unittest.mock.html)

---

**Phase 5 Status**: 🟡 **IN PROGRESS**  
**Test Infrastructure**: ✅ **COMPLETE**  
**Unit Tests**: 🟡 **STARTED** (Domain entities done)  
**Integration Tests**: ⏳ **TODO**  
**E2E Tests**: ⏳ **TODO**  
**Coverage**: ⏳ **TBD** (run pytest --cov to check)
