# Documentation Rules & Guidelines

**Version:** 1.0  
**Last Updated:** 2025-11-07  
**Status:** Active

---

## Table of Contents

1. [Overview](#overview)
2. [Documentation Structure](#documentation-structure)
3. [Writing Documentation](#writing-documentation)
4. [Code Documentation](#code-documentation)
5. [API Documentation](#api-documentation)
6. [Feature Documentation](#feature-documentation)
7. [Deployment Documentation](#deployment-documentation)
8. [Documentation Formatting](#documentation-formatting)
9. [Maintenance & Review](#maintenance--review)
10. [Templates & Examples](#templates--examples)

---

## Overview

### Purpose
This document provides comprehensive rules and guidelines for writing, organizing, and maintaining documentation in the Modular Trade Agent project. All developers must follow these rules to ensure documentation quality, consistency, and usability.

### Documentation Philosophy
- **User-Centric**: Write for the user, not for yourself
- **Comprehensive**: Document everything users need to know
- **Up-to-Date**: Keep documentation synchronized with code
- **Accessible**: Make documentation easy to find and navigate
- **Examples**: Include working code examples

---

## Documentation Structure

### Root-Level Documentation

```
modular_trade_agent/
├── README.md                    # Project overview, quick start
├── CHANGELOG.md                 # Version history, changes
├── PROJECT_RULES.md             # Project rules and standards
├── CONTRIBUTING.md              # Contribution guidelines
├── MAINTAINERS.md               # Maintenance processes
├── SECURITY.md                  # Security policies
└── documents/                   # All project documentation
```

### Documents Directory Structure

```
documents/
├── getting-started/             # Beginner guides
│   ├── GETTING_STARTED.md
│   ├── DOCUMENTATION_INDEX.md
│   ├── PYTHON_SETUP.md
│   └── QUICK_NAV.md
├── architecture/                # System design docs
│   ├── ARCHITECTURE_GUIDE.md
│   └── SYSTEM_ARCHITECTURE_EVOLUTION.md
├── features/                    # Feature documentation
│   ├── BACKTEST_INTEGRATION.md
│   ├── ML_IMPLEMENTATION_GUIDE.md
│   └── ...
├── deployment/                  # Deployment guides
│   ├── windows/
│   ├── ubuntu/
│   ├── oracle/
│   └── gcp/
├── testing/                     # Testing guides
│   ├── TESTING_RULES.md
│   └── ...
├── reference/                   # API references
│   ├── COMMANDS.md
│   └── CLI_USAGE.md
└── phases/                      # Phase documentation
```

### Documentation Categories

1. **Getting Started**: Beginner-friendly guides
2. **Architecture**: System design and patterns
3. **Features**: Feature-specific documentation
4. **Deployment**: Platform-specific deployment guides
5. **Testing**: Testing guides and test results
6. **Reference**: API references and command guides
7. **Phases**: Development phase documentation

---

## Writing Documentation

### Documentation Principles

1. **Clarity**: Use clear, simple language
2. **Completeness**: Cover all aspects users need
3. **Accuracy**: Ensure information is correct
4. **Consistency**: Use consistent terminology and formatting
5. **Examples**: Include practical code examples

### Target Audience

Consider your audience:
- **Beginners**: Need step-by-step guides
- **Intermediate Users**: Need feature documentation
- **Advanced Users**: Need API references and architecture docs
- **Contributors**: Need contribution guidelines and code structure

### Documentation Types

1. **Tutorials**: Step-by-step learning guides
2. **How-To Guides**: Task-oriented instructions
3. **Reference**: API and command references
4. **Explanation**: Architecture and design decisions

---

## Code Documentation

### Module-Level Docstrings

**Required for all modules:**

```python
"""
Module Description

This module provides [purpose]. It handles [key functionality]
and integrates with [dependencies].

Key Features:
    - Feature 1 description
    - Feature 2 description

Example:
    Basic usage example here.

    >>> from module import Class
    >>> instance = Class()
    >>> result = instance.method()
"""
```

### Class Docstrings

**Google style with attributes and methods:**

```python
class AnalysisService:
    """
    Service for analyzing stock tickers.
    
    This service orchestrates the analysis pipeline including data
    fetching, indicator calculation, signal generation, and verdict
    determination. It implements the core RSI10 < 30 reversal strategy
    with multi-timeframe analysis.
    
    Attributes:
        config: Strategy configuration instance (StrategyConfig)
        data_service: Data fetching service (DataService)
        indicator_service: Technical indicator calculator (IndicatorService)
        signal_service: Signal detection service (SignalService)
        verdict_service: Verdict determination service (VerdictService)
    
    Example:
        Basic usage:
        
        >>> from services import AnalysisService
        >>> service = AnalysisService()
        >>> result = service.analyze_ticker("RELIANCE.NS")
        >>> print(result.verdict)
        'buy'
        
        Advanced usage with custom config:
        
        >>> from config.strategy_config import StrategyConfig
        >>> config = StrategyConfig(rsi_oversold=25.0)
        >>> service = AnalysisService(config=config)
        >>> result = service.analyze_ticker("RELIANCE.NS")
    """
```

### Function/Method Docstrings

**Google style with Args, Returns, Raises:**

```python
def analyze_ticker(
    self, 
    ticker: str, 
    enable_mtf: bool = True,
    enable_backtest: bool = False
) -> AnalysisResult:
    """
    Analyze a single stock ticker.
    
    Performs comprehensive technical analysis including RSI calculation,
    EMA200 trend confirmation, volume analysis, and multi-timeframe
    alignment scoring. Returns a complete analysis result with trading
    parameters and scores.
    
    Args:
        ticker: Stock ticker symbol (e.g., "RELIANCE.NS"). Must end with
            ".NS" for NSE stocks.
        enable_mtf: Enable multi-timeframe analysis (daily + weekly).
            Defaults to True. When enabled, analyzes both daily and weekly
            timeframes for trend alignment.
        enable_backtest: Enable 2-year historical backtesting validation.
            Defaults to False. When enabled, performs historical validation
            and includes backtest_score in result.
    
    Returns:
        AnalysisResult containing:
            - verdict: Trading verdict ("buy", "strong_buy", "watch", "avoid")
            - trading_params: Buy range, target, stop loss, risk-reward
            - rsi: RSI10 value
            - mtf_alignment_score: Multi-timeframe alignment score (0-10)
            - backtest_score: Historical performance score (0-100, if enabled)
            - combined_score: Combined current + historical score
            - priority_score: Trading priority ranking
    
    Raises:
        DataError: If stock data cannot be fetched or is insufficient.
            Raised when yfinance API fails or returns incomplete data.
        IndicatorError: If indicator calculation fails.
            Raised when RSI or EMA200 calculation encounters errors.
        AnalysisError: If analysis process fails.
            Raised for general analysis failures.
    
    Example:
        Basic analysis:
        
        >>> service = AnalysisService()
        >>> result = service.analyze_ticker("RELIANCE.NS")
        >>> print(f"Verdict: {result.verdict}, RSI: {result.rsi}")
        Verdict: buy, RSI: 28.5
        
        With backtesting:
        
        >>> result = service.analyze_ticker(
        ...     "RELIANCE.NS",
        ...     enable_backtest=True
        ... )
        >>> print(f"Combined Score: {result.combined_score}")
        Combined Score: 45.2
        
    Note:
        This method performs network I/O to fetch stock data. Consider
        using AsyncAnalysisService for batch analysis of multiple tickers.
    """
```

### Inline Comments

**Guidelines:**
- Explain "why" not "what" (code should be self-documenting)
- Document non-obvious business logic
- Explain workarounds or temporary solutions
- Reference external algorithms or formulas

**Good Examples:**
```python
# Use RSI10 (not RSI14) to match TradingView default for short-term strategy
rsi = calculate_rsi(data, period=10)

# Extend data period to ensure accurate EMA200 calculation
# EMA200 requires 200+ periods, but we fetch 800+ days for precision
if len(data) < 800:
    data = fetch_extended_data(ticker, days=800)

# Reset pyramiding state when RSI crosses above 30
# This prevents over-trading during extended oversold conditions
if current_rsi > 30 and last_rsi <= 30:
    reset_pyramiding_state()
```

**Bad Examples:**
```python
# Calculate RSI
rsi = calculate_rsi(data, period=10)  # Obvious from code

# Set variable to 10
value = 10  # Not helpful
```

---

## API Documentation

### Public API Documentation

**All public APIs must be documented:**

1. **Purpose**: What the API does
2. **Parameters**: All parameters with types and descriptions
3. **Return Values**: Return type and structure
4. **Exceptions**: What exceptions can be raised
5. **Examples**: Working code examples
6. **Notes**: Important usage notes or limitations

### API Documentation Template

```markdown
## Function/Class Name

**Purpose**: Brief description of what it does.

**Signature**:
```python
def function_name(param1: Type, param2: Type = default) -> ReturnType:
```

**Parameters**:
- `param1` (Type): Description of parameter
- `param2` (Type, optional): Description with default value

**Returns**:
- `ReturnType`: Description of return value

**Raises**:
- `ExceptionType`: When this exception is raised

**Example**:
```python
# Basic usage example
result = function_name("value1", param2="value2")
print(result)
```

**See Also**:
- Related functions or classes
- External documentation links
```

### Deprecated API Documentation

**When deprecating an API:**

```python
@deprecated(
    version="25.4.0",
    reason="Use AnalysisService.analyze_ticker() instead",
    removal_version="26.1.0"
)
def analyze_ticker_legacy(ticker: str) -> dict:
    """
    Legacy analysis function (DEPRECATED).
    
    .. deprecated:: 25.4.0
        Use :class:`AnalysisService.analyze_ticker()` instead.
        This function will be removed in version 26.1.0.
    
    Migration Guide:
        Old:
            result = analyze_ticker_legacy("RELIANCE.NS")
        
        New:
            from services import AnalysisService
            service = AnalysisService()
            result = service.analyze_ticker("RELIANCE.NS")
    """
```

---

## Feature Documentation

### Feature Documentation Template

```markdown
# Feature Name

**Version**: X.Y.Z  
**Status**: Active/Experimental/Deprecated  
**Last Updated**: YYYY-MM-DD

## Overview

Brief description of the feature and its purpose.

## Key Features

- Feature point 1
- Feature point 2
- Feature point 3

## Configuration

### Environment Variables

```env
FEATURE_ENABLED=true
FEATURE_PARAMETER=value
```

### Code Configuration

```python
from config.strategy_config import StrategyConfig

config = StrategyConfig(
    feature_enabled=True,
    feature_parameter=value
)
```

## Usage

### Basic Usage

```python
# Basic usage example
from services import FeatureService

service = FeatureService()
result = service.use_feature()
```

### Advanced Usage

```python
# Advanced usage example
service = FeatureService(config=custom_config)
result = service.use_feature(advanced_option=True)
```

## Integration

How to integrate this feature with other components.

## Examples

### Example 1: Basic Scenario

```python
# Example code
```

### Example 2: Advanced Scenario

```python
# Example code
```

## Troubleshooting

### Common Issues

**Issue**: Description of issue

**Solution**: How to fix it

## References

- Related documentation
- External resources
```

### Feature Documentation Requirements

1. **Overview**: What the feature does
2. **Configuration**: How to configure it
3. **Usage**: How to use it (with examples)
4. **Integration**: How it integrates with other features
5. **Examples**: Practical examples
6. **Troubleshooting**: Common issues and solutions

---

## Deployment Documentation

### Deployment Guide Template

```markdown
# Platform Deployment Guide

**Platform**: Windows/Ubuntu/Oracle Cloud/GCP  
**Last Updated**: YYYY-MM-DD

## Prerequisites

- Requirement 1
- Requirement 2

## Installation

### Step 1: Title

Description and commands.

```bash
command here
```

### Step 2: Title

Description and commands.

## Configuration

Configuration steps and examples.

## Verification

How to verify installation:

```bash
verification command
```

## Troubleshooting

Common issues and solutions.

## Next Steps

Links to related documentation.
```

### Deployment Documentation Requirements

1. **Prerequisites**: What's needed before starting
2. **Installation**: Step-by-step installation
3. **Configuration**: Configuration steps
4. **Verification**: How to verify it works
5. **Troubleshooting**: Common issues
6. **Screenshots**: Include for GUI steps
7. **Commands**: Provide copy-paste commands

---

## Documentation Formatting

### Markdown Guidelines

1. **Headers**: Use proper hierarchy (H1 → H2 → H3)
2. **Code Blocks**: Use syntax highlighting
3. **Lists**: Use consistent formatting
4. **Links**: Use relative links for internal docs
5. **Tables**: Use Markdown tables
6. **Emphasis**: Use **bold** and *italic* appropriately

### Code Block Formatting

**Python:**
````markdown
```python
def example():
    """Example function."""
    return "example"
```
````

**Bash:**
````markdown
```bash
python trade_agent.py
```
````

**Configuration:**
````markdown
```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```
````

### Link Formatting

**Internal Links:**
```markdown
[Link Text](relative/path/to/file.md)
[Link Text](../parent/file.md)
```

**External Links:**
```markdown
[Link Text](https://example.com)
```

**Anchor Links:**
```markdown
[Section Name](#section-name)
```

### Table Formatting

```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
| Value 4  | Value 5  | Value 6  |
```

---

## Maintenance & Review

### Documentation Review Checklist

Before submitting documentation:

- [ ] All new features documented
- [ ] Code examples tested and working
- [ ] Links verified (no broken links)
- [ ] Screenshots updated (if applicable)
- [ ] CHANGELOG.md updated
- [ ] Documentation index updated
- [ ] README.md reflects current state
- [ ] Breaking changes documented prominently
- [ ] Spelling and grammar checked
- [ ] Formatting consistent

### Update Frequency

- **README.md**: Update for every user-facing change
- **CHANGELOG.md**: Update for every release
- **Feature Docs**: Update when features change
- **API Docs**: Update when APIs change
- **Deployment Docs**: Update when deployment process changes

### Review Schedule

- **Quarterly Review**: Review all documentation quarterly
- **Post-Release**: Review docs after each release
- **User Feedback**: Update based on user questions/issues
- **Breaking Changes**: Immediate update required

### Outdated Content

**Handling outdated content:**

1. **Update**: If information is still relevant, update it
2. **Deprecate**: If feature is deprecated, mark as deprecated
3. **Remove**: If content is no longer relevant, remove it
4. **Archive**: Move historical docs to archive if needed

---

## Templates & Examples

### README.md Section Template

```markdown
## Feature Name

Brief description of the feature.

### Key Features

- Feature point 1
- Feature point 2

### Usage

```python
from module import Feature

feature = Feature()
result = feature.use()
```

### Configuration

```env
FEATURE_ENABLED=true
```

### Documentation

See [Feature Documentation](documents/features/FEATURE.md) for details.
```

### CHANGELOG.md Entry Template

```markdown
## [Version] - YYYY-MM-DD

### Added
- New feature 1
- New feature 2

### Changed
- Changed behavior 1

### Fixed
- Bug fix 1

### Deprecated
- Deprecated feature (removal in version X.Y.Z)

### Removed
- Removed feature (breaking change)

### Security
- Security fix
```

---

## References

- [PROJECT_RULES.md](../../PROJECT_RULES.md) - Overall project rules
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - Contribution guidelines
- [documents/getting-started/DOCUMENTATION_INDEX.md](../getting-started/DOCUMENTATION_INDEX.md) - Documentation index

---

**Last Updated**: 2025-11-07
