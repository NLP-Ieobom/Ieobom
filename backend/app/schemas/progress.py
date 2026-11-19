import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReadingProgress(BaseModel):
    viewed_pages: int
    total_pages: int | None
    progress_percent: float | None


class DocumentReadingProgress(ReadingProgress):
    last_page_number: int | None
    last_viewed_at: datetime | None


class DocumentProgressResponse(DocumentReadingProgress):
    document_id: uuid.UUID


class ProgressUpdateRequest(BaseModel):
    page_number: int = Field(ge=1)
