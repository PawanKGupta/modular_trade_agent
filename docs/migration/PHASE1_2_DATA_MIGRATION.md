# Phase 1.2: Data Migration Scripts

**Last Updated**: January 2025
**Status**: ✅ Complete

---

## Overview

This document describes the data migration scripts created in Phase 1.2 to migrate data from file-based storage to the database.

---

## Migration Scripts

### 1. `migrate_trades_history.py`

Migrates trades from `trades_history.json` to `Orders` and `Fills` tables.

**Source**: `data/trades_history.json`
**Target**: `orders` + `fills` tables

**Mapping**:
- Each trade → 1 buy order (always) + 1 sell order (if closed)
- Entry fill → 1 fill record for buy order
- Exit fill → 1 fill record for sell order (if closed)

**Usage**:
```bash
python scripts/migration/migrate_trades_history.py \
    --trades-history data/trades_history.json \
    --user-id 1 \
    [--dry-run]
```

**Features**:
- Handles both open and closed trades
- Extracts broker order IDs from order_response
- Deduplicates based on (symbol, entry_time, entry_price, qty)
- Validates required fields

---

### 2. `migrate_pending_orders.py`

Migrates pending orders from `pending_orders.json` to `Orders` table with AMO status.

**Source**: `data/pending_orders.json`
**Target**: `orders` table

**Mapping**:
- Each pending order → 1 order record
- Status mapping: PENDING → AMO, OPEN → ONGOING, EXECUTED → CLOSED

**Usage**:
```bash
python scripts/migration/migrate_pending_orders.py \
    --pending-orders data/pending_orders.json \
    --user-id 1 \
    [--dry-run]
```

**Features**:
- Maps pending order statuses to OrderStatus enum
- Stores broker_order_id for tracking
- Skips duplicates (checks existing broker_order_ids in DB)
- Handles missing optional fields

---

### 3. `migrate_paper_trading.py`

Migrates paper trading data to database.

**Sources**:
- `paper_trading/unified_service/orders.json` → `orders` table
- `paper_trading/unified_service/holdings.json` → `positions` table
- `paper_trading/unified_service/transactions.json` → `fills` table

**Usage**:
```bash
python scripts/migration/migrate_paper_trading.py \
    --paper-trading-dir paper_trading/unified_service \
    --user-id 1 \
    [--dry-run]
```

**Features**:
- Migrates orders, holdings, and transactions
- Maps paper trading statuses to OrderStatus enum
- Links transactions to orders by symbol, side, and timestamp
- Updates existing positions or creates new ones

---

### 4. `migrate_all_data.py`

Main orchestrator script that runs all migrations in the correct order.

**Usage**:
```bash
python scripts/migration/migrate_all_data.py \
    --user-id 1 \
    [--data-dir data] \
    [--paper-trading-dir paper_trading/unified_service] \
    [--dry-run]
```

**Process**:
1. Migrate `trades_history.json` → orders + fills
2. Migrate `pending_orders.json` → orders (AMO status)
3. Migrate paper trading data → orders + positions + fills
4. Print summary report

**Features**:
- Runs all migrations in sequence
- Provides comprehensive summary
- Supports dry-run mode
- Confirmation prompt for live runs

---

## Validation Scripts

### `validate_migration.py`

Validates that migrated data matches source files.

**Validations**:
- **trades_history**: Counts orders and fills, verifies each trade has at least 1 order
- **pending_orders**: Verifies all broker_order_ids exist in DB
- **paper_trading**: Validates orders, holdings, and transactions counts

**Usage**:
```bash
python scripts/migration/validate_migration.py \
    --user-id 1 \
    [--data-dir data] \
    [--paper-trading-dir paper_trading/unified_service]
```

**Output**:
- Validation status (✅ VALID / ❌ INVALID)
- Statistics (source vs DB counts)
- Errors and warnings

---

## Rollback Scripts

### `rollback_migration.py`

Removes migrated data from database.

**WARNING**: This will DELETE data from the database!

**Usage**:
```bash
python scripts/migration/rollback_migration.py \
    --user-id 1 \
    [--dry-run] \
    [--no-rollback-trades] \
    [--no-rollback-pending] \
    [--no-rollback-paper]
```

**Rollback Strategy**:
- **trades_history**: Deletes orders with `orig_source='signal'` and their fills
- **pending_orders**: Deletes orders with `broker_order_id` (excluding signal orders)
- **paper_trading**: Deletes orders with `orig_source='paper_trading'`, their fills, and positions

**Safety Features**:
- Requires confirmation (type 'DELETE')
- Supports dry-run mode
- Can selectively rollback specific migrations

---

## Data Deduplication

All migration scripts implement deduplication:

1. **trades_history**: Uses (symbol, entry_time, entry_price, qty) as unique key
2. **pending_orders**: Checks `broker_order_id` against existing DB records
3. **paper_trading**: Uses `order_id` to prevent duplicates

**Deduplication Strategy**:
- Track processed items in memory during migration
- Check existing DB records before inserting
- Skip duplicates with warning messages

---

## Error Handling

All scripts include comprehensive error handling:

- **File not found**: Logs error, continues with other files
- **Invalid JSON**: Logs error, returns statistics
- **Missing required fields**: Skips record, logs warning
- **Database errors**: Rolls back transaction, logs error
- **Validation errors**: Continues processing, collects all errors

**Error Reporting**:
- Errors collected in `stats['errors']` list
- Skipped records in `stats['skipped']` list
- Summary printed at end of migration

---

## Testing

Unit tests are available in:
- `tests/integration/test_data_migration.py`

**Test Coverage**:
- ✅ Empty file handling
- ✅ Single trade/order migration
- ✅ Closed trade migration (buy + sell)
- ✅ Duplicate detection
- ✅ Dry-run mode
- ✅ Validation
- ✅ Rollback

**Run Tests**:
```bash
pytest tests/integration/test_data_migration.py -v
```

---

## Migration Workflow

### Recommended Process

1. **Backup Data**:
   ```bash
   # Backup source files
   cp -r data data_backup
   cp -r paper_trading paper_trading_backup
   ```

2. **Dry Run**:
   ```bash
   python scripts/migration/migrate_all_data.py --user-id 1 --dry-run
   ```

3. **Review Results**:
   - Check statistics
   - Review errors and warnings
   - Verify counts match expectations

4. **Run Migration**:
   ```bash
   python scripts/migration/migrate_all_data.py --user-id 1
   ```

5. **Validate**:
   ```bash
   python scripts/migration/validate_migration.py --user-id 1
   ```

6. **If Issues, Rollback**:
   ```bash
   python scripts/migration/rollback_migration.py --user-id 1 --dry-run
   python scripts/migration/rollback_migration.py --user-id 1
   ```

---

## Data Mapping Reference

### trades_history.json → Orders

| Source Field | Target Field | Notes |
|-------------|--------------|-------|
| `symbol` | `symbol` | Cleaned (remove .NS, -EQ) |
| `entry_price` | `avg_price` | For buy order |
| `qty` | `quantity` | |
| `entry_time` | `placed_at`, `filled_at` | |
| `exit_price` | `avg_price` | For sell order |
| `exit_time` | `placed_at`, `filled_at`, `closed_at` | For sell order |
| `status` | `status` | open → ONGOING, closed → CLOSED |
| `order_response.orderId` | `broker_order_id` | If available |

### pending_orders.json → Orders

| Source Field | Target Field | Notes |
|-------------|--------------|-------|
| `order_id` | `broker_order_id` | |
| `symbol` | `symbol` | Cleaned |
| `qty` | `quantity` | |
| `order_type` | `order_type` | |
| `variety` | (not stored) | |
| `price` | `price` | 0.0 → None |
| `placed_at` | `placed_at` | |
| `status` | `status` | Mapped to OrderStatus enum |

### paper_trading/orders.json → Orders

| Source Field | Target Field | Notes |
|-------------|--------------|-------|
| `order_id` | `order_id` | Internal ID |
| `symbol` | `symbol` | Cleaned |
| `side` | `side` | |
| `quantity` | `quantity` | |
| `price` | `price` | |
| `order_type` | `order_type` | |
| `status` | `status` | Mapped to OrderStatus enum |
| `timestamp` | `placed_at` | |

### paper_trading/holdings.json → Positions

| Source Field | Target Field | Notes |
|-------------|--------------|-------|
| `symbol` (key) | `symbol` | Cleaned |
| `quantity` | `quantity` | |
| `avg_price` | `avg_price` | |
| `unrealized_pnl` | `unrealized_pnl` | |
| `opened_at` | `opened_at` | |

---

## Next Steps

1. ✅ **Phase 1.2 Complete**: All migration scripts created, tested, and documented
2. **Phase 1.3**: Repository layer updates
3. **Phase 1.4**: User configuration management

---

## References

- [Migration Plan](./UNIFIED_SERVICE_TO_MULTIUSER_MIGRATION_PLAN.md)
- [Database Schema](./PHASE1_DATABASE_SCHEMA.md)
