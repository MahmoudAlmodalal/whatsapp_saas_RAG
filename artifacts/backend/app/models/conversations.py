"""
app/models/conversations.py
────────────────────────────
Conversation model — one conversation per (tenant, customer_phone) session.

A conversation groups all messages exchanged with a single customer until
the session is closed or handed off to a human agent.
"""
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ConversationStatus(str, enum.Enum):
    active = "active"
    handoff = "handoff"
    closed = "closed"


class Conversation(Base):
    __tablename__ = "conversations"

    # ── Table-level constraints & indexes ─────────────────────────────────────
    __table_args__ = (
        Index("ix_conversations_tenant_id", "tenant_id"),
        Index("ix_conversations_tenant_customer", "tenant_id", "customer_phone"),
        Index("ix_conversations_status", "status"),
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

    # ── Customer info ─────────────────────────────────────────────────────────
    customer_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="E.164 phone number of the end-customer on WhatsApp.",
    )

    # ── State ─────────────────────────────────────────────────────────────────
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="conversation_status_enum"),
        nullable=False,
        default=ConversationStatus.active,
        server_default="active",
        comment="active → handoff → closed lifecycle.",
    )
    ai_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="True = AI replies; False = human agent handles the conversation.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    started_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the first message was received.",
    )
    last_message_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp of the most recent message (updated on each new message).",
    )

    # ── Arbitrary metadata (customer name, source channel, tags, etc.) ────────
    meta_data: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Flexible JSON bag: customer_name, tags, source_channel, etc.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship(  # noqa: F821
        "Tenant", back_populates="conversations"
    )
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation id={self.id} tenant={self.tenant_id} "
            f"phone={self.customer_phone} status={self.status}>"
        )
