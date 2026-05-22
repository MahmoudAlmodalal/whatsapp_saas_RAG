from abc import ABC, abstractmethod

class ResponseStrategy(ABC):
    @abstractmethod
    async def execute(
        self,
        message: str,
        company_id: str,
        session_id: str,
        language: str,
        history: list,
        persona_name: str = "نصيح",
        tone: str = "professional",
        system_prompt_extra: str = "",
    ) -> dict:
        """
        Returns:
          {
            "answer": str,
            "confidence": float,
            "strategy_used": str,
            "should_escalate": bool,
            "sources": list
          }
        """
        pass
