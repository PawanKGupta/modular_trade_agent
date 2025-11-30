# API Documentation

Complete REST API reference for Rebound — Modular Trade Agent.

## Base URL

- **Development:** `http://localhost:8000/api`
- **Production:** `https://your-domain.com/api`

## Authentication

Most endpoints require authentication via JWT tokens.

### Getting a Token

```bash
POST /api/auth/login
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
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}
```

## Endpoints

### Authentication

#### Sign Up
```http
POST /api/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password",
  "name": "User Name"
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}
```

#### Get Current User
```http
GET /api/auth/me
Authorization: Bearer <token>
```

#### Refresh Token
```http
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}
```

### Trading Signals

#### Get Buying Zone
```http
GET /api/signals/buying-zone?limit=100&date_filter=2025-01-01&status_filter=active
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
POST /api/signals/reject
Authorization: Bearer <token>
Content-Type: application/json

{
  "symbol": "RELIANCE.NS"
}
```

### Orders

#### Get Orders
```http
GET /api/orders?limit=50&offset=0&status=open
Authorization: Bearer <token>
```

**Query Parameters:**
- `limit` (optional): Number of results
- `offset` (optional): Pagination offset
- `status` (optional): Filter by status (`open`, `filled`, `cancelled`)

#### Get Order by ID
```http
GET /api/orders/{order_id}
Authorization: Bearer <token>
```

### Targets

#### Get Targets
```http
GET /api/targets?status=active
Authorization: Bearer <token>
```

**Query Parameters:**
- `status` (optional): Filter by status

### P&L

#### Get P&L Summary
```http
GET /api/pnl/summary
Authorization: Bearer <token>
```

#### Get P&L History
```http
GET /api/pnl/history?start_date=2025-01-01&end_date=2025-01-31
Authorization: Bearer <token>
```

### Paper Trading

#### Execute Paper Trade
```http
POST /api/paper-trading/execute
Authorization: Bearer <token>
Content-Type: application/json

{
  "symbol": "RELIANCE.NS",
  "quantity": 10,
  "price": 2450.00,
  "transaction_type": "BUY"
}
```

#### Get Paper Trading History
```http
GET /api/paper-trading/history?limit=50
Authorization: Bearer <token>
```

#### Get Paper Trading Portfolio
```http
GET /api/paper-trading/portfolio
Authorization: Bearer <token>
```

### Trading Configuration

#### Get Trading Config
```http
GET /api/trading-config
Authorization: Bearer <token>
```

**Response:**
```json
{
  "rsi_period": 10,
  "ema9_period": 9,
  "ema200_period": 200,
  "min_volume_multiplier": 0.7,
  "user_capital": 200000.0,
  "max_position_volume_ratio": 0.10
}
```

#### Update Trading Config
```http
PUT /api/trading-config
Authorization: Bearer <token>
Content-Type: application/json

{
  "rsi_period": 10,
  "ema9_period": 9,
  "user_capital": 300000.0
}
```

### Broker Credentials

#### Get Broker Credentials
```http
GET /api/broker/credentials
Authorization: Bearer <token>
```

**Response:** (decrypted credentials)
```json
{
  "consumer_key": "xxx",
  "consumer_secret": "xxx",
  "access_token": "xxx",
  "user_id": "xxx"
}
```

#### Update Broker Credentials
```http
PUT /api/broker/credentials
Authorization: Bearer <token>
Content-Type: application/json

{
  "consumer_key": "xxx",
  "consumer_secret": "xxx",
  "access_token": "xxx",
  "user_id": "xxx"
}
```

**Note:** Credentials are encrypted before storage.

### Notification Preferences

#### Get Notification Preferences
```http
GET /api/v1/user/notification-preferences
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": 1,
  "user_id": 1,
  "telegram_enabled": true,
  "telegram_chat_id": "123456789",
  "email_enabled": false,
  "email_address": null,
  "in_app_enabled": true,
  "notify_order_placed": true,
  "notify_order_rejected": true,
  "notify_order_executed": true,
  "notify_order_cancelled": true,
  "notify_order_modified": false,
  "notify_retry_queue_added": true,
  "notify_retry_queue_updated": true,
  "notify_retry_queue_removed": true,
  "notify_retry_queue_retried": true,
  "notify_partial_fill": true,
  "notify_system_errors": true,
  "notify_system_warnings": false,
  "notify_system_info": false,
  "notify_service_started": true,
  "notify_service_stopped": true,
  "notify_service_execution_completed": true,
  "quiet_hours_start": "22:00:00",
  "quiet_hours_end": "08:00:00",
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

#### Update Notification Preferences
```http
PUT /api/v1/user/notification-preferences
Authorization: Bearer <token>
Content-Type: application/json

{
  "telegram_enabled": true,
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

**Note:** All fields are optional. Only provided fields will be updated. Set fields to `null` to clear them (e.g., `quiet_hours_start: null` to disable quiet hours).

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
PUT /api/v1/user/notifications/{notification_id}/read
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
PUT /api/v1/user/notifications/read-all
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
GET /api/v1/user/notifications/unread-count
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
GET /api/service/status
Authorization: Bearer <token>
```

#### Get Service Tasks
```http
GET /api/service/tasks?limit=50
Authorization: Bearer <token>
```

#### Run Service Task
```http
POST /api/service/run/{task_name}
Authorization: Bearer <token>
```

### Admin Endpoints

**Note:** Admin endpoints require admin role.

#### List Users
```http
GET /api/admin/users
Authorization: Bearer <admin_token>
```

#### Get ML Training Status
```http
GET /api/admin/ml/training
Authorization: Bearer <admin_token>
```

#### Start ML Training
```http
POST /api/admin/ml/train
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "model_version": "v4",
  "force_retrain": false
}
```

#### Get Logs
```http
GET /api/admin/logs?level=ERROR&limit=100
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

Endpoints that return lists support pagination:

- `limit`: Number of results per page (default: 50)
- `offset`: Number of results to skip (default: 0)

**Example:**
```http
GET /api/orders?limit=20&offset=40
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
