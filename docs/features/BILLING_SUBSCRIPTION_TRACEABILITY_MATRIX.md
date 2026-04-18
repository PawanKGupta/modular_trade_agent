# Billing & subscription — traceability matrix (subscriber / end-user)

This matrix maps common product requirements to **this repository** (FastAPI routes, services, web, webhooks). It is a QA / sign-off aid, not a legal guarantee of behavior.

**Legend:** ✓ implemented · ~ partial / depends on Razorpay or config · ✗ not implemented or gap

| # | Requirement | Status | Where (primary) | Notes |
|---|---------------|--------|-----------------|-------|
| 1 | User can view available subscription plans | ✓ | `GET /user/billing/plans` — `server/app/routers/billing_user.py` · `web/src/routes/dashboard/BillingPage.tsx` · `web/src/api/billing.ts` | Lists active plans from DB. |
| 2 | User can successfully subscribe to a plan | ~ | `POST /user/billing/subscribe` — `billing_user.py` · `src/application/services/billing_checkout_service.py` · `BillingPage.tsx` | Creates Razorpay subscription + local row. **Web does not embed Razorpay Checkout**; user must complete payment in Razorpay UI / link flow. |
| 3 | Subscription activated after successful payment | ✓ | `src/application/services/billing_webhook_service.py` · `server/app/routers/billing_webhooks.py` | `subscription.activated` / `charged` / `resumed` → `ACTIVE`; payment `captured` can set `PENDING` → `ACTIVE`. |
| 4 | User receives confirmation after subscription | ~ | Prefs: `services/notification_preference_service.py` (`SUBSCRIPTION_ACTIVATED`) · `server/app/routers/notification_preferences.py` | **Webhook path does not send** activation email/in-app in traced code; renewal **email** exists in `billing_reconciliation_service.py`. |
| 5 | Correct subscription start and expiry dates | ~ | `billing_webhook_service.py` (`current_start` / `current_end` → `started_at` / `current_period_end`) · `GET /user/billing/subscription` · `BillingPage.tsx` | Correct when Razorpay payloads include timestamps; UI shows `current_period_end`. |
| 6 | User cannot subscribe with invalid payment details | ~ | N/A in-app | Validation is on **Razorpay** once Checkout / pay is used; no card form in repo. |
| 7 | System handles payment failure gracefully | ~ | `billing_webhook_service.py` (failed payment → `BillingTransaction` + `PAST_DUE` + `grace_until`) | Records failure; sets grace from `billing_admin_settings.grace_period_days`. |
| 8 | User can retry payment after failure | ✗ | — | No dedicated user API or UI flow for “retry”; may use Razorpay dashboard / links outside app. |
| 9 | User can upgrade subscription plan | ~ | `POST /user/billing/change-plan` — `billing_user.py` · `BillingCheckoutService.schedule_plan_change` · `BillingPage.tsx` | Sets `pending_plan_id`. **`apply_pending_plan_change`** in `billing_webhook_service.py` is **not invoked** anywhere — plan swap at renewal is **not wired**. |
| 10 | User can downgrade subscription plan | ~ | Same as #9 | Same code path; same **pending plan not applied** gap. |
| 11 | User can cancel subscription | ✓ | `POST /user/billing/cancel` — `billing_user.py` · `BillingCheckoutService.cancel_at_period_end` · `BillingPage.tsx` | Razorpay cancel when configured; `cancel_at_period_end` locally. |
| 12 | Subscription status updates after cancellation | ✓ | `billing_webhook_service.py` · `src/application/services/billing_reconciliation_service.py` | Webhooks + reconcile for period end / cancelled / expired paths. |
| 13 | User access revoked after subscription expiry | ~ | `src/application/services/subscription_entitlement_service.py` · `server/app/core/deps.py` (`require_entitlement`) | **Only when** `settings.subscription_enforcement_enabled` is **true** (see `server/app/core/config.py`). Otherwise full access for backward compatibility. |
| 14 | Premium features only with active subscription | ~ | `broker.py`, `service.py`, `paper_trading.py`, `signals.py` — `require_entitlement(...)` | Same enforcement flag as #13. |
| 15 | Free trial activated for eligible users | ✓ | `billing_checkout_service.py` (`default_trial_days`, `TRIALING`, `trial_end`) · admin settings in `billing_admin.py` / `BillingRepository` | Trial skipped if `trial_used` for key `global_v1`. |
| 16 | Free trial expires correctly after defined period | ✗ | — | **`trial_end` not enforced** in `SubscriptionEntitlementService.resolve`; status relies on Razorpay / missing local job. |
| 17 | User cannot reuse free trial multiple times | ✓ | `billing_checkout_service.py` · `billing_repository.py` (`trial_used` / `mark_trial_used`) · `free_trial_usage` table | Per-user + `trial_key` uniqueness. |
| 18 | Auto-renewal triggered before subscription expiry | ~ | `billing_reconciliation_service.py` (`_renewal_reminders`) | **Email reminder** in window before `current_period_end`; **charging** is Razorpay’s subscription engine, not this app. |
| 19 | Payment deducted during auto-renewal | ~ | Razorpay + `billing_webhook_service.py` (payment events → `BillingRepository.add_transaction`) | App records success/failure; does not initiate charge. |
| 20 | Renewal failure with retry mechanism | ✗ | `billing_admin_settings.dunning_retry_interval_hours` in DB/schema | Field exists; **no consumer** found that schedules retries. |
| 21 | Grace period after failed renewal | ~ | `billing_webhook_service.py` · `billing_reconciliation_service.py` (`_grace_and_expiry`) | Failure → `PAST_DUE` + `grace_until`; overdue grace → `EXPIRED`. **`GRACE` status** enum exists but failure path uses **`PAST_DUE`**, not `GRACE`. |
| 22 | User can view subscription details | ✓ | `GET /user/billing/subscription` · `GET /user/billing/entitlements` · `BillingPage.tsx` | Entitlements block still JSON in UI (cosmetic). |
| 23 | User can view billing history | ✓ | `GET /user/billing/transactions` · `BillingPage.tsx` | |
| 24 | User can update payment method | ✗ | `UserBillingProfile.default_payment_method_id` — `src/infrastructure/db/models.py` | **No user-facing route** to set or sync token from Razorpay. |
| 25 | Updated payment method used for next billing | ✗ | — | Depends on #24 + Razorpay customer/payment APIs. |

## Related files (quick index)

| Area | Paths |
|------|--------|
| User billing API | `server/app/routers/billing_user.py` |
| Webhooks | `server/app/routers/billing_webhooks.py`, `src/application/services/billing_webhook_service.py` |
| Checkout / cancel / plan change | `src/application/services/billing_checkout_service.py` |
| Entitlements | `src/application/services/subscription_entitlement_service.py`, `server/app/core/deps.py` |
| Reconcile / reminders / expiry | `src/application/services/billing_reconciliation_service.py` |
| Admin reconcile trigger | `POST /admin/billing/reconcile` — `server/app/routers/billing_admin.py` |
| Persistence | `src/infrastructure/persistence/billing_repository.py` |
| Models | `src/infrastructure/db/models.py` (`UserSubscription`, `BillingAdminSettings`, …) |
| Subscriber UI | `web/src/routes/dashboard/BillingPage.tsx`, `web/src/api/billing.ts` |
| Schemas | `server/app/schemas/billing.py` |

## Config switches

| Setting | Effect |
|---------|--------|
| `subscription_enforcement_enabled` | When **false** (default in code path), non-admin users get **full feature entitlements** regardless of subscription. |
| `subscription_grandfather_until` | ISO date: full access until that instant (UTC). |

---

*Last updated from codebase review (agent); re-run when shipping billing changes.*
