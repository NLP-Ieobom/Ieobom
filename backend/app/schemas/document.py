import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.progress import DocumentReadingProgress


class UploadUrlRequest(BaseModel):
    course_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int


class UploadUrlResponse(BaseModel):
    document_id: uuid.UUID
    upload_url: str
    s3_key: str
    expires_in: int


class CompleteResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    job_id: uuid.UUID


class StatusResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    job_status: str | None
    stage: str | None
    completed_pages: int | None
    total_pages: int | None
    stage_progress_percent: int | None
    attempt: int
    error_code: str | None
    error_message: str | None
    can_retry: bool
    next_retry_at: datetime | None


class RetryResponse(BaseModel):
    document_id: uuid.UUID
    job_id: uuid.UUID
    job_status: str


class FileUrlResponse(BaseModel):
    file_url: str
    expires_in: int


class DocumentSummary(BaseModel):
    document_id: uuid.UUID
    filename: str
    status: str
    created_at: datetime
    reading_progress: DocumentReadingProgress


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
