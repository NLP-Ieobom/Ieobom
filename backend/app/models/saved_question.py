import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedQuestion(Base):
    __tablename__ = "saved_question"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # 행이 있으면 저장된 상태, 없으면 저장 안 한 상태다.
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
