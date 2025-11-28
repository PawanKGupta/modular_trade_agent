# Coverage Improvement Plan (Phase 3)

## Completed (Phase 2)
- ✅ `trade_agent.py`: 100% statement coverage
- ✅ `server/app/core/crypto.py`: Tests added
- ✅ `server/app/core/security.py`: Tests added
- ✅ `server/app/core/deps.py`: Tests added
- ✅ `server/app/routers/activity.py`: Tests added
- ✅ `server/app/routers/admin.py`: Tests added

## Current Status
The core modules are now covered. Router coverage progress:
- ✅ `server/app/routers/activity.py`: Tests added
- ✅ `server/app/routers/admin.py`: Tests added
- ✅ `server/app/routers/auth.py`: Tests added (34 test cases, comprehensive coverage)
- ✅ `server/app/routers/user.py`: Tests added (22 test cases)
- ✅ `server/app/routers/orders.py`: Tests added (34 test cases)

## Next Targets - Router Coverage

### Priority 1: Authentication & User Management (Critical Path)
These routers are foundational for the application and should be tested early:

1. **`server/app/routers/auth.py`** ✅ COMPLETED
   - Endpoints: `/signup`, `/login`, `/refresh`, `/me`
   - Test scenarios:
     - ✅ Signup: successful creation, duplicate email, exception handling
     - ✅ Signup: exceptions from SettingsRepository, JWT creation, get_by_email
     - ✅ Login: valid credentials, invalid credentials, missing user, legacy password upgrade
     - ✅ Login: different bcrypt hash prefixes ($2a$, $2b$, $2y$)
     - ✅ Login: None/empty password hash handling
     - ✅ Login: exceptions from JWT creation, set_password
     - ✅ Refresh: valid refresh token, invalid token, missing uid, inactive user
     - ✅ Refresh: exceptions from get_by_id, JWT creation
     - ✅ Refresh: edge cases (None uid, empty dict decode)
     - ✅ Me: authenticated user with different roles, None name handling
     - ✅ HTTPException propagation testing
   - Dependencies: UserRepository, SettingsRepository, JWT tokens
   - Test file: `tests/unit/server/routers/test_auth.py` (34 tests)
   - Coverage: Target ≥90% (currently improving from 60.55%)

2. **`server/app/routers/user.py`** ✅ COMPLETED
   - Endpoints: `/settings`, `/buying-zone-columns`
   - Test scenarios:
     - ✅ GET settings: existing settings, default creation, None values
     - ✅ PUT settings: update trade_mode, broker, broker_status, all fields, partial updates
     - ✅ PUT settings: None trade_mode handling, creates default if missing
     - ✅ GET buying-zone-columns: existing preferences, defaults, missing keys, empty lists
     - ✅ PUT buying-zone-columns: success, merges existing, overwrites, creates default, exception handling
   - Dependencies: SettingsRepository, get_current_user
   - Test file: `tests/unit/server/routers/test_user.py` (22 tests)
   - Coverage: Target ≥90%

### Priority 2: Core Trading Functionality
3. **`server/app/routers/orders.py`** ✅ COMPLETED
   - Endpoints: `GET /`, `POST /{order_id}/retry`, `DELETE /{order_id}`, `GET /statistics`
   - Test scenarios:
     - ✅ GET /: Filter by status (all 5 statuses), reason, date ranges, combined filters
     - ✅ GET /: Default behavior (no filters), empty results, date format errors
     - ✅ GET /: Serialization handling, None values, optional fields
     - ✅ POST /{order_id}/retry: Success, not found, wrong user, invalid status
     - ✅ POST /{order_id}/retry: Retry count increment, first_failed_at handling, reason updates
     - ✅ DELETE /{order_id}: Success, not found, wrong user, invalid status
     - ✅ GET /statistics: Success, empty stats
     - ✅ Exception handling for all endpoints
   - Dependencies: OrdersRepository, date parsing
   - Test file: `tests/unit/server/routers/test_orders.py` (34 tests)
   - Coverage: Target ≥90%

4. **`server/app/routers/broker.py`** (Medium Priority)
   - Test broker connection and status endpoints
   - Dependencies: Broker services

5. **`server/app/routers/paper_trading.py`** (Medium Priority)
   - Test paper trading configuration and execution
   - Dependencies: Paper trading services

### Priority 3: Supporting Features
6. **`server/app/routers/signals.py`** (Medium Priority)
   - Test signal generation and retrieval

7. **`server/app/routers/targets.py`** (Medium Priority)
   - Test target management

8. **`server/app/routers/pnl.py`** (Medium Priority)
   - Test PnL calculation and reporting

9. **`server/app/routers/ml.py`** (Lower Priority)
   - Test ML model endpoints

10. **`server/app/routers/logs.py`** (Lower Priority)
    - Test log retrieval endpoints

11. **`server/app/routers/service.py`** (Lower Priority)
    - Test service management endpoints

12. **`server/app/routers/trading_config.py`** (Lower Priority)
    - Test trading configuration endpoints

## Testing Strategy

### Unit Test Approach
- Mock external dependencies (repositories, services)
- Use FastAPI's `TestClient` for endpoint testing where integration is needed
- Test both success and error paths
- Validate response models and status codes
- Cover all exception branches and edge cases

### Example Test Structure
```python
from types import SimpleNamespace
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Mock dependencies
# Test endpoint behavior
# Assert response format and status codes
```

## Validation Checklist (per router)
1. Run `pytest tests/unit/server/routers/test_[router].py -q`
2. Achieve ≥90% coverage for the router module
3. Test all endpoints and major branches
4. Test error handling (HTTPException cases)
5. Test authentication/authorization where applicable
6. Test exception paths from all dependencies
7. Test edge cases (None values, empty strings, etc.)

## Next Steps
1. ✅ ~~Start with `auth.py` router tests (critical path)~~ - COMPLETED (34 tests)
2. ✅ ~~Continue with `user.py` router tests (next priority)~~ - COMPLETED (22 tests)
3. ✅ ~~Continue with `orders.py` router tests (next priority)~~ - COMPLETED (34 tests)
4. Continue with remaining routers by priority
4. Move through remaining routers by priority

## Notes
- Some routers may require integration test setup for full coverage
- Focus on unit tests first, integration tests can follow in later phase
- Mock database sessions and repository classes to keep tests fast and isolated
- Ensure comprehensive exception path coverage for ≥90% target
