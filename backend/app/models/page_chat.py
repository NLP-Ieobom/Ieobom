import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PageChat(Base):
    __tablename__ = "page_chat"
    __table_args__ = (
        CheckConstraint(
            "answer_status IN ('answered', 'conversation', 'insufficient_evidence')",
            name="ck_page_chat_answer_status",
        ),
        Index("ix_page_chat_history", "user_id", "document_page_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    document_page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_page.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    answer_status: Mapped[str] = mapped_column(String(30))
    evidence_block_ids: Mapped[list[str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
