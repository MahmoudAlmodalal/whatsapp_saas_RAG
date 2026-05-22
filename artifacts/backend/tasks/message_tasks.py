"""
tasks/message_tasks.py
───────────────────────
Celery task: process_inbound_message

Drives the full inbound message processing pipeline with end-to-end
Langfuse observability:

  Trace: "process_message"
    └─ Span:       "rag_retrieval"
    └─ Generation: "llm_response"

Subscription enforcement
────────────────────────
  The first step after trace initialisation is a quota check via
  ``app.services.subscription.check_and_increment()``.  If the tenant has
  exhausted their monthly plan limit the task:
    1. Sends a polite Arabic rejection message directly to the customer.
    2. Records the outcome on the Langfuse trace.
    3. Returns immediately — quota breaches are NOT retried.

Retry policy: up to 5 attempts with exponential back-off (capped at 300 s).
Only pipeline errors (not quota denials) trigger retries.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import redis as redis_sync_lib

from celery_app import celery_app
from core.logging import tenant_id_var, trace_id_var
from core.observability import create_trace, end_generation, flush, span_ctx

logger = logging.getLogger(__name__)

# ── Subscription rejection message (Arabic) ────────────────────────────────────
_QUOTA_EXCEEDED_MSG = (
    "عذراً، لقد وصلت إلى الحد الأقصى من الرسائل المتاحة في خطتك الحالية هذا الشهر. "
    "يرجى التواصل مع الدعم للترقية إلى خطة أعلى والاستمرار في الاستخدام. 🙏"
)


# ── Sync Redis singleton (used in Celery worker processes) ─────────────────────

_redis_sync: redis_sync_lib.Redis | None = None


def _get_redis_sync() -> redis_sync_lib.Redis:
    """
    Return a module-level synchronous Redis client.

    Celery workers are sync processes — they cannot use redis.asyncio.
    This singleton is created lazily on the first task execution.
    """
    global _redis_sync
    if _redis_sync is None:
        try:
            from app.config import get_settings
            settings = get_settings()
            _redis_sync = redis_sync_lib.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            _redis_sync.ping()
            logger.info("Sync Redis client initialised for Celery worker.")
        except Exception as exc:
            logger.warning(
                "Sync Redis unavailable (%s) — falling back to fakeredis.", exc
            )
            try:
                import fakeredis
                _redis_sync = fakeredis.FakeRedis(decode_responses=True)
            except ImportError:
                # fakeredis not installed — create a no-op stub so the task
                # still runs; quota enforcement will be disabled but won't crash.
                logger.error(
                    "fakeredis not installed and Redis is unavailable. "
                    "Subscription quota enforcement is DISABLED for this worker."
                )
                _redis_sync = _NoopRedis()  # type: ignore[assignment]
    return _redis_sync


class _NoopRedis:
    """Minimal stub that disables quota enforcement when Redis is unreachable."""

    def get(self, *_a, **_kw):
        return None

    def incr(self, *_a, **_kw):
        return 0

    def decr(self, *_a, **_kw):
        return 0

    def expire(self, *_a, **_kw):
        return False

    def ping(self):
        return True


# ── Sync WhatsApp rejection sender ────────────────────────────────────────────

def _send_rejection_sync(
    to_phone: str,
    tenant_id: str,
    phone_number_id: str,
    access_token: str,
) -> None:
    """
    Send the quota-exceeded message to the customer via a synchronous HTTP call.

    Uses httpx directly (not the async whatsapp_sender) because this runs
    inside a sync Celery task.  A single attempt is made — delivery failures
    are logged but do not cause the task to retry (we already dropped the msg).
    """
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": _QUOTA_EXCEEDED_MSG},
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        logger.info(
            "Quota rejection sent — tenant=%s to=%s status=%d",
            tenant_id, to_phone, resp.status_code,
        )
    except Exception as exc:
        logger.warning(
            "Failed to send quota rejection to %s (tenant=%s): %s",
            to_phone, tenant_id, exc,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _set_log_context(tenant_id: str, trace_id: str) -> None:
    """Propagate tenant / trace identifiers into the logging ContextVars."""
    tenant_id_var.set(tenant_id)
    trace_id_var.set(trace_id)


# ── Celery task ────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="tasks.message_tasks.process_inbound_message",
    max_retries=5,
    retry_backoff=True,
    retry_backoff_max=300,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_inbound_message(self, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Process a single inbound WhatsApp message through the full AI pipeline.

    Expected payload keys (set by the webhook router):
        wa_message_id          – WhatsApp message ID (dedup key)
        customer_phone         – sender's phone number
        tenant_id              – owning tenant UUID string
        tenant_whatsapp_number – tenant's WhatsApp number (for logging)
        content                – message body (Arabic or otherwise)

    Pipeline:
        1. Subscription quota check  ← NEW: enforced before any AI work
        2. Langfuse trace start
        3. RAG retrieval span
        4. LLM call + generation recording
        5. Trace close

    Retry:
        Quota denials are never retried (returned immediately).
        All other unhandled exceptions retry with exponential back-off.
    """
    wa_message_id: str = payload.get("wa_message_id", "")
    customer_phone: str = payload.get("customer_phone", "")
    tenant_id: str = payload.get("tenant_id", "")
    message_text: str = payload.get("content", payload.get("message_text", ""))
    conversation_id: str = payload.get("conversation_id", "")

    # ── 1. Subscription quota check ────────────────────────────────────────────
    from app.services.subscription import check_and_increment

    quota = check_and_increment(tenant_id, _get_redis_sync())

    if not quota.allowed:
        logger.warning(
            "Quota exceeded — dropping message (no retry) tenant=%s "
            "wa_message_id=%s used=%d limit=%s tier=%s",
            tenant_id, wa_message_id, quota.used, quota.limit, quota.tier,
        )

        # Notify the customer politely if we have the necessary credentials
        if customer_phone:
            try:
                from app.config import get_settings
                s = get_settings()
                if s.WHATSAPP_TOKEN and s.WHATSAPP_PHONE_NUMBER_ID:
                    _send_rejection_sync(
                        to_phone=customer_phone,
                        tenant_id=tenant_id,
                        phone_number_id=s.WHATSAPP_PHONE_NUMBER_ID,
                        access_token=s.WHATSAPP_TOKEN,
                    )
            except Exception as exc:
                logger.warning("Could not send quota rejection: %s", exc)

        return {
            "status": "quota_exceeded",
            "wa_message_id": wa_message_id,
            "used": quota.used,
            "limit": quota.limit,
            "tier": quota.tier,
        }

    # ── 2. Start Langfuse trace ────────────────────────────────────────────────
    trace = create_trace(
        "process_message",
        user_id=customer_phone,
        tenant_id=tenant_id,
        input_data={
            "wa_message_id": wa_message_id,
            "message_text": message_text,
            "conversation_id": conversation_id,
        },
    )

    _set_log_context(tenant_id, trace.id)

    logger.info(
        "Processing inbound message",
        extra={
            "wa_message_id": wa_message_id,
            "customer_phone": customer_phone,
            "conversation_id": conversation_id,
            "quota_used": quota.used,
            "quota_limit": quota.limit,
            "attempt": self.request.retries + 1,
        },
    )

    try:
        # ── 3. RAG Retrieval span ──────────────────────────────────────────────
        retrieved_chunks: list[dict[str, Any]] = []
        retrieval_scores: list[float] = []

        with span_ctx(
            trace,
            "rag_retrieval",
            input_data={"query": message_text, "tenant_id": tenant_id},
        ) as rag_span:
            # TODO (TASK-011): replace stub with real retrieval call:
            # retrieved_chunks = await retrieve_context(message_text, tenant_id)
            retrieved_chunks = []  # stub
            retrieval_scores = []  # stub

            logger.info(
                "RAG retrieval complete",
                extra={
                    "chunks_count": len(retrieved_chunks),
                    "top_score": retrieval_scores[0] if retrieval_scores else None,
                },
            )
            rag_span.update(
                output={
                    "chunks_count": len(retrieved_chunks),
                    "top_scores": retrieval_scores[:3],
                }
            )

        # ── 4. LLM call + generation recording ────────────────────────────────
        # TODO (TASK-011): replace stub with real LLM call via llm_orchestrator
        llm_start = time.perf_counter()

        messages: list[dict[str, str]] = [
            {"role": "user", "content": message_text},
        ]
        response_text: str = ""
        model_name: str = "deepseek-chat"
        tokens_input: int = 0
        tokens_output: int = 0

        llm_latency_ms = round((time.perf_counter() - llm_start) * 1000, 2)

        end_generation(
            trace,
            name="llm_response",
            model=model_name,
            messages=messages,
            response_text=response_text,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            latency_ms=llm_latency_ms,
            metadata={"conversation_id": conversation_id},
        )

        logger.info(
            "LLM response generated",
            extra={
                "model": model_name,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "latency_ms": llm_latency_ms,
            },
        )

        # ── 5. Close trace with success outcome ────────────────────────────────
        result: dict[str, Any] = {
            "status": "processed",
            "wa_message_id": wa_message_id,
            "chunks_used": len(retrieved_chunks),
            "quota_used": quota.used,
            "quota_limit": quota.limit,
        }
        trace.update(output=result)

        logger.info("Message pipeline completed", extra={"result": result})
        return result

    except Exception as exc:
        countdown = min(2 ** self.request.retries, 300)

        logger.error(
            "Message pipeline failed — retrying",
            extra={
                "wa_message_id": wa_message_id,
                "attempt": self.request.retries + 1,
                "retry_countdown_s": countdown,
                "error": str(exc),
            },
            exc_info=True,
        )
        try:
            trace.update(output={"status": "error", "error": str(exc)})
        except Exception:  # noqa: BLE001
            pass

        raise self.retry(exc=exc, countdown=countdown)

    finally:
        flush()
