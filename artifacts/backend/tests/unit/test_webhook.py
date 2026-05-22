"""
tests/unit/test_webhook.py
───────────────────────────
Unit tests for the WhatsApp webhook processing logic:
- HMAC-SHA256 signature validation
- Payload parsing (text, audio, image, document)
- Message deduplication logic
- Retry backoff
All tests are pure unit tests — no network, no DB, no Redis.
"""
import hashlib
import hmac
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.unit

# ─── Helpers ─────────────────────────────────────────────────────────────────

APP_SECRET = "test-app-secret-67890"


def make_signature(payload_bytes: bytes, secret: str = APP_SECRET) -> str:
    """Generate a valid X-Hub-Signature-256 header value."""
    digest = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def make_text_payload(
    from_number: str = "+966501234567",
    message_id: str = "wamid.test001",
    text: str = "مرحباً، كيف يمكنني مساعدتك؟",
    phone_number_id: str = "123456789",
) -> dict:
    """Build a minimal WhatsApp text message payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "entry_001",
            "changes": [{
                "field": "messages",
                "value": {
                    "metadata": {"phone_number_id": phone_number_id},
                    "messages": [{
                        "id": message_id,
                        "from": from_number,
                        "type": "text",
                        "text": {"body": text},
                        "timestamp": "1700000000",
                    }],
                    "contacts": [{"profile": {"name": "عميل تجريبي"}}],
                },
            }],
        }],
    }


def make_audio_payload(from_number: str = "+966501234567") -> dict:
    """Build a WhatsApp audio message payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "entry_001",
            "changes": [{
                "field": "messages",
                "value": {
                    "metadata": {"phone_number_id": "123456789"},
                    "messages": [{
                        "id": "wamid.audio001",
                        "from": from_number,
                        "type": "audio",
                        "audio": {"id": "audio_media_id_001", "mime_type": "audio/ogg"},
                        "timestamp": "1700000001",
                    }],
                    "contacts": [{"profile": {"name": "عميل"}}],
                },
            }],
        }],
    }


def make_image_payload(from_number: str = "+966501234567") -> dict:
    """Build a WhatsApp image message payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "entry_001",
            "changes": [{
                "field": "messages",
                "value": {
                    "metadata": {"phone_number_id": "123456789"},
                    "messages": [{
                        "id": "wamid.image001",
                        "from": from_number,
                        "type": "image",
                        "image": {"id": "img_001", "mime_type": "image/jpeg", "caption": "صورة"},
                        "timestamp": "1700000002",
                    }],
                    "contacts": [{"profile": {"name": "عميل"}}],
                },
            }],
        }],
    }


def make_document_payload(from_number: str = "+966501234567") -> dict:
    """Build a WhatsApp document message payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "entry_001",
            "changes": [{
                "field": "messages",
                "value": {
                    "metadata": {"phone_number_id": "123456789"},
                    "messages": [{
                        "id": "wamid.doc001",
                        "from": from_number,
                        "type": "document",
                        "document": {
                            "id": "doc_001",
                            "filename": "فاتورة.pdf",
                            "mime_type": "application/pdf",
                        },
                        "timestamp": "1700000003",
                    }],
                    "contacts": [{"profile": {"name": "عميل"}}],
                },
            }],
        }],
    }


# ─── HMAC Signature Validation ────────────────────────────────────────────────

class TestHMACSignature:
    """Test HMAC-SHA256 signature validation used for webhook security."""

    def test_valid_signature_accepted(self):
        from app.core.whatsapp import verify_webhook_signature
        payload = b'{"test": "data"}'
        signature = make_signature(payload)
        assert verify_webhook_signature(payload, signature, APP_SECRET) is True

    def test_invalid_signature_rejected(self):
        from app.core.whatsapp import verify_webhook_signature
        payload = b'{"test": "data"}'
        assert verify_webhook_signature(payload, "sha256=invalidsignature", APP_SECRET) is False

    def test_tampered_payload_rejected(self):
        from app.core.whatsapp import verify_webhook_signature
        payload = b'{"test": "data"}'
        signature = make_signature(payload)
        tampered = b'{"test": "tampered"}'
        assert verify_webhook_signature(tampered, signature, APP_SECRET) is False

    def test_missing_sha256_prefix_rejected(self):
        from app.core.whatsapp import verify_webhook_signature
        payload = b'{"test": "data"}'
        raw_hex = hmac.new(APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
        # Missing the "sha256=" prefix
        assert verify_webhook_signature(payload, raw_hex, APP_SECRET) is False

    def test_empty_payload_valid_signature(self):
        from app.core.whatsapp import verify_webhook_signature
        payload = b""
        signature = make_signature(payload)
        assert verify_webhook_signature(payload, signature, APP_SECRET) is True

    def test_wrong_secret_rejected(self):
        from app.core.whatsapp import verify_webhook_signature
        payload = b'{"test": "data"}'
        sig_with_real_secret = make_signature(payload, APP_SECRET)
        assert verify_webhook_signature(payload, sig_with_real_secret, "wrong-secret") is False


# ─── Payload Parsing ─────────────────────────────────────────────────────────

class TestPayloadParsing:
    """Test WhatsApp payload extraction functions."""

    def test_extract_text_message(self):
        from app.routers.webhook import _extract_message_data
        payload = make_text_payload(
            from_number="+966501234567",
            message_id="wamid.abc",
            text="كيف حالك؟",
        )
        result = _extract_message_data(payload)
        assert result is not None
        assert result["from"] == "+966501234567"
        assert result["message_id"] == "wamid.abc"
        assert result["type"] == "text"
        assert result["text"] == "كيف حالك؟"

    def test_extract_audio_message(self):
        from app.routers.webhook import _extract_message_data
        payload = make_audio_payload()
        result = _extract_message_data(payload)
        assert result is not None
        assert result["type"] == "audio"
        assert "audio" in result

    def test_extract_image_message(self):
        from app.routers.webhook import _extract_message_data
        payload = make_image_payload()
        result = _extract_message_data(payload)
        assert result is not None
        assert result["type"] == "image"

    def test_extract_document_message(self):
        from app.routers.webhook import _extract_message_data
        payload = make_document_payload()
        result = _extract_message_data(payload)
        assert result is not None
        assert result["type"] == "document"

    def test_empty_payload_returns_none(self):
        from app.routers.webhook import _extract_message_data
        result = _extract_message_data({})
        assert result is None

    def test_payload_without_messages_returns_none(self):
        from app.routers.webhook import _extract_message_data
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"id": "x", "changes": [{"field": "statuses", "value": {}}]}],
        }
        result = _extract_message_data(payload)
        assert result is None
