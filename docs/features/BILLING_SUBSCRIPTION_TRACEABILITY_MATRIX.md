# Billing — traceability matrix (subscriber / end-user)

**Admin matrix:** [`BILLING_ADMIN_TRACEABILITY_MATRIX.md`](./BILLING_ADMIN_TRACEABILITY_MATRIX.md)

This matrix maps product requirements to **this repository** after **legacy subscription catalog removal**: there is **no** in-app plan list, subscribe, cancel, change-plan, or subscription pay-link API. Users see **current access** (`entitlements`), **broker performance fee** invoices and Razorpay **Order** checkout for those bills, and **payment history** (`transactions`). Existing **Razorpay subscription** webhooks and reconciliation can still update `UserSubscription` / transactions for data created before catalog removal or outside this app.

**Legend:** ✓ implemented · ~ partial / depends on Razorpay or config · ✗ removed from app or gap

| # | Requirement | Status | Where (primary) | Notes |
|---|---------------|--------|-----------------|-------|
| 1 | User can view available subscription plans in the app | ✗ | N/A | **Removed.** Was `GET /user/billing/plans` · plan list on `BillingPage.tsx`. |
| 2 | User can subscribe to a plan from the app | ✗ | N/A | **Removed.** Was `POST /user/billing/subscribe` · `BillingCheckoutService` (file removed). |
| 3 | Subscription activated after successful payment | ✓ | `billing_webhook_service.py` · `billing_webhooks.py` | Applies to **legacy** Razorpay subscription payments still hitting webhooks. |
| 4 | User receives confirmation after subscription | ~ | `billing_webhook_service.py` (`_send_billing_email_if_allowed`) · `notification_preference_service.py` | Email when SMTP + prefs allow. |
| 5 | Correct subscription start and expiry dates | ~ | `billing_webhook_service.py` · `GET /user/billing/entitlements` | Period / trial surfaced on **entitlements**; no dedicated `GET /user/billing/subscription` route. |
| 6 | User cannot complete checkout with invalid payment details | ~ | Razorpay Checkout | Applies to **performance fee** checkout (`POST …/performance-bills/{id}/checkout`); validation is Razorpay-side. |
| 7 | System handles payment failure gracefully | ✓ | `billing_webhook_service.py` | Failed tx + `PAST_DUE` + `grace_until` from admin settings (subscription path). |
| 8 | User can retry failed subscription payment via in-app pay link | ✗ | N/A | **Removed.** Was `GET /user/billing/subscription/pay-link`. Use Razorpay/hosted flows or support for legacy subs. |
| 9 | User can upgrade subscription plan in the app | ✗ | N/A | **Removed.** Was `POST /user/billing/change-plan`. `apply_pending_plan_change` may still run from webhooks if `pending_plan_id` is set elsewhere. |
| 10 | User can downgrade subscription plan in the app | ✗ | N/A | Same as #9. |
| 11 | User can cancel subscription from the app | ✗ | N/A | **Removed.** Was `POST /user/billing/cancel`. |
| 12 | Subscription status updates after cancellation | ✓ | `billing_webhook_service.py` | For events Razorpay still sends. |
| 13 | User access revoked after subscription expiry | ~ | `subscription_entitlement_service.py` · `require_entitlement` | When **`subscription_enforcement_enabled`** is true. |
| 14 | Premium features only with active subscription | ~ | `broker.py`, `service.py`, `paper_trading.py`, `signals.py` | Same enforcement flag as #13. |
| 15 | Free trial activated on subscribe from the app | ✗ | N/A | No in-app subscribe; trial fields still matter for **existing** rows + reconciliation. |
| 16 | Free trial expires correctly after defined period | ~ | `subscription_entitlement_service.py` | Access denied after `trial_end` when enforcement is on; app reconcile no longer bulk-marks `TRIALING` → `EXPIRED`. |
| 17 | User cannot reuse free trial multiple times | ~ | `billing_repository.py` · `free_trial_usage` | DB rules remain; **no** first-party subscribe path to consume trial in-app. |
| 18 | Auto-renewal reminder before subscription expiry | ✗ | N/A | App-driven renewal reminder job removed with reconcile slim-down. |
| 19 | Payment deducted during auto-renewal | ~ | Razorpay + `billing_webhook_service.py` | App records tx from webhooks. |
| 20 | Renewal failure with in-app retry scheduling | ✗ | N/A | Dunning interval admin setting removed; **no** automated Razorpay retry job in app. |
| 21 | Grace period after failed renewal | ~ | `billing_webhook_service.py` | Failed payment sets `PAST_DUE` + `grace_until` (**fixed 3-day** window). Reconcile no longer bulk-expires grace. |
| 22 | User can view subscription / access summary | ✓ | `GET /user/billing/entitlements` · `BillingPage.tsx` | “Current access” card (tier, status, period end, feature flags). |
| 23 | User can view billing history | ✓ | `GET /user/billing/transactions` · `BillingPage.tsx` | |
| 24 | User can update payment method (subscription) in app | ✗ | N/A | Pay-link / first-party subscription card flows removed from user router. |
| 25 | Updated payment method used for next subscription charge | ~ | Razorpay | Only if customer completes Razorpay-side flows; not wired through this app’s user APIs. |
| 26 | User can pay broker performance fee invoices | ✓ | `GET /user/billing/performance-bills` · `POST …/performance-bills/{id}/checkout` — `billing_user.py` · `PerformanceFeeCheckoutService` · `BillingPage.tsx` | Razorpay **Order** Checkout.js. |

## Related files (quick index)

| Area | Paths |
|------|-------|
| User billing API | `server/app/routers/billing_user.py` |
| Webhooks | `server/app/routers/billing_webhooks.py`, `src/application/services/billing_webhook_service.py` |
| Performance fee checkout | `src/application/services/performance_fee_checkout_service.py` |
| Entitlements | `src/application/services/subscription_entitlement_service.py`, `server/app/core/deps.py` |
| Reconcile (performance overdue only) | `src/application/services/billing_reconciliation_service.py` |
| Admin reconcile trigger | `POST /admin/billing/reconcile` — `server/app/routers/billing_admin.py` |
| Persistence | `src/infrastructure/persistence/billing_repository.py`, `performance_billing_repository.py` |
| Models | `src/infrastructure/db/models.py` |
| Subscriber UI | `web/src/routes/dashboard/BillingPage.tsx`, `web/src/api/billing.ts` |
| Schemas | `server/app/schemas/billing.py` (`EntitlementsOut`, `PerformanceBillOut`, `PerformanceFeeCheckoutResponse`, `TransactionOut`, …) |

## Config switches

| Setting | Effect |
|---------|--------|
| `subscription_enforcement_enabled` | When **false**, non-admin users get **full feature entitlements** regardless of subscription. |
| `subscription_grandfather_until` | ISO date: full access until that instant (UTC). |

## Remaining product gaps (intentionally not claimed above)

- **In-app** subscription catalog, subscribe, cancel, change-plan, and subscription pay-link (**removed by design**).
- **Seat / usage quotas** beyond boolean `features_json`.
- **App-driven dunning** / Razorpay retry scheduling from `dunning_retry_interval_hours`.
- **Native card/token management** APIs for legacy Razorpay subscriptions (only performance-fee Order checkout is first-party in the UI).

---

*Matrix aligned with legacy plan/subscribe API removal and performance-fee billing on `BillingPage`. Re-run QA when changing billing behavior.*
