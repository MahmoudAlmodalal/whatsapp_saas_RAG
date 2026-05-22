"""create_core_tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18

TASK-002 — Database Schema & RLS Policies
─────────────────────────────────────────
Creates the five core tables for the multi-tenant WhatsApp AI SaaS:
  tenants, conversations, messages, documents, document_chunks

Also:
  - Creates all tenant_id / conversation_id / embedding indexes
  - HNSW vector index on document_chunks.embedding (pgvector)
  - Enables RLS on the four tenant-scoped tables
  - NOTE: RLS *policies* are applied via the companion rls_policies.sql
    script (idempotent, safe to re-run after DB restore).

Run with:
    alembic upgrade head

Rollback with:
    alembic downgrade 0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# pgvector column type — requires `pip install pgvector` (in requirements.txt)
try:
    from pgvector.sqlalchemy import Vector
    _vector_type = Vector(1536)
except ImportError:  # pragma: no cover — never hit inside the container
    # Fallback so the migration file can at least be imported in test envs
    # without the pgvector C extension installed.
    _vector_type = sa.Text()  # type: ignore[assignment]


# ── Revision identifiers ──────────────────────────────────────────────────────
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Enums ─────────────────────────────────────────────────────────────────────
subscription_tier_enum = postgresql.ENUM(
    "basic", "pro", "enterprise",
    name="subscription_tier_enum",
    create_type=False,  # we create it manually below for idempotency
)
conversation_status_enum = postgresql.ENUM(
    "active", "handoff", "closed",
    name="conversation_status_enum",
    create_type=False,
)
message_role_enum = postgresql.ENUM(
    "customer", "ai", "agent",
    name="message_role_enum",
    create_type=False,
)
document_status_enum = postgresql.ENUM(
    "queued", "processing", "ready", "failed",
    name="document_status_enum",
    create_type=False,
)


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Create Postgres ENUM types ─────────────────────────────────────────
    # We let SQLAlchemy create these automatically via `sa.Enum(..., create_type=True)`.

    # ── 2. tenants ─────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("whatsapp_number", sa.String(20), nullable=True, unique=True),
        sa.Column(
            "subscription_tier",
            sa.Enum("basic", "pro", "enterprise", name="subscription_tier_enum",
                    create_constraint=False),
            nullable=False,
            server_default="basic",
        ),
        sa.Column("config", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ── 3. conversations ───────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_phone", sa.String(20), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "handoff", "closed", name="conversation_status_enum",
                    create_constraint=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("ai_mode", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("meta_data", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'")),
    )
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    op.create_index("ix_conversations_tenant_customer", "conversations",
                    ["tenant_id", "customer_phone"])
    op.create_index("ix_conversations_status", "conversations", ["status"])

    # ── 4. messages ────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column(
            "role",
            sa.Enum("customer", "ai", "agent", name="message_role_enum",
                    create_constraint=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("wa_message_id", sa.String(255), nullable=True, unique=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_wa_message_id", "messages", ["wa_message_id"],
                    unique=True)
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    # ── 5. documents ───────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("queued", "processing", "ready", "failed",
                    name="document_status_enum", create_constraint=False),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index("ix_documents_status", "documents", ["status"])

    # ── 6. document_chunks ─────────────────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        # pgvector column — 1536 dims for OpenAI text-embedding-3-small
        sa.Column("embedding", _vector_type, nullable=False),
        sa.Column("meta_data", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_document_chunks_tenant_id", "document_chunks", ["tenant_id"])
    op.create_index("ix_document_chunks_document_id", "document_chunks",
                    ["document_id"])

    # HNSW index for fast ANN vector similarity search
    # m=16 (number of bi-directional links) and ef_construction=64 are safe
    # production defaults; tune upward for higher recall at cost of build time.
    conn.execute(sa.text(
        "CREATE INDEX ix_document_chunks_embedding_hnsw "
        "ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64);"
    ))

    # ── 7. Enable Row-Level Security on tenant-scoped tables ───────────────────
    # RLS prevents cross-tenant data leakage at the Postgres layer.
    # The actual POLICY is in rls_policies.sql (apply separately or via psql).
    for table in ("conversations", "messages", "documents", "document_chunks"):
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"))
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"))


def downgrade() -> None:
    conn = op.get_bind()

    # ── Disable RLS before dropping tables ────────────────────────────────────
    for table in ("conversations", "messages", "documents", "document_chunks"):
        conn.execute(sa.text(
            f"ALTER TABLE IF EXISTS {table} DISABLE ROW LEVEL SECURITY;"
        ))

    # ── Drop tables (reverse FK order) ────────────────────────────────────────
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("tenants")

    # ── Drop ENUM types ───────────────────────────────────────────────────────
    for enum_name in (
        "document_status_enum",
        "message_role_enum",
        "conversation_status_enum",
        "subscription_tier_enum",
    ):
        conn.execute(sa.text(f"DROP TYPE IF EXISTS {enum_name};"))
