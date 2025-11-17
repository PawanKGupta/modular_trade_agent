# Re-authentication Bug Reproduction Tests

These tests reproduce and verify the fix for the stale client re-authentication bug.

## Bug Description

**Production Issue:**
- Login succeeds at 09:15:06
- JWT token expires quickly (13 seconds later at 09:15:19)
- Re-authentication fails with: `'NoneType' object has no attribute 'get'`

**Root Cause:**
- `force_relogin()` was reusing stale/expired client instances
- Stale clients cause SDK internal errors during 2FA

**Fix:**
- `force_relogin()` now always creates a fresh client instance
- Prevents stale client reuse

## Test Scripts

### 1. `reproduce_production_bug.py`
**Purpose:** Reproduces the exact production scenario

**What it tests:**
- Initial login
- Re-authentication behavior
- Verifies new client is created (not reused)
- API calls after re-auth

**Run:**
```bash
python tests/integration/reproduce_production_bug.py
```

### 2. `test_reauth_real_api.py`
**Purpose:** Comprehensive real API tests

**What it tests:**
- Basic re-authentication flow
- Re-auth after JWT expiry
- Concurrent re-authentication scenario
- Multiple components sharing same auth session

**Run:**
```bash
python tests/integration/test_reauth_real_api.py
```

## Prerequisites

1. Valid Kotak Neo credentials in `modules/kotak_neo_auto_trader/kotak_neo.env`:
   ```
   KOTAK_CONSUMER_KEY=your_key
   KOTAK_CONSUMER_SECRET=your_secret
   KOTAK_MOBILE_NUMBER=your_mobile
   KOTAK_PASSWORD=your_password
   KOTAK_MPIN=your_mpin
   KOTAK_ENVIRONMENT=sandbox  # or prod
   ```

2. Python dependencies installed:
   ```bash
   pip install neo-api-client python-dotenv
   ```

## What to Verify

When running these tests, verify:

1. **New Client Creation:**
   - Client ID before re-auth ≠ Client ID after re-auth
   - This confirms fresh client is created

2. **Re-authentication Success:**
   - `force_relogin()` returns `True`
   - No exceptions raised
   - No `'NoneType' object has no attribute 'get'` errors

3. **API Calls Work:**
   - API calls succeed after re-auth
   - No JWT expiry errors

## Expected Output

```
================================================================================
REPRODUCING PRODUCTION RE-AUTHENTICATION BUG SCENARIO
================================================================================

[09:15:06] Step 1: Initial login...
✓ Login completed successfully!
  Initial client ID: 140234567890

[09:15:19] Step 4: Simulating JWT expiry scenario...
  Calling force_relogin()...
  State after re-auth:
    Result: ✓ Success
    Client ID: 140234567891  # Different ID = new client created
    Is logged in: True

  ✓ VERIFICATION PASSED: New client created
    Old client ID: 140234567890
    New client ID: 140234567891

[09:15:19] Step 5: Verifying API calls after re-auth...
✓ API call successful after re-auth

================================================================================
PRODUCTION SCENARIO TEST SUMMARY
================================================================================
✓ Initial login successful
✓ Re-authentication successful
✓ New client created (not reused)
✓ API calls work after re-auth
================================================================================
```

## Troubleshooting

**If tests fail:**

1. **Login fails:**
   - Check credentials in `kotak_neo.env`
   - Verify environment (sandbox vs prod)
   - Check network connectivity

2. **Re-auth fails:**
   - Check if MPIN is correct
   - Verify 2FA is enabled
   - Check API status

3. **Same client reused:**
   - This indicates the fix may not be applied
   - Verify `force_relogin()` sets `self.client = None` before creating new client

## Notes

- These tests use **REAL API calls** (no mocking)
- They may take time to complete (API calls are slow)
- They require valid credentials and network access
- They verify the fix works in production-like scenarios

