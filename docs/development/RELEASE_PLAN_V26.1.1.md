# Release Plan v26.1.1 - Enhanced Dashboard & Analytics

**Target Release Date:** TBD
**Version:** 26.1.1
**Status:** Planning
**Base Version:** 26.1.0

---

## 📋 Quick Summary

### 🎯 Release Focus
Complete all pending dashboard enhancements, visual analytics, and data export capabilities.

### 📦 Key Features by Phase

**Phase -1: Critical Infrastructure Fixes (Week -1 to Week 0)**
- Kotak Authentication & Session Management Fixes

**Phase 0: Database Schema Enhancements (Week 0-1)**
- High Priority: Trade Mode Column, Exit Details, Portfolio Snapshots
- Medium Priority: Targets Table, P&L Calculation Audit, Price Cache
- Low Priority: Export Job Tracking, Analytics Cache

**Phase 1: Foundation (Week 1)**
- Install Chart Library (Recharts)
- Chart infrastructure setup
- PnL Data Population Service (prerequisite for charts)

**Phase 2: Core Charts (Week 1-2)**
- PnL Data Population Service (prerequisite for charts)
- P&L Trend Chart with time ranges
- Portfolio Value Chart with historical data
- Broker Trading History (parity with paper trading)
- Targets Page Implementation

**Phase 3: Dashboard & Export (Week 2-3)**
- Complete Enhanced Dashboard Metrics (win rate, avg profit, best/worst trades)
- Complete CSV Export UI (connect backend to frontend)
- PDF Report Generation

**Phase 4: Analytics (Week 3-4)**
- Performance Analytics Page
- Risk Metrics Dashboard

**Phase 5: Watchlist (Week 4-5)**
- Watchlist Feature (database + API + UI)
- Watchlist Dashboard Widget

**Phase 6: UX Polish (Week 5-6)**
- Complete Saved Filters & Preferences

### ⏱️ Timeline
**Total Duration:** 9-10 weeks (includes 1-2 week buffer for unexpected issues)
  - Phase -1: Critical Infrastructure Fixes (Week -1 to Week 0) - Must complete before Phase 0
  - Phase 0: Database Migrations (Week 0-1) - Can run in parallel with Phase 1
  - Phase 1-6: Feature Development (Week 1-8)
**Target Release:** TBD
**Alternative:** Phased release option (see Timeline & Milestones section)

**⚠️ Critical Path:**
- **Phase -1** (Kotak Authentication Fixes) - Must complete before Phase 0 (prevents production issues)
- **Phase 0.1-0.3** (High Priority DB Migrations) - Must complete before Phase 2.2, 2.4, 4.1
- **Phase 1.2** (PnL Data Population Service) - Must start immediately as it blocks multiple features

### 📊 Success Metrics

**User Engagement:**
- Dashboard views ↑ 30%
- Session time ↑ 20%
- Export usage > 50% of users
- Analytics page views > 40% of users

**Performance:**
- Dashboard load < 2 seconds
- Charts render < 1 second (for up to 1000 data points)
- CSV export < 5 seconds (for up to 10,000 records)
- Analytics page load < 3 seconds
- P&L calculation < 5 seconds (on-demand)

**Data Quality:**
- P&L calculation accuracy: 99.9%
- Chart data freshness: < 5 minutes old
- Export data completeness: 100%

**Error Rates:**
- P&L calculation failure rate: < 1%
- Chart rendering errors: < 0.5%
- Export failures: < 2%
- Authentication failures: < 0.1% (after Phase -1 fixes)
- API call failures due to stale client: 0% (after Phase -1 fixes)

---

## 📋 Executive Summary

This release focuses on completing all pending dashboard enhancements, visual analytics, and data export capabilities from the previous release plan. The goal is to provide traders with comprehensive insights into their trading performance through interactive charts, complete data export functionality, and advanced analytics.

**Scope:** All pending features from v2.0 release plan that are not yet implemented.

### 🗄️ Database Schema Enhancements

**8 database schema enhancements** have been identified to support this release:

**High Priority (Must Have):**
1. **Trade Mode Column** in Orders table - Enables efficient broker trading history filtering
2. **Exit Details** in Positions table - Enables analytics and better closed position tracking
3. **Portfolio Snapshots** table - Enables portfolio value chart with historical data

**Medium Priority (Should Have):**
4. **Targets Table** - Unified storage for sell order targets
5. **P&L Calculation Audit** - Track calculation runs and performance
6. **Historical Price Cache** - Performance improvement for portfolio calculations

**Low Priority (Nice to Have):**
7. **Export Job Tracking** - Monitor export operations
8. **Analytics Cache** - Cache expensive analytics calculations

**📄 Detailed Documentation:**
- Schema Design: [`RELEASE_PLAN_V26.1.1_DB_SCHEMA_ENHANCEMENTS.md`](./RELEASE_PLAN_V26.1.1_DB_SCHEMA_ENHANCEMENTS.md)
- Migration Scripts: [`RELEASE_PLAN_V26.1.1_DB_MIGRATIONS.md`](./RELEASE_PLAN_V26.1.1_DB_MIGRATIONS.md)

### Recent Work Impact

**Recent Bug Fixes (v26.1.0):**
- Retry logic bug fixes (ticker extraction from `order_metadata`)
- Paper trading adapter improvements (balance checks, DB persistence)
- Integration test fixes and improvements

**Critical Infrastructure Issues Identified (v26.1.1):**
- **Kotak Authentication & Session Management** - Client reference staleness, session expiration handling
  - **Impact:** Can cause API call failures, unnecessary re-authentication, race conditions
  - **Priority:** Critical - Must fix before new features
  - **Status:** Analysis complete, fixes planned in Phase -1
  - **📄 Analysis Document:** [`KOTAK_AUTH_SESSION_REUSE_ANALYSIS.md`](./KOTAK_AUTH_SESSION_REUSE_ANALYSIS.md)

**Compatibility Notes:**
- New features must be compatible with recent retry logic changes
- PnL calculation should account for `order_metadata` structure
- Broker trading history should handle updated order status flow
- Integration tests should cover new features with recent fixes
- All API calls must use fresh client references (Phase -1 fixes)

### Related Infrastructure Work

**Unified DB-Only Storage Migration** (Future Release)
- 📄 **Implementation Plan**: [`../kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md`](../kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md)
- **Goal**: Migrate from hybrid storage (paper=file, real=DB) to unified DB-only approach
- **Timeline**: 6-8 weeks
- **Status**: Planning phase
- **Impact**: This infrastructure improvement will enable unified reporting and better data consistency across paper and real trading modes

---

## 🎯 Release Goals

1. **Visual Analytics**: Implement interactive charts for P&L and portfolio visualization
2. **Data Portability**: Complete CSV export UI and add PDF report generation
3. **Enhanced Dashboard**: Complete dashboard metrics and add advanced analytics
4. **Performance Insights**: Add comprehensive analytics page with performance metrics
5. **User Experience**: Complete saved filters and preferences functionality

---

## 📦 Features Breakdown

### Phase -1: Critical Infrastructure Fixes (Kotak Authentication)

**Priority:** 🔴 **CRITICAL - START IMMEDIATELY**
**Effort:** Medium (3-4 days)
**Dependencies:** None
**Timeline:** Week -1 to Week 0 (before Phase 0)
**⚠️ BLOCKER:** These fixes prevent authentication failures and improve system stability

**Description:**
Critical fixes for Kotak Neo authentication and session management to prevent client reference staleness, improve session validity tracking, and ensure thread-safe client usage across concurrent API calls.

**⚠️ Important Note - PR #67 (Session Reuse):**
- **Status:** PR #67 (Session Reuse Feature) is currently **OPEN** and **NOT MERGED** in the official Kotak Neo SDK
- **Decision:** We will **WAIT** for PR #67 to be merged into production before implementing session reuse
- **Current Approach:** Phase -1 fixes work with the **current SDK** (no dependency on PR #67)
- **Future Enhancement:** Once PR #67 is merged, we will implement day-long session reuse (see "Future Enhancements" section below)
- **PR Link:** [Kotak-Neo/kotak-neo-api PR #67](https://github.com/Kotak-Neo/kotak-neo-api/pull/67) - Session reuse feature that enables day-long sessions

**📄 Detailed Analysis:**
- Full analysis document: [`KOTAK_AUTH_SESSION_REUSE_ANALYSIS.md`](./KOTAK_AUTH_SESSION_REUSE_ANALYSIS.md)

**Issues Identified:**
1. **Client Reference Staleness** - Client references become stale when re-auth happens between get and use
2. **SDK Thread Safety** - Unknown if NeoAPI SDK client is thread-safe for concurrent calls
3. **Cached Client Staleness** - Adapters cache client references that may become stale
4. **Session Expiration During Long Operations** - Long-running API calls fail if session expires mid-call
5. **Session Validation Race Condition** - Session validated but may expire before use
6. **🔴 CRITICAL: Re-auth State Race Condition** - `force_relogin()` sets `is_logged_in = False` immediately, causing Web API thread to clear session during re-auth → OTP spam every minute
7. **False Positive Auth Error Detection** - `is_auth_error()` too broad, triggers re-auth on non-auth errors
8. **Aggressive Session Clearing** - `SharedSessionManager` clears session too aggressively without checking if re-auth is in progress
9. **No Re-auth Rate Limiting** - No cooldown between re-auth attempts, allowing rapid cycles

**Deliverables:**
- [ ] Add session validity tracking to `KotakNeoAuth` (session creation time, TTL)
- [ ] Update `get_client()` to proactively check session validity before returning client
- [ ] **🔴 CRITICAL:** Fix `force_relogin()` to NOT set `is_logged_in = False` until re-auth actually fails
- [ ] Improve `is_auth_error()` to be more strict and reduce false positives (only JWT-specific errors)
- [ ] Refine session validation in `SharedSessionManager` to check session validity before clearing
- [ ] Add re-authentication rate limiting (60-second cooldown) to prevent OTP spam
- [ ] Add `_ensure_fresh_client()` method to `KotakNeoBrokerAdapter`
- [ ] Update all adapter methods to use `_ensure_fresh_client()` before API calls
- [ ] Verify SDK thread safety (check documentation or add wrapper if needed)
- [ ] Add timeout wrappers for long-running operations
- [ ] Add monitoring for re-authentication frequency
- [ ] Write tests for concurrent API calls with re-auth
- [ ] Write tests for client staleness scenarios
- [ ] Write tests for sell monitoring + Web API thread race condition
- [ ] Performance testing with thread safety wrapper (if needed)

**Files to Create/Modify:**
- `modules/kotak_neo_auto_trader/auth.py` - Add session validity tracking, fix `force_relogin()` state management
- `modules/kotak_neo_auto_trader/auth_handler.py` - Improve `is_auth_error()` to reduce false positives
- `modules/kotak_neo_auto_trader/shared_session_manager.py` - Refine session validation, add rate limiting
- `modules/kotak_neo_auto_trader/infrastructure/broker_adapters/kotak_neo_adapter.py` - Add `_ensure_fresh_client()`
- `modules/kotak_neo_auto_trader/portfolio.py` - Verify client usage pattern (already good)
- `modules/kotak_neo_auto_trader/orders.py` - Verify client usage pattern (already good)
- `modules/kotak_neo_auto_trader/market_data.py` - Verify client usage pattern
- `tests/unit/kotak/test_auth_session_management.py` - New test file for session management
- `tests/integration/test_sell_monitoring_reauth_race.py` - Test for sell monitoring + Web API race condition

**Code Changes Required:**

1. **Session Validity Tracking (`auth.py`):**
   ```python
   class KotakNeoAuth:
       def __init__(self, config_file: str = ...):
           # ... existing code ...
           self.session_created_at: float | None = None
           self.session_ttl: int = 3300  # 55 minutes (safety margin for 1-hour JWT)

       def login(self) -> bool:
           # ... existing login code ...
           if self._complete_2fa():
               self.is_logged_in = True
               self.session_created_at = time.time()  # Track session creation
               return True

       def force_relogin(self) -> bool:
           """
           Force a fresh login + 2FA (used when JWT expires) - THREAD-SAFE.

           🔴 CRITICAL FIX: Keep is_logged_in = True during re-auth attempt.
           Only set False if re-auth completely fails. This prevents Web API thread
           from clearing session while re-auth is in progress.
           """
           with self._client_lock:
               try:
                   self.logger.info("Forcing fresh login...")

                   # Step 1: Clean up old client first (if exists)
                   old_client = self.client
                   if old_client:
                       try:
                           old_client.logout()
                       except Exception:
                           pass  # Ignore logout errors

                   # Step 2: Create new client (but keep is_logged_in = True)
                   # CRITICAL: Don't set is_logged_in = False here!
                   self.client = self._initialize_client()
                   if not self.client:
                       # Only set False if client initialization fails
                       self.is_logged_in = False
                       self.session_token = None
                       return False

                   # Step 3: Perform fresh login + 2FA
                   if not self._perform_login():
                       # Only set False if login fails
                       self.is_logged_in = False
                       self.session_token = None
                       self.client = None
                       return False

                   # Step 4: Complete 2FA (with retry logic)
                   max_2fa_retries = 2
                   for attempt in range(max_2fa_retries):
                       if self._complete_2fa():
                           # Success - keep is_logged_in = True, update timestamp
                           self.is_logged_in = True
                           self.session_created_at = time.time()  # Reset session timer
                           self.logger.info("Re-authentication successful")
                           return True

                       if attempt < max_2fa_retries - 1:
                           # Retry: create new client and re-login
                           self.client = None
                           self.client = self._initialize_client()
                           if not self.client:
                               break
                           if not self._perform_login():
                               break

                   # Re-auth failed completely - only now set False
                   self.is_logged_in = False
                   self.session_token = None
                   self.client = None
                   return False

               except Exception as e:
                   self.logger.error(f"Force re-login failed: {e}")
                   # Reset state on failure
                   self.is_logged_in = False
                   self.session_token = None
                   self.client = None
                   return False

       def is_session_valid(self) -> bool:
           """Check if session is still valid (not expired)"""
           if not self.is_logged_in:
               return False
           if self.session_created_at is None:
               return True  # Legacy session, assume valid
           elapsed = time.time() - self.session_created_at
           return elapsed < self.session_ttl

       def get_client(self):
           """Get client with proactive session validity check"""
           with self._client_lock:
               # Proactively check session validity
               if not self.is_session_valid():
                   self.logger.warning("Session expired, forcing re-login")
                   if not self.force_relogin():
                       return None
               return self.client
   ```

2. **🔴 CRITICAL: Improve Auth Error Detection (`auth_handler.py`):**
   ```python
   def is_auth_error(response: Any) -> bool:
       """
       More strict auth error detection to reduce false positives.

       Only triggers re-auth for actual JWT/auth errors, not generic 401/403 responses.
       This prevents unnecessary re-auth cycles that cause OTP spam.
       """
       if not isinstance(response, dict):
           return False

       code = str(response.get("code", "")).strip()
       message = str(response.get("message", "")).lower()
       description = str(response.get("description", "")).lower()

       # ONLY check for specific JWT error code (most reliable)
       if code == "900901":
           return True

       # ONLY check for explicit JWT token errors (not generic "unauthorized")
       if "invalid jwt token" in description or "jwt token expired" in description:
           return True
       if "invalid jwt token" in message or "jwt token expired" in message:
           return True

       # REMOVED: Generic "unauthorized" checks that cause false positives
       # REMOVED: Generic "invalid credentials" checks

       return False
   ```

3. **🔴 CRITICAL: Refine Session Validation (`shared_session_manager.py`):**
   ```python
   class SharedSessionManager:
       _REAUTH_COOLDOWN = 60  # seconds
       _last_reauth_time: dict[int, float] = {}

       def get_or_create_session(
           self, user_id: int, env_file: str, force_new: bool = False
       ) -> Optional["KotakNeoAuth"]:
           # Get or create lock for this user
           with self._manager_lock:
               if user_id not in self._locks:
                   self._locks[user_id] = threading.Lock()
               user_lock = self._locks[user_id]

           with user_lock:
               # Check if session exists and is valid
               if not force_new and user_id in self._sessions:
                   auth = self._sessions[user_id]

                   # Check session health more carefully
                   if auth.is_authenticated():
                       client = auth.get_client()

                       # Only clear if BOTH are false/None AND session actually expired
                       if not client:
                           # Check if session is actually expired (not just client None)
                           if hasattr(auth, 'is_session_valid') and auth.is_session_valid():
                               # Session valid but client None - don't clear, let it recover
                               logger.warning(
                                   f"Session valid but client None for user {user_id}, "
                                   "attempting recovery"
                               )
                               return auth  # Return existing, let API call handle via @handle_reauth
                           else:
                               # Session expired - clear it
                               logger.warning(
                                   f"Session expired for user {user_id}, clearing"
                               )
                               with self._manager_lock:
                                   self._sessions.pop(user_id, None)
                       else:
                           # Both authenticated and client available - reuse
                           logger.info(f"[SHARED_SESSION] Reusing existing session for user {user_id}")
                           return auth
                   else:
                       # Not authenticated - clear
                       logger.warning(
                           f"[SHARED_SESSION] Existing session for user {user_id} is invalid, clearing"
                       )
                       with self._manager_lock:
                           self._sessions.pop(user_id, None)

                   # Check re-auth rate limiting
                   if user_id in self._last_reauth_time:
                       time_since_reauth = time.time() - self._last_reauth_time[user_id]
                       if time_since_reauth < self._REAUTH_COOLDOWN:
                           logger.warning(
                               f"Re-auth cooldown active for user {user_id}, "
                               f"{self._REAUTH_COOLDOWN - time_since_reauth:.0f}s remaining"
                           )
                           # Return existing session even if client is None (let API call handle it)
                           if user_id in self._sessions:
                               return self._sessions[user_id]

               # Create new session
               logger.info(f"[SHARED_SESSION] Creating new session for user {user_id}")
               from .auth import KotakNeoAuth

               auth = KotakNeoAuth(env_file)
               if auth.login():
                   with self._manager_lock:
                       self._sessions[user_id] = auth
                   # Record re-auth time
                   self._last_reauth_time[user_id] = time.time()
                   logger.info(f"[SHARED_SESSION] Session created and cached for user {user_id}")
                   return auth
               else:
                   logger.error(f"[SHARED_SESSION] Failed to create session for user {user_id}")
                   return None
   ```

4. **Client Refresh in Adapters (`kotak_neo_adapter.py`):**
   ```python
   class KotakNeoBrokerAdapter(IBrokerGateway):
       def _ensure_fresh_client(self):
           """Always get fresh client before API calls"""
           if not self.auth_handler or not self.auth_handler.is_authenticated():
               raise ConnectionError("Not authenticated")

           # Always get fresh client (don't rely on cache)
           fresh_client = self.auth_handler.get_client()
           if not fresh_client:
               raise ConnectionError("No authenticated client available")

           self._client = fresh_client  # Update cache
           return fresh_client

       def place_order(self, order: Order) -> str:
           # Always ensure fresh client
           self._ensure_fresh_client()
           # ... rest of method
   ```

5. **SDK Thread Safety Verification:**
   - Check NeoAPI SDK documentation for thread safety
   - If not thread-safe, add `ThreadSafeClientWrapper`:
     ```python
     class ThreadSafeClientWrapper:
         """Wrapper to serialize API calls if SDK is not thread-safe"""
         def __init__(self, client):
             self._client = client
             self._call_lock = threading.Lock()

         def __getattr__(self, name):
             attr = getattr(self._client, name)
             if callable(attr):
                 def locked_call(*args, **kwargs):
                     with self._call_lock:
                         return attr(*args, **kwargs)
                 return locked_call
             return attr
     ```

**Acceptance Criteria:**
- ✅ Session validity tracking works correctly
- ✅ `get_client()` proactively re-authenticates if session expired
- ✅ **🔴 CRITICAL:** `force_relogin()` keeps `is_logged_in = True` during re-auth attempt
- ✅ **🔴 CRITICAL:** `is_auth_error()` only triggers on real JWT errors (no false positives)
- ✅ **🔴 CRITICAL:** `SharedSessionManager` checks session validity before clearing
- ✅ **🔴 CRITICAL:** Re-auth rate limiting prevents OTP spam (60-second cooldown)
- ✅ All adapter methods use fresh client before API calls
- ✅ No client reference staleness issues
- ✅ Concurrent API calls work correctly (sell monitoring + Web API threads)
- ✅ Re-authentication frequency reduced (proactive vs reactive)
- ✅ **🔴 CRITICAL:** "Re-auth every minute" issue resolved (no OTP spam)
- ✅ All tests pass
- ✅ Performance impact minimal (< 5ms overhead per API call)

**Testing Requirements:**
- Unit tests for session validity tracking
- Unit tests for `_ensure_fresh_client()` method
- **🔴 CRITICAL:** Unit tests for `force_relogin()` state management (verify `is_logged_in` stays True during re-auth)
- **🔴 CRITICAL:** Unit tests for improved `is_auth_error()` (verify no false positives)
- **🔴 CRITICAL:** Integration tests for sell monitoring + Web API thread race condition
- Integration tests for concurrent API calls with re-auth
- Tests for client staleness race conditions
- Tests for re-auth rate limiting (verify cooldown works)
- Performance tests (verify minimal overhead)
- SDK thread safety verification tests

**Risk Mitigation:**
- **Risk:** Session validity check adds overhead
  - **Mitigation:** Check is fast (time comparison), minimal impact
- **Risk:** Proactive re-auth might trigger too frequently
  - **Mitigation:** Use 55-minute TTL (safety margin for 1-hour JWT)
- **Risk:** Keeping `is_logged_in = True` during re-auth might cause issues if re-auth hangs
  - **Mitigation:** Add timeout to re-auth operations, set `is_logged_in = False` on timeout
- **Risk:** Stricter `is_auth_error()` might miss some real auth errors
  - **Mitigation:** Monitor for missed auth errors, adjust detection if needed
- **Risk:** Re-auth rate limiting might block legitimate re-auth attempts
  - **Mitigation:** 60-second cooldown is reasonable, can be adjusted if needed
- **Risk:** SDK thread safety wrapper impacts performance
  - **Mitigation:** Only add if SDK is confirmed not thread-safe, test performance impact

**Success Metrics:**
- **🔴 CRITICAL:** "Re-auth every minute" issue resolved (OTP spam eliminated)
- Re-authentication failures reduced by 80%
- False positive re-auth attempts reduced by 90%
- API call failures due to stale client: 0%
- Concurrent API call success rate: > 99%
- Session validity check overhead: < 5ms per call
- Re-auth frequency: < 1 per hour (only on legitimate expiration)

**Future Enhancement: Session Reuse (PR #67) - PENDING MERGE**

**Status:** Waiting for PR #67 to be merged into official Kotak Neo SDK

**Once PR #67 is merged:**
- [ ] Update SDK version to include `reuse_session` feature
- [ ] Implement session storage (file-based or database)
- [ ] Update `_initialize_client()` to support `reuse_session` parameter
- [ ] Add session persistence across service restarts
- [ ] Update session TTL to day-long (6-7 hours for trading day)
- [ ] Simplify re-auth logic (only re-auth at market open, not hourly)
- [ ] Test session reuse across multiple users
- [ ] Update documentation

**Expected Benefits:**
- ✅ One login per day (at market open) instead of hourly re-auth
- ✅ Complete elimination of OTP spam
- ✅ Better stability (no interruptions during trading)
- ✅ Simpler code (less re-auth complexity)

**Implementation Plan:**
- Monitor PR #67 status
- Once merged, create new phase or update Phase -1
- Implement session reuse feature
- Test thoroughly before production deployment

---

### Phase 0: Database Schema Enhancements (Foundation)

**Priority:** 🔴 High (Critical Blockers)
**Effort:** 5-8 days (High Priority only) | 13-22 days (All enhancements)
**Dependencies:** None (must complete before Phase 2.2, 2.4, 4.1)
**Timeline:** Week 0-1 (can run in parallel with Phase 1.1)

**Description:**
Database schema enhancements to support new features in this release. High-priority enhancements are critical blockers for core features.

**📄 Detailed Documentation:**
- Full schema design: [`RELEASE_PLAN_V26.1.1_DB_SCHEMA_ENHANCEMENTS.md`](./RELEASE_PLAN_V26.1.1_DB_SCHEMA_ENHANCEMENTS.md)
- Migration scripts: [`RELEASE_PLAN_V26.1.1_DB_MIGRATIONS.md`](./RELEASE_PLAN_V26.1.1_DB_MIGRATIONS.md)

---

#### 0.1 Trade Mode Column in Orders Table
**Priority:** 🔴 High (Must Have)
**Effort:** Low-Medium (1-2 days)
**Dependencies:** None
**Blocks:** Phase 2.4 (Broker Trading History)

**Description:**
Add `trade_mode` column to `orders` table to distinguish paper trading vs. broker trading orders. Enables efficient filtering and unified reporting.

**Deliverables:**
- [ ] Add `trade_mode` column to `Orders` model (nullable for backward compatibility)
- [ ] Create Alembic migration script
- [ ] Create data backfill script (populate from `user_settings.trade_mode`)
- [ ] Update all order creation code to set `trade_mode`
- [ ] Add index on `trade_mode` column
- [ ] Update `OrdersRepository` methods
- [ ] Test migration up/down
- [ ] Verify backfill accuracy

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `trade_mode` to `Orders`
- `alembic/versions/XXXX_add_trade_mode_to_orders.py` - Migration
- `scripts/backfill_trade_mode_to_orders.py` - Data backfill script
- `src/infrastructure/persistence/orders_repository.py` - Update create methods
- All order creation code - Set `trade_mode` when creating orders

**Code Changes Required:**

1. **Model Update:**
   - `src/infrastructure/db/models.py` - Add `trade_mode` field to `Orders` class

2. **Repository Updates:**
   - `src/infrastructure/persistence/orders_repository.py`:
     - Update `create_amo()` method to accept `trade_mode` parameter
     - Get `trade_mode` from `UserSettings` if not provided
     - Update `Orders()` instantiation to include `trade_mode`

3. **Order Creation Points (Must Update):**
   - `modules/kotak_neo_auto_trader/order_tracker.py`:
     - Line 192: `orders_repo.create_amo()` - Add `trade_mode` parameter
     - Get `trade_mode` from user settings or context

   - `src/infrastructure/persistence/dual_write.py`:
     - Line 44: `self.db_repo.create_amo()` - Pass `trade_mode` parameter
     - Get `trade_mode` from user settings

   - `src/application/services/paper_trading_service_adapter.py`:
     - Line 2162: `orders_repo.create_amo()` - Add `trade_mode=TradeMode.PAPER`
     - Line 2809: `orders_repo.create_amo()` - Add `trade_mode=TradeMode.PAPER`

   - `services/persistence_bridge.py`:
     - Line 51: `orders_writer.create_amo()` - Add `trade_mode` parameter
     - Get from user settings

4. **Query Updates:**
   - `src/infrastructure/persistence/orders_repository.py`:
     - Update `list()` method to support filtering by `trade_mode`
     - Add helper method: `list_by_trade_mode(user_id, trade_mode)`

5. **API Updates:**
   - `server/app/routers/orders.py` (if exists):
     - Add `trade_mode` filter parameter to list endpoints

   - `server/app/routers/broker.py`:
     - Update order queries to filter by `trade_mode=TradeMode.BROKER`

   - `server/app/routers/paper_trading.py`:
     - Update order queries to filter by `trade_mode=TradeMode.PAPER`

6. **Helper Function:**
   - Create utility function to get `trade_mode` from user settings:
     ```python
     def get_user_trade_mode(db: Session, user_id: int) -> TradeMode:
         settings_repo = SettingsRepository(db)
         settings = settings_repo.get_by_user_id(user_id)
         return settings.trade_mode if settings else TradeMode.PAPER
     ```

**Acceptance Criteria:**
- Migration runs successfully
- All new orders have `trade_mode` set
- Backfill completes for existing orders
- Queries filter by `trade_mode` efficiently
- No breaking changes to existing code (backward compatible)

---

#### 0.2 Exit Details in Positions Table
**Priority:** 🔴 High (Must Have)
**Effort:** Medium (2-3 days)
**Dependencies:** None
**Blocks:** Phase 2.4 (Broker Trading History), Phase 4.1 (Performance Analytics)

**Description:**
Add exit detail columns to `positions` table (exit_price, exit_reason, exit_rsi, realized_pnl, etc.) to enable efficient queries for closed positions and analytics.

**Deliverables:**
- [ ] Add exit detail columns to `Positions` model (all nullable)
  - `exit_price`, `exit_reason`, `exit_rsi`
  - `realized_pnl`, `realized_pnl_pct`
  - `sell_order_id` (foreign key to orders)
- [ ] Create Alembic migration script
- [ ] Create data backfill script (populate from Orders table)
- [ ] Update `mark_closed()` method to populate exit details
- [ ] Add index on `exit_reason` (for analytics queries)
- [ ] Update sell engine to populate exit details when closing positions
- [ ] Test migration up/down
- [ ] Verify backfill accuracy

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add exit fields to `Positions`
- `alembic/versions/XXXX_add_exit_details_to_positions.py` - Migration
- `scripts/backfill_exit_details_to_positions.py` - Data backfill script
- `src/infrastructure/persistence/positions_repository.py` - Update `mark_closed()`
- `modules/kotak_neo_auto_trader/sell_engine.py` - Populate exit details

**Code Changes Required:**

1. **Model Update:**
   - `src/infrastructure/db/models.py` - Add exit fields to `Positions` class:
     - `exit_price`, `exit_reason`, `exit_rsi`
     - `realized_pnl`, `realized_pnl_pct`
     - `sell_order_id` (foreign key to Orders)

2. **Repository Updates:**
   - `src/infrastructure/persistence/positions_repository.py`:
     - Update `mark_closed()` method signature:
       ```python
       def mark_closed(
           self,
           user_id: int,
           symbol: str,
           closed_at: datetime | None = None,
           exit_price: float | None = None,
           exit_reason: str | None = None,
           exit_rsi: float | None = None,
           realized_pnl: float | None = None,
           realized_pnl_pct: float | None = None,
           sell_order_id: int | None = None,
           auto_commit: bool = True,
       ) -> Positions | None:
       ```
     - Update method body to set all exit fields
     - Calculate `realized_pnl` and `realized_pnl_pct` if not provided:
       ```python
       if exit_price and not realized_pnl:
           realized_pnl = (exit_price - pos.avg_price) * pos.quantity
       if realized_pnl and not realized_pnl_pct:
           cost_basis = pos.avg_price * pos.quantity
           realized_pnl_pct = (realized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0
       ```

3. **Sell Engine Updates:**
   - `modules/kotak_neo_auto_trader/sell_engine.py`:
     - Line 4329: `positions_repo.mark_closed()` - Update call to include exit details:
       ```python
       # Get exit details from order_metadata or calculate
       exit_reason = order_metadata.get("exit_note", "EMA9_TARGET")
       exit_rsi = order_metadata.get("exit_rsi")

       positions_repo.mark_closed(
           user_id=self.user_id,
           symbol=full_symbol,
           closed_at=ist_now(),
           exit_price=current_price,
           exit_reason=exit_reason,
           exit_rsi=exit_rsi,
           sell_order_id=sell_order.id,  # Get from executed sell order
           auto_commit=False,
       )
       ```
     - Extract exit details from sell order metadata
     - Calculate realized P&L if not provided

4. **Unified Order Monitor Updates:**
   - `modules/kotak_neo_auto_trader/unified_order_monitor.py`:
     - Update position closing logic to populate exit details
     - Line 4329 area: Similar updates as sell_engine.py

5. **Query Updates:**
   - `src/infrastructure/persistence/positions_repository.py`:
     - Add method: `list_closed_with_exit_details(user_id, exit_reason=None)`
     - Update queries to use exit fields for analytics

6. **API Updates:**
   - `server/app/routers/positions.py` (if exists):
     - Add `exit_reason` filter parameter
     - Include exit details in response schema

   - `server/app/routers/broker.py`:
     - Update trading history endpoint to use exit details
     - Include exit information in closed positions response

7. **Analytics Service Updates:**
   - `server/app/services/analytics_service.py` (Phase 4.1):
     - Use `exit_reason` for analytics by exit type
     - Use `realized_pnl` for accurate P&L calculations

**Acceptance Criteria:**
- Migration runs successfully
- All new closed positions have exit details populated
- Backfill completes for existing closed positions
- Analytics queries by exit_reason work efficiently
- `mark_closed()` method backward compatible (all new params optional)

---

#### 0.3 Portfolio Snapshots Table
**Priority:** 🔴 High (Must Have)
**Effort:** Medium (2-3 days)
**Dependencies:** None
**Blocks:** Phase 2.2 (Portfolio Value Chart)

**Description:**
Create `portfolio_snapshots` table to store historical portfolio value snapshots. Enables portfolio value chart without recalculating from positions.

**Deliverables:**
- [ ] Create `PortfolioSnapshot` model
- [ ] Create Alembic migration script
- [ ] Create repository (`PortfolioSnapshotRepository`)
- [ ] Create initial snapshot creation script (optional backfill)
- [ ] Add snapshot creation to EOD cleanup (or on-demand)
- [ ] Add API endpoint for historical portfolio data
- [ ] Test migration up/down

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `PortfolioSnapshot` model
- `alembic/versions/XXXX_add_portfolio_snapshots.py` - Migration
- `src/infrastructure/persistence/portfolio_snapshot_repository.py` - New repository
- `scripts/create_initial_portfolio_snapshots.py` - Optional backfill
- `server/app/routers/portfolio.py` - Add historical endpoint
- EOD cleanup service - Create daily snapshots

**Code Changes Required:**

1. **New Repository:**
   - `src/infrastructure/persistence/portfolio_snapshot_repository.py` - Create new file:
     ```python
     class PortfolioSnapshotRepository:
         def create(self, snapshot: PortfolioSnapshot) -> PortfolioSnapshot
         def get_by_date_range(self, user_id: int, start_date: date, end_date: date) -> list[PortfolioSnapshot]
         def get_latest(self, user_id: int) -> PortfolioSnapshot | None
         def upsert_daily(self, user_id: int, date: date, snapshot_data: dict) -> PortfolioSnapshot
     ```

2. **Portfolio Calculation Service:**
   - Create `server/app/services/portfolio_calculation_service.py`:
     ```python
     class PortfolioCalculationService:
         def calculate_portfolio_metrics(self, user_id: int, date: date) -> dict:
             # Calculate total_value, invested_value, available_cash
             # Calculate unrealized_pnl, realized_pnl
             # Count open/closed positions
             # Calculate returns
             pass

         def create_snapshot(self, user_id: int, date: date, snapshot_type: str = "eod") -> PortfolioSnapshot:
             # Calculate metrics and create snapshot
             pass
     ```

3. **EOD Cleanup Integration:**
   - `modules/kotak_neo_auto_trader/eod_cleanup.py` (or wherever EOD cleanup runs):
     - Add snapshot creation at end of EOD cleanup:
       ```python
       from server.app.services.portfolio_calculation_service import PortfolioCalculationService

       # After EOD cleanup completes
       portfolio_service = PortfolioCalculationService(db)
       snapshot = portfolio_service.create_snapshot(user_id, today, "eod")
       ```

4. **Portfolio API Updates:**
   - `server/app/routers/broker.py`:
     - Line 611-631: Portfolio value calculation - Can use snapshots for historical data
     - Add new endpoint: `GET /api/v1/user/portfolio/history?start_date=&end_date=`
     - Use `PortfolioSnapshotRepository` for historical queries

   - `server/app/routers/paper_trading.py`:
     - Line 148-169: Portfolio value calculation - Similar updates
     - Add historical endpoint for paper trading

5. **Portfolio Chart Integration (Phase 2.2):**
   - `web/src/routes/dashboard/PortfolioChartPage.tsx`:
     - Update to use `/api/v1/user/portfolio/history` endpoint
     - Use snapshot data instead of calculating on-demand

6. **Helper Functions:**
   - Create utility to calculate portfolio metrics from positions/orders:
     ```python
     def calculate_portfolio_metrics_from_positions(
         db: Session,
         user_id: int,
         date: date
     ) -> dict:
         # Query positions, orders, cash
         # Calculate all metrics
         # Return dict with all snapshot fields
     ```

**Acceptance Criteria:**
- Migration runs successfully
- Snapshot creation works correctly
- Historical queries are fast (indexed)
- Portfolio chart can use snapshot data
- EOD cleanup creates snapshots automatically
- Backward compatible (can still calculate on-demand if snapshot missing)

---

#### 0.4 Targets Table
**Priority:** 🟡 Medium (Should Have)
**Effort:** Medium (3-4 days)
**Dependencies:** None
**Blocks:** Phase 2.5 (Targets Page) - Improves implementation

**Description:**
Create `targets` table to store sell order targets in database instead of JSON files. Enables unified storage for paper and broker trading.

**Deliverables:**
- [ ] Create `Targets` model
- [ ] Create Alembic migration script
- [ ] Create repository (`TargetsRepository`)
- [ ] Update sell order placement to create target records
- [ ] Migrate existing JSON targets to database (optional)
- [ ] Update Targets API to query from database
- [ ] Test migration up/down

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `Targets` model
- `alembic/versions/XXXX_add_targets_table.py` - Migration
- `src/infrastructure/persistence/targets_repository.py` - New repository
- `server/app/routers/targets.py` - Update to query from database
- `modules/kotak_neo_auto_trader/sell_engine.py` - Create target records

**Code Changes Required:**

1. **New Repository:**
   - `src/infrastructure/persistence/targets_repository.py` - Create new file:
     ```python
     class TargetsRepository:
         def create(self, target: Targets) -> Targets
         def get_active_by_user(self, user_id: int) -> list[Targets]
         def get_by_position(self, position_id: int) -> Targets | None
         def update_target_price(self, target_id: int, new_price: float) -> Targets
         def mark_achieved(self, target_id: int, achieved_at: datetime) -> Targets
         def deactivate(self, target_id: int) -> Targets
     ```

2. **Sell Engine Updates:**
   - `modules/kotak_neo_auto_trader/sell_engine.py`:
     - Line 2143: `place_sell_order()` - After placing sell order, create target record:
       ```python
       # After sell order placed successfully
       if self.targets_repo and self.user_id:
           target = self.targets_repo.create(
               Targets(
                   user_id=self.user_id,
                   position_id=position.id if position else None,
                   symbol=full_symbol,
                   target_price=target_price,
                   entry_price=position.avg_price if position else trade.get("entry_price", 0),
                   quantity=position.quantity if position else trade.get("qty", 0),
                   target_type="ema9",
                   is_active=True,
                   trade_mode=self.trade_mode,  # Get from context
               )
           )
       ```
     - Line 2397: `update_sell_order_price()` - Update target price when order price changes
     - Line 4329: `monitor_and_update()` - Mark target as achieved when order executes

3. **Targets API Updates:**
   - `server/app/routers/targets.py`:
     - Line 13: `list_targets()` - Update to query from database:
       ```python
       targets_repo = TargetsRepository(db)
       active_targets = targets_repo.get_active_by_user(current.id)

       # Convert to TargetItem schema
       return [TargetItem(...) for target in active_targets]
       ```
     - Add endpoint to update target: `PUT /api/v1/user/targets/{target_id}`
     - Add endpoint to mark achieved: `POST /api/v1/user/targets/{target_id}/achieved`

4. **Paper Trading Integration:**
   - `server/app/routers/paper_trading.py`:
     - Line 180-183: Reading `active_sell_orders.json` - Migrate to database
     - Update to create targets in database when sell orders placed
     - Update targets endpoint to query from database

5. **Targets Service (Optional):**
   - `server/app/services/targets_service.py` - Create new service:
     ```python
     class TargetsService:
         def calculate_targets_for_positions(self, user_id: int) -> list[Targets]:
             # Calculate EMA9 targets for all open positions
             # Create/update target records
             pass

         def update_target_prices(self, user_id: int):
             # Update target prices based on latest EMA9
             pass
     ```

6. **Migration from JSON:**
   - Create script to migrate existing `active_sell_orders.json` to database:
     - `scripts/migrate_targets_from_json.py`
     - Read JSON files for all users
     - Create target records in database

**Acceptance Criteria:**
- Migration runs successfully
- Targets created when sell orders placed
- Targets page queries from database
- Historical target tracking works
- JSON migration completes successfully
- Backward compatible (can still read JSON if target not in DB)

---

#### 0.5 P&L Calculation Audit Table
**Priority:** 🟡 Medium (Should Have)
**Effort:** Low (1-2 days)
**Dependencies:** None
**Blocks:** Phase 1.2 (PnL Service) - Monitoring and debugging

**Description:**
Create `pnl_calculation_audit` table to track when P&L calculations were run, what data was used, and performance metrics.

**Deliverables:**
- [ ] Create `PnlCalculationAudit` model
- [ ] Create Alembic migration script
- [ ] Update PnL calculation service to log audit records
- [ ] Add API endpoint to view calculation history
- [ ] Test migration up/down

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `PnlCalculationAudit` model
- `alembic/versions/XXXX_add_pnl_calculation_audit.py` - Migration
- `server/app/services/pnl_calculation_service.py` - Log audit records
- `server/app/routers/pnl.py` - Add audit history endpoint

**Code Changes Required:**

1. **Model Update:**
   - `src/infrastructure/db/models.py` - Add `PnlCalculationAudit` model

2. **Repository (Optional):**
   - `src/infrastructure/persistence/pnl_audit_repository.py` - Create new file:
     ```python
     class PnlAuditRepository:
         def create(self, audit: PnlCalculationAudit) -> PnlCalculationAudit
         def get_by_user(self, user_id: int, limit: int = 100) -> list[PnlCalculationAudit]
         def get_latest(self, user_id: int) -> PnlCalculationAudit | None
     ```

3. **PnL Calculation Service Updates:**
   - `server/app/services/pnl_calculation_service.py` (Phase 1.2):
     - Wrap calculation in audit logging:
       ```python
       def calculate_pnl(self, user_id: int, date_range: tuple[date, date] | None = None):
           start_time = time.time()
           audit = PnlCalculationAudit(
               user_id=user_id,
               calculation_type="on_demand",
               date_range_start=date_range[0] if date_range else None,
               date_range_end=date_range[1] if date_range else None,
               status="running",
               triggered_by="user",
           )
           db.add(audit)
           db.commit()

           try:
               # Perform calculation
               positions_processed = ...
               orders_processed = ...
               pnl_records_created = ...

               audit.status = "success"
               audit.positions_processed = positions_processed
               audit.orders_processed = orders_processed
               audit.pnl_records_created = pnl_records_created
           except Exception as e:
               audit.status = "failed"
               audit.error_message = str(e)
           finally:
               audit.duration_seconds = time.time() - start_time
               db.commit()
       ```

4. **API Updates:**
   - `server/app/routers/pnl.py`:
     - Add endpoint: `GET /api/v1/user/pnl/audit-history`
     - Return list of calculation audit records

**Acceptance Criteria:**
- Migration runs successfully
- Audit records created for each calculation
- Calculation history queryable via API
- Performance metrics tracked correctly

---

#### 0.6 Historical Price Cache Table
**Priority:** 🟡 Medium (Should Have)
**Effort:** Medium (2-3 days)
**Dependencies:** None
**Blocks:** Phase 2.2 (Portfolio Chart) - Performance improvement

**Description:**
Create `price_cache` table to cache historical prices. Reduces API calls and improves portfolio value calculation performance.

**Deliverables:**
- [ ] Create `PriceCache` model
- [ ] Create Alembic migration script
- [ ] Create repository (`PriceCacheRepository`)
- [ ] Update price fetching to check cache first
- [ ] Populate cache during EOD cleanup or on-demand
- [ ] Add cache invalidation logic (TTL)
- [ ] Test migration up/down

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `PriceCache` model
- `alembic/versions/XXXX_add_price_cache.py` - Migration
- `src/infrastructure/persistence/price_cache_repository.py` - New repository
- `core/data_fetcher.py` or price service - Check cache before API call
- EOD cleanup service - Populate cache

**Code Changes Required:**

1. **New Repository:**
   - `src/infrastructure/persistence/price_cache_repository.py` - Create new file:
     ```python
     class PriceCacheRepository:
         def get(self, symbol: str, date: date) -> PriceCache | None
         def create_or_update(self, symbol: str, date: date, price_data: dict) -> PriceCache
         def get_bulk(self, symbols: list[str], date: date) -> dict[str, PriceCache]
         def invalidate_old(self, days: int = 365) -> int  # Remove old cache entries
     ```

2. **Price Service Updates:**
   - `core/data_fetcher.py` or price service:
     - Update `get_price()` method to check cache first:
       ```python
       def get_price(self, symbol: str, date: date) -> float:
           # Check cache first
           cached = price_cache_repo.get(symbol, date)
           if cached:
               return cached.close

           # Fetch from API
           price_data = yfinance_fetch(symbol, date)

           # Cache result
           price_cache_repo.create_or_update(symbol, date, price_data)

           return price_data["close"]
       ```

3. **EOD Cleanup Integration:**
   - EOD cleanup service:
     - After market close, fetch prices for all symbols in positions
     - Cache prices for next day's calculations

4. **Portfolio Calculation Updates:**
   - `server/app/services/portfolio_calculation_service.py`:
     - Use cached prices when calculating historical portfolio values
     - Fallback to API if cache miss

**Acceptance Criteria:**
- Migration runs successfully
- Price cache reduces API calls
- Portfolio calculations are faster
- Cache invalidation works correctly

---

#### 0.7 Export Job Tracking Table
**Priority:** 🟢 Low (Nice to Have)
**Effort:** Low (1-2 days)
**Dependencies:** None
**Blocks:** Phase 3.1 (CSV Export) - User experience improvement

**Description:**
Create `export_jobs` table to track export operations for monitoring and user feedback.

**Deliverables:**
- [ ] Create `ExportJob` model
- [ ] Create Alembic migration script
- [ ] Update export service to create job records
- [ ] Add progress tracking
- [ ] Add API endpoint to check export status
- [ ] Test migration up/down

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `ExportJob` model
- `alembic/versions/XXXX_add_export_jobs.py` - Migration
- `server/app/services/export_service.py` - Track export jobs
- `server/app/routers/export.py` - Add job status endpoint

**Acceptance Criteria:**
- Migration runs successfully
- Export jobs tracked correctly
- User can check export status

---

#### 0.8 Analytics Cache Table
**Priority:** 🟢 Low (Nice to Have)
**Effort:** Low (1-2 days)
**Dependencies:** None
**Blocks:** Phase 4.1 (Performance Analytics) - Performance improvement

**Description:**
Create `analytics_cache` table to cache expensive analytics calculations.

**Deliverables:**
- [ ] Create `AnalyticsCache` model
- [ ] Create Alembic migration script
- [ ] Update analytics service to check cache first
- [ ] Invalidate cache when new trades/positions added
- [ ] Add TTL for cache expiration
- [ ] Test migration up/down

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add `AnalyticsCache` model
- `alembic/versions/XXXX_add_analytics_cache.py` - Migration
- `server/app/services/analytics_service.py` - Use cache
- Cache invalidation on order/position updates

**Code Changes Required:**

1. **Model Update:**
   - `src/infrastructure/db/models.py` - Add `AnalyticsCache` model

2. **Repository:**
   - `src/infrastructure/persistence/analytics_cache_repository.py` - Create new file:
     ```python
     class AnalyticsCacheRepository:
         def get(self, user_id: int, cache_key: str) -> AnalyticsCache | None
         def create_or_update(self, user_id: int, cache_key: str, data: dict, ttl_hours: int = 24) -> AnalyticsCache
         def invalidate(self, user_id: int, analytics_type: str | None = None) -> int
         def cleanup_expired(self) -> int
     ```

3. **Analytics Service Updates:**
   - `server/app/services/analytics_service.py` (Phase 4.1):
     - Check cache before calculating:
       ```python
       def get_win_rate(self, user_id: int, date_range: tuple[date, date]) -> float:
           cache_key = f"win_rate_{date_range[0]}_{date_range[1]}"

           # Check cache
           cached = analytics_cache_repo.get(user_id, cache_key)
           if cached and cached.expires_at > ist_now():
               return cached.cached_data["win_rate"]

           # Calculate
           win_rate = self._calculate_win_rate(user_id, date_range)

           # Cache result
           analytics_cache_repo.create_or_update(
               user_id, cache_key, {"win_rate": win_rate}, ttl_hours=24
           )

           return win_rate
       ```

4. **Cache Invalidation:**
   - On order/position updates:
     - `src/infrastructure/persistence/orders_repository.py` - Invalidate cache after order updates
     - `src/infrastructure/persistence/positions_repository.py` - Invalidate cache after position updates
     - Or use event system to trigger invalidation

**Acceptance Criteria:**
- Migration runs successfully
- Analytics page loads faster
- Cache invalidation works correctly
- TTL expiration works correctly

---

**Phase 0 Summary:**
- **High Priority (Must Have):** 0.1, 0.2, 0.3 (5-8 days)
- **Medium Priority (Should Have):** 0.4, 0.5, 0.6 (6-9 days)
- **Low Priority (Nice to Have):** 0.7, 0.8 (2-4 days)
- **Total Effort:** 13-22 days (can be done in parallel with Phase 1.1)

**Testing Requirements:**
- All migrations tested up/down
- Data backfill scripts tested
- Verify no data loss
- Performance impact assessment
- Rollback plan ready

---

### Phase 1: Chart Library & Infrastructure Setup (Foundation)

#### 1.1 Install Chart Library
**Priority:** 🔴 High
**Effort:** Low (0.5 days)
**Dependencies:** None
**Status:** ✅ Complete

**Description:**
- Install and configure charting library (Recharts recommended for React)
- Set up chart utilities and helpers
- Configure chart themes to match application design

**Deliverables:**
- [x] Install `recharts` package in `web/package.json`
- [x] Create chart theme configuration
- [x] Create reusable chart wrapper components
- [x] Add chart styling to match dark theme

**Acceptance Criteria:**
- ✅ Chart library installed and configured
- ✅ Chart components match application theme
- ✅ No bundle size issues

**Files Modified:**
- `web/package.json` - Added recharts dependency (v3.6.0)
- `web/src/components/charts/` - Created chart components directory with:
  - `chartTheme.ts` - Theme configuration
  - `ChartContainer.tsx` - Panel container component
  - `ResponsiveChart.tsx` - Responsive wrapper
  - `chartStyles.ts` - Recharts style utilities
  - `ExampleLineChart.tsx` - Example component
  - `index.ts` - Exports
- `web/src/index.css` - Added chart-specific CSS

---

#### 1.2 PnL Data Population Service
**Priority:** 🔴 **CRITICAL - START IMMEDIATELY**
**Effort:** Medium-High (3-4 days) - Updated estimate based on complexity
**Dependencies:** Phase 0.5 (P&L Calculation Audit) - Optional, can be added later
**⚠️ BLOCKER:** This feature blocks 3 major features. Start immediately, don't wait for Phase 1.1.
**Status:** ✅ Complete (Core Implementation)

**Description:**
- Create service to populate `pnl_daily` table with calculated P&L data
- Calculate daily P&L from positions and orders tables
- Support both paper trading and broker trading modes
- Enable on-demand calculation and scheduled daily updates

**Current State:**
- ✅ `pnl_daily` table exists
- ✅ P&L API endpoints exist (`/api/v1/user/pnl/daily`, `/api/v1/user/pnl/summary`)
- ✅ PnL calculation service created
- ✅ On-demand calculation endpoint added
- ✅ Historical backfill endpoint added
- ⏳ `pnl_daily` table population (ready to use via API)
- ⏳ Unrealized P&L uses placeholder (needs price fetching integration)

**Deliverables:**
- [x] PnL calculation service (`server/app/services/pnl_calculation_service.py`)
- [x] Calculate realized P&L from closed positions (uses Phase 0.2 exit details)
- [x] Calculate unrealized P&L from open positions (placeholder - uses unrealized_pnl field)
- [x] Estimate fees from orders (0.1% per transaction)
- [x] Daily P&L aggregation logic
- [x] On-demand calculation endpoint (`POST /api/v1/user/pnl/calculate`)
- [ ] Background job/service for daily EOD calculation (optional, can be scheduled later)
- [x] Support for both paper trading and broker trading modes
- [x] Historical data backfill capability (`POST /api/v1/user/pnl/backfill`, max 1 year)
- [x] Error handling and logging
- [ ] **Data validation script** to compare calculated P&L vs. manual calculation (future)
- [ ] **Performance benchmarks** for backfill (future)
- [ ] **Error recovery mechanism** for failed calculations (basic error handling done)
- [ ] **Audit trail** for P&L calculations (Phase 0.5 integration pending)
- [ ] **Progress indicator** for backfill operations (future)
- [x] **Date range limits** for backfill (max 1 year at a time)

**Acceptance Criteria:**
- ✅ P&L calculation service created and functional
- ✅ Realized P&L calculated from closed positions accurately (uses realized_pnl from Phase 0.2)
- ⏳ Unrealized P&L calculated from open positions (placeholder - needs price fetching)
- ✅ Fees estimated correctly (0.1% per transaction)
- ✅ Works for both paper and broker trading modes
- ✅ On-demand calculation endpoint available
- ✅ Historical backfill works correctly (with date range limits)

**Files to Create/Modify:**
- `server/app/services/pnl_calculation_service.py` - New PnL calculation service
- `server/app/routers/pnl.py` - Add endpoint to trigger calculation/backfill
- `src/infrastructure/persistence/pnl_repository.py` - May need upsert improvements
- `src/infrastructure/persistence/positions_repository.py` - Query positions (use exit details from Phase 0.2)
- `src/infrastructure/persistence/orders_repository.py` - Query orders for fees
- `src/infrastructure/persistence/pnl_calculation_audit_repository.py` - Optional (Phase 0.5)

**API Requirements:**
- `POST /api/v1/user/pnl/calculate` - Trigger on-demand P&L calculation
- `POST /api/v1/user/pnl/backfill` - Backfill historical P&L data (optional)

**Implementation Details:**

1. **Realized P&L Calculation:**
   - Query closed positions (`positions` table where `closed_at IS NOT NULL`)
   - Calculate: `(exit_price - avg_price) * quantity` for each closed position
   - Sum by date (using `closed_at` date)
   - Account for fees (estimate or use actual from orders)

2. **Unrealized P&L Calculation:**
   - Query open positions (`positions` table where `closed_at IS NULL`)
   - Get current price (from broker API or yfinance)
   - Calculate: `(current_price - avg_price) * quantity` for each open position
   - Sum by date (using current date)
   - Update daily as prices change

3. **Fees Calculation:**
   - Option 1: Estimate 0.1% per transaction (buy + sell)
   - Option 2: Use actual charges from `order_metadata` if available
   - Sum fees by date

4. **Daily Aggregation:**
   - Group by `user_id` and `date`
   - Store in `pnl_daily` table using `upsert` (handles duplicates)
   - Ensure one record per user per date

**Integration Points:**
- Prerequisite for Phase 2.1 (P&L Trend Chart) - chart needs data
- Prerequisite for Phase 2.3 (Dashboard Metrics) - metrics need P&L data
- Prerequisite for Phase 4.1 (Performance Analytics) - analytics need P&L data
- Can be scheduled as EOD job in future (not required for v26.1.1)

**Testing Requirements:**
- Unit tests for P&L calculation logic
- Unit tests for realized vs unrealized P&L
- **Edge case tests:** Partial fills, manual trades, symbol mismatches
- **Data validation tests:** Compare calculated vs. expected P&L
- **Performance tests:** Large datasets (1000+ positions), backfill performance
- Integration tests for calculation service
- Test with both paper and broker trading data
- Test historical backfill (incremental and full)
- **Error handling tests:** Failed calculations, missing data, API failures

**Future Enhancements (Not in v26.1.1):**
- Scheduled EOD job for automatic daily calculation
- Real-time P&L updates via WebSocket
- More accurate fee calculation from broker API
- P&L breakdown by symbol/strategy

---

### Phase 2: Core Dashboard Enhancements (High Priority)

#### 2.1 P&L Trend Chart
**Priority:** 🔴 High
**Effort:** Medium (3-5 days)
**Dependencies:** 1.1 (Chart Library), 1.2 (PnL Data Population Service), 0.5 (P&L Calculation Audit - Optional)

**Description:**
- Add interactive line chart showing P&L over time
- Support multiple time ranges (7 days, 30 days, 90 days, 1 year)
- Show realized vs unrealized P&L separately
- Display key milestones (best day, worst day, break-even points)

**Current State:**
- ✅ P&L API endpoints exist (`/api/v1/user/pnl/daily`, `/api/v1/user/pnl/summary`)
- ✅ P&L Page exists (`web/src/routes/dashboard/PnlPage.tsx`)
- ❌ P&L data not populated in `pnl_daily` table (blocking chart display)
- ❌ No chart component
- ❌ No time range selector

**Deliverables:**
- [ ] P&L trend chart component using Recharts
- [ ] Time range selector (7d, 30d, 90d, 1y)
- [ ] Realized vs unrealized P&L toggle/overlay
- [ ] Tooltip with detailed information (date, P&L, realized, unrealized)
- [ ] Key milestone markers (best day, worst day, break-even)
- [ ] Mobile-responsive chart
- [ ] Loading states and error handling

**Acceptance Criteria:**
- Chart loads within 2 seconds
- Supports all time ranges
- Works on mobile devices
- Tooltips show accurate data
- Smooth interactions and animations

**Files to Create/Modify:**
- `web/src/components/charts/PnlTrendChart.tsx` - New chart component
- `web/src/routes/dashboard/PnlPage.tsx` - Add chart and time range selector
- `web/src/api/pnl.ts` - Add time range parameter support if needed

**API Requirements:**
- Verify `/api/v1/user/pnl/daily` supports date range parameters
- May need to add endpoint for historical P&L data if not available

---

#### 2.2 Portfolio Value Chart
**Priority:** 🔴 High
**Effort:** Medium (2-3 days)
**Dependencies:** 1.1 (Chart Library), 0.3 (Portfolio Snapshots - Required), 0.6 (Price Cache - Optional), 2.1 (P&L Chart for reference)

**Description:**
- Line chart showing portfolio value over time
- Overlay with initial capital for reference
- Highlight major gains/losses
- Show return percentage trend

**Current State:**
- ✅ Portfolio value displayed as metric card on dashboard
- ✅ Portfolio data API exists (`/api/v1/user/portfolio`)
- ❌ No historical portfolio data API
- ❌ No chart component

**Deliverables:**
- [ ] Historical portfolio data API endpoint
- [ ] Portfolio value chart component
- [ ] Initial capital reference line
- [ ] Return percentage overlay/annotation
- [ ] Major gain/loss markers
- [ ] Time range selector
- [ ] Mobile-responsive chart

**Acceptance Criteria:**
- Chart updates in real-time (when data refreshes)
- Shows accurate portfolio value over time
- Initial capital line clearly visible
- Mobile-responsive
- Smooth animations

**Files to Create/Modify:**
- `server/app/routers/paper_trading.py` or new router - Add historical portfolio endpoint
- `web/src/components/charts/PortfolioValueChart.tsx` - New chart component
- `web/src/routes/dashboard/PaperTradingPage.tsx` - Add chart
- `web/src/api/paper-trading.ts` - Add historical portfolio API call

**API Requirements:**
- Create `/api/v1/user/portfolio/history` endpoint
- Return portfolio value snapshots over time
- Support date range filtering

---

#### 2.3 Complete Enhanced Dashboard Metrics
**Priority:** 🟡 Medium
**Effort:** Low (1-2 days)
**Dependencies:** 1.2 (PnL Data Population Service) - Metrics need P&L data

**Description:**
- Complete missing dashboard metrics
- Win rate percentage
- Average profit per trade
- Best/worst trade
- Ensure all metrics are accurate and performant
- **Note:** Requires P&L data to be populated (from 1.2)

**Current State:**
- ✅ Basic metrics exist (Portfolio Value, Total P&L, Active Signals, Open Orders)
- ✅ Active positions count available
- ✅ Total trades count available
- ❌ Win rate percentage - NOT implemented
- ❌ Average profit per trade - NOT implemented
- ❌ Best/worst trade - NOT implemented

**Deliverables:**
- [ ] Win rate calculation API endpoint
- [ ] Average profit per trade calculation
- [ ] Best/worst trade API endpoint
- [ ] Additional metric cards on dashboard
- [ ] Loading states for new metrics
- [ ] Error handling

**Acceptance Criteria:**
- All metrics display correctly
- Fast loading (< 1 second)
- Mobile-friendly layout
- Accurate calculations

**Files to Create/Modify:**
- `server/app/routers/pnl.py` or new router - Add metrics endpoints
- `web/src/routes/dashboard/DashboardHome.tsx` - Add new metric cards
- `web/src/api/pnl.ts` or new API file - Add metrics API calls

**API Requirements:**
- `/api/v1/user/metrics/win-rate` - Calculate win rate
- `/api/v1/user/metrics/average-profit` - Calculate average profit per trade
- `/api/v1/user/metrics/best-worst-trades` - Get best and worst trades

---

#### 2.4 Broker Trading History
**Priority:** 🔴 High
**Effort:** Medium-High (5-7 days) - Updated estimate based on complexity
**Dependencies:** 0.1 (Trade Mode Column - Required), 0.2 (Exit Details - Required)
**⚠️ COMPLEXITY:** FIFO matching, edge cases, and performance optimization require careful implementation

**Description:**
- Add broker trading history endpoint and UI page
- Provide complete trade history for real broker trades (similar to paper trading history)
- Show all transactions, closed positions with P&L, and statistics
- Address critical edge cases: trade mode filtering, partial fills, symbol normalization, manual trades

**Current State:**
- ✅ Paper trading history exists (`/api/v1/user/paper-trading/history`)
- ✅ Paper trading history page exists (`web/src/routes/dashboard/PaperTradingHistoryPage.tsx`)
- ✅ Broker orders and positions stored in database (`orders` and `positions` tables)
- ❌ No broker trade history endpoint
- ❌ No broker trade history UI page

**Deliverables:**
- [ ] Broker trade history API endpoint (`/api/v1/user/broker/history`)
- [ ] Trade history calculation logic (transactions, closed positions, statistics)
- [ ] Edge case handling:
  - Trade mode validation (ensure user is in broker mode)
  - Partial fill handling (use `execution_qty` when available)
  - Symbol normalization for matching
  - Manual trade filtering/flagging
  - FIFO matching without in-place mutation
  - Timezone-aware timestamp handling
- [ ] Broker trade history UI page (`web/src/routes/dashboard/BrokerTradingHistoryPage.tsx`)
- [ ] Reuse existing `TradeHistory` schema and components where possible
- [ ] Date range filtering support
- [ ] Pagination for large datasets (from the start, not as afterthought)
- [ ] Loading states and error handling
- [ ] Mobile-responsive design
- [ ] **Performance optimization** for large datasets (1000+ orders)

**Implementation Phases (Recommended):**
- **Phase A:** Basic history (transactions only, no matching) - 2 days
- **Phase B:** FIFO matching and closed positions - 2-3 days
- **Phase C:** Statistics and edge cases - 1-2 days

**Acceptance Criteria:**
- API endpoint returns data in same format as paper trading history
- All transactions from `orders` table are included
- Closed positions calculated correctly using FIFO matching
- Statistics (win rate, P&L, etc.) are accurate
- Only broker trades included (no paper trading data leakage)
- Handles partial fills correctly
- Fast response time (< 2 seconds for typical datasets)
- Works on mobile devices
- Error handling for edge cases

**Files to Create/Modify:**
- `server/app/routers/broker.py` - Add `/history` endpoint
- `web/src/routes/dashboard/BrokerTradingHistoryPage.tsx` - New page component
- `web/src/api/broker.ts` - Add `getBrokerTradingHistory()` function
- `web/src/router.tsx` - Add broker history route
- `web/src/routes/AppShell.tsx` - Add navigation link (if needed)

**API Requirements:**
- Endpoint: `GET /api/v1/user/broker/history`
- Query parameters:
  - `from_date` (optional): Filter transactions from date (ISO format)
  - `to_date` (optional): Filter transactions to date (ISO format)
  - `limit` (optional): Limit number of transactions (default: 1000, max: 10000)
- Response: Same `TradeHistory` schema as paper trading
- Validation: Ensure user is in broker mode (return 400 if not)

**Implementation Details:**

1. **Backend Implementation** (`server/app/routers/broker.py`):
   - Add `get_broker_trading_history()` endpoint
   - Query `orders` table for executed orders (status ONGOING or CLOSED with execution details)
   - Query `positions` table for closed positions
   - Convert orders to transactions format
   - Match buy/sell orders using FIFO algorithm (without in-place mutation)
   - Calculate closed positions from matched transactions
   - Calculate statistics (win rate, total P&L, etc.)
   - Filter by trade mode (validate user is in broker mode)
   - Handle partial fills using `execution_qty`
   - Normalize symbols for matching
   - Add date range filtering
   - Add pagination support

2. **Frontend Implementation**:
   - Create `BrokerTradingHistoryPage.tsx` similar to `PaperTradingHistoryPage.tsx`
   - Reuse existing `TradeHistory` type and components
   - Add date range picker
   - Add export button (connects to Phase 3.1 CSV export)
   - Show loading states
   - Handle errors gracefully

3. **Edge Cases to Address**:
   - Trade mode validation: Check `user_settings.trade_mode == TradeMode.BROKER`
   - Partial fills: Use `order.execution_qty` if available, otherwise `order.quantity`
   - Symbol matching: Normalize symbols using `extract_base_symbol()` utility
   - Manual trades: Option to filter or flag (add `is_manual` field to transactions)
   - FIFO matching: Create copies for matching, don't mutate original transaction objects
   - Charges: Use actual charges from `order_metadata` if available, otherwise estimate
   - Exit price: Match sell orders to closed positions by timestamp proximity
   - Timezone: Ensure all timestamps are timezone-aware
   - Performance: Add pagination and date filtering to avoid loading all orders

**Integration Points:**
- Reuses `TradeHistory` schema from `server/app/routers/paper_trading.py`
- Integrates with Phase 3.1 CSV export (add broker history to export list)
- Can be used by Phase 4.1 Performance Analytics (as data source)
- Shares UI components with paper trading history page

**Testing Requirements:**
- **Unit tests for FIFO matching algorithm** (TDD approach - write tests first)
- Unit tests for statistics calculations
- Integration tests for API endpoint
- Edge case tests (partial fills, manual trades, symbol mismatches, timezone issues)
- **Performance tests** (large datasets: 1000+, 5000+, 10000+ orders)
- E2E tests for UI page
- **Data validation tests** (compare calculated history vs. expected)

**Dependencies:**
- `src/infrastructure/persistence/orders_repository.py` - Query orders
- `src/infrastructure/persistence/positions_repository.py` - Query positions
- `src/infrastructure/persistence/settings_repository.py` - Get trade mode
- `modules/kotak_neo_auto_trader/utils/symbol_utils.py` - Symbol normalization

**Future Enhancements (Not in v26.1.1):**
- Add `trade_mode` column to `orders` table (from UNIFIED_DB_IMPLEMENTATION_COMPLETE.md)
- Store actual charges in `order_metadata` for accurate P&L
- Add open positions to history (currently only closed positions)
- Add caching for calculated history
- Real-time updates via WebSocket

---

#### 2.5 Targets Page Implementation
**Priority:** 🟡 Medium
**Effort:** Low (1-2 days)
**Dependencies:** 0.4 (Targets Table - Optional, improves implementation)

**Description:**
- Implement Targets page to display active sell order targets
- Show target prices (EMA9) for open positions
- Display current price and distance to target
- Support both paper trading and broker trading modes

**Current State:**
- ✅ Targets page exists (`web/src/routes/dashboard/TargetsPage.tsx`)
- ❌ Targets endpoint is placeholder (returns empty list)
- ❌ Target prices exist in system but not exposed via API
- ✅ Paper trading: Targets stored in `active_sell_orders.json`
- ✅ Broker trading: Targets can be derived from positions or calculated from EMA9

**Deliverables:**
- [ ] Targets API endpoint implementation (`/api/v1/user/targets`)
- [ ] Query targets from appropriate source:
  - Paper trading: Read from `active_sell_orders.json`
  - Broker trading: Derive from positions or calculate EMA9 for open positions
- [ ] Return target information:
  - Symbol
  - Target price (EMA9)
  - Current price
  - Distance to target (percentage)
  - Entry price (from position)
  - Quantity
- [ ] Update Targets page UI to display data
- [ ] Add current price fetching (broker API or yfinance)
- [ ] Add distance to target calculation
- [ ] Loading states and error handling
- [ ] Mobile-responsive design

**Acceptance Criteria:**
- Targets page displays active targets correctly
- Target prices are accurate (EMA9 values)
- Current prices update correctly
- Distance to target calculated accurately
- Works for both paper and broker trading modes
- Fast loading (< 2 seconds)
- Mobile-responsive

**Files to Create/Modify:**
- `server/app/routers/targets.py` - Implement targets endpoint (currently placeholder)
- `web/src/routes/dashboard/TargetsPage.tsx` - Update to display target data
- `web/src/api/targets.ts` - Verify API client works
- `server/app/services/targets_service.py` - New service for target calculation (optional)

**API Requirements:**
- Endpoint: `GET /api/v1/user/targets`
- Response: List of target items with:
  - `id`: Target ID (or position ID)
  - `symbol`: Stock symbol
  - `target_price`: EMA9 target price
  - `current_price`: Current market price
  - `entry_price`: Average entry price (from position)
  - `quantity`: Position quantity
  - `distance_to_target`: Percentage distance to target
  - `note`: Optional note/description
  - `created_at`: When target was set

**Implementation Details:**

1. **For Paper Trading:**
   - Read `active_sell_orders.json` from user's paper trading directory
   - Extract target prices from sell orders
   - Get current prices from yfinance or stored prices
   - Calculate distance to target

2. **For Broker Trading:**
   - Option A: Query open positions from `positions` table
   - Calculate EMA9 for each position symbol
   - Get current prices from broker API
   - Calculate distance to target
   - Option B: Query active sell orders from broker API (if available)
   - Extract target prices from sell orders

3. **Target Calculation:**
   - Use existing EMA9 calculation logic from `sell_engine.py`
   - Reuse `calculate_ema9()` function or similar
   - Ensure consistency with sell order targets

**Integration Points:**
- Standalone feature providing immediate value
- Can be enhanced in future with manual target creation
- Supports Phase 4.1 (Performance Analytics) - target achievement metrics

**Testing Requirements:**
- Unit tests for target calculation
- Integration tests for targets API
- Test with both paper and broker trading modes
- Test with empty targets (no open positions)
- E2E tests for Targets page

**Future Enhancements (Not in v26.1.1):**
- Manual target creation/editing
- Target alerts (notify when target reached)
- Target history tracking
- Multiple targets per symbol
- Target achievement statistics

---

### Phase 3: Data Export & Reporting (High Priority)

#### 3.1 Complete CSV Export UI
**Priority:** 🔴 High
**Effort:** Low (2-3 days)
**Dependencies:** Backend CSV export endpoint (already exists), 0.7 (Export Job Tracking - Optional)

**Description:**
- Connect existing backend CSV export to web UI
- Add export buttons on relevant pages
- Support date range selection
- Add progress indicators for large exports

**Current State:**
- ✅ Backend CSV export exists (`core/csv_exporter.py`)
- ✅ Backend CSV export for paper trading reports
- ❌ No UI export buttons
- ❌ No API endpoints for CSV export from web UI
- ❌ No date range selection

**Deliverables:**
- [ ] CSV export API endpoints for:
  - P&L data
  - Trade history
  - Signals data
  - Orders
  - Portfolio holdings
- [ ] Export button component
- [ ] Date range picker for exports
- [ ] Progress indicator for large exports
- [ ] Error handling and user feedback
- [ ] Export buttons on:
  - P&L page
  - Paper Trading History page
  - Broker Trading History page
  - Orders page
  - Buying Zone (Signals) page
  - Portfolio page

**Acceptance Criteria:**
- Exports complete within 5 seconds for < 1000 records
- CSV format is correct and importable
- All relevant data fields included
- Works on all browsers
- User-friendly error messages

**Files to Create/Modify:**
- `server/app/routers/export.py` - New export router
- `web/src/components/ExportButton.tsx` - Reusable export button
- `web/src/routes/dashboard/PnlPage.tsx` - Add export button
- `web/src/routes/dashboard/PaperTradingHistoryPage.tsx` - Add export button
- `web/src/routes/dashboard/OrdersPage.tsx` - Add export button
- `web/src/routes/dashboard/BuyingZonePage.tsx` - Add export button
- `web/src/api/export.ts` - Export API functions

**Backend Integration:**
- Leverage existing `core/csv_exporter.py`
- Create service layer for export operations
- Add proper error handling and validation

---

#### 3.2 PDF Report Generation
**Priority:** 🟡 Medium
**Effort:** Medium (4-5 days)
**Dependencies:** 3.1 (CSV Export), 2.1 (P&L Chart), 2.2 (Portfolio Chart)

**Description:**
- Generate PDF reports for P&L
- Daily/weekly/monthly summary reports
- Include charts in PDF
- Professional formatting

**Deliverables:**
- [ ] Install PDF generation library (e.g., `reportlab` or `weasyprint`)
- [ ] PDF report templates
- [ ] Chart rendering in PDF (convert charts to images)
- [ ] Report generation API endpoint
- [ ] Download functionality
- [ ] Report types:
  - Daily P&L report
  - Weekly summary report
  - Monthly summary report
  - Custom date range report

**Acceptance Criteria:**
- PDFs generate within 10 seconds
- Charts render correctly in PDF
- Professional formatting
- All data accurate
- Downloadable files

**Files to Create/Modify:**
- `server/app/routers/reports.py` - New reports router
- `server/app/services/pdf_generator.py` - PDF generation service
- `server/app/templates/reports/` - PDF templates
- `web/src/routes/dashboard/PnlPage.tsx` - Add PDF export option
- `web/src/api/reports.ts` - Reports API functions

**Dependencies to Add:**
- `reportlab` or `weasyprint` for Python backend
- Chart-to-image conversion utility

---

### Phase 4: Advanced Analytics (Medium Priority)

#### 4.1 Performance Analytics Page
**Priority:** 🟡 Medium
**Effort:** High (5-7 days)
**Dependencies:** 1.1 (Chart Library), 2.1 (P&L Chart), 1.2 (PnL Data Population Service), 0.2 (Exit Details - Required), 0.8 (Analytics Cache - Optional)

**Description:**
- Comprehensive performance metrics page
- Win rate analysis with charts
- Average profit/loss per trade
- Best/worst trades
- Trade duration analysis
- Strategy performance breakdown
- Can use broker trade history as data source for analytics (from Phase 2.4)
- **Note:** Requires P&L data to be populated (from 1.2)

**Current State:**
- ✅ Backend performance analyzer exists (`backtest/performance_analyzer.py`)
- ❌ No frontend analytics page
- ❌ No performance metrics API for web UI

**Deliverables:**
- [ ] New analytics page route (`/dashboard/analytics`)
- [ ] Performance metrics API endpoints
- [ ] Win rate chart (pie or bar chart)
- [ ] Profit/loss distribution chart
- [ ] Trade duration histogram
- [ ] Best/worst trades table
- [ ] Strategy performance breakdown
- [ ] Filtering options (date range, strategy type)
- [ ] Export functionality (CSV, PDF)

**Acceptance Criteria:**
- All metrics calculate correctly
- Charts render properly
- Fast page load (< 3 seconds)
- Mobile-responsive
- Accurate data

**Files to Create/Modify:**
- `server/app/routers/analytics.py` - New analytics router
- `server/app/services/analytics_service.py` - Analytics calculation service
- `web/src/routes/dashboard/AnalyticsPage.tsx` - New analytics page
- `web/src/components/charts/WinRateChart.tsx` - Win rate visualization
- `web/src/components/charts/ProfitLossDistribution.tsx` - Distribution chart
- `web/src/api/analytics.ts` - Analytics API functions
- `web/src/router.tsx` - Add analytics route

**Backend Integration:**
- Leverage existing `backtest/performance_analyzer.py` logic
- Adapt for live trading data
- Create service layer for analytics calculations

---

#### 4.2 Risk Metrics Dashboard
**Priority:** 🟢 Low
**Effort:** Medium (3-4 days)
**Dependencies:** 4.1 (Performance Analytics)

**Description:**
- Risk metrics calculations and visualization
- Sharpe ratio calculation
- Maximum drawdown
- Volatility metrics
- Risk-reward ratios
- Position concentration analysis

**Current State:**
- ✅ Some risk metrics calculated in backtest analyzer
- ❌ No UI dashboard for risk metrics
- ❌ No real-time risk metrics for live trading

**Deliverables:**
- [ ] Risk metrics calculation API
- [ ] Risk metrics section in analytics page
- [ ] Sharpe ratio display
- [ ] Maximum drawdown chart
- [ ] Volatility metrics visualization
- [ ] Risk-reward ratio chart
- [ ] Position concentration chart
- [ ] Historical risk trends

**Acceptance Criteria:**
- Metrics calculate accurately
- Visual indicators are clear
- Historical data available
- Mobile-responsive

**Files to Create/Modify:**
- `server/app/routers/analytics.py` - Add risk metrics endpoints
- `server/app/services/risk_metrics_service.py` - Risk calculations
- `web/src/routes/dashboard/AnalyticsPage.tsx` - Add risk metrics section
- `web/src/components/charts/RiskMetricsChart.tsx` - Risk visualization

---

### Phase 5: Watchlist Management (Medium Priority)

#### 5.1 Watchlist Feature
**Priority:** 🟡 Medium
**Effort:** Medium (4-5 days)
**Dependencies:** None

**Description:**
- Create/manage custom watchlists
- Add/remove stocks from watchlists
- View watchlist stocks on dashboard
- Quick access to watchlist stocks

**Deliverables:**
- [ ] Watchlist database model (Alembic migration)
- [ ] Watchlist API endpoints (CRUD operations)
- [ ] Watchlist management UI page
- [ ] Add/remove stocks functionality
- [ ] Multiple watchlists support
- [ ] Watchlist persistence

**Acceptance Criteria:**
- Users can create multiple watchlists
- Stocks can be added/removed easily
- Watchlist persists across sessions
- Mobile-friendly interface

**Files to Create/Modify:**
- `src/infrastructure/db/models.py` - Add Watchlist and WatchlistItem models
- `alembic/versions/XXXX_add_watchlist.py` - Database migration
- `server/app/routers/watchlist.py` - Watchlist API router
- `web/src/routes/dashboard/WatchlistPage.tsx` - Watchlist management page
- `web/src/api/watchlist.ts` - Watchlist API functions
- `web/src/router.tsx` - Add watchlist route

**Database Schema:**
```python
class Watchlist(Base):
    id: int
    user_id: int
    name: str
    created_at: datetime
    updated_at: datetime

class WatchlistItem(Base):
    id: int
    watchlist_id: int
    symbol: str
    added_at: datetime
```

---

#### 5.2 Watchlist Dashboard Widget
**Priority:** 🟡 Medium
**Effort:** Low (1-2 days)
**Dependencies:** 5.1 (Watchlist Feature)

**Description:**
- Display watchlist stocks on dashboard
- Show current price and change
- Quick link to buying zone for each stock
- Color-coded price changes

**Deliverables:**
- [ ] Watchlist widget component
- [ ] Price display (if available from API)
- [ ] Quick action buttons
- [ ] Responsive design
- [ ] Integration with dashboard home

**Acceptance Criteria:**
- Widget loads quickly
- Prices update (if real-time available)
- Easy navigation to stock details
- Mobile-responsive

**Files to Create/Modify:**
- `web/src/components/WatchlistWidget.tsx` - Widget component
- `web/src/routes/dashboard/DashboardHome.tsx` - Add widget
- `web/src/api/watchlist.ts` - Add widget data API

---

### Phase 6: User Experience Improvements (Low Priority)

#### 6.1 Complete Saved Filters & Preferences
**Priority:** 🟢 Low
**Effort:** Low (2-3 days)
**Dependencies:** None

**Description:**
- Complete saved filters implementation
- Save filter presets for signals
- Save column preferences
- Remember date range preferences

**Current State:**
- ✅ `ui_preferences` field exists in `UserSettings` model
- ✅ `SettingsRepository.get_ui_preferences()` method exists
- ✅ API endpoint for UI preferences exists
- ❌ No implementation of saved filter presets
- ❌ No implementation of column preferences persistence
- ❌ No implementation of date range preferences

**Deliverables:**
- [ ] Filter preset storage in `ui_preferences`
- [ ] Save/load filter presets UI
- [ ] Column preferences persistence
- [ ] Date range preferences persistence
- [ ] Auto-restore preferences on page load
- [ ] Preset management UI

**Acceptance Criteria:**
- Preferences save correctly
- Restore on page load
- Multiple presets supported
- Works across all filterable pages

**Files to Create/Modify:**
- `web/src/hooks/useSavedFilters.ts` - Custom hook for filter persistence
- `web/src/routes/dashboard/BuyingZonePage.tsx` - Add filter persistence
- `web/src/routes/dashboard/OrdersPage.tsx` - Add filter persistence
- `web/src/api/settings.ts` - Add preferences update functions
- `server/app/routers/user.py` - Verify preferences API works

---

## 🗓️ Timeline & Milestones

### Option A: Extended Timeline (Recommended)

**Total Duration:** 9-10 weeks (includes 1-2 week buffer)
  - Week -1 to Week 0: Critical Infrastructure Fixes (Kotak Authentication)
  - Week 0-1: Database Migrations (can run in parallel with Phase 1.1)
  - Week 1-8: Feature Development

### Milestone -1: Critical Infrastructure Fixes (Week -1 to Week 0)
- ✅ Kotak Authentication & Session Management Fixes
- ✅ Session validity tracking
- ✅ Proactive session expiration handling
- ✅ Client freshness validation
- ✅ SDK thread safety verification
- **Note:** Must complete before Phase 0

### Milestone 0: Database Migrations (Week 0-1)
- ✅ High Priority: Trade Mode Column, Exit Details, Portfolio Snapshots
- ✅ Medium Priority: Targets Table, P&L Calculation Audit, Price Cache (optional)
- ✅ Low Priority: Export Job Tracking, Analytics Cache (optional)
- **Note:** Can run in parallel with Phase 1.1

### Milestone 1: Foundation & Charts (Week 1-2)
- ✅ Install chart library
- ✅ **PnL Data Population Service** (START IMMEDIATELY - Critical Blocker)
- ✅ P&L Trend Chart
- ✅ Portfolio Value Chart
- ✅ Broker Trading History (Phase A: Basic history)
- ✅ Targets Page Implementation
- **Target:** End of Week 2

### Milestone 2: Dashboard & Export (Week 2-3)
- ✅ Complete Enhanced Dashboard Metrics
- ✅ Complete CSV Export UI
- ✅ Broker Trading History (Phase B: FIFO matching)
- **Target:** End of Week 3

### Milestone 3: Reports & Analytics (Week 3-4)
- ✅ PDF Report Generation
- ✅ Performance Analytics Page
- ✅ Broker Trading History (Phase C: Statistics & edge cases)
- **Target:** End of Week 4

### Milestone 4: Advanced Features (Week 4-6)
- ✅ Risk Metrics Dashboard
- ✅ Watchlist Feature
- ✅ Watchlist Dashboard Widget
- **Target:** End of Week 6

### Milestone 5: UX Polish & Buffer (Week 6-8)
- ✅ Complete Saved Filters
- ✅ Final testing and bug fixes
- ✅ Performance optimization
- ✅ Documentation updates
- **Target:** End of Week 7-8

---

### Option B: Phased Release (Alternative)

**Benefits:** Faster time to market, reduced risk, better user feedback loop

#### v26.1.1a - Core Features (Week 4)
**Target Release:** End of Week 4

**Features:**
- ✅ PnL Data Population Service
- ✅ P&L Trend Chart
- ✅ Portfolio Value Chart
- ✅ Complete Enhanced Dashboard Metrics
- ✅ Complete CSV Export UI
- ✅ Targets Page Implementation
- ✅ Broker Trading History (Basic)

**Success Criteria:**
- All core charts functional
- P&L data populated and accurate
- CSV export working
- Dashboard metrics complete

#### v26.1.1b - Advanced Features (Week 6-7)
**Target Release:** End of Week 6-7

**Features:**
- ✅ PDF Report Generation
- ✅ Performance Analytics Page
- ✅ Risk Metrics Dashboard
- ✅ Watchlist Feature
- ✅ Watchlist Dashboard Widget
- ✅ Complete Saved Filters
- ✅ Broker Trading History (Complete with FIFO matching)

**Success Criteria:**
- All advanced features functional
- Analytics page complete
- Watchlist working
- All features tested and documented

---

## 🧪 Comprehensive Testing Strategy

### Phase -1: Kotak Authentication & Session Management Tests

#### Unit Tests

**Session Validity Tracking:**
- [ ] `is_session_valid()` returns `True` for valid session (< TTL)
- [ ] `is_session_valid()` returns `False` for expired session (> TTL)
- [ ] `is_session_valid()` returns `True` for legacy session (no creation time)
- [ ] `is_session_valid()` returns `False` when not logged in
- [ ] Session creation time tracked correctly on `login()`
- [ ] Session creation time reset correctly on `force_relogin()`
- [ ] TTL safety margin works correctly (55 minutes for 1-hour JWT)

**Client Freshness:**
- [ ] `get_client()` proactively re-authenticates if session expired
- [ ] `get_client()` returns `None` if re-auth fails
- [ ] `get_client()` returns fresh client after successful re-auth
- [ ] `_ensure_fresh_client()` always gets latest client from auth handler
- [ ] `_ensure_fresh_client()` raises `ConnectionError` if not authenticated
- [ ] `_ensure_fresh_client()` raises `ConnectionError` if no client available

**Thread Safety:**
- [ ] Multiple threads can call `get_client()` simultaneously without errors
- [ ] Re-authentication coordinated correctly across threads
- [ ] No race conditions when multiple threads trigger re-auth
- [ ] Client reference updates are thread-safe

#### Integration Tests

**Concurrent API Calls:**
- [ ] 10 threads making API calls simultaneously with same auth instance
- [ ] Re-auth triggered mid-execution, all threads eventually succeed
- [ ] No client reference staleness issues
- [ ] All API calls use fresh client after re-auth
- [ ] ThreadPoolExecutor (10 workers) making concurrent calls works correctly

**Session Expiration Scenarios:**
- [ ] API call succeeds when session valid
- [ ] API call triggers re-auth when session expired
- [ ] API call succeeds after re-auth completes
- [ ] Multiple API calls during re-auth wait correctly
- [ ] Re-auth timeout handled correctly (30s wait, 5s lock timeout)

**Client Staleness Race Conditions:**
- [ ] Get client reference → Re-auth happens → Original reference invalidated
- [ ] Cached client in adapter refreshed correctly after re-auth
- [ ] Object identity check works correctly (same vs different client objects)
- [ ] Client refresh before each API call prevents staleness

**Long-Running Operations:**
- [ ] WebSocket subscription handles session expiry mid-operation
- [ ] Batch operations handle session expiry correctly
- [ ] Timeout wrappers work correctly
- [ ] Retry logic works for long operations

#### Edge Cases

**Session Management:**
- [ ] Session expires exactly at TTL boundary
- [ ] Session expires during `get_client()` call
- [ ] Multiple re-auth attempts simultaneously (only one succeeds)
- [ ] Re-auth fails, subsequent calls handle failure correctly
- [ ] Re-auth succeeds but client still invalid (SDK issue)
- [ ] Session created but never used (legacy session handling)

**Concurrent Access:**
- [ ] 100 concurrent API calls with same auth instance
- [ ] Re-auth happens while 50 calls in progress
- [ ] All calls eventually succeed or fail gracefully
- [ ] No deadlocks or infinite waits
- [ ] Lock timeout prevents hanging

**Error Scenarios:**
- [ ] Re-auth fails (invalid credentials)
- [ ] Re-auth times out (network issue)
- [ ] SDK client becomes `None` unexpectedly
- [ ] Session validation throws exception
- [ ] Client refresh throws exception

**Performance:**
- [ ] Session validity check overhead < 5ms
- [ ] Client refresh overhead < 10ms
- [ ] Concurrent calls don't degrade performance significantly
- [ ] Thread safety wrapper overhead (if needed) < 20ms per call

---

### Phase 0: Database Schema Enhancement Tests

#### Unit Tests

**Trade Mode Column (0.1):**
- [ ] Migration script runs successfully (up)
- [ ] Migration script rolls back successfully (down)
- [ ] `trade_mode` column added correctly (nullable)
- [ ] Index created on `trade_mode` column
- [ ] Backfill script populates existing orders correctly
- [ ] New orders have `trade_mode` set correctly
- [ ] Queries filter by `trade_mode` efficiently

**Exit Details (0.2):**
- [ ] Migration script runs successfully
- [ ] All exit columns added correctly (nullable)
- [ ] `mark_closed()` populates exit details correctly
- [ ] Exit details calculated correctly (realized P&L, P&L %)
- [ ] Backfill script populates from Orders table correctly
- [ ] Index on `exit_reason` works correctly
- [ ] Foreign key to `orders` table works correctly

**Portfolio Snapshots (0.3):**
- [ ] Migration script runs successfully
- [ ] `PortfolioSnapshot` model works correctly
- [ ] Repository methods work correctly (create, get_by_date_range, get_latest)
- [ ] Snapshot creation calculates metrics correctly
- [ ] Historical queries are fast (indexed)
- [ ] Upsert works correctly (one record per user per date)

**Targets Table (0.4):**
- [ ] Migration script runs successfully
- [ ] Target records created when sell orders placed
- [ ] Target price updates work correctly
- [ ] Target achievement marking works correctly
- [ ] JSON migration script works correctly

**P&L Calculation Audit (0.5):**
- [ ] Migration script runs successfully
- [ ] Audit records created for each calculation
- [ ] Performance metrics tracked correctly
- [ ] Error messages stored correctly

**Price Cache (0.6):**
- [ ] Migration script runs successfully
- [ ] Cache hit reduces API calls
- [ ] Cache miss fetches from API and stores
- [ ] Cache invalidation works correctly
- [ ] Bulk cache retrieval works correctly

#### Integration Tests

**Data Migration:**
- [ ] All migrations run in sequence successfully
- [ ] Rollback works correctly (reverse order)
- [ ] Data integrity maintained during migration
- [ ] Backfill scripts don't corrupt existing data
- [ ] Migration with existing data works correctly

**Backfill Operations:**
- [ ] Trade mode backfill completes for all orders
- [ ] Exit details backfill completes for all closed positions
- [ ] Portfolio snapshot creation works for historical dates
- [ ] Backfill handles missing data gracefully
- [ ] Backfill can be resumed from last successful date

**Query Performance:**
- [ ] Trade mode filtering is fast (< 100ms for 10K orders)
- [ ] Exit reason queries are fast (< 100ms for 5K positions)
- [ ] Portfolio snapshot queries are fast (< 200ms for 1 year)
- [ ] Indexes used correctly (verify with EXPLAIN)

#### Edge Cases

**Migration Edge Cases:**
- [ ] Migration with empty database
- [ ] Migration with large dataset (100K+ records)
- [ ] Migration rollback with partial data
- [ ] Concurrent migration attempts (should fail gracefully)
- [ ] Migration with corrupted data

**Backfill Edge Cases:**
- [ ] Backfill with missing source data
- [ ] Backfill with duplicate data
- [ ] Backfill with invalid data (nulls, invalid dates)
- [ ] Backfill interrupted and resumed
- [ ] Backfill with date range spanning multiple years

**Data Integrity:**
- [ ] Foreign key constraints work correctly
- [ ] Unique constraints prevent duplicates
- [ ] Nullable columns handle nulls correctly
- [ ] Enum types validate correctly
- [ ] Date ranges validated correctly

---

### Phase 1: Foundation Tests

#### Unit Tests

**Chart Library (1.1):**
- [ ] Recharts installed and configured correctly
- [ ] Chart theme matches application design
- [ ] Chart wrapper components render correctly
- [ ] Chart styling works in dark theme
- [ ] Bundle size within acceptable limits

**PnL Calculation Service (1.2):**
- [ ] Realized P&L calculated correctly from closed positions
- [ ] Unrealized P&L calculated correctly from open positions
- [ ] Fees estimated correctly (0.1% per transaction)
- [ ] Daily aggregation works correctly (one record per user per date)
- [ ] Date range filtering works correctly
- [ ] Trade mode filtering works correctly (paper vs broker)
- [ ] FIFO matching for closed positions works correctly
- [ ] Partial fills handled correctly
- [ ] Missing data handled gracefully

#### Integration Tests

**PnL Calculation Workflow:**
- [ ] Create positions → Close positions → Calculate P&L → Verify accuracy
- [ ] On-demand calculation completes within 5 seconds
- [ ] Historical backfill processes correctly
- [ ] Backfill with large dataset (1 year) completes successfully
- [ ] Backfill can be resumed from last successful date
- [ ] Calculation audit records created correctly

**Data Validation:**
- [ ] Calculated P&L matches manual calculation
- [ ] Realized P&L matches sum of closed position P&L
- [ ] Unrealized P&L updates with current prices
- [ ] Fees calculated correctly for all transactions
- [ ] Daily totals match sum of individual positions

#### Edge Cases

**PnL Calculation Edge Cases:**
- [ ] Empty positions table (no data)
- [ ] Positions with missing exit prices
- [ ] Positions with missing entry prices
- [ ] Positions with zero quantity
- [ ] Positions with negative P&L
- [ ] Positions with very large P&L
- [ ] Multiple positions closed on same day
- [ ] Positions closed across date boundaries
- [ ] Partial fills with different execution prices
- [ ] Manual trades mixed with automated trades
- [ ] Symbol mismatches (normalization issues)
- [ ] Missing price data for unrealized P&L
- [ ] Price API failures during calculation
- [ ] Calculation interrupted and resumed

**Performance Edge Cases:**
- [ ] Calculation with 10,000+ positions
- [ ] Backfill for 2+ years of data
- [ ] Concurrent calculation requests
- [ ] Calculation during high system load

---

### Phase 2: Core Dashboard Enhancement Tests

#### Unit Tests

**P&L Trend Chart (2.1):**
- [ ] Chart renders with valid data
- [ ] Time range selector works (7d, 30d, 90d, 1y)
- [ ] Realized vs unrealized toggle works
- [ ] Tooltip shows correct data
- [ ] Key milestones displayed correctly
- [ ] Empty state handled correctly
- [ ] Error state handled correctly

**Portfolio Value Chart (2.2):**
- [ ] Chart renders with historical data
- [ ] Initial capital line displayed correctly
- [ ] Return percentage calculated correctly
- [ ] Major gain/loss markers displayed
- [ ] Time range selector works
- [ ] Real-time updates work correctly

**Dashboard Metrics (2.3):**
- [ ] Win rate calculated correctly
- [ ] Average profit per trade calculated correctly
- [ ] Best/worst trade identified correctly
- [ ] Metrics update correctly with new data
- [ ] Loading states work correctly

**Broker Trading History (2.4):**
- [ ] FIFO matching algorithm works correctly
- [ ] Statistics calculated correctly (win rate, P&L, etc.)
- [ ] Trade mode filtering works correctly
- [ ] Partial fills handled correctly
- [ ] Symbol normalization works correctly
- [ ] Date range filtering works correctly
- [ ] Pagination works correctly

**Targets Page (2.5):**
- [ ] Targets retrieved correctly (paper trading from JSON)
- [ ] Targets retrieved correctly (broker trading from positions)
- [ ] Target prices calculated correctly (EMA9)
- [ ] Current prices fetched correctly
- [ ] Distance to target calculated correctly

#### Integration Tests

**Chart Data Flow:**
- [ ] P&L data populated → Chart displays correctly
- [ ] Portfolio snapshots created → Chart displays correctly
- [ ] Data updates → Chart updates correctly
- [ ] Time range change → Chart refreshes correctly

**Broker Trading History Workflow:**
- [ ] Orders placed → Positions closed → History calculated correctly
- [ ] FIFO matching produces correct closed positions
- [ ] Statistics match expected values
- [ ] Date filtering works correctly
- [ ] Pagination works for large datasets

**Dashboard Metrics Workflow:**
- [ ] P&L data available → Metrics calculated correctly
- [ ] New trades → Metrics update correctly
- [ ] Multiple users → Metrics isolated correctly

#### Edge Cases

**Chart Edge Cases:**
- [ ] Chart with no data (empty state)
- [ ] Chart with single data point
- [ ] Chart with 10,000+ data points (performance)
- [ ] Chart with missing data points (gaps)
- [ ] Chart with negative values
- [ ] Chart with very large values
- [ ] Chart time range spanning multiple years
- [ ] Chart with timezone issues

**Broker History Edge Cases:**
- [ ] History with no orders
- [ ] History with no closed positions
- [ ] History with partial fills only
- [ ] History with manual trades
- [ ] History with symbol mismatches
- [ ] History with missing execution prices
- [ ] History with duplicate orders
- [ ] History with orders in wrong order (timestamp issues)
- [ ] History with very large dataset (10K+ orders)
- [ ] FIFO matching with complex scenarios (multiple buys, multiple sells)

**Targets Edge Cases:**
- [ ] Targets with no open positions
- [ ] Targets with missing EMA9 data
- [ ] Targets with price API failures
- [ ] Targets with invalid symbols
- [ ] Targets with very old positions

---

### Phase 3: Data Export & Reporting Tests

#### Unit Tests

**CSV Export (3.1):**
- [ ] CSV format is correct (comma-separated, quoted strings)
- [ ] All data fields included correctly
- [ ] Date formatting correct
- [ ] Number formatting correct
- [ ] Special characters escaped correctly
- [ ] Headers included correctly

**PDF Report Generation (3.2):**
- [ ] PDF generates successfully
- [ ] Charts render in PDF correctly
- [ ] Formatting is professional
- [ ] All data included correctly
- [ ] Page breaks work correctly

#### Integration Tests

**Export Workflows:**
- [ ] P&L data → CSV export → Verify data accuracy
- [ ] Trade history → CSV export → Verify completeness
- [ ] Multiple data types → CSV export → All included
- [ ] Large dataset → CSV export → Completes within timeout
- [ ] P&L chart → PDF export → Chart renders correctly
- [ ] Portfolio chart → PDF export → Chart renders correctly

**Export Error Handling:**
- [ ] Export with no data → Error handled gracefully
- [ ] Export timeout → Progress shown, can cancel
- [ ] Export failure → Error message shown, can retry
- [ ] Partial export failure → Partial data exported with warning

#### Edge Cases

**Export Edge Cases:**
- [ ] Export with 100K+ records (performance)
- [ ] Export with special characters in data
- [ ] Export with very long text fields
- [ ] Export with missing data (nulls)
- [ ] Export with date range spanning years
- [ ] Export interrupted and resumed
- [ ] Concurrent export requests
- [ ] Export with corrupted data

**PDF Export Edge Cases:**
- [ ] PDF with no charts (text only)
- [ ] PDF with multiple charts
- [ ] PDF with very long data tables
- [ ] PDF generation timeout
- [ ] PDF with missing images (chart rendering fails)

---

### Phase 4: Advanced Analytics Tests

#### Unit Tests

**Performance Analytics (4.1):**
- [ ] Win rate calculated correctly
- [ ] Profit/loss distribution calculated correctly
- [ ] Trade duration calculated correctly
- [ ] Best/worst trades identified correctly
- [ ] Strategy performance breakdown calculated correctly
- [ ] Date range filtering works correctly

**Risk Metrics (4.2):**
- [ ] Sharpe ratio calculated correctly
- [ ] Maximum drawdown calculated correctly
- [ ] Volatility metrics calculated correctly
- [ ] Risk-reward ratio calculated correctly
- [ ] Position concentration calculated correctly

#### Integration Tests

**Analytics Workflow:**
- [ ] P&L data available → Analytics calculated correctly
- [ ] Trade history available → Analytics calculated correctly
- [ ] Date range change → Analytics recalculated correctly
- [ ] New trades → Analytics updated correctly
- [ ] Analytics cache works correctly (if implemented)

**Analytics API:**
- [ ] All analytics endpoints return correct data
- [ ] Date range filtering works correctly
- [ ] Strategy filtering works correctly
- [ ] Response time acceptable (< 3 seconds)

#### Edge Cases

**Analytics Edge Cases:**
- [ ] Analytics with no trades (empty state)
- [ ] Analytics with single trade
- [ ] Analytics with all winning trades
- [ ] Analytics with all losing trades
- [ ] Analytics with very large P&L values
- [ ] Analytics with missing data
- [ ] Analytics calculation timeout
- [ ] Analytics with invalid date ranges

**Risk Metrics Edge Cases:**
- [ ] Risk metrics with insufficient data (< 30 days)
- [ ] Risk metrics with zero volatility
- [ ] Risk metrics with negative returns
- [ ] Risk metrics with extreme values

---

### Phase 5: Watchlist Tests

#### Unit Tests

**Watchlist API (5.1):**
- [ ] Create watchlist works correctly
- [ ] Add stock to watchlist works correctly
- [ ] Remove stock from watchlist works correctly
- [ ] Delete watchlist works correctly
- [ ] Multiple watchlists per user work correctly
- [ ] Watchlist persistence works correctly

**Watchlist Widget (5.2):**
- [ ] Widget displays watchlist stocks correctly
- [ ] Current prices displayed correctly
- [ ] Price changes color-coded correctly
- [ ] Quick links work correctly

#### Integration Tests

**Watchlist Workflow:**
- [ ] Create watchlist → Add stocks → View on dashboard
- [ ] Watchlist persists across sessions
- [ ] Multiple watchlists work correctly
- [ ] Watchlist widget updates correctly

#### Edge Cases

**Watchlist Edge Cases:**
- [ ] Watchlist with no stocks (empty state)
- [ ] Watchlist with invalid symbols
- [ ] Watchlist with duplicate stocks
- [ ] Watchlist with very large number of stocks (100+)
- [ ] Watchlist with missing price data
- [ ] Watchlist deletion with active widget

---

### Phase 6: UX Polish Tests

#### Unit Tests

**Filter Persistence (6.1):**
- [ ] Filter presets saved correctly
- [ ] Filter presets loaded correctly
- [ ] Column preferences saved correctly
- [ ] Date range preferences saved correctly
- [ ] Multiple presets work correctly

#### Integration Tests

**Filter Persistence Workflow:**
- [ ] Set filters → Save preset → Reload page → Filters restored
- [ ] Change column order → Save → Reload → Order restored
- [ ] Set date range → Save → Reload → Range restored

#### Edge Cases

**Filter Persistence Edge Cases:**
- [ ] Filter preset with invalid data
- [ ] Filter preset with missing fields
- [ ] Multiple users with same preset names
- [ ] Very large filter presets
- [ ] Filter preset corruption

---

### Cross-Phase Integration Tests

**End-to-End Workflows:**
- [ ] Create position → Close position → Calculate P&L → Display chart → Export CSV
- [ ] Place order → Order executes → Position created → P&L updated → Dashboard metrics updated
- [ ] Broker trade → History calculated → Analytics updated → Export PDF
- [ ] Watchlist created → Stock added → Price updated → Widget displays

**Error Recovery:**
- [ ] P&L calculation fails → Error shown → Retry succeeds
- [ ] Chart rendering fails → Error shown → Retry succeeds
- [ ] Export fails → Error shown → Retry succeeds
- [ ] API timeout → Progress shown → Can cancel → Retry succeeds

**Performance Under Load:**
- [ ] 10 concurrent users → All features work correctly
- [ ] 50 concurrent users → Performance acceptable
- [ ] 100 concurrent users → No crashes, graceful degradation

---

### Performance Tests

**Chart Rendering:**
- [ ] 100 data points: < 0.5 seconds
- [ ] 1,000 data points: < 1 second
- [ ] 5,000 data points: < 2 seconds
- [ ] 10,000 data points: < 5 seconds

**Data Export:**
- [ ] 1,000 records: < 2 seconds
- [ ] 10,000 records: < 5 seconds
- [ ] 50,000 records: < 15 seconds
- [ ] 100,000 records: < 30 seconds

**Dashboard Load:**
- [ ] Initial load: < 2 seconds
- [ ] With cached data: < 1 second
- [ ] With fresh data: < 3 seconds

**Analytics Calculation:**
- [ ] 30 days data: < 1 second
- [ ] 90 days data: < 2 seconds
- [ ] 1 year data: < 5 seconds

**PnL Calculation:**
- [ ] 100 positions: < 1 second
- [ ] 1,000 positions: < 3 seconds
- [ ] 5,000 positions: < 10 seconds

**Backfill Performance:**
- [ ] 1 month: < 1 minute
- [ ] 6 months: < 5 minutes
- [ ] 1 year: < 10 minutes

**Broker History:**
- [ ] 1,000 orders: < 2 seconds
- [ ] 5,000 orders: < 5 seconds
- [ ] 10,000 orders: < 10 seconds

**Concurrent Load:**
- [ ] 10 users: All requests < 2 seconds
- [ ] 50 users: 95% requests < 3 seconds
- [ ] 100 users: 90% requests < 5 seconds

---

### Test Coverage Requirements

**Code Coverage:**
- [ ] Phase -1: 95%+ coverage for authentication code
- [ ] Phase 0: 90%+ coverage for migration scripts
- [ ] Phase 1: 90%+ coverage for PnL calculation service
- [ ] Phase 2: 85%+ coverage for chart components
- [ ] Phase 3: 85%+ coverage for export services
- [ ] Phase 4: 85%+ coverage for analytics services
- [ ] Phase 5: 85%+ coverage for watchlist features
- [ ] Phase 6: 80%+ coverage for UX features

**Test Types:**
- [ ] Unit tests: 70%+ of test suite
- [ ] Integration tests: 20%+ of test suite
- [ ] E2E tests: 10%+ of test suite

**Critical Path Tests:**
- [ ] All critical path features have 95%+ coverage
- [ ] All authentication code has 95%+ coverage
- [ ] All P&L calculation code has 95%+ coverage
- [ ] All FIFO matching code has 95%+ coverage

---

## 📊 Success Metrics

### User Engagement
- Dashboard page views increase by 30%
- Average session time increases by 20%
- Export feature usage > 50% of active users
- Analytics page views > 40% of active users

### Performance
- Dashboard loads in < 2 seconds
- Charts render in < 1 second
- Export completes in < 5 seconds for typical datasets
- Analytics page loads in < 3 seconds

### Quality
- Zero critical bugs in production
- < 1% error rate on new features
- 95%+ test coverage for new code
- All acceptance criteria met

### Data Quality
- P&L calculation accuracy: 99.9%
- Chart data freshness: < 5 minutes old
- Export data completeness: 100%

### Error Rates
- P&L calculation failure rate: < 1%
- Chart rendering errors: < 0.5%
- Export failures: < 2%
- Analytics calculation errors: < 1%

---

## ⚠️ Risk Mitigation & Error Handling

### Critical Risks

#### 1. PnL Calculation Accuracy
**Risk:** Incorrect P&L calculations lead to wrong financial data
**Mitigation:**
- Create data validation script to compare calculated vs. manual P&L
- Add unit tests with known expected values
- Implement audit trail for all calculations
- Add manual verification step before production release
- **Error Handling:**
  - If calculation fails: Show error message, allow retry
  - If data inconsistent: Log warning, show partial results
  - If validation fails: Block calculation, show detailed error

#### 2. Performance with Large Datasets
**Risk:** Charts/exports slow or timeout with large datasets
**Mitigation:**
- Implement pagination for charts (show last N days by default)
- Add data aggregation for dashboard metrics
- Use server-side processing for exports
- Add progress indicators for long operations
- **Error Handling:**
  - If timeout: Show progress, allow cancellation
  - If too slow: Suggest date range reduction
  - If memory issue: Process in batches

#### 3. Broker Trading History FIFO Matching
**Risk:** Incorrect matching leads to wrong trade history
**Mitigation:**
- Write unit tests first (TDD approach)
- Test with known edge cases (partial fills, manual trades)
- Add data validation to compare matched vs. expected
- **Error Handling:**
  - If matching fails: Show error, allow manual review
  - If data inconsistent: Flag for manual review
  - If performance issue: Process in smaller batches

#### 4. Data Migration & Backfill
**Risk:** Backfilling historical data fails or is slow
**Mitigation:**
- Implement incremental backfill (process in batches)
- Add progress tracking and resumable backfill
- Add date range limits (max 1 year at a time)
- **Error Handling:**
  - If backfill fails: Show error, allow retry from last successful date
  - If partial failure: Continue from last successful date
  - If timeout: Process in smaller date ranges

### Error Handling Scenarios

#### PnL Calculation Errors
- **Scenario:** Calculation fails due to missing data
  - **Action:** Show error message with details, allow retry
  - **UI:** Display error banner with "Retry" button
- **Scenario:** Calculation takes too long (> 10 seconds)
  - **Action:** Show progress indicator, allow cancellation
  - **UI:** Progress bar with cancel button
- **Scenario:** Calculated P&L doesn't match expected
  - **Action:** Log warning, show validation report
  - **UI:** Warning message with "View Details" link

#### Chart Rendering Errors
- **Scenario:** No data available for chart
  - **Action:** Show empty state with helpful message
  - **UI:** Empty state component with "Calculate P&L" button
- **Scenario:** Chart data unavailable (API error)
  - **Action:** Show error message, allow retry
  - **UI:** Error message with retry button
- **Scenario:** Chart rendering fails (too much data)
  - **Action:** Suggest date range reduction
  - **UI:** Error message with "Reduce Date Range" button

#### Export Errors
- **Scenario:** Export timeout (> 30 seconds)
  - **Action:** Show progress, allow cancellation, suggest smaller date range
  - **UI:** Progress indicator with cancel button
- **Scenario:** Export fails (server error)
  - **Action:** Show error message, allow retry
  - **UI:** Error message with retry button
- **Scenario:** Export data incomplete
  - **Action:** Show warning, allow partial export
  - **UI:** Warning message with "Export Partial Data" option

#### Analytics Calculation Errors
- **Scenario:** Analytics calculation fails
  - **Action:** Show error message, allow retry
  - **UI:** Error banner with retry button
- **Scenario:** Analytics calculation slow (> 5 seconds)
  - **Action:** Show loading state, allow cancellation
  - **UI:** Loading spinner with cancel option
- **Scenario:** Partial data available
  - **Action:** Show partial results with warning
  - **UI:** Warning message with partial results

### Performance Monitoring

**Metrics to Track:**
- P&L calculation time (target: < 5 seconds)
- Chart rendering time (target: < 1 second for 1000 points)
- Export completion time (target: < 5 seconds for 10K records)
- Analytics page load time (target: < 3 seconds)
- Error rates (target: < 1% for calculations, < 0.5% for charts)

**Alerts:**
- P&L calculation failures > 5%
- Chart rendering errors > 1%
- Export timeouts > 2%
- Analytics page load > 5 seconds

---

## 🚀 Deployment Plan

### Pre-Release
1. **Critical infrastructure fixes applied** (Kotak authentication fixes from Phase -1)
2. **Database migrations applied** (high-priority schema enhancements)
3. **Data backfill completed** (trade_mode, exit_details, portfolio snapshots)
4. Complete all features
5. Full test suite passes
6. Code review completed
7. Documentation updated
8. Performance benchmarks met
9. Security review completed
10. **Authentication stability verified** (re-auth failures < 0.1%)

### Release
1. Deploy to staging environment
2. Smoke testing
3. User acceptance testing (if applicable)
4. Deploy to production
5. Monitor for issues

### Post-Release
1. Monitor error rates
2. Collect user feedback
3. Track usage metrics
4. Plan hotfixes if needed

---

## 📝 Documentation Updates

- [ ] Update user guide with new features
- [ ] Add API documentation for new endpoints
- [ ] Update dashboard screenshots
- [ ] Create feature documentation for:
  - Chart usage guide
  - Export functionality guide
  - Analytics page guide
  - Watchlist management guide
- [ ] Update changelog
- [ ] Create release notes

---

## 🔄 Rollback Plan

If critical issues are found:
1. Revert to version 26.1.0
2. Investigate issues
3. Fix and re-test
4. Re-deploy

---

## 📋 Dependencies & Prerequisites

### New Dependencies Required

**Frontend:**
- `recharts` - Chart library for React

**Backend:**
- `reportlab` or `weasyprint` - PDF generation (for Phase 3.2)
- `Pillow` - Image processing for chart-to-PDF conversion (if needed)

### Database Migrations

**High Priority (Must Have):**
- Trade Mode column in Orders table (Phase 2.4: Broker Trading History)
- Exit Details in Positions table (Phase 2.4, 4.1: Analytics)
- Portfolio Snapshots table (Phase 2.2: Portfolio Value Chart)

**Medium Priority (Should Have):**
- Targets table (Phase 2.5: Targets Page)
- P&L Calculation Audit table (Phase 1.2: PnL Service)
- Historical Price Cache table (Phase 2.2: Performance)

**Low Priority (Nice to Have):**
- Export Job Tracking table (Phase 3.1: CSV Export)
- Analytics Cache table (Phase 4.1: Performance Analytics)
- Watchlist tables (Phase 5.1)

**📄 Detailed Schema Design:** See [`RELEASE_PLAN_V26.1.1_DB_SCHEMA_ENHANCEMENTS.md`](./RELEASE_PLAN_V26.1.1_DB_SCHEMA_ENHANCEMENTS.md)
**📄 Migration Scripts:** See [`RELEASE_PLAN_V26.1.1_DB_MIGRATIONS.md`](./RELEASE_PLAN_V26.1.1_DB_MIGRATIONS.md)

### API Endpoints to Create
- Historical portfolio data endpoint
- Metrics endpoints (win rate, average profit, best/worst trades)
- P&L calculation endpoints (`POST /api/v1/user/pnl/calculate`, `POST /api/v1/user/pnl/backfill`)
- Targets endpoint (`GET /api/v1/user/targets` - implement existing placeholder)
- Broker trading history endpoint (`/api/v1/user/broker/history`)
- Export endpoints (CSV for various data types)
- PDF report generation endpoint
- Analytics endpoints
- Risk metrics endpoints
- Watchlist CRUD endpoints

### Infrastructure Considerations

**Background Jobs (Optional for v26.1.1):**
- P&L calculation can be on-demand initially
- Scheduled EOD calculation can be added in future release
- If implementing scheduled jobs, consider:
  - Job queue system (Celery, RQ, or simple cron)
  - Job monitoring and error handling
  - Retry mechanism for failed jobs

**Caching Strategy:**
- Cache current prices for unrealized P&L (reduce API calls)
- Cache dashboard metrics (update every 5 minutes)
- Cache analytics calculations (update daily)
- Consider Redis for distributed caching (if multi-instance deployment)

**Rate Limiting:**
- Price API calls (yfinance/broker API) - implement rate limiting
- Chart data requests - consider caching
- Export requests - limit concurrent exports

**Monitoring:**
- Track P&L calculation performance
- Monitor chart rendering errors
- Track export success/failure rates
- Monitor API rate limit usage

---

## 🎯 Future Considerations (Not in v26.1.1)

### UI/UX Features
- WebSocket real-time updates for charts
- Advanced portfolio analytics
- Social features
- Mobile app
- Price alerts for watchlist
- Email delivery for PDF reports

### Infrastructure & Backend
- **Unified DB-Only Storage**: Migrate from hybrid storage (paper=file, real=DB) to unified DB-only approach
  - 📄 **Implementation Plan**: [`../kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md`](../kotak_neo_trader/UNIFIED_DB_IMPLEMENTATION_COMPLETE.md)
  - **Timeline**: 6-8 weeks
  - **Benefits**: Single codebase, consistency, unified reporting, data integrity
  - **Status**: Planning phase
- **Order-Position Reconciliation Job**: Background job to reconcile ONGOING orders for closed positions
  - **Purpose**: Catch any missed order closures when positions are closed (edge case handling)
  - **Implementation**: Periodic job that queries for closed positions with ONGOING buy orders and updates them to CLOSED
  - **Frequency**: Run daily (e.g., during EOD cleanup) or on-demand
  - **Benefits**: Ensures data consistency, handles edge cases where order closure fails after position closure
  - **Timeline**: 1-2 days
  - **Status**: Future improvement
  - **Related Issue**: Fixed in current release - positions now close buy orders, but this provides additional safety net
- Advanced order management
- Multi-broker support

---

## 📋 Implementation Checklist

### Development
- [ ] Critical infrastructure fixes implemented (Phase -1)
- [ ] All features implemented
- [ ] Code reviewed
- [ ] Tests written and passing
- [ ] Performance optimized
- [ ] Security reviewed
- [ ] Accessibility checked

### Testing
- [ ] Authentication session management tests complete (Phase -1)
- [ ] Concurrent API call tests complete (Phase -1)
- [ ] Unit tests complete
- [ ] Integration tests complete
- [ ] E2E tests complete
- [ ] Manual testing complete
- [ ] Mobile testing complete
- [ ] Performance testing complete

### Documentation
- [ ] User guide updated
- [ ] API docs updated
- [ ] Changelog updated
- [ ] Release notes prepared
- [ ] Feature documentation created

### Deployment
- [ ] Authentication fixes verified in staging (Phase -1)
- [ ] Staging deployment successful
- [ ] Production deployment plan ready
- [ ] Rollback plan ready
- [ ] Monitoring configured
- [ ] Database migrations tested
- [ ] Authentication monitoring configured (re-auth frequency tracking)

---

## 👥 Team Assignments (if applicable)

- **Frontend Development:** Charts, Export UI, Analytics Page, Watchlist UI
- **Backend Development:** APIs, Export logic, Analytics calculations, Watchlist backend
- **Testing:** All test types
- **DevOps:** Deployment, Monitoring
- **Documentation:** User guides, API docs

---

## 📞 Support & Feedback

- Create GitHub issues for bugs
- Feature requests via GitHub discussions
- User feedback collection mechanism

---

**Last Updated:** 2025-12-22
**Next Review:** Weekly during development
**Review Status:** ✅ Updated based on comprehensive review (see RELEASE_PLAN_V26.1.1_REVIEW.md)

### Key Updates from Review:
- ✅ Extended timeline to 9-10 weeks (added 1-2 week buffer + Phase -1)
- ✅ Added Phase -1: Critical Infrastructure Fixes (Kotak Authentication & Session Management)
- ✅ Prioritized PnL Service (Phase 1.2) - marked as critical blocker
- ✅ Updated Broker Trading History estimate (5-7 days, broken into phases)
- ✅ Added comprehensive risk mitigation section
- ✅ Enhanced testing requirements (edge cases, performance, validation)
- ✅ Added error handling scenarios
- ✅ Added phased release option (v26.1.1a + v26.1.1b)
- ✅ Enhanced success metrics (data quality, error rates, authentication stability)
