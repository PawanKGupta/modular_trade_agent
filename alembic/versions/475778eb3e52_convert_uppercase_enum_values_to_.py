"""convert_uppercase_enum_values_to_lowercase

Revision ID: 475778eb3e52
Revises: aa11bb22cc33
Create Date: 2025-12-28 18:37:38.786383+00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "475778eb3e52"
down_revision = "aa11bb22cc33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert uppercase enum values in existing rows to lowercase."""
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # Update orders table
        op.execute(
            """
            UPDATE orders SET trade_mode = LOWER(trade_mode::text)::trademode
            WHERE trade_mode::text IN ('BROKER', 'PAPER');
            """
        )

        # Update usersettings table (if exists)
        op.execute(
            """
            UPDATE usersettings SET trade_mode = LOWER(trade_mode::text)::trademode
            WHERE trade_mode::text IN ('BROKER', 'PAPER');
            """
        )

        # Update users table
        op.execute(
            """
            UPDATE users SET role = LOWER(role::text)::userrole
            WHERE role::text IN ('ADMIN', 'USER');
            """
        )


def downgrade() -> None:
    """No downgrade needed - data normalization is permanent."""
    pass
