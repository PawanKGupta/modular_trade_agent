# Database Migration Scripts for v26.1.1 Schema Enhancements

**Date:** 2025-12-22
**Related Document:** RELEASE_PLAN_V26.1.1_DB_SCHEMA_ENHANCEMENTS.md

---

## 📋 Overview

This document provides detailed migration scripts for the database schema enhancements recommended for v26.1.1.

**Migration Order:**
1. Trade Mode Column (High Priority)
2. Exit Details in Positions (High Priority)
3. Portfolio Snapshots (High Priority)
4. Targets Table (Medium Priority)
5. P&L Calculation Audit (Medium Priority)
6. Historical Price Cache (Medium Priority)
7. Export Job Tracking (Low Priority)
8. Analytics Cache (Low Priority)

---

## 🔴 High Priority Migrations

### Migration 1: Add Trade Mode to Orders Table

**File:** `alembic/versions/XXXX_add_trade_mode_to_orders.py`

```python
"""Add trade_mode column to orders table

Revision ID: XXXX
Revises: YYYY
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'XXXX'
down_revision = 'YYYY'
branch_labels = None
depends_on = None


def upgrade():
    # Add trade_mode column (nullable for backward compatibility)
    op.add_column('orders', sa.Column('trade_mode', sa.String(16), nullable=True))

    # Create index for performance
    op.create_index('ix_orders_trade_mode', 'orders', ['trade_mode'])

    # Backfill trade_mode from user_settings
    # Note: This requires a data migration script (see below)
    # For now, column is nullable and will be populated by application code


def downgrade():
    op.drop_index('ix_orders_trade_mode', table_name='orders')
    op.drop_column('orders', 'trade_mode')
```

**Data Migration Script:** `scripts/backfill_trade_mode_to_orders.py`

```python
"""Backfill trade_mode column in orders table from user_settings"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from src.infrastructure.db.base import Base
from src.infrastructure.db.models import TradeMode
from src.infrastructure.db.session import get_db_session


def backfill_trade_mode():
    """Backfill trade_mode for existing orders"""
    session = next(get_db_session())

    try:
        # Get all users with their trade_mode
        users_query = text("""
            SELECT u.id, us.trade_mode
            FROM users u
            JOIN user_settings us ON u.id = us.user_id
        """)

        users = session.execute(users_query).fetchall()

        updated_count = 0
        for user_id, trade_mode in users:
            if trade_mode:
                # Update all orders for this user
                update_query = text("""
                    UPDATE orders
                    SET trade_mode = :trade_mode
                    WHERE user_id = :user_id AND trade_mode IS NULL
                """)

                result = session.execute(
                    update_query,
                    {"trade_mode": trade_mode, "user_id": user_id}
                )
                updated_count += result.rowcount

        session.commit()
        print(f"✅ Backfilled trade_mode for {updated_count} orders")

    except Exception as e:
        session.rollback()
        print(f"❌ Error backfilling trade_mode: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    backfill_trade_mode()
```

---

### Migration 2: Add Exit Details to Positions Table

**File:** `alembic/versions/XXXX_add_exit_details_to_positions.py`

```python
"""Add exit details columns to positions table

Revision ID: XXXX
Revises: YYYY
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'XXXX'
down_revision = 'YYYY'
branch_labels = None
depends_on = None


def upgrade():
    # Add exit detail columns (all nullable for backward compatibility)
    op.add_column('positions', sa.Column('exit_price', sa.Float(), nullable=True))
    op.add_column('positions', sa.Column('exit_reason', sa.String(64), nullable=True))
    op.add_column('positions', sa.Column('exit_rsi', sa.Float(), nullable=True))
    op.add_column('positions', sa.Column('realized_pnl', sa.Float(), nullable=True))
    op.add_column('positions', sa.Column('realized_pnl_pct', sa.Float(), nullable=True))
    op.add_column('positions', sa.Column('sell_order_id', sa.Integer(), nullable=True))

    # Add foreign key constraint for sell_order_id
    op.create_foreign_key(
        'fk_positions_sell_order_id',
        'positions', 'orders',
        ['sell_order_id'], ['id']
    )

    # Create index for exit_reason (for analytics queries)
    op.create_index('ix_positions_exit_reason', 'positions', ['exit_reason'])

    # Note: Backfill script needed (see below)


def downgrade():
    op.drop_index('ix_positions_exit_reason', table_name='positions')
    op.drop_constraint('fk_positions_sell_order_id', 'positions', type_='foreignkey')
    op.drop_column('positions', 'sell_order_id')
    op.drop_column('positions', 'realized_pnl_pct')
    op.drop_column('positions', 'realized_pnl')
    op.drop_column('positions', 'exit_rsi')
    op.drop_column('positions', 'exit_reason')
    op.drop_column('positions', 'exit_price')
```

**Data Migration Script:** `scripts/backfill_exit_details_to_positions.py`

```python
"""Backfill exit details for closed positions from orders table"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from src.infrastructure.db.session import get_db_session


def backfill_exit_details():
    """Backfill exit details for existing closed positions"""
    session = next(get_db_session())

    try:
        # Find closed positions and their corresponding sell orders
        # Match by symbol, user_id, and timestamp proximity
        backfill_query = text("""
            UPDATE positions p
            SET
                exit_price = (
                    SELECT o.execution_price
                    FROM orders o
                    WHERE o.user_id = p.user_id
                        AND o.symbol = p.symbol
                        AND o.side = 'sell'
                        AND o.status = 'CLOSED'
                        AND o.execution_time >= p.closed_at - INTERVAL '1 hour'
                        AND o.execution_time <= p.closed_at + INTERVAL '1 hour'
                    ORDER BY ABS(EXTRACT(EPOCH FROM (o.execution_time - p.closed_at)))
                    LIMIT 1
                ),
                sell_order_id = (
                    SELECT o.id
                    FROM orders o
                    WHERE o.user_id = p.user_id
                        AND o.symbol = p.symbol
                        AND o.side = 'sell'
                        AND o.status = 'CLOSED'
                        AND o.execution_time >= p.closed_at - INTERVAL '1 hour'
                        AND o.execution_time <= p.closed_at + INTERVAL '1 hour'
                    ORDER BY ABS(EXTRACT(EPOCH FROM (o.execution_time - p.closed_at)))
                    LIMIT 1
                ),
                exit_reason = (
                    SELECT
                        CASE
                            WHEN o.order_metadata->>'exit_note' LIKE '%EMA9%' THEN 'EMA9_TARGET'
                            WHEN o.order_metadata->>'exit_note' LIKE '%RSI%' THEN 'RSI_EXIT'
                            WHEN o.order_metadata->>'exit_note' LIKE '%MANUAL%' THEN 'MANUAL'
                            ELSE 'UNKNOWN'
                        END
                    FROM orders o
                    WHERE o.user_id = p.user_id
                        AND o.symbol = p.symbol
                        AND o.side = 'sell'
                        AND o.status = 'CLOSED'
                        AND o.execution_time >= p.closed_at - INTERVAL '1 hour'
                        AND o.execution_time <= p.closed_at + INTERVAL '1 hour'
                    ORDER BY ABS(EXTRACT(EPOCH FROM (o.execution_time - p.closed_at)))
                    LIMIT 1
                ),
                realized_pnl = (
                    SELECT (o.execution_price - p.avg_price) * p.quantity
                    FROM orders o
                    WHERE o.user_id = p.user_id
                        AND o.symbol = p.symbol
                        AND o.side = 'sell'
                        AND o.status = 'CLOSED'
                        AND o.execution_time >= p.closed_at - INTERVAL '1 hour'
                        AND o.execution_time <= p.closed_at + INTERVAL '1 hour'
                    ORDER BY ABS(EXTRACT(EPOCH FROM (o.execution_time - p.closed_at)))
                    LIMIT 1
                )
            WHERE p.closed_at IS NOT NULL
                AND p.exit_price IS NULL
        """)

        result = session.execute(backfill_query)
        updated_count = result.rowcount

        # Calculate realized_pnl_pct
        update_pct_query = text("""
            UPDATE positions
            SET realized_pnl_pct = (realized_pnl / (avg_price * quantity)) * 100
            WHERE closed_at IS NOT NULL
                AND exit_price IS NOT NULL
                AND realized_pnl IS NOT NULL
                AND realized_pnl_pct IS NULL
        """)

        session.execute(update_pct_query)
        session.commit()

        print(f"✅ Backfilled exit details for {updated_count} closed positions")

    except Exception as e:
        session.rollback()
        print(f"❌ Error backfilling exit details: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    backfill_exit_details()
```

---

### Migration 3: Create Portfolio Snapshots Table

**File:** `alembic/versions/XXXX_add_portfolio_snapshots.py`

```python
"""Create portfolio_snapshots table

Revision ID: XXXX
Revises: YYYY
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'XXXX'
down_revision = 'YYYY'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'portfolio_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('total_value', sa.Float(), nullable=False),
        sa.Column('invested_value', sa.Float(), nullable=False),
        sa.Column('available_cash', sa.Float(), nullable=False),
        sa.Column('unrealized_pnl', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('realized_pnl', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('open_positions_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('closed_positions_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_return', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('daily_return', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('snapshot_type', sa.String(16), nullable=False, server_default='eod'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', 'snapshot_type', name='uq_portfolio_snapshot_user_date_type')
    )

    # Create indexes
    op.create_index('ix_portfolio_snapshot_user_date', 'portfolio_snapshots', ['user_id', 'date'])
    op.create_index('ix_portfolio_snapshots_user_id', 'portfolio_snapshots', ['user_id'])


def downgrade():
    op.drop_index('ix_portfolio_snapshots_user_id', table_name='portfolio_snapshots')
    op.drop_index('ix_portfolio_snapshot_user_date', table_name='portfolio_snapshots')
    op.drop_table('portfolio_snapshots')
```

**Initial Snapshot Creation Script:** `scripts/create_initial_portfolio_snapshots.py`

```python
"""Create initial portfolio snapshots from existing positions and orders"""
import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.infrastructure.db.session import get_db_session
from src.infrastructure.db.models import PortfolioSnapshot


def create_initial_snapshots():
    """Create portfolio snapshots for last 30 days from existing data"""
    session = next(get_db_session())

    try:
        # Get all users
        users = session.execute(text("SELECT id FROM users")).fetchall()

        created_count = 0
        for (user_id,) in users:
            # Get user's initial capital (from user_trading_config or default)
            capital_query = text("""
                SELECT user_capital, paper_trading_initial_capital
                FROM user_trading_config
                WHERE user_id = :user_id
            """)
            capital_result = session.execute(capital_query, {"user_id": user_id}).fetchone()

            if capital_result:
                initial_capital = capital_result[1] if capital_result[1] else capital_result[0]
            else:
                initial_capital = 100000.0  # Default

            # Create snapshots for last 30 days
            today = date.today()
            for days_ago in range(30, -1, -1):
                snapshot_date = today - timedelta(days=days_ago)

                # Check if snapshot already exists
                existing = session.execute(
                    text("""
                        SELECT id FROM portfolio_snapshots
                        WHERE user_id = :user_id AND date = :date AND snapshot_type = 'eod'
                    """),
                    {"user_id": user_id, "date": snapshot_date}
                ).fetchone()

                if existing:
                    continue

                # Calculate portfolio value for this date
                # (Simplified - would need actual calculation from positions/orders)
                snapshot = PortfolioSnapshot(
                    user_id=user_id,
                    date=snapshot_date,
                    total_value=initial_capital,  # Placeholder - needs actual calculation
                    invested_value=0.0,
                    available_cash=initial_capital,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0,
                    open_positions_count=0,
                    closed_positions_count=0,
                    total_return=0.0,
                    daily_return=0.0,
                    snapshot_type='eod'
                )

                session.add(snapshot)
                created_count += 1

        session.commit()
        print(f"✅ Created {created_count} initial portfolio snapshots")

    except Exception as e:
        session.rollback()
        print(f"❌ Error creating snapshots: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    create_initial_snapshots()
```

---

## 🟡 Medium Priority Migrations

### Migration 4: Create Targets Table

**File:** `alembic/versions/XXXX_add_targets_table.py`

```python
"""Create targets table

Revision ID: XXXX
Revises: YYYY
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'XXXX'
down_revision = 'YYYY'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'targets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('position_id', sa.Integer(), nullable=True),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('target_price', sa.Float(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('current_price', sa.Float(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('distance_to_target', sa.Float(), nullable=True),
        sa.Column('distance_to_target_absolute', sa.Float(), nullable=True),
        sa.Column('target_type', sa.String(32), nullable=False, server_default='ema9'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('trade_mode', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('achieved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['position_id'], ['positions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_targets_user_symbol_active', 'targets', ['user_id', 'symbol', 'is_active'])
    op.create_index('ix_targets_position', 'targets', ['position_id'])
    op.create_index('ix_targets_user_id', 'targets', ['user_id'])


def downgrade():
    op.drop_index('ix_targets_user_id', table_name='targets')
    op.drop_index('ix_targets_position', table_name='targets')
    op.drop_index('ix_targets_user_symbol_active', table_name='targets')
    op.drop_table('targets')
```

---

### Migration 5: Create P&L Calculation Audit Table

**File:** `alembic/versions/XXXX_add_pnl_calculation_audit.py`

```python
"""Create pnl_calculation_audit table

Revision ID: XXXX
Revises: YYYY
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'XXXX'
down_revision = 'YYYY'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pnl_calculation_audit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('calculation_type', sa.String(32), nullable=False),
        sa.Column('date_range_start', sa.Date(), nullable=True),
        sa.Column('date_range_end', sa.Date(), nullable=True),
        sa.Column('positions_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('orders_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pnl_records_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pnl_records_updated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duration_seconds', sa.Float(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('error_message', sa.String(512), nullable=True),
        sa.Column('triggered_by', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index
    op.create_index('ix_pnl_audit_user_created', 'pnl_calculation_audit', ['user_id', 'created_at'])


def downgrade():
    op.drop_index('ix_pnl_audit_user_created', table_name='pnl_calculation_audit')
    op.drop_table('pnl_calculation_audit')
```

---

### Migration 6: Create Price Cache Table

**File:** `alembic/versions/XXXX_add_price_cache.py`

```python
"""Create price_cache table

Revision ID: XXXX
Revises: YYYY
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'XXXX'
down_revision = 'YYYY'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'price_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('open', sa.Float(), nullable=True),
        sa.Column('high', sa.Float(), nullable=True),
        sa.Column('low', sa.Float(), nullable=True),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(32), nullable=False, server_default='yfinance'),
        sa.Column('cached_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', 'date', name='uq_price_cache_symbol_date')
    )

    # Create indexes
    op.create_index('ix_price_cache_symbol_date', 'price_cache', ['symbol', 'date'])
    op.create_index('ix_price_cache_symbol', 'price_cache', ['symbol'])


def downgrade():
    op.drop_index('ix_price_cache_symbol', table_name='price_cache')
    op.drop_index('ix_price_cache_symbol_date', table_name='price_cache')
    op.drop_table('price_cache')
```

---

## 🟢 Low Priority Migrations

### Migration 7: Create Export Jobs Table

**File:** `alembic/versions/XXXX_add_export_jobs.py`

```python
"""Create export_jobs table

Revision ID: XXXX
Revises: YYYY
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'XXXX'
down_revision = 'YYYY'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'export_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('export_type', sa.String(32), nullable=False),
        sa.Column('data_type', sa.String(32), nullable=False),
        sa.Column('date_range_start', sa.Date(), nullable=True),
        sa.Column('date_range_end', sa.Date(), nullable=True),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('file_path', sa.String(512), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('records_exported', sa.Integer(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('error_message', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index
    op.create_index('ix_export_jobs_user_status_created', 'export_jobs', ['user_id', 'status', 'created_at'])


def downgrade():
    op.drop_index('ix_export_jobs_user_status_created', table_name='export_jobs')
    op.drop_table('export_jobs')
```

---

### Migration 8: Create Analytics Cache Table

**File:** `alembic/versions/XXXX_add_analytics_cache.py`

```python
"""Create analytics_cache table

Revision ID: XXXX
Revises: YYYY
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'XXXX'
down_revision = 'YYYY'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'analytics_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('cache_key', sa.String(128), nullable=False),
        sa.Column('analytics_type', sa.String(32), nullable=False),
        sa.Column('date_range_start', sa.Date(), nullable=True),
        sa.Column('date_range_end', sa.Date(), nullable=True),
        sa.Column('cached_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('calculated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'cache_key', name='uq_analytics_cache_user_key')
    )

    # Create indexes
    op.create_index('ix_analytics_cache_user_type', 'analytics_cache', ['user_id', 'analytics_type'])
    op.create_index('ix_analytics_cache_key', 'analytics_cache', ['cache_key'])


def downgrade():
    op.drop_index('ix_analytics_cache_key', table_name='analytics_cache')
    op.drop_index('ix_analytics_cache_user_type', table_name='analytics_cache')
    op.drop_table('analytics_cache')
```

---

## 📝 Migration Execution Guide

### Step 1: Create Migrations

1. Generate migration files using Alembic:
```bash
cd <project_root>
alembic revision -m "add_trade_mode_to_orders"
alembic revision -m "add_exit_details_to_positions"
alembic revision -m "add_portfolio_snapshots"
# ... etc
```

2. Copy migration code from this document into generated files

### Step 2: Test Migrations

```bash
# Test upgrade
alembic upgrade head

# Test downgrade
alembic downgrade -1

# Verify schema
alembic current
```

### Step 3: Run Data Migrations

```bash
# Run backfill scripts
python scripts/backfill_trade_mode_to_orders.py
python scripts/backfill_exit_details_to_positions.py
python scripts/create_initial_portfolio_snapshots.py
```

### Step 4: Verify Data

```sql
-- Check trade_mode backfill
SELECT COUNT(*) FROM orders WHERE trade_mode IS NULL;

-- Check exit details backfill
SELECT COUNT(*) FROM positions WHERE closed_at IS NOT NULL AND exit_price IS NULL;

-- Check portfolio snapshots
SELECT COUNT(*) FROM portfolio_snapshots;
```

---

## ⚠️ Important Notes

1. **Backup Database First**: Always backup before running migrations
2. **Test on Staging**: Test all migrations on staging environment first
3. **Run During Low Traffic**: Schedule migrations during low-traffic periods
4. **Monitor Performance**: Watch for performance impact after migrations
5. **Rollback Plan**: Keep rollback scripts ready

---

**Last Updated:** 2025-12-22
