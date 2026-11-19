import uuid
from datetime import datetime

from pydantic import BaseModel


class QuestionCreateRequest(BaseModel):
    content: str


class QuestionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    content: str
    created_at: datetime


class QuestionListResponse(BaseModel):
    questions: list[QuestionResponse]
