"""
app/services/ingestion.py
──────────────────────────
Document ingestion pipeline for Arabic RAG system.

Stages (each a standalone function):
  1. extract_text        — PDF / DOCX / TXT / XLSX → raw string
  2. normalize_arabic    — Unicode normalization + dediacritization (CAMeL Tools)
  3. chunk_text          — Semantic chunking with token-aware overlap (tiktoken)
  4. generate_embeddings — multilingual-e5-large (1024-dim) via sentence-transformers
  5. store_chunks        — Bulk-insert DocumentChunk rows + update Document status

All heavy CPU work (extract / embed) runs in a thread pool so the async
event loop is never blocked.  Celery calls this via asyncio.run().
"""
from __future__ import annotations

import logging
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, set_tenant_context
from app.models.document_chunks import DocumentChunk
from app.models.documents import Document, DocumentStatus
from app.services.retrieval import invalidate_bm25_cache

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Lazy singletons — loaded once per Celery worker process
# ─────────────────────────────────────────────────────────────────────────────
_embedding_model = None


def _get_embedding_model():
    """Load sentence-transformers model once per worker process."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: intfloat/multilingual-e5-large")
        _embedding_model = SentenceTransformer("intfloat/multilingual-e5-large")
        logger.info("Embedding model loaded (dim=1024).")
    return _embedding_model


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — Text extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_text(file_path: str, file_type: str) -> str:
    """
    Extract raw text from a document file.

    Args:
        file_path: Absolute path to the downloaded file.
        file_type: MIME type or extension string (case-insensitive).

    Returns:
        Extracted text as a single string (UTF-8, Arabic-safe).

    Raises:
        ValueError: For unsupported file types.
    """
    ft = file_type.lower().strip()
    path = Path(file_path)

    # ── PDF ──────────────────────────────────────────────────────────────────
    if "pdf" in ft or path.suffix.lower() == ".pdf":
        import fitz  # PyMuPDF

        pages: list[str] = []
        with fitz.open(file_path) as doc:
            for page in doc:
                pages.append(page.get_text())
        return "\n\n".join(pages)

    # ── DOCX ─────────────────────────────────────────────────────────────────
    if "docx" in ft or "wordprocessingml" in ft or path.suffix.lower() == ".docx":
        from docx import Document as DocxDocument

        docx = DocxDocument(file_path)
        return "\n\n".join(p.text for p in docx.paragraphs if p.text.strip())

    # ── TXT / plain ──────────────────────────────────────────────────────────
    if "text/plain" in ft or path.suffix.lower() in (".txt", ".text", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")

    # ── XLSX ─────────────────────────────────────────────────────────────────
    if "xlsx" in ft or "spreadsheet" in ft or path.suffix.lower() in (".xlsx", ".xls"):
        import openpyxl

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        parts: list[str] = []
        for sheet in wb.worksheets:
            rows: list[str] = []
            for row in sheet.iter_rows(values_only=True):
                cells = [str(cell) if cell is not None else "" for cell in row]
                rows.append("\t".join(cells))
            parts.append(f"=== Sheet: {sheet.title} ===\n" + "\n".join(rows))
        wb.close()
        return "\n\n".join(parts)

    raise ValueError(
        f"Unsupported file type: {file_type!r}. "
        "Supported: PDF, DOCX, TXT, XLSX."
    )


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — Arabic text normalization
# ─────────────────────────────────────────────────────────────────────────────

def normalize_arabic_text(text: str) -> str:
    """
    Normalize Arabic text for consistent embedding.

    Steps:
      a. normalize_unicode  — alef/hamza/waw/ya variants → canonical forms
      b. dediac_ar          — remove tashkeel (short vowel diacritics)
      c. Collapse whitespace — multiple spaces/newlines → single space

    Non-Arabic content passes through unchanged.
    """
    from camel_tools.utils.dediac import dediac_ar
    from camel_tools.utils.normalize import normalize_unicode

    text = normalize_unicode(text)
    text = dediac_ar(text)
    # Collapse multiple whitespace characters into a single space
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — Semantic chunking
# ─────────────────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[str]:
    """
    Split text into overlapping token-aware semantic chunks.

    Strategy:
      1. Split on paragraph boundaries (double newline).
      2. Paragraphs longer than chunk_size are split at sentence boundaries
         (ASCII period, Arabic full stop ، or ؟).
      3. Small paragraphs are merged into a running chunk until chunk_size is reached.
      4. The last `overlap` tokens of the previous chunk are prepended to the next.

    Args:
        text:       Normalized input text.
        chunk_size: Target maximum size in tokens (cl100k_base encoding).
        overlap:    Number of tokens from the tail of the previous chunk to prepend.

    Returns:
        List of chunk strings.  Guaranteed non-empty for non-empty input.
    """
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")

    def token_count(s: str) -> int:
        return len(enc.encode(s))

    def decode_tokens(tokens: list[int]) -> str:
        return enc.decode(tokens)

    # ── Split on paragraph boundaries ────────────────────────────────────────
    raw_paragraphs = re.split(r"\n{2,}", text)
    paragraphs: list[str] = [p.strip() for p in raw_paragraphs if p.strip()]

    if not paragraphs:
        return []

    # ── Split oversized paragraphs at sentence boundaries ────────────────────
    sentence_boundary = re.compile(r"(?<=[.!?؟،])\s+")
    sentences: list[str] = []
    for para in paragraphs:
        if token_count(para) <= chunk_size:
            sentences.append(para)
        else:
            # Try sentence-level splits
            parts = sentence_boundary.split(para)
            sentences.extend([p.strip() for p in parts if p.strip()])

    # ── Merge sentences into chunks with overlap ──────────────────────────────
    chunks: list[str] = []
    current_tokens: list[int] = []
    prev_overlap_tokens: list[int] = []  # tail of last chunk for overlap

    for sentence in sentences:
        sent_tokens = enc.encode(sentence)

        # If a single sentence is already larger than chunk_size, emit it alone
        if len(sent_tokens) >= chunk_size:
            if current_tokens:
                chunks.append(decode_tokens(current_tokens))
            chunk_tokens = prev_overlap_tokens + sent_tokens
            chunks.append(decode_tokens(chunk_tokens))
            prev_overlap_tokens = sent_tokens[-overlap:] if overlap else []
            current_tokens = []
            continue

        # Would adding this sentence exceed the limit?
        prospective = len(prev_overlap_tokens) + len(current_tokens) + len(sent_tokens)
        if current_tokens and prospective > chunk_size:
            # Flush current chunk
            final_tokens = prev_overlap_tokens + current_tokens
            chunks.append(decode_tokens(final_tokens))
            prev_overlap_tokens = current_tokens[-overlap:] if overlap else []
            current_tokens = sent_tokens
        else:
            current_tokens.extend(sent_tokens)

    # Flush remaining tokens
    if current_tokens:
        final_tokens = prev_overlap_tokens + current_tokens
        chunks.append(decode_tokens(final_tokens))

    return chunks if chunks else [text[:4000]]  # Safety fallback


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4 — Embedding generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_embeddings(chunks: list[str]) -> list[list[float]]:
    """
    Generate 1024-dimensional embeddings using multilingual-e5-large.

    Each chunk is prefixed with "passage: " as required by E5 models.
    Batched at 32 for memory efficiency.

    Args:
        chunks: List of text chunks.

    Returns:
        List of 1024-dim float vectors, one per chunk.
    """
    model = _get_embedding_model()
    prefixed = [f"passage: {chunk}" for chunk in chunks]

    all_embeddings: list[list[float]] = []
    batch_size = 32
    for i in range(0, len(prefixed), batch_size):
        batch = prefixed[i : i + batch_size]
        vecs = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        all_embeddings.extend(vec.tolist() for vec in vecs)
        logger.debug("Encoded batch %d/%d", i // batch_size + 1,
                     (len(prefixed) + batch_size - 1) // batch_size)

    return all_embeddings


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 5 — Persist to PostgreSQL (pgvector)
# ─────────────────────────────────────────────────────────────────────────────

async def store_chunks(
    chunks: list[str],
    embeddings: list[list[float]],
    document_id: str,
    tenant_id: str,
    session: AsyncSession,
) -> None:
    """
    Bulk-insert DocumentChunk rows and update the parent Document.

    Uses SQLAlchemy bulk save objects (single INSERT round-trip).

    Args:
        chunks:      Text chunks from stage 3.
        embeddings:  Corresponding embedding vectors from stage 4.
        document_id: UUID string of the parent document.
        tenant_id:   UUID string of the owning tenant.
        session:     Active AsyncSession (tenant context already set).
    """
    doc_uuid = uuid.UUID(document_id)
    tenant_uuid = uuid.UUID(tenant_id)
    now = datetime.now(tz=timezone.utc)

    chunk_objects = [
        DocumentChunk(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            document_id=doc_uuid,
            content=chunk,
            embedding=embedding,
            meta_data={
                "chunk_index": idx,
                # rough page estimate: every ~3000 chars ≈ 1 page
                "page_estimate": max(1, len(chunk) // 3000 + 1),
            },
        )
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    # Bulk insert — single round-trip to DB
    session.add_all(chunk_objects)

    # Update parent document
    result = await session.execute(
        select(Document).where(
            Document.id == doc_uuid,
            Document.tenant_id == tenant_uuid,
        )
    )
    document = result.scalar_one()
    document.status = DocumentStatus.ready
    document.chunk_count = len(chunks)
    document.processed_at = now
    session.add(document)

    await session.commit()
    logger.info(
        "Stored %d chunks for document %s (tenant=%s)",
        len(chunks),
        document_id,
        tenant_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Storage download helper (sync — called from Celery worker thread)
# ─────────────────────────────────────────────────────────────────────────────

def download_file_to_temp(storage_path: str, file_name: str) -> str:
    """
    Download a file from the configured storage backend to a local temp path.

    Returns the temp file path (caller is responsible for cleanup).
    Uses boto3 (S3) or supabase-py depending on STORAGE_BACKEND setting.
    """
    from app.config import get_settings

    settings = get_settings()
    suffix = Path(file_name).suffix or ".tmp"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    tmp.close()

    backend = settings.STORAGE_BACKEND.lower()

    if backend == "s3":
        import boto3

        kwargs: dict[str, Any] = {}
        if settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
        s3 = boto3.client("s3", **kwargs)
        s3.download_file(settings.S3_BUCKET, storage_path, tmp_path)

    elif backend == "supabase":
        from supabase import create_client

        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        raw: bytes = client.storage.from_(settings.S3_BUCKET).download(storage_path)
        Path(tmp_path).write_bytes(raw)

    else:
        raise RuntimeError(
            f"Unsupported STORAGE_BACKEND: {settings.STORAGE_BACKEND!r}"
        )

    logger.info("Downloaded %r → %s (%d bytes)",
                storage_path, tmp_path, Path(tmp_path).stat().st_size)
    return tmp_path


# ─────────────────────────────────────────────────────────────────────────────
# Status helpers (async — for use inside the Celery task via asyncio.run)
# ─────────────────────────────────────────────────────────────────────────────

async def _update_document_status(
    document_id: str,
    tenant_id: str,
    status: DocumentStatus,
    error_message: str | None = None,
) -> None:
    """Set document.status and optionally store an error in metadata."""
    doc_uuid = uuid.UUID(document_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        result = await session.execute(
            select(Document).where(
                Document.id == doc_uuid,
                Document.tenant_id == tenant_uuid,
            )
        )
        document = result.scalar_one_or_none()
        if document is None:
            logger.warning("Document %s not found during status update.", document_id)
            return

        document.status = status
        if error_message:
            # Store error without overwriting other metadata
            try:
                meta = dict(document.meta_data or {})
            except Exception:
                meta = {}
            meta["ingestion_error"] = error_message[:2000]  # cap length
            document.meta_data = meta

        session.add(document)
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestration (async — called from the Celery task)
# ─────────────────────────────────────────────────────────────────────────────

async def run_ingestion_pipeline(document_id: str, tenant_id: str) -> dict[str, Any]:
    """
    Orchestrate all 5 ingestion stages for a single document.

    1. Fetch document metadata from DB.
    2. Download file from storage.
    3. Extract text.
    4. Normalize Arabic.
    5. Chunk.
    6. Embed.
    7. Store chunks + update document.

    Returns a summary dict on success.
    """
    import asyncio

    doc_uuid = uuid.UUID(document_id)
    tenant_uuid = uuid.UUID(tenant_id)
    tmp_path: str | None = None

    # ── Fetch document metadata ───────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        result = await session.execute(
            select(Document).where(
                Document.id == doc_uuid,
                Document.tenant_id == tenant_uuid,
            )
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise ValueError(f"Document {document_id} not found for tenant {tenant_id}.")

        storage_path = document.storage_path
        file_name = document.file_name
        file_type = document.file_type

    logger.info(
        "Starting ingestion pipeline: document=%s tenant=%s file=%r type=%r",
        document_id, tenant_id, file_name, file_type,
    )

    try:
        # ── Stage 1: Download + Extract (CPU — thread pool) ────────────────────
        tmp_path = await asyncio.to_thread(download_file_to_temp, storage_path, file_name)
        raw_text = await asyncio.to_thread(extract_text, tmp_path, file_type)
        logger.info("Extracted %d characters from %r.", len(raw_text), file_name)

        # ── Stage 2: Normalize Arabic ──────────────────────────────────────────
        normalized = await asyncio.to_thread(normalize_arabic_text, raw_text)
        logger.info("Text normalized (%d chars after normalization).", len(normalized))

        # ── Stage 3: Chunk ─────────────────────────────────────────────────────
        chunks = await asyncio.to_thread(chunk_text, normalized)
        logger.info("Created %d chunks.", len(chunks))

        if not chunks:
            raise ValueError("No chunks produced — document may be empty or unreadable.")

        # ── Stage 4: Embed (GPU/CPU — thread pool) ─────────────────────────────
        embeddings = await asyncio.to_thread(generate_embeddings, chunks)
        logger.info("Generated %d embeddings (dim=1024).", len(embeddings))

        # ── Stage 5: Store ─────────────────────────────────────────────────────
        async with AsyncSessionLocal() as session:
            await set_tenant_context(session, tenant_id)
            await store_chunks(chunks, embeddings, document_id, tenant_id, session)

        # ── Stage 6: Invalidate BM25 cache ────────────────────────────────────
        # Evict the stale per-tenant BM25 index so the next retrieve_context()
        # call rebuilds with the newly-added chunks included.
        await invalidate_bm25_cache(tenant_id)
        logger.info("BM25 cache invalidated for tenant %s after ingestion.", tenant_id)

        return {
            "status": "ready",
            "document_id": document_id,
            "tenant_id": tenant_id,
            "chunk_count": len(chunks),
            "file_name": file_name,
        }

    finally:
        # Always clean up the temp file
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass
