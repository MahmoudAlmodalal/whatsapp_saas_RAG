"""
app/services/retrieval.py
──────────────────────────
Hybrid RAG retrieval service: Vector Search + BM25 + Reciprocal Rank Fusion.

Architecture
────────────
  1. vector_search         — pgvector cosine similarity (tenant-scoped, RLS-enforced)
  2. bm25_search           — BM25Okapi full-text search (Redis-cached per tenant, TTL 1h)
  3. reciprocal_rank_fusion — merge two ranked lists using RRF scoring
  4. retrieve_context       — main entry point; runs 1+2 concurrently, fuses, top_k

Arabic query normalization mirrors the ingestion pipeline (same CAMeL Tools functions)
so that tokenization is consistent between stored chunks and incoming queries.

E5 embedding prefix
────────────────────
  Ingestion used  → "passage: <text>"
  Retrieval uses  → "query: <text>"    ← required by intfloat/multilingual-e5-large

Redis cache keys
────────────────
  bm25_index:{tenant_id}  → JSON {"ids": [...], "contents": [...]} blob (TTL 3 600 s)
  The BM25 index object is rebuilt in-process from the cached corpus data.
  Storing raw text (not pickled objects) eliminates the RCE attack surface.

Cache invalidation
──────────────────
  Call invalidate_bm25_cache(tenant_id) from the ingestion pipeline *after*
  store_chunks() completes so the next bm25_search rebuilds from fresh data.
  See run_ingestion_pipeline() in services/ingestion.py.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import List

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import set_tenant_context

logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# Redis text client (decode_responses=True — we store JSON, not binary blobs)
# ─────────────────────────────────────────────────────────────────────────────

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    """Return a module-level singleton Redis client configured for text data."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


# ─────────────────────────────────────────────────────────────────────────────
# Lazy embedding model singleton (mirrors ingestion.py pattern)
# ─────────────────────────────────────────────────────────────────────────────

_embedding_model = None


def _get_embedding_model():
    """Load intfloat/multilingual-e5-large once per worker process."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: intfloat/multilingual-e5-large")
        _embedding_model = SentenceTransformer("intfloat/multilingual-e5-large")
        logger.info("Embedding model loaded (dim=1024).")
    return _embedding_model


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ChunkResult:
    """A single retrieved document chunk with its retrieval score."""

    id: str
    content: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _normalize_query(text_str: str) -> str:
    """
    Apply the same Arabic normalization used during ingestion so that query
    tokens align with the stored chunk tokens.

    Steps:
      a. normalize_unicode — alef / hamza / waw / ya variants → canonical forms
      b. dediac_ar         — remove tashkeel (short vowel diacritics)
      c. Collapse whitespace — multiple spaces / newlines → single space
    """
    from camel_tools.utils.dediac import dediac_ar
    from camel_tools.utils.normalize import normalize_unicode

    text_str = normalize_unicode(text_str)
    text_str = dediac_ar(text_str)
    text_str = re.sub(r"\s+", " ", text_str).strip()
    return text_str


def _embed_query_sync(normalized_query: str) -> list[float]:
    """
    Generate a 1024-dim embedding for a query string.
    Prefixes with "query: " as required by the E5 model family.
    CPU/GPU-bound — always call via asyncio.to_thread().
    """
    model = _get_embedding_model()
    vec = model.encode(
        f"query: {normalized_query}",
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vec.tolist()


def _format_vector(embedding: list[float]) -> str:
    """
    Format a Python list as the pgvector literal string expected by
    CAST(:param AS vector): '[0.1,0.2,...]'  (no spaces after commas).
    """
    return "[" + ",".join(str(v) for v in embedding) + "]"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Vector Search
# ─────────────────────────────────────────────────────────────────────────────


async def vector_search(
    query: str,
    tenant_id: str,
    session: AsyncSession,
    top_k: int = 20,
) -> List[ChunkResult]:
    """
    Cosine-similarity ANN search using pgvector.

    Steps:
      1. Normalize query with Arabic normalization (same as ingestion stage).
      2. Generate query embedding with "query: " prefix (E5 requirement).
      3. Execute pgvector ORDER BY <=> query scoped to the tenant.
         RLS context is set before the query.

    The returned score is cosine *similarity* (1 − distance), so higher = better.

    Args:
        query:     Raw user query string (Arabic or mixed).
        tenant_id: Owning tenant UUID string.
        session:   Active AsyncSession; RLS context will be set internally.
        top_k:     Maximum number of results to return.

    Returns:
        List[ChunkResult] sorted by cosine similarity descending.
    """
    normalized = await asyncio.to_thread(_normalize_query, query)
    query_embedding = await asyncio.to_thread(_embed_query_sync, normalized)
    embedding_str = _format_vector(query_embedding)

    await set_tenant_context(session, tenant_id)

    sql = text("""
        SELECT
            id::text                                                    AS id,
            content,
            metadata,
            1 - (embedding <=> CAST(:query_embedding AS vector))        AS score
        FROM document_chunks
        WHERE tenant_id = :tenant_id::uuid
        ORDER BY embedding <=> CAST(:query_embedding AS vector)
        LIMIT :top_k
    """)

    result = await session.execute(
        sql,
        {
            "query_embedding": embedding_str,
            "tenant_id": tenant_id,
            "top_k": top_k,
        },
    )
    rows = result.fetchall()

    logger.debug(
        "vector_search: tenant=%s query=%r → %d rows",
        tenant_id, query[:60], len(rows),
    )

    return [
        ChunkResult(
            id=row.id,
            content=row.content,
            metadata=row.metadata or {},
            score=float(row.score),
        )
        for row in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 2. BM25 Lexical Search
# ─────────────────────────────────────────────────────────────────────────────

_BM25_CACHE_TTL = 3_600
_BM25_CACHE_KEY_PREFIX = "bm25_index"


def _bm25_cache_key(tenant_id: str) -> str:
    return f"{_BM25_CACHE_KEY_PREFIX}:{tenant_id}"


async def invalidate_bm25_cache(tenant_id: str) -> None:
    """
    Delete the cached BM25 corpus for a tenant.

    Must be called from the ingestion pipeline *immediately after* store_chunks()
    so that the next bm25_search() rebuilds the index with the newly added chunks.
    """
    redis = _get_redis()
    await redis.delete(_bm25_cache_key(tenant_id))
    logger.debug("BM25 cache invalidated for tenant %s", tenant_id)


def _build_bm25_index(contents: list[str]):
    """Build a BM25Okapi index from tokenized chunk contents (CPU-bound)."""
    from rank_bm25 import BM25Okapi

    tokenized = [c.split() for c in contents]
    return BM25Okapi(tokenized)


async def bm25_search(
    query: str,
    tenant_id: str,
    session: AsyncSession,
    top_k: int = 20,
) -> List[ChunkResult]:
    """
    BM25Okapi lexical search over all chunks for the tenant.

    Cache strategy
    ──────────────
    The corpus (chunk ids + text contents) is stored as JSON in Redis with a
    1-hour TTL under key ``bm25_index:{tenant_id}``.  The BM25 index object is
    rebuilt in-process from the cached text on every cache hit — this avoids
    the RCE risk of deserializing pickled Python objects from an external store.

    On cache miss the corpus is fetched from DB, the index is built, and only
    the raw text corpus is persisted back to Redis as JSON.

    Invalidation: call invalidate_bm25_cache(tenant_id) after ingestion so
    the stale corpus is evicted and rebuilt on the next search.

    Args:
        query:     Raw user query string (Arabic or mixed).
        tenant_id: Owning tenant UUID string.
        session:   Active AsyncSession (used only on cache miss to fetch corpus).
        top_k:     Number of results to return.

    Returns:
        List[ChunkResult] sorted by BM25 score descending.
    """
    normalized = await asyncio.to_thread(_normalize_query, query)
    redis = _get_redis()
    cache_key = _bm25_cache_key(tenant_id)

    chunk_ids: list[str] = []
    chunk_contents: list[str] = []

    # ── Try Redis cache (JSON corpus only — no pickled objects) ───────────────
    cached_json: str | None = await redis.get(cache_key)
    if cached_json:
        try:
            cached = json.loads(cached_json)
            chunk_ids = cached["ids"]
            chunk_contents = cached["contents"]
            logger.debug(
                "BM25 cache HIT for tenant %s (%d chunks)",
                tenant_id, len(chunk_ids),
            )
        except Exception as exc:
            logger.warning(
                "BM25 cache parse failed for tenant %s (%s); rebuilding.",
                tenant_id, exc,
            )
            chunk_ids = []
            chunk_contents = []

    # ── Cache miss: fetch corpus from DB ─────────────────────────────────────
    if not chunk_ids:
        await set_tenant_context(session, tenant_id)

        sql = text("""
            SELECT id::text AS id, content
            FROM document_chunks
            WHERE tenant_id = :tenant_id::uuid
        """)
        result = await session.execute(sql, {"tenant_id": tenant_id})
        rows = result.fetchall()

        if not rows:
            logger.info(
                "No chunks in DB for tenant %s — BM25 returning empty.", tenant_id
            )
            return []

        chunk_ids = [row.id for row in rows]
        chunk_contents = [row.content for row in rows]

        # Cache only the raw text corpus as JSON (never pickled objects)
        payload = json.dumps({"ids": chunk_ids, "contents": chunk_contents})
        await redis.set(cache_key, payload, ex=_BM25_CACHE_TTL)
        logger.debug(
            "BM25 cache MISS for tenant %s — cached %d chunks as JSON (%ds TTL).",
            tenant_id, len(chunk_ids), _BM25_CACHE_TTL,
        )

    # ── Build BM25 index in-process from corpus text (CPU-bound) ─────────────
    bm25_index = await asyncio.to_thread(_build_bm25_index, chunk_contents)

    # ── Score query against the corpus ────────────────────────────────────────
    query_tokens = normalized.split()

    def _score_query(index, tokens: list[str]) -> list[float]:
        return index.get_scores(tokens).tolist()

    scores: list[float] = await asyncio.to_thread(_score_query, bm25_index, query_tokens)

    ranked = sorted(
        zip(chunk_ids, chunk_contents, scores),
        key=lambda x: x[2],
        reverse=True,
    )

    logger.debug(
        "bm25_search: tenant=%s query=%r → top score=%.4f",
        tenant_id, query[:60], ranked[0][2] if ranked else 0.0,
    )

    return [
        ChunkResult(id=cid, content=content, metadata={}, score=float(score))
        for cid, content, score in ranked[:top_k]
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Reciprocal Rank Fusion
# ─────────────────────────────────────────────────────────────────────────────


def reciprocal_rank_fusion(
    vector_results: List[ChunkResult],
    bm25_results: List[ChunkResult],
    k: int = 60,
) -> List[ChunkResult]:
    """
    Merge two ranked result lists using Reciprocal Rank Fusion (RRF).

    RRF formula (Cormack et al., 2009):
        score(d) = Σ  1 / (k + rank_i)

    where rank_i is the 1-based position of document d in ranked list i.
    k=60 is the standard default that smooths the impact of high-rank positions.

    Args:
        vector_results: Ranked list from vector_search (index 0 = highest similarity).
        bm25_results:   Ranked list from bm25_search   (index 0 = highest BM25 score).
        k:              RRF constant — higher k de-emphasises rank differences.

    Returns:
        Single merged list sorted by RRF score descending, deduplicated by chunk id.
        The .score field of each ChunkResult holds the RRF score (not the original).
    """
    fused: dict[str, dict] = {}

    for rank, chunk in enumerate(vector_results, start=1):
        if chunk.id not in fused:
            fused[chunk.id] = {"chunk": chunk, "rrf_score": 0.0}
        fused[chunk.id]["rrf_score"] += 1.0 / (k + rank)

    for rank, chunk in enumerate(bm25_results, start=1):
        if chunk.id not in fused:
            fused[chunk.id] = {"chunk": chunk, "rrf_score": 0.0}
        fused[chunk.id]["rrf_score"] += 1.0 / (k + rank)

    merged: list[ChunkResult] = [
        ChunkResult(
            id=entry["chunk"].id,
            content=entry["chunk"].content,
            metadata=entry["chunk"].metadata,
            score=entry["rrf_score"],
        )
        for entry in sorted(
            fused.values(), key=lambda e: e["rrf_score"], reverse=True
        )
    ]

    return merged


# ─────────────────────────────────────────────────────────────────────────────
# 4. Main entry point
# ─────────────────────────────────────────────────────────────────────────────


async def retrieve_context(
    query: str,
    tenant_id: str,
    session: AsyncSession,
    top_k: int = 5,
) -> List[ChunkResult]:
    """
    Hybrid RAG retrieval: vector + BM25 → Reciprocal Rank Fusion → top_k chunks.

    Both retrievers run concurrently via asyncio.gather().  Results are fused
    with RRF (k=60) to produce a ranked list of the most contextually relevant
    chunks for the given query.

    Args:
        query:     User's natural-language question (Arabic or mixed language).
        tenant_id: Owning tenant UUID string — enforces data isolation.
        session:   Active AsyncSession (RLS context set internally by each sub-search).
        top_k:     Number of final chunks to return (default 5).

    Returns:
        List[ChunkResult] sorted by RRF score descending, length ≤ top_k.

    Example:
        chunks = await retrieve_context("ما هي شروط الضمان؟", tenant_id, db)
        context_block = "\\n\\n".join(c.content for c in chunks)
    """
    vector_results, bm25_results = await asyncio.gather(
        vector_search(query, tenant_id, session, top_k=20),
        bm25_search(query, tenant_id, session, top_k=20),
    )

    logger.info(
        "Retrieval complete — tenant=%s vector=%d bm25=%d",
        tenant_id, len(vector_results), len(bm25_results),
    )

    merged = reciprocal_rank_fusion(vector_results, bm25_results)
    top = merged[:top_k]

    logger.debug(
        "Top-%d chunks after RRF: %s",
        top_k, [f"{c.id[:8]}…(rrf={c.score:.4f})" for c in top],
    )

    return top
