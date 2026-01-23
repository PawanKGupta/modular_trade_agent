# Broker Session Expiry Testing Guide

This guide explains how to test broker session expiration and re-authentication.

## Methods to Test Session Expiration

### Method 1: Clear Session via API (Recommended)

Use the provided script to clear the broker session:

```bash
# Get your JWT token first (see below)
python scripts/clear_broker_session.py
```

Or set the token as environment variable:
```bash
export JWT_TOKEN="your_token_here"
python scripts/clear_broker_session.py
```

**How to get JWT token:**
1. Open browser DevTools (F12)
2. Go to Application → Local Storage
3. Find `ta_access_token` key
4. Copy the token value

Or in browser console:
```javascript
localStorage.getItem('ta_access_token')
```

### Method 2: Clear Session via Browser Console

You can also clear the session directly via API call from browser console:

```javascript
// Get your token
const token = localStorage.getItem('ta_access_token');

// Clear broker session
fetch('http://localhost:8000/api/v1/user/broker/session/clear', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})
.then(r => r.json())
.then(data => console.log('Session cleared:', data))
.catch(err => console.error('Error:', err));
```

### Method 3: Wait for Natural Expiration

Broker sessions expire naturally after approximately **1 hour** of inactivity. However, this is not practical for testing.

### Method 4: Simulate Stale Session (Advanced)

You can manually set the session to a stale state by modifying the session timestamp in the code (for development only).

## Testing Scenarios

### Scenario 1: Test Portfolio Page After Session Expiry

1. **Clear the session:**
   ```bash
   python scripts/clear_broker_session.py
   ```

2. **Open broker portfolio page** in browser:
   - Navigate to `/dashboard/broker-portfolio`
   - The page should detect stale session
   - Should automatically re-authenticate
   - Check browser console and server logs for re-auth messages

3. **Expected behavior:**
   - Session is detected as stale (`is_authenticated=True` but `client=None`)
   - Session is cleared and new session is created
   - Portfolio data loads successfully after re-auth

### Scenario 2: Test Orders Page After Session Expiry

1. **Clear the session:**
   ```bash
   python scripts/clear_broker_session.py
   ```

2. **Open broker orders page** in browser:
   - Navigate to `/dashboard/broker-orders`
   - Should automatically re-authenticate
   - Check logs for re-auth flow

3. **Expected behavior:**
   - Same as portfolio page
   - Orders should load after successful re-auth

### Scenario 3: Test API Endpoints Directly

You can test the endpoints directly using curl or Postman:

```bash
# Get JWT token (from browser localStorage)
TOKEN="your_jwt_token_here"

# Clear session
curl -X POST http://localhost:8000/api/v1/user/broker/session/clear \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Try to get portfolio (should trigger re-auth)
curl http://localhost:8000/api/v1/user/broker/portfolio \
  -H "Authorization: Bearer $TOKEN"

# Try to get orders (should trigger re-auth)
curl http://localhost:8000/api/v1/user/broker/orders \
  -H "Authorization: Bearer $TOKEN"
```

## What to Check in Logs

When testing session expiration, look for these log messages:

### Successful Re-authentication:
```
[BROKER_PORTFOLIO] Stale session detected for user X: is_authenticated=True but client is None
[BROKER_PORTFOLIO] Cleared stale session for user X, creating new session
[SHARED_SESSION] Creating new session for user X
[BROKER_PORTFOLIO] Re-authentication successful for user X
```

### Session State Logs:
```
[BROKER_PORTFOLIO] Session state for user X: is_authenticated=True, client=None
[BROKER_PORTFOLIO] Updated session state for user X: is_authenticated=True, client=available
```

### Error Cases:
```
[BROKER_PORTFOLIO] Re-authentication failed for user X
```

## Troubleshooting

### Session Not Clearing

If the session doesn't clear:
1. Check if you're using the correct user ID
2. Verify the JWT token is valid
3. Check server logs for errors
4. Try restarting the server

### Re-authentication Fails

If re-authentication fails:
1. Check broker credentials are correct
2. Verify broker API is accessible
3. Check for rate limiting (too many login attempts)
4. Look for specific error messages in logs

### Session Still Valid After Clearing

If session appears valid after clearing:
1. Check if another service is recreating the session
2. Verify the clear endpoint is working (check response)
3. Check shared session manager logs

## Quick Test Script

Here's a quick test to verify session expiry handling:

```python
#!/usr/bin/env python3
"""Quick test for broker session expiry."""
import requests
import time

API_URL = "http://localhost:8000"
TOKEN = "your_jwt_token_here"  # Get from browser localStorage

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 1. Clear session
print("1. Clearing broker session...")
response = requests.post(
    f"{API_URL}/api/v1/user/broker/session/clear",
    headers=headers
)
print(f"   Status: {response.status_code}")
print(f"   Response: {response.json()}")

# 2. Wait a moment
time.sleep(1)

# 3. Try to get portfolio (should trigger re-auth)
print("\n2. Fetching portfolio (should trigger re-auth)...")
response = requests.get(
    f"{API_URL}/api/v1/user/broker/portfolio",
    headers=headers
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Holdings count: {len(data.get('holdings', []))}")
else:
    print(f"   Error: {response.text}")

# 4. Try to get orders (should use same re-authenticated session)
print("\n3. Fetching orders (should use existing session)...")
response = requests.get(
    f"{API_URL}/api/v1/user/broker/orders",
    headers=headers
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Orders count: {len(data)}")
else:
    print(f"   Error: {response.text}")
```

## Notes

- Broker sessions are separate from JWT authentication
- JWT tokens expire independently (typically at end of trading day)
- Broker sessions expire after ~1 hour of inactivity
- The system automatically re-authenticates when stale sessions are detected
- Re-authentication happens transparently to the user (no manual action needed)
