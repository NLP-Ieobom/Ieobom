import uuid
from datetime import datetime

from pydantic import BaseModel


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


class FileUrlResponse(BaseModel):
    file_url: str
    expires_in: int


class DocumentSummary(BaseModel):
    document_id: uuid.UUID
    filename: str
    status: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
