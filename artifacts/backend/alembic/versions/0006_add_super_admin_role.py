"""0006_add_super_admin_role.py
──────────────────────────────────────────────────────────
Add 'super_admin' to the user_role_enum PostgreSQL enum type.

PostgreSQL does not allow removing enum values, but adding is safe.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_add_super_admin_role"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: add new value to existing enum — must be done outside a transaction
    op.execute("ALTER TYPE user_role_enum ADD VALUE IF NOT EXISTS 'super_admin'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values — document the limitation
    # To fully revert: recreate the enum without super_admin and update the column
    # For now, this is a no-op downgrade (safe — just leave the value in the enum)
    pass
