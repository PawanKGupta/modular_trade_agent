# Release Plan v26.2.3.3

**Branch:** `releases/rebound_26233` (on top of `v26.2.3.2`)
**Version:** 26.2.3.3 (CalVer Q2 2026 patch)
**Status:** Ready for tag and deploy after checklist below
**Release notes:** See [CHANGELOG.md](../../CHANGELOG.md) `[26.2.3.3]`

---

## Scope

Three operational/observability fixes on top of `v26.2.3.2`:

| Theme | Operator impact |
|-------|-----------------|
| **Stale ML training dataset on upgrade** | The API entrypoint seeded `data/training/verdict_classifier.csv` into the data volume only when absent, so any deployment that existed before the price-regressor dataset kept an old copy missing the `max_favorable_pct_20d` target. Price-regressor training failed with `requires target column 'max_favorable_pct_20d'`. The entrypoint now **refreshes** the volume copy when the image-baked dataset differs (backing up the previous file), and the training error messages point to the bundled dataset / `/app/data_default` refresh path instead of the unshipped `build_historical_dataset.py`. |
| **Weekend "service stale" false alerts** | The paper-trading scheduler's per-minute liveness heartbeat was placed below the weekend `continue`, so on Sat/Sun it stopped heartbeating while the thread stayed alive — monitoring flagged healthy paper services as critically "stale" all weekend. The scheduler now heartbeats on the weekend path too (no weekend tasks run, as before). Weekday off-market hours were never affected. |
| **Off-market schedule validation (400 on update)** | Updating the `buy_margin_preview` / `eod_cleanup` schedule to an evening time (after 6:00 PM) returned `400 Bad Request`: validation only allowed `analysis` off-market and forced everything else into 09:00–18:00. `buy_margin_preview` and `eod_cleanup` are now validated as off-market tasks (allowed outside 09:00–16:00); on-market tasks stay 09:00–18:00. |

No new features, no schema changes.

---

## Why a separate patch

`v26.2.3.2` was already tagged and published (Docker images built via `docker-release.yml`) before this fix landed. Rather than move a released tag, the fix ships as `v26.2.3.3`.

---

## Pre-release verification

| Gate | Result (2026-06-28 local) |
|------|---------------------------|
| `docker/api-entrypoint.sh` shell syntax (`bash -n`) | Passes |
| `tests/unit/services/test_ml_training_csv_validation.py` | 2 passed (error message still matches `max_favorable_pct_20d`) |
| ML-related suite (csv validation, sample weight, ml router, training service, order sizing) | 54 passed |
| Weekend heartbeat regression (`tests/unit/application/test_paper_scheduler_weekend_heartbeat.py`) | Passes — and fails (1 ≠ 2 heartbeats) when the fix is reverted, confirming it guards the bug |
| `multi_user_trading_service` + paper-scheduler suites | Passed |
| Schedule validation + admin router (`test_schedule_manager.py`, `test_admin.py`) | 51 passed (off-market evening allowed for buy_margin_preview/eod_cleanup; on-market tasks still capped at 18:00) |
| Ruff + Black on changed files | Clean |

> Code changes vs `v26.2.3.2`: the entrypoint dataset refresh, two corrected price-regressor error strings, and one heartbeat line moved into the weekend branch of the paper scheduler (plus a dead-variable cleanup the linter required in the same file). All other source is the already-released `v26.2.3.2` tip.

---

## Deploy steps

From **`v26.2.3.2`**:

1. Pull image `v26.2.3.3` (or check out the tag) and restart:
   ```bash
   export APP_VERSION=v26.2.3.3
   docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml pull
   docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
   ```
2. On restart, the entrypoint auto-refreshes a stale `data/training/verdict_classifier.csv` from the image default (look for `Refreshed ML training dataset from image default ...` in the logs).
3. **Post-deploy smoke:** run a price_regressor training job (training_data_path = `data/training/verdict_classifier.csv`) and confirm it completes (the `max_favorable_pct_20d` target is present).

> Already manually refreshed a deployment's CSV for `v26.2.3.2`? This release simply makes that automatic and idempotent — no manual step needed going forward.

---

## Rollback

- Redeploy `v26.2.3.2`. The entrypoint change is backward-safe; the dataset backup files (`verdict_classifier.csv.bak.*`) remain in the volume if you need the prior copy.

---

## Deliverables checklist

- [x] Version `26.2.3.3` in `VERSION` and `web/package.json`
- [x] `CHANGELOG.md` `[26.2.3.3]`
- [x] This release plan
- [x] Upgrade notes in [DEPLOYMENT.md](../deployment/DEPLOYMENT.md#upgrading-to-26233)
- [ ] Tag `v26.2.3.3` on branch tip (pending — triggers `docker-release.yml` image build/publish)

---

## Related docs

- [Upgrading to 26.2.3.3](../deployment/DEPLOYMENT.md#upgrading-to-26233)
- [Release Plan v26.2.3.2](RELEASE_PLAN_V26.2.3.2.md)
