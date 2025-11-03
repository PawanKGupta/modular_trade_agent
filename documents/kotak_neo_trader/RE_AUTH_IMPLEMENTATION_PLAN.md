# Re-Authentication Implementation Plan

## Recommendation: Centralized Solution

**✅ Recommended Approach**: Create a centralized re-authentication handler that all services can use, rather than implementing it individually in each service.

## Why Centralized?

### ✅ Advantages

1. **Single Source of Truth**: One place to maintain re-auth logic
2. **Consistent Behavior**: All services handle auth failures the same way
3. **Easier Maintenance**: Fix bugs or improve logic in one place
4. **Reduced Code Duplication**: Don't repeat the same code in every method
5. **Flexibility**: Can be applied via decorator, helper function, or context manager
6. **Testing**: Easier to test re-auth logic in isolation

### ❌ Disadvantages of Individual Implementation

1. **Code Duplication**: Same logic repeated in every method
2. **Maintenance Burden**: Fix bugs in multiple places
3. **Inconsistency**: Easy to miss places or implement differently
4. **Harder to Test**: Need to test re-auth logic in every service

## Implementation Options

### Option 1: Decorator Pattern (Recommended) ⭐

**Best for**: Class methods that have `self.auth` attribute

```python
from modules.kotak_neo_auto_trader.auth_handler import handle_reauth

class KotakNeoOrders:
    def __init__(self, auth):
        self.auth = auth
    
    @handle_reauth
    def place_equity_order(self, ...):
        # Your existing code - no changes needed
        response = self.client.place_order(...)
        return response
```

**Pros**:
- Minimal code changes
- Clean and readable
- Automatic re-auth on any method

**Cons**:
- Requires all classes to have `self.auth` attribute

### Option 2: Helper Function

**Best for**: Standalone functions or complex flows

```python
from modules.kotak_neo_auto_trader.auth_handler import call_with_reauth

def place_equity_order(self, ...):
    def _call_api():
        return self.client.place_order(...)
    
    result = call_with_reauth(self.auth, _call_api)
    return result
```

**Pros**:
- Works with any function
- Explicit control

**Cons**:
- More verbose
- Requires wrapping API calls

### Option 3: Context Manager

**Best for**: Block of code with multiple API calls

```python
from modules.kotak_neo_auto_trader.auth_handler import AuthGuard

def some_complex_operation(self):
    with AuthGuard(self.auth):
        result1 = self.client.method1()
        if AuthGuard.is_auth_error(result1):
            # Will be handled by context manager
            return None
        
        result2 = self.client.method2()
        return process_results(result1, result2)
```

**Pros**:
- Good for multiple API calls
- Can handle exceptions

**Cons**:
- Requires checking errors manually
- Less automatic

## Migration Plan

### Phase 1: Create Centralized Handler ✅
- [x] Create `auth_handler.py` with all three options
- [x] Implement `is_auth_error()` helper
- [x] Implement `handle_reauth` decorator
- [x] Implement `call_with_reauth()` helper
- [x] Implement `AuthGuard` context manager

### Phase 2: Migrate High-Priority Methods

1. **Orders Module** (`orders.py`):
   - [ ] `place_equity_order()` - Use decorator
   - [ ] `modify_order()` - Use decorator
   - [ ] `cancel_order()` - Use decorator
   - [x] `get_orders()` - Already has re-auth, refactor to use decorator

2. **Market Data Module** (`market_data.py`):
   - [ ] `get_quote()` - Use decorator
   - [ ] `get_ltp()` - Use decorator (calls get_quote, so will benefit automatically)

### Phase 3: Migrate Medium-Priority Methods

3. **Portfolio Module** (`portfolio.py`):
   - [ ] `get_positions()` - Use decorator
   - [ ] `get_limits()` - Use decorator

4. **Other Modules**:
   - [ ] Any other API-calling methods

### Phase 4: Testing and Validation

- [ ] Unit tests for auth_handler
- [ ] Integration tests with expired JWT
- [ ] Test all decorated methods
- [ ] Verify no infinite retry loops
- [ ] Performance testing

## Code Examples

### Before (Individual Implementation)

```python
def place_equity_order(self, ...):
    try:
        response = self.client.place_order(...)
        
        # Duplicate re-auth logic
        if isinstance(response, dict):
            code = response.get('code', '')
            if code == '900901':
                if self.auth.force_relogin():
                    return self.client.place_order(...)  # Retry
        return response
    except Exception as e:
        # More duplicate logic
        ...
```

### After (Centralized with Decorator)

```python
from modules.kotak_neo_auto_trader.auth_handler import handle_reauth

@handle_reauth
def place_equity_order(self, ...):
    # Clean code - re-auth handled automatically
    response = self.client.place_order(...)
    return response
```

## Implementation Steps

1. **Create `auth_handler.py`** ✅ (Done)
2. **Update imports** in each module:
   ```python
   from modules.kotak_neo_auto_trader.auth_handler import handle_reauth
   ```
3. **Add decorator** to methods:
   ```python
   @handle_reauth
   def method_name(self, ...):
   ```
4. **Remove duplicate code** from `get_orders()` (refactor to use decorator)
5. **Test** all methods with expired JWT scenarios

## Decision Matrix

| Criteria | Individual | Centralized |
|----------|-----------|-------------|
| Code Duplication | ❌ High | ✅ None |
| Maintainability | ❌ Hard | ✅ Easy |
| Consistency | ❌ Low | ✅ High |
| Testing | ❌ Complex | ✅ Simple |
| Implementation Time | ⚠️ Fast initially | ⚠️ Medium |
| Long-term Cost | ❌ High | ✅ Low |

## Recommendation

**Use Centralized Solution with Decorator Pattern**

1. ✅ **Immediate**: Apply `@handle_reauth` decorator to all critical methods
2. ✅ **Clean**: No code duplication, easier to maintain
3. ✅ **Reliable**: Consistent behavior across all services
4. ✅ **Testable**: Can test re-auth logic independently

The initial setup time is slightly higher, but the long-term benefits far outweigh the costs.

