# Billing — admin traceability matrix

Admin billing is **performance-fee and payments focused**: Razorpay credentials, payment method toggles, performance-fee defaults (API), transactions, refunds, and a **reconcile** job that only marks overdue performance-fee bills. Legacy subscription **plan catalog**, **SaaS KPI reports**, **subscription list/activate APIs**, and **trial/grace/dunning admin knobs** have been removed.

For user-facing billing, see [`BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md`](./BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md).

**Legend:** ✓ implemented · ✗ removed / not applicable

| # | Requirement | Status | Where (primary) | Notes |
|---|-------------|--------|-----------------|-------|
| 1 | Admin plan catalog CRUD | ✗ | N/A | Removed earlier (`POST/PATCH …/plans`, etc.). |
| 2 | Admin subscription list / activate / suspend | ✗ | N/A | Routes removed from `billing_admin.py`. |
| 3 | Admin SaaS-style revenue / churn reports | ✗ | N/A | `GET /admin/billing/reports` removed. |
| 4 | Admin trial / grace / renewal / dunning settings | ✗ | N/A | Columns removed from `billing_admin_settings`. |
| 5 | Admin payment toggles (card / UPI) | ✓ | `GET`/`PATCH /admin/billing/settings` · `AdminBillingPage.tsx` | |
| 6 | Admin performance fee defaults | ~ | `PATCH /admin/billing/settings` | Exposed on API; extend admin UI if you want fields here. |
| 7 | Admin Razorpay credentials | ✓ | `PATCH /admin/billing/razorpay-credentials` · `AdminBillingPage.tsx` | |
| 8 | Admin list transactions & refunds | ✓ | `GET /admin/billing/transactions`, `POST /admin/billing/refunds` · `AdminBillingPage.tsx` | |
| 9 | Reconcile overdue performance bills | ✓ | `POST /admin/billing/reconcile` · `BillingReconciliationService` · `AdminBillingPage.tsx` | Returns `{ performance_bills_marked_overdue: n }`. |
| 10 | Admin offline payment settings (UPI, instructions) | ✓ | `GET`/`PATCH /admin/billing/settings` · `AdminBillingPage.tsx` | Shown when online checkout is off (`online_payments_enabled=false`). |
| 11 | Admin upload offline payment QR image | ✓ | `POST`/`DELETE /admin/billing/offline-payment-qr` · `billing_offline_qr_storage.py` · `AdminBillingPage.tsx` | PNG/JPEG/WebP/GIF, max 2 MB; stored under `data/billing/`; replaces hosted QR URL. |
| 12 | Admin record cash payment on open performance bills | ✓ | `POST /admin/billing/performance-bills/{id}/record-cash-payment` · `AdminBillingPage.tsx` | For offline UPI settlements after manual confirmation. |

## Admin API summary (`billing_admin.py`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/billing/settings` | Payment toggles + performance fee fields + Razorpay meta |
| PATCH | `/admin/billing/settings` | Update those settings |
| PATCH | `/admin/billing/razorpay-credentials` | Store/clear Razorpay key id + encrypted secrets |
| GET | `/admin/billing/transactions` | List / filter transactions |
| POST | `/admin/billing/refunds` | Razorpay refund + local row |
| POST | `/admin/billing/reconcile` | Mark overdue performance-fee bills |
| POST | `/admin/billing/offline-payment-qr` | Upload offline payment QR image (multipart) |
| DELETE | `/admin/billing/offline-payment-qr` | Remove uploaded QR image |
| POST | `/admin/billing/performance-bills/{id}/record-cash-payment` | Mark performance bill paid (offline/cash) |

## Admin UI (`web/src/routes/dashboard/AdminBillingPage.tsx`)

Payment toggles, offline UPI/instructions, **QR upload** (or optional hosted URL), Razorpay credentials, **Reconciliation** (run reconcile), **Record cash payment**, refund form, failed + recent transaction tables.

---

*Matrix reflects subscription-style admin surface removal. Re-run QA when changing billing behavior.*
