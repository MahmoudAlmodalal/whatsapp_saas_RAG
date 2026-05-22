import os
import chromadb
from openai import AsyncOpenAI
from app.strategies.base import ResponseStrategy
from app.strategies.fallback import FallbackStrategy
from app.config import get_settings

settings = get_settings()

class RAGStrategy(ResponseStrategy):
    def __init__(self):
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.threshold = settings.CONFIDENCE_THRESHOLD
        self._chroma_client = None

    def _get_chroma(self):
        if self._chroma_client is None:
            os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        return self._chroma_client

    async def _embed(self, text: str) -> list:
        resp = await self.openai.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=text,
        )
        return resp.data[0].embedding

    async def execute(self, message, company_id, session_id, language, history,
                      persona_name="نصيح", tone="professional", system_prompt_extra=""):
        if not settings.OPENAI_API_KEY:
            return await FallbackStrategy().execute(
                message, company_id, session_id, language, history, persona_name, tone
            )

        try:
            query_embedding = await self._embed(message)
        except Exception:
            return await FallbackStrategy().execute(
                message, company_id, session_id, language, history, persona_name, tone
            )

        try:
            client = self._get_chroma()
            collection = client.get_collection(f"company_{company_id}")
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=5,
                include=["documents", "distances", "metadatas"],
            )
        except Exception:
            return await FallbackStrategy().execute(
                message, company_id, session_id, language, history, persona_name, tone
            )

        distances = results["distances"][0] if results["distances"] else [1.0]
        confidence = max(0.0, 1.0 - min(distances)) if distances else 0.0

        if confidence < self.threshold:
            return {
                "answer": self._no_info(language),
                "confidence": confidence,
                "strategy_used": "fallback",
                "should_escalate": True,
                "sources": [],
            }

        chunks = results["documents"][0]
        context = "\n\n---\n\n".join(chunks)
        sources = list({m.get("source", "") for m in results["metadatas"][0]})

        lang_instruction = "أجب باللغة العربية." if language == "ar" else "Respond in English."
        tone_map = {
            "professional": "You are professional and concise.",
            "friendly": "You are warm, friendly, and approachable.",
            "formal": "You are formal and authoritative.",
        }
        tone_instruction = tone_map.get(tone, tone_map["professional"])

        system = (
            f"You are {persona_name}, an AI customer support agent. "
            f"{tone_instruction} "
            f"Answer ONLY based on the provided context. "
            f"If the answer is not in the context, say you don't know. "
            f"{lang_instruction}"
        )
        if system_prompt_extra:
            system += f"\n\n{system_prompt_extra}"
        system += f"\n\nContext:\n{context}"

        messages = [{"role": "system", "content": system}]
        for h in history[-6:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        try:
            resp = await self.openai.chat.completions.create(
                model=settings.CHAT_MODEL,
                messages=messages,
            )
            answer = resp.choices[0].message.content
        except Exception as e:
            return await FallbackStrategy().execute(
                message, company_id, session_id, language, history, persona_name, tone
            )

        return {
            "answer": answer,
            "confidence": confidence,
            "strategy_used": "rag",
            "should_escalate": False,
            "sources": sources,
        }

    def _no_info(self, language: str) -> str:
        if language == "ar":
            return "عذراً، لا تتوفر لديّ معلومات كافية للإجابة على هذا السؤال. هل تريد التحدث مع موظف؟"
        return "I don't have enough information to answer that question. Would you like to speak with a human agent?"
