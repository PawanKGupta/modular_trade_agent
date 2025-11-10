# Architecture Guide - Trading Agent

**Updated:** Phase 4 (2025-11-02)  
**Status:** Service-based architecture (Phase 1-4 complete)

## 📐 Architecture Overview

The system uses a **service-based architecture** with clear separation of concerns across multiple layers:

### Service Layer Architecture (Phase 1-4)

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│  (trade_agent.py, CLI, Telegram, CSV Export)                │
│  - User interaction                                          │
│  - Input validation                                          │
│  - Output formatting                                         │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    SERVICE LAYER (Phase 1-4)                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Analysis Services                                   │    │
│  │  - AnalysisService (Phase 1)                         │    │
│  │  - AsyncAnalysisService (Phase 2)                    │    │
│  │  - AnalysisPipeline (Phase 3)                        │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Data & Infrastructure Services                      │    │
│  │  - DataService (Phase 1)                            │    │
│  │  - IndicatorService (Phase 1)                        │    │
│  │  - SignalService (Phase 1)                           │    │
│  │  - VerdictService (Phase 1)                          │    │
│  │  - ScoringService (Phase 4)                          │    │
│  │  - BacktestService (Phase 4)                         │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Infrastructure Support (Phase 2-4)                  │    │
│  │  - CacheService (Phase 2)                           │    │
│  │  - AsyncDataService (Phase 2)                        │    │
│  │  - EventBus (Phase 3)                                │    │
│  │  - Pipeline Steps (Phase 3)                           │    │
│  └─────────────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                 INFRASTRUCTURE LAYER                         │
│  (src/infrastructure/ + legacy core/ for backward compat)    │
│  - Data providers (yfinance, etc.)                           │
│  - Indicator calculators (pandas_ta)                         │
│  - Notifications (Telegram)                                  │
│  - Persistence (CSV, databases)                              │
│  - Web scraping (ChartInk)                                   │
└─────────────────────────────────────────────────────────────┘
```

### Legacy Architecture (Deprecated in Phase 4)

```
⚠️ DEPRECATED: core/ modules are deprecated in Phase 4
   See documents/phases/PHASE4_MIGRATION_GUIDE.md for migration
   
core/analysis.py → services/analysis_service.py
core/scoring.py → services/scoring_service.py
core/backtest_scoring.py → services/backtest_service.py
```

## 🎯 Layer Responsibilities

### Domain Layer (Core Business Logic)
**Location:** `src/domain/`

The innermost layer containing business logic, independent of frameworks and external systems.

#### Entities
**Location:** `src/domain/entities/`
- `Stock` - Tradable security
- `Signal` - Trading signal
- `AnalysisResult` - Complete analysis result
- `Trade` - Trade execution tracking

**Rules:**
- ✅ Rich behavior and business logic
- ✅ Validation in constructors
- ✅ No framework dependencies
- ❌ No database/API awareness

#### Value Objects
**Location:** `src/domain/value_objects/`
- `Price` - Immutable price with operations
- `Volume` - Volume with quality assessment
- `Indicators` - Technical indicator results

**Rules:**
- ✅ Immutable (frozen dataclasses)
- ✅ Value equality
- ✅ Self-validating
- ❌ No identity

#### Interfaces (Ports)
**Location:** `src/domain/interfaces/`
- `DataProvider` - Market data abstraction
- `IndicatorCalculator` - Technical indicators
- `SignalGenerator` - Signal generation
- `NotificationService` - Alert sending

**Rules:**
- ✅ Abstract base classes
- ✅ Define contracts
- ✅ No implementation details
- ❌ No concrete dependencies

---

### Application Layer (Use Cases)
**Location:** `src/application/`

Orchestrates domain objects to fulfill user requests.

#### Use Cases
**Location:** `src/application/use_cases/`
- Single-purpose application workflows
- Coordinates domain entities
- Returns DTOs to presentation layer

**Example:**
```python
class AnalyzeStockUseCase:
    def __init__(
        self,
        data_provider: DataProvider,
        indicator_calculator: IndicatorCalculator,
        signal_generator: SignalGenerator
    ):
        self.data_provider = data_provider
        self.indicator_calculator = indicator_calculator
        self.signal_generator = signal_generator
    
    def execute(self, ticker: str) -> AnalysisResultDTO:
        # 1. Fetch data
        data = self.data_provider.fetch_daily_data(ticker)
        
        # 2. Calculate indicators
        indicators = self.indicator_calculator.calculate_all_indicators(data)
        
        # 3. Generate signal
        signal = self.signal_generator.generate_signal(ticker, indicators, data)
        
        # 4. Return DTO
        return AnalysisResultDTO.from_entity(signal)
```

#### Services
**Location:** `src/application/services/`
- Application-level services
- Business logic coordination
- Cross-cutting concerns

#### DTOs
**Location:** `src/application/dto/`
- Data transfer objects
- Serialization/deserialization
- API contracts

---

### Infrastructure Layer (Adapters)
**Location:** `src/infrastructure/`

Implements domain interfaces with concrete technologies.

#### Data Providers
**Location:** `src/infrastructure/data_providers/`
```python
class YFinanceProvider(DataProvider):
    def fetch_daily_data(self, ticker: str, days: int = 365) -> pd.DataFrame:
        # yfinance implementation
        pass
```

#### Indicators
**Location:** `src/infrastructure/indicators/`
```python
class PandasTACalculator(IndicatorCalculator):
    def calculate_rsi(self, data: pd.DataFrame, period: int = 10) -> pd.Series:
        return ta.rsi(data['close'], length=period)
```

#### Notifications
**Location:** `src/infrastructure/notifications/`
```python
class TelegramNotifier(NotificationService):
    def send_alert(self, message: str, **kwargs) -> bool:
        # Telegram API implementation
        pass
```

#### Resilience
**Location:** `src/infrastructure/resilience/`
- Retry handlers
- Circuit breakers
- Rate limiters

---

### Presentation Layer (UI/CLI)
**Location:** `src/presentation/`

Handles user interaction and output formatting.

#### CLI Commands
**Location:** `src/presentation/cli/commands/`
```python
class AnalyzeCommand:
    def __init__(self, use_case: AnalyzeStockUseCase):
        self.use_case = use_case
    
    def execute(self, args):
        result = self.use_case.execute(args.ticker)
        # Format and display
```

#### Formatters
**Location:** `src/presentation/formatters/`
- Telegram message formatting
- Console output formatting
- CSV/JSON export formatting

#### Validators
**Location:** `src/presentation/validators/`
- Input validation
- Parameter sanitization

---

## 🔧 Dependency Injection

### Container Setup
**Location:** `src/config/dependencies.py`

```python
from src.config.dependencies import register_singleton, resolve

# Register implementations
register_singleton(DataProvider, YFinanceProvider())
register_singleton(IndicatorCalculator, PandasTACalculator())
register_singleton(SignalGenerator, ReversalSignalGenerator())
register_singleton(NotificationService, TelegramNotifier())

# Use in application
data_provider = resolve(DataProvider)
```

### Benefits
- ✅ Loose coupling
- ✅ Easy testing (mock dependencies)
- ✅ Swap implementations without code changes
- ✅ Clear dependency graph

---

## 📦 Import Guidelines

### ✅ Allowed Dependencies

**Domain Layer:**
- Can import: Nothing (pure business logic)
- Used by: Application, Infrastructure, Presentation

**Application Layer:**
- Can import: Domain (entities, interfaces, value objects)
- Used by: Presentation

**Infrastructure Layer:**
- Can import: Domain interfaces
- Used by: Application (via DI)

**Presentation Layer:**
- Can import: Application, Domain DTOs
- Used by: CLI entry points

### ❌ Forbidden Dependencies

```python
# ❌ Domain importing infrastructure
from src.infrastructure.data_providers import YFinanceProvider  # NO!

# ✅ Domain defines interface, infrastructure implements
from src.domain.interfaces.data_provider import DataProvider  # YES!
```

---

## 🧪 Testing Strategy

### Unit Tests
```python
# Test domain entities
def test_stock_validation():
    with pytest.raises(ValueError):
        Stock(ticker="", exchange="NSE", last_close=-100)

# Test value objects
def test_price_operations():
    price = Price(100.0)
    assert price.add(50).value == 150.0

# Test use cases with mocks
def test_analyze_stock_use_case(mocker):
    mock_provider = mocker.Mock(spec=DataProvider)
    use_case = AnalyzeStockUseCase(mock_provider, ...)
    result = use_case.execute("TEST.NS")
    assert result.status == "success"
```

### Integration Tests
```python
# Test with real implementations
def test_full_analysis_flow():
    provider = YFinanceProvider()
    calculator = PandasTACalculator()
    use_case = AnalyzeStockUseCase(provider, calculator)
    result = use_case.execute("RELIANCE.NS")
    assert result is not None
```

---

## 🚀 Migration Strategy

### Phase 1: Foundation ✅ (COMPLETE)
- Directory structure
- Domain entities and value objects
- Domain interfaces
- DI container

### Phase 2: Service Layer (NEXT)
- Extract use cases from `trade_agent.py`
- Create application services
- Define DTOs

### Phase 3: Infrastructure
- Wrap existing data fetching
- Encapsulate indicators
- Abstract notifications

### Phase 4: Presentation
- Extract CLI commands
- Create formatters
- Add validators

### Phase 5: Testing
- Unit tests for all layers
- Integration tests
- End-to-end tests

---

## 📚 Quick Reference

### Creating a New Entity
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MyEntity:
    id: str
    created_at: datetime
    
    def __post_init__(self):
        # Validation
        if not self.id:
            raise ValueError("ID required")
```

### Creating a New Value Object
```python
from dataclasses import dataclass

@dataclass(frozen=True)  # Immutable
class MyValue:
    value: float
    
    def __post_init__(self):
        if self.value < 0:
            raise ValueError("Must be positive")
```

### Creating a New Interface
```python
from abc import ABC, abstractmethod

class MyService(ABC):
    @abstractmethod
    def do_something(self, param: str) -> bool:
        pass
```

### Creating a New Use Case
```python
class MyUseCase:
    def __init__(self, service: MyService):
        self.service = service
    
    def execute(self, request: RequestDTO) -> ResponseDTO:
        # Business logic
        result = self.service.do_something(request.data)
        return ResponseDTO(result)
```

---

## 🎯 Best Practices

1. **Keep Domain Pure** - No framework dependencies in domain layer
2. **Use Interfaces** - Depend on abstractions, not concretions
3. **Immutable Value Objects** - Use frozen dataclasses
4. **Rich Entities** - Put behavior with data
5. **Thin Controllers** - Keep presentation logic minimal
6. **Test Boundaries** - Test each layer independently
7. **DI Everything** - Use dependency injection for flexibility

---

**For detailed examples, see:** `PHASE1_COMPLETE.md`
