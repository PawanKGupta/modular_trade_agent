# API Documentation

Complete REST API reference for Rebound — Modular Trade Agent.

## Base URL

- **Development:** `http://localhost:8000/api/v1`
- **Production:** `https://your-domain.com/api/v1`

All endpoints use the `/api/v1` prefix.

## Authentication

Most endpoints require authentication via JWT tokens.

### Getting a Token

```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ..."
}
```

### Using Tokens

Include the token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Token Refresh

```bash
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}
```

## Endpoints

### Authentication

#### Sign Up
```http
POST /api/v1/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password",
  "name": "User Name",
  "mobile_number": "9876543210"
}
```

`mobile_number` is optional; when provided it must be a valid 10-digit Indian mobile number (starts with 6–9).

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}
```

#### Get Current User
```http
GET /api/v1/auth/me
Authorization: Bearer <token>
```

Response includes `email`, `name`, optional `mobile_number`, `roles`, and `email_verified`.

#### Update Profile
```http
PATCH /api/v1/auth/profile
Authorization: Bearer <token>
Content-Type: application/json

{
  "email": "user@example.com",
  "mobile_number": "9876543210"
}
```

Users may update **email** and **mobile_number** only (name is read-only). **`mobile_number` is optional contact info and is not required to be unique** across accounts.

- **Mobile only:** send `mobile_number` (or `null` / `""` to clear). No password required.
- **Email change:** include `current_password`. The account is marked unverified and a verification link is sent to the **new** address. If sending that email fails (SMTP configured but delivery fails), the email address is **not** changed — use resend verification or try again.
- Send `mobile_number: null` or `""` to clear a stored mobile.

```json
{
  "email": "new@example.com",
  "mobile_number": "9876543210",
  "current_password": "YourCurrentPassword123!"
}
```

#### Change Password
```http
POST /api/v1/auth/change-password
Authorization: Bearer <token>
Content-Type: application/json

{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword123!"
}
```

#### Forgot Password
```http
POST /api/v1/auth/forgot-password
Content-Type: application/json

{
  "email": "user@example.com"
}
```

Always returns 200 when SMTP is configured (does not reveal whether the email exists).

#### Reset Password
```http
POST /api/v1/auth/reset-password
Content-Type: application/json

{
  "token": "<reset-token-from-email>",
  "new_password": "NewPassword123!"
}
```

#### Verify Email
```http
POST /api/v1/auth/verify-email
Content-Type: application/json

{
  "token": "<verification-token-from-email>"
}
```

Returns access and refresh tokens on success (auto-login).

#### Resend Verification
```http
POST /api/v1/auth/resend-verification
Content-Type: application/json

{
  "email": "user@example.com"
}
```

Verification links expire **72 hours** after send.

### User Billing

Prefix: `/api/v1/user` (authenticated). See [Billing user traceability matrix](features/BILLING_SUBSCRIPTION_TRACEABILITY_MATRIX.md).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/billing/payment-options` | Offline UPI instructions vs online checkout availability |
| GET | `/billing/offline-payment-qr` | Admin-uploaded QR image (when offline mode) |
| GET | `/billing/performance-fee-arrears` | Open arrears summary |
| GET | `/billing/performance-bills` | User performance-fee invoices |
| POST | `/billing/performance-bills/{bill_id}/checkout` | Razorpay checkout for a bill (when online enabled) |
| POST | `/billing/razorpay/create-order` | Generic Razorpay order (prefer performance-bill checkout) |
| POST | `/billing/razorpay/verify-payment` | Verify Razorpay payment signature |
| GET | `/billing/transactions` | Payment transaction history |

### Admin Billing

Prefix: `/api/v1/admin` (admin role). See [Billing admin traceability matrix](features/BILLING_ADMIN_TRACEABILITY_MATRIX.md).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/billing/settings` | Payment toggles, offline UPI fields, performance-fee defaults |
| PATCH | `/billing/settings` | Update settings |
| POST | `/billing/offline-payment-qr` | Upload offline payment QR (PNG/JPEG/WebP/GIF, max 2 MB) |
| DELETE | `/billing/offline-payment-qr` | Remove uploaded QR |
| PATCH | `/billing/razorpay-credentials` | Store encrypted Razorpay keys |
| GET | `/billing/transactions` | All billing transactions |
| POST | `/billing/refunds` | Issue refund |
| POST | `/billing/reconcile` | Mark overdue performance bills |
| GET | `/billing/performance-bills` | All users' performance bills |
| POST | `/billing/performance-bills/{bill_id}/record-cash-payment` | Mark bill paid (offline UPI/cash) |

### Billing Webhooks

```http
POST /api/v1/billing/webhooks/razorpay
```

Razorpay server-to-server events (signature verified). No JWT.

### Trading Signals

#### Get Buying Zone
```http
GET /api/v1/signals/buying-zone?limit=100&date_filter=today&status_filter=active
Authorization: Bearer <token>
```

**Query Parameters:**
- `limit` (optional): Number of results (default: 100)
- `date_filter` (optional): Filter by date (YYYY-MM-DD)
- `status_filter` (optional): `active`, `rejected`, or `null` for all

**Response:**
```json
[
  {
    "symbol": "RELIANCE.NS",
    "status": "active",
    "rsi10": 25.5,
    "ema9": 2450.50,
    "ema200": 2400.00,
    "distance_to_ema9": 2.5,
    "buy_range": {"low": 2380.00, "high": 2395.00},
    "target": 2450.50,
    "stop": 2300.00,
    "confidence": 75.5,
    "backtest_score": 65.0,
    "ml_verdict": "buy",
    "ml_confidence": 0.82,
    "ts": "2025-01-15T10:30:00Z"
  }
]
```

#### Reject Signal
```http
PATCH /api/v1/signals/signals/{symbol}/reject
Authorization: Bearer <token>
Content-Type: application/json

{
  "reason": "Manually decided not to trade"
}
```

#### Activate Signal
```http
PATCH /api/v1/signals/signals/{symbol}/activate
Authorization: Bearer <token>
Content-Type: application/json

{
  "reason": "Re-activate signal"
}
```

### Orders

#### Get Orders
```http
GET /api/v1/user/orders/?page=1&page_size=50&status=pending
Authorization: Bearer <token>
```

**Query Parameters:**
- `status` (optional): Filter by status (`pending`, `ongoing`, `closed`, `failed`, `cancelled`)
- `reason` (optional): Filter by reason (partial match)
- `from_date` (optional): Filter orders from this date (`YYYY-MM-DD`)
- `to_date` (optional): Filter orders to this date (`YYYY-MM-DD`)
- `page` (optional): Page number (1-based, default: 1)
- `page_size` (optional): Items per page (default: 50)

**Response (paginated):**
```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 50,
  "total_pages": 0
}
```

#### Retry Failed Order
```http
POST /api/v1/user/orders/{order_id}/retry
Authorization: Bearer <token>
```

#### Drop Failed Order From Retry Queue
```http
DELETE /api/v1/user/orders/{order_id}
Authorization: Bearer <token>
```

#### Sync Order Status
```http
POST /api/v1/user/orders/sync?order_id=123
Authorization: Bearer <token>
```

**Query Parameters:**
- `order_id` (optional): Sync specific order. If omitted, syncs all pending/ongoing orders

**Response:**
```json
{
  "message": "Order sync completed",
  "sync_performed": true,
  "monitoring_active": false,
  "synced": 2,
  "updated": 2,
  "executed": 1,
  "rejected": 1,
  "cancelled": 0,
  "errors": []
}
```

**Use Cases:**
- Order monitoring service is not running
- Force refresh order status
- Troubleshooting order status issues

**Note:** If monitoring service (unified or sell_monitor) is active, the endpoint returns a message indicating automatic sync is available and no manual sync is performed.

### Targets

#### Get Targets
```http
GET /api/v1/user/targets
Authorization: Bearer <token>
```

**Query Parameters:**
- `status` (optional): Filter by status

### P&L

#### Get P&L Summary
```http
GET /api/v1/user/pnl/summary
Authorization: Bearer <token>
```

#### Get Daily P&L
```http
GET /api/v1/user/pnl/daily?start=2025-01-01&end=2025-01-31
Authorization: Bearer <token>
```

### Paper Trading


#### Get Paper Trading History
```http
GET /api/v1/user/paper-trading/history?limit=50
Authorization: Bearer <token>
```

#### Get Paper Trading Portfolio
```http
GET /api/v1/user/paper-trading/portfolio
Authorization: Bearer <token>
```

### Trading Configuration

#### Get Trading Config
```http
GET /api/v1/user/trading-config
Authorization: Bearer <token>
```

**Response:**
```json
{
  "rsi_period": 10,
  "rsi_oversold": 30.0,
  "rsi_extreme_oversold": 20.0,
  "rsi_near_oversold": 40.0,
  "user_capital": 100000.0,
  "paper_trading_initial_capital": 1000000.0,
  "max_portfolio_size": 6,
  "max_position_volume_ratio": 0.10,
  "min_absolute_avg_volume": 10000,
  "chart_quality_enabled": true,
  "chart_quality_min_score": 50.0,
  "chart_quality_max_gap_frequency": 25.0,
  "chart_quality_min_daily_range_pct": 1.0,
  "chart_quality_max_extreme_candle_frequency": 20.0,
  "default_stop_loss_pct": null,
  "tight_stop_loss_pct": null,
  "min_stop_loss_pct": null,
  "default_target_pct": 0.10,
  "strong_buy_target_pct": 0.12,
  "excellent_target_pct": 0.15,
  "strong_buy_risk_reward": 3.0,
  "buy_risk_reward": 2.5,
  "excellent_risk_reward": 3.5,
  "default_exchange": "NSE",
  "default_product": "CNC",
  "default_order_type": "MARKET",
  "default_variety": "AMO",
  "default_validity": "DAY",
  "allow_duplicate_recommendations_same_day": false,
  "exit_on_ema9_or_rsi50": true,
  "min_combined_score": 25,
  "enable_premarket_amo_adjustment": true,
  "news_sentiment_enabled": true,
  "news_sentiment_lookback_days": 30,
  "news_sentiment_min_articles": 2,
  "news_sentiment_pos_threshold": 0.25,
  "news_sentiment_neg_threshold": -0.25,
  "ml_enabled": false,
  "ml_price_enabled": false,
  "ml_price_models_available": false,
  "ml_model_version": null,
  "ml_confidence_threshold": 0.6,
  "ml_combine_with_rules": true
}
```

#### Update Trading Config
```http
PUT /api/v1/user/trading-config
Authorization: Bearer <token>
Content-Type: application/json

{
  "rsi_period": 10,
  "user_capital": 300000.0,
  "ml_price_enabled": false
}
```

All fields are optional. Returns the updated configuration matching the `GET /api/v1/user/trading-config` schema.

#### Reset Trading Config
```http
POST /api/v1/user/trading-config/reset
Authorization: Bearer <token>
```

Resets all parameters to their system default values. Returns the default configuration matching the `GET /api/v1/user/trading-config` schema.

### Broker Credentials

#### Get Broker Credentials Info
```http
GET /api/v1/user/broker/creds/info?show_full=false
Authorization: Bearer <token>
```

**Query Parameters:**
- `show_full` (optional, default `false`): Set to `true` to return full decrypted credentials instead of masked values.

**Response:**
```json
{
  "has_creds": true,
  "api_key": "xxx",
  "api_secret": "xxx",
  "mobile_number": "xxx",
  "password": "xxx",
  "mpin": "xxx",
  "totp_secret": "xxx",
  "environment": "prod",
  "api_key_masked": "ap...key",
  "api_secret_masked": "se...ret"
}
```

#### Save/Update Broker Credentials
```http
POST /api/v1/user/broker/creds
Authorization: Bearer <token>
Content-Type: application/json

{
  "broker": "kotak",
  "api_key": "your_consumer_key",
  "api_secret": "your_consumer_secret_ucc",
  "mobile_number": "9876543210",
  "password": "your_password",
  "mpin": "1234",
  "totp_secret": "your_totp_secret_key",
  "environment": "prod"
}
```

**Note:** Credentials are encrypted before database storage. Saving credentials automatically switches the user's trade mode to `broker` (live trading mode) and restarts any running trading services to apply the new credentials.

### Notification Preferences

#### Get Notification Preferences
```http
GET /api/v1/user/notification-preferences
Authorization: Bearer <token>
```

**Response:**
```json
{
  "telegram_enabled": true,
  "telegram_bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
  "telegram_chat_id": "123456789",
  "email_enabled": false,
  "email_address": null,
  "in_app_enabled": true,
  "notify_service_events": false,
  "notify_trading_events": true,
  "notify_system_events": true,
  "notify_errors": true,
  "notify_order_placed": true,
  "notify_order_rejected": true,
  "notify_order_executed": true,
  "notify_order_cancelled": true,
  "notify_order_modified": true,
  "notify_retry_queue_added": true,
  "notify_retry_queue_updated": true,
  "notify_retry_queue_removed": true,
  "notify_retry_queue_retried": true,
  "notify_partial_fill": true,
  "notify_balance_shortfall": true,
  "notify_system_errors": true,
  "notify_system_warnings": false,
  "notify_system_info": false,
  "notify_service_started": false,
  "notify_service_stopped": false,
  "notify_service_execution_completed": false,
  "notify_payment_failed": true,
  "quiet_hours_start": "22:00:00",
  "quiet_hours_end": "08:00:00"
}
```

#### Update Notification Preferences
```http
PUT /api/v1/user/notification-preferences
Authorization: Bearer <token>
Content-Type: application/json

{
  "telegram_enabled": true,
  "telegram_bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
  "telegram_chat_id": "123456789",
  "email_enabled": false,
  "in_app_enabled": true,
  "notify_order_placed": true,
  "notify_order_rejected": false,
  "notify_order_modified": true,
  "notify_service_started": true,
  "quiet_hours_start": "22:00:00",
  "quiet_hours_end": "08:00:00"
}
```

**Response:** Same as GET endpoint.

**Note:** All fields are optional. Only provided fields will be updated. Set fields to `null` to clear them (e.g., `quiet_hours_start: null` to disable quiet hours).

#### Test Telegram Bot Configuration
```http
POST /api/v1/user/notification-preferences/telegram/test?bot_token=YOUR_TOKEN&chat_id=YOUR_CHAT_ID
Authorization: Bearer <token>
```

**Parameters (Query Params):**
- `bot_token` (str): Telegram bot token to test.
- `chat_id` (str): Telegram chat ID to test.

**Response:**
```json
{
  "success": true,
  "message": "Test message sent successfully! Check your Telegram chat."
}
```

### Notifications (In-App)

#### Get Notifications
```http
GET /api/v1/user/notifications?type=service&level=info&read=false&limit=50
Authorization: Bearer <token>
```

**Query Parameters:**
- `type` (optional): Filter by type (`service`, `trading`, `system`, `error`)
- `level` (optional): Filter by level (`info`, `warning`, `error`, `critical`)
- `read` (optional): Filter by read status (`true`/`false`)
- `limit` (optional): Maximum number of notifications (default: 100, max: 500)

**Response:**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "type": "service",
    "level": "info",
    "title": "Service Started",
    "message": "Service: Analysis\nStatus: Running\nProcess ID: 12345",
    "read": false,
    "telegram_sent": true,
    "email_sent": false,
    "created_at": "2025-01-15T10:00:00Z"
  }
]
```

#### Mark Notification as Read
```http
POST /api/v1/user/notifications/{notification_id}/read
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": 1,
  "read": true,
  "read_at": "2025-01-15T10:05:00Z"
}
```

#### Mark All Notifications as Read
```http
POST /api/v1/user/notifications/read-all
Authorization: Bearer <token>
```

**Response:**
```json
{
  "updated_count": 5
}
```

#### Get Unread Count
```http
GET /api/v1/user/notifications/count
Authorization: Bearer <token>
```

**Response:**
```json
{
  "count": 3
}
```

### Service Management

#### Get Service Status
```http
GET /api/v1/user/service/status
Authorization: Bearer <token>
```

#### Get Service Tasks
```http
GET /api/v1/user/service/tasks?limit=50
Authorization: Bearer <token>
```

#### Start Unified Service
```http
POST /api/v1/user/service/start
Authorization: Bearer <token>
```

#### Stop Unified Service
```http
POST /api/v1/user/service/stop
Authorization: Bearer <token>
```

#### Start Individual Service
```http
POST /api/v1/user/service/individual/start
Authorization: Bearer <token>
Content-Type: application/json

{
  "service_name": "analysis"
}
```

#### Stop Individual Service
```http
POST /api/v1/user/service/individual/stop
Authorization: Bearer <token>
Content-Type: application/json

{
  "service_name": "analysis"
}
```

### Admin Endpoints

**Note:** Admin endpoints require admin role.

#### List Users
```http
GET /api/v1/admin/users
Authorization: Bearer <admin_token>
```

Response includes optional `mobile_number` (account contact) per user.

#### Create User
```http
POST /api/v1/admin/users
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "Secret123!",
  "name": "User Name",
  "role": "user",
  "mobile_number": "9876543210"
}
```

`mobile_number` is optional (same 10-digit Indian validation as signup). Admin-created users are email-verified immediately.

#### Get ML Training Jobs
```http
GET /api/v1/admin/ml/jobs?status=running&limit=50
Authorization: Bearer <admin_token>
```

#### Start ML Training
```http
POST /api/v1/admin/ml/train
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "model_type": "verdict_classifier",
  "algorithm": "random_forest",
  "training_data_path": "data/ml/verdict_rows.csv",
  "hyperparameters": {},
  "notes": "v4 RF model",
  "auto_activate": true,
  "incremental_training": false,
  "training_run_end_date": "2026-06-22"
}
```

#### Get User Logs
```http
GET /api/v1/user/logs?level=ERROR&limit=100
Authorization: Bearer <token>
```

#### Get Admin Logs (across users)
```http
GET /api/v1/admin/logs?user_id=1&level=ERROR&limit=100
Authorization: Bearer <admin_token>
```

## Error Responses

### Standard Error Format

```json
{
  "detail": "Error message"
}
```

### HTTP Status Codes

- `200 OK` - Success
- `201 Created` - Resource created
- `400 Bad Request` - Invalid request
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (e.g., email already exists)
- `500 Internal Server Error` - Server error

### Example Error Response

```json
{
  "detail": "Invalid credentials"
}
```

## Rate Limiting

Currently, no rate limiting is implemented. Consider implementing for production use.

## Pagination

Some endpoints return paginated objects (with `items`, `total`, `page`, `page_size`, `total_pages`).

For these endpoints, use:

- `page`: Page number (1-based)
- `page_size`: Items per page

**Example:**
```http
GET /api/v1/user/orders/?page=2&page_size=20
```

## Filtering

Many endpoints support filtering via query parameters:

- Date ranges: `start_date`, `end_date`
- Status: `status` (varies by endpoint)
- Search: `search` (text search where applicable)

## Response Format

All responses are JSON. Dates are in ISO 8601 format (UTC).

## WebSocket (Future)

WebSocket support for real-time updates is planned but not yet implemented.
