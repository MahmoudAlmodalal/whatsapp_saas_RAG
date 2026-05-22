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
      Detects explicit *request* phrases for a human agent in both Arabic
      and English.  Phrases are intentionally specific to avoid false
      positives on common words.

      NOT matched: standalone words like "خدمة عملاء"، "إنسان"، "agent"،
      "human" — these appear in normal conversation (e.g. "شكراً على خدمة
      عملاء ممتازة") and would produce unwanted handoffs.

All checks are case-insensitive.  Returns True if ANY check passes.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Check 2: Low-confidence marker emitted by the LLM orchestrator ───────────
_LOW_CONFIDENCE_MARKER = "لا أملك معلومات كافية"

# ── Check 3: Explicit handoff request phrases (Arabic + English) ──────────────
# Rules for adding a phrase:
#   • Must be a request/command form, not a noun or descriptive phrase.
#   • Must be specific enough that it cannot appear in positive/neutral context.
#   • Arabic entries must cover both alef forms (أ / ا) where common.
_EXPLICIT_HANDOFF_PHRASES: list[str] = [
    # Arabic — request / command forms
    "تكلم مع موظف",
    "تكلم مع إنسان",
    "تكلم مع انسان",
    "تحدث مع موظف",
    "تحدث مع إنسان",
    "تحدث مع انسان",
    "أريد موظف",
    "اريد موظف",
    "أريد التحدث مع موظف",
    "اريد التحدث مع موظف",
    "أريد التحدث مع إنسان",
    "اريد التحدث مع انسان",
    "وكيل بشري",
    "ممثل خدمة عملاء",
    "تواصل مع موظف",
    "تواصل مع إنسان",
    "تواصل مع انسان",
    "حول محادثتي",
    "حول المحادثة",
    "ابغى اكلم موظف",
    "ابغى موظف",
    # English — request forms only
    "speak to a human",
    "talk to a human",
    "speak to an agent",
    "talk to an agent",
    "speak to someone",
    "talk to someone",
    "connect me to an agent",
    "transfer me to an agent",
    "real person",
    "live agent",
    "live support",
    "human support",
    "human agent",
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
