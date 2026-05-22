"""
app/schemas/handoff.py
───────────────────────
Pydantic request/response schemas for the Human Handoff System.

Schema map
──────────
  HandoffTriggerRequest    → POST .../handoff  body
  HandoffTriggerResponse   → POST .../handoff  response
  HandoffAcceptRequest     → POST .../handoff/accept  body
  HandoffResolveRequest    → POST .../handoff/resolve body
  PendingHandoffItem       → one row in GET .../handoffs/pending list
  PendingHandoffsResponse  → full response wrapper for pending list
  AgentMessageRequest      → POST .../messages  body (agent → customer)
  AgentMessageResponse     → POST .../messages  response
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Handoff trigger ───────────────────────────────────────────────────────────

class HandoffTriggerRequest(BaseModel):
    reason: Literal["customer_request", "low_confidence", "agent_override"] = Field(
        ...,
        description="سبب التحويل إلى موظف بشري",
        examples=["customer_request"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {"reason": "customer_request"}
        }
    }


class MessageSummaryItem(BaseModel):
    """Compact message representation returned inside the handoff payload."""

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HandoffTriggerResponse(BaseModel):
    handoff_id: uuid.UUID = Field(..., description="UUID فريد لحدث التحويل")
    conversation_id: uuid.UUID
    reason: str
    ai_summary: str = Field(..., description="ملخص المحادثة للموظف البشري (عربي)")
    conversation_history: list[MessageSummaryItem] = Field(
        ..., description="آخر 20 رسالة في المحادثة"
    )
    status: Literal["pending_agent"] = "pending_agent"


# ── Pending handoffs list ─────────────────────────────────────────────────────

class PendingHandoffItem(BaseModel):
    """Single row returned by GET /handoffs/pending."""

    conversation_id: uuid.UUID
    customer_phone: str
    ai_summary: str | None = Field(None, description="ملخص المحادثة — مُنشأ عند التحويل")
    last_message_at: datetime
    message_count: int
    handoff_reason: str | None = None
    assigned_agent_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PendingHandoffsResponse(BaseModel):
    total: int
    items: list[PendingHandoffItem]


# ── Accept handoff ────────────────────────────────────────────────────────────

class HandoffAcceptRequest(BaseModel):
    agent_id: uuid.UUID = Field(..., description="UUID الموظف المقبول للمحادثة")

    model_config = {
        "json_schema_extra": {
            "example": {"agent_id": "11111111-2222-3333-4444-555555555555"}
        }
    }


# ── Resolve handoff ───────────────────────────────────────────────────────────

class HandoffResolveRequest(BaseModel):
    re_enable_ai: bool = Field(
        False,
        description=(
            "إذا كان True: إعادة تفعيل الذكاء الاصطناعي وإعادة المحادثة إلى الوضع النشط. "
            "إذا كان False: إغلاق المحادثة نهائياً."
        ),
    )

    model_config = {
        "json_schema_extra": {"example": {"re_enable_ai": True}}
    }


# ── Agent → Customer message ──────────────────────────────────────────────────

class AgentMessageRequest(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="نص الرسالة المرسلة من الموظف إلى العميل",
    )

    model_config = {
        "json_schema_extra": {"example": {"content": "مرحباً، كيف يمكنني مساعدتك؟"}}
    }


class AgentMessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    wa_delivery: dict | None = Field(
        None,
        description="استجابة Meta Graph API — None إذا فشل الإرسال عبر WhatsApp",
    )

    model_config = ConfigDict(from_attributes=True)


# ── Conversation List & Detail Response Schemas (TASK-013) ──────────────────────

class ConversationListItem(BaseModel):
    id: uuid.UUID
    customer_phone: str
    status: str
    ai_mode: bool
    started_at: datetime
    last_message_at: datetime
    message_count: int
    meta_data: dict = Field(default_factory=dict, alias="metadata")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MessageDetailItem(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    tokens_used: int | None = None
    model_used: str | None = None
    latency_ms: int | None = None

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(BaseModel):
    id: uuid.UUID
    customer_phone: str
    status: str
    ai_mode: bool
    started_at: datetime
    last_message_at: datetime
    meta_data: dict = Field(default_factory=dict, alias="metadata")
    messages: list[MessageDetailItem]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

