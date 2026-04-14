# Release Plan v26.1.1 (REST-Only Update)

## Scope

- Kotak broker integration is REST-only.
- Removed all SDK-era implementation paths and private helper usage.
- Re-auth path uses `tradeApiLogin` + `tradeApiValidate` exclusively.

## Key Deliverables

1. REST authentication and reauthentication hardening.
2. REST-only broker adapter for orders, holdings, limits, and reports.
3. Cleanup of tests/dev-tests/docs/CI references to SDK-era flow.
4. Validation of modify-order mapping with token fallback logic.

## Risks and Mitigations

- **Session expiry during concurrent calls**
  - Mitigation: lock-protected `force_relogin()` and TTL checks.
- **Incomplete API field payloads**
  - Mitigation: robust response parsing and fallback mappings.
- **Legacy test drift**
  - Mitigation: replace legacy tests with REST-focused tests.

## Verification Checklist

- [x] Runtime modules no longer import/use SDK client.
- [x] Auth flow uses REST endpoints only.
- [x] Broker adapter path is REST-only.
- [x] CI/Docker no longer install SDK package.
- [x] Dev tests updated to REST-only behavior.

