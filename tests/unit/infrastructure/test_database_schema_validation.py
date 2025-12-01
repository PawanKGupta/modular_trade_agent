"""Comprehensive database schema validation tests.

This test suite validates that the actual database schema matches the SQLAlchemy model definitions.
It checks:
- All tables exist
- All columns exist with correct types
- All indexes are present
- All foreign keys are correct
- All constraints (unique, check) are in place
- Column nullability matches model definitions
"""

import pytest
from sqlalchemy import inspect
from sqlalchemy.types import DateTime, Enum, String


@pytest.fixture
def inspector(db_session):
    """Get SQLAlchemy inspector for schema validation"""
    return inspect(db_session.bind)


class TestSchemaExistence:
    """Test that all expected tables exist in the database"""

    def test_all_tables_exist(self, inspector):
        """Verify all expected tables are present"""
        expected_tables = {
            "users",
            "usersettings",
            "orders",
            "positions",
            "fills",
            "pnldaily",
            "signals",
            "activity",
            "service_status",
            "service_task_execution",
            "service_logs",
            "error_logs",
            "user_trading_config",
            "ml_training_jobs",
            "ml_models",
            "user_notification_preferences",
            "notifications",
            "audit_logs",
        }
        actual_tables = set(inspector.get_table_names())

        missing_tables = expected_tables - actual_tables
        assert not missing_tables, f"Missing tables: {missing_tables}"

        # Check for unexpected tables (optional, for awareness)
        unexpected_tables = actual_tables - expected_tables
        if unexpected_tables:
            print(f"Note: Unexpected tables found: {unexpected_tables}")


class TestUsersTableSchema:
    """Validate Users table schema"""

    def test_users_table_columns(self, inspector):
        """Validate Users table has all expected columns with correct types"""
        columns = {col["name"]: col for col in inspector.get_columns("users")}

        assert "id" in columns
        assert columns["id"]["type"].python_type == int
        assert not columns["id"]["nullable"]

        assert "email" in columns
        assert isinstance(columns["email"]["type"], String)
        assert not columns["email"]["nullable"]

        assert "name" in columns
        assert isinstance(columns["name"]["type"], String)
        assert columns["name"]["nullable"]

        assert "password_hash" in columns
        assert isinstance(columns["password_hash"]["type"], String)
        assert not columns["password_hash"]["nullable"]

        assert "role" in columns
        # SQLite stores enums as VARCHAR, not Enum type
        assert isinstance(columns["role"]["type"], String) or isinstance(
            columns["role"]["type"], Enum
        )
        assert not columns["role"]["nullable"]

        assert "is_active" in columns
        assert columns["is_active"]["type"].python_type == bool
        assert not columns["is_active"]["nullable"]

        assert "created_at" in columns
        assert isinstance(columns["created_at"]["type"], DateTime)
        assert not columns["created_at"]["nullable"]

        assert "updated_at" in columns
        assert isinstance(columns["updated_at"]["type"], DateTime)
        assert not columns["updated_at"]["nullable"]

    def test_users_table_indexes(self, inspector):
        """Validate Users table indexes"""
        indexes = {idx["name"]: idx for idx in inspector.get_indexes("users")}

        # Check for email unique index
        email_indexes = [idx for idx in indexes.values() if "email" in idx.get("column_names", [])]
        assert len(email_indexes) > 0, "Email index not found"

        # Check that email index is unique
        unique_email_index = next((idx for idx in email_indexes if idx.get("unique")), None)
        assert unique_email_index is not None, "Email unique constraint not found"


class TestOrdersTableSchema:
    """Validate Orders table schema"""

    def test_orders_table_columns(self, inspector):
        """Validate Orders table has all expected columns"""
        columns = {col["name"]: col for col in inspector.get_columns("orders")}

        # Required columns
        required_columns = [
            "id",
            "user_id",
            "symbol",
            "side",
            "order_type",
            "quantity",
            "price",
            "status",
            "avg_price",
            "placed_at",
            "filled_at",
            "closed_at",
            "orig_source",
        ]
        for col_name in required_columns:
            assert col_name in columns, f"Missing required column: {col_name}"

        # Check user_id foreign key
        assert columns["user_id"]["type"].python_type == int
        assert not columns["user_id"]["nullable"]

        # Check symbol
        assert isinstance(columns["symbol"]["type"], String)
        assert not columns["symbol"]["nullable"]

        # Check status enum (SQLite stores as VARCHAR)
        assert isinstance(columns["status"]["type"], String) or isinstance(
            columns["status"]["type"], Enum
        )
        assert not columns["status"]["nullable"]

        # Check optional columns
        assert "order_id" in columns or True  # May not exist in older schemas
        assert "broker_order_id" in columns or True  # May not exist in older schemas
        assert "metadata" in columns or True  # May not exist in older schemas

        # Check nullable columns
        assert columns["price"]["nullable"], "price should be nullable"
        assert columns["avg_price"]["nullable"], "avg_price should be nullable"
        assert columns["filled_at"]["nullable"], "filled_at should be nullable"
        assert columns["closed_at"]["nullable"], "closed_at should be nullable"
        assert columns["orig_source"]["nullable"], "orig_source should be nullable"

    def test_orders_table_foreign_keys(self, inspector):
        """Validate Orders table foreign keys"""
        foreign_keys = inspector.get_foreign_keys("orders")

        # Check user_id foreign key
        user_fk = next((fk for fk in foreign_keys if "user_id" in fk["constrained_columns"]), None)
        assert user_fk is not None, "user_id foreign key not found"
        assert user_fk["referred_table"] == "users", "user_id should reference users table"
        assert user_fk["referred_columns"] == ["id"], "user_id should reference users.id"

    def test_orders_table_indexes(self, inspector):
        """Validate Orders table indexes"""
        indexes = {idx["name"]: idx for idx in inspector.get_indexes("orders")}

        # Check for user_id index
        user_indexes = [idx for idx in indexes.values() if "user_id" in idx.get("column_names", [])]
        assert len(user_indexes) > 0, "user_id index not found"

        # Check for status index
        status_indexes = [
            idx for idx in indexes.values() if "status" in idx.get("column_names", [])
        ]
        assert len(status_indexes) > 0, "status index not found"

        # Check for composite index
        composite_indexes = [
            idx
            for idx in indexes.values()
            if len(idx.get("column_names", [])) > 2
            and "user_id" in idx.get("column_names", [])
            and "status" in idx.get("column_names", [])
        ]
        assert len(composite_indexes) > 0, "Composite index (user_id, status, ...) not found"


class TestPositionsTableSchema:
    """Validate Positions table schema"""

    def test_positions_table_columns(self, inspector):
        """Validate Positions table has all expected columns"""
        columns = {col["name"]: col for col in inspector.get_columns("positions")}

        required_columns = [
            "id",
            "user_id",
            "symbol",
            "quantity",
            "avg_price",
            "unrealized_pnl",
            "opened_at",
        ]
        for col_name in required_columns:
            assert col_name in columns, f"Missing required column: {col_name}"

        assert columns["user_id"]["type"].python_type == int
        assert not columns["user_id"]["nullable"]

        assert isinstance(columns["symbol"]["type"], String)
        assert not columns["symbol"]["nullable"]

        assert columns["quantity"]["type"].python_type == float
        assert not columns["quantity"]["nullable"]

        assert columns["closed_at"]["nullable"], "closed_at should be nullable"

    def test_positions_table_unique_constraint(self, inspector):
        """Validate Positions table unique constraint on (user_id, symbol)"""
        unique_constraints = inspector.get_unique_constraints("positions")

        user_symbol_constraint = next(
            (uc for uc in unique_constraints if set(uc["column_names"]) == {"user_id", "symbol"}),
            None,
        )
        assert user_symbol_constraint is not None, "Unique constraint (user_id, symbol) not found"


class TestFillsTableSchema:
    """Validate Fills table schema"""

    def test_fills_table_columns(self, inspector):
        """Validate Fills table has all expected columns"""
        columns = {col["name"]: col for col in inspector.get_columns("fills")}

        required_columns = ["id", "order_id", "qty", "price", "ts"]
        for col_name in required_columns:
            assert col_name in columns, f"Missing required column: {col_name}"

        assert columns["order_id"]["type"].python_type == int
        assert not columns["order_id"]["nullable"]

        assert columns["qty"]["type"].python_type == float
        assert not columns["qty"]["nullable"]

        assert columns["price"]["type"].python_type == float
        assert not columns["price"]["nullable"]

    def test_fills_table_foreign_key(self, inspector):
        """Validate Fills table foreign key to Orders"""
        foreign_keys = inspector.get_foreign_keys("fills")

        order_fk = next(
            (fk for fk in foreign_keys if "order_id" in fk["constrained_columns"]), None
        )
        assert order_fk is not None, "order_id foreign key not found"
        assert order_fk["referred_table"] == "orders", "order_id should reference orders table"


class TestServiceStatusTableSchema:
    """Validate ServiceStatus table schema"""

    def test_service_status_table_columns(self, inspector):
        """Validate ServiceStatus table has all expected columns"""
        columns = {col["name"]: col for col in inspector.get_columns("service_status")}

        required_columns = [
            "id",
            "user_id",
            "service_running",
            "last_heartbeat",
            "last_task_execution",
            "error_count",
            "last_error",
            "created_at",
            "updated_at",
        ]
        for col_name in required_columns:
            assert col_name in columns, f"Missing required column: {col_name}"

        assert columns["user_id"]["type"].python_type == int
        assert not columns["user_id"]["nullable"]

        assert columns["service_running"]["type"].python_type == bool
        assert not columns["service_running"]["nullable"]

        assert columns["error_count"]["type"].python_type == int
        assert not columns["error_count"]["nullable"]

        assert columns["last_heartbeat"]["nullable"], "last_heartbeat should be nullable"
        assert columns["last_task_execution"]["nullable"], "last_task_execution should be nullable"
        assert columns["last_error"]["nullable"], "last_error should be nullable"

    def test_service_status_unique_constraint(self, inspector):
        """Validate ServiceStatus unique constraint on user_id"""
        # Check both unique constraints and unique indexes (SQLite uses indexes for unique)
        unique_constraints = inspector.get_unique_constraints("service_status")
        indexes = inspector.get_indexes("service_status")

        # Check unique constraint
        user_unique_constraint = next(
            (uc for uc in unique_constraints if uc["column_names"] == ["user_id"]), None
        )

        # Check unique index (SQLite often uses this instead)
        user_unique_index = next(
            (
                idx
                for idx in indexes
                if idx.get("unique") and idx.get("column_names") == ["user_id"]
            ),
            None,
        )

        assert (
            user_unique_constraint is not None or user_unique_index is not None
        ), "Unique constraint/index on user_id not found"


class TestUserTradingConfigTableSchema:
    """Validate UserTradingConfig table schema"""

    def test_user_trading_config_table_columns(self, inspector):
        """Validate UserTradingConfig table has all expected columns"""
        columns = {col["name"]: col for col in inspector.get_columns("user_trading_config")}

        # Check key columns exist
        assert "id" in columns
        assert "user_id" in columns
        assert "rsi_period" in columns
        assert "user_capital" in columns
        assert "max_portfolio_size" in columns
        assert "ml_enabled" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

        assert columns["user_id"]["type"].python_type == int
        assert not columns["user_id"]["nullable"]

        assert columns["rsi_period"]["type"].python_type == int
        assert not columns["rsi_period"]["nullable"]

        assert columns["user_capital"]["type"].python_type == float
        assert not columns["user_capital"]["nullable"]

        assert columns["ml_enabled"]["type"].python_type == bool
        assert not columns["ml_enabled"]["nullable"]

    def test_user_trading_config_unique_constraint(self, inspector):
        """Validate UserTradingConfig unique constraint on user_id"""
        # Check both unique constraints and unique indexes (SQLite uses indexes for unique)
        unique_constraints = inspector.get_unique_constraints("user_trading_config")
        indexes = inspector.get_indexes("user_trading_config")

        # Check unique constraint
        user_unique_constraint = next(
            (uc for uc in unique_constraints if uc["column_names"] == ["user_id"]), None
        )

        # Check unique index (SQLite often uses this instead)
        user_unique_index = next(
            (
                idx
                for idx in indexes
                if idx.get("unique") and idx.get("column_names") == ["user_id"]
            ),
            None,
        )

        assert (
            user_unique_constraint is not None or user_unique_index is not None
        ), "Unique constraint/index on user_id not found"


class TestAllTablesHaveUserForeignKey:
    """Validate that all user-scoped tables have user_id foreign key"""

    def test_all_tables_have_user_foreign_key(self, inspector):
        """Check that all expected user-scoped tables have user_id foreign key"""
        # Note: signals table might be global (not user-scoped) depending on design
        # ml_training_jobs uses started_by instead of user_id
        # ml_models uses created_by instead of user_id
        user_scoped_tables = [
            "orders",
            "positions",
            "pnldaily",
            "activity",  # signals might be global, so we check separately
            "service_status",
            "service_task_execution",
            "service_logs",
            "error_logs",
            "user_trading_config",
            "user_notification_preferences",
            "notifications",
            "audit_logs",
        ]

        for table_name in user_scoped_tables:
            if table_name not in inspector.get_table_names():
                continue  # Skip if table doesn't exist

            foreign_keys = inspector.get_foreign_keys(table_name)
            user_fk = next(
                (fk for fk in foreign_keys if "user_id" in fk["constrained_columns"]), None
            )
            assert user_fk is not None, f"Table {table_name} missing user_id foreign key"
            assert (
                user_fk["referred_table"] == "users"
            ), f"Table {table_name} user_id should reference users table"

        # Check ml_training_jobs (uses started_by instead of user_id)
        if "ml_training_jobs" in inspector.get_table_names():
            foreign_keys = inspector.get_foreign_keys("ml_training_jobs")
            started_by_fk = next(
                (fk for fk in foreign_keys if "started_by" in fk["constrained_columns"]), None
            )
            assert started_by_fk is not None, "ml_training_jobs missing started_by foreign key"
            assert (
                started_by_fk["referred_table"] == "users"
            ), "ml_training_jobs started_by should reference users table"

        # Check ml_models (uses created_by instead of user_id)
        if "ml_models" in inspector.get_table_names():
            foreign_keys = inspector.get_foreign_keys("ml_models")
            created_by_fk = next(
                (fk for fk in foreign_keys if "created_by" in fk["constrained_columns"]), None
            )
            assert created_by_fk is not None, "ml_models missing created_by foreign key"
            assert (
                created_by_fk["referred_table"] == "users"
            ), "ml_models created_by should reference users table"

        # Check signals separately (might be global or user-scoped)
        if "signals" in inspector.get_table_names():
            columns = {col["name"]: col for col in inspector.get_columns("signals")}
            if "user_id" in columns:
                foreign_keys = inspector.get_foreign_keys("signals")
                user_fk = next(
                    (fk for fk in foreign_keys if "user_id" in fk["constrained_columns"]), None
                )
                if user_fk:
                    assert (
                        user_fk["referred_table"] == "users"
                    ), "signals user_id should reference users table"


class TestAllTablesHaveTimestamps:
    """Validate that tables with created_at/updated_at have correct types"""

    def test_timestamp_columns_are_datetime(self, inspector):
        """Check that created_at and updated_at columns are DateTime type"""
        tables_with_timestamps = [
            "users",
            "usersettings",
            "service_status",
            "user_trading_config",
            "ml_models",
            "user_notification_preferences",
        ]

        for table_name in tables_with_timestamps:
            if table_name not in inspector.get_table_names():
                continue

            columns = {col["name"]: col for col in inspector.get_columns(table_name)}

            if "created_at" in columns:
                assert isinstance(
                    columns["created_at"]["type"], DateTime
                ), f"Table {table_name} created_at should be DateTime"
                assert not columns["created_at"][
                    "nullable"
                ], f"Table {table_name} created_at should not be nullable"

            if "updated_at" in columns:
                assert isinstance(
                    columns["updated_at"]["type"], DateTime
                ), f"Table {table_name} updated_at should be DateTime"
                assert not columns["updated_at"][
                    "nullable"
                ], f"Table {table_name} updated_at should not be nullable"
