"""
app/routers/documents.py
────────────────────────
Tenant-admin document upload, listing, and deletion endpoints.
"""
from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.database import get_db
from app.models.document_chunks import DocumentChunk
from app.models.documents import Document, DocumentStatus
from app.models.user import User
from app.schemas.document import DocumentListItem, DocumentUploadResponse
from app.services.storage import get_storage_service
from tasks.ingestion_tasks import ingest_document

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".xlsx"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ESTIMATED_PROCESSING_TIME_S = 30


def _require_matching_tenant(path_tenant_id: UUID, user_tenant_id: UUID) -> None:
    if user_tenant_id != path_tenant_id:
        raise HTTPException(
            status_code=403,
            detail="لا تملك صلاحية الوصول لهذه الشركة",
        )


def _safe_file_name(file_name: str | None) -> str:
    if not file_name:
        raise HTTPException(status_code=400, detail="اسم الملف مطلوب")

    safe_name = Path(file_name.replace("\\", "/")).name.strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="اسم الملف مطلوب")

    return safe_name


def _validate_extension(file_name: str) -> str:
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="نوع الملف غير مدعوم. الأنواع المسموحة: pdf, docx, txt, xlsx",
        )
    return extension


async def _read_and_validate_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)

    if not data:
        raise HTTPException(status_code=400, detail="الملف فارغ")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="حجم الملف يتجاوز 50MB")

    return data


@router.post(
    "/{tenant_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=202,
)
async def upload_document(
    tenant_id: UUID,
    file: UploadFile = File(...),
    current_user_and_tenant: tuple[User, UUID] = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload a tenant document and enqueue asynchronous ingestion."""
    _, user_tenant_id = current_user_and_tenant
    _require_matching_tenant(tenant_id, user_tenant_id)

    file_name = _safe_file_name(file.filename)
    file_type = _validate_extension(file_name)
    file_bytes = await _read_and_validate_upload(file)

    document_id = uuid4()
    storage_path = f"tenant_{tenant_id}/{document_id}/{file_name}"
    content_type = file.content_type or "application/octet-stream"
    storage = get_storage_service()

    try:
        await storage.upload_bytes(
            path=storage_path,
            data=file_bytes,
            content_type=content_type,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="فشل رفع الملف إلى التخزين",
        ) from exc

    document = Document(
        id=document_id,
        tenant_id=tenant_id,
        file_name=file_name,
        file_type=file_type,
        status=DocumentStatus.queued,
        storage_path=storage_path,
    )

    try:
        db.add(document)
        await db.commit()
    except Exception:
        await db.rollback()
        try:
            await storage.delete_object(path=storage_path)
        except Exception:
            logger.warning(
                "Failed to clean up uploaded document after DB failure: %s",
                storage_path,
                exc_info=True,
            )
        raise

    ingest_document.delay(str(document_id), str(tenant_id))

    return DocumentUploadResponse(
        document_id=document.id,
        file_name=document.file_name,
        status=document.status,
        estimated_processing_time_s=ESTIMATED_PROCESSING_TIME_S,
    )


@router.get("/{tenant_id}/documents", response_model=list[DocumentListItem])
async def list_documents(
    tenant_id: UUID,
    document_status: DocumentStatus | None = Query(default=None, alias="status"),
    current_user_and_tenant: tuple[User, UUID] = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[Document]:
    """List documents for the authenticated tenant."""
    _, user_tenant_id = current_user_and_tenant
    _require_matching_tenant(tenant_id, user_tenant_id)

    query = select(Document).where(Document.tenant_id == tenant_id)
    if document_status is not None:
        query = query.where(Document.status == document_status)
    query = query.order_by(desc(Document.uploaded_at))

    result = await db.execute(query)
    return list(result.scalars().all())


@router.delete("/{tenant_id}/documents/{document_id}", status_code=204)
async def delete_document(
    tenant_id: UUID,
    document_id: UUID,
    current_user_and_tenant: tuple[User, UUID] = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a tenant document, its chunks, and its object-store blob."""
    _, user_tenant_id = current_user_and_tenant
    _require_matching_tenant(tenant_id, user_tenant_id)

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(status_code=404, detail="المستند غير موجود")

    storage = get_storage_service()

    try:
        await storage.delete_object(path=document.storage_path)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="فشل حذف الملف من التخزين",
        ) from exc

    await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.tenant_id == tenant_id,
        )
    )
    await db.delete(document)
    await db.commit()

    return Response(status_code=204)
