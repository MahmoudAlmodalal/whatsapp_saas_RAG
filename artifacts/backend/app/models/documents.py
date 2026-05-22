"""
app/models/documents.py
────────────────────────
Document model — uploaded knowledge-base files (PDFs, DOCX, TXT, etc.).

Documents go through an async processing pipeline:
  queued → processing → ready | failed

Once processed, child DocumentChunk rows hold the text + vector embeddings.
"""
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    # ── Table-level indexes ───────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_documents_tenant_id", "tenant_id"),
        Index("ix_documents_status", "status"),
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

    # ── File metadata ─────────────────────────────────────────────────────────
    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Original filename as uploaded (preserves Arabic characters).",
    )
    file_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="MIME type or extension, e.g. 'application/pdf', 'text/plain'.",
    )
    storage_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Absolute path or object-store key (S3/GCS/Supabase Storage).",
    )

    # ── Processing state ──────────────────────────────────────────────────────
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status_enum"),
        nullable=False,
        default=DocumentStatus.queued,
        server_default="queued",
        comment="Lifecycle: queued → processing → ready | failed.",
    )
    chunk_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of chunks created after processing (null until done).",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    uploaded_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the file was received by the API.",
    )
    processed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When chunking & embedding completed (null if not yet done).",
    )

    # ── Arbitrary metadata ────────────────────────────────────────────────────
    meta_data: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Pipeline metadata: ingestion_error, retry_count, etc.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="documents")  # noqa: F821
    chunks: Mapped[list["DocumentChunk"]] = relationship(  # noqa: F821
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id} name={self.file_name!r} status={self.status}>"
        )
