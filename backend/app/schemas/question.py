import uuid
from datetime import datetime

from pydantic import BaseModel


class QuestionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    question_type: str
    content: str
    recommended_reason: str
    prerequisite: str
    learning_order: str
    first_activity: str
    created_at: datetime
    is_saved: bool


class QuestionListResponse(BaseModel):
    questions: list[QuestionResponse]
