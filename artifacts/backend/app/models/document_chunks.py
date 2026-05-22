"""
app/models/document_chunks.py
──────────────────────────────
DocumentChunk model — individual text segments with pgvector embeddings.

Each Document is split into overlapping chunks during the RAG ingestion
pipeline.  The `embedding` column (Vector(1024)) is indexed with an HNSW
index for fast ANN (approximate nearest-neighbour) similarity search.

Phase 1 uses intfloat/multilingual-e5-large which outputs 1024-dim vectors.

pgvector integration via sqlalchemy-pgvector:
    pip install pgvector   (already in requirements.txt)
"""
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    # ── Table-level indexes ───────────────────────────────────────────────────
    # NOTE: The HNSW vector index cannot be expressed via __table_args__ in
    # SQLAlchemy — it is created explicitly in the Alembic migration.
    __table_args__ = (
        Index("ix_document_chunks_tenant_id", "tenant_id"),
        Index("ix_document_chunks_document_id", "document_id"),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Tenant isolation ──────────────────────────────────────────────────────
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        comment="Owning tenant — enforced by RLS policy.",
    )

    # ── Parent document ───────────────────────────────────────────────────────
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="Parent document this chunk was extracted from.",
    )

    # ── Chunk content ─────────────────────────────────────────────────────────
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Raw text of the chunk — UTF-8, supports Arabic.",
    )

    # ── Vector embedding (pgvector) ───────────────────────────────────────────
    embedding: Mapped[list[float]] = mapped_column(
        Vector(1024),
        nullable=False,
        comment=(
            "1024-dimensional embedding vector (intfloat/multilingual-e5-large). "
            "Searched via HNSW index.  Arabic + multilingual support."
        ),
    )

    # ── Arbitrary chunk metadata ──────────────────────────────────────────────
    meta_data: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment=(
            "Chunk-level metadata: chunk_index, page_number, source_section, "
            "char_start, char_end, etc."
        ),
    )

    # ── Timestamp ─────────────────────────────────────────────────────────────
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship(  # noqa: F821
        "Tenant", back_populates="document_chunks"
    )
    document: Mapped["Document"] = relationship(  # noqa: F821
        "Document", back_populates="chunks"
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk id={self.id} document={self.document_id} "
            f"content_len={len(self.content)}>"
        )
