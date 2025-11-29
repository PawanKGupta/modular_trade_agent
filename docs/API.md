# API Documentation

Complete REST API reference for the Modular Trade Agent.

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
