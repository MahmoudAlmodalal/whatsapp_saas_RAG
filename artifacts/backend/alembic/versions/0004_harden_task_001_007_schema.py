"""harden_task_001_007_schema

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-18

Bring the TASK-001..TASK-007 schema to its final MVP baseline:
- expose SQL columns named `metadata` while keeping SQLAlchemy attributes
  named `meta_data` because `metadata` is reserved by Declarative models
- install tenant RLS policies through Alembic as well as the standalone SQL file
- leave users outside tenant RLS so email/password login works before tenant context
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TENANT_SCOPED_TABLES = (
    "conversations",
    "messages",
    "documents",
    "document_chunks",
)


def _rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = '{table_name}'
                      AND column_name = '{old_name}'
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = '{table_name}'
                      AND column_name = '{new_name}'
                ) THEN
                    ALTER TABLE {table_name} RENAME COLUMN {old_name} TO {new_name};
                END IF;
            END $$;
            """
        )
    )


def _create_tenant_policy(table_name: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;"))
    op.execute(sa.text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name};"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation ON {table_name}
                AS PERMISSIVE
                FOR ALL
                TO PUBLIC
                USING (
                    tenant_id = current_setting('app.current_tenant', TRUE)::uuid
                )
                WITH CHECK (
                    tenant_id = current_setting('app.current_tenant', TRUE)::uuid
                );
            """
        )
    )


def upgrade() -> None:
    _rename_column_if_needed("conversations", "meta_data", "metadata")
    _rename_column_if_needed("document_chunks", "meta_data", "metadata")

    for table_name in TENANT_SCOPED_TABLES:
        _create_tenant_policy(table_name)

    # Login looks up users before the app can safely set app.current_tenant.
    op.execute(sa.text("ALTER TABLE users NO FORCE ROW LEVEL SECURITY;"))
    op.execute(sa.text("ALTER TABLE users DISABLE ROW LEVEL SECURITY;"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE users ENABLE ROW LEVEL SECURITY;"))
    op.execute(sa.text("ALTER TABLE users FORCE ROW LEVEL SECURITY;"))

    for table_name in TENANT_SCOPED_TABLES:
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name};"))

    _rename_column_if_needed("conversations", "metadata", "meta_data")
    _rename_column_if_needed("document_chunks", "metadata", "meta_data")
