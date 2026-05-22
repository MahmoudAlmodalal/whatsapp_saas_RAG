"""
app/routers/handoff.py
───────────────────────
Human Handoff System — TASK-012

When a conversation is handed off, `conversations.ai_mode` is set to False
and `conversations.status` is set to 'handoff'.  The AI pipeline
(conversation_manager / webhook) skips any conversation where ai_mode=False,
so the agent takes full control until the handoff is resolved.

Endpoints
─────────
  POST   /api/v1/tenants/{tenant_id}/conversations/{conv_id}/handoff
  GET    /api/v1/tenants/{tenant_id}/handoffs/pending
  POST   /api/v1/tenants/{tenant_id}/conversations/{conv_id}/handoff/accept
  POST   /api/v1/tenants/{tenant_id}/conversations/{conv_id}/handoff/resolve
  POST   /api/v1/tenants/{tenant_id}/conversations/{conv_id}/messages

Auth model
──────────
  Trigger / Resolve / Agent-message → get_current_agent  (admin or agent)
  Pending list                       → get_current_agent
  Accept                             → get_current_agent

Multi-tenancy
─────────────
  Path tenant_id is validated against the JWT-derived tenant_id so that
  a user from tenant A can never access tenant B's conversations.

Arabic LLM Summary
──────────────────
  On trigger, a call to DeepSeek is made with a lightweight summarisation
  prompt (Arabic).  The call is capped at 300 tokens and uses temperature=0
  for deterministic output.  Failures are non-fatal; a fallback message is
  returned instead.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_agent, get_current_admin
from app.database import get_db, set_tenant_context
from app.models.conversations import Conversation, ConversationStatus
from app.models.messages import Message, MessageRole
from app.schemas.handoff import (
    AgentMessageRequest,
    AgentMessageResponse,
    HandoffAcceptRequest,
    HandoffResolveRequest,
    HandoffTriggerRequest,
    HandoffTriggerResponse,
    MessageSummaryItem,
    PendingHandoffItem,
    PendingHandoffsResponse,
    ConversationListItem,
    ConversationDetailResponse,
    MessageDetailItem,
)
from app.services.whatsapp_sender import send_whatsapp_message

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Human Handoff"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def _get_conversation_or_404(
    conv_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Conversation:
    """Fetch a conversation row, raising 404 if not found."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.tenant_id == tenant_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"المحادثة {conv_id} غير موجودة أو لا تنتمي لهذا المستأجر",
        )
    return conv


def _assert_tenant_match(
    path_tenant_id: uuid.UUID,
    jwt_tenant_id: uuid.UUID,
) -> None:
    """Prevent cross-tenant access: path UUID must match JWT-derived UUID."""
    if path_tenant_id != jwt_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا يمكنك الوصول إلى بيانات مستأجر آخر",  # Cross-tenant access denied
        )


async def _fetch_last_messages(
    conv_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 20,
) -> list[Message]:
    """Return the last `limit` messages for a conversation, ordered oldest→newest."""
    result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id == conv_id,
            Message.tenant_id == tenant_id,
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    msgs = list(reversed(result.scalars().all()))
    return msgs


async def _generate_ai_summary(
    messages: list[Message],
    tenant_id: str,
) -> str:
    """
    Call DeepSeek to produce a 3-bullet Arabic summary of the conversation.

    Falls back to a static Arabic message on any error so that the handoff
    response is never blocked by an LLM failure.
    """
    try:
        from openai import AsyncOpenAI  # imported locally to avoid circular imports
        from app.config import get_settings

        settings = get_settings()
        client = AsyncOpenAI(
            base_url="https://api.deepseek.com/v1",
            api_key=settings.DEEPSEEK_API_KEY,
        )

        # Build a compact conversation transcript for the summarisation prompt
        history_text = "\n".join(
            f"[{msg.role}]: {msg.content}" for msg in messages[-30:]
        )

        prompt = (
            f"لخص هذه المحادثة في 3 نقاط للموظف المسؤول:\n{history_text}"
        )

        completion = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "أنت مساعد متخصص في تلخيص المحادثات. "
                        "قدم ملخصاً مختصراً وواضحاً للموظف البشري باللغة العربية."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.0,  # deterministic summarisation
        )

        summary: str = completion.choices[0].message.content or ""
        logger.info(
            "AI summary generated for handoff — tenant=%s chars=%d",
            tenant_id, len(summary),
        )
        return summary.strip()

    except Exception as exc:
        logger.warning(
            "AI summary generation failed for tenant=%s: %s — using fallback",
            tenant_id, exc,
        )
        return "لم يتمكن النظام من إنشاء ملخص تلقائي. يرجى مراجعة المحادثة مباشرة."


# ─────────────────────────────────────────────────────────────────────────────
# 1. POST /tenants/{tenant_id}/conversations/{conv_id}/handoff
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/{tenant_id}/conversations/{conv_id}/handoff",
    response_model=HandoffTriggerResponse,
    status_code=status.HTTP_200_OK,
    summary="تفعيل التحويل إلى موظف بشري",
    description=(
        "يضع المحادثة في وضع الانتظار البشري: يوقف ردود الذكاء الاصطناعي، "
        "ويولّد ملخصاً للموظف، ويعيد آخر 20 رسالة."
    ),
)
async def trigger_handoff(
    tenant_id: uuid.UUID,
    conv_id: uuid.UUID,
    body: HandoffTriggerRequest,
    auth: tuple = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> HandoffTriggerResponse:
    current_user, jwt_tenant_id = auth
    _assert_tenant_match(tenant_id, jwt_tenant_id)
    await set_tenant_context(db, str(tenant_id))

    # ── Fetch conversation ────────────────────────────────────────────────────
    conv = await _get_conversation_or_404(conv_id, tenant_id, db)

    if conv.status == ConversationStatus.handoff:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="المحادثة في وضع التحويل بالفعل",  # Already in handoff
        )

    # ── Fetch recent messages ─────────────────────────────────────────────────
    recent_msgs = await _fetch_last_messages(conv_id, tenant_id, db, limit=20)

    # ── Generate AI summary (non-blocking — fallback on failure) ──────────────
    ai_summary = await _generate_ai_summary(recent_msgs, str(tenant_id))

    # ── Build handoff event record ────────────────────────────────────────────
    handoff_id = uuid.uuid4()
    handoff_event: dict[str, Any] = {
        "handoff_id": str(handoff_id),
        "reason": body.reason,
        "timestamp": _now_utc().isoformat(),
        "assigned_agent": None,
        "ai_summary": ai_summary,
    }

    # ── Persist state changes ─────────────────────────────────────────────────
    # Append to metadata.handoff_events list (initialise if key missing)
    existing_meta: dict = dict(conv.meta_data or {})
    handoff_events: list = existing_meta.get("handoff_events", [])
    handoff_events.append(handoff_event)
    existing_meta["handoff_events"] = handoff_events

    await db.execute(
        update(Conversation)
        .where(Conversation.id == conv_id, Conversation.tenant_id == tenant_id)
        .values(
            ai_mode=False,
            status=ConversationStatus.handoff,
            meta_data=existing_meta,
        )
    )
    await db.commit()

    logger.info(
        "Handoff triggered — tenant=%s conv=%s reason=%s handoff_id=%s",
        tenant_id, conv_id, body.reason, handoff_id,
    )

    # ── Build response ────────────────────────────────────────────────────────
    history_items = [
        MessageSummaryItem(
            id=m.id,
            role=m.role.value if hasattr(m.role, "value") else str(m.role),
            content=m.content,
            created_at=m.created_at,
        )
        for m in recent_msgs
    ]

    return HandoffTriggerResponse(
        handoff_id=handoff_id,
        conversation_id=conv_id,
        reason=body.reason,
        ai_summary=ai_summary,
        conversation_history=history_items,
        status="pending_agent",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /tenants/{tenant_id}/handoffs/pending
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/{tenant_id}/handoffs/pending",
    response_model=PendingHandoffsResponse,
    summary="قائمة المحادثات المنتظِرة موظفاً",
    description="جلب جميع المحادثات في وضع التحويل لهذا المستأجر، مرتبة بالأقدم أولاً.",
)
async def list_pending_handoffs(
    tenant_id: uuid.UUID,
    auth: tuple = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> PendingHandoffsResponse:
    current_user, jwt_tenant_id = auth
    _assert_tenant_match(tenant_id, jwt_tenant_id)
    await set_tenant_context(db, str(tenant_id))

    # Count messages per conversation via subquery
    msg_count_sq = (
        select(
            Message.conversation_id,
            func.count(Message.id).label("msg_count"),
        )
        .where(Message.tenant_id == tenant_id)
        .group_by(Message.conversation_id)
        .subquery()
    )

    result = await db.execute(
        select(Conversation, msg_count_sq.c.msg_count)
        .outerjoin(
            msg_count_sq,
            Conversation.id == msg_count_sq.c.conversation_id,
        )
        .where(
            Conversation.tenant_id == tenant_id,
            Conversation.status == ConversationStatus.handoff,
        )
        .order_by(Conversation.last_message_at.asc())
    )
    rows = result.all()

    items: list[PendingHandoffItem] = []
    for conv, msg_count in rows:
        meta: dict = conv.meta_data or {}
        handoff_events: list = meta.get("handoff_events", [])

        # Last handoff event has the latest summary & reason
        last_event: dict = handoff_events[-1] if handoff_events else {}

        assigned_agent_raw = last_event.get("assigned_agent") or meta.get("assigned_agent_id")
        assigned_agent_id: uuid.UUID | None = None
        if assigned_agent_raw:
            try:
                assigned_agent_id = uuid.UUID(str(assigned_agent_raw))
            except (ValueError, AttributeError):
                pass

        items.append(
            PendingHandoffItem(
                conversation_id=conv.id,
                customer_phone=conv.customer_phone,
                ai_summary=last_event.get("ai_summary"),
                last_message_at=conv.last_message_at,
                message_count=msg_count or 0,
                handoff_reason=last_event.get("reason"),
                assigned_agent_id=assigned_agent_id,
            )
        )

    return PendingHandoffsResponse(total=len(items), items=items)


# ─────────────────────────────────────────────────────────────────────────────
# 3. POST /tenants/{tenant_id}/conversations/{conv_id}/handoff/accept
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/{tenant_id}/conversations/{conv_id}/handoff/accept",
    status_code=status.HTTP_200_OK,
    summary="قبول المحادثة من قِبَل موظف",
    description="يسجّل هوية الموظف الذي قَبِل التعامل مع المحادثة.",
)
async def accept_handoff(
    tenant_id: uuid.UUID,
    conv_id: uuid.UUID,
    body: HandoffAcceptRequest,
    auth: tuple = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> dict:
    current_user, jwt_tenant_id = auth
    _assert_tenant_match(tenant_id, jwt_tenant_id)
    await set_tenant_context(db, str(tenant_id))

    conv = await _get_conversation_or_404(conv_id, tenant_id, db)

    if conv.status != ConversationStatus.handoff:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="المحادثة ليست في وضع التحويل",
        )

    # Update last handoff event and top-level metadata
    meta: dict = dict(conv.meta_data or {})
    handoff_events: list = meta.get("handoff_events", [])

    if handoff_events:
        handoff_events[-1]["assigned_agent"] = str(body.agent_id)
    meta["handoff_events"] = handoff_events
    meta["assigned_agent_id"] = str(body.agent_id)

    await db.execute(
        update(Conversation)
        .where(Conversation.id == conv_id, Conversation.tenant_id == tenant_id)
        .values(meta_data=meta)
    )
    await db.commit()

    logger.info(
        "Handoff accepted — tenant=%s conv=%s agent=%s",
        tenant_id, conv_id, body.agent_id,
    )
    return {"status": "accepted", "agent_id": str(body.agent_id)}


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST /tenants/{tenant_id}/conversations/{conv_id}/handoff/resolve
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/{tenant_id}/conversations/{conv_id}/handoff/resolve",
    status_code=status.HTTP_200_OK,
    summary="إنهاء وضع التحويل",
    description=(
        "إنهاء التحويل البشري: إما إعادة تفعيل الذكاء الاصطناعي (re_enable_ai=true) "
        "أو إغلاق المحادثة نهائياً (re_enable_ai=false)."
    ),
)
async def resolve_handoff(
    tenant_id: uuid.UUID,
    conv_id: uuid.UUID,
    body: HandoffResolveRequest,
    auth: tuple = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> dict:
    current_user, jwt_tenant_id = auth
    _assert_tenant_match(tenant_id, jwt_tenant_id)
    await set_tenant_context(db, str(tenant_id))

    conv = await _get_conversation_or_404(conv_id, tenant_id, db)

    if conv.status != ConversationStatus.handoff:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="المحادثة ليست في وضع التحويل",
        )

    if body.re_enable_ai:
        new_status = ConversationStatus.active
        new_ai_mode = True
        outcome = "ai_re_enabled"
    else:
        new_status = ConversationStatus.closed
        new_ai_mode = False
        outcome = "closed"

    await db.execute(
        update(Conversation)
        .where(Conversation.id == conv_id, Conversation.tenant_id == tenant_id)
        .values(status=new_status, ai_mode=new_ai_mode)
    )
    await db.commit()

    logger.info(
        "Handoff resolved — tenant=%s conv=%s outcome=%s",
        tenant_id, conv_id, outcome,
    )
    return {
        "status": "resolved",
        "outcome": outcome,
        "conversation_status": new_status.value,
        "ai_mode": new_ai_mode,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. POST /tenants/{tenant_id}/conversations/{conv_id}/messages  (agent send)
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/{tenant_id}/conversations/{conv_id}/messages",
    response_model=AgentMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="إرسال رسالة من موظف إلى العميل",
    description=(
        "يحفظ الرسالة في قاعدة البيانات بدور 'agent' ثم يرسلها عبر WhatsApp."
        " يُسمح بذلك فقط عندما تكون المحادثة في وضع التحويل."
    ),
)
async def send_agent_message(
    tenant_id: uuid.UUID,
    conv_id: uuid.UUID,
    body: AgentMessageRequest,
    auth: tuple = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> AgentMessageResponse:
    current_user, jwt_tenant_id = auth
    _assert_tenant_match(tenant_id, jwt_tenant_id)
    await set_tenant_context(db, str(tenant_id))

    conv = await _get_conversation_or_404(conv_id, tenant_id, db)

    # Guard: only allow agent messages while in handoff (ai_mode=False)
    if conv.ai_mode:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "المحادثة في وضع الذكاء الاصطناعي. "
                "فعّل التحويل أولاً قبل إرسال رسائل يدوية."
            ),
        )

    now = _now_utc()

    # ── Persist agent message ─────────────────────────────────────────────────
    msg = Message(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        conversation_id=conv_id,
        role=MessageRole.agent,
        content=body.content,
        created_at=now,
    )
    db.add(msg)

    # Bump last_message_at on the conversation
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conv_id, Conversation.tenant_id == tenant_id)
        .values(last_message_at=now)
    )
    await db.flush()

    # ── Send via WhatsApp ─────────────────────────────────────────────────────
    wa_delivery: dict | None = None
    try:
        wa_delivery = await send_whatsapp_message(
            to_phone=conv.customer_phone,
            text=body.content,
            tenant_id=str(tenant_id),
        )
        logger.info(
            "Agent message delivered via WhatsApp — tenant=%s conv=%s phone=%s",
            tenant_id, conv_id, conv.customer_phone,
        )
    except Exception as exc:
        # Non-fatal: message is saved in DB even if WhatsApp delivery fails
        logger.error(
            "WhatsApp delivery failed for agent message — tenant=%s conv=%s: %s",
            tenant_id, conv_id, exc,
        )

    await db.commit()
    await db.refresh(msg)

    return AgentMessageResponse(
        id=msg.id,
        conversation_id=conv_id,
        role=msg.role.value if hasattr(msg.role, "value") else str(msg.role),
        content=msg.content,
        created_at=msg.created_at,
        wa_delivery=wa_delivery,
    )


# ── Added for TASK-013 ────────────────────────────────────────────────────────

@router.get(
    "/{tenant_id}/conversations",
    response_model=list[ConversationListItem],
    summary="قائمة المحادثات",
    description="جلب قائمة المحادثات لشركة معينة مع إمكانية التصفية حسب الحالة.",
)
async def list_conversations(
    tenant_id: uuid.UUID,
    status: ConversationStatus | None = None,
    auth: tuple = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationListItem]:
    current_user, jwt_tenant_id = auth
    _assert_tenant_match(tenant_id, jwt_tenant_id)
    await set_tenant_context(db, str(tenant_id))

    # Count messages subquery
    msg_count_sq = (
        select(
            Message.conversation_id,
            func.count(Message.id).label("msg_count"),
        )
        .where(Message.tenant_id == tenant_id)
        .group_by(Message.conversation_id)
        .subquery()
    )

    query = select(Conversation, msg_count_sq.c.msg_count).outerjoin(
        msg_count_sq, Conversation.id == msg_count_sq.c.conversation_id
    ).where(Conversation.tenant_id == tenant_id)

    if status:
        query = query.where(Conversation.status == status)

    query = query.order_by(Conversation.last_message_at.desc())

    result = await db.execute(query)
    rows = result.all()

    items = []
    for conv, msg_count in rows:
        items.append(
            ConversationListItem(
                id=conv.id,
                customer_phone=conv.customer_phone,
                status=conv.status.value if hasattr(conv.status, "value") else str(conv.status),
                ai_mode=conv.ai_mode,
                started_at=conv.started_at,
                last_message_at=conv.last_message_at,
                message_count=msg_count or 0,
                meta_data=conv.meta_data or {},
            )
        )
    return items


@router.get(
    "/{tenant_id}/conversations/{conv_id}",
    response_model=ConversationDetailResponse,
    summary="تفاصيل محادثة",
    description="جلب تفاصيل محادثة معينة وتاريخ الرسائل الخاص بها مرتباً بالأقدم أولاً.",
)
async def get_conversation_details(
    tenant_id: uuid.UUID,
    conv_id: uuid.UUID,
    auth: tuple = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    current_user, jwt_tenant_id = auth
    _assert_tenant_match(tenant_id, jwt_tenant_id)
    await set_tenant_context(db, str(tenant_id))

    conv = await _get_conversation_or_404(conv_id, tenant_id, db)

    # Fetch messages order oldest to newest
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id, Message.tenant_id == tenant_id)
        .order_by(Message.created_at.asc())
    )
    msgs = result.scalars().all()

    messages_list = [
        MessageDetailItem(
            id=m.id,
            role=m.role.value if hasattr(m.role, "value") else str(m.role),
            content=m.content,
            created_at=m.created_at,
            tokens_used=m.tokens_used,
            model_used=m.model_used,
            latency_ms=m.latency_ms,
        )
        for m in msgs
    ]

    return ConversationDetailResponse(
        id=conv.id,
        customer_phone=conv.customer_phone,
        status=conv.status.value if hasattr(conv.status, "value") else str(conv.status),
        ai_mode=conv.ai_mode,
        started_at=conv.started_at,
        last_message_at=conv.last_message_at,
        meta_data=conv.meta_data or {},
        messages=messages_list,
    )
