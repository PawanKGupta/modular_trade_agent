# Billing & subscription — admin traceability matrix

Maps admin-facing requirements to **this repository**. For subscriber flows, see
[`BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md`](./BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md).

**Legend:** ✓ implemented · ~ partial / API only or heuristic · ✗ missing or not applicable

| # | Requirement | Status | Where (primary) | Notes |
|---|-------------|--------|-----------------|-------|
| 1 | Admin can create a new subscription plan | ✓ | `POST /admin/billing/plans` — `billing_admin.py` · `AdminBillingPage.tsx` · `postAdminCreatePlan` in `web/src/api/billing.ts` | Form: slug, name, tier, interval, amount (paise), optional Razorpay sync. |
| 2 | Admin can edit existing subscription plan | ~ | `PATCH /admin/billing/plans/{plan_id}` — `billing_admin.py` | **API only**; no edit form on `AdminBillingPage` yet. |
| 3 | Admin can delete or deactivate a plan | ~ | `POST /admin/billing/plans/{id}/deactivate` — `billing_admin.py` · **Deactivate** button in `AdminBillingPage.tsx` | No hard-delete endpoint. |
| 4 | Plan changes are reflected to end users | ✓ | `GET /user/billing/plans` (`list_active_plans`) · `BillingRepository` | Inactive plans hidden from public list. |
| 5 | Admin can view all user subscriptions | ✓ | `GET /admin/billing/subscriptions` · `AdminBillingPage.tsx` | Table; API supports `limit`/`offset` (UI uses fixed limit). |
| 6 | Admin can manually activate a user subscription | ✓ | `POST /admin/billing/subscriptions/{id}/activate` · **Activate** in `AdminBillingPage.tsx` | |
| 7 | Admin can manually deactivate a user subscription | ✓ | `POST /admin/billing/subscriptions/{id}/deactivate` · **Suspend** in `AdminBillingPage.tsx` | |
| 8 | Admin can assign custom subscription plans | ~ | `POST /admin/billing/subscriptions/manual` · **Manual subscription** form in `AdminBillingPage.tsx` | Catalog `plan_id` only; `MANUAL` provider row. |
| 9 | Admin can view all transactions | ✓ | `GET /admin/billing/transactions` · `AdminBillingPage.tsx` | **Table** (failed + recent sections). |
| 10 | Admin can process refunds | ✓ | `POST /admin/billing/refunds` · **Refund** form in `AdminBillingPage.tsx` · `postAdminRefund` in `billing.ts` | |
| 11 | Admin can view failed payments | ✓ | `GET /admin/billing/transactions?failed_only=true` · `AdminBillingPage.tsx` | Table, not raw JSON. |
| 12 | Admin can access subscription reports | ✓ | `GET /admin/billing/reports` · `AdminBillingPage.tsx` (`BillingReportsGrid`) | |
| 13 | Analytics show correct active subscriber count | ~ | `BillingRepository.active_subscriber_count()` | Heuristic (includes trialing/grace); align with product definition if needed. |
| 14 | Churn rate is calculated correctly | ~ | `BillingRepository.churn_logo_count()` | Documented heuristic; not cohort MRR churn. |
| 15 | Revenue reports are accurate | ~ | `BillingRepository.revenue_paise_between()` | Captured tx sum; MRR ≈ month revenue in handler comment. |
| 16 | Admin can configure notification settings | ~ | `PATCH /admin/billing/settings` · `AdminBillingPage.tsx` | **Billing knobs**: card/UPI toggles + **numeric** trial / grace / reminder / dunning hours. Per-user email prefs remain under user notification APIs. |
| 17 | Renewal reminder notifications are triggered | ~ | `BillingReconciliationService._renewal_reminders` · **Run reconcile** button | Needs SMTP + prefs + cron/reconcile. |
| 18 | Payment failure notifications are sent | ~ | `billing_webhook_service.py` (`PAYMENT_FAILED` email path) | When SMTP + `email_enabled` + prefs allow. |
| 19 | Plan limits (usage / users) are enforced correctly | ✗ | `features_json` | Boolean features only; no seat counters. |
| 20 | Feature access is controlled based on plan | ~ | `SubscriptionEntitlementService` · `require_entitlement` | When enforcement enabled; snapshots on `UserSubscription`. |

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
| POST | `/admin/billing/reconcile` | Reminders + grace/expiry + **trial expiry** |

## Admin UI (`web/src/routes/dashboard/AdminBillingPage.tsx`)

**Covers:** payment toggles; **numeric** billing settings (trial, grace, reminder lead, dunning hours); reports grid; subscription table with **Activate / Suspend**; **Create plan**; **Deactivate** per plan; **manual subscription** form; **refund** form; failed + recent transactions as **tables**; **Run reconcile**.

**Not yet in UI:** plan **edit** (PATCH) — use API or add a small edit form later.

---

*Matrix revised to match admin billing UI + webhook email behavior. See subscriber matrix for end-user flows.*
