"""
tasks/message_tasks.py
───────────────────────
Celery task: process_inbound_message

Drives the full inbound message processing pipeline with end-to-end
Langfuse observability:

  Trace: "process_message"
    └─ Span:       "rag_retrieval"
    └─ Generation: "llm_response"

TASK-011 populates this stub with the real retrieval + LLM logic.
TASK-014 adds the observability harness (spans, generations, structured logs).

Retry policy: up to 5 attempts with exponential back-off (capped at 300 s).
"""
from __future__ import annotations

import logging
import time
from typing import Any

from celery_app import celery_app
from core.logging import tenant_id_var, trace_id_var
from core.observability import create_trace, end_generation, flush, span_ctx

logger = logging.getLogger(__name__)


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
        wa_message_id   – WhatsApp message ID (dedup key)
        customer_phone  – sender's phone number (Langfuse user_id)
        tenant_id       – owning tenant UUID string
        message_text    – raw message body (Arabic or otherwise)
        conversation_id – internal conversation UUID string

    Observability:
        • Langfuse trace "process_message" wraps the entire task.
        • Span "rag_retrieval" captures retrieval quality (chunks, scores).
        • Generation "llm_response" captures model, tokens, and latency.
        • trace_id is written to ContextVar so every log line in this call
          carries the same trace identifier automatically.

    Retry:
        On any unhandled exception the task retries with exponential back-off
        (2^n seconds, capped at 300 s). After all retries the exception is
        propagated to the Dead Letter Queue (DLQ).
    """
    wa_message_id: str = payload.get("wa_message_id", "")
    customer_phone: str = payload.get("customer_phone", "")
    tenant_id: str = payload.get("tenant_id", "")
    message_text: str = payload.get("message_text", "")
    conversation_id: str = payload.get("conversation_id", "")

    # ── 1. Start Langfuse trace ────────────────────────────────────────────────
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

    # Propagate IDs into logging context so every log below carries them
    _set_log_context(tenant_id, trace.id)

    logger.info(
        "Processing inbound message",
        extra={
            "wa_message_id": wa_message_id,
            "customer_phone": customer_phone,
            "conversation_id": conversation_id,
            "attempt": self.request.retries + 1,
        },
    )

    try:
        # ── 2. RAG Retrieval span ──────────────────────────────────────────────
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

        # ── 3. LLM call + generation recording ────────────────────────────────
        # TODO (TASK-011): replace stub with real LLM call via llm_orchestrator
        llm_start = time.perf_counter()

        # Build messages array (stub — TASK-011 will add system prompt + history)
        messages: list[dict[str, str]] = [
            {"role": "user", "content": message_text},
        ]
        response_text: str = ""     # stub — TASK-011 sets the real value
        model_name: str = "deepseek-chat"
        tokens_input: int = 0       # stub
        tokens_output: int = 0      # stub

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

        # ── 4. Close trace with success outcome ────────────────────────────────
        result: dict[str, Any] = {
            "status": "processed",
            "wa_message_id": wa_message_id,
            "chunks_used": len(retrieved_chunks),
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
        # Always flush Langfuse events — even on retry / failure
        flush()
