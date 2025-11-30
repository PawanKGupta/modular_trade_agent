# Project Rules - Rebound — Modular Trade Agent

**Version:** 1.0  
**Last Updated:** 2025-11-07  
**Status:** Active

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Principles](#architecture-principles)
3. [Development Guidelines](#development-guidelines)
4. [Code Quality Standards](#code-quality-standards)
5. [Testing Requirements](#testing-requirements)
6. [Documentation Standards](#documentation-standards)
7. [Deployment & Operations](#deployment--operations)
8. [Security Practices](#security-practices)
9. [Version Control & Release Management](#version-control--release-management)
10. [Technology Stack](#technology-stack)

---

## Project Overview

### Purpose
Rebound — Modular Trade Agent is a professional-grade **cloud-automated trading system** for Indian stock markets (NSE) specializing in **RSI10 < 30 reversal strategy** with multi-timeframe analysis and historical backtesting validation.

### Core Strategy
- **Entry Signal**: RSI10 < 30 (oversold) + Price > EMA200 (uptrend) + Volume ≥ 80% average
- **Risk Management**: Support-based stop losses (5-6%), resistance-aware targets (2-4x risk-reward)
- **Validation**: 2-year historical backtesting with combined scoring (50% current + 50% historical)

### Key Features
- Cloud automation via GitHub Actions (4PM IST weekdays)
- Multi-timeframe analysis (Daily + Weekly)
- Intelligent backtesting with priority ranking
- Kotak Neo broker integration
- Telegram notifications
- ML-enhanced verdict system (optional)

---

## Architecture Principles

### 1. Clean Architecture Pattern
- **Domain Layer** (`src/domain/`): Business entities and rules
- **Application Layer** (`src/application/`): Use cases and orchestration
- **Infrastructure Layer** (`src/infrastructure/`): External adapters (APIs, storage)
- **Presentation Layer** (`src/presentation/`): CLI, Telegram formatting

### 2. Service Layer Pattern (Primary)
- **Services** (`services/`): Main business logic orchestration
  - `AnalysisService`: Core analysis orchestrator
  - `DataService`: Data fetching and caching
  - `IndicatorService`: Technical indicator calculations
  - `SignalService`: Signal detection
  - `VerdictService`: Trade verdict determination
  - `ScoringService`: Multi-factor scoring
  - `BacktestService`: Historical validation
  - `MLService`: Machine learning predictions (optional)

### 3. Modular Design
- **Modules** (`modules/`): Self-contained feature modules
  - `kotak_neo_auto_trader/`: Broker integration module
- **Core** (`core/`): Legacy code (deprecated, use services instead)
- **Backtest** (`backtest/`): Standalone backtesting framework

### 4. Dependency Injection
- Services accept dependencies via constructor injection
- Use interfaces/abstract classes for external dependencies
- Enable easy testing and swapping implementations

### 5. Event-Driven Architecture (Phase 3+)
- `EventBus` for decoupled communication
- `Pipeline` pattern for sequential processing
- Async support for batch operations

### 6. Configuration Management
- Centralized config in `config/strategy_config.py` (StrategyConfig dataclass)
- Environment variables via `.env` files
- No hardcoded magic numbers

---

## Development Guidelines

### 1. Python Standards
- **Python Version**: 3.12+ (minimum 3.9 for ML features)
- **Formatting**: Black (max line length: 88)
- **Type Hints**: Required for all functions and methods
- **Docstrings**: Google style for all public functions/classes
- **String Formatting**: Prefer f-strings over `.format()` or `%`

### 2. Code Organization
- **New Features**: Add to `services/` layer (not `core/`)
- **Legacy Code**: Mark deprecated, migrate to services gradually
- **Modules**: Keep self-contained, minimal cross-module dependencies
- **Utils**: Shared utilities in `utils/` (logger, retry, circuit breaker)

### 3. Import Organization
```python
# Standard library
import os
from typing import Optional

# Third-party
import pandas as pd
from dotenv import load_dotenv

# Local imports
from services import AnalysisService
from config.strategy_config import StrategyConfig
```

### 4. Error Handling
- Use `RetryHandler` for external API calls
- Use `CircuitBreaker` for unreliable services
- Specific exception types (not generic `Exception`)
- Log errors with context (ticker, operation, error details)

### 5. Async Programming (Phase 2+)
- Use `AsyncAnalysisService` for batch operations
- Prefer `asyncio` for I/O-bound operations
- Use `aiohttp` for async HTTP requests
- Throttle concurrent requests to respect rate limits

### 6. Data Structures
- Use typed dataclasses (`services/models.py`) instead of dicts
- Type hints for all function parameters and returns
- Avoid mutable default arguments

---

## Code Quality Standards

### 1. SOLID Principles
- **Single Responsibility**: Each service/class has one clear purpose
- **Open/Closed**: Extend via composition, not modification
- **Liskov Substitution**: Interfaces must be substitutable
- **Interface Segregation**: Small, focused interfaces
- **Dependency Inversion**: Depend on abstractions, not concretions

### 2. Code Complexity
- Maximum function length: 50 lines (exceptions with justification)
- Maximum cyclomatic complexity: 10
- Avoid deep nesting (max 3 levels)

### 3. Naming Conventions
- **Classes**: PascalCase (`AnalysisService`)
- **Functions/Methods**: snake_case (`analyze_ticker`)
- **Constants**: UPPER_SNAKE_CASE (`RSI_OVERSOLD`)
- **Private Methods**: Leading underscore (`_internal_method`)
- **Type Variables**: Single uppercase letter (`T`, `K`, `V`)

### 4. Documentation
- Public APIs must have docstrings
- Complex logic requires inline comments
- Update docstrings when changing function signatures
- Document breaking changes in CHANGELOG.md

### 5. Deprecation Policy
- Mark deprecated code with `@deprecated` decorator
- Provide migration path in deprecation message
- Remove deprecated code after 2 major versions
- Use `utils/deprecation.py` for consistent warnings

---

## Testing Requirements

### 1. Test Organization
- **Unit Tests**: `tests/unit/` (mirror source structure)
  - `tests/unit/services/` - Service layer tests
  - `tests/unit/domain/` - Domain entity tests
  - `tests/unit/infrastructure/` - Infrastructure adapter tests
  - `tests/unit/presentation/` - CLI/formatter tests
  - `tests/unit/kotak/` - Broker integration tests
- **Integration Tests**: `tests/integration/`
  - `tests/integration/kotak/` - Broker integration workflows
  - `tests/integration/use_cases/` - Use case integration tests
  - `tests/integration/test_ml_pipeline.py` - ML pipeline tests
- **Regression Tests**: `tests/regression/` - Bug fix validation
- **E2E Tests**: `tests/e2e/` - End-to-end workflows
- **Performance Tests**: `tests/performance/` - Performance benchmarks
- **Security Tests**: `tests/security/` - Security validation
- **Test Files**: `test_*.py` naming convention
- **Test Classes**: `Test*` naming convention (optional, prefer functions)

### 2. Test Coverage
- **Minimum Coverage**: 80% for new code
- **Critical Paths**: 95%+ (trading logic, order execution, authentication)
- **Coverage Reports**: Generate HTML in `logs/htmlcov/`
- **Coverage Configuration**: Defined in `pytest.ini`
- **Coverage Scope**: `src/` directory (excludes tests, `__pycache__`, site-packages)
- **Coverage Reports**: HTML (logs/htmlcov), terminal (term-missing), fail-under=0 (warnings only)

### 3. Test Requirements
- **Mandatory Tests**: Every new function/module must have at least one test
- **Framework**: Use `pytest` exclusively
- **Fixtures**: Use `conftest.py` for shared fixtures (project root and per-directory)
- **Mocking**: Mock all external dependencies (APIs, file I/O, network calls)
- **Temporary Files**: Use `tmp_path` or `tmpdir` fixtures (never hardcode paths)
- **Test Isolation**: Each test must be independent (no shared state)
- **Test Markers**: Use pytest markers (`@pytest.mark.unit`, `@pytest.mark.integration`, etc.)
- **Async Tests**: Use `pytest-asyncio` for async test functions
- **Parametrize**: Use `@pytest.mark.parametrize` for testing multiple scenarios

### 4. Test Structure & Best Practices
- **Arrange-Act-Assert**: Follow AAA pattern in test functions
- **Descriptive Names**: Test names should describe what is being tested
  - Good: `test_analysis_service_returns_buy_verdict_when_rsi_below_30`
  - Bad: `test_analysis_service`
- **One Assertion Per Test**: Prefer multiple focused tests over one test with many assertions
- **Test Fixtures**: Reuse fixtures from `tests/conftest.py` (sample_stock, sample_analysis_result, etc.)
- **Mock Services**: Use `mock_data_service`, `mock_scoring_service` fixtures for service dependencies
- **Error Testing**: Test both success and failure paths
- **Edge Cases**: Test boundary conditions, empty inputs, None values

### 5. Running Tests
```bash
# Quick test run (quiet mode)
.\.venv\Scripts\python.exe -m pytest -q

# Verbose output
.\.venv\Scripts\python.exe -m pytest -v

# With coverage (HTML report)
.\.venv\Scripts\python.exe -m pytest --cov=. --cov-report=html

# Specific test file
.\.venv\Scripts\python.exe -m pytest tests/unit/services/test_analysis_service.py

# Specific test function
.\.venv\Scripts\python.exe -m pytest tests/unit/services/test_analysis_service.py::test_analyze_ticker

# Run only unit tests
.\.venv\Scripts\python.exe -m pytest -m unit

# Run only integration tests
.\.venv\Scripts\python.exe -m pytest -m integration

# Run tests matching pattern
.\.venv\Scripts\python.exe -m pytest -k "test_analysis"

# Run with specific markers
.\.venv\Scripts\python.exe -m pytest -m "not slow"

# Run tests in parallel (if pytest-xdist installed)
.\.venv\Scripts\python.exe -m pytest -n auto
```

### 6. Test Data Management
- **No Sensitive Data**: Do not commit API keys, tokens, real trade data
- **Fixtures**: Use fixtures for reusable test data (`tests/conftest.py`)
- **Golden Files**: Store expected outputs in `tests/data/golden/` for regression tests
- **Mock Data**: Use `unittest.mock` or `pytest-mock` for API responses
- **Temporary Files**: Use `tmp_path` fixture, clean up in teardown
- **Test Data Files**: Place in `tests/data/` (gitignored if sensitive)
- **Never Hit Real APIs**: All external API calls must be mocked

### 7. Test Categories & Markers
- **@pytest.mark.unit**: Fast, isolated unit tests (default)
- **@pytest.mark.integration**: Slower tests with real dependencies
- **@pytest.mark.e2e**: End-to-end workflow tests (slowest)
- **@pytest.mark.slow**: Tests that take significant time
- **@pytest.mark.backtest**: Tests involving backtest logic
- **@pytest.mark.security**: Security tests (secrets, auth, injection)
- **@pytest.mark.performance**: Performance/benchmark tests

### 8. Test Configuration
- **Pytest Config**: `pytest.ini` in project root
- **Test Discovery**: `test_*.py` files, `Test*` classes, `test_*` functions
- **Test Paths**: `testpaths = tests` (all tests under tests/)
- **Python Path**: `pythonpath = .` (project root in path)
- **Output**: Verbose by default, short traceback format
- **Warnings**: Suppressed by default (`-p no:warnings`)

### 9. Integration Test Requirements
- **Broker Integration**: Test Kotak Neo API interactions (mocked)
- **Service Integration**: Test service layer interactions
- **Use Case Integration**: Test complete use case workflows
- **ML Pipeline**: Test ML service integration (if enabled)
- **Database/Storage**: Test data persistence (if applicable)

### 10. Regression Test Requirements
- **Bug Fixes**: Add regression test for every bug fix
- **Golden Files**: Compare against expected outputs
- **Continuous Service**: Test long-running service scenarios
- **Historical Validation**: Ensure fixes don't break existing functionality

### 11. Performance Test Requirements
- **Benchmarks**: Test indicator calculations, data fetching performance
- **Service Performance**: Test analysis service throughput
- **Memory Usage**: Monitor memory consumption in tests
- **Timing**: Use `pytest-benchmark` for performance metrics

### 12. Security Test Requirements
- **Credential Handling**: Test that credentials are never logged or exposed
- **API Security**: Test input validation, injection prevention
- **Authentication**: Test JWT expiry, 2FA handling, session management
- **Data Sanitization**: Test that sensitive data is properly sanitized

---

## Documentation Standards

### 1. Documentation Structure
- **Root Documentation**:
  - `README.md` - Project overview, quick start, features
  - `CHANGELOG.md` - Version history, changes, breaking changes
  - `PROJECT_RULES.md` - This document (project rules and standards)
  - `CONTRIBUTING.md` - Contribution guidelines
  - `MAINTAINERS.md` - Maintenance processes and ownership
  - `SECURITY.md` - Security policies and reporting
- **Getting Started**: `documents/getting-started/`
  - `GETTING_STARTED.md` - Complete beginner's guide
  - `DOCUMENTATION_INDEX.md` - Comprehensive documentation index
  - `PYTHON_SETUP.md` - Python environment setup
  - `QUICK_NAV.md` - Quick navigation guide
- **Architecture**: `documents/architecture/` - System design and architecture docs
- **Features**: `documents/features/` - Feature documentation and guides
- **Deployment**: `documents/deployment/` - Platform-specific deployment guides
  - `windows/` - Windows deployment (executable, services, tasks)
  - `ubuntu/` - Ubuntu/Linux deployment (systemd, cron)
  - `oracle/` - Oracle Cloud deployment
  - `gcp/` - Google Cloud Platform deployment
- **Testing**: `documents/testing/` - Testing guides and test results
- **Reference**: `documents/reference/` - Command references, API docs
- **Phases**: `documents/phases/` - Phase completion documentation

### 2. Documentation Requirements
- **README.md Updates**: Required for all user-facing changes
  - New features must be documented
  - Configuration changes must be explained
  - Installation steps must be updated
  - Usage examples must be current
- **CHANGELOG.md Updates**: Required for all releases
  - Use format: `## [Version] - YYYY-MM-DD`
  - Categorize: Added, Changed, Deprecated, Removed, Fixed, Security
  - Link to related issues/PRs
  - Document breaking changes prominently
- **Breaking Changes**: Must be documented prominently
  - Mark with ⚠️ BREAKING CHANGE in CHANGELOG
  - Provide migration guide
  - Update affected documentation
- **Documentation Index**: Keep `documents/getting-started/DOCUMENTATION_INDEX.md` updated
  - Add new documents to index
  - Update links when moving documents
  - Maintain logical organization

### 3. Code Documentation (Docstrings)
- **Module-Level Docstrings**: Required for all modules
  ```python
  """
  Module Description
  
  This module provides [purpose]. It handles [key functionality]
  and integrates with [dependencies].
  
  Example:
      Basic usage example here.
  """
  ```
- **Class Docstrings**: Google style with attributes and methods
  ```python
  class AnalysisService:
      """
      Service for analyzing stock tickers.
      
      This service orchestrates the analysis pipeline including data
      fetching, indicator calculation, signal generation, and verdict
      determination.
      
      Attributes:
          config: Strategy configuration instance
          data_service: Data fetching service
          indicator_service: Technical indicator calculator
      
      Example:
          >>> service = AnalysisService()
          >>> result = service.analyze_ticker("RELIANCE.NS")
          >>> print(result.verdict)
          'buy'
      """
  ```
- **Function/Method Docstrings**: Google style with Args, Returns, Raises
  ```python
  def analyze_ticker(
      self, 
      ticker: str, 
      enable_mtf: bool = True
  ) -> AnalysisResult:
      """
      Analyze a single stock ticker.
      
      Performs comprehensive technical analysis including RSI calculation,
      EMA200 trend confirmation, volume analysis, and multi-timeframe
      alignment scoring.
      
      Args:
          ticker: Stock ticker symbol (e.g., "RELIANCE.NS")
          enable_mtf: Enable multi-timeframe analysis (default: True)
      
      Returns:
          AnalysisResult containing verdict, trading parameters, and scores
      
      Raises:
          DataError: If stock data cannot be fetched
          IndicatorError: If indicator calculation fails
          AnalysisError: If analysis process fails
      
      Example:
          >>> service = AnalysisService()
          >>> result = service.analyze_ticker("RELIANCE.NS")
          >>> print(f"Verdict: {result.verdict}, RSI: {result.rsi}")
          Verdict: buy, RSI: 28.5
      """
  ```
- **Inline Comments**: Required for complex algorithms
  - Explain "why" not "what" (code should be self-documenting)
  - Document non-obvious business logic
  - Explain workarounds or temporary solutions
  - Reference external algorithms or formulas

### 4. API Documentation
- **Public APIs**: All public functions/classes must be documented
  - Include purpose and usage
  - Document all parameters and return types
  - Provide code examples
  - Document exceptions that may be raised
- **Usage Examples**: Include in docstrings and feature docs
  - Show basic usage
  - Show advanced usage
  - Show error handling
- **Parameter Documentation**: Document all parameters
  - Type hints required
  - Default values explained
  - Optional vs required parameters
- **Deprecated APIs**: Must document deprecation
  - Use `@deprecated` decorator
  - Provide migration path
  - Include version when deprecated
  - Include removal timeline

### 5. Feature Documentation
- **New Features**: Create documentation in `documents/features/`
  - Feature overview and purpose
  - Configuration options
  - Usage examples
  - Integration guide
  - Troubleshooting section
- **Feature Updates**: Update existing feature docs
  - Document new options
  - Update examples
  - Note breaking changes
- **Code Examples**: Include in all feature docs
  - Basic usage
  - Advanced usage
  - Integration examples
  - Error handling examples

### 6. Deployment Documentation
- **Platform Guides**: Create/update platform-specific guides
  - Installation steps
  - Configuration requirements
  - Service setup instructions
  - Troubleshooting common issues
- **Quick Start Guides**: Provide quick start for each platform
  - Minimal steps to get running
  - Link to detailed guides
- **Update Frequency**: Update when deployment process changes
  - Test deployment steps before documenting
  - Include screenshots for GUI steps
  - Provide command-line examples

### 7. Architecture Documentation
- **System Architecture**: Document in `documents/architecture/`
  - High-level system design
  - Component interactions
  - Data flow diagrams
  - Technology stack
- **Design Decisions**: Document important design decisions
  - Why certain patterns were chosen
  - Trade-offs considered
  - Alternatives evaluated
- **Evolution**: Document architectural evolution
  - Phase transitions (see `SYSTEM_ARCHITECTURE_EVOLUTION.md`)
  - Migration guides
  - Deprecation timelines

### 8. Testing Documentation
- **Test Guides**: Document in `documents/testing/`
  - How to run tests
  - Test organization structure
  - Writing new tests
  - Test fixtures and utilities
- **Test Results**: Document significant test results
  - Performance benchmarks
  - Coverage improvements
  - Bug fix validations
- **Test Examples**: Include examples of test patterns
  - Unit test examples
  - Integration test examples
  - Mock usage examples

### 9. Documentation Formatting
- **Markdown**: Use Markdown for all documentation
- **Code Blocks**: Use syntax highlighting
  ```python
  # Python code example
  ```
  ```bash
  # Bash command example
  ```
- **Headers**: Use proper heading hierarchy (H1 → H2 → H3)
- **Lists**: Use consistent list formatting
- **Links**: Use relative links for internal docs
- **Tables**: Use Markdown tables for structured data
- **Diagrams**: Use Mermaid or ASCII art for diagrams

### 10. Documentation Maintenance
- **Review Frequency**: Review documentation quarterly
- **Outdated Content**: Mark outdated content, update or remove
- **Broken Links**: Fix broken links immediately
- **Version Alignment**: Keep docs aligned with code version
- **User Feedback**: Incorporate user feedback and questions
- **Searchability**: Use descriptive titles and keywords

### 11. Documentation Review Checklist
- [ ] All new features documented
- [ ] Code examples tested and working
- [ ] Links verified (no broken links)
- [ ] Screenshots updated (if applicable)
- [ ] CHANGELOG.md updated
- [ ] Documentation index updated
- [ ] README.md reflects current state
- [ ] Breaking changes documented prominently

---

## Deployment & Operations

### 1. Deployment Platforms
- **Windows**: Executable, Windows Service, Task Scheduler
- **Ubuntu/Linux**: Systemd services, cron jobs
- **Cloud**: GitHub Actions, Oracle Cloud, GCP

### 2. Environment Configuration
- Use `.env` files for local development (`cred.env`)
- Never commit `.env` files (use `.gitignore`)
- Document required environment variables in README
- Use environment-specific configs for different deployments

### 3. Logging
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Log Files**: `logs/trade_agent_YYYYMMDD.log`
- **Structured Logging**: Timestamp, module, level, message
- **Rotation**: Daily log files, archive old logs

### 4. Monitoring
- Health check endpoint/script (`health_check.py`)
- Telegram notifications for critical errors
- Monitor log files for errors
- Track signal performance over time

### 5. Build & Packaging
- **Windows Executable**: `scripts/build/build.ps1`
- **Installer**: `scripts/build/build_installer.ps1`
- **PyInstaller Spec**: `build/build_executable.spec`
- **Version Management**: CalVer (YY.Q.PATCH) in `VERSION` file

---

## Security Practices

### 1. Credentials Management
- **Never hardcode** API keys, tokens, or passwords
- Store secrets in `.env` files (not committed)
- Use environment variables for production
- Rotate credentials regularly

### 2. API Security
- Validate all API inputs
- Use retry logic with exponential backoff
- Implement circuit breakers for unreliable services
- Rate limit API calls to prevent abuse

### 3. Data Security
- Do not commit sensitive data (trades, positions, credentials)
- Encrypt sensitive data at rest (if required)
- Use secure connections (HTTPS) for API calls
- Sanitize log output (no credentials in logs)

### 4. Code Security
- Avoid `eval()` and `exec()` unless explicitly justified
- Validate user inputs
- Use parameterized queries (if using databases)
- Keep dependencies updated (check for vulnerabilities)

---

## Version Control & Release Management

### 1. Versioning
- **Scheme**: CalVer (YY.Q.PATCH)
  - YY: Year (25 for 2025)
  - Q: Quarter (1-4)
  - PATCH: Incremental patch number
- **Version File**: `VERSION` (single line, e.g., "25.4.1")
- **Git Tags**: Tag releases with version number

### 2. Branch Strategy
- **Main Branch**: `main` (production-ready code)
- **Feature Branches**: `feature/feature-name`
- **Bug Fixes**: `fix/bug-description`
- **Hotfixes**: `hotfix/critical-fix`

### 3. Commit Policy
- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`
- **Descriptive Messages**: Clear, concise commit messages
- **Scope**: Keep commits focused (one logical change per commit)
- **Approval Required**: Never push without explicit approval

### 4. Pull Request Process
1. Create feature branch from `main`
2. Make changes with tests and documentation
3. Run full test suite locally
4. Update CHANGELOG.md if needed
5. Open PR with clear description
6. Wait for approval before merging

### 5. Release Process
1. Update `VERSION` file (CalVer)
2. Update CHANGELOG.md with changes
3. Update documentation (README, guides)
4. Run full test suite
5. Verify coverage not regressed
6. Build installer/executable if applicable
7. Tag release: `git tag v25.4.1`
8. Create release notes

---

## Technology Stack

### 1. Core Dependencies
- **Data Processing**: pandas 2.3.3, numpy 2.2.6
- **Market Data**: yfinance 0.2.66
- **Technical Analysis**: pandas-ta 0.3.14b0 / 0.4.71b0 (Python version dependent)
- **Web Scraping**: selenium 4.37.0, beautifulsoup4 4.14.2
- **Async**: aiohttp 3.11.11, asyncio-throttle 1.0.2

### 2. ML Dependencies (Optional)
- **Scikit-learn**: >=1.3.0
- **XGBoost**: >=2.0.0
- **Joblib**: >=1.3.0

### 3. Broker Integration
- **Kotak Neo API**: git+https://github.com/Kotak-Neo/kotak-neo-api@67143c58f29da9572cdbb273199852682a0019d5 (Python < 3.12 only)

### 4. Development Tools
- **Testing**: pytest
- **Formatting**: black
- **Type Checking**: mypy (recommended)
- **Linting**: flake8 or pylint (recommended)

### 5. Python Version Support
- **Primary**: Python 3.12+
- **Minimum**: Python 3.9 (for ML features)
- **Virtual Environment**: Use `.venv` in project root

---

## Project-Specific Rules

### 1. Trading Strategy Rules
- **RSI Period**: 10 (not configurable without strategy review)
- **EMA Period**: 200 (long-term trend confirmation)
- **Volume Threshold**: 80% of 20-day average (minimum liquidity)
- **Support-Based Stops**: 5-6% typical, minimum 3%
- **Risk-Reward**: Target 2-4x ratios

### 2. Data Requirements
- **Minimum Data**: 800+ days for accurate EMA200 calculation
- **Lookback Periods**: 90 days default, adaptive based on availability
- **Data Validation**: Check data quality before analysis
- **Data Leakage Prevention**: Exclude current-day data in backtests

### 3. Backtesting Rules
- **Historical Period**: 2 years minimum for validation
- **Combined Scoring**: 50% current analysis + 50% historical performance
- **Filtering**: Exclude stocks with poor track records or insufficient data
- **Strategy Consistency**: Use same RSI10 strategy rules for validation

### 4. Broker Integration Rules
- **Kotak Neo Module**: Self-contained in `modules/kotak_neo_auto_trader/`
- **Authentication**: Handle JWT expiry and 2FA properly
- **Order Management**: Track orders, handle rejections, retry logic
- **Position Monitoring**: Continuous monitoring with retry on failures
- **Error Handling**: Circuit breakers for API failures

### 5. File Organization Rules
- **Temporary Files**: Use `temp/` directory (not committed)
- **Logs**: `logs/` directory (gitignored)
- **Data**: `data/` directory (gitignored for sensitive data)
- **Build Artifacts**: `build/`, `dist/` (gitignored)
- **Documentation**: All docs in `documents/` subdirectories

---

## Enforcement & Compliance

### 1. Pre-Commit Checks
- Run tests before committing
- Check code formatting (black)
- Verify no hardcoded credentials
- Ensure documentation updated

### 2. Code Review Checklist
- [ ] Follows architecture principles
- [ ] Has appropriate tests (80%+ coverage)
- [ ] Documentation updated
- [ ] No hardcoded values
- [ ] Error handling implemented
- [ ] Type hints included
- [ ] Docstrings present
- [ ] CHANGELOG updated (if needed)

### 3. Continuous Integration
- Automated test runs on PRs
- Coverage reports generated
- Linting checks (if configured)
- Build verification (if applicable)

---

## Exceptions & Special Cases

### 1. Legacy Code (`core/` directory)
- Mark as deprecated with migration path
- Do not add new features to `core/`
- Migrate to `services/` layer gradually
- Document deprecation timeline

### 2. Experimental Features
- Use `temp/` directory for experiments
- Do not commit experimental code to main branch
- Document experiments before deletion

### 3. Critical Hotfixes
- May bypass some rules for urgent fixes
- Must add tests and documentation in follow-up PR
- Document exception in commit message

---

## Updates & Maintenance

### 1. Rule Updates
- Update this document when architecture changes
- Version the rules document
- Announce breaking rule changes in team communication
- Review rules quarterly

### 2. Rule Violations
- Document violations and rationale
- Plan migration path for violations
- Update rules if violations reveal gaps

---

## References

- [README.md](README.md) - Project overview and quick start
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [MAINTAINERS.md](MAINTAINERS.md) - Maintenance processes
- [documents/SYSTEM_ARCHITECTURE_EVOLUTION.md](documents/SYSTEM_ARCHITECTURE_EVOLUTION.md) - Architecture details
- [documents/getting-started/DOCUMENTATION_INDEX.md](documents/getting-started/DOCUMENTATION_INDEX.md) - Documentation index

---

**Last Review Date**: 2025-11-07  
**Next Review Date**: 2026-02-07 (Quarterly)
