"""initial_setup

Revision ID: 0001
Revises: 
Create Date: 2026-05-18 00:00:00.000000

This is the base migration. Subsequent tasks will add tables here.
Run with:
    alembic upgrade head
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Enable PostgreSQL extensions required by the platform:
    - pgcrypto  : UUID generation and encryption helpers
    - pg_trgm   : trigram similarity for Arabic full-text search
    - vector    : pgvector — required for RAG / AI embeddings (TASK-004+)
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")  # pgvector for embeddings


def downgrade() -> None:
    """Drop extensions in reverse dependency order."""
    op.execute("DROP EXTENSION IF EXISTS vector;")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto;")
