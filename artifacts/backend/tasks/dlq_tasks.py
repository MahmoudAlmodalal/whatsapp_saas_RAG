import logging

from celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.dlq_tasks.handle_dead_letter", queue="dlq")
def handle_dead_letter(
    original_task_name: str,
    payload: dict,
    error: str,
    traceback: str,
) -> dict:
    """Log permanently failed tasks for manual inspection."""
    logger.error(
        "DEAD LETTER: task=%s error=%s",
        original_task_name,
        error,
        extra={
            "original_task_name": original_task_name,
            "payload": payload,
            "traceback": traceback,
        },
    )
    # TODO Phase 2: store to DB dead_letter_items table
    return {"status": "logged"}

