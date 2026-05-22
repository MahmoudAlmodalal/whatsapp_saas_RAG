"""
core/observability.py
─────────────────────
Langfuse observability client + context-manager helpers.

Design principles:
  • Single Langfuse client (singleton) shared across the process.
  • All public functions degrade gracefully: if Langfuse is unavailable or
    misconfigured, a no-op shim is returned so that tracing NEVER breaks the
    main business flow.
  • trace_id is propagated through contextvars so that every log line emitted
    inside a traced request automatically carries the same trace_id.

Usage (Celery task):
    from core.observability import create_trace, span_ctx, generation_ctx

    trace = create_trace("process_message", user_id=phone, tenant_id=tid)
    with span_ctx(trace, "rag_retrieval", input_data={"query": q}) as sp:
        chunks = retrieve(...)
        sp.update(output={"chunks_count": len(chunks)})

    result_text = llm_call(...)
    end_generation(trace, model="deepseek-chat", ...)
    trace.update(output={"status": "ok"})
    flush()
"""
from __future__ import annotations

import contextlib
import logging
import time
import uuid
from typing import Any, Generator

logger = logging.getLogger(__name__)

# ── Lazy import so missing SDK never crashes the worker ────────────────────────
try:
    from langfuse import Langfuse
    from langfuse.api.resources.commons.errors.not_found_error import NotFoundError  # noqa: F401
    _LANGFUSE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGFUSE_AVAILABLE = False
    logger.warning(
        "langfuse package not installed — observability disabled. "
        "Add 'langfuse' to requirements.txt to enable."
    )


# ── No-op shims (used when Langfuse is unavailable / misconfigured) ────────────

class _NoOpSpan:
    """Drop-in replacement for a Langfuse Span when tracing is disabled."""

    def update(self, **kwargs: Any) -> "_NoOpSpan":  # noqa: ANN401
        return self

    def end(self, **kwargs: Any) -> None:
        pass


class _NoOpGeneration:
    """Drop-in replacement for a Langfuse Generation when tracing is disabled."""

    def update(self, **kwargs: Any) -> "_NoOpGeneration":  # noqa: ANN401
        return self

    def end(self, **kwargs: Any) -> None:
        pass


class _NoOpTrace:
    """Drop-in replacement for a Langfuse Trace when tracing is disabled."""

    id: str = ""

    def update(self, **kwargs: Any) -> "_NoOpTrace":  # noqa: ANN401
        return self

    def span(self, **kwargs: Any) -> _NoOpSpan:  # noqa: ANN401
        return _NoOpSpan()

    def generation(self, **kwargs: Any) -> _NoOpGeneration:  # noqa: ANN401
        return _NoOpGeneration()


# ── Client singleton ───────────────────────────────────────────────────────────

_client: "Langfuse | None" = None


def _get_client() -> "Langfuse | None":
    """
    Return the singleton Langfuse client, initialising it on first call.

    Returns None if the SDK is unavailable or keys are not configured so that
    callers can fall back to no-op shims without raising exceptions.
    """
    global _client  # noqa: PLW0603

    if _client is not None:
        return _client

    if not _LANGFUSE_AVAILABLE:
        return None

    try:
        from app.config import get_settings
        settings = get_settings()

        public_key = getattr(settings, "LANGFUSE_PUBLIC_KEY", "")
        secret_key = getattr(settings, "LANGFUSE_SECRET_KEY", "")
        host = getattr(settings, "LANGFUSE_HOST", "https://cloud.langfuse.com")

        if not public_key or not secret_key:
            logger.warning(
                "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set — "
                "Langfuse tracing disabled."
            )
            return None

        _client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        logger.info("Langfuse client initialised (host=%s)", host)
        return _client

    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse client init failed (%s) — tracing disabled.", exc)
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

def create_trace(
    name: str,
    *,
    user_id: str | None = None,
    tenant_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    input_data: Any = None,
) -> "Any":
    """
    Start a new Langfuse trace and propagate its ID into the logging context.

    Returns a real Langfuse trace object or a ``_NoOpTrace`` on failure.
    The returned object always exposes ``.id``, ``.span()``, ``.generation()``,
    and ``.update()`` so callers need no ``if`` guards.
    """
    from core.logging import trace_id_var  # local import to avoid cycles

    client = _get_client()
    if client is None:
        noop = _NoOpTrace()
        noop.id = str(uuid.uuid4())
        trace_id_var.set(noop.id)
        return noop

    try:
        meta = dict(metadata or {})
        if tenant_id:
            meta["tenant_id"] = tenant_id

        trace = client.trace(
            name=name,
            user_id=user_id,
            metadata=meta,
            input=input_data,
        )
        # Propagate to structured logging
        trace_id_var.set(trace.id)
        return trace
    except Exception as exc:  # noqa: BLE001
        logger.warning("create_trace failed (%s) — returning no-op trace.", exc)
        noop = _NoOpTrace()
        noop.id = str(uuid.uuid4())
        trace_id_var.set(noop.id)
        return noop


@contextlib.contextmanager
def span_ctx(
    trace: Any,
    name: str,
    *,
    input_data: Any = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """
    Context manager that wraps a pipeline stage in a Langfuse span.

    Automatically records ``start_time`` / ``end_time`` and ``latency_ms``.
    The yielded object exposes ``.update(output=..., metadata=...)`` for
    callers that want to attach results before the span closes.

    Example::

        with span_ctx(trace, "rag_retrieval", input_data={"query": q}) as sp:
            chunks = retrieve(q)
            sp.update(output={"chunks_count": len(chunks)})
    """
    start = time.perf_counter()
    span: Any = _NoOpSpan()

    try:
        span = trace.span(
            name=name,
            input=input_data,
            metadata=metadata or {},
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("span_ctx — could not create span '%s': %s", name, exc)

    try:
        yield span
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        try:
            span.end(metadata={"latency_ms": elapsed_ms})
        except Exception as exc:  # noqa: BLE001
            logger.debug("span_ctx — could not end span '%s': %s", name, exc)


def end_generation(
    trace: Any,
    *,
    name: str = "llm_response",
    model: str,
    messages: list[dict[str, str]] | None = None,
    response_text: str = "",
    tokens_input: int = 0,
    tokens_output: int = 0,
    latency_ms: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Record a completed LLM generation on an existing trace.

    Wraps ``trace.generation()`` in a try/except so failures are logged but
    never propagated to callers.
    """
    try:
        gen = trace.generation(
            name=name,
            model=model,
            input=messages or [],
            output=response_text,
            usage={
                "input": tokens_input,
                "output": tokens_output,
                "total": tokens_input + tokens_output,
            },
            metadata={**(metadata or {}), "latency_ms": latency_ms},
        )
        gen.end()
    except Exception as exc:  # noqa: BLE001
        logger.debug("end_generation failed (%s) — skipping.", exc)


def flush() -> None:
    """
    Flush pending Langfuse events to the remote server.

    Should be called at the end of every Celery task to ensure events are
    shipped before the worker process idles or is terminated.
    """
    client = _get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Langfuse flush failed (%s) — events may be buffered.", exc)
