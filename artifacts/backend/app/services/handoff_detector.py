"""
app/services/handoff_detector.py
──────────────────────────────────
Human-agent handoff detection for the WhatsApp AI pipeline.

Determines whether a conversation should be escalated to a human agent
by evaluating three independent signals:

  Check 1 — Keyword match
      Checks the customer's message content against the tenant's configured
      handoff keywords list (tenant_config['handoff_keywords']).

  Check 2 — Low-confidence AI marker
      Detects the Arabic phrase "لا أملك معلومات كافية" in the AI response,
      which the LLM orchestrator uses to signal insufficient knowledge.

  Check 3 — Explicit handoff request
      Detects explicit customer requests for a human agent in both Arabic
      and English ("تكلم مع موظف", "إنسان", "human", "agent", etc.).

All checks are case-insensitive.  Returns True if ANY check passes.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Check 2: Low-confidence marker emitted by the LLM orchestrator ───────────
_LOW_CONFIDENCE_MARKER = "لا أملك معلومات كافية"

# ── Check 3: Explicit handoff request phrases (Arabic + English) ──────────────
_EXPLICIT_HANDOFF_PHRASES: list[str] = [
    # Arabic
    "تكلم مع موظف",
    "تحدث مع موظف",
    "أريد موظف",
    "اريد موظف",
    "تواصل مع إنسان",
    "تواصل مع انسان",
    "إنسان",
    "انسان",
    "وكيل بشري",
    "ممثل خدمة عملاء",
    "خدمة عملاء",
    # English
    "human",
    "agent",
    "real person",
    "speak to someone",
    "talk to someone",
    "live agent",
    "customer service",
]


def should_handoff(
    message_content: str,
    ai_response: str,
    tenant_config: dict,
) -> bool:
    """
    Evaluate whether this conversation should be handed off to a human agent.

    Args:
        message_content: The customer's latest message (raw text, Arabic/English).
        ai_response:     The AI's generated response for this turn.
        tenant_config:   Tenant configuration dict; checked for 'handoff_keywords'
                         (list of str).

    Returns:
        True if any handoff trigger condition is met, False otherwise.
    """
    content_lower = message_content.lower()
    response_lower = ai_response.lower()

    # ── Check 1: Tenant-defined keyword match ─────────────────────────────────
    handoff_keywords: list[str] = tenant_config.get("handoff_keywords", [])
    for keyword in handoff_keywords:
        if keyword.lower() in content_lower:
            logger.info(
                "Handoff triggered [Check 1 — tenant keyword]: keyword=%r "
                "message=%r",
                keyword, message_content[:120],
            )
            return True

    # ── Check 2: Low-confidence AI response marker ────────────────────────────
    if _LOW_CONFIDENCE_MARKER in ai_response:
        logger.info(
            "Handoff triggered [Check 2 — low confidence marker] "
            "ai_response=%r",
            ai_response[:120],
        )
        return True

    # ── Check 3: Explicit customer handoff request ────────────────────────────
    for phrase in _EXPLICIT_HANDOFF_PHRASES:
        if phrase.lower() in content_lower:
            logger.info(
                "Handoff triggered [Check 3 — explicit request]: phrase=%r "
                "message=%r",
                phrase, message_content[:120],
            )
            return True

    return False
