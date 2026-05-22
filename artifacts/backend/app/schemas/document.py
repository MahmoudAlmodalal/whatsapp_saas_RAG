from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.documents import DocumentStatus


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    file_name: str
    status: DocumentStatus
    estimated_processing_time_s: int


class DocumentListItem(BaseModel):
    id: UUID
    file_name: str
    file_type: str
    status: DocumentStatus
    chunk_count: int | None
    uploaded_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
