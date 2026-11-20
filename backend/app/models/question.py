import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# AI가 페이지마다 미리 만들어 두는 질문이다. 학생은 저장 여부만 바꾼다 (saved_question).
class Question(Base):
    __tablename__ = "question"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_page.id"))
    question_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    recommended_reason: Mapped[str] = mapped_column(Text)
    prerequisite: Mapped[str] = mapped_column(Text)
    learning_order: Mapped[str] = mapped_column(Text)
    first_activity: Mapped[str] = mapped_column(Text)
    evidence_block_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    evidence_blocks: Mapped[list[dict]] = mapped_column(JSONB, default=list, server_default="[]")
    explanation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    related_courses: Mapped[list[dict]] = mapped_column(JSONB, default=list, server_default="[]")
    trends: Mapped[list[dict]] = mapped_column(JSONB, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
