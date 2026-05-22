import logging
import uuid
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.core.whatsapp import validate_whatsapp_signature
from app.core.cache import get_tenant_id_by_phone, redis_client
from tasks.message_tasks import process_inbound_message

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/webhook", tags=["webhook"])

SUPPORTED_MEDIA_PLACEHOLDERS = {
    "audio": "[audio message]",
    "image": "[image message]",
    "document": "[document]",
}


def _first_change_value(payload_dict: dict) -> dict:
    entry = payload_dict.get("entry") or []
    if not entry:
        return {}

    changes = entry[0].get("changes") or []
    if not changes:
        return {}

    return changes[0].get("value") or {}


def _first_message(value: dict) -> dict:
    messages = value.get("messages") or []
    if not messages:
        return {}

    return messages[0]


def _tenant_phone_from_value(value: dict) -> str | None:
    metadata = value.get("metadata") or {}
    return metadata.get("display_phone_number") or metadata.get("phone_number_id")


async def _lookup_tenant_id(tenant_phone: str | None) -> str | None:
    if not tenant_phone:
        return None

    candidates = [tenant_phone]
    if tenant_phone.startswith("+"):
        candidates.append(tenant_phone[1:])
    else:
        candidates.append(f"+{tenant_phone}")

    for candidate in dict.fromkeys(candidates):
        tenant_id = await get_tenant_id_by_phone(candidate)
        if tenant_id:
            return tenant_id

    return None


def _normalize_message(
    *,
    tenant_id: str,
    tenant_phone: str,
    message: dict,
    payload_dict: dict,
    trace_id: str,
) -> dict | None:
    message_type = message.get("type")
    wa_message_id = message.get("id")

    if not wa_message_id:
        logger.warning("[%s] Missing 'id' in WhatsApp message payload.", trace_id)
        return None

    media_id = None
    if message_type == "text":
        content = (message.get("text") or {}).get("body")
        if content is None:
            logger.warning("[%s] Missing text body in WhatsApp message: %s", trace_id, wa_message_id)
            return None
    elif message_type in SUPPORTED_MEDIA_PLACEHOLDERS:
        media = message.get(message_type) or {}
        media_id = media.get("id")
        content = SUPPORTED_MEDIA_PLACEHOLDERS[message_type]
    else:
        logger.info(
            "[%s] Unsupported WhatsApp message type skipped: %s",
            trace_id,
            message_type,
        )
        return None

    return {
        "tenant_id": tenant_id,
        "tenant_whatsapp_number": tenant_phone,
        "wa_message_id": wa_message_id,
        "customer_phone": message.get("from"),
        "message_type": message_type,
        "content": content,
        "media_id": media_id,
        "timestamp": message.get("timestamp"),
        "raw_message": message,
        "raw_payload": payload_dict,
        "trace_id": trace_id,
    }

@router.get("/whatsapp", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Verification endpoint for Meta WhatsApp Cloud API.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully by Meta.")
        return hub_challenge
    
    logger.warning("Webhook verification failed: Verify token mismatch.")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch"
    )

async def process_webhook_in_bg(payload_dict: dict, trace_id: str):
    """
    Background task to extract details, deduplicate using Redis, and dispatch to Celery.
    """
    try:
        value = _first_change_value(payload_dict)
        message = _first_message(value)

        if not message:
            logger.info(f"[{trace_id}] Webhook payload does not contain any messages. Skipping.")
            return

        tenant_phone = _tenant_phone_from_value(value)
        tenant_id = await _lookup_tenant_id(tenant_phone)
        if tenant_id is None:
            logger.warning(
                "[%s] No tenant mapping found for WhatsApp phone: %s",
                trace_id,
                tenant_phone,
            )
            return

        normalized_payload = _normalize_message(
            tenant_id=tenant_id,
            tenant_phone=tenant_phone or "",
            message=message,
            payload_dict=payload_dict,
            trace_id=trace_id,
        )
        if normalized_payload is None:
            return

        wa_message_id = normalized_payload["wa_message_id"]
        dedup_key = f"dedup:{wa_message_id}"

        was_set = await redis_client.set(dedup_key, "1", ex=86400, nx=True)
        if not was_set:
            logger.info(f"[{trace_id}] Message already processed (duplicate skipped): {wa_message_id}")
            return

        process_inbound_message.delay(normalized_payload)
        logger.info(f"[{trace_id}] Celery task dispatched for message ID: {wa_message_id}")

    except Exception as e:
        logger.error(f"[{trace_id}] Exception in background webhook handler: {e}", exc_info=True)

@router.post("/whatsapp")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Main webhook receiver endpoint.
    Validates HMAC signature and enqueues processing in background.
    """
    trace_id = str(uuid.uuid4())
    logger.info(f"[{trace_id}] Received webhook request.")

    # 1. Get raw request body & header
    body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")
    
    if not signature_header:
        logger.warning(f"[{trace_id}] Missing X-Hub-Signature-256 header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signature missing"
        )

    # 2. Validate signature
    is_valid = validate_whatsapp_signature(body, signature_header, settings.WHATSAPP_APP_SECRET)
    if not is_valid:
        logger.warning(f"[{trace_id}] Invalid webhook signature.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid signature"
        )

    # 3. Parse JSON payload
    try:
        payload_dict = await request.json()
    except Exception as e:
        logger.error(f"[{trace_id}] Failed to parse JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body"
        )

    # 4. Dispatch to background tasks & immediately return HTTP 200
    background_tasks.add_task(process_webhook_in_bg, payload_dict, trace_id)
    
    return {"status": "accepted"}
