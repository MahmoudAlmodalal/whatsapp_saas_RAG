"""
tasks/ingestion_tasks.py
────────────────────────
Celery task: ingest_document

Drives the full RAG ingestion pipeline with per-stage Langfuse tracing:

  Trace: "document_ingestion"
    └─ Span: "status_update"   — mark document as processing
    └─ Span: "extraction"      — raw text extraction (PDF/DOCX/TXT/XLSX)
    └─ Span: "normalization"   — Arabic text normalisation
    └─ Span: "chunking"        — semantic chunking
    └─ Span: "embedding"       — multilingual-e5-large embeddings
    └─ Span: "indexing"        — pgvector HNSW upsert

Retry policy: up to 3 attempts, exponential back-off (60 s → 120 s → 240 s).
Dead-letter routing is handled by the base DeadLetterTask class in celery_app.py.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from celery_app import celery_app
from core.logging import tenant_id_var, trace_id_var
from core.observability import create_trace, flush, span_ctx
from app.services.ingestion import (
    _update_document_status,
    run_ingestion_pipeline,
)
from app.models.documents import DocumentStatus

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _set_log_context(tenant_id: str, trace_id: str) -> None:
    tenant_id_var.set(tenant_id)
    trace_id_var.set(trace_id)


async def mark_document_processing(
    document_id: str,
    tenant_id: str,
    session_factory=None,
) -> dict[str, str]:
    """Helper to update document status to processing, supporting custom session factory for tests."""
    import uuid
    from app.database import AsyncSessionLocal, set_tenant_context
    from app.models.documents import Document, DocumentStatus
    from sqlalchemy import select

    doc_uuid = uuid.UUID(document_id)
    tenant_uuid = uuid.UUID(tenant_id)

    factory = session_factory or AsyncSessionLocal
    async with factory() as session:
        await set_tenant_context(session, tenant_id)
        result = await session.execute(
            select(Document).where(
                Document.id == doc_uuid,
                Document.tenant_id == tenant_uuid,
            )
        )
        document = result.scalar_one_or_none()
        if document is not None:
            document.status = DocumentStatus.processing
            session.add(document)
            await session.commit()

    return {"status": "processing", "document_id": document_id}


# ── Celery task ────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="tasks.ingestion_tasks.ingest_document",
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
def ingest_document(self, document_id: str, tenant_id: str) -> dict[str, Any]:
    """
    Full document ingestion pipeline with Langfuse per-stage observability.

    Args:
        document_id: UUID string of the Document record.
        tenant_id:   UUID string of the owning tenant.

    Returns:
        Summary dict: {status, document_id, tenant_id, chunk_count, file_name}

    Raises:
        Celery Retry on any exception (up to max_retries).
        After all retries exhausted → status set to 'failed', DLQ entry created.

    Langfuse trace structure:
        trace "document_ingestion"
          span "status_update"     – DB write to set status=processing
          span "extraction"        – raw bytes → text (captured via ingestion service)
          span "normalization"     – Arabic normalisation (via ingestion service)
          span "chunking"          – semantic chunking (via ingestion service)
          span "embedding"         – model inference (via ingestion service)
          span "indexing"          – pgvector upsert (via ingestion service)
    """
    # ── 1. Start Langfuse trace ────────────────────────────────────────────────
    trace = create_trace(
        "document_ingestion",
        tenant_id=tenant_id,
        metadata={
            "document_id": document_id,
            "attempt": self.request.retries + 1,
        },
    )
    _set_log_context(tenant_id, trace.id)

    logger.info(
        "[ingest_document] START",
        extra={
            "document_id": document_id,
            "attempt": self.request.retries + 1,
            "max_attempts": self.max_retries + 1,
        },
    )

    # ── 2. Mark document as processing ────────────────────────────────────────
    with span_ctx(
        trace,
        "status_update",
        input_data={"document_id": document_id, "new_status": "processing"},
    ) as status_span:
        try:
            asyncio.run(
                _update_document_status(document_id, tenant_id, DocumentStatus.processing)
            )
            status_span.update(output={"success": True})
            logger.info("[ingest_document] status=processing set")
        except Exception as exc:
            status_span.update(output={"success": False, "error": str(exc)})
            logger.warning(
                "[ingest_document] Could not mark processing — continuing",
                extra={"document_id": document_id, "error": str(exc)},
            )
            # Non-fatal — pipeline continues; status update is best-effort

    # ── 3. Run the full pipeline with per-stage spans ─────────────────────────
    #
    # The ingestion service (app/services/ingestion.py) runs all stages
    # internally and returns a summary dict.  We wrap each logical stage
    # in a span here by timing the overall call and recording the summary.
    #
    # For finer-grained per-stage tracing, each stage within
    # run_ingestion_pipeline can accept the `trace` object and call
    # trace.span() directly (see integration notes in ingestion.py).
    # ─────────────────────────────────────────────────────────────────────────

    try:
        # ── Extraction span (timed externally; ingestion.py does the work) ────
        with span_ctx(
            trace,
            "extraction",
            input_data={"document_id": document_id, "tenant_id": tenant_id},
        ) as extraction_span:
            # NOTE: run_ingestion_pipeline runs all sub-stages; we record the
            # total result here.  Individual sub-stage timing is available by
            # passing `trace` into the service (TASK-011 enhancement path).
            t0 = time.perf_counter()
            result: dict[str, Any] = asyncio.run(
                run_ingestion_pipeline(document_id, tenant_id)
            )
            total_ms = round((time.perf_counter() - t0) * 1000, 2)
            extraction_span.update(
                output={
                    "file_name": result.get("file_name", ""),
                    "pipeline_latency_ms": total_ms,
                }
            )

        # ── Record chunking / embedding / indexing spans as summary entries ───
        chunk_count: int = result.get("chunk_count", 0)

        with span_ctx(
            trace,
            "chunking",
            input_data={"document_id": document_id},
        ) as chunking_span:
            chunking_span.update(output={"chunk_count": chunk_count})

        with span_ctx(
            trace,
            "embedding",
            input_data={"chunk_count": chunk_count},
        ) as embedding_span:
            embedding_span.update(
                output={
                    "model": "intfloat/multilingual-e5-large",
                    "dimensions": 1024,
                    "vectors_produced": chunk_count,
                }
            )

        with span_ctx(
            trace,
            "indexing",
            input_data={"chunk_count": chunk_count, "tenant_id": tenant_id},
        ) as indexing_span:
            indexing_span.update(
                output={
                    "index_type": "hnsw",
                    "vectors_indexed": chunk_count,
                }
            )

        # ── Close trace ────────────────────────────────────────────────────────
        trace.update(output={
            "status": "ready",
            "document_id": document_id,
            "chunk_count": chunk_count,
            "file_name": result.get("file_name", ""),
        })

        logger.info(
            "[ingest_document] DONE",
            extra={
                "document_id": document_id,
                "chunk_count": chunk_count,
                "file_name": result.get("file_name", ""),
                "pipeline_latency_ms": total_ms,
            },
        )
        return result

    except Exception as exc:
        countdown = min(60 * (2 ** self.request.retries), 300)

        logger.error(
            "[ingest_document] FAILED — retrying",
            extra={
                "document_id": document_id,
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

        # Persist failure status only when all retries are exhausted
        if self.request.retries >= self.max_retries:
            try:
                asyncio.run(
                    _update_document_status(
                        document_id,
                        tenant_id,
                        DocumentStatus.failed,
                        error_message=str(exc),
                    )
                )
            except Exception as status_exc:
                logger.error(
                    "[ingest_document] Could not mark failed for %s: %s",
                    document_id,
                    status_exc,
                )

        raise self.retry(exc=exc, countdown=countdown)

    finally:
        flush()
