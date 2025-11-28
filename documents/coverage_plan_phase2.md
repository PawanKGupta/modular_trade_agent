# Coverage Improvement Plan (Phase 2)

## Current Snapshot
- `trade_agent.py`: ✅ 100% statement coverage after new regression suite.
- `server/app/core/crypto.py`: 40% (easy surface, pure functions).
- `server/app/core/security.py`: 30% (JWT helpers, needs auth-focused tests).
- `server/app/core/deps.py`: 43% (FastAPI dependency wrappers).

These three lightweight core modules are the quickest wins to keep momentum while we design broader integration coverage for routers later.

## Immediate Target — `server/app/core/crypto.py`
| Scenario | Test Idea | Notes |
| --- | --- | --- |
| `BROKER_SECRET_KEY` present | patch `os.environ` to ensure `_get_or_create_key` returns exact key | validates highest-priority branch |
| Fallback to `JWT_SECRET` | ensure derived key length is 44 chars (urlsafe base64) | covers secondary branch |
| Default dev secret | clear envs and assert deterministic derived key | ensures final branch |
| `encrypt_blob` / `decrypt_blob` happy path | encrypt sample bytes and assert decrypt returns original | uses real Fernet |
| `decrypt_blob` invalid token | feed junk bytes, expect `None` | covers InvalidToken guard |

## Validation Checklist
1. `pytest tests/unit/server/core/test_crypto.py -q`
2. `pytest tests/unit/trade_agent/test_trade_agent.py -q` (regression guard for recent changes)
3. `pytest --maxfail=1 --disable-warnings -q` when batching multiple modules.
4. `pytest tests/unit/server/core/test_crypto.py --cov=server/app/core/crypto.py --cov-report term` to confirm ≥90%.

## Next Modules (after crypto.py)
1. `server/app/core/security.py`: mock `datetime` and env secrets to cover token helpers.
2. `server/app/core/deps.py`: use FastAPI `Depends` stubs + dummy user context to validate dependency wrappers.

Each module will only be considered “done” when:
- Targeted unit tests cover every branch listed above.
- Validation checklist passes locally.
- Coverage report shows ≥90% for the module (captured in PR description).
