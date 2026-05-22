from app.strategies.base import ResponseStrategy

class FallbackStrategy(ResponseStrategy):
    async def execute(self, message, company_id, session_id, language, history,
                      persona_name="نصيح", tone="professional", system_prompt_extra=""):
        if language == "ar":
            answer = "عذراً، لا أملك معلومات كافية حول هذا الموضوع. هل تريد التحدث مع موظف؟"
        else:
            answer = "I don't have enough information about that in my knowledge base. Would you like to speak with a human agent?"

        return {
            "answer": answer,
            "confidence": 0.0,
            "strategy_used": "fallback",
            "should_escalate": True,
            "sources": [],
        }
