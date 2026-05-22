"""
app/services/conversation_manager.py
──────────────────────────────────────
Conversation context manager for the WhatsApp AI pipeline.

Responsibilities
────────────────
  1. get_or_create_conversation  — resolve or create the active Conversation row
  2. get_conversation_history    — fetch the last N messages as role/content dicts
  3. save_message                — insert a Message row and update conversation timestamp
  4. get_context_from_cache      — pull conversation history list from Redis
  5. set_context_cache           — persist conversation history list to Redis (TTL 1 h)
  6. get_tenant_config           — fetch tenant JSONB config (Redis-cached, TTL 5 min)

Redis key schema
────────────────
  conv_ctx:{conversation_id}    → JSON list of {role, content} dicts   (TTL 3 600 s)
  tenant_cfg:{tenant_id}        → JSON dict of tenant.config            (TTL 300 s)

Multi-tenancy
─────────────
  Every DB call sets the Postgres session variable via set_tenant_context() so that
  Row-Level Security policies are satisfied.  tenant_id is always passed explicitly.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import redis_client
from app.database import set_tenant_context
from app.models.conversations import Conversation, ConversationStatus
from app.models.messages import Message, MessageRole

logger = logging.getLogger(__name__)

# ── Redis TTLs ────────────────────────────────────────────────────────────────
_CONV_CTX_TTL = 3_600   # 1 hour — conversation context
_TENANT_CFG_TTL = 300   # 5 minutes — tenant config


# ─────────────────────────────────────────────────────────────────────────────
# 1. Conversation lifecycle
# ─────────────────────────────────────────────────────────────────────────────


async def get_or_create_conversation(
    customer_phone: str,
    tenant_id: str,
    session: AsyncSession,
) -> Conversation:
    """
    Return the current active Conversation for (customer_phone, tenant_id),
    creating one if none exists.

    "Active" means status == 'active'.  A customer may have at most one
    active conversation per tenant at a time.

    Args:
        customer_phone: E.164 phone number of the customer.
        tenant_id:      Owning tenant UUID string.
        session:        Async DB session — RLS context set internally.

    Returns:
        Conversation ORM instance (new or existing).
    """
    await set_tenant_context(session, tenant_id)

    tid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id

    stmt = (
        select(Conversation)
        .where(
            Conversation.tenant_id == tid,
            Conversation.customer_phone == customer_phone,
            Conversation.status == ConversationStatus.active,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    conversation = result.scalar_one_or_none()

    if conversation is not None:
        logger.debug(
            "Existing conversation found: id=%s tenant=%s phone=%s",
            conversation.id, tenant_id, customer_phone,
        )
        return conversation

    # Create a new active conversation
    conversation = Conversation(
        tenant_id=tid,
        customer_phone=customer_phone,
        status=ConversationStatus.active,
        ai_mode=True,
        started_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
        meta_data={},
    )
    session.add(conversation)
    await session.flush()  # populate conversation.id without full commit

    logger.info(
        "New conversation created: id=%s tenant=%s phone=%s",
        conversation.id, tenant_id, customer_phone,
    )
    return conversation


# ─────────────────────────────────────────────────────────────────────────────
# 2. Conversation history
# ─────────────────────────────────────────────────────────────────────────────


async def get_conversation_history(
    conversation_id: uuid.UUID | str,
    tenant_id: str,
    session: AsyncSession,
    last_n: int = 10,
) -> list[dict[str, str]]:
    """
    Fetch the last *last_n* messages for a conversation and return them
    in the OpenAI chat-completion messages format.

    Role mapping:
        customer  → "user"
        ai        → "assistant"
        agent     → "assistant"  (human agent replies look the same to the LLM)

    Args:
        conversation_id: UUID of the conversation.
        tenant_id:       Owning tenant UUID string.
        session:         Async DB session.
        last_n:          Maximum number of messages to fetch (default 10).

    Returns:
        List of {"role": "user"|"assistant", "content": str}, oldest first.
    """
    await set_tenant_context(session, tenant_id)

    conv_id = (
        uuid.UUID(str(conversation_id))
        if not isinstance(conversation_id, uuid.UUID)
        else conversation_id
    )
    tid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id

    # Fetch last N messages ordered by created_at ASC (oldest first)
    subq = (
        select(Message)
        .where(
            Message.conversation_id == conv_id,
            Message.tenant_id == tid,
        )
        .order_by(Message.created_at.desc())
        .limit(last_n)
        .subquery()
    )
    # Re-order ascending for chronological history
    from sqlalchemy import select as _select, alias, asc
    inner = alias(subq, name="latest_msgs")
    stmt = _select(inner).order_by(asc(inner.c.created_at))
    result = await session.execute(stmt)
    rows = result.fetchall()

    _ROLE_MAP = {
        MessageRole.customer: "user",
        MessageRole.ai: "assistant",
        MessageRole.agent: "assistant",
    }

    history: list[dict[str, str]] = []
    for row in rows:
        role_val = row.role
        # row.role may come back as a string when querying via alias
        if isinstance(role_val, str):
            try:
                role_val = MessageRole(role_val)
            except ValueError:
                role_val = MessageRole.ai
        history.append({
            "role": _ROLE_MAP.get(role_val, "assistant"),
            "content": row.content,
        })

    logger.debug(
        "Loaded %d history messages for conversation %s",
        len(history), conversation_id,
    )
    return history


# ─────────────────────────────────────────────────────────────────────────────
# 3. Save message
# ─────────────────────────────────────────────────────────────────────────────


async def save_message(
    conversation_id: uuid.UUID | str,
    tenant_id: str,
    role: str,
    content: str,
    session: AsyncSession,
    *,
    wa_message_id: str | None = None,
    tokens_used: int | None = None,
    model_used: str | None = None,
    latency_ms: int | None = None,
) -> Message:
    """
    Persist a new message row and bump conversations.last_message_at.

    Args:
        conversation_id: Parent conversation UUID.
        tenant_id:       Owning tenant UUID string.
        role:            One of "customer", "ai", "agent".
        content:         Message text (UTF-8, Arabic supported).
        session:         Async DB session.
        wa_message_id:   WhatsApp message ID for deduplication (nullable).
        tokens_used:     Total LLM tokens consumed (nullable).
        model_used:      LLM model identifier (nullable).
        latency_ms:      LLM call latency in milliseconds (nullable).

    Returns:
        Persisted Message ORM instance.
    """
    await set_tenant_context(session, tenant_id)

    conv_id = (
        uuid.UUID(str(conversation_id))
        if not isinstance(conversation_id, uuid.UUID)
        else conversation_id
    )
    tid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id

    try:
        role_enum = MessageRole(role)
    except ValueError:
        logger.warning("Unknown message role %r — defaulting to 'ai'", role)
        role_enum = MessageRole.ai

    now = datetime.now(timezone.utc)

    msg = Message(
        tenant_id=tid,
        conversation_id=conv_id,
        role=role_enum,
        content=content,
        wa_message_id=wa_message_id,
        tokens_used=tokens_used,
        model_used=model_used,
        latency_ms=latency_ms,
        created_at=now,
    )
    session.add(msg)

    # Update last_message_at on the parent conversation
    await session.execute(
        update(Conversation)
        .where(Conversation.id == conv_id, Conversation.tenant_id == tid)
        .values(last_message_at=now)
    )

    await session.flush()

    logger.debug(
        "Saved message: id=%s role=%s conv=%s tenant=%s",
        msg.id, role, conversation_id, tenant_id,
    )
    return msg


# ─────────────────────────────────────────────────────────────────────────────
# 4 & 5. Conversation context Redis cache
# ─────────────────────────────────────────────────────────────────────────────


def _conv_ctx_key(conversation_id: uuid.UUID | str) -> str:
    return f"conv_ctx:{conversation_id}"


async def get_context_from_cache(
    conversation_id: uuid.UUID | str,
) -> list[dict[str, str]] | None:
    """
    Retrieve the cached conversation history list from Redis.

    Returns:
        Parsed list of {"role", "content"} dicts, or None on cache miss / error.
    """
    key = _conv_ctx_key(conversation_id)
    try:
        raw: str | None = await redis_client.get(key)
        if raw is None:
            return None
        history: list[dict[str, str]] = json.loads(raw)
        logger.debug(
            "Conv context cache HIT: conversation=%s entries=%d",
            conversation_id, len(history),
        )
        return history
    except Exception as exc:
        logger.warning(
            "Conv context cache GET failed for %s: %s", conversation_id, exc
        )
        return None


async def set_context_cache(
    conversation_id: uuid.UUID | str,
    history: list[dict[str, str]],
) -> None:
    """
    Store the conversation history list in Redis as JSON with a 1-hour TTL.

    Failures are logged but never raised — caching is best-effort.
    """
    key = _conv_ctx_key(conversation_id)
    try:
        payload = json.dumps(history, ensure_ascii=False)
        await redis_client.set(key, payload, ex=_CONV_CTX_TTL)
        logger.debug(
            "Conv context cache SET: conversation=%s entries=%d ttl=%ds",
            conversation_id, len(history), _CONV_CTX_TTL,
        )
    except Exception as exc:
        logger.warning(
            "Conv context cache SET failed for %s: %s", conversation_id, exc
        )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Tenant config cache
# ─────────────────────────────────────────────────────────────────────────────


def _tenant_cfg_key(tenant_id: str) -> str:
    return f"tenant_cfg:{tenant_id}"


async def get_tenant_config(
    tenant_id: str,
    session: AsyncSession,
) -> dict[str, Any]:
    """
    Return the tenant's AI configuration dict, served from Redis when available.

    Cache strategy:
        Key:    tenant_cfg:{tenant_id}
        TTL:    300 s (5 minutes)
        Source: tenants.config JSONB column on cache miss

    Returns:
        Tenant config dict (may be empty dict if tenant has no config set yet).
        Falls back to {} on any error so the pipeline always continues.
    """
    key = _tenant_cfg_key(tenant_id)

    # ── Try Redis cache ───────────────────────────────────────────────────────
    try:
        raw: str | None = await redis_client.get(key)
        if raw is not None:
            config: dict[str, Any] = json.loads(raw)
            logger.debug("Tenant config cache HIT: tenant=%s", tenant_id)
            return config
    except Exception as exc:
        logger.warning("Tenant config cache GET failed: %s", exc)

    # ── Cache miss: load from DB ──────────────────────────────────────────────
    try:
        from app.models.tenants import Tenant  # local import to avoid circular

        await set_tenant_context(session, tenant_id)
        tid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id

        result = await session.execute(
            select(Tenant.config).where(Tenant.id == tid)
        )
        row = result.scalar_one_or_none()
        config = dict(row) if row else {}

        # Persist to Redis
        try:
            await redis_client.set(
                key, json.dumps(config, ensure_ascii=False), ex=_TENANT_CFG_TTL
            )
        except Exception as exc:
            logger.warning("Tenant config cache SET failed: %s", exc)

        logger.debug(
            "Tenant config loaded from DB: tenant=%s keys=%s",
            tenant_id, list(config.keys()),
        )
        return config

    except Exception as exc:
        logger.error(
            "Failed to load tenant config for %s: %s", tenant_id, exc, exc_info=True
        )
        return {}
