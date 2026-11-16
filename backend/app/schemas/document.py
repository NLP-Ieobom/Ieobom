import uuid

from pydantic import BaseModel


class UploadUrlRequest(BaseModel):
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
