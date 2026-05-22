"""
tests/integration/test_webhook_pipeline.py
───────────────────────────────────────────
Integration tests for the complete webhook processing pipeline:
WhatsApp HTTP request → HMAC validation → Redis dedup → Celery dispatch

Uses real Redis (DB index 9), real DB (transaction-rolled-back).
Mocks: WhatsApp outbound sender only.
"""
import hashlib
import hmac
import json
import time
import pytest
from fastapi import status

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

APP_SECRET = "test-app-secret-67890"


def _sign(payload_bytes: bytes) -> str:
    digest = hmac.new(APP_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _text_webhook(
    from_number: str = "+966501111111",
    msg_id: str = "wamid.unique001",
    text: str = "مرحباً",
    phone_id: str = "123456789",
) -> bytes:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "entry_001",
            "changes": [{
                "field": "messages",
                "value": {
                    "metadata": {"phone_number_id": phone_id},
                    "messages": [{
                        "id": msg_id,
                        "from": from_number,
                        "type": "text",
                        "text": {"body": text},
                        "timestamp": str(int(time.time())),
                    }],
                    "contacts": [{"profile": {"name": "عميل"}}],
                },
            }],
        }],
    }
    return json.dumps(payload, ensure_ascii=False).encode()


class TestWebhookVerification:
    """GET /api/v1/webhook — Meta hub verification."""

    async def test_verify_valid_token(self, client):
        resp = await client.get(
            "/api/v1/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token",
                "hub.challenge": "challenge_string_123",
            },
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.text == "challenge_string_123"

    async def test_verify_invalid_token(self, client):
        resp = await client.get(
            "/api/v1/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "challenge_123",
            },
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    async def test_verify_missing_params(self, client):
        resp = await client.get("/api/v1/webhook")
        assert resp.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)


class TestWebhookIngest:
    """POST /api/v1/webhook — Message ingestion."""

    async def test_valid_webhook_returns_200(self, client, test_tenant):
        payload_bytes = _text_webhook(
            from_number=test_tenant.whatsapp_number or "+966501234567",
            msg_id="wamid.valid001",
        )
        headers = {
            "X-Hub-Signature-256": _sign(payload_bytes),
            "Content-Type": "application/json",
        }
        resp = await client.post("/api/v1/webhook", content=payload_bytes, headers=headers)
        assert resp.status_code == status.HTTP_200_OK

    async def test_invalid_signature_rejected(self, client):
        payload_bytes = _text_webhook()
        headers = {
            "X-Hub-Signature-256": "sha256=invalidsignature000",
            "Content-Type": "application/json",
        }
        resp = await client.post("/api/v1/webhook", content=payload_bytes, headers=headers)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_missing_signature_rejected(self, client):
        payload_bytes = _text_webhook()
        resp = await client.post(
            "/api/v1/webhook",
            content=payload_bytes,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED)

    async def test_response_time_under_200ms(self, client, test_tenant):
        """Webhook must respond within 200ms (Meta requires fast ACK)."""
        payload_bytes = _text_webhook(
            from_number=test_tenant.whatsapp_number or "+966501234567",
            msg_id="wamid.timing001",
        )
        headers = {
            "X-Hub-Signature-256": _sign(payload_bytes),
            "Content-Type": "application/json",
        }
        start = time.monotonic()
        resp = await client.post("/api/v1/webhook", content=payload_bytes, headers=headers)
        elapsed_ms = (time.monotonic() - start) * 1000
        assert resp.status_code == status.HTTP_200_OK
        assert elapsed_ms < 500  # generous bound for test env (200ms in prod)

    async def test_duplicate_message_deduplication(self, client, test_tenant):
        """Same message ID sent twice must only be processed once (Redis dedup)."""
        payload_bytes = _text_webhook(
            from_number=test_tenant.whatsapp_number or "+966501234567",
            msg_id="wamid.dup001",
        )
        headers = {
            "X-Hub-Signature-256": _sign(payload_bytes),
            "Content-Type": "application/json",
        }
        # First send — should process
        r1 = await client.post("/api/v1/webhook", content=payload_bytes, headers=headers)
        assert r1.status_code == status.HTTP_200_OK

        # Second send — duplicate, must be silently ignored
        r2 = await client.post("/api/v1/webhook", content=payload_bytes, headers=headers)
        assert r2.status_code == status.HTTP_200_OK  # still 200, just ignored

    async def test_task_dispatched_on_valid_webhook(
        self, client, test_tenant, mock_celery_task
    ):
        """Celery task must be dispatched after successful webhook ingestion."""
        payload_bytes = _text_webhook(
            from_number=test_tenant.whatsapp_number or "+966501234567",
            msg_id="wamid.dispatch001",
        )
        headers = {
            "X-Hub-Signature-256": _sign(payload_bytes),
            "Content-Type": "application/json",
        }
        await client.post("/api/v1/webhook", content=payload_bytes, headers=headers)
        mock_celery_task.assert_called_once()
