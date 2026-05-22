"""
app/services/whatsapp_sender.py
────────────────────────────────
WhatsApp Business Cloud API outbound message sender.

Sends text messages to WhatsApp users via Meta's Graph API.

API endpoint
────────────
  POST https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages

Retry strategy
──────────────
  HTTP 429 (rate limited) → exponential backoff, max 3 retries:
      delay = 2^attempt seconds  → 1 s, 2 s, 4 s

Logging
───────
  Every call logs: tenant_id, destination phone, HTTP status, latency_ms.
  On rate-limit retry: attempt number and wait duration are also logged.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Meta Graph API constants ──────────────────────────────────────────────────
_GRAPH_API_BASE = "https://graph.facebook.com/v18.0"
_MAX_RETRIES = 3
_REQUEST_TIMEOUT = 10.0  # seconds


# ─────────────────────────────────────────────────────────────────────────────
# Singleton async HTTP client
# ─────────────────────────────────────────────────────────────────────────────

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """
    Return a module-level singleton httpx.AsyncClient.

    Re-using a single client enables connection pooling and avoids the
    overhead of creating a new TCP connection per message.
    """
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(_REQUEST_TIMEOUT),
            headers={"Content-Type": "application/json"},
        )
        logger.debug("WhatsApp httpx.AsyncClient initialised.")
    return _http_client


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


async def send_whatsapp_message(
    to_phone: str,
    text: str,
    tenant_id: str,
    *,
    phone_number_id: str | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    """
    Send a plain-text WhatsApp message via the Meta Cloud API.

    Retries automatically on HTTP 429 (rate limit) with exponential backoff
    (up to _MAX_RETRIES = 3 attempts beyond the first).

    Args:
        to_phone:        Destination phone in E.164 format, e.g. "+970599123456".
        text:            Message body (UTF-8, Arabic supported, ≤ 4096 chars).
        tenant_id:       Owning tenant UUID — used only for structured logging.
        phone_number_id: Override the WhatsApp Phone Number ID from settings.
        access_token:    Override the WhatsApp access token from settings.

    Returns:
        Parsed JSON response dict from Meta on success.

    Raises:
        httpx.HTTPStatusError: On non-retriable HTTP errors (4xx/5xx except 429).
        httpx.RequestError:    On network-level failures after all retries.
    """
    pid = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
    token = access_token or settings.WHATSAPP_TOKEN

    url = f"{_GRAPH_API_BASE}/{pid}/messages"
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {token}"}

    client = _get_http_client()
    attempt = 0

    while True:
        t0 = time.monotonic()
        try:
            response = await client.post(url, json=payload, headers=headers)
            latency_ms = int((time.monotonic() - t0) * 1000)

            logger.info(
                "WhatsApp send — tenant=%s to=%s status=%d latency=%dms attempt=%d",
                tenant_id, to_phone, response.status_code, latency_ms, attempt,
            )

            if response.status_code == 429:
                # Rate limited — retry with exponential backoff
                if attempt >= _MAX_RETRIES:
                    logger.error(
                        "WhatsApp rate limit exceeded after %d retries — "
                        "tenant=%s to=%s",
                        _MAX_RETRIES, tenant_id, to_phone,
                    )
                    response.raise_for_status()  # let caller handle

                wait_secs = 2 ** attempt
                logger.warning(
                    "WhatsApp rate limited (429) — tenant=%s to=%s "
                    "retrying in %ds (attempt %d/%d)",
                    tenant_id, to_phone, wait_secs, attempt + 1, _MAX_RETRIES,
                )
                await asyncio.sleep(wait_secs)
                attempt += 1
                continue

            # Raise on any other non-2xx response
            response.raise_for_status()
            return response.json()

        except httpx.RequestError as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            if attempt >= _MAX_RETRIES:
                logger.error(
                    "WhatsApp network error after %d retries — tenant=%s to=%s: %s",
                    _MAX_RETRIES, tenant_id, to_phone, exc,
                )
                raise

            wait_secs = 2 ** attempt
            logger.warning(
                "WhatsApp network error — tenant=%s to=%s retrying in %ds "
                "(attempt %d/%d): %s",
                tenant_id, to_phone, wait_secs, attempt + 1, _MAX_RETRIES, exc,
            )
            await asyncio.sleep(wait_secs)
            attempt += 1
