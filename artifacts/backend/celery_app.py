from __future__ import annotations

from typing import Any

from celery import Celery, Task
from celery.signals import setup_logging
from kombu import Queue

from app.config import get_settings
from core.logging import configure_logging

settings = get_settings()


def _extract_payload(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict:
    if args and isinstance(args[0], dict):
        return args[0]
    payload = kwargs.get("payload") or kwargs.get("payload_dict")
    if isinstance(payload, dict):
        return payload
    return {"args": list(args), "kwargs": kwargs}


class DeadLetterTask(Task):
    abstract = True
    max_retries = 5
    retry_backoff = True
    retry_backoff_max = 300
    acks_late = True
    reject_on_worker_lost = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if self.name != "tasks.dlq_tasks.handle_dead_letter":
            from tasks.dlq_tasks import handle_dead_letter

            handle_dead_letter.apply_async(
                kwargs={
                    "original_task_name": self.name,
                    "payload": _extract_payload(args, kwargs),
                    "error": repr(exc),
                    "traceback": str(einfo),
                },
                queue="dlq",
            )
        super().on_failure(exc, task_id, args, kwargs, einfo)


celery_app = Celery(
    "whatsapp_saas",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "tasks.message_tasks",
        "tasks.dlq_tasks",
        "tasks.ingestion_tasks",
    ],
    task_cls=DeadLetterTask,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_default_queue="default",
    task_default_exchange="tasks",
    task_default_exchange_type="direct",
    task_default_routing_key="default",
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("dlq", routing_key="dlq"),
    ),
    task_routes={
        "tasks.message_tasks.process_inbound_message": {
            "queue": "default",
            "routing_key": "default",
        },
        "tasks.ingestion_tasks.ingest_document": {
            "queue": "default",
            "routing_key": "default",
        },
        "tasks.dlq_tasks.handle_dead_letter": {
            "queue": "dlq",
            "routing_key": "dlq",
        },
    },
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)


@setup_logging.connect
def setup_celery_logging(**kwargs) -> None:
    configure_logging(service="celery_worker")
