# Release Plan v26.2.3

**Branch:** `releases/rebound_2623`
**Version:** 26.2.3 (CalVer Q2 2026 patch)
**Status:** Ready for tag and deploy after checklist below
**Release notes:** Full branch scope — see [CHANGELOG.md](../../CHANGELOG.md) `[26.2.3]`

---

## Scope

Major themes on this branch (since `26.2.2.1`):

| Theme | Operator impact |
|-------|-----------------|
| ML leakage fixes (Phase 0) | Forward-looking feature removal, calibration fix, train/serve skew fix; threshold raised 0.5 → 0.6 |
| ML model persistence (Docker) | New `trading_models` named volume; activated models survive restarts/rebuilds |
| ML activate-and-deploy | Activating a model via UI immediately copies artifact to canonical runtime path |
| Register external model | New endpoint + UI form to import externally-trained `.pkl` files |
| FinBERT India overrides | Hard negative score for promoter pledge, SEBI notice, ED/CBI raids, F&O ban, NPA, etc. |
| Stale signal expiry fix | `watch`/`avoid` re-analysis now correctly expires old ACTIVE buy signals in Buying Zone |
| UI accordion polish | Trading Config and Notification Preferences use Settings-page SectionCard pattern |
| ML help content | `/help/ml-signals` page; FAQ items; Getting Started Step 5 |

---

## Pre-release verification

| Gate | Result (2026-06-20 local) |
|------|---------------------------|
| Frontend Vitest (79 files) | **715 passed** |
| TypeScript (`tsc --noEmit`) | **0 errors** |
| Alembic migrations | **None** — no DB changes in this release |
| Backend pytest (targeted) | Run `pytest tests/unit/services/test_ml_verdict_service_ema9_feature.py` and related ML tests |
| Docker build + volume seed | Verify `trading_models` volume created and model seeded on first boot |

**Staging / production:** Run full backend `pytest` suite and Playwright E2E if configured.

---

## Deploy steps

1. **Backup** Postgres ([POSTGRES_DOCKER_BACKUP_CRON.md](../deployment/POSTGRES_DOCKER_BACKUP_CRON.md)).
2. Pull `releases/rebound_2623` (or tag `v26.2.3`).
3. No `.env` changes required. Optional: set `ML_CONFIDENCE_THRESHOLD=0.6` explicitly if the old 0.5 default was previously relied upon.
4. Rebuild and restart Docker stack:
   ```bash
   docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up --build -d
   ```
   - The new `trading_models` volume is created automatically and auto-seeded from the image baseline on first boot.
5. No `alembic upgrade head` needed — no migrations in this release. Verify with `alembic current`.
6. **Post-deploy smoke:**
   - Login → Buying Zone: confirm ML Verdict and ML Confidence columns available
   - Trading Config: all sections collapsed; expand, edit, save — confirm values persist
   - Notification Preferences: accordion sections open/close correctly
   - Admin → ML Training: activate a model; confirm timestamp on `/app/models/verdict_model_random_forest.pkl` updates
   - `/help/ml-signals` loads without login
   - Run an analysis job; verify signals with `watch`/`avoid` verdict expire existing buy signals

---

## Rollback

No DB migrations — rollback is container-only:

- Redeploy previous image/tag (`v26.2.2.1`). No DB restore needed.
- The `trading_models` volume can be left in place (previous containers use the same canonical pkl path).
- If the baseline model should be reset: `docker volume rm trading_models` then restart (auto-seed re-runs).

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| ML threshold change (0.5 → 0.6) | Fewer buy signals through ML gate initially; operator can lower threshold in Trading Config if desired |
| `trading_models` volume new on existing installs | Docker creates it automatically; auto-seed ensures a working model on first boot |
| Stale signal expiry may archive previously-visible signals | Expected behaviour — the buying zone now reflects current combined opinion; monitor on first analysis run after deploy |
| FinBERT India overrides aggressive | Operators on non-Indian equities can ignore; India-phrase list is exact-match only |

---

## Deliverables checklist

- [x] Version `26.2.3` in `VERSION` and `web/package.json`
- [x] `CHANGELOG.md` `[26.2.3]`
- [x] This release plan
- [x] Upgrade notes in [DEPLOYMENT.md](../deployment/DEPLOYMENT.md#upgrading-to-2623)
- [ ] Full backend `pytest` suite (staging)
- [ ] Tag `v26.2.3` on branch tip (local; push with explicit approval)
- [ ] Production deploy + post-deploy smoke

---

## Related docs

- [Upgrading to 26.2.3](../deployment/DEPLOYMENT.md#upgrading-to-2623)
- [ML Complete Guide](../architecture/ML_COMPLETE_GUIDE.md)
- [Signal Management — Verdict-Downgrade Expiration](../features/SIGNAL_MANAGEMENT_IMPLEMENTATION.md#verdict-downgrade-expiration)
- [ML Model Persistence (Docker)](../deployment/DEPLOYMENT.md#ml-model-persistence-docker)
