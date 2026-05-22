"""
app/core/whatsapp.py
────────────────────
Helpers for WhatsApp Webhook payload processing.
"""
import hmac
import hashlib
import secrets

def validate_whatsapp_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    """
    Validates the X-Hub-Signature-256 header against the request body.
    signature_header format is typically "sha256=<hash>"
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
        
    actual_signature = signature_header.split("sha256=")[-1]
    
    # Compute HMAC SHA256 of the payload using the app secret
    expected_hmac = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256
    )
    expected_signature = expected_hmac.hexdigest()
    
    return secrets.compare_digest(expected_signature, actual_signature)
