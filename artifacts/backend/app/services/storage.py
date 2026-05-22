"""
app/services/storage.py
───────────────────────
Storage backend abstraction for uploaded tenant documents.
"""
from __future__ import annotations

import asyncio
from typing import Protocol

from app.config import get_settings


class StorageService(Protocol):
    """Minimal object-storage interface used by the document router."""

    async def upload_bytes(
        self,
        *,
        path: str,
        data: bytes,
        content_type: str,
    ) -> None:
        """Upload a blob to the configured storage backend."""

    async def delete_object(self, *, path: str) -> None:
        """Delete a blob from the configured storage backend."""


class SupabaseStorageService:
    """Supabase Storage implementation using supabase-py."""

    def __init__(self, *, url: str, key: str, bucket: str) -> None:
        if not url or not key or not bucket:
            raise RuntimeError(
                "Supabase storage requires SUPABASE_URL, SUPABASE_KEY, and S3_BUCKET."
            )

        from supabase import create_client

        self._client = create_client(url, key)
        self._bucket = bucket

    async def upload_bytes(
        self,
        *,
        path: str,
        data: bytes,
        content_type: str,
    ) -> None:
        def _upload() -> None:
            self._client.storage.from_(self._bucket).upload(
                path=path,
                file=data,
                file_options={
                    "content-type": content_type,
                    "upsert": "true",
                },
            )

        await asyncio.to_thread(_upload)

    async def delete_object(self, *, path: str) -> None:
        def _delete() -> None:
            self._client.storage.from_(self._bucket).remove([path])

        await asyncio.to_thread(_delete)


class S3StorageService:
    """S3 or S3-compatible storage implementation using boto3."""

    def __init__(self, *, bucket: str, endpoint_url: str = "") -> None:
        if not bucket:
            raise RuntimeError("S3 storage requires S3_BUCKET.")

        import boto3

        kwargs = {"endpoint_url": endpoint_url} if endpoint_url else {}
        self._client = boto3.client("s3", **kwargs)
        self._bucket = bucket

    async def upload_bytes(
        self,
        *,
        path: str,
        data: bytes,
        content_type: str,
    ) -> None:
        def _upload() -> None:
            self._client.put_object(
                Bucket=self._bucket,
                Key=path,
                Body=data,
                ContentType=content_type,
            )

        await asyncio.to_thread(_upload)

    async def delete_object(self, *, path: str) -> None:
        def _delete() -> None:
            self._client.delete_object(Bucket=self._bucket, Key=path)

        await asyncio.to_thread(_delete)


def get_storage_service() -> StorageService:
    """FastAPI dependency factory for the configured storage backend."""
    settings = get_settings()
    backend = settings.STORAGE_BACKEND.lower()

    if backend == "supabase":
        return SupabaseStorageService(
            url=settings.SUPABASE_URL,
            key=settings.SUPABASE_KEY,
            bucket=settings.S3_BUCKET,
        )
    if backend == "s3":
        return S3StorageService(
            bucket=settings.S3_BUCKET,
            endpoint_url=settings.S3_ENDPOINT_URL,
        )

    raise RuntimeError("STORAGE_BACKEND must be either 'supabase' or 's3'.")
