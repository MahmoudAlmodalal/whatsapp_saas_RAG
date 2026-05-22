import hmac
import hashlib
import json
import pytest
from fastapi import status
from app.config import get_settings
from app.core.cache import redis_client

pytestmark = pytest.mark.asyncio
settings = get_settings()


def calculate_signature(payload_bytes: bytes, secret: str) -> str:
    """Calculate the sha256 HMAC signature for test payloads."""
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def make_whatsapp_payload(
    msg_id: str,
    msg_type: str = "text",
    content: str = "مرحباً",
    tenant_phone: str = "+966501234567",
) -> dict:
    """Generate a valid mock WhatsApp webhook payload structure."""
    msg_data = {
        "from": "966500000000",
        "id": msg_id,
        "timestamp": "1716000000",
        "type": msg_type
    }
    
    if msg_type == "text":
        msg_data["text"] = {"body": content}
    elif msg_type in ("audio", "image", "document"):
        msg_data[msg_type] = {"id": f"media_id_{msg_id}"}
        
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_id_123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": tenant_phone,
                                "phone_number_id": "phone-number-id-123",
                            },
                            "messages": [msg_data]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }


# ─── GET Webhook Verification Tests ───

async def test_verify_webhook_success(client):
    """Verify that Meta's verification challenge returns HTTP 200 and the challenge string."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
        "hub.challenge": "verification_challenge_123"
    }
    response = await client.get("/api/v1/webhook/whatsapp", params=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.text == "verification_challenge_123"


async def test_verify_webhook_token_mismatch(client):
    """Verify that wrong verification token returns HTTP 403 Forbidden."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong-token",
        "hub.challenge": "challenge"
    }
    response = await client.get("/api/v1/webhook/whatsapp", params=params)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Verification token mismatch" in response.json()["detail"]


# ─── POST Webhook Receiver & Processing Tests ───

async def test_receive_webhook_missing_signature(client):
    """Verify that POST requests with no signature header return HTTP 403 Forbidden."""
    payload = make_whatsapp_payload("msg_1")
    response = await client.post("/api/v1/webhook/whatsapp", json=payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Signature missing" in response.json()["detail"]


async def test_receive_webhook_invalid_signature(client):
    """Verify that POST requests with an incorrect signature return HTTP 403 Forbidden."""
    payload = make_whatsapp_payload("msg_1")
    headers = {"X-Hub-Signature-256": "sha256=invalidhashvalue12345"}
    response = await client.post("/api/v1/webhook/whatsapp", json=payload, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Invalid signature" in response.json()["detail"]


async def test_receive_webhook_success_and_celery_dispatch(client, mock_celery_task, test_tenant):
    """Verify that a valid webhook registers in Redis, returns 200 immediately, and triggers Celery."""
    payload = make_whatsapp_payload(
        "msg_success_1",
        "text",
        "أهلاً بك",
        tenant_phone=test_tenant.whatsapp_number,
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    
    headers = {"X-Hub-Signature-256": calculate_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)}
    
    # We must post the bytes directly to preserve matching signature validation
    response = await client.post(
        "/api/v1/webhook/whatsapp",
        content=payload_bytes,
        headers=headers,
        extensions={"headers": [("content-type", "application/json")]}
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "accepted"}
    
    # Since background tasks execute after returning the response, we wait a tiny bit to let the background task complete.
    import asyncio
    await asyncio.sleep(0.1)
    
    # Verify that the message is cached as processed in Redis (for deduplication)
    cached_val = await redis_client.get("dedup:msg_success_1")
    ttl = await redis_client.ttl("dedup:msg_success_1")
    assert cached_val == "1"
    assert 0 < ttl <= 86400
    
    mock_celery_task.assert_called_once()
    dispatched_payload = mock_celery_task.call_args.args[0]
    assert dispatched_payload["tenant_id"] == str(test_tenant.id)
    assert dispatched_payload["tenant_whatsapp_number"] == test_tenant.whatsapp_number
    assert dispatched_payload["wa_message_id"] == "msg_success_1"
    assert dispatched_payload["customer_phone"] == "966500000000"
    assert dispatched_payload["message_type"] == "text"
    assert dispatched_payload["content"] == "أهلاً بك"
    assert dispatched_payload["media_id"] is None
    assert dispatched_payload["timestamp"] == "1716000000"
    assert dispatched_payload["raw_payload"] == payload


async def test_receive_webhook_deduplication_skips_dispatch(client, mock_celery_task, test_tenant):
    """Verify that duplicate message IDs return HTTP 200 but skip Celery task dispatching."""
    msg_id = "msg_duplicate_999"
    payload = make_whatsapp_payload(
        msg_id,
        "text",
        "مكرر",
        tenant_phone=test_tenant.whatsapp_number,
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    
    headers = {"X-Hub-Signature-256": calculate_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)}
    
    # Send first time
    response1 = await client.post(
        "/api/v1/webhook/whatsapp",
        content=payload_bytes,
        headers=headers,
        extensions={"headers": [("content-type", "application/json")]}
    )
    assert response1.status_code == status.HTTP_200_OK
    
    # Send second time (duplicate)
    response2 = await client.post(
        "/api/v1/webhook/whatsapp",
        content=payload_bytes,
        headers=headers,
        extensions={"headers": [("content-type", "application/json")]}
    )
    assert response2.status_code == status.HTTP_200_OK
    
    import asyncio
    await asyncio.sleep(0.1)
    
    # Celery should only have been called ONCE (for the first request)
    mock_celery_task.assert_called_once()
    assert mock_celery_task.call_args.args[0]["wa_message_id"] == msg_id


async def test_webhook_different_media_types(client, mock_celery_task, test_tenant):
    """Verify that different media types (audio, image, document) are successfully parsed and enqueued."""
    media_types = ["audio", "image", "document"]
    expected_content = {
        "audio": "[audio message]",
        "image": "[image message]",
        "document": "[document]",
    }
    
    for m_type in media_types:
        msg_id = f"msg_{m_type}_id_100"
        payload = make_whatsapp_payload(
            msg_id,
            m_type,
            tenant_phone=test_tenant.whatsapp_number,
        )
        payload_bytes = json.dumps(payload).encode("utf-8")
        
        headers = {"X-Hub-Signature-256": calculate_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)}
        
        response = await client.post(
            "/api/v1/webhook/whatsapp",
            content=payload_bytes,
            headers=headers,
            extensions={"headers": [("content-type", "application/json")]}
        )
        assert response.status_code == status.HTTP_200_OK
        
    import asyncio
    await asyncio.sleep(0.1)
    
    # Verify Celery was called 3 times (once for each media type)
    assert mock_celery_task.call_count == 3
    dispatched_payloads = [call.args[0] for call in mock_celery_task.call_args_list]
    assert [item["message_type"] for item in dispatched_payloads] == media_types
    for item in dispatched_payloads:
        assert item["tenant_id"] == str(test_tenant.id)
        assert item["content"] == expected_content[item["message_type"]]
        assert item["media_id"] == f"media_id_{item['wa_message_id']}"


async def test_webhook_unsupported_message_type_skips_dispatch(client, mock_celery_task, test_tenant):
    """Verify unsupported WhatsApp message types are acknowledged but not enqueued."""
    payload = make_whatsapp_payload(
        "msg_unsupported_1",
        "sticker",
        tenant_phone=test_tenant.whatsapp_number,
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    headers = {"X-Hub-Signature-256": calculate_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)}

    response = await client.post(
        "/api/v1/webhook/whatsapp",
        content=payload_bytes,
        headers=headers,
        extensions={"headers": [("content-type", "application/json")]}
    )

    assert response.status_code == status.HTTP_200_OK

    import asyncio
    await asyncio.sleep(0.1)

    mock_celery_task.assert_not_called()
    assert await redis_client.get("dedup:msg_unsupported_1") is None


async def test_webhook_unmapped_tenant_skips_dispatch(client, mock_celery_task):
    """Verify inbound messages without a WhatsApp phone mapping are acknowledged and skipped."""
    payload = make_whatsapp_payload(
        "msg_unmapped_1",
        "text",
        "لا يوجد مستأجر",
        tenant_phone="+966509999999",
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    headers = {"X-Hub-Signature-256": calculate_signature(payload_bytes, settings.WHATSAPP_APP_SECRET)}

    response = await client.post(
        "/api/v1/webhook/whatsapp",
        content=payload_bytes,
        headers=headers,
        extensions={"headers": [("content-type", "application/json")]}
    )

    assert response.status_code == status.HTTP_200_OK

    import asyncio
    await asyncio.sleep(0.1)

    mock_celery_task.assert_not_called()
    assert await redis_client.get("dedup:msg_unmapped_1") is None
