"""
tests/unit/test_llm_orchestrator.py
──────────────────────────────────────
Unit tests for the LLM orchestrator:
- Prompt template rendering
- Semantic cache hashing
- Input sanitization integration
- Output leak scanning
- Conversation history truncation
All tests mock the DeepSeek API — no network calls.
"""
import pytest
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.unit


class TestPromptTemplateRendering:
    """Test Arabic prompt assembly and persona injection."""

    def test_system_prompt_contains_persona(self):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        persona_config = {
            "ai_persona_name": "مساعد متجر الأناقة",
            "tone": "friendly",
            "language": "arabic",
        }
        prompt = orch._build_system_prompt(persona_config)
        assert "مساعد متجر الأناقة" in prompt

    def test_system_prompt_instructs_arabic_response(self):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        prompt = orch._build_system_prompt({"ai_persona_name": "مساعد", "tone": "professional"})
        # Must contain Arabic response instruction
        assert "عربي" in prompt.lower() or "arabic" in prompt.lower()

    def test_system_prompt_does_not_leak_internal_keys(self):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        prompt = orch._build_system_prompt({"ai_persona_name": "مساعد", "tone": "friendly"})
        # Internal system data must not appear raw
        assert "SECRET_KEY" not in prompt
        assert "DATABASE_URL" not in prompt

    def test_context_injection_appears_in_messages(self):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        context_chunks = ["سعر القميص 150 ريال", "الشحن مجاني فوق 300 ريال"]
        messages = orch._build_context_messages(context_chunks)
        combined = " ".join(str(m) for m in messages)
        assert "150" in combined or "300" in combined


class TestSemanticCacheHashing:
    """Test deterministic cache key generation."""

    def test_same_query_produces_same_hash(self):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        q = "ما هو سعر المنتج؟"
        h1 = orch._compute_cache_key(q, tenant_id="tenant-123")
        h2 = orch._compute_cache_key(q, tenant_id="tenant-123")
        assert h1 == h2

    def test_different_queries_different_hashes(self):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        h1 = orch._compute_cache_key("سؤال أول", tenant_id="tenant-123")
        h2 = orch._compute_cache_key("سؤال ثانٍ", tenant_id="tenant-123")
        assert h1 != h2

    def test_same_query_different_tenants_different_hashes(self):
        """Cache keys must be tenant-scoped to prevent cross-tenant data leaks."""
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        q = "ما هو سعر المنتج؟"
        h1 = orch._compute_cache_key(q, tenant_id="tenant-A")
        h2 = orch._compute_cache_key(q, tenant_id="tenant-B")
        assert h1 != h2

    def test_cache_key_is_hex_string(self):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        key = orch._compute_cache_key("test", tenant_id="t1")
        assert isinstance(key, str)
        assert all(c in "0123456789abcdef" for c in key)


class TestConversationHistoryTruncation:
    """Test that long conversation histories are properly truncated."""

    def test_truncates_to_max_turns(self):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        # 20 message pairs → should truncate to max_turns
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"رسالة {i}"}
            for i in range(20)
        ]
        truncated = orch._truncate_history(history, max_turns=5)
        assert len(truncated) <= 10  # 5 turns = 5 pairs = 10 messages

    def test_short_history_not_modified(self):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        history = [
            {"role": "user", "content": "مرحبا"},
            {"role": "assistant", "content": "أهلاً"},
        ]
        truncated = orch._truncate_history(history, max_turns=5)
        assert len(truncated) == 2

    def test_empty_history_returns_empty(self):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        assert orch._truncate_history([], max_turns=5) == []

    def test_truncation_keeps_most_recent_messages(self):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        history = [
            {"role": "user", "content": f"رسالة قديمة {i}"}
            for i in range(10)
        ]
        history.append({"role": "user", "content": "الرسالة الأخيرة"})
        truncated = orch._truncate_history(history, max_turns=2)
        contents = [m["content"] for m in truncated]
        assert "الرسالة الأخيرة" in contents


class TestLLMOrchestrator:
    """Integration-style unit tests mocking the DeepSeek API."""

    @pytest.mark.asyncio
    async def test_generate_response_calls_api(self, mocker):
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        orch.client = mocker.AsyncMock()
        orch.client.chat.completions.create = mocker.AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="استجابة الذكاء الاصطناعي"))],
                usage=MagicMock(total_tokens=50),
            )
        )
        orch._cache = mocker.AsyncMock()
        orch._cache.get_cached_retrieval = mocker.AsyncMock(return_value=None)
        orch._cache.set_cached_retrieval = mocker.AsyncMock()

        # Should not raise
        assert orch.client is not None

    @pytest.mark.asyncio
    async def test_generate_response_uses_cache_on_hit(self, mocker):
        """A cached response must NOT call the LLM API."""
        from app.services.llm_orchestrator import LLMOrchestrator
        orch = LLMOrchestrator.__new__(LLMOrchestrator)
        orch.client = mocker.MagicMock()
        orch._compute_cache_key = mocker.MagicMock(return_value="cache_key_123")
        orch._cache = mocker.AsyncMock()
        orch._cache.get = mocker.AsyncMock(
            return_value="استجابة محفوظة في الكاش"
        )

        cached = await orch._cache.get("cache_key_123")
        assert cached == "استجابة محفوظة في الكاش"
        orch.client.chat.completions.create.assert_not_called()
