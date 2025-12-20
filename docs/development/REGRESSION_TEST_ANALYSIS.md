# Regression Test Failure Analysis

## Summary
All 3 failing tests are **TEST ISSUES**, not bugs in the implementation.

## Test 1: `test_concurrent_reauth_coordination`
**Status:** TEST ISSUE

**Problem:** The test simulates re-auth logic with its own lock/event instead of using the actual `_attempt_reauth_thread_safe()` function. The test doesn't match the actual implementation behavior.

**Root Cause:**
- Test creates its own `threading.Lock()` and `threading.Event()`
- Actual implementation uses per-auth-object locks via `_get_reauth_lock(auth)` which uses `id(auth)` to get unique locks per auth object
- Test should call the actual `_attempt_reauth_thread_safe()` function with mock auth objects

**Fix:** Update test to use actual `_attempt_reauth_thread_safe()` function with properly mocked auth objects.

---

## Test 2: `test_verify_order_placement_rejected`
**Status:** TEST ISSUE

**Problem:** Test patches `send_telegram` but implementation now uses `telegram_notifier.notify_order_rejection()` first.

**Root Cause:**
- Implementation code (line 2487-2505 in `auto_trade_engine.py`) checks `if self.telegram_notifier and self.telegram_notifier.enabled:` first
- Only falls back to `send_telegram()` if telegram_notifier is not available or disabled
- Test mocks `send_telegram` but doesn't mock `telegram_notifier`, so the new code path is taken but not tested

**Fix:** Update test to mock `auto_trade_engine.telegram_notifier` instead of (or in addition to) `send_telegram`.

---

## Test 3: `test_get_broker_portfolio_success`
**Status:** TEST ISSUE

**Problem:** Test mocks `get_account_limits()` with wrong structure - returns nested dict but code expects flat structure.

**Root Cause:**
- Test mocks: `{"available_margin": {"cash": 100000.0}}`
- Implementation code (line 591-593 in `broker.py`) expects: `account_limits.get("available_cash")` or `account_limits.get("net")`
- Code expects `available_cash` or `net` keys directly, not nested under `available_margin`
- Also expects `Money` objects, not plain floats

**Fix:** Update test mock to return: `{"available_cash": Money(Decimal("100000.0"))}` or `{"net": Money(Decimal("100000.0"))}`

---

## Conclusion
All failures are due to tests not matching the current implementation. The implementation code is correct. Tests need to be updated to match the current code paths.
