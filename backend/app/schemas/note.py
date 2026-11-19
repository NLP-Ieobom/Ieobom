import uuid

from pydantic import BaseModel


class NoteResponse(BaseModel):
    document_id: uuid.UUID
    page_number: int
    content: str | None


class NoteUpdateRequest(BaseModel):
    content: str
