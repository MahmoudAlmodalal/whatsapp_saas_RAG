import os
import asyncio
import chromadb
from openai import AsyncOpenAI
from app.config import get_settings

settings = get_settings()

def _split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return [c for c in chunks if c.strip()]

async def chunk_and_store(markdown: str, source_name: str, company_id: str) -> int:
    if not markdown.strip():
        return 0

    chunks = _split_text(markdown)
    if not chunks:
        return 0

    if not settings.OPENAI_API_KEY:
        return 0

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    batch_size = 50
    all_embeddings = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        resp = await client.embeddings.create(model=settings.EMBEDDING_MODEL, input=batch)
        all_embeddings.extend([item.embedding for item in resp.data])

    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    chroma = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    collection = chroma.get_or_create_collection(name=f"company_{company_id}")

    ids = [f"{source_name}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": source_name} for _ in chunks]

    try:
        collection.delete(where={"source": source_name})
    except Exception:
        pass

    collection.add(
        documents=chunks,
        embeddings=all_embeddings,
        ids=ids,
        metadatas=metadatas,
    )

    return len(chunks)

def chunk_and_store_sync(markdown: str, source_name: str, company_id: str) -> int:
    return asyncio.run(chunk_and_store(markdown, source_name, company_id))
