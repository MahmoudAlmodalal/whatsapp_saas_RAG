"""
core/logging.py
───────────────
Structured JSON logging for all services (API + Celery workers).

Every log record is emitted as a single-line JSON object with stable fields:
  {
    "timestamp":   ISO-8601 string,
    "service":     e.g. "api" | "worker",
    "tenant_id":   UUID string or "",
    "trace_id":    Langfuse trace-id or self-generated UUID or "",
    "level":       "INFO" | "WARNING" | "ERROR" | …,
    "message":     human-readable log text,
    … extra fields passed as keyword arguments
  }

Usage:
    from core.logging import configure_logging, get_logger

    configure_logging("api")                        # once at startup
    log = get_logger(__name__)

    log.info("Webhook received", extra={"wa_message_id": mid, "tenant_id": tid})
    log.error("Pipeline failed", extra={"document_id": doc_id}, exc_info=True)

Context vars:
    tenant_id_var and trace_id_var are ContextVar instances.  Set them at
    request / task boundaries so every downstream log call within that context
    automatically includes the correct identifiers without explicit passing.

        from core.logging import tenant_id_var, trace_id_var
        tenant_id_var.set(str(tenant_uuid))
        trace_id_var.set(langfuse_trace.id)
"""
import logging
import sys
from contextvars import ContextVar
from typing import Any

from pythonjsonlogger import jsonlogger

# ── Context variables (propagated via ContextVar across async / sync calls) ────
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


# ── JSON formatter ─────────────────────────────────────────────────────────────

class ContextJsonFormatter(jsonlogger.JsonFormatter):
    """
    JSON formatter with stable field names expected by the log platform.

    Fields always present (even if empty string):
      timestamp, service_name, tenant_id, trace_id, level, message
    """

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        # Rename / normalise fields
        log_record["timestamp"] = log_record.pop("asctime", record.created)
        log_record["level"] = log_record.pop("levelname", record.levelname)
        log_record["service_name"] = log_record.pop("service", "")
        log_record.setdefault("tenant_id", "")
        log_record.setdefault("trace_id", "")
        log_record.setdefault("message", record.getMessage())

        # Ensure consistent key ordering for readability
        ordered: dict[str, Any] = {
            "timestamp": log_record.pop("timestamp"),
            "level": log_record.pop("level"),
            "service_name": log_record.pop("service_name"),
            "tenant_id": log_record.pop("tenant_id"),
            "trace_id": log_record.pop("trace_id"),
            "message": log_record.pop("message"),
        }
        # Append remaining (extra) fields
        ordered.update(log_record)
        log_record.clear()
        log_record.update(ordered)


# ── Context filter (injects ContextVar values into every record) ───────────────

class RequestContextFilter(logging.Filter):
    """
    Injects tenant_id and trace_id from ContextVars into every LogRecord.

    Records that already have these attributes (set explicitly by the caller)
    are not overwritten, giving per-call overrides priority.
    """

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        # service_name: prefer record-level override, fall back to process-level
        if not getattr(record, "service", ""):
            record.service = self.service  # type: ignore[attr-defined]

        # tenant_id
        if not getattr(record, "tenant_id", ""):
            record.tenant_id = tenant_id_var.get() or ""  # type: ignore[attr-defined]

        # trace_id
        if not getattr(record, "trace_id", ""):
            record.trace_id = trace_id_var.get() or ""  # type: ignore[attr-defined]

        return True


# ── Public API ─────────────────────────────────────────────────────────────────

def configure_logging(service: str, level: int = logging.INFO) -> None:
    """
    Configure process-wide JSON logging for API and worker processes.

    Call once during application startup:
        configure_logging("api")      # FastAPI main.py
        configure_logging("worker")   # celery_app.py / worker entrypoint

    Args:
        service: Short service name embedded in every log line (e.g. "api").
        level:   Root logger level (default: INFO).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        ContextJsonFormatter(
            "%(asctime)s %(service)s %(tenant_id)s %(trace_id)s %(levelname)s %(message)s"
        )
    )
    handler.addFilter(RequestContextFilter(service=service))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """
    Return a standard Python logger.

    The RequestContextFilter installed by ``configure_logging`` will
    automatically inject tenant_id and trace_id into every record.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        logging.Logger instance.
    """
    return logging.getLogger(name)
