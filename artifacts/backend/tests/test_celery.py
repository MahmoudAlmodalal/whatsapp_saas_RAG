import logging
from unittest.mock import patch

from celery_app import celery_app
from tasks.dlq_tasks import handle_dead_letter
from tasks.ingestion_tasks import ingest_document
from tasks.message_tasks import process_inbound_message


def test_celery_queues_and_defaults_are_configured():
    queue_names = {queue.name for queue in celery_app.conf.task_queues}

    assert {"default", "dlq"}.issubset(queue_names)
    assert celery_app.conf.task_default_queue == "default"
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True


def test_ingestion_task_is_registered_on_default_queue():
    assert ingest_document.name == "tasks.ingestion_tasks.ingest_document"
    assert celery_app.conf.task_routes["tasks.ingestion_tasks.ingest_document"] == {
        "queue": "default",
        "routing_key": "default",
    }


def test_process_inbound_message_stub_returns_processed_status():
    result = process_inbound_message({"wa_message_id": "wamid.test"})

    assert result == {"status": "processed"}


def test_handle_dead_letter_logs_failed_task(caplog):
    caplog.set_level(logging.ERROR)

    result = handle_dead_letter(
        original_task_name="tasks.message_tasks.process_inbound_message",
        payload={"wa_message_id": "wamid.failed"},
        error="RuntimeError('boom')",
        traceback="traceback details",
    )

    assert result == {"status": "logged"}
    assert "DEAD LETTER" in caplog.text
    assert "tasks.message_tasks.process_inbound_message" in caplog.text


def test_failed_task_routes_to_dlq_queue():
    payload = {"wa_message_id": "wamid.failed"}

    with patch("tasks.dlq_tasks.handle_dead_letter.apply_async") as mock_apply_async:
        process_inbound_message.on_failure(
            exc=RuntimeError("boom"),
            task_id="task-id-123",
            args=(payload,),
            kwargs={},
            einfo="traceback details",
        )

    mock_apply_async.assert_called_once()
    call_kwargs = mock_apply_async.call_args.kwargs
    assert call_kwargs["queue"] == "dlq"
    assert call_kwargs["kwargs"]["original_task_name"] == (
        "tasks.message_tasks.process_inbound_message"
    )
    assert call_kwargs["kwargs"]["payload"] == payload
    assert "boom" in call_kwargs["kwargs"]["error"]
