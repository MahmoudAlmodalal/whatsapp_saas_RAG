"""
tests/factories/document_factory.py
─────────────────────────────────────
DocumentFactory — generates test Document instances across all processing statuses.
"""
import uuid
import random
from datetime import datetime, timezone
import factory

from app.models.documents import Document, DocumentStatus

_ARABIC_DOCUMENT_NAMES = [
    "دليل المنتجات 2024.pdf",
    "سياسة الإرجاع والاستبدال.pdf",
    "الأسئلة الشائعة.docx",
    "كتالوج الخدمات.pdf",
    "شروط وأحكام الخدمة.txt",
    "قائمة الأسعار المحدثة.xlsx",
    "دليل المستخدم.pdf",
    "ملف المنتجات التفصيلي.docx",
]

_MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class DocumentFactory(factory.Factory):
    """Factory for generating Document instances."""

    class Meta:
        model = Document

    id = factory.LazyFunction(uuid.uuid4)
    tenant_id = factory.LazyFunction(uuid.uuid4)
    file_name = factory.LazyFunction(lambda: random.choice(_ARABIC_DOCUMENT_NAMES))
    file_type = factory.LazyFunction(
        lambda: random.choice(list(_MIME_TYPES.values()))
    )
    storage_path = factory.LazyFunction(
        lambda: f"uploads/{uuid.uuid4().hex}/document.pdf"
    )
    status = DocumentStatus.queued
    chunk_count = None
    uploaded_at = factory.LazyFunction(lambda: datetime.now(tz=timezone.utc))
    processed_at = None
    meta_data = factory.LazyFunction(lambda: {})

    class Params:
        """Status variants."""

        queued = factory.Trait(status=DocumentStatus.queued, chunk_count=None)
        processing = factory.Trait(status=DocumentStatus.processing, chunk_count=None)
        ready = factory.Trait(
            status=DocumentStatus.ready,
            chunk_count=factory.LazyFunction(lambda: random.randint(5, 50)),
            processed_at=factory.LazyFunction(lambda: datetime.now(tz=timezone.utc)),
        )
        failed = factory.Trait(
            status=DocumentStatus.failed,
            meta_data=factory.LazyFunction(
                lambda: {"ingestion_error": "فشل في معالجة الملف", "retry_count": 3}
            ),
        )
        pdf = factory.Trait(
            file_name="test_document.pdf",
            file_type="application/pdf",
        )
        docx = factory.Trait(
            file_name="test_document.docx",
            file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
