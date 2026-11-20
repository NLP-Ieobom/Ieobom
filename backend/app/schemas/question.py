import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.learning import CourseLink, EvidenceBlock, Explanation, ResearchTrend


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
    evidence_block_ids: list[str] = Field(default_factory=list)
    evidence_blocks: list[EvidenceBlock] = Field(default_factory=list)
    explanation: Explanation | None = None
    related_courses: list[CourseLink] = Field(default_factory=list)
    trends: list[ResearchTrend] = Field(default_factory=list)


class QuestionListResponse(BaseModel):
    questions: list[QuestionResponse]
