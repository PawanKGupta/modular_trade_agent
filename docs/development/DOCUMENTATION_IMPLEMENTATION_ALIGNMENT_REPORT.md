# Documentation Implementation Alignment Report

**Date:** 2026-06-06 (updated for release **26.2.1**)
**Status:** ✅ **REVIEWED**

## Summary

Documentation aligned with `releases/rebound_2621` / **v26.2.1** implementation. Prior sections below remain valid where noted; this pass adds auth, billing, and removal of Activity Log.

## 26.2.1 additions

### Auth endpoints ✅

Documented in [API.md](../API.md):

- `/api/v1/auth/signup`, `login`, `me`, `refresh`, `profile`
- `/api/v1/auth/change-password`, `forgot-password`, `reset-password`
- `/api/v1/auth/verify-email`, `resend-verification`

UI: [UI_GUIDE.md](../guides/UI_GUIDE.md) §9 Settings, §18–23 auth pages.

### Billing endpoints ✅

Documented in [API.md](../API.md):

- User prefix `/api/v1/user/billing/*` — `billing_user.router`
- Admin prefix `/api/v1/admin/billing/*` — `billing_admin.router`
- Webhook `POST /api/v1/billing/webhooks/razorpay`

Traceability: [BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md](../features/BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md), [BILLING_ADMIN_TRACEABILITY_MATRIX.md](../features/BILLING_ADMIN_TRACEABILITY_MATRIX.md).

UI: [UI_GUIDE.md](../guides/UI_GUIDE.md) §14–15 Billing pages.

### Removed ✅

- **Activity Log:** `/dashboard/activity`, `server/app/routers/activity.py`, and `activity` table removed — use **Log Viewer** (`/dashboard/logs`). Documented in UI_GUIDE §17.

### Analysis access ✅

- Market analysis **run-once** restricted to **admin** role — noted in CHANGELOG and USER_GUIDE admin sections.

---

## Prior verification (still valid)

### 1. API Endpoints ✅

Core endpoints verified against routers:

- ✅ Auth routes — see 26.2.1 additions above
- ✅ Billing routes — see 26.2.1 additions above
- ✅ `/api/v1/signals/buying-zone` — `signals.router`
- ✅ `/api/v1/user/orders/` — `orders.router` (paginated)
- ✅ `/api/v1/user/trading-config` — `trading_config.router`
- ✅ `/api/v1/user/broker/credentials` — `broker.router`
- ✅ `/api/v1/user/notification-preferences` — `notification_preferences.router`
- ✅ `/api/v1/user/notifications` — `notifications.router`
- ✅ `/api/v1/user/service/*` — `service.router`
- ✅ `/api/v1/admin/ml/training` — `ml.router`
- ✅ `/api/v1/user/paper-trading/*` — `paper_trading.router`

### 2. Service Task Names ✅

Matches `ScheduleManager.validate_schedule()` including `buy_margin_preview` (morning schedule).

### 3. Trading Configuration Parameters ✅

Matches `TradingConfigResponse` including `ml_price_enabled`.

### 4–6. ML, notifications, paper trading ✅

Unchanged from prior review; see [TRADING_CONFIG.md](../guides/TRADING_CONFIG.md) and [PAPER_TRADING_COMPLETE.md](../guides/PAPER_TRADING_COMPLETE.md).

---

## Conclusion

✅ **Documentation updated for 26.2.1** (auth, billing, activity removal, upgrade path).

Release checklist: [RELEASE_PLAN_V26.2.1.md](RELEASE_PLAN_V26.2.1.md).
