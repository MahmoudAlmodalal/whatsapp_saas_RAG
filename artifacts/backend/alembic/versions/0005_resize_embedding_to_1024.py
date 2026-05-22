"""resize_embedding_vector_to_1024

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-20

TASK-008 — Document Ingestion Pipeline (RAG)
─────────────────────────────────────────────
Phase 1 uses intfloat/multilingual-e5-large which outputs 1024-dimensional
vectors, not the originally planned 1536-dim (OpenAI).

This migration:
  1. Drops the existing HNSW index on document_chunks.embedding
  2. Alters the column type from vector(1536) → vector(1024)
  3. Re-creates the HNSW index with the corrected dimension
  4. Adds a `metadata` JSONB column to the `documents` table

Run with:
    alembic upgrade head

Rollback with:
    alembic downgrade 0004
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# pgvector column type
try:
    from pgvector.sqlalchemy import Vector
    _vector_1024 = Vector(1024)
    _vector_1536 = Vector(1536)
except ImportError:  # pragma: no cover
    _vector_1024 = sa.Text()  # type: ignore[assignment]
    _vector_1536 = sa.Text()  # type: ignore[assignment]


# ── Revision identifiers ──────────────────────────────────────────────────────
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HNSW_INDEX = "ix_document_chunks_embedding_hnsw"
_TABLE = "document_chunks"
_COLUMN = "embedding"


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Drop the HNSW index (must be dropped before altering column type)
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {_HNSW_INDEX};"))

    # 2. Cast the column: vector(1536) → vector(1024)
    #    Any existing rows will be truncated/reset — acceptable in Phase 1
    #    where no production embeddings exist yet.
    conn.execute(sa.text(
        f"ALTER TABLE {_TABLE} "
        f"ALTER COLUMN {_COLUMN} TYPE vector(1024) "
        f"USING NULL::vector(1024);"
    ))

    # 3. Re-create HNSW index with updated dimension
    conn.execute(sa.text(
        f"CREATE INDEX {_HNSW_INDEX} "
        f"ON {_TABLE} "
        f"USING hnsw ({_COLUMN} vector_cosine_ops) "
        f"WITH (m = 16, ef_construction = 64);"
    ))

    # 4. Add metadata JSONB column to documents (for ingestion error tracking)
    op.add_column(
        "documents",
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
            comment="Pipeline metadata: ingestion_error, retry_count, etc.",
        ),
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop metadata column from documents
    op.drop_column("documents", "metadata")

    # Drop 1024-dim index
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {_HNSW_INDEX};"))

    # Revert column to vector(1536)
    conn.execute(sa.text(
        f"ALTER TABLE {_TABLE} "
        f"ALTER COLUMN {_COLUMN} TYPE vector(1536) "
        f"USING NULL::vector(1536);"
    ))

    # Re-create HNSW index for 1536-dim
    conn.execute(sa.text(
        f"CREATE INDEX {_HNSW_INDEX} "
        f"ON {_TABLE} "
        f"USING hnsw ({_COLUMN} vector_cosine_ops) "
        f"WITH (m = 16, ef_construction = 64);"
    ))
