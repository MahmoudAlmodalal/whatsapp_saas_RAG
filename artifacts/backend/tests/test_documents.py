from uuid import UUID, uuid4
from unittest.mock import patch

import pytest
from fastapi import status
from sqlalchemy import select

from app.database import set_tenant_context
from app.models.document_chunks import DocumentChunk
from app.models.documents import Document, DocumentStatus
from app.models.tenants import Tenant
from tasks.ingestion_tasks import mark_document_processing

pytestmark = pytest.mark.asyncio


class FakeStorageService:
    def __init__(self, *, upload_error: Exception | None = None) -> None:
        self.uploaded: list[dict] = []
        self.deleted: list[str] = []
        self.upload_error = upload_error

    async def upload_bytes(self, *, path: str, data: bytes, content_type: str) -> None:
        if self.upload_error:
            raise self.upload_error

        self.uploaded.append(
            {
                "path": path,
                "data": data,
                "content_type": content_type,
            }
        )

    async def delete_object(self, *, path: str) -> None:
        self.deleted.append(path)


class ExistingSessionContext:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def fake_storage():
    storage = FakeStorageService()
    with patch("app.routers.documents.get_storage_service", return_value=storage):
        yield storage


@pytest.fixture
def failing_storage():
    storage = FakeStorageService(upload_error=RuntimeError("storage unavailable"))
    with patch("app.routers.documents.get_storage_service", return_value=storage):
        yield storage


@pytest.fixture
def mock_ingestion_delay():
    with patch("app.routers.documents.ingest_document.delay") as mock_delay:
        yield mock_delay


async def create_document(
    db_session,
    tenant_id,
    *,
    file_name: str = "catalog.pdf",
    status: DocumentStatus = DocumentStatus.queued,
) -> Document:
    document = Document(
        id=uuid4(),
        tenant_id=tenant_id,
        file_name=file_name,
        file_type=f".{file_name.rsplit('.', 1)[-1].lower()}",
        status=status,
        storage_path=f"tenant_{tenant_id}/existing/{file_name}",
    )
    await set_tenant_context(db_session, str(tenant_id))
    db_session.add(document)
    await db_session.commit()
    return document


async def test_upload_document_success_creates_record_and_enqueues_ingestion(
    client,
    db_session,
    test_tenant,
    admin_headers,
    fake_storage,
    mock_ingestion_delay,
):
    response = await client.post(
        f"/api/v1/tenants/{test_tenant.id}/documents",
        files={"file": ("قائمة الأسعار.pdf", b"hello arabic catalog", "application/pdf")},
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["file_name"] == "قائمة الأسعار.pdf"
    assert data["status"] == "queued"
    assert data["estimated_processing_time_s"] == 30

    await set_tenant_context(db_session, str(test_tenant.id))
    result = await db_session.execute(
        select(Document).where(Document.id == UUID(data["document_id"]))
    )
    document = result.scalar_one()

    assert document.tenant_id == test_tenant.id
    assert document.file_name == "قائمة الأسعار.pdf"
    assert document.file_type == ".pdf"
    assert document.status == DocumentStatus.queued
    assert document.storage_path.startswith(f"tenant_{test_tenant.id}/{document.id}/")

    assert fake_storage.uploaded[0]["path"] == document.storage_path
    assert fake_storage.uploaded[0]["data"] == b"hello arabic catalog"
    mock_ingestion_delay.assert_called_once_with(str(document.id), str(test_tenant.id))


async def test_upload_document_rejects_invalid_extension(
    client,
    test_tenant,
    admin_headers,
    fake_storage,
    mock_ingestion_delay,
):
    response = await client.post(
        f"/api/v1/tenants/{test_tenant.id}/documents",
        files={"file": ("malware.exe", b"bad", "application/octet-stream")},
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert fake_storage.uploaded == []
    mock_ingestion_delay.assert_not_called()


async def test_upload_document_rejects_oversized_file(
    client,
    test_tenant,
    admin_headers,
    fake_storage,
    mock_ingestion_delay,
    monkeypatch,
):
    monkeypatch.setattr("app.routers.documents.MAX_UPLOAD_BYTES", 10)

    response = await client.post(
        f"/api/v1/tenants/{test_tenant.id}/documents",
        files={"file": ("large.pdf", b"x" * 11, "application/pdf")},
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert fake_storage.uploaded == []
    mock_ingestion_delay.assert_not_called()


async def test_upload_document_storage_failure_does_not_create_record(
    client,
    db_session,
    test_tenant,
    admin_headers,
    failing_storage,
    mock_ingestion_delay,
):
    response = await client.post(
        f"/api/v1/tenants/{test_tenant.id}/documents",
        files={"file": ("catalog.pdf", b"hello", "application/pdf")},
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert failing_storage.uploaded == []
    mock_ingestion_delay.assert_not_called()

    await set_tenant_context(db_session, str(test_tenant.id))
    result = await db_session.execute(
        select(Document).where(Document.file_name == "catalog.pdf")
    )
    assert result.scalar_one_or_none() is None


async def test_upload_document_db_failure_deletes_uploaded_object(
    client,
    db_session,
    test_tenant,
    admin_headers,
    fake_storage,
    mock_ingestion_delay,
    monkeypatch,
):
    async def fail_commit():
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    with pytest.raises(RuntimeError, match="commit failed"):
        await client.post(
            f"/api/v1/tenants/{test_tenant.id}/documents",
            files={"file": ("rollback.pdf", b"hello", "application/pdf")},
            headers=admin_headers,
        )

    assert len(fake_storage.uploaded) == 1
    assert fake_storage.deleted == [fake_storage.uploaded[0]["path"]]
    mock_ingestion_delay.assert_not_called()


async def test_upload_document_forbidden_for_agent_and_operator(
    client,
    test_tenant,
    agent_headers,
    operator_headers,
    fake_storage,
    mock_ingestion_delay,
):
    for headers in (agent_headers, operator_headers):
        response = await client.post(
            f"/api/v1/tenants/{test_tenant.id}/documents",
            files={"file": ("catalog.pdf", b"hello", "application/pdf")},
            headers=headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    assert fake_storage.uploaded == []
    mock_ingestion_delay.assert_not_called()


async def test_upload_document_rejects_cross_tenant_path(
    client,
    admin_headers,
    fake_storage,
    mock_ingestion_delay,
):
    response = await client.post(
        f"/api/v1/tenants/{uuid4()}/documents",
        files={"file": ("catalog.pdf", b"hello", "application/pdf")},
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert fake_storage.uploaded == []
    mock_ingestion_delay.assert_not_called()


async def test_list_documents_is_tenant_scoped(
    client,
    db_session,
    test_tenant,
    admin_headers,
):
    tenant_document = await create_document(
        db_session,
        test_tenant.id,
        file_name="tenant-catalog.pdf",
    )

    other_tenant = Tenant(name="شركة ثانية", whatsapp_number="+966501111111")
    db_session.add(other_tenant)
    await db_session.commit()
    await db_session.refresh(other_tenant)
    await create_document(
        db_session,
        other_tenant.id,
        file_name="other-catalog.pdf",
    )

    response = await client.get(
        f"/api/v1/tenants/{test_tenant.id}/documents",
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert [item["id"] for item in data] == [str(tenant_document.id)]


async def test_list_documents_filters_by_status(
    client,
    db_session,
    test_tenant,
    admin_headers,
):
    ready_document = await create_document(
        db_session,
        test_tenant.id,
        file_name="ready.pdf",
        status=DocumentStatus.ready,
    )
    await create_document(
        db_session,
        test_tenant.id,
        file_name="queued.pdf",
        status=DocumentStatus.queued,
    )

    response = await client.get(
        f"/api/v1/tenants/{test_tenant.id}/documents?status=ready",
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert [item["id"] for item in data] == [str(ready_document.id)]
    assert data[0]["status"] == "ready"


async def test_delete_document_removes_storage_chunks_and_record(
    client,
    db_session,
    test_tenant,
    admin_headers,
    fake_storage,
):
    document = await create_document(db_session, test_tenant.id)
    chunk = DocumentChunk(
        id=uuid4(),
        tenant_id=test_tenant.id,
        document_id=document.id,
        content="نص تجريبي",
        embedding=[0.0] * 1024,
        meta_data={"chunk_index": 0},
    )
    await set_tenant_context(db_session, str(test_tenant.id))
    db_session.add(chunk)
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/tenants/{test_tenant.id}/documents/{document.id}",
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert fake_storage.deleted == [document.storage_path]

    await set_tenant_context(db_session, str(test_tenant.id))
    document_result = await db_session.execute(
        select(Document).where(Document.id == document.id)
    )
    chunk_result = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.id == chunk.id)
    )

    assert document_result.scalar_one_or_none() is None
    assert chunk_result.scalar_one_or_none() is None


async def test_ingestion_stub_marks_document_processing(
    db_session,
    test_tenant,
):
    document = await create_document(db_session, test_tenant.id)

    result = await mark_document_processing(
        str(document.id),
        str(test_tenant.id),
        session_factory=lambda: ExistingSessionContext(db_session),
    )

    assert result == {"status": "processing", "document_id": str(document.id)}

    await set_tenant_context(db_session, str(test_tenant.id))
    db_result = await db_session.execute(
        select(Document).where(Document.id == document.id)
    )
    updated_document = db_result.scalar_one()
    assert updated_document.status == DocumentStatus.processing
