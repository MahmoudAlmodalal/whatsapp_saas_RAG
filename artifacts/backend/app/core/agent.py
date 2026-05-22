from app.core.language import detect_language
from app.core.memory import get_session_history, save_message, log_unanswered, ensure_conversation
from app.strategies.rag_strategy import RAGStrategy
from app.strategies.escalation import EscalationStrategy

ESCALATION_KEYWORDS_AR = ["موظف", "انسان", "بشري", "وكيل", "تحويل", "مدير"]
ESCALATION_KEYWORDS_EN = ["human", "agent", "person", "manager", "transfer", "escalate"]

def _wants_escalation(message: str, language: str) -> bool:
    msg_lower = message.lower()
    keywords = ESCALATION_KEYWORDS_AR if language == "ar" else ESCALATION_KEYWORDS_EN
    return any(k in msg_lower for k in keywords)

async def process_message(
    message: str,
    session_id: str,
    company_id: str = "default",
    channel: str = "web",
    persona_name: str = "نصيح",
    tone: str = "professional",
    system_prompt_extra: str = "",
) -> dict:
    language = detect_language(message)
    history = get_session_history(session_id)
    ensure_conversation(session_id, company_id, channel, language)

    if _wants_escalation(message, language):
        strategy = EscalationStrategy()
    else:
        strategy = RAGStrategy()

    result = await strategy.execute(
        message=message,
        company_id=company_id,
        session_id=session_id,
        language=language,
        history=history,
        persona_name=persona_name,
        tone=tone,
        system_prompt_extra=system_prompt_extra,
    )

    save_message(session_id, "user", message, language)
    save_message(
        session_id, "assistant", result["answer"], language,
        confidence=result.get("confidence"),
        strategy_used=result.get("strategy_used"),
    )

    if result.get("strategy_used") == "fallback":
        log_unanswered(message, session_id, company_id)

    return {
        "answer": result["answer"],
        "confidence": round(result.get("confidence", 0), 2),
        "strategy": result.get("strategy_used"),
        "should_escalate": result.get("should_escalate", False),
        "language": language,
        "sources": result.get("sources", []),
    }
