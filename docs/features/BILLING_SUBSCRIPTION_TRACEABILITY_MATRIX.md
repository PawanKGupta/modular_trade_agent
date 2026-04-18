# Billing & subscription — traceability matrix (subscriber / end-user)

**Admin matrix:** [`BILLING_ADMIN_TRACEABILITY_MATRIX.md`](./BILLING_ADMIN_TRACEABILITY_MATRIX.md)

This matrix maps common product requirements to **this repository** (FastAPI routes, services, web, webhooks). It is a QA / sign-off aid, not a legal guarantee of behavior.

**Legend:** ✓ implemented · ~ partial / depends on Razorpay or config · ✗ not implemented or gap

| # | Requirement | Status | Where (primary) | Notes |
|---|---------------|--------|-----------------|-------|
| 1 | User can view available subscription plans | ✓ | `GET /user/billing/plans` — `server/app/routers/billing_user.py` · `web/src/routes/dashboard/BillingPage.tsx` · `web/src/api/billing.ts` | Lists active plans from DB. |
| 2 | User can successfully subscribe to a plan | ~ | `POST /user/billing/subscribe` — `billing_user.py` · `billing_checkout_service.py` · `BillingPage.tsx` | After subscribe, **Razorpay Checkout.js** opens when `razorpay_key_id` + `razorpay_subscription_id` are returned. Needs Razorpay keys + plan linked to Razorpay. |
| 3 | Subscription activated after successful payment | ✓ | `billing_webhook_service.py` · `billing_webhooks.py` | `subscription.activated` / `charged` / `resumed` → `ACTIVE`; payment `captured` can set `PENDING` → `ACTIVE`. |
| 4 | User receives confirmation after subscription | ~ | `billing_webhook_service.py` (`_send_billing_email_if_allowed` on `subscription.activated`) · prefs in `notification_preference_service.py` | **Email** when SMTP + `email_enabled` + event pref allow. No in-app notification in this path. Renewal reminder still in `billing_reconciliation_service.py`. |
| 5 | Correct subscription start and expiry dates | ~ | `billing_webhook_service.py` · `GET /user/billing/subscription` · `BillingPage.tsx` | Razorpay timestamps → `started_at` / `current_period_end`; UI shows renew + **trial_end** when set. |
| 6 | User cannot subscribe with invalid payment details | ~ | Razorpay Checkout | Card validation is **Razorpay-side** in Checkout. |
| 7 | System handles payment failure gracefully | ✓ | `billing_webhook_service.py` | Failed tx row + `PAST_DUE` + `grace_until` from admin settings. |
| 8 | User can retry payment after failure | ~ | `GET /user/billing/subscription/pay-link` — `billing_user.py` · `BillingPage.tsx` (`getSubscriptionPayLink`) | Opens Razorpay **`short_url`** in a new tab when API returns it (depends on Razorpay subscription state). |
| 9 | User can upgrade subscription plan | ✓ | `POST /user/billing/change-plan` · `BillingPage.tsx` · **`subscription.charged`** in `billing_webhook_service.py` | `pending_plan_id` applied via **`apply_pending_plan_change`** on each **charged** event when set. |
| 10 | User can downgrade subscription plan | ✓ | Same as #9 | Same path. |
| 11 | User can cancel subscription | ✓ | `POST /user/billing/cancel` — `billing_user.py` · `BillingCheckoutService` · `BillingPage.tsx` | |
| 12 | Subscription status updates after cancellation | ✓ | `billing_webhook_service.py` · `billing_reconciliation_service.py` | |
| 13 | User access revoked after subscription expiry | ~ | `subscription_entitlement_service.py` · `require_entitlement` | When **`subscription_enforcement_enabled`** is true. |
| 14 | Premium features only with active subscription | ~ | `broker.py`, `service.py`, `paper_trading.py`, `signals.py` | Same enforcement flag as #13. |
| 15 | Free trial activated for eligible users | ✓ | `billing_checkout_service.py` · admin settings | `trial_used` / `global_v1` gate. |
| 16 | Free trial expires correctly after defined period | ✓ | `subscription_entitlement_service.py` (deny if `trial_end` passed) · `billing_reconciliation_service._expire_trials` | Access denied immediately; reconcile marks **`EXPIRED`** and returns **`trial_subscriptions_expired`** count. |
| 17 | User cannot reuse free trial multiple times | ✓ | `billing_checkout_service.py` · `billing_repository.py` · `free_trial_usage` | |
| 18 | Auto-renewal triggered before subscription expiry | ~ | `billing_reconciliation_service._renewal_reminders` | **Email reminder** before `current_period_end`; **billing** charge is Razorpay. |
| 19 | Payment deducted during auto-renewal | ~ | Razorpay + `billing_webhook_service.py` | App records tx from webhooks. |
| 20 | Renewal failure with retry mechanism | ✗ | `billing_admin_settings.dunning_retry_interval_hours` | Stored + editable in admin UI; **no automated Razorpay retry job** in app. |
| 21 | Grace period after failed renewal | ~ | `billing_webhook_service.py` · `billing_reconciliation_service._grace_and_expiry` | Uses **`PAST_DUE`** + `grace_until` (not `GRACE` enum value). |
| 22 | User can view subscription details | ✓ | `GET /user/billing/subscription` · entitlements · `BillingPage.tsx` | Entitlements still JSON block (cosmetic). |
| 23 | User can view billing history | ✓ | `GET /user/billing/transactions` · `BillingPage.tsx` | |
| 24 | User can update payment method | ~ | `GET /user/billing/subscription/pay-link` | **Hosted** Razorpay flow when `short_url` exists; no first-class “save card” API on our side. |
| 25 | Updated payment method used for next billing | ~ | Razorpay | Depends on customer completing Razorpay hosted / Checkout flows; not verified in-app. |

## Related files (quick index)

| Area | Paths |
|------|--------|
| User billing API | `server/app/routers/billing_user.py` |
| Webhooks | `server/app/routers/billing_webhooks.py`, `src/application/services/billing_webhook_service.py` |
| Checkout / cancel / plan change | `src/application/services/billing_checkout_service.py` |
| Entitlements | `src/application/services/subscription_entitlement_service.py`, `server/app/core/deps.py` |
| Reconcile / reminders / expiry / trials | `src/application/services/billing_reconciliation_service.py` |
| Admin reconcile trigger | `POST /admin/billing/reconcile` — `server/app/routers/billing_admin.py` |
| Persistence | `src/infrastructure/persistence/billing_repository.py` |
| Models | `src/infrastructure/db/models.py` |
| Subscriber UI | `web/src/routes/dashboard/BillingPage.tsx`, `web/src/api/billing.ts` |
| Schemas | `server/app/schemas/billing.py` (`SubscriptionPayLinkOut`, …) |

## Config switches

| Setting | Effect |
|---------|--------|
| `subscription_enforcement_enabled` | When **false**, non-admin users get **full feature entitlements** regardless of subscription. |
| `subscription_grandfather_until` | ISO date: full access until that instant (UTC). |

## Remaining product gaps (intentionally not claimed above)

- **Seat / usage quotas** beyond boolean `features_json`.
- **App-driven dunning** / Razorpay retry scheduling from `dunning_retry_interval_hours`.
- **Native card/token management** APIs (only hosted `short_url` + Checkout where applicable).

---

*Matrix revised to match billing gap implementation (Checkout, webhooks, pay-link, trial expiry, plan apply on charge). Re-run QA when changing billing behavior.*
