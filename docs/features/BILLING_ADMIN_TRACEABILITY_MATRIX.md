# Billing & subscription — admin traceability matrix

Maps admin-facing requirements to **this repository**. For subscriber flows, see
[`BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md`](./BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md).

**Legend:** ✓ implemented · ~ partial / API only or heuristic · ✗ missing or not applicable

| # | Requirement | Status | Where (primary) | Notes |
|---|-------------|--------|-----------------|-------|
| 1 | Admin can create a new subscription plan | ~ | `POST /admin/billing/plans` — `server/app/routers/billing_admin.py` (`admin_create_plan`) · optional Razorpay sync | **No admin web UI**; `web/src/api/billing.ts` has no `createPlan` helper. Use API or extend UI. |
| 2 | Admin can edit existing subscription plan | ~ | `PATCH /admin/billing/plans/{plan_id}` — `billing_admin.py` (`admin_update_plan`) · `AdminPlanUpdate` in `server/app/schemas/billing.py` | **No admin web UI** for edit. |
| 3 | Admin can delete or deactivate a plan | ~ | `POST /admin/billing/plans/{plan_id}/deactivate` — `billing_admin.py` | **Deactivate only** (sets `is_active=False`); **no hard-delete** endpoint. |
| 4 | Plan changes are reflected to end users | ✓ | `GET /user/billing/plans` uses `list_active_plans()` — `billing_user.py` · `BillingRepository` | Inactive plans drop off public list; entitlements use `UserSubscription` + snapshot, not live plan row for already-assigned subs until change flows apply. |
| 5 | Admin can view all user subscriptions | ✓ | `GET /admin/billing/subscriptions` — `billing_admin.py` · `AdminBillingPage.tsx` (table) | Pagination params exist on API (`limit`, `offset`); UI uses fixed limit. |
| 6 | Admin can manually activate a user subscription | ✓ | `POST /admin/billing/subscriptions/{sub_id}/activate` — `billing_admin.py` | Sets `ACTIVE`, sets `started_at` if missing. **No web button** in `AdminBillingPage.tsx`. |
| 7 | Admin can manually deactivate a user subscription | ✓ | `POST /admin/billing/subscriptions/{sub_id}/deactivate` — `billing_admin.py` | Sets `SUSPENDED`. **No web button** in admin billing UI. |
| 8 | Admin can assign custom subscription plans | ~ | `POST /admin/billing/subscriptions/manual` — `billing_admin.py` (`AdminManualSubscription`: `user_id`, `plan_id`, `period_months`) | Assigns an **existing** catalog `plan_id`; creates `MANUAL` provider sub. **No UI**; not arbitrary “custom” JSON plans. |
| 9 | Admin can view all transactions | ✓ | `GET /admin/billing/transactions` — `billing_admin.py` · `AdminBillingPage.tsx` (JSON list) | Optional `user_id`, `failed_only`, `limit`. |
| 10 | Admin can process refunds | ✓ | `POST /admin/billing/refunds` — `billing_admin.py` · Razorpay in same handler | Refund via Razorpay + local `BillingRefund` row. **No admin web UI** wired in `billing.ts`. |
| 11 | Admin can view failed payments | ✓ | `GET /admin/billing/transactions?failed_only=true` — `billing_admin.py` · `AdminBillingPage.tsx` | Shown as JSON block. |
| 12 | Admin can access subscription reports | ✓ | `GET /admin/billing/reports` — `billing_admin.py` · `AdminBillingPage.tsx` (`BillingReportsGrid`) | Year/month query params. |
| 13 | Analytics show correct active subscriber count | ~ | `BillingRepository.active_subscriber_count()` · `billing_admin.py` → `BillingReportsOut` | Counts `ACTIVE` / `TRIALING` / `GRACE` with `current_period_end` null or ≥ `now`. Heuristic; **includes trialing/grace**; may differ from product definition of “paying”. |
| 14 | Churn rate is calculated correctly | ~ | `BillingRepository.churn_logo_count()` · `billing_admin.py` | **Defined as:** churned distinct users with `CANCELLED`/`EXPIRED` and `updated_at` in `(period_start, period_end]` vs “active at start” heuristic. **Not cohort MRR churn**; document for stakeholders. |
| 15 | Revenue reports are accurate | ~ | `BillingRepository.revenue_paise_between()` | Sums **captured** `BillingTransaction` in `[start, end)`. Accuracy = completeness of webhook logging + clocks. **MRR** in reports is **same as month revenue** per `billing_admin.py` comment (approximation). |
| 16 | Admin can configure notification settings | ~ | `PATCH /admin/billing/settings` — `billing_admin.py` (`grace_period_days`, `renewal_reminder_days_before`, `default_trial_days`, `dunning_retry_interval_hours`, payment toggles) | **Billing-related** knobs only. **Per-user** email/Telegram prefs live under user notification APIs, not this admin billing page. **`AdminBillingPage` UI** currently exposes **payment toggles only**, not full settings payload. |
| 17 | Renewal reminder notifications are triggered | ~ | `BillingReconciliationService._renewal_reminders` · `POST /admin/billing/reconcile` | Sends email when job runs and prefs allow. **Requires** reconcile/cron + `EmailNotifier` configured. |
| 18 | Payment failure notifications are sent | ✗ | `billing_webhook_service.py` (failed payment → DB only) | **No** email/in-app send on payment failure in traced path; prefs include `notify_payment_failed` but **no consumer** hooked from webhook. |
| 19 | Plan limits (usage / users) are enforced correctly | ✗ | `features_json` on `SubscriptionPlan` | Feature **flags** (e.g. `broker_execution`) drive access via `SubscriptionEntitlementService`; **no** built-in “max seats / API usage” counters in billing models. |
| 20 | Feature access is controlled based on plan | ~ | `SubscriptionEntitlementService` · `features_snapshot` on `UserSubscription` · `require_entitlement` | Effective when `subscription_enforcement_enabled`; uses snapshot + tier defaults. |

## Admin API summary (`billing_admin.py`)

| Method | Path | Purpose |
|--------|------|---------|
| GET/PATCH | `/admin/billing/settings` | Billing admin settings |
| GET | `/admin/billing/plans` | All plans (incl. inactive) |
| POST | `/admin/billing/plans` | Create plan |
| PATCH | `/admin/billing/plans/{id}` | Update plan |
| POST | `/admin/billing/plans/{id}/deactivate` | Soft-deactivate |
| POST | `/admin/billing/plans/{id}/price-schedules` | Price schedule row |
| POST | `/admin/billing/coupons` | Create coupon |
| GET | `/admin/billing/subscriptions` | List subs |
| POST | `/admin/billing/subscriptions/manual` | Manual assign |
| POST | `/admin/billing/subscriptions/{id}/activate` | Activate |
| POST | `/admin/billing/subscriptions/{id}/deactivate` | Suspend |
| GET | `/admin/billing/transactions` | List / filter txs |
| POST | `/admin/billing/refunds` | Refund |
| GET | `/admin/billing/reports` | Metrics for month |
| POST | `/admin/billing/reconcile` | Reminders + expiry pass |

## Admin UI (`web/src/routes/dashboard/AdminBillingPage.tsx`)

Covers: payment toggles, reports grid, subscription table (read-only), plan list (read-only), failed + recent transactions (JSON), reconcile button.

Does **not** cover (API-only today): plan CRUD, manual subscription, activate/deactivate subscription, refunds, full billing settings form.

---

*See also subscriber matrix: [`BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md`](./BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md)*
