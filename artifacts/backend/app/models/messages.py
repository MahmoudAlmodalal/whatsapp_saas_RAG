"""
app/models/messages.py
───────────────────────
Message model — individual WhatsApp messages (customer ↔ AI ↔ agent).

Each row stores the raw content, the WhatsApp message-id for deduplication,
and optional AI telemetry (tokens, model, latency) for cost/performance tracking.
"""
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MessageRole(str, enum.Enum):
    customer = "customer"
    ai = "ai"
    agent = "agent"


class Message(Base):
    __tablename__ = "messages"

    # ── Table-level indexes ───────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_messages_tenant_id", "tenant_id"),
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_wa_message_id", "wa_message_id", unique=True),
        Index("ix_messages_created_at", "created_at"),
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

    # ── Conversation FK ───────────────────────────────────────────────────────
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        comment="Parent conversation.",
    )

    # ── Message content ───────────────────────────────────────────────────────
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role_enum"),
        nullable=False,
        comment="Who sent this message: customer, AI, or human agent.",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Raw message text — UTF-8, supports Arabic.",
    )

    # ── WhatsApp deduplication ────────────────────────────────────────────────
    wa_message_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        comment=(
            "WhatsApp-assigned message ID (wamid.*).  "
            "Used to deduplicate webhook retries."
        ),
    )

    # ── AI telemetry (nullable — not set for customer/agent messages) ─────────
    tokens_used: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total tokens consumed by the LLM (prompt + completion).",
    )
    model_used: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Model identifier, e.g. 'gpt-4o-mini' or 'gemini-1.5-flash'.",
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="End-to-end AI response latency in milliseconds.",
    )

    # ── Timestamp ─────────────────────────────────────────────────────────────
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the message was stored (may differ slightly from WhatsApp timestamp).",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="messages")  # noqa: F821
    conversation: Mapped["Conversation"] = relationship(  # noqa: F821
        "Conversation", back_populates="messages"
    )

    def __repr__(self) -> str:
        return (
            f"<Message id={self.id} role={self.role} "
            f"conversation={self.conversation_id}>"
        )
