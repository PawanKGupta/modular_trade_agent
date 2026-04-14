# Kotak Auth Session Reuse Analysis (REST-Only)

## Current Model

- Shared session per user managed by `SharedSessionManager`.
- Auth state is represented by:
  - `session_token` (`Auth`)
  - `trade_sid` (`Sid`)
  - `base_url`
  - `session_created_at`
- TTL-based validation triggers refresh before expiry.

## Reuse Semantics

- Reuse is allowed only while `is_session_valid()` is true.
- On expiry or invalid state:
  - session is cleared
  - fresh REST login is performed
  - `KotakRestClient` is rebuilt

## Concurrency

- `KotakNeoAuth` uses lock-protected client retrieval and relogin.
- `SharedSessionManager` uses per-user locks to avoid duplicate relogins.

## Outcome

- Session reuse remains efficient and safe under concurrent access.
- No SDK-era client lifecycle concerns remain in the current architecture.

