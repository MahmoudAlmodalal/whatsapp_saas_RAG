from app.strategies.base import ResponseStrategy

class EscalationStrategy(ResponseStrategy):
    async def execute(self, message, company_id, session_id, language, history,
                      persona_name="نصيح", tone="professional", system_prompt_extra=""):
        if language == "ar":
            answer = "حسناً، سأقوم بتحويلك إلى موظف بشري الآن. يرجى الانتظار قليلاً..."
        else:
            answer = "Sure, I'll transfer you to a human agent now. Please wait a moment..."

        return {
            "answer": answer,
            "confidence": 1.0,
            "strategy_used": "escalation",
            "should_escalate": True,
            "sources": [],
        }
