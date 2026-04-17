# Kotak Neo Auth/Reauth (REST-Only)

## Overview

The project uses REST-only authentication for Kotak Neo.

- Login step 1: `tradeApiLogin` with TOTP
- Login step 2: `tradeApiValidate` with MPIN
- Session material persisted in memory:
  - `baseUrl`
  - `session token` (`Auth`)
  - `session sid` (`Sid`)

## Re-auth Behavior

- `get_client()` checks TTL (`session_created_at` + `session_ttl`)
- If expired, it triggers `force_relogin()` (thread-safe lock)
- Re-auth re-runs the REST login flow and refreshes the REST client
- On re-auth failure, session fields are cleared

## Error Handling

- Network/connectivity errors are classified separately from service-unavailable errors
- Auth errors (`JWT expired`, missing/invalid session) trigger re-auth path
- Re-auth failure rate is tracked by `auth_handler` helpers to avoid loops

## Current Constraints

- No SDK or SDK fallback paths exist
- No private SDK-era methods are used (`_initialize_client`, `_perform_login`, `_complete_2fa`)
- Adapter integration is through `KotakRestClient` only

