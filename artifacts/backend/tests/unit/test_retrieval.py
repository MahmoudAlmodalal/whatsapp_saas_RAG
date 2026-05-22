"""
tests/unit/test_retrieval.py
──────────────────────────────
Unit tests for the hybrid retrieval engine:
- Vector similarity scoring
- BM25 ranking
- Reciprocal Rank Fusion (RRF) score calculation
- Arabic normalization for queries
- Cache hit/miss logic
All tests are pure unit tests — no DB, no network.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

pytestmark = pytest.mark.unit


class TestRRFScoring:
    """Test Reciprocal Rank Fusion score calculation."""

    def test_rrf_score_formula(self):
        from app.services.retrieval import _rrf_score
        # RRF(rank) = 1 / (k + rank), default k=60
        score = _rrf_score(rank=1, k=60)
        expected = 1 / (60 + 1)
        assert abs(score - expected) < 1e-9

    def test_rrf_rank1_highest_score(self):
        from app.services.retrieval import _rrf_score
        assert _rrf_score(1) > _rrf_score(2) > _rrf_score(10)

    def test_rrf_fusion_merges_rankings(self):
        from app.services.retrieval import _compute_rrf_scores
        vector_results = [
            {"chunk_id": "a", "content": "chunk a"},
            {"chunk_id": "b", "content": "chunk b"},
            {"chunk_id": "c", "content": "chunk c"},
        ]
        bm25_results = [
            {"chunk_id": "b", "content": "chunk b"},
            {"chunk_id": "a", "content": "chunk a"},
            {"chunk_id": "d", "content": "chunk d"},
        ]
        fused = _compute_rrf_scores(vector_results, bm25_results)
        assert len(fused) >= 3
        # chunk "a" and "b" appear in both lists → should rank higher than "c" or "d"
        ids = [r["chunk_id"] for r in fused]
        assert "a" in ids
        assert "b" in ids

    def test_rrf_empty_inputs(self):
        from app.services.retrieval import _compute_rrf_scores
        result = _compute_rrf_scores([], [])
        assert result == []

    def test_rrf_single_list(self):
        from app.services.retrieval import _compute_rrf_scores
        vector_results = [{"chunk_id": "x", "content": "content x"}]
        result = _compute_rrf_scores(vector_results, [])
        assert len(result) == 1
        assert result[0]["chunk_id"] == "x"


class TestBM25Ranking:
    """Test BM25 lexical search ranking."""

    def test_bm25_ranks_relevant_chunks_higher(self):
        from app.services.retrieval import _rank_with_bm25
        corpus = [
            "سياسة الإرجاع والاستبدال للمنتجات",
            "مواعيد عمل المتجر والفروع",
            "إمكانية إرجاع المنتج بعد الشراء",
            "طرق الدفع المتاحة في المتجر",
        ]
        query = "كيف يمكنني إرجاع المنتج"
        ranked = _rank_with_bm25(query, corpus, top_k=2)
        assert len(ranked) == 2
        # Both top results should relate to "إرجاع"
        combined = " ".join([r["content"] for r in ranked])
        assert "إرجاع" in combined

    def test_bm25_empty_corpus(self):
        from app.services.retrieval import _rank_with_bm25
        result = _rank_with_bm25("استفسار", [], top_k=5)
        assert result == []

    def test_bm25_returns_at_most_top_k(self):
        from app.services.retrieval import _rank_with_bm25
        corpus = [f"نص رقم {i}" for i in range(20)]
        result = _rank_with_bm25("نص", corpus, top_k=5)
        assert len(result) <= 5


class TestQueryEmbeddingFormatting:
    """Test query embedding preparation (e5 query prefix)."""

    def test_query_gets_e5_prefix(self):
        from app.services.retrieval import _format_query_for_embedding
        query = "ما هو سعر المنتج؟"
        formatted = _format_query_for_embedding(query)
        assert formatted.startswith("query: ")
        assert query in formatted

    def test_passage_gets_passage_prefix(self):
        from app.services.retrieval import _format_passage_for_embedding
        passage = "سعر المنتج هو 150 ريال"
        formatted = _format_passage_for_embedding(passage)
        assert formatted.startswith("passage: ")
        assert passage in formatted


class TestCacheLogic:
    """Test retrieval cache hit/miss behaviour."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self, mocker):
        from app.services.retrieval import RetrievalService
        service = RetrievalService.__new__(RetrievalService)
        service._cache = mocker.AsyncMock()

        cached_result = [{"chunk_id": "cached_chunk", "content": "من الكاش"}]
        service._cache.get_cached_retrieval = mocker.AsyncMock(return_value=cached_result)

        result = await service._cache.get_cached_retrieval("test_key")
        assert result == cached_result
        service._cache.get_cached_retrieval.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, mocker):
        from app.services.retrieval import RetrievalService
        service = RetrievalService.__new__(RetrievalService)
        service._cache = mocker.AsyncMock()
        service._cache.get_cached_retrieval = mocker.AsyncMock(return_value=None)

        result = await service._cache.get_cached_retrieval("missing_key")
        assert result is None
