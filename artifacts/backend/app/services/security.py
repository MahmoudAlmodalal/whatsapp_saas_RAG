"""
app/services/security.py
────────────────────────
Security hardening for the Arabic WhatsApp AI system.

Responsibilities
────────────────
1. INJECTION_PATTERNS   — curated list of English + Arabic prompt-injection strings
2. detect_injection()   — classify risk level of a user message
3. sanitize_user_input()— strip HTML/control chars, enforce length cap, raise on high risk
4. wrap_in_safe_delimiters() — XML-tag user input to prevent role confusion in the LLM prompt
5. scan_output_for_leaks()   — redact any LLM response that leaks system-prompt content

Design notes
────────────
- All pattern matching is case-insensitive; Arabic is matched verbatim (no lowercasing
  needed — Arabic script has no case concept).
- Risk classification follows a three-tier model:
    • high   → 3+ patterns OR any "system:" / "[SYSTEM]" literal
    • medium → 1–2 patterns matched
    • low    → no patterns (safe)
- sanitize_user_input() raises InjectionDetectedError on HIGH risk so the caller
  (generate_response / Celery task) can return an apology without hitting the LLM.
  MEDIUM risk is allowed through with a warning prefix so the LLM is still invoked
  but the operator can review flagged turns in Langfuse.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import List

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Custom exception
# ─────────────────────────────────────────────────────────────────────────────


class InjectionDetectedError(ValueError):
    """Raised when user input is classified as HIGH-risk prompt injection."""

    def __init__(self, matched_patterns: List[str]) -> None:
        self.matched_patterns = matched_patterns
        super().__init__(
            f"Prompt injection detected — matched patterns: {matched_patterns}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Master injection pattern list (English + Arabic)
# ─────────────────────────────────────────────────────────────────────────────

# Patterns that trigger an AUTOMATIC HIGH-RISK override regardless of count
_CRITICAL_PATTERNS: frozenset[str] = frozenset(
    {
        "system:",
        "[system]",
        "<system>",
        "###system",
    }
)

INJECTION_PATTERNS: List[str] = [
    # ── English patterns ──────────────────────────────────────────────────
    "ignore previous instructions",
    "ignore all prior",
    "ignore all previous",
    "disregard your",
    "disregard all previous",
    "you are now",
    "new persona",
    "act as",
    "pretend you are",
    "pretend to be",
    "forget your instructions",
    "forget everything above",
    "forget previous",
    "system:",
    "[system]",
    "<system>",
    "###system",
    "jailbreak",
    "bypass",
    "override",
    "override previous",
    "reveal your prompt",
    "reveal your instructions",
    "show me your prompt",
    "what are your instructions",
    "ignore your training",
    "new instructions:",
    "updated instructions:",
    "your new role",
    "do anything now",
    "dan mode",
    # ── Arabic patterns ───────────────────────────────────────────────────
    "تجاهل التعليمات",           # ignore instructions
    "تجاهل جميع التعليمات",      # ignore all instructions
    "تجاهل التعليمات السابقة",   # ignore previous instructions
    "أنت الآن",                  # you are now
    "غير شخصيتك",               # change your persona
    "تصرف كـ",                   # act as
    "تصرف ك",                    # act as (variant)
    "تظاهر أنك",                  # pretend you are
    "انسَ تعليماتك",              # forget your instructions
    "انسَ كل شيء",               # forget everything
    "تعليمات جديدة",              # new instructions
    "دور جديد",                  # new role
    "تجاوز",                     # bypass / override
    "اكشف عن تعليماتك",          # reveal your instructions
    "ما هي تعليماتك",            # what are your instructions
    "تجاهل السياق",              # ignore the context
]

# Compiled regex: match whole pattern, case-insensitive, Unicode-safe
_PATTERN_REGEXES: list[tuple[str, re.Pattern[str]]] = [
    (pat, re.compile(re.escape(pat), re.IGNORECASE | re.UNICODE))
    for pat in INJECTION_PATTERNS
]

# ─────────────────────────────────────────────────────────────────────────────
# HTML / control-char cleanup helpers
# ─────────────────────────────────────────────────────────────────────────────

_HTML_TAG_RE = re.compile(r"<[^>]+>", re.UNICODE)
_NULL_BYTES_RE = re.compile(r"\x00")
# Control characters (C0 + C1 ranges) excluding standard whitespace (\t \n \r)
_CONTROL_CHAR_RE = re.compile(
    r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", re.UNICODE
)
_WHITESPACE_RE = re.compile(r" {2,}", re.UNICODE)

_MAX_INPUT_LENGTH = 2_000  # characters (not bytes)

# Warning prefix prepended to MEDIUM-risk messages before LLM call
_MEDIUM_RISK_PREFIX = "[تحذير: رسالة مشبوهة] "

# ─────────────────────────────────────────────────────────────────────────────
# Output leak patterns
# ─────────────────────────────────────────────────────────────────────────────

_LEAK_PATTERNS: List[str] = [
    # English
    "system prompt",
    "my instructions are",
    "i was instructed to",
    "my training says",
    "confidential instructions",
    # Arabic
    "أنا مبرمج",               # I am programmed
    "تعليماتي هي",             # my instructions are
    "النظام يقول",             # the system says
    "تم تدريبي على",           # I was trained to
    "تعليمات سرية",            # confidential instructions
]

_LEAK_APOLOGY_AR = "عذراً، لا أستطيع الإجابة على هذا السؤال."


# ─────────────────────────────────────────────────────────────────────────────
# 1. Injection detection
# ─────────────────────────────────────────────────────────────────────────────


def detect_injection(text: str) -> dict:
    """
    Scan *text* for prompt-injection patterns and return a risk assessment.

    Args:
        text: Raw user input (Arabic, English, or mixed).

    Returns:
        {
            "is_injection":      bool,
            "matched_patterns":  List[str],
            "risk_level":        "low" | "medium" | "high",
        }

    Risk tiers
    ----------
    - high   : 3+ patterns matched, OR any critical "system:" / "[SYSTEM]" literal hit
    - medium : 1–2 patterns matched
    - low    : 0 patterns matched
    """
    matched: List[str] = []
    has_critical = False

    lower_text = text.lower()  # for English patterns; Arabic patterns match as-is

    for pattern, regex in _PATTERN_REGEXES:
        if regex.search(text):
            matched.append(pattern)
            # Check if this pattern is a critical override
            if pattern.lower() in _CRITICAL_PATTERNS:
                has_critical = True

    is_injection = len(matched) > 0

    if has_critical or len(matched) >= 3:
        risk_level = "high"
    elif len(matched) >= 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    if is_injection:
        logger.warning(
            "Injection detection — risk=%s matched=%s input_snippet=%r",
            risk_level,
            matched,
            text[:120],
        )

    return {
        "is_injection": is_injection,
        "matched_patterns": matched,
        "risk_level": risk_level,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Input sanitization
# ─────────────────────────────────────────────────────────────────────────────


def sanitize_user_input(text: str) -> str:
    """
    Sanitize raw user input before it is passed to the LLM.

    Pipeline
    ────────
    1. Strip HTML/XML tags.
    2. Remove null bytes and C0/C1 control characters (preserve newlines).
    3. Normalize Unicode to NFC (canonical composition).
    4. Collapse runs of 2+ spaces to a single space.
    5. Truncate to MAX_INPUT_LENGTH (2 000 chars).
    6. Run injection detection:
       - HIGH risk  → raise InjectionDetectedError (caller returns apology).
       - MEDIUM risk → prepend Arabic warning prefix and continue.
       - LOW risk   → return sanitized text unchanged.

    Args:
        text: Arbitrary user-supplied message.

    Returns:
        Sanitized string safe for LLM injection.

    Raises:
        InjectionDetectedError: On HIGH-risk injection classification.
    """
    if not isinstance(text, str):
        text = str(text)

    # Step 1 — Strip HTML/XML tags
    cleaned = _HTML_TAG_RE.sub("", text)

    # Step 2 — Remove null bytes and control chars
    cleaned = _NULL_BYTES_RE.sub("", cleaned)
    cleaned = _CONTROL_CHAR_RE.sub("", cleaned)

    # Step 3 — NFC Unicode normalization (important for Arabic diacritics)
    cleaned = unicodedata.normalize("NFC", cleaned)

    # Step 4 — Collapse repeated spaces (keep newlines for multi-line messages)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()

    # Step 5 — Hard truncation
    if len(cleaned) > _MAX_INPUT_LENGTH:
        logger.debug(
            "Input truncated from %d to %d chars.", len(cleaned), _MAX_INPUT_LENGTH
        )
        cleaned = cleaned[:_MAX_INPUT_LENGTH]

    # Step 6 — Injection scan
    assessment = detect_injection(cleaned)

    if assessment["risk_level"] == "high":
        raise InjectionDetectedError(assessment["matched_patterns"])

    if assessment["risk_level"] == "medium":
        # Allow through but mark for operator review in Langfuse
        logger.warning(
            "Medium-risk injection — prepending warning prefix. patterns=%s",
            assessment["matched_patterns"],
        )
        cleaned = _MEDIUM_RISK_PREFIX + cleaned

    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# 3. Safe delimiter wrapper
# ─────────────────────────────────────────────────────────────────────────────


def wrap_in_safe_delimiters(user_text: str) -> str:
    """
    Wrap sanitized user input in XML-style delimiters before LLM injection.

    The LLM system prompt instructs the model to treat content inside
    <customer_message>…</customer_message> as customer input, preventing role
    confusion even if the text contains instruction-like phrases.

    Args:
        user_text: Already-sanitized user message.

    Returns:
        Delimited string ready for the ``user`` role in the messages array.
    """
    return f"<customer_message>{user_text}</customer_message>"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Output leak scanner
# ─────────────────────────────────────────────────────────────────────────────


def scan_output_for_leaks(response: str) -> str:
    """
    Scan the LLM response for system-prompt leakage or internal disclosure.

    If any known leak phrase is found the entire response is replaced with a
    safe Arabic apology message — we never return partial leaks.

    Args:
        response: Raw LLM output string.

    Returns:
        Either the original response (if clean) or the Arabic apology constant.
    """
    lower_response = response.lower()

    for pattern in _LEAK_PATTERNS:
        if pattern.lower() in lower_response:
            logger.warning(
                "Output leak scanner triggered — pattern=%r; redacting response.",
                pattern,
            )
            return _LEAK_APOLOGY_AR

    return response
